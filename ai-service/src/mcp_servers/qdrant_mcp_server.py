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
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
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

        Returns list of {chunk_id, text, score, clause_type, importance}.
        """
        if clause_types is None:
            clause_types = []

        logger.info(f"Searching: query={query_text[:50]}, doc={document_id}, top_k={top_k}")

        dense_vector = await asyncio.to_thread(self.embedding_model.embed_query, query_text)
        sparse_result = await asyncio.to_thread(lambda q=query_text: list(self.sparse_model.embed([q])))
        sparse_vec = sparse_result[0]

        must_filters = [
            models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))
        ]
        if clause_types:
            must_filters.append(
                models.FieldCondition(key="clause_type", match=models.MatchAny(any=clause_types))
            )

        qdrant_filter = models.Filter(must=must_filters)
        results = []

        if use_sparse:
            sparse_results = await self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=("sparse", models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                )),
                limit=top_k,
                query_filter=qdrant_filter,
            )

            dense_results = await self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=("dense", dense_vector),
                limit=top_k,
                query_filter=qdrant_filter,
            )

            seen = set()
            for result in sparse_results + dense_results:
                if result.id not in seen:
                    seen.add(result.id)
                    results.append({
                        "chunk_id": result.payload.get("chunk_id"),
                        "text": result.payload.get("text"),
                        "score": result.score,
                        "clause_type": result.payload.get("clause_type"),
                        "importance": result.payload.get("importance"),
                    })
        else:
            dense_results = await self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=("dense", dense_vector),
                limit=top_k,
                query_filter=qdrant_filter,
            )

            for result in dense_results:
                results.append({
                    "chunk_id": result.payload.get("chunk_id"),
                    "text": result.payload.get("text"),
                    "score": result.score,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Qdrant MCP Server...")
    await server.ensure_collection()
    yield
    logger.info("Shutting down Qdrant MCP Server...")


app = FastAPI(title="Qdrant MCP Server", lifespan=lifespan)
server = QdrantMCPServer()


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

    logger.info(f"Tool call: {tool_name} with params={params}")

    try:
        if tool_name == "vector_search":
            results = await server.vector_search(**params)
        elif tool_name == "metadata_filter":
            results = await server.metadata_filter(**params)
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
        port=int(os.getenv("QDRANT_MCP_PORT", 8001)),
        log_level="info",
    )
