"""Code embedding functionality for codebase datasets."""

import os
from typing import List, Optional

import structlog
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()


class CodeEmbedder:
    """Generates embeddings for code content."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: Optional[str] = None,
    ):
        """Initialize code embedder.

        Args:
            model_name: Name of the embedding model
            cache_dir: Directory to cache models
        """
        self.model_name = model_name
        self.cache_dir = cache_dir or os.getenv("MODEL_CACHE_DIR", "/tmp/models")

        # Load model
        self.model = self._load_model()
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        logger.info(
            "Code embedder initialized",
            model=self.model_name,
            embedding_dim=self.embedding_dim,
        )

    def _load_model(self) -> SentenceTransformer:
        """Load the embedding model.

        Returns:
            Loaded model
        """
        try:
            model = SentenceTransformer(
                self.model_name,
                cache_folder=self.cache_dir,
            )
            logger.info("Model loaded successfully", model=self.model_name)
            return model
        except Exception as e:
            logger.error("Failed to load model", model=self.model_name, error=str(e))
            raise

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            # Clean and preprocess text
            cleaned_text = self._preprocess_text(text)

            # Generate embedding
            embedding = self.model.encode(cleaned_text)

            return embedding.tolist()

        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            # Clean and preprocess texts
            cleaned_texts = [self._preprocess_text(text) for text in texts]

            # Generate embeddings
            embeddings = self.model.encode(cleaned_texts)

            return [embedding.tolist() for embedding in embeddings]

        except Exception as e:
            logger.error("Failed to generate batch embeddings", error=str(e))
            raise

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for embedding.

        Args:
            text: Raw text

        Returns:
            Preprocessed text
        """
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Truncate if too long (most models have token limits)
        max_length = 512  # Conservative limit
        if len(text) > max_length:
            text = text[:max_length]

        return text

    def get_embedding_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Embedding dimension
        """
        return self.embedding_dim
