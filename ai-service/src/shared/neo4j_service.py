import logging
import re

from neo4j import AsyncGraphDatabase

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

ENTITY_ALIASES = {
    "service provider": "provider",
    "vendor": "provider",
    "supplier": "provider",
    "client": "customer",
    "customer": "customer",
    "buyer": "customer",
    "purchaser": "customer",
    "company": "company",
}


class Neo4jService:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
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

        stored_nodes = 0
        stored_rels = 0

        async with self.driver.session() as session:
            for graph_doc in graph_documents:
                for node in graph_doc.nodes:
                    if not node.id or len(str(node.id).strip()) < 2:
                        continue

                    # Extract bridge properties from node
                    props = getattr(node, "properties", {}) or {}

                    await session.run(
                        """
                        MERGE (n:Entity {id: $id})
                        SET n.type = coalesce(n.type, $type),
                            n.confidence = coalesce(n.confidence, $confidence),
                            n.chunk_id = $chunk_id,
                            n.document_id = $document_id,
                            n.clause_type = $clause_type,
                            n.importance = $importance
                        WITH n
                        MATCH (d:Document {id: $doc_id})
                        MERGE (d)-[:HAS_ENTITY]->(n)
                        """,
                        id=self.normalize_entity(node.id),
                        type=node.type,
                        doc_id=document_id,
                        confidence=0.8,
                        chunk_id=props.get("chunk_id"),
                        document_id=props.get("document_id"),
                        clause_type=props.get("clause_type"),
                        importance=props.get("importance"),
                    )
                    stored_nodes += 1

                for rel in graph_doc.relationships:
                    if not rel.source or not rel.target:
                        continue

                    rel_type = rel.type.upper().replace(" ", "_")
                    if rel_type not in ALLOWED_REL_TYPES:
                        logger.warning(f"Dropped unsupported relationship type: {rel.type}")
                        continue

                    # Extract bridge properties from relationship
                    rel_props = getattr(rel, "properties", {}) or {}

                    await session.run(
                        f"""
                        MATCH (s:Entity {{id: $source}})
                        MATCH (t:Entity {{id: $target}})
                        MATCH (d:Document {{id: $document_id}})
                        WITH s, t, d
                        WHERE s IS NOT NULL AND t IS NOT NULL
                        MERGE (s)-[r:{rel_type} {{doc_id: $document_id}}]->(t)
                        SET r.confidence = coalesce(r.confidence, $confidence),
                            r.chunk_id = $chunk_id,
                            r.rel_document_id = $rel_document_id
                        """,
                        source=self.normalize_entity(rel.source.id),
                        target=self.normalize_entity(rel.target.id),
                        document_id=document_id,
                        confidence=0.8,
                        chunk_id=rel_props.get("chunk_id"),
                        rel_document_id=rel_props.get("document_id"),
                    )
                    stored_rels += 1

        logger.info(f"Stored {stored_nodes} nodes and {stored_rels} relationships")
