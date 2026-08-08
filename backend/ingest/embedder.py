import time
import structlog
from google import genai
from google.genai import types

from app.config import settings

logger = structlog.get_logger(__name__)

DEFAULT_BATCH_SIZE = 50


def generate_embeddings_batch(
    texts: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[list[float]]:
    """Generates Gemini embeddings for a list of text strings in batches.

    Uses GEMINI_EMBEDDING_MODEL and GEMINI_EMBEDDING_DIMENSIONS (768) configured in settings.
    """
    if not texts:
        return []

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        logger.info(
            "Generating Gemini embeddings batch",
            batch_start=i,
            batch_count=len(batch_texts),
            total=len(texts),
        )

        try:
            response = client.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=batch_texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSIONS
                ),
            )
            for emb in response.embeddings:
                embeddings.append(list(emb.values))
        except Exception as exc:
            logger.error("Failed generating embeddings batch", batch_start=i, error=str(exc))
            raise

        # Respect API rate limits between batches
        time.sleep(0.1)

    return embeddings
