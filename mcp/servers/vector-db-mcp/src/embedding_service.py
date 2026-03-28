"""Embedding service for text-to-vector conversion."""

import asyncio

import numpy as np
import structlog

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore

logger = structlog.get_logger()


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize embedding service."""
        self.model_name = model_name
        self.model: SentenceTransformer | None = None
        self._load_model()

    def _load_model(self):
        """Load the embedding model."""
        try:
            if SentenceTransformer is not None:
                self.model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded", model=self.model_name)
            else:
                logger.warning(
                    "sentence-transformers not installed; using fallback hasher embeddings"
                )
                self.model = None
        except Exception as e:
            logger.error(
                "Failed to load embedding model", model=self.model_name, error=str(e)
            )
            self.model = None

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        if not self.model:
            # Fallback: deterministic hashing-based embedding
            import hashlib

            dim = 384
            h = hashlib.blake2b(text.encode("utf-8"), digest_size=64).digest()
            # Repeat hash to fill dim, convert bytes to floats in [0,1]
            vals = list(h) * ((dim + len(h) - 1) // len(h))
            arr = np.array(vals[:dim], dtype=np.float32) / 255.0
            return arr.tolist()

        try:
            # Run embedding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(None, self.model.encode, text)

            # Convert numpy array to list
            return embedding.tolist()

        except Exception as e:
            logger.error("Failed to generate embedding", text=text[:100], error=str(e))
            raise

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not self.model:
            # Fallback batch: apply single fallback
            return [await self.embed_text(t) for t in texts]

        try:
            # Run embedding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(None, self.model.encode, texts)

            # Convert numpy array to list of lists
            return [embedding.tolist() for embedding in embeddings]

        except Exception as e:
            logger.error(
                "Failed to generate embeddings", count=len(texts), error=str(e)
            )
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        if not self.model:
            return 384

        # Get dimension by encoding a dummy text
        dummy_embedding = self.model.encode("dummy")
        return len(dummy_embedding)
