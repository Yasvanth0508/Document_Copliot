from dataclasses import dataclass, field
from typing import Any
import structlog

from google import genai
from google.genai import types

from app.config import settings
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import fulltext_search_chunks, semantic_search_chunks

logger = structlog.get_logger(__name__)


@dataclass
class SourcePassage:
    """Typed evidence passage retrieved for LLM answer generation and citation."""

    chunk_id: str
    document_id: str
    ticker: str
    company_name: str
    form_type: str
    filing_date: str
    section: str
    excerpt: str
    rrf_score: float
    source_url: str
    metadata: dict[str, Any] = field(default_factory=dict)
    neighbor_texts: list[str] = field(default_factory=list)


class DocumentRetriever:
    """Orchestrates hybrid retrieval (semantic pgvector + lexical full-text + RRF fusion)."""

    def __init__(self, top_k: int = 20, rrf_top_n: int = 10) -> None:
        self.top_k = top_k
        self.rrf_top_n = rrf_top_n
        self._genai_client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    def embed_query(self, query: str) -> list[float]:
        """Embeds user search query using Gemini embedding model."""
        response = self._genai_client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSIONS
            ),
        )
        return list(response.embeddings[0].values)

    def retrieve(
        self,
        query: str,
        ticker: str | None = None,
        year: str | None = None,
        top_n: int | None = None,
    ) -> list[SourcePassage]:
        """Executes hybrid retrieval: query embedding -> pgvector + full-text -> RRF fusion -> SourcePassage objects."""
        if not query or not query.strip():
            return []

        limit = top_n if top_n is not None else self.rrf_top_n

        logger.info(
            "Executing document retrieval",
            query=query,
            ticker=ticker,
            year=year,
            limit=limit,
        )

        # 1. Embed query
        query_embedding = self.embed_query(query)

        # 2. Run semantic and full-text searches
        semantic_results = semantic_search_chunks(
            query_embedding=query_embedding,
            top_k=self.top_k,
            ticker=ticker,
            year=year,
        )
        fulltext_results = fulltext_search_chunks(
            query_text=query,
            top_k=self.top_k,
            ticker=ticker,
            year=year,
        )

        # 3. Fuse ranked results with RRF
        fused_items = reciprocal_rank_fusion(
            ranked_lists=[semantic_results, fulltext_results],
            id_key="chunk_id",
            top_n=limit,
        )

        # 4. Convert fused results into typed SourcePassage objects
        passages: list[SourcePassage] = []
        for item in fused_items:
            meta = item.get("metadata", {})
            passages.append(
                SourcePassage(
                    chunk_id=str(item["chunk_id"]),
                    document_id=str(item["document_id"]),
                    ticker=str(item["ticker"]),
                    company_name=str(item["company_name"]),
                    form_type=str(item["form_type"]),
                    filing_date=str(item["filing_date"]),
                    section=str(meta.get("section", "GENERAL")),
                    excerpt=str(item["chunk_text"]),
                    rrf_score=float(item.get("rrf_score", 0.0)),
                    source_url=str(item["source_url"]),
                    metadata=meta,
                )
            )

        logger.info("Retrieval completed", returned_passages=len(passages))
        return passages
