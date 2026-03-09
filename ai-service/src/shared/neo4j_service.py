import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import AsyncGraphDatabase
from src.shared.settings import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jService:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
    
    def normalize_entity(self, name: str) -> str:
        """Normalize entity names to avoid duplicates"""
        name = str(name).lower().strip()
        
        mapping = {
            "service provider": "Provider",
            "vendor": "Provider",
            "supplier": "Provider",
            "the vendor": "Provider",
            "client": "Customer",
            "customer": "Customer",
            "the client": "Customer"
        }
        
        return mapping.get(name, name.title())
    
    async def close(self):
        await self.driver.close()
    
    async def store_graph_documents(self, graph_documents, document_id: str):
        """Store extracted graph entities and relationships in Neo4j"""
        stored_nodes = 0
        stored_rels = 0
        
        async with self.driver.session() as session:
            for graph_doc in graph_documents:
                # Store nodes with validation
                for node in graph_doc.nodes:
                    # Skip if node has no meaningful content
                    if not node.id or len(str(node.id).strip()) < 2:
                        logger.warning(f"⚠️  Skipping invalid node: {node.id}")
                        continue
                    
                    # Normalize entity name
                    normalized_id = self.normalize_entity(node.id)
                    
                    await session.run(
                        """
                        MERGE (n:Entity {id: $id})
                        SET n.type = $type,
                            n.document_id = $document_id,
                            n.confidence = $confidence
                        """,
                        id=normalized_id,
                        type=node.type,
                        document_id=document_id,
                        confidence=0.8
                    )
                    stored_nodes += 1
                
                # Store relationships with validation
                for rel in graph_doc.relationships:
                    # Skip if relationship is invalid
                    if not rel.source or not rel.target:
                        logger.warning(f"⚠️  Skipping invalid relationship")
                        continue
                    
                    # Normalize entity names
                    normalized_source = self.normalize_entity(rel.source.id)
                    normalized_target = self.normalize_entity(rel.target.id)
                    
                    await session.run(
                        """
                        MATCH (source:Entity {id: $source_id})
                        MATCH (target:Entity {id: $target_id})
                        MERGE (source)-[r:RELATES {type: $rel_type}]->(target)
                        SET r.document_id = $document_id,
                            r.confidence = $confidence
                        """,
                        source_id=normalized_source,
                        target_id=normalized_target,
                        rel_type=rel.type,
                        document_id=document_id,
                        confidence=0.8
                    )
                    stored_rels += 1
        
        logger.info(f"✅ Stored {stored_nodes} nodes and {stored_rels} relationships in Neo4j")
    
    async def create_document_node(self, document_id: str, metadata: dict):
        """Create a document node in Neo4j"""
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (d:Document {id: $document_id})
                SET d.doc_type = $doc_type,
                    d.created_at = datetime()
                """,
                document_id=document_id,
                doc_type=metadata.get("type", "Unknown")
            )
        
        logger.info(f"✅ Created document node in Neo4j: {document_id}")
