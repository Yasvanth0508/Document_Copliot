import uuid
import structlog
from app.database.supabase import get_supabase_admin_client
from ingest.chunker import ParsedChunk

logger = structlog.get_logger(__name__)


def load_document_and_chunks(
    doc_data: dict,
    chunks: list[ParsedChunk],
    embeddings: list[list[float]],
) -> str | None:
    """Inserts a source document and its embedded chunks into Supabase Postgres.

    Uses the admin service-role Supabase client to perform privileged ingestion writes.
    Checks accession_number to prevent duplicate filing insertion.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunk count ({len(chunks)}) does not match embedding count ({len(embeddings)})"
        )

    supabase = get_supabase_admin_client()
    accession_number = doc_data["accession_number"]

    # Check if document already exists
    existing = (
        supabase.table("source_documents")
        .select("id")
        .eq("accession_number", accession_number)
        .execute()
    )
    if existing.data:
        logger.info(
            "Filing already ingested, skipping",
            accession_number=accession_number,
            doc_id=existing.data[0]["id"],
        )
        return existing.data[0]["id"]

    doc_id = str(uuid.uuid4())
    doc_payload = {
        "id": doc_id,
        "ticker": doc_data["ticker"],
        "company_name": doc_data.get("company_name", doc_data["ticker"]),
        "form_type": doc_data["form"],
        "filing_date": doc_data["filing_date"],
        "report_date": doc_data.get("report_date"),
        "accession_number": accession_number,
        "source_url": doc_data["source_url"],
        "markdown_content": doc_data["markdown_content"],
        "metadata": {
            "cik": doc_data.get("cik"),
            "local_path": doc_data.get("local_path"),
            "primary_document": doc_data.get("primary_document"),
        },
    }

    logger.info(
        "Inserting source document",
        ticker=doc_data["ticker"],
        form=doc_data["form"],
        accession_number=accession_number,
    )
    supabase.table("source_documents").insert(doc_payload).execute()

    # Prepare chunks payload
    chunk_payloads = []
    for chunk, emb in zip(chunks, embeddings, strict=True):
        chunk_payloads.append(
            {
                "id": str(uuid.uuid4()),
                "document_id": doc_id,
                "chunk_index": chunk.chunk_index,
                "chunk_text": chunk.chunk_text,
                "token_count": chunk.token_count,
                "embedding": emb,
                "metadata": chunk.metadata,
            }
        )

    # Insert chunks in batches of 100
    batch_size = 100
    for i in range(0, len(chunk_payloads), batch_size):
        batch = chunk_payloads[i : i + batch_size]
        supabase.table("document_chunks").insert(batch).execute()

    logger.info(
        "Successfully loaded document and chunks",
        doc_id=doc_id,
        chunk_count=len(chunks),
    )
    return doc_id
