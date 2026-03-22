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
}

ENTITY_ALIASES = {
    "service provider": "provider",
    "vendor": "provider",
    "supplier": "provider",
    "client": "customer",
    "customer": "customer",
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

                    await session.run(
                        """
                        MERGE (n:Entity {id: $id})
                        SET n.type = coalesce(n.type, $type),
                            n.confidence = coalesce(n.confidence, $confidence)
                        WITH n
                        MATCH (d:Document {id: $document_id})
                        MERGE (d)-[:HAS_ENTITY]->(n)
                        """,
                        id=self.normalize_entity(node.id),
                        type=node.type,
                        document_id=document_id,
                        confidence=0.8,
                    )
                    stored_nodes += 1

                for rel in graph_doc.relationships:
                    if not rel.source or not rel.target:
                        continue

                    rel_type = rel.type.upper().replace(" ", "_")
                    if rel_type not in ALLOWED_REL_TYPES:
                        logger.warning(f"Dropped unsupported relationship type: {rel.type}")
                        continue

                    await session.run(
                        f"""
                        MATCH (s:Entity {{id: $source}})
                        MATCH (t:Entity {{id: $target}})
                        MATCH (d:Document {{id: $document_id}})
                        WITH s, t, d
                        WHERE s IS NOT NULL AND t IS NOT NULL
                        MERGE (s)-[r:{rel_type} {{doc_id: $document_id}}]->(t)
                        SET r.confidence = coalesce(r.confidence, $confidence)
                        """,
                        source=self.normalize_entity(rel.source.id),
                        target=self.normalize_entity(rel.target.id),
                        document_id=document_id,
                        confidence=0.8,
                    )
                    stored_rels += 1

        logger.info(f"Stored {stored_nodes} nodes and {stored_rels} relationships")
