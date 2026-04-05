# Standard library
import asyncio
import time
from typing import Any

# Third-party
from qdrant_client import AsyncQdrantClient

# Local
from src.retrieval.fusion import bridge, deduplicate, reciprocal_rank_fusion, rerank
from src.retrieval.state import RetrievalState
from src.shared.langfuse_config import update_observation
from src.shared.settings import settings

# Module-level Qdrant client singleton — initialised once on first use.
_QDRANT_CLIENT: AsyncQdrantClient | None = None
_QDRANT_CLIENT_LOCK = asyncio.Lock()


async def _get_qdrant_client() -> AsyncQdrantClient:
    global _QDRANT_CLIENT
    if _QDRANT_CLIENT is not None:
        return _QDRANT_CLIENT

    async with _QDRANT_CLIENT_LOCK:
        if _QDRANT_CLIENT is None:
            _QDRANT_CLIENT = AsyncQdrantClient(url=settings.qdrant_url)
    return _QDRANT_CLIENT


async def bridge_fusion_node(state: RetrievalState) -> dict[str, Any]:
    t0 = time.perf_counter()
    qdrant_results = state.get("qdrant_results", [])
    neo4j_chunk_ids = state.get("neo4j_chunk_ids", [])
    rerank_query = state.get("rewritten_query") or state.get("question", "")

    qdrant_client = await _get_qdrant_client()

    bridged_chunks = await bridge(
        neo4j_chunk_ids,
        qdrant_client,
        collection_name=settings.qdrant_collection_name,
    )

    fused_rrf = reciprocal_rank_fusion([qdrant_results, bridged_chunks], k=60, top_k=25)
    fused_dedup = deduplicate(fused_rrf)
    fused_chunks = await asyncio.to_thread(rerank, rerank_query, fused_dedup)

    update_observation("bridge_fusion_node", {
        "qdrant_results_count": len(qdrant_results),
        "neo4j_chunk_ids_count": len(neo4j_chunk_ids),
        "bridged_chunks_count": len(bridged_chunks),
        "rrf_count": len(fused_rrf),
        "dedup_count": len(fused_dedup),
        "fused_chunks_count": len(fused_chunks),
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
    })

    return {"fused_chunks": fused_chunks}
