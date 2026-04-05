# Standard library
from collections import defaultdict
import threading
from typing import Any

# Third-party
from qdrant_client import models as qdrant_models
from sentence_transformers import CrossEncoder

# Local
from src.shared.settings import settings

_cross_encoder: CrossEncoder | None = None
_cross_encoder_lock = threading.Lock()


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        with _cross_encoder_lock:
            if _cross_encoder is None:
                _cross_encoder = CrossEncoder(settings.cross_encoder_model)
    return _cross_encoder


def deduplicate(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate chunks by chunk_id while keeping first occurrence."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        unique.append(chunk)
    return unique


async def bridge(
    neo4j_chunk_ids: list[str],
    qdrant_client: Any,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch full chunk payloads for Neo4j chunk_ids from Qdrant."""
    if not neo4j_chunk_ids:
        return []

    filter_by_ids = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="chunk_id",
                match=qdrant_models.MatchAny(any=neo4j_chunk_ids),
            )
        ]
    )

    target_collection = collection_name or settings.qdrant_collection_name
    bridged: list[dict[str, Any]] = []
    offset = None

    while True:
        points, next_offset = await qdrant_client.scroll(
            collection_name=target_collection,
            scroll_filter=filter_by_ids,
            limit=50,
            offset=offset,
        )

        for point in points:
            payload = point.payload or {}
            bridged.append(
                {
                    "chunk_id": payload.get("chunk_id"),
                    "text": payload.get("text", ""),
                    "clause_type": payload.get("clause_type"),
                    "importance": payload.get("importance"),
                }
            )

        if next_offset is None:
            break
        offset = next_offset

    return bridged


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
    top_k: int = 15,
) -> list[dict[str, Any]]:
    """Fuse ranked lists via Reciprocal Rank Fusion.

    score(d) = sum_i 1 / (k + rank_i(d))
    rank_i is zero-based list position.
    """
    scores: dict[str, float] = defaultdict(float)
    best_chunk: dict[str, dict[str, Any]] = {}

    for results in result_lists:
        for rank, item in enumerate(results):
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                continue
            scores[chunk_id] += 1.0 / (k + rank)
            if chunk_id not in best_chunk:
                best_chunk[chunk_id] = item

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[:top_k]
    fused: list[dict[str, Any]] = []
    for chunk_id in ranked_ids:
        row = dict(best_chunk[chunk_id])
        row["rrf_score"] = scores[chunk_id]
        fused.append(row)
    return fused


def rerank(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rerank chunks using cross-encoder/ms-marco-MiniLM-L-6-v2."""
    if not chunks:
        return []

    non_empty = [chunk for chunk in chunks if str(chunk.get("text", "")).strip()]
    empty = [chunk for chunk in chunks if not str(chunk.get("text", "")).strip()]

    if not non_empty:
        return [{**chunk, "rerank_score": 0.0} for chunk in chunks]

    pairs = [(query, chunk.get("text", "")) for chunk in non_empty]
    scores = _get_cross_encoder().predict(pairs)

    reranked: list[dict[str, Any]] = []
    for chunk, score in zip(non_empty, scores):
        row = dict(chunk)
        row["rerank_score"] = float(score)
        reranked.append(row)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    for chunk in empty:
        row = dict(chunk)
        row["rerank_score"] = 0.0
        reranked.append(row)

    return reranked
