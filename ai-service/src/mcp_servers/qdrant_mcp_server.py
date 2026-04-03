"""Qdrant MCP Server — Vector search and metadata filtering.

FastAPI app exposing two tools over SSE + HTTP:
- vector_search(query_text, document_id, clause_types, top_k, use_sparse)
- metadata_filter(document_id, importance_gte, clause_types)

Standalone process listens on port 8001, streams results via SSE.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastembed import SparseTextEmbedding
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, VectorParams

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.shared.settings import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class QdrantMCPServer:
    def __init__(self):
        self.qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = "legal_contracts_hybrid"

        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
        )

        self.sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

    async def ensure_collection(self) -> None:
        if not await self.qdrant.collection_exists(self.collection_name):
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            )
            logger.info(f"Created collection {self.collection_name}")

    async def vector_search(
        self,
        query_text: str,
        document_id: str,
        clause_types: list[str] = None,
        top_k: int = 10,
        use_sparse: bool = True,
    ) -> list[dict]:
        """Search Qdrant using dense + sparse (hybrid) vectors.

        Returns list of {chunk_id, text, score_dense, score_sparse, clause_type, importance}.
        Scores from both paths are returned separately for RRF fusion in retrieval layer.
        """
        if clause_types is None:
            clause_types = []

        logger.info(f"Searching: query={query_text[:50]}, doc={document_id}, top_k={top_k}")

        # Embed query (parallel)
        dense_vec, sparse_result = await asyncio.gather(
            asyncio.to_thread(self.embedding_model.embed_query, query_text),
            asyncio.to_thread(lambda q=query_text: list(self.sparse_model.embed([q]))),
            return_exceptions=True,
        )

        # Handle errors
        if isinstance(dense_vec, Exception):
            logger.error(f"Dense embedding error: {dense_vec}")
            raise dense_vec
        if isinstance(sparse_result, Exception):
            logger.error(f"Sparse embedding error: {sparse_result}")
            raise sparse_result

        sparse_vec = sparse_result[0]

        must_filters = [
            models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))
        ]
        if clause_types:
            must_filters.append(
                models.FieldCondition(key="clause_type", match=models.MatchAny(any=clause_types))
            )

        qdrant_filter = models.Filter(must=must_filters)
        results_by_id = {}  # Track scores from both paths

        if use_sparse:
            # Parallel searches: dense + sparse simultaneously
            search_tasks = [
                self.qdrant.search(
                    collection_name=self.collection_name,
                    query_vector=("sparse", models.SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist(),
                    )),
                    limit=top_k * 2,  # Over-fetch for RRF fusion
                    query_filter=qdrant_filter,
                    timeout=30,  # 30s timeout
                ),
                self.qdrant.search(
                    collection_name=self.collection_name,
                    query_vector=("dense", dense_vec),
                    limit=top_k * 2,
                    query_filter=qdrant_filter,
                    timeout=30,
                ),
            ]

            try:
                sparse_results, dense_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                if isinstance(sparse_results, Exception):
                    logger.error(f"Sparse search error: {sparse_results}")
                    raise sparse_results
                if isinstance(dense_results, Exception):
                    logger.error(f"Dense search error: {dense_results}")
                    raise dense_results
            except Exception as e:
                logger.error(f"Search error: {e}")
                raise

            # Combine results: preserve both scores for RRF fusion layer
            for rank, result in enumerate(sparse_results):
                cid = result.id
                if cid not in results_by_id:
                    results_by_id[cid] = {
                        "chunk_id": result.payload.get("chunk_id"),
                        "text": result.payload.get("text"),
                        "score_sparse": result.score,
                        "score_dense": None,
                        "rank_sparse": rank,
                        "rank_dense": None,
                        "clause_type": result.payload.get("clause_type"),
                        "importance": result.payload.get("importance"),
                    }
                else:
                    results_by_id[cid]["score_sparse"] = result.score
                    results_by_id[cid]["rank_sparse"] = rank

            for rank, result in enumerate(dense_results):
                cid = result.id
                if cid not in results_by_id:
                    results_by_id[cid] = {
                        "chunk_id": result.payload.get("chunk_id"),
                        "text": result.payload.get("text"),
                        "score_sparse": None,
                        "score_dense": result.score,
                        "rank_sparse": None,
                        "rank_dense": rank,
                        "clause_type": result.payload.get("clause_type"),
                        "importance": result.payload.get("importance"),
                    }
                else:
                    results_by_id[cid]["score_dense"] = result.score
                    results_by_id[cid]["rank_dense"] = rank

            results = list(results_by_id.values())
        else:
            # Dense search only
            try:
                dense_results = await asyncio.wait_for(
                    self.qdrant.search(
                        collection_name=self.collection_name,
                        query_vector=("dense", dense_vec),
                        limit=top_k,
                        query_filter=qdrant_filter,
                    ),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                logger.error("Dense search timeout")
                raise

            for result in dense_results:
                results.append({
                    "chunk_id": result.payload.get("chunk_id"),
                    "text": result.payload.get("text"),
                    "score_dense": result.score,
                    "score_sparse": None,
                    "clause_type": result.payload.get("clause_type"),
                    "importance": result.payload.get("importance"),
                })

        return results[:top_k]

    async def metadata_filter(
        self,
        document_id: str,
        importance_gte: int = 1,
        clause_types: list[str] = None,
    ) -> list[dict]:
        """Filter by metadata: importance level and clause types.

        Returns chunks matching filters.
        """
        if clause_types is None:
            clause_types = []

        logger.info(
            f"Filtering: doc={document_id}, importance>={importance_gte}, "
            f"clause_types={clause_types}"
        )

        must_filters = [
            models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)),
            models.FieldCondition(key="importance", range=models.Range(gte=importance_gte)),
        ]
        if clause_types:
            must_filters.append(
                models.FieldCondition(key="clause_type", match=models.MatchAny(any=clause_types))
            )

        results_list = []
        try:
            points, _ = await self.qdrant.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(must=must_filters),
                limit=50,
            )

            for point in points:
                results_list.append({
                    "chunk_id": point.payload.get("chunk_id"),
                    "text": point.payload.get("text"),
                    "clause_type": point.payload.get("clause_type"),
                    "importance": point.payload.get("importance"),
                })
        except Exception as e:
            logger.warning(f"Metadata filter error: {e}")

        return results_list


# TODO: Implement real MCP-over-SSE streaming
# Current /sse is a stub. Real implementation should:
# 1. Accept SSE connection
# 2. Send tool results back through SSE stream
# 3. Not just return HTTP response body
# For now: MCP client gets results via HTTP POST response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Qdrant MCP Server...")
    await server.ensure_collection()
    yield
    logger.info("Shutting down Qdrant MCP Server...")


app = FastAPI(title="Qdrant MCP Server", lifespan=lifespan)
server = QdrantMCPServer()

# CORS middleware — restrict to local AI service and Gateway only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:3000"],  # Gateway/client
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


async def verify_auth(request: Request):
    """Simple auth middleware: check X-API-Key header.
    
    In production, validate against real API key store.
    For now, localhost can bypass; remote requests need header.
    """
    client_host = request.client.host if request.client else "unknown"
    if client_host not in ("127.0.0.1", "localhost"):
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
    async def event_stream():
        yield "data: " + json.dumps({"type": "session_start"}) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/messages")
async def handle_messages(request: dict):
    """Handle MCP tool call requests.

    Expected request format:
    {
      "tool": "vector_search" | "metadata_filter",
      "params": {...}
    }
    """
    tool_name = request.get("tool")
    params = request.get("params", {})
    results = []  # Initialize results to avoid reference before assignment

    if not tool_name:
        return {"success": False, "error": "Missing 'tool' field"}

    logger.info(f"Tool call: {tool_name} with params={params}")

    try:
        if tool_name == "vector_search":
            # Validate params
            if not params.get("query_text") or not params.get("document_id"):
                return {"success": False, "error": "Missing required params: query_text, document_id"}
            results = await server.vector_search(**params)
        elif tool_name == "metadata_filter":
            if not params.get("document_id"):
                return {"success": False, "error": "Missing required param: document_id"}
            results = await server.metadata_filter(**params)
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
        port=int(os.getenv("QDRANT_MCP_PORT", 8001)),
        log_level="info",
    )
