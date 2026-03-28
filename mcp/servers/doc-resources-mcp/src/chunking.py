"""Document chunking functionality for document datasets."""

import re
from typing import Any, Dict, List, Optional

import structlog
import tiktoken

logger = structlog.get_logger()


class DocumentChunker:
    """Chunks documents for optimal retrieval."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        tokenizer_name: str = "cl100k_base",
    ):
        """Initialize document chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            tokenizer_name: Name of the tokenizer to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer_name = tokenizer_name

        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding(tokenizer_name)
        except Exception as e:
            logger.warning(
                "Failed to load tokenizer, using character-based chunking", error=str(e)
            )
            self.tokenizer = None

    def chunk_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a document.

        Args:
            document: Parsed document

        Returns:
            List of chunks
        """
        if document["type"] == "pdf":
            return self._chunk_pdf_document(document)
        else:
            return self._chunk_text_document(document)

    def _chunk_pdf_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a PDF document.

        Args:
            document: PDF document

        Returns:
            List of chunks
        """
        chunks = []
        chunk_index = 0

        for page in document["pages"]:
            page_content = page["content"]
            page_number = page["page_number"]

            # Chunk page content
            page_chunks = self._chunk_text(
                text=page_content,
                chunk_index=chunk_index,
                page_number=page_number,
                metadata=page.get("metadata", {}),
            )

            chunks.extend(page_chunks)
            chunk_index += len(page_chunks)

        return chunks

    def _chunk_text_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a text document.

        Args:
            document: Text document

        Returns:
            List of chunks
        """
        return self._chunk_text(
            text=document["content"],
            chunk_index=0,
            metadata=document.get("metadata", {}),
        )

    def _chunk_text(
        self,
        text: str,
        chunk_index: int = 0,
        page_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Chunk text content.

        Args:
            text: Text to chunk
            chunk_index: Starting chunk index
            page_number: Optional page number
            metadata: Optional metadata

        Returns:
            List of chunks
        """
        if not text.strip():
            return []

        # Clean text
        text = self._clean_text(text)

        # Split into sentences
        sentences = self._split_into_sentences(text)

        # Create chunks
        chunks = []
        current_chunk = ""
        current_chunk_index = chunk_index

        for sentence in sentences:
            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(
                    {
                        "chunk_index": current_chunk_index,
                        "content": current_chunk.strip(),
                        "page_number": page_number,
                        "metadata": metadata or {},
                    }
                )

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + sentence
                current_chunk_index += 1
            else:
                current_chunk += sentence

        # Add final chunk
        if current_chunk.strip():
            chunks.append(
                {
                    "chunk_index": current_chunk_index,
                    "content": current_chunk.strip(),
                    "page_number": page_number,
                    "metadata": metadata or {},
                }
            )

        return chunks

    def _clean_text(self, text: str) -> str:
        """Clean text content.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove special characters that might interfere with chunking
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        return text.strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting
        sentences = re.split(r"[.!?]+", text)

        # Clean up sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        # Add punctuation back
        sentences = [
            s + "." if not s.endswith((".", "!", "?")) else s for s in sentences
        ]

        return sentences

    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from the end of a chunk.

        Args:
            text: Chunk text

        Returns:
            Overlap text
        """
        if len(text) <= self.chunk_overlap:
            return text

        # Get last chunk_overlap characters
        overlap_text = text[-self.chunk_overlap :]

        # Try to break at word boundary
        words = overlap_text.split()
        if len(words) > 1:
            # Take last few words that fit within overlap
            overlap_words = []
            current_length = 0

            for word in reversed(words):
                if current_length + len(word) + 1 <= self.chunk_overlap:
                    overlap_words.insert(0, word)
                    current_length += len(word) + 1
                else:
                    break

            if overlap_words:
                return " ".join(overlap_words) + " "

        return overlap_text

    def chunk_by_tokens(
        self,
        text: str,
        max_tokens: int = 1000,
        overlap_tokens: int = 100,
    ) -> List[Dict[str, Any]]:
        """Chunk text by tokens.

        Args:
            text: Text to chunk
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Overlap tokens between chunks

        Returns:
            List of chunks
        """
        if not self.tokenizer:
            # Fallback to character-based chunking
            return self._chunk_text(text)

        # Tokenize text
        tokens = self.tokenizer.encode(text)

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(tokens):
            # Get chunk tokens
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]

            # Decode tokens back to text
            chunk_text = self.tokenizer.decode(chunk_tokens)

            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "content": chunk_text,
                    "token_count": len(chunk_tokens),
                    "metadata": {},
                }
            )

            # Move start position with overlap
            start = end - overlap_tokens
            chunk_index += 1

            # Prevent infinite loop
            if start >= len(tokens) - overlap_tokens:
                break

        return chunks

    def chunk_by_paragraphs(
        self,
        text: str,
        max_chunk_size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Chunk text by paragraphs.

        Args:
            text: Text to chunk
            max_chunk_size: Maximum chunk size

        Returns:
            List of chunks
        """
        # Split into paragraphs
        paragraphs = text.split("\n\n")

        chunks = []
        current_chunk = ""
        chunk_index = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Check if adding this paragraph would exceed chunk size
            if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
                # Save current chunk
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "content": current_chunk.strip(),
                        "metadata": {"chunk_type": "paragraph"},
                    }
                )

                # Start new chunk
                current_chunk = paragraph
                chunk_index += 1
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        # Add final chunk
        if current_chunk.strip():
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "content": current_chunk.strip(),
                    "metadata": {"chunk_type": "paragraph"},
                }
            )

        return chunks
