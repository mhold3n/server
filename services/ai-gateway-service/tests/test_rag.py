import pytest
import numpy as np
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import io

import sys
import os

# Add the parent directory to Python path for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Need to mock model loading before importing app
with patch.dict("os.environ", {"WRKHRS_DISABLE_MODEL_LOAD": "1"}):
    from services.rag.app import api, rag_service, RAGService


@pytest.fixture
def client():
    return TestClient(api)


@pytest.fixture
def sample_document():
    return {
        "content": "This is a sample technical document about Python asyncio.",
        "metadata": {"author": "Test Author"},
        "domain": "general",
        "source": "test_script",
    }


@pytest.fixture(autouse=True)
def setup_rag_service():
    # Set up some dummy state
    rag_service.qdrant_client = Mock()
    rag_service.embedding_model = Mock()
    yield
    rag_service.qdrant_client = None
    rag_service.embedding_model = None


class TestRAGService:
    """Test RAG service functionality"""

    @pytest.mark.asyncio
    @patch("services.rag.app.SentenceTransformer")
    @patch("services.rag.app.QdrantClient")
    async def test_rag_service_initialization(
        self, mock_client_cls, mock_transformer_cls
    ):
        """Test RAG service initialization"""
        with patch.dict(
            os.environ, {"WRKHRS_DISABLE_MODEL_LOAD": "0", "USE_MOCK_MODELS": "false"}
        ):
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_transformer_cls.return_value = mock_model
            mock_client = Mock()

            # ensure_collection_exists will iterate over this
            mock_collection = Mock()
            mock_collection.name = "test_collection"
            mock_collections_response = Mock()
            mock_collections_response.collections = [mock_collection]
            mock_client.get_collections.return_value = mock_collections_response

            mock_client_cls.return_value = mock_client

            service = RAGService()
            await service.initialize()

            assert service.embedding_model is not None
            assert service.qdrant_client is not None

    def test_chunk_text(self):
        """Test text chunking logic"""
        service = RAGService()

        # Test short text
        text = "Short sentence"
        chunks = service.chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == text

        # Test long text
        long_text = "Word " * 200
        chunks = service.chunk_text(long_text, chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_calculate_domain_score_chemistry(self):
        """Test domain score calculation for chemistry"""
        service = RAGService()
        text = "molecule reaction chemical compound element solubility"
        domain_weights = {"chemistry": 0.8, "mechanical": 0.1, "materials": 0.1}

        score = service.calculate_domain_score(text, domain_weights)
        assert (
            score > 0.3
        )  # Adjusted since max for 5 keywords is 0.5 (scaled by weight)

    def test_calculate_domain_score_mechanical(self):
        """Test domain score calculation for mechanical"""
        service = RAGService()
        text = "stress strain force material engineering tension compression load"
        domain_weights = {"chemistry": 0.1, "mechanical": 0.8, "materials": 0.1}

        score = service.calculate_domain_score(text, domain_weights)
        assert score > 0.3

    @pytest.mark.asyncio
    @patch("services.rag.app.rag_service.embed", new_callable=AsyncMock)
    async def test_add_document_success(self, mock_embed, sample_document):
        """Test successful document addition"""
        # Mock embedding generation
        mock_embed.return_value = np.random.rand(1, 384)

        # Mock Qdrant client
        rag_service.qdrant_client.upsert = Mock()

        # Test adding document
        with patch.object(rag_service, "chunk_text") as mock_chunk:
            mock_chunk.return_value = [sample_document["content"]]

            result = await rag_service.add_document(
                content=sample_document["content"],
                metadata=sample_document["metadata"],
                domain=sample_document["domain"],
                source=sample_document["source"],
            )

            assert "document_id" in result
            assert result["chunks_created"] == 1
            rag_service.qdrant_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.rag.app.rag_service.embed", new_callable=AsyncMock)
    async def test_search_documents_success(self, mock_embed):
        """Test successful document search"""
        # Mock embedding generation
        mock_embed.return_value = np.random.rand(1, 384)

        # Mock Qdrant search results
        mock_result = Mock()
        mock_result.payload = {
            "content": "Sample result text",
            "metadata": {"title": "Test"},
            "domain": "chemistry",
            "domain_score": 0.8,
        }
        mock_result.score = 0.9

        # IMPORTANT: ensure generator / iterable for results
        rag_service.qdrant_client.search.return_value = [mock_result]

        # Test search
        results = await rag_service.search(
            query="molecular weight",
            domain_weights={"chemistry": 0.8},
            k=5,
            threshold=0.7,
            use_bm25_reranking=False,
        )

        assert len(results["results"]) == 1
        assert results["results"][0]["embedding_score"] == 0.9
        assert results["results"][0]["content"] == "Sample result text"

    @pytest.mark.asyncio
    @patch("services.rag.app.rag_service.embed", new_callable=AsyncMock)
    async def test_search_documents_no_results(self, mock_embed):
        """Test search with no results above threshold"""
        # Mock embedding generation
        mock_embed.return_value = np.random.rand(1, 384)

        # Mock low-score results
        mock_result = Mock()
        mock_result.score = 0.1  # very low score
        mock_result.payload = {"content": "Sample", "domain_score": 0.1}
        rag_service.qdrant_client.search.return_value = [mock_result]

        # Test search with high threshold
        results = await rag_service.search(query="test query", threshold=0.8)

        assert len(results["results"]) == 0


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client):
        """Test successful health check"""
        rag_service.qdrant_client.get_collection.return_value = Mock()

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "embedding_model_loaded" in data
        assert data["qdrant_status"] == "connected"

    def test_health_check_qdrant_error(self, client):
        """Test health check with Qdrant connection error"""
        rag_service.qdrant_client.get_collections.side_effect = Exception(
            "Connection error"
        )

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["qdrant_status"] == "error"


