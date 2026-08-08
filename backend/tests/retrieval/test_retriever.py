from unittest.mock import MagicMock, patch

import pytest
from app.retrieval.retriever import DocumentRetriever, SourcePassage


@pytest.mark.integration
@patch("app.retrieval.retriever.semantic_search_chunks")
@patch("app.retrieval.retriever.fulltext_search_chunks")
@patch.object(DocumentRetriever, "embed_query")
def test_document_retriever_pipeline(mock_embed, mock_fulltext, mock_semantic):
    """Integration test verifying end-to-end retriever workflow."""
    mock_embed.return_value = [0.1] * 768

    mock_semantic.return_value = [
        {
            "chunk_id": "c1",
            "document_id": "d1",
            "chunk_index": 0,
            "chunk_text": "Apple Services revenue reached record highs.",
            "token_count": 8,
            "score": 0.92,
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "form_type": "10-K",
            "filing_date": "2025-10-31",
            "source_url": "https://sec.gov/aapl",
            "metadata": {"section": "ITEM 7. MD&A"},
        }
    ]

    mock_fulltext.return_value = [
        {
            "chunk_id": "c1",
            "document_id": "d1",
            "chunk_index": 0,
            "chunk_text": "Apple Services revenue reached record highs.",
            "token_count": 8,
            "score": 0.85,
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "form_type": "10-K",
            "filing_date": "2025-10-31",
            "source_url": "https://sec.gov/aapl",
            "metadata": {"section": "ITEM 7. MD&A"},
        }
    ]

    retriever = DocumentRetriever(top_k=10, rrf_top_n=5)
    passages = retriever.retrieve(
        query="Apple Services revenue mix shift", ticker="AAPL", year="2025"
    )

    assert len(passages) == 1
    passage = passages[0]
    assert isinstance(passage, SourcePassage)
    assert passage.chunk_id == "c1"
    assert passage.ticker == "AAPL"
    assert passage.section == "ITEM 7. MD&A"
    assert "Apple Services" in passage.excerpt
    assert passage.rrf_score > 0.0

    mock_embed.assert_called_once_with("Apple Services revenue mix shift")
    mock_semantic.assert_called_once()
    mock_fulltext.assert_called_once()
