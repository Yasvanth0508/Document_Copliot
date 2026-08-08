import json
from pathlib import Path
import structlog

from ingest.chunker import chunk_markdown
from ingest.embedder import generate_embeddings_batch
from ingest.loader import load_document_and_chunks
from ingest.parser import parse_html_to_markdown

logger = structlog.get_logger(__name__)

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}

# Resolve root repo data downloads directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOWNLOADS_DIR = REPO_ROOT / "data" / "downloads"
MANIFEST_PATH = DOWNLOADS_DIR / "manifest.json"


def run_ingestion_pipeline(manifest_path: Path = MANIFEST_PATH) -> dict:
    """Executes full SEC document ingestion pipeline from downloaded corpus.

    Flow: read manifest -> load HTML -> parse to Markdown -> chunk -> embed -> write to Supabase.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Corpus manifest not found at {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest.get("filings", [])

    logger.info("Starting document ingestion pipeline", total_filings=len(filings))

    total_docs = 0
    total_chunks = 0

    for filing in filings:
        ticker = filing["ticker"]
        accession = filing["accession_number"]
        local_rel_path = filing["local_path"]
        html_file_path = DOWNLOADS_DIR / local_rel_path

        if not html_file_path.exists():
            logger.warning(
                "Filing HTML file not found, skipping",
                path=str(html_file_path),
                ticker=ticker,
                accession=accession,
            )
            continue

        logger.info(
            "Processing filing",
            ticker=ticker,
            year=filing.get("filing_date", "")[:4],
            accession=accession,
        )

        html_content = html_file_path.read_text(encoding="utf-8", errors="replace")
        markdown_content = parse_html_to_markdown(html_content)

        doc_data = {
            "ticker": ticker,
            "company_name": COMPANY_NAMES.get(ticker, ticker),
            "form": filing["form"],
            "filing_date": filing["filing_date"],
            "report_date": filing.get("report_date"),
            "accession_number": accession,
            "source_url": filing["source_url"],
            "markdown_content": markdown_content,
            "cik": filing.get("cik"),
            "local_path": local_rel_path,
            "primary_document": filing.get("primary_document"),
        }

        chunks = chunk_markdown(markdown_content, doc_metadata=doc_data)
        if not chunks:
            logger.warning("No chunks generated for filing", accession=accession)
            continue

        chunk_texts = [c.chunk_text for c in chunks]
        embeddings = generate_embeddings_batch(chunk_texts)

        doc_id = load_document_and_chunks(
            doc_data=doc_data,
            chunks=chunks,
            embeddings=embeddings,
        )

        if doc_id:
            total_docs += 1
            total_chunks += len(chunks)

    summary = {
        "status": "completed",
        "processed_documents": total_docs,
        "total_chunks_ingested": total_chunks,
    }
    logger.info("Ingestion pipeline finished", **summary)
    return summary


if __name__ == "__main__":
    summary = run_ingestion_pipeline()
    print("Ingestion Summary:", summary)
