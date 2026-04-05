"""Neo4j MCP Server — Graph traversal and entity extraction.

FastAPI app exposing two tools over SSE + HTTP:
- graph_traverse(entity_names, document_id, relationship_types, depth)
- extract_entity(entity_name, document_id)

Standalone process listens on port 8002, streams results via SSE.
"""

# Standard library
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Path bootstrap — must happen before any local imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Third-party
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Local
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

        # Validate and clamp depth before interpolating into Cypher.
        # Neo4j does not support parameterized variable-length path lengths.
        depth = max(1, min(int(depth), 5))  # Clamp to 1-5

        logger.info(
            f"Graph traverse: entities={entity_names}, doc={document_id}, "
            f"rel_types={relationship_types}, depth={depth}"
        )

        results = []

        try:
            async with self.neo4j.driver.session() as session:
                normalized_names = [self.neo4j.normalize_entity(n) for n in entity_names]

                if depth == 1:
                    cypher = """
                    MATCH (d:Document {id: $doc_id})-[:HAS_ENTITY]->(e:Entity)
                    WHERE e.id IN $entity_names
                    MATCH (e)-[r]->(connected:Entity)
                    WHERE connected.document_id = $doc_id
                      AND ($rel_types = [] OR type(r) IN $rel_types)
                                        RETURN DISTINCT
                        e.chunk_id         AS source_chunk_id,
                        e.id               AS source_entity,
                        type(r)            AS relationship_type,
                        connected.id       AS target_entity,
                        connected.chunk_id AS target_chunk_id
                    LIMIT 50
                    """
                else:
                    cypher = f"""
                    MATCH (d:Document {{id: $doc_id}})-[:HAS_ENTITY]->(e:Entity)
                    WHERE e.id IN $entity_names
                    MATCH path = (e)-[*1..{depth}]-(connected:Entity)
                                        WHERE connected.document_id = $doc_id
                                            AND ALL(n IN nodes(path) WHERE n.document_id = $doc_id OR n = e)
                    UNWIND relationships(path) AS r
                                        WITH e, r, endNode(r) AS tgt
                                        WHERE tgt.document_id = $doc_id
                                            AND ($rel_types = [] OR type(r) IN $rel_types)
                                        RETURN DISTINCT
                        e.chunk_id         AS source_chunk_id,
                        e.id               AS source_entity,
                        type(r)            AS relationship_type,
                                                tgt.id             AS target_entity,
                                                tgt.chunk_id       AS target_chunk_id
                    LIMIT 50
                    """

                try:
                    async def _run_traverse():
                        r = await session.run(
                            cypher,
                            {
                                "doc_id": document_id,
                                "entity_names": normalized_names,
                                "rel_types": relationship_types,
                            },
                        )
                        return await r.data()

                    records = await asyncio.wait_for(_run_traverse(), timeout=30)
                except asyncio.TimeoutError:
                    logger.error(f"Graph traverse timeout for {entity_names}")
                    raise

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
            logger.error(f"Graph traverse error: {e}", exc_info=True)
            raise

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
                MATCH (d:Document {id: $doc_id})-[:HAS_ENTITY]->(e:Entity {id: $entity_id})
                OPTIONAL MATCH (e)-[r]-(connected:Entity)
                WITH e, connected
                WHERE connected IS NULL OR connected.document_id = $doc_id
                RETURN
                    e.type                        AS entity_type,
                    e.chunk_id                    AS chunk_id,
                    e.clause_type                 AS clause_type,
                    e.importance                  AS importance,
                    collect(DISTINCT connected.chunk_id) AS connected_chunk_ids
                """

                async def _run_extract():
                    query_result = await session.run(
                        cypher,
                        {"entity_id": normalized_name, "doc_id": document_id},
                    )
                    return await query_result.data()

                records = await asyncio.wait_for(_run_extract(), timeout=30)

                for record in records:
                    connected_ids = record.get("connected_chunk_ids", [])
                    results.append({
                        "entity_type": record.get("entity_type"),
                        "chunk_id": record.get("chunk_id"),
                        "clause_type": record.get("clause_type"),
                        "importance": record.get("importance"),
                        "connected_chunk_ids": [cid for cid in connected_ids if cid is not None],
                    })

                logger.info(f"Extract entity found {len(results)} results")

        except Exception as e:
            logger.error(f"Extract entity error: {e}")

        return results

    async def delete_document_graph(self, document_id: str) -> dict:
        """Delete document node and all document-scoped entities/relationships."""
        logger.info(f"Deleting Neo4j graph for doc={document_id}")

        async with self.neo4j.driver.session() as session:
            # Delete document and linked entities first.
            await session.run(
                """
                MATCH (d:Document {id: $doc_id})
                OPTIONAL MATCH (d)-[:HAS_ENTITY]->(e:Entity)
                DETACH DELETE d, e
                """,
                {"doc_id": document_id},
            )

            # Defensive cleanup for any remaining document-scoped entities.
            await session.run(
                """
                MATCH (e:Entity {document_id: $doc_id})
                DETACH DELETE e
                """,
                {"doc_id": document_id},
            )

        return {"deleted": True, "document_id": document_id}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Neo4j MCP Server...")
    await server.neo4j._ensure_indexes()
    yield
    logger.info("Shutting down Neo4j MCP Server...")
    await server.neo4j.close()


app = FastAPI(title="Neo4j MCP Server", lifespan=lifespan)
server = Neo4jMCPServer()
allowed_origins = [origin.strip() for origin in settings.mcp_allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


async def verify_auth(request: Request):
    """Check X-API-Key header for MCP tool invocations."""
    client_host = request.client.host if request.client else "unknown"
    if settings.mcp_allow_local_bypass and client_host in ("127.0.0.1", "localhost"):
        return

    api_key = request.headers.get("X-API-Key")
    expected_key = settings.mcp_auth_key
    if not expected_key:
        raise HTTPException(status_code=503, detail="MCP auth key is not configured")
    if not api_key or api_key != expected_key:
        raise HTTPException(status_code=403, detail="Unauthorized")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Apply auth to /messages endpoint."""
    if request.url.path == "/messages":
        try:
            await verify_auth(request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"success": False, "error": str(e.detail)})
    return await call_next(request)


