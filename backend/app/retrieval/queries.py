from typing import Any
import structlog
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import DocumentChunk, SourceDocument

logger = structlog.get_logger(__name__)

# Cached SQLAlchemy engine for direct database queries
_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def semantic_search_chunks(
    query_embedding: list[float],
    top_k: int = 20,
    ticker: str | None = None,
    year: str | None = None,
) -> list[dict[str, Any]]:
    """Performs pgvector cosine distance semantic search over document_chunks.

    Returns ranked list of matching chunks with similarity scores.
    """
    with Session(_engine) as session:
        # Build SQL query using pgvector cosine operator (<=>)
        embedding_str = f"[{','.join(str(f) for f in query_embedding)}]"
        
        sql = """
            SELECT 
                c.id AS chunk_id,
                c.document_id,
                c.chunk_index,
                c.chunk_text,
                c.token_count,
                c.metadata,
                d.ticker,
                d.company_name,
                d.form_type,
                d.filing_date,
                d.source_url,
                1 - (c.embedding <=> :embedding::vector) AS similarity_score
            FROM document_chunks c
            JOIN source_documents d ON c.document_id = d.id
            WHERE c.embedding IS NOT NULL
        """
        params: dict[str, Any] = {"embedding": embedding_str, "top_k": top_k}

        if ticker:
            sql += " AND d.ticker = :ticker"
            params["ticker"] = ticker.upper()

        if year:
            sql += " AND EXTRACT(YEAR FROM d.filing_date)::text = :year"
            params["year"] = year

        sql += " ORDER BY c.embedding <=> :embedding::vector ASC LIMIT :top_k"

        results = session.execute(text(sql), params).mappings().all()

        return [
            {
                "chunk_id": str(r["chunk_id"]),
                "document_id": str(r["document_id"]),
                "chunk_index": r["chunk_index"],
                "chunk_text": r["chunk_text"],
                "token_count": r["token_count"],
                "score": float(r["similarity_score"]),
                "ticker": r["ticker"],
                "company_name": r["company_name"],
                "form_type": r["form_type"],
                "filing_date": str(r["filing_date"]),
                "source_url": r["source_url"],
                "metadata": dict(r["metadata"]),
            }
            for r in results
        ]


def fulltext_search_chunks(
    query_text: str,
    top_k: int = 20,
    ticker: str | None = None,
    year: str | None = None,
) -> list[dict[str, Any]]:
    """Performs Postgres full-text lexical search over document_chunks.search_vector.

    Uses websearch_to_tsquery and ts_rank for keyword relevance scoring.
    """
    if not query_text or not query_text.strip():
        return []

    with Session(_engine) as session:
        sql = """
            SELECT 
                c.id AS chunk_id,
                c.document_id,
                c.chunk_index,
                c.chunk_text,
                c.token_count,
                c.metadata,
                d.ticker,
                d.company_name,
                d.form_type,
                d.filing_date,
                d.source_url,
                ts_rank(c.search_vector, websearch_to_tsquery('english', :query)) AS rank_score
            FROM document_chunks c
            JOIN source_documents d ON c.document_id = d.id
            WHERE c.search_vector @@ websearch_to_tsquery('english', :query)
        """
        params: dict[str, Any] = {"query": query_text.strip(), "top_k": top_k}

        if ticker:
            sql += " AND d.ticker = :ticker"
            params["ticker"] = ticker.upper()

        if year:
            sql += " AND EXTRACT(YEAR FROM d.filing_date)::text = :year"
            params["year"] = year

        sql += " ORDER BY rank_score DESC LIMIT :top_k"

        results = session.execute(text(sql), params).mappings().all()

        return [
            {
                "chunk_id": str(r["chunk_id"]),
                "document_id": str(r["document_id"]),
                "chunk_index": r["chunk_index"],
                "chunk_text": r["chunk_text"],
                "token_count": r["token_count"],
                "score": float(r["rank_score"]),
                "ticker": r["ticker"],
                "company_name": r["company_name"],
                "form_type": r["form_type"],
                "filing_date": str(r["filing_date"]),
                "source_url": r["source_url"],
                "metadata": dict(r["metadata"]),
            }
            for r in results
        ]
