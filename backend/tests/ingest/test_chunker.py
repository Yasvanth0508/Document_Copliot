from ingest.chunker import chunk_markdown, estimate_token_count


def test_estimate_token_count():
    text = "Apple Inc. designs, manufactures, and markets smartphones."
    count = estimate_token_count(text)
    assert count >= 7  # ~7 words * 1.3


def test_chunk_markdown_preserves_metadata_and_sections():
    markdown = """# ITEM 1. BUSINESS

Apple designs, manufactures, and markets smartphones, personal computers, tablets, wearables and accessories.

# ITEM 1A. RISK FACTORS

Global macroeconomic conditions and inflation could impact consumer spending on high-end hardware.

Supply chain disruptions in component manufacturing could delay product availability.
"""
    doc_meta = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "form": "10-K",
        "filing_date": "2025-10-31",
        "accession_number": "0000320193-25-000079",
        "source_url": "https://sec.gov/sample",
    }

    chunks = chunk_markdown(markdown, doc_metadata=doc_meta, target_chars=200, max_chars=400)
    assert len(chunks) >= 2

    first_chunk = chunks[0]
    assert first_chunk.chunk_index == 0
    assert first_chunk.metadata["ticker"] == "AAPL"
    assert first_chunk.metadata["accession_number"] == "0000320193-25-000079"
    assert "ITEM 1." in first_chunk.metadata["section"]

    risk_chunk = [c for c in chunks if "ITEM 1A" in c.metadata["section"]][0]
    assert "macroeconomic conditions" in risk_chunk.chunk_text or "Supply chain" in risk_chunk.chunk_text


def test_chunk_markdown_empty_input():
    chunks = chunk_markdown("", doc_metadata={})
    assert chunks == []
