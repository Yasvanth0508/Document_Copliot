"""Retrieval layer package: hybrid semantic pgvector search, Postgres full-text search, Reciprocal Rank Fusion, and source passage retrieval."""

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.retriever import DocumentRetriever, SourcePassage

__all__ = ["reciprocal_rank_fusion", "DocumentRetriever", "SourcePassage"]
