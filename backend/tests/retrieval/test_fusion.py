from app.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_single_list():
    list1 = [
        {"chunk_id": "chunk-1", "text": "First chunk"},
        {"chunk_id": "chunk-2", "text": "Second chunk"},
    ]
    results = reciprocal_rank_fusion([list1], id_key="chunk_id", k=60, top_n=10)
    assert len(results) == 2
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[1]["chunk_id"] == "chunk-2"
    assert results[0]["rrf_score"] > results[1]["rrf_score"]


def test_rrf_combines_multiple_lists():
    semantic_list = [
        {"chunk_id": "chunk-A", "title": "A"},
        {"chunk_id": "chunk-B", "title": "B"},
    ]
    fulltext_list = [
        {"chunk_id": "chunk-B", "title": "B"},
        {"chunk_id": "chunk-C", "title": "C"},
    ]

    results = reciprocal_rank_fusion(
        [semantic_list, fulltext_list], id_key="chunk_id", k=60, top_n=10
    )

    assert len(results) == 3
    # chunk-B is rank 2 in list 1 and rank 1 in list 2, so it should rank first overall
    assert results[0]["chunk_id"] == "chunk-B"
    # 1/(60+2) + 1/(60+1)
    expected_score_b = (1.0 / 62.0) + (1.0 / 61.0)
    assert abs(results[0]["rrf_score"] - expected_score_b) < 1e-6


def test_rrf_sorts_descending_and_respects_top_n():
    list1 = [{"chunk_id": f"chunk-{i}"} for i in range(1, 10)]
    list2 = [{"chunk_id": f"chunk-{i}"} for i in range(10, 0, -1)]

    results = reciprocal_rank_fusion([list1, list2], id_key="chunk_id", k=60, top_n=5)
    assert len(results) == 5

    # Verify strictly descending order of scores
    for i in range(len(results) - 1):
        assert results[i]["rrf_score"] >= results[i + 1]["rrf_score"]


def test_rrf_empty_lists():
    results = reciprocal_rank_fusion([[], []], id_key="chunk_id")
    assert results == []
