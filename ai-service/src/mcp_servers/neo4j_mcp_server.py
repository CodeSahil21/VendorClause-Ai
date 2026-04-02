"""Neo4j MCP Server — Graph traversal and entity extraction.

FastAPI app exposing two tools over SSE + HTTP:
- graph_traverse(entity_names, document_id, relationship_types, depth)
- extract_entity(entity_name, document_id)

Standalone process listens on port 8002, streams results via SSE.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.shared.neo4j_service import Neo4jService
from src.shared.settings import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Neo4jMCPServer:
    def __init__(self):
        self.neo4j = Neo4jService()

    async def graph_traverse(
        self,
        entity_names: list[str],
        document_id: str,
        relationship_types: list[str] = None,
        depth: int = 2,
    ) -> list[dict]:
        """Traverse entity relationships in Neo4j graph.

        Returns list of {source_chunk_id, source_entity, relationship, target_entity, target_chunk_id}.
        """
        if relationship_types is None:
            relationship_types = []

        logger.info(
            f"Graph traverse: entities={entity_names}, doc={document_id}, "
            f"rel_types={relationship_types}, depth={depth}"
        )

        results = []

        try:
            async with self.neo4j.driver.session() as session:
                normalized_names = [self.neo4j.normalize_entity(n) for n in entity_names]

                # Use generic relationship pattern — ingestion stores typed edges
                # (HAS_CLAUSE, OWES_PAYMENT etc.), not a generic RELATES type.
                # rel_types passed as Cypher parameter to avoid injection.
                cypher = f"""
                MATCH (e:Entity {{document_id: $doc_id}})
                WHERE e.id IN $entity_names
                MATCH (e)-[r*1..{depth}]-(connected:Entity)
                WHERE $rel_types = [] OR type(r[-1]) IN $rel_types
                RETURN
                    e.chunk_id        AS source_chunk_id,
                    e.id              AS source_entity,
                    type(r[-1])       AS relationship_type,
                    connected.id      AS target_entity,
                    connected.chunk_id AS target_chunk_id
                LIMIT 50
                """

                query_result = await session.run(
                    cypher,
                    {
                        "doc_id": document_id,
                        "entity_names": normalized_names,
                        "rel_types": relationship_types,
                    },
                )

                records = await query_result.data()

                for record in records:
                    results.append({
                        "source_chunk_id": record.get("source_chunk_id"),
                        "source_entity": record.get("source_entity"),
                        "relationship": record.get("relationship_type"),
                        "target_entity": record.get("target_entity"),
                        "target_chunk_id": record.get("target_chunk_id"),
                    })

                logger.info(f"Graph traverse found {len(results)} connections")

        except Exception as e:
            logger.error(f"Graph traverse error: {e}")

        return results

    async def extract_entity(
        self,
        entity_name: str,
        document_id: str,
    ) -> list[dict]:
        """Extract entity properties and connected chunk_ids.

        Returns list of {entity_type, chunk_id, properties, connected_chunk_ids}.
        """
        logger.info(f"Extract entity: {entity_name} from doc={document_id}")

        results = []

        try:
            async with self.neo4j.driver.session() as session:
                normalized_name = self.neo4j.normalize_entity(entity_name)

                cypher = """
                MATCH (e:Entity {id: $entity_id, document_id: $doc_id})
                OPTIONAL MATCH (e)-[r]-(connected:Entity)
                RETURN
                    e.type                        AS entity_type,
                    e.chunk_id                    AS chunk_id,
                    e.clause_type                 AS clause_type,
                    e.importance                  AS importance,
                    collect(DISTINCT connected.chunk_id) AS connected_chunk_ids
                """

                query_result = await session.run(
                    cypher,
                    {"entity_id": normalized_name, "doc_id": document_id},
                )

                records = await query_result.data()

                for record in records:
                    results.append({
                        "entity_type": record.get("entity_type"),
                        "chunk_id": record.get("chunk_id"),
                        "clause_type": record.get("clause_type"),
                        "importance": record.get("importance"),
                        "connected_chunk_ids": record.get("connected_chunk_ids", []),
                    })

                logger.info(f"Extract entity found {len(results)} results")

        except Exception as e:
            logger.error(f"Extract entity error: {e}")

        return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Neo4j MCP Server...")
    await server.neo4j._ensure_indexes()
    yield
    logger.info("Shutting down Neo4j MCP Server...")
    await server.neo4j.close()


app = FastAPI(title="Neo4j MCP Server", lifespan=lifespan)
server = Neo4jMCPServer()


@app.get("/sse")
async def sse_connect():
    async def event_stream():
        yield "data: " + json.dumps({"type": "session_start"}) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/messages")
async def handle_messages(request: dict):
    """Handle MCP tool call requests.

    Expected request format:
    {
      "tool": "graph_traverse" | "extract_entity",
      "params": {...}
    }
    """
    tool_name = request.get("tool")
    params = request.get("params", {})

    logger.info(f"Tool call: {tool_name} with params={params}")

    try:
        if tool_name == "graph_traverse":
            results = await server.graph_traverse(**params)
        elif tool_name == "extract_entity":
            results = await server.extract_entity(**params)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        return {"success": True, "results": results}
    except Exception as e:
        logger.error(f"Error in {tool_name}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("NEO4J_MCP_PORT", 8002)),
        log_level="info",
    )
