import re
from dataclasses import dataclass
from typing import Any

# Default target bounds (in characters, roughly 4 chars/token)
DEFAULT_MIN_CHUNK_SIZE = 1000  # ~250 tokens
DEFAULT_TARGET_CHUNK_SIZE = 2400  # ~600 tokens
DEFAULT_MAX_CHUNK_SIZE = 3600  # ~900 tokens

HEADER_PATTERN = re.compile(r"^(#+)\s+(.*)", re.MULTILINE)


@dataclass
class ParsedChunk:
    """Dataclass holding chunk content and metadata for ingestion."""

    chunk_index: int
    chunk_text: str
    token_count: int
    metadata: dict[str, Any]


def estimate_token_count(text: str) -> int:
    """Estimates token count for a text string (~1.3 tokens per word)."""
    words = text.split()
    return max(1, int(len(words) * 1.3))


def chunk_markdown(
    markdown_content: str,
    doc_metadata: dict[str, Any],
    target_chars: int = DEFAULT_TARGET_CHUNK_SIZE,
    max_chars: int = DEFAULT_MAX_CHUNK_SIZE,
) -> list[ParsedChunk]:
    """Splits a document's Markdown content into semantic retrieval-ready chunks.

    Respects section headers and paragraph boundaries while targeting ~500-800 tokens per chunk.
    Preserves active section name and document metadata per chunk.
    """
    if not markdown_content or not markdown_content.strip():
        return []

    paragraphs = markdown_content.split("\n\n")
    chunks: list[ParsedChunk] = []

    current_section = "GENERAL"
    current_buffer: list[str] = []
    current_char_count = 0
    chunk_index = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue

        # Detect section header
        header_match = HEADER_PATTERN.match(para_clean)
        if header_match:
            # Flush current buffer under existing section before starting new section
            if current_buffer:
                chunk_text = "\n\n".join(current_buffer).strip()
                if chunk_text:
                    chunks.append(
                        _create_parsed_chunk(
                            chunk_index=chunk_index,
                            chunk_text=chunk_text,
                            section=current_section,
                            doc_metadata=doc_metadata,
                        )
                    )
                    chunk_index += 1
                current_buffer = []
                current_char_count = 0

            current_section = header_match.group(2).strip().upper()

        para_len = len(para_clean)

        # If adding this paragraph exceeds max chunk size and we already have content in buffer
        if current_char_count + para_len > max_chars and current_buffer:
            chunk_text = "\n\n".join(current_buffer).strip()
            if chunk_text:
                chunks.append(
                    _create_parsed_chunk(
                        chunk_index=chunk_index,
                        chunk_text=chunk_text,
                        section=current_section,
                        doc_metadata=doc_metadata,
                    )
                )
                chunk_index += 1
            current_buffer = []
            current_char_count = 0

        current_buffer.append(para_clean)
        current_char_count += para_len + 2  # +2 for \n\n

        # If buffer reached target chunk size, flush
        if current_char_count >= target_chars:
            chunk_text = "\n\n".join(current_buffer).strip()
            if chunk_text:
                chunks.append(
                    _create_parsed_chunk(
                        chunk_index=chunk_index,
                        chunk_text=chunk_text,
                        section=current_section,
                        doc_metadata=doc_metadata,
                    )
                )
                chunk_index += 1
            current_buffer = []
            current_char_count = 0

    # Flush remaining buffer
    if current_buffer:
        chunk_text = "\n\n".join(current_buffer).strip()
        if chunk_text:
            chunks.append(
                _create_parsed_chunk(
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    section=current_section,
                    doc_metadata=doc_metadata,
                )
            )

    return chunks


def _create_parsed_chunk(
    chunk_index: int,
    chunk_text: str,
    section: str,
    doc_metadata: dict[str, Any],
) -> ParsedChunk:
    """Helper to construct a ParsedChunk with enriched metadata."""
    token_count = estimate_token_count(chunk_text)
    chunk_meta = {
        "ticker": doc_metadata.get("ticker"),
        "company_name": doc_metadata.get("company_name"),
        "form_type": doc_metadata.get("form"),
        "filing_date": doc_metadata.get("filing_date"),
        "report_date": doc_metadata.get("report_date"),
        "accession_number": doc_metadata.get("accession_number"),
        "source_url": doc_metadata.get("source_url"),
        "section": section,
        "chunk_index": chunk_index,
    }
    return ParsedChunk(
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        token_count=token_count,
        metadata=chunk_meta,
    )
