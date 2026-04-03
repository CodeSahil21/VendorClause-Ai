from collections import defaultdict
from typing import Any

from src.shared.settings import settings

_cross_encoder: Any | None = None


def _get_cross_encoder() -> Any:
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
        except Exception as exc:
            raise RuntimeError("sentence-transformers is required for rerank()") from exc
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
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
    """Fetch full chunk payloads for Neo4j chunk_ids from Qdrant.

    Expects qdrant_client to expose async scroll(collection_name=..., scroll_filter=..., limit=...)
    compatible with AsyncQdrantClient.
    """
    if not neo4j_chunk_ids:
        return []

    try:
        from qdrant_client import models
    except Exception as exc:
        raise RuntimeError("qdrant-client is required for bridge()") from exc

    filter_by_ids = models.Filter(
        must=[
            models.FieldCondition(
                key="chunk_id",
                match=models.MatchAny(any=neo4j_chunk_ids),
            )
        ]
    )

    target_collection = collection_name or settings.qdrant_collection_name

    points, _ = await qdrant_client.scroll(
        collection_name=target_collection,
        scroll_filter=filter_by_ids,
        limit=max(len(neo4j_chunk_ids), 1),
    )

    bridged: list[dict[str, Any]] = []
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

    model = _get_cross_encoder()
    pairs = [(query, chunk.get("text", "")) for chunk in chunks]
    scores = model.predict(pairs)

    reranked: list[dict[str, Any]] = []
    for chunk, score in zip(chunks, scores):
        row = dict(chunk)
        row["rerank_score"] = float(score)
        reranked.append(row)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    return reranked


def test_rrf_math() -> None:
    """Quick mock test to validate RRF ordering."""
    list_a = [
        {"chunk_id": "c1", "text": "A"},
        {"chunk_id": "c2", "text": "B"},
        {"chunk_id": "c3", "text": "C"},
    ]
    list_b = [
        {"chunk_id": "c2", "text": "B"},
        {"chunk_id": "c4", "text": "D"},
        {"chunk_id": "c1", "text": "A"},
    ]

    fused = reciprocal_rank_fusion([list_a, list_b], k=60, top_k=4)
    assert fused[0]["chunk_id"] in {"c1", "c2"}
    assert len(fused) == 4
