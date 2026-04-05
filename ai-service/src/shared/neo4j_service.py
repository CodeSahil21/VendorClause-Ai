# Standard library
import logging
import re

# Third-party
from neo4j import AsyncGraphDatabase

# Local
from src.ingestion.constants import ENTITY_ALIASES
from src.shared.settings import settings

logger = logging.getLogger(__name__)

ALLOWED_REL_TYPES = {
    "HAS_CLAUSE",
    "HAS_OBLIGATION",
    "OWES_PAYMENT",
    "PROVIDES_SERVICE",
    "CAN_TERMINATE",
    "LIMITS_LIABILITY",
    "GOVERNS",
    "EFFECTIVE_ON",
    "DEFINES",
    "COMPLIES_WITH",
    "APPLIES_TO",
}

class Neo4jService:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            notifications_min_severity="WARNING",
        )
        self._indexes_created = False

    async def close(self) -> None:
        await self.driver.close()

    def normalize_entity(self, name: str) -> str:
        name = re.sub(r"[^a-z0-9 ]", "", str(name).lower().strip())
        return ENTITY_ALIASES.get(name, name)

    async def _ensure_indexes(self) -> None:
        if self._indexes_created:
            return
        async with self.driver.session() as session:
            await session.run("CREATE INDEX entity_id IF NOT EXISTS FOR (n:Entity) ON (n.id);")
            await session.run("CREATE INDEX entity_id_doc IF NOT EXISTS FOR (n:Entity) ON (n.id, n.document_id);")
            await session.run("CREATE INDEX document_id IF NOT EXISTS FOR (d:Document) ON (d.id);")
            await session.run("CREATE INDEX chunk_id IF NOT EXISTS FOR (n:Entity) ON (n.chunk_id);")
        self._indexes_created = True
        logger.info("Neo4j indexes ensured")

    async def create_document_node(self, document_id: str, metadata: dict) -> None:
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (d:Document {id: $document_id})
                SET d.doc_type = $doc_type, d.created_at = datetime()
                """,
                document_id=document_id,
                doc_type=metadata.get("type", "Unknown"),
            )
        logger.info(f"Document node created: {document_id}")

    async def store_graph_documents(self, graph_documents: list, document_id: str) -> None:
        await self._ensure_indexes()

        node_rows: list[dict] = []
        rel_rows_by_type: dict[str, list[dict]] = {}

        for graph_doc in graph_documents:
            for node in graph_doc.nodes:
                if not node.id or len(str(node.id).strip()) < 2:
                    continue

                props = getattr(node, "properties", {}) or {}
                node_rows.append(
                    {
                        "id": self.normalize_entity(node.id),
                        "type": node.type,
                        "confidence": 0.8,
                        "chunk_id": props.get("chunk_id"),
                        "document_id": props.get("document_id") or document_id,
                        "clause_type": props.get("clause_type"),
                        "importance": props.get("importance"),
                    }
                )

            for rel in graph_doc.relationships:
                if not rel.source or not rel.target:
                    continue

                rel_type = rel.type.upper().replace(" ", "_")
                if rel_type not in ALLOWED_REL_TYPES:
                    logger.warning(f"Dropped unsupported relationship type: {rel.type}")
                    continue

                rel_props = getattr(rel, "properties", {}) or {}
                rel_rows_by_type.setdefault(rel_type, []).append(
                    {
                        "source": self.normalize_entity(rel.source.id),
                        "target": self.normalize_entity(rel.target.id),
                        "document_id": document_id,
                        "confidence": 0.8,
                        "chunk_id": rel_props.get("chunk_id"),
                        "rel_document_id": rel_props.get("document_id"),
                    }
                )

        async with self.driver.session() as session:
            if node_rows:
                await session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:Entity {id: row.id, document_id: row.document_id})
                    SET n.type = coalesce(n.type, row.type),
                        n.confidence = coalesce(n.confidence, row.confidence),
                        n.chunk_id = coalesce(row.chunk_id, n.chunk_id),
                        n.document_id = coalesce(row.document_id, n.document_id),
                        n.clause_type = coalesce(row.clause_type, n.clause_type),
                        n.importance = coalesce(row.importance, n.importance)
                    WITH n
                    MATCH (d:Document {id: $doc_id})
                    MERGE (d)-[:HAS_ENTITY]->(n)
                    """,
                    rows=node_rows,
                    doc_id=document_id,
                )

            for rel_type, rows in rel_rows_by_type.items():
                await session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (s:Entity {{id: row.source, document_id: row.document_id}})
                    MATCH (t:Entity {{id: row.target, document_id: row.document_id}})
                    MATCH (d:Document {{id: row.document_id}})
                    WITH s, t, d, row
                    WHERE s IS NOT NULL AND t IS NOT NULL
                    MERGE (s)-[r:{rel_type} {{doc_id: row.document_id}}]->(t)
                    SET r.confidence = coalesce(r.confidence, row.confidence),
                        r.chunk_id = row.chunk_id,
                        r.rel_document_id = row.rel_document_id
                    """,
                    rows=rows,
                )

        stored_nodes = len(node_rows)
        stored_rels = sum(len(rows) for rows in rel_rows_by_type.values())
        logger.info(f"Stored {stored_nodes} nodes and {stored_rels} relationships")
