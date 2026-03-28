"""
Tests for Example Repo MCP Server
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.mcp_server import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def mock_code_indexer():
    """Mock code indexer."""
    with patch("src.mcp_server.code_indexer") as mock:
        mock.index_codebase.return_value = {
            "files_count": 10,
            "languages": ["python", "javascript"],
            "index_size": 1024,
        }
        mock.search.return_value = [
            {
                "file": "test.py",
                "language": "python",
                "matches": [{"line_number": 1, "content": "def test_function():"}],
                "score": 1,
            }
        ]
        mock.get_stats.return_value = {
            "total_files": 10,
            "total_size": 1024,
            "languages": {"python": 5, "javascript": 5},
        }
        yield mock


@pytest.fixture
def mock_dependency_analyzer():
    """Mock dependency analyzer."""
    with patch("src.mcp_server.dependency_analyzer") as mock:
        mock.analyze_dependencies.return_value = {
            "project_type": "python",
            "dependencies": {"fastapi": {"version": "0.104.1", "type": "runtime"}},
            "graph": {"nodes": ["fastapi"], "edges": []},
            "vulnerabilities": [],
            "outdated": [],
        }
        mock.get_stats.return_value = {"analyzed_projects": 1, "total_dependencies": 1}
        yield mock


@pytest.fixture
def mock_project_analyzer():
    """Mock project analyzer."""
    with patch("src.mcp_server.project_analyzer") as mock:
        mock.analyze_project.return_value = {
            "name": "test-project",
            "type": "python",
            "size": {"total_files": 10, "total_size_mb": 1.0},
            "structure": {"directories": ["src", "tests"], "key_files": ["README.md"]},
            "metrics": {"lines_of_code": 100, "languages": {"python": 100}},
            "configuration": {"pyproject.toml": {"type": "python"}},
            "documentation": {"files": ["README.md"], "total_files": 1},
            "testing": {"files": ["test_main.py"], "total_files": 1},
            "ci_cd": {"files": [".github/workflows/ci.yml"], "total_files": 1},
        }
        mock.get_stats.return_value = {"analyzed_projects": 1, "cache_size": 1}
        yield mock


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "example-repo-mcp"}


class TestIndexCodebase:
    """Test codebase indexing endpoint."""

    def test_index_codebase_success(self, client, mock_code_indexer):
        """Test successful codebase indexing."""
        request_data = {
            "path": "/test/path",
            "languages": ["python", "javascript"],
            "include_tests": True,
        }

        with patch("pathlib.Path.exists", return_value=True):
            response = client.post("/index", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["indexed_files"] == 10
        assert data["languages"] == ["python", "javascript"]
        assert data["index_size"] == 1024

    def test_index_codebase_path_not_found(self, client, mock_code_indexer):
        """Test indexing with non-existent path."""
        request_data = {
            "path": "/nonexistent/path",
            "languages": ["python"],
            "include_tests": True,
        }

        with patch("pathlib.Path.exists", return_value=False):
            response = client.post("/index", json=request_data)

        assert response.status_code == 404
        assert "Path not found" in response.json()["detail"]

    def test_index_codebase_indexer_not_initialized(self, client):
        """Test indexing when indexer is not initialized."""
        request_data = {
            "path": "/test/path",
            "languages": ["python"],
            "include_tests": True,
        }

        with patch("src.mcp_server.code_indexer", None):
            with patch("pathlib.Path.exists", return_value=True):
                response = client.post("/index", json=request_data)

        assert response.status_code == 500
        assert "Code indexer not initialized" in response.json()["detail"]


class TestSearchCodebase:
    """Test codebase search endpoint."""

    def test_search_success(self, client, mock_code_indexer):
        """Test successful codebase search."""
        request_data = {
            "query": "test_function",
            "file_types": ["python"],
            "max_results": 5,
        }

        response = client.post("/search", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["query"] == "test_function"
        assert len(data["results"]) == 1
        assert data["results"][0]["file"] == "test.py"
        assert data["total_results"] == 1

    def test_search_indexer_not_initialized(self, client):
        """Test search when indexer is not initialized."""
        request_data = {
            "query": "test_function",
            "file_types": ["python"],
            "max_results": 5,
        }

        with patch("src.mcp_server.code_indexer", None):
            response = client.post("/search", json=request_data)

        assert response.status_code == 500
        assert "Code indexer not initialized" in response.json()["detail"]


class TestAnalyzeDependencies:
    """Test dependency analysis endpoint."""

    def test_analyze_dependencies_success(self, client, mock_dependency_analyzer):
        """Test successful dependency analysis."""
        request_data = {"path": "/test/path"}

        with patch("pathlib.Path.exists", return_value=True):
            response = client.post("/analyze-dependencies", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["path"] == "/test/path"
        assert data["dependencies"]["fastapi"]["version"] == "0.104.1"
        assert data["vulnerabilities"] == []
        assert data["outdated"] == []

    def test_analyze_dependencies_path_not_found(
        self, client, mock_dependency_analyzer
    ):
        """Test dependency analysis with non-existent path."""
        request_data = {"path": "/nonexistent/path"}

        with patch("pathlib.Path.exists", return_value=False):
            response = client.post("/analyze-dependencies", json=request_data)

        assert response.status_code == 404
        assert "Path not found" in response.json()["detail"]

    def test_analyze_dependencies_analyzer_not_initialized(self, client):
        """Test dependency analysis when analyzer is not initialized."""
        request_data = {"path": "/test/path"}

        with patch("src.mcp_server.dependency_analyzer", None):
            with patch("pathlib.Path.exists", return_value=True):
                response = client.post("/analyze-dependencies", json=request_data)

        assert response.status_code == 500
        assert "Dependency analyzer not initialized" in response.json()["detail"]


class TestProjectInfo:
    """Test project info endpoint."""

    def test_project_info_success(self, client, mock_project_analyzer):
        """Test successful project info retrieval."""
        request_data = {"path": "/test/path"}

        with patch("pathlib.Path.exists", return_value=True):
            response = client.post("/project-info", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["path"] == "/test/path"
        assert data["project_info"]["name"] == "test-project"
        assert data["project_info"]["type"] == "python"
        assert data["project_info"]["size"]["total_files"] == 10

    def test_project_info_path_not_found(self, client, mock_project_analyzer):
        """Test project info with non-existent path."""
        request_data = {"path": "/nonexistent/path"}

        with patch("pathlib.Path.exists", return_value=False):
            response = client.post("/project-info", json=request_data)

        assert response.status_code == 404
        assert "Path not found" in response.json()["detail"]

    def test_project_info_analyzer_not_initialized(self, client):
        """Test project info when analyzer is not initialized."""
        request_data = {"path": "/test/path"}

        with patch("src.mcp_server.project_analyzer", None):
            with patch("pathlib.Path.exists", return_value=True):
                response = client.post("/project-info", json=request_data)

        assert response.status_code == 500
        assert "Project analyzer not initialized" in response.json()["detail"]


class TestStats:
    """Test stats endpoint."""

    def test_stats_success(
        self, client, mock_code_indexer, mock_dependency_analyzer, mock_project_analyzer
    ):
        """Test successful stats retrieval."""
        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "example-repo-mcp"
        assert data["version"] == "0.1.0"
        assert data["status"] == "running"
        assert "indexer" in data
        assert "dependency_analyzer" in data
        assert "project_analyzer" in data

    def test_stats_error(self, client):
        """Test stats endpoint with error."""
        with patch(
            "src.mcp_server.code_indexer.get_stats", side_effect=Exception("Test error")
        ):
            response = client.get("/stats")

        assert response.status_code == 500
        assert "Error getting stats" in response.json()["detail"]