class TestSearchEndpoint:
    """Test search documents endpoint"""

    @patch("services.rag.app.RAGService.search", new_callable=AsyncMock)
    def test_search_endpoint_success(self, mock_search, client):
        """Test successful search endpoint"""
        # Mock search results
        mock_search.return_value = {
            "results": [
                {
                    "content": "Test result",
                    "embedding_score": 0.9,
                    "metadata": {"title": "Test Doc"},
                    "domain": "chemistry",
                }
            ],
            "total_found": 1,
            "query": "molecular weight",
            "search_time": 0.1,
            "evidence": "Found test evidence.",
        }

        response = client.post(
            "/search",
            json={
                "query": "molecular weight",
                "domain_weights": {"chemistry": 0.8},
                "k": 5,
                "threshold": 0.7,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["embedding_score"] == 0.9

    @patch("services.rag.app.RAGService.search", new_callable=AsyncMock)
    def test_search_endpoint_error(self, mock_search, client):
        """Test search endpoint with service error"""
        mock_search.side_effect = Exception("Search error")

        response = client.post("/search", json={"query": "test query"})

        assert response.status_code == 500

    def test_search_endpoint_missing_query(self, client):
        """Test search endpoint with missing query"""
        response = client.post("/search", json={})

        assert response.status_code == 422  # Validation error


class TestAddDocumentEndpoint:
    """Test add document endpoint"""

    @patch("services.rag.app.RAGService.add_document", new_callable=AsyncMock)
    def test_add_document_success(self, mock_add, client):
        """Test successful document addition"""
        mock_add.return_value = {
            "chunks_created": 3,
            "document_id": "test_doc_123",
            "embedding_dimension": 384,
        }

        response = client.post(
            "/documents",
            json={
                "content": "Test document content",
                "metadata": {"title": "Test"},
                "domain": "chemistry",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "test_doc_123"
        assert data["chunks_created"] == 3

    @patch("services.rag.app.RAGService.add_document", new_callable=AsyncMock)
    def test_add_document_error(self, mock_add, client):
        """Test document addition with service error"""
        mock_add.side_effect = Exception("Add document error")

        response = client.post("/documents", json={"content": "Test content"})

        assert response.status_code == 500


class TestUploadDocumentEndpoint:
    """Test upload document endpoint"""

    @patch("services.rag.app.RAGService.add_document", new_callable=AsyncMock)
    def test_upload_document_success(self, mock_add, client):
        """Test successful document upload"""
        mock_add.return_value = {
            "chunks_created": 2,
            "document_id": "uploaded_doc_456",
            "embedding_dimension": 384,
        }

        # Create test file
        test_content = b"This is a test document for upload."
        test_file = io.BytesIO(test_content)

        response = client.post(
            "/documents/upload",
            files={"file": ("test.txt", test_file, "text/plain")},
            data={"domain": "materials", "metadata": "{}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "uploaded_doc_456"

    def test_upload_document_invalid_file_type(self, client):
        """Test upload with invalid file type"""
        test_content = b"\xff\xfe\x00\x00invalid bytes"
        test_file = io.BytesIO(test_content)

        response = client.post(
            "/documents/upload",
            files={"file": ("test.bin", test_file, "application/octet-stream")},
            data={"domain": "general"},
        )

        assert response.status_code == 500


class TestCollectionEndpoints:
    """Test collection management endpoints"""

    def test_get_collection_info_success(self, client):
        """Test successful collection info retrieval"""
        mock_collection = Mock()
        mock_collection.points_count = 100
        mock_collection.vectors_count = 100
        mock_collection.status = "green"
        rag_service.qdrant_client.get_collection.return_value = mock_collection

        response = client.get("/collections/info")
        assert response.status_code == 200

        data = response.json()
        assert "collection_name" in data
        assert "points_count" in data

    @patch(
        "services.rag.app.RAGService.ensure_collection_exists", new_callable=AsyncMock
    )
    def test_clear_collection_success(self, mock_ensure, client):
        """Test successful collection clearing"""
        response = client.delete("/collections/clear")
        assert response.status_code == 200

        data = response.json()
        assert "cleared" in data["message"]


class TestDomainScoring:
    """Test domain-specific scoring functionality"""

    def test_domain_score_mixed_content(self):
        """Test domain scoring with mixed content"""
        service = RAGService()
        text = "Steel beam analysis shows stress patterns in molecular bonding."

        # Test different domain weights
        chem_weights = {"chemistry": 0.8, "mechanical": 0.1, "materials": 0.1}
        mech_weights = {"chemistry": 0.1, "mechanical": 0.8, "materials": 0.1}

        chem_score = service.calculate_domain_score(text, chem_weights)
        mech_score = service.calculate_domain_score(text, mech_weights)

        # Both should have some relevance, but different weightings
        assert chem_score > 0
        assert mech_score > 0

    def test_domain_score_no_weights(self):
        """Test domain scoring without weights"""
        service = RAGService()
        text = "General text content."

        score = service.calculate_domain_score(text, None)

        assert score >= 0
        assert score <= 1


if __name__ == "__main__":
    pytest.main([__file__])