@app.get("/sse")
async def sse_connect():
    return JSONResponse(
        status_code=501,
        content={"success": False, "error": "SSE is not enabled on this server. Use POST /messages."},
    )


@app.post("/messages")
async def handle_messages(request: dict):
    """Handle MCP tool call requests.

        Expected request format:
    {
            "tool": "graph_traverse" | "extract_entity" | "delete_document_graph",
      "params": {...}
    }
    """
    tool_name = request.get("tool")
    params = request.get("params", {})

    if not tool_name:
        return {"success": False, "error": "Missing 'tool' field"}

    logger.info(f"Tool call: {tool_name} with params={params}")

    try:
        if tool_name == "graph_traverse":
            if not params.get("entity_names") or not params.get("document_id"):
                return {"success": False, "error": "Missing required params: entity_names, document_id"}
            results = await server.graph_traverse(**params)
        elif tool_name == "extract_entity":
            if not params.get("entity_name") or not params.get("document_id"):
                return {"success": False, "error": "Missing required params: entity_name, document_id"}
            results = await server.extract_entity(**params)
        elif tool_name == "delete_document_graph":
            if not params.get("document_id"):
                return {"success": False, "error": "Missing required param: document_id"}
            results = await server.delete_document_graph(**params)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        return {"success": True, "results": results}
    except asyncio.TimeoutError:
        logger.error(f"Timeout in {tool_name}")
        return {"success": False, "error": "Request timeout", "tool": tool_name}
    except Exception as e:
        logger.error(f"Error in {tool_name}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "tool": tool_name}


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
