from src.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_math() -> None:
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
