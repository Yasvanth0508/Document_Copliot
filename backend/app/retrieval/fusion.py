from typing import Any

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    id_key: str = "chunk_id",
    k: int = DEFAULT_RRF_K,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Combines multiple ranked lists using Reciprocal Rank Fusion (RRF).

    Formula: RRF_score(doc) = sum(1.0 / (k + rank)) across all input lists.
    preserves item metadata and attaches the calculated `rrf_score`.
    """
    scores: dict[str, float] = {}
    item_map: dict[str, dict[str, Any]] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            item_id = str(item.get(id_key, ""))
            if not item_id:
                continue

            if item_id not in item_map:
                item_map[item_id] = item.copy()

            score = 1.0 / (k + rank)
            scores[item_id] = scores.get(item_id, 0.0) + score

    # Sort item IDs by RRF score descending
    sorted_ids = sorted(scores.keys(), key=lambda item_id: scores[item_id], reverse=True)

    fused_results: list[dict[str, Any]] = []
    for item_id in sorted_ids[:top_n]:
        res = item_map[item_id]
        res["rrf_score"] = scores[item_id]
        fused_results.append(res)

    return fused_results
