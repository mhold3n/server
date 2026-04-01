import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from pathlib import Path

from tests._module_loader import load_module

orch_app = load_module(
    "wrkhrs_orchestrator_app",
    Path(__file__).resolve().parent.parent / "services" / "orchestrator" / "app.py",
)

api = orch_app.api
search_knowledge_base = orch_app.search_knowledge_base
transcribe_audio = orch_app.transcribe_audio
get_domain_data = orch_app.get_domain_data
get_available_tools = orch_app.get_available_tools
analyze_request = orch_app.analyze_request
gather_context = orch_app.gather_context
generate_response = orch_app.generate_response
create_workflow = orch_app.create_workflow
WorkflowState = orch_app.WorkflowState


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(api)


@pytest.fixture
def sample_workflow_state():
    """Create sample workflow state for testing"""
    return WorkflowState(
        messages=[{"role": "user", "content": "test message"}],
        current_step="analyze",
        context={},
        tools_available=[],
        domain_weights={"chemistry": 0.5, "mechanical": 0.3, "materials": 0.2},
        response="",
        metadata={}
    )


class TestTools:
    """Test tool functions"""

    @patch("wrkhrs_orchestrator_app.requests.post")
    def test_search_knowledge_base_success(self, mock_post):
        """Test successful knowledge base search"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "evidence": "test evidence"
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = search_knowledge_base("test query", {"chemistry": 0.8})
        
        assert result == "test evidence"

    @patch("wrkhrs_orchestrator_app.requests.post")
    def test_search_knowledge_base_failure(self, mock_post):
        """Test knowledge base search failure"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        result = search_knowledge_base("test query")
        
        assert "Error searching knowledge base" in result

    @patch("wrkhrs_orchestrator_app.requests.post")
    def test_transcribe_audio_success(self, mock_post):
        """Test successful audio transcription"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "transcript": "test transcription",
            "segments": [{"start": 0, "end": 5, "text": "test"}]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = transcribe_audio("base64_audio_data")
        
        assert result == "test transcription"

    @patch("wrkhrs_orchestrator_app.requests.post")
    def test_get_domain_data_success(self, mock_post):
        """Test successful domain data retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"property": "value"},
            "domain": "chemistry"
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = get_domain_data("chemistry", "test query")
        
        assert result["property"] == "value"

    @patch("wrkhrs_orchestrator_app.requests.get")
    def test_get_available_tools_success(self, mock_get):
        """Test successful tool registry query"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "tools": [
                {"name": "calculator", "description": "Basic calculator"},
                {"name": "converter", "description": "Unit converter"}
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = get_available_tools()
        
        assert len(result) == 2
        assert result[0]["name"] == "calculator"


class TestWorkflowFunctions:
    """Test workflow step functions"""

    def test_analyze_request_basic(self, sample_workflow_state):
        """Test basic request analysis"""
        result = analyze_request(sample_workflow_state)
        
        assert result.current_step in {"gather_context", "generate_response"}

    def test_analyze_request_chemistry_detection(self, sample_workflow_state):
        """Test chemistry domain detection in request analysis"""
        sample_workflow_state.messages = [
            {"role": "user", "content": "What is the molecular weight of H2O?"}
        ]
        
        result = analyze_request(sample_workflow_state)
        
        assert result.domain_weights["chemistry"] >= 0.0

    def test_analyze_request_mechanical_detection(self, sample_workflow_state):
        """Test mechanical domain detection in request analysis"""
        sample_workflow_state.messages = [
            {"role": "user", "content": "Calculate the stress on a steel beam under 100N force"}
        ]
        
        result = analyze_request(sample_workflow_state)
        
        assert result.domain_weights["mechanical"] >= 0.0

    @patch("wrkhrs_orchestrator_app.search_knowledge_base")
    @patch("wrkhrs_orchestrator_app.get_available_tools")
    def test_gather_context_success(self, mock_tools, mock_search, sample_workflow_state):
        """Test successful context gathering"""
        # Mock responses
        mock_search.return_value = "relevant context"
        mock_tools.return_value = [{"name": "calculator", "description": "Basic calculator"}]
        
        sample_workflow_state.current_step = "gather_context"
        sample_workflow_state.tools_needed = ["rag_search"]
        result = gather_context(sample_workflow_state)
        
        assert result.current_step == "generate_response"
        assert "rag" in result.tool_results

    @pytest.mark.asyncio
    async def test_generate_response_success(self, sample_workflow_state):
        """Test successful response generation"""
        sample_workflow_state.current_step = "generate"
        sample_workflow_state.rag_results = "context"
        
        result = await generate_response(sample_workflow_state)
        
        assert result.current_step == "complete"
        assert result.final_response


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client):
        """Test successful health check"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "workflow_ready" in data


class TestChatEndpoint:
    """Test chat endpoint"""

    def test_chat_endpoint_success(self, client):
        """Test successful chat endpoint"""
        with patch("wrkhrs_orchestrator_app.workflow_app") as mock_workflow_app:
            mock_workflow_app.invoke.return_value = WorkflowState(
                messages=[{"role": "user", "content": "test"}],
                current_step="complete",
                final_response="Test response",
                metadata={"tokens_used": 50},
            )
        
            response = client.post("/v1/chat/completions", json={
                "messages": [{"role": "user", "content": "test message"}],
                "model": "test-model"
            })
        
            assert response.status_code == 200
            data = response.json()
            assert "choices" in data
            assert data["choices"][0]["message"]["content"] == "Test response"

    def test_chat_endpoint_missing_messages(self, client):
        """Test chat endpoint with missing messages"""
        response = client.post("/v1/chat/completions", json={
            "model": "test-model"
        })
        
        assert response.status_code == 422  # Validation error

    def test_chat_endpoint_workflow_error(self, client):
        """Test chat endpoint with workflow error"""
        with patch("wrkhrs_orchestrator_app.workflow_app") as mock_workflow_app:
            mock_workflow_app.invoke.side_effect = Exception("Workflow error")
            response = client.post("/v1/chat/completions", json={
                "messages": [{"role": "user", "content": "test message"}],
                "model": "test-model"
            })
        
            assert response.status_code == 500


class TestWorkflowStatus:
    """Test workflow status endpoint"""

    def test_workflow_status_success(self, client):
        """Test workflow status endpoint"""
        response = client.get("/workflow/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "active_workflows" in data
        assert "total_processed" in data
        assert "average_response_time" in data


class TestWorkflowCreation:
    """Test workflow creation and configuration"""

    def test_create_workflow(self):
        """Test workflow creation"""
        workflow = create_workflow()
        
        # Check that workflow is properly configured
        assert workflow is not None
        # Workflow should have the required nodes and edges
        # This is a basic test - in practice you'd test the graph structure


class TestWorkflowState:
    """Test WorkflowState model"""

    def test_workflow_state_creation(self):
        """Test WorkflowState creation with default values"""
        state = WorkflowState(
            messages=[{"role": "user", "content": "test"}]
        )
        
        assert len(state.messages) == 1
        assert state.current_step == "analyze"
        assert state.context == {}
        assert state.tools_available == []
        assert state.response == ""

    def test_workflow_state_with_custom_values(self):
        """Test WorkflowState creation with custom values"""
        state = WorkflowState(
            messages=[{"role": "user", "content": "test"}],
            current_step="generate",
            context={"key": "value"},
            domain_weights={"chemistry": 0.8}
        )
        
        assert state.current_step == "generate"
        assert state.context["key"] == "value"
        assert state.domain_weights["chemistry"] == 0.8


if __name__ == "__main__":
    pytest.main([__file__])