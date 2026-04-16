import json

import httpx
import respx
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings
from src.routes.devplane import get_service, reset_devplane_service_for_tests


def test_ai_query_via_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w1",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post("/api/ai/query", json={"prompt": "hi", "use_router": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_name"] == "wrkhrs_chat"
        assert body["status"] in ("completed", "failed")


def test_ai_query_forwards_model_routing_hints():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w-route",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": "hi",
                "provider": "huggingface",
                "model": "Qwen/Qwen3-8B",
                "temperature": 0.25,
                "max_tokens": 512,
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["input_data"]["model"] == "Qwen/Qwen3-8B"
        assert payload["input_data"]["temperature"] == 0.25
        assert payload["input_data"]["max_tokens"] == 512
        assert payload["workflow_config"]["provider_preference"] == "huggingface"
        assert payload["workflow_config"]["model_routing"] == {
            "provider_preference": "huggingface",
            "model": "Qwen/Qwen3-8B",
            "temperature": 0.25,
            "max_tokens": 512,
        }


def test_ai_query_via_ai_stack():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w2",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post("/api/ai/query", json={"prompt": "hi", "use_router": False})
        assert resp.status_code == 200
        assert resp.json()["workflow_name"] == "wrkhrs_chat"


def test_ai_query_auto_promotes_complex_engineering_prompt():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "weng",
                    "workflow_name": "engineering_workflow",
                    "duration": 0.01,
                    "result": {
                        "final_response": "Engineering clarification required",
                        "clarification_questions": ["What system is in scope?"],
                    },
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": "Design an engineering workflow that refactors multiple files and adds deterministic verification gates for the orchestrator.",
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "engineering_workflow"
        assert payload["workflow_config"]["strict_engineering"] is True
        assert payload["input_data"]["knowledge_pool_assessment_ref"]
        assert "knowledge_pool_coverage" in payload["input_data"]


def test_ai_query_routes_chemistry_plus_engineering_directly_to_strict_mode():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "wstrict",
                    "workflow_name": "engineering_workflow",
                    "duration": 0.01,
                    "result": {
                        "final_response": "ok",
                        "required_gates": [],
                        "task_packets": [],
                    },
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": (
                    "Investigate catalyst reaction kinetics and mechanical transmission "
                    "tolerances together, then build the governed verification pipeline."
                ),
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "engineering_workflow"
        assert payload["workflow_config"]["engagement_mode"] == "strict_engineering"
        assert payload["workflow_config"]["strict_engineering"] is True
        assert payload["input_data"]["knowledge_pool_assessment_ref"]
        assert isinstance(payload["input_data"]["knowledge_candidate_refs"], list)


def test_ai_query_routes_bounded_repo_work_to_engineering_task():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "weng-task",
                    "workflow_name": "engineering_workflow",
                    "duration": 0.01,
                    "result": {
                        "final_response": "ok",
                        "required_gates": [],
                        "task_packets": [],
                    },
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": (
                    "Fix the repository endpoint bug in one file and add deterministic "
                    "verification tests for the bounded patch."
                ),
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "engineering_workflow"
        assert payload["workflow_config"]["engagement_mode"] == "engineering_task"
        assert payload["workflow_config"]["strict_engineering"] is False
        assert payload["input_data"]["knowledge_pool_assessment_ref"]


def test_ai_query_routes_quantitative_non_mutating_work_to_napkin_math():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "wnapkin",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": (
                    "Estimate shaft torque, backlash sensitivity, and thermal growth "
                    "for the mechanism with no repo mutation."
                ),
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "wrkhrs_chat"
        assert payload["workflow_config"]["engagement_mode"] == "napkin_math"
        assert payload["workflow_config"]["non_mutating_only"] is True
        assert "knowledge_required" in payload["input_data"]


def test_ai_query_routes_open_exploration_to_ideation():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "widea",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/query",
            json={
                "prompt": "Brainstorm possible approaches for a future engineering UI."
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "wrkhrs_chat"
        assert payload["workflow_config"]["engagement_mode"] == "ideation"
        assert payload["input_data"]["knowledge_pool_assessment_ref"]


def test_ai_query_strict_engineering_creates_visible_devplane_session(tmp_path):
    original_root = settings.devplane_root
    original_db = settings.devplane_db_path
    settings.devplane_root = str(tmp_path / "devplane")
    settings.devplane_db_path = str(tmp_path / "devplane.sqlite3")
    reset_devplane_service_for_tests()
    client = TestClient(app)
    try:
        task_packet_id = "11111111-1111-4111-8111-111111111111"
        with respx.mock(assert_all_called=True) as mock:
            route = mock.post(
                f"{settings.agent_platform_url}/v1/workflows/execute"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "completed",
                        "workflow_id": "weng-chat-1",
                        "workflow_name": "engineering_workflow",
                        "duration": 0.01,
                        "result": {
                            "final_response": "Structured coding output",
                            "referential_state": {
                                "problem_brief_ref": "artifact://problem_brief/pb-1",
                                "engineering_state_ref": "artifact://engineering_state/es-1",
                                "active_task_packet_id": task_packet_id,
                                "active_task_packet_ref": f"artifact://task_packet/{task_packet_id}",
                                "verification_report_ref": "artifact://verification_report/vr-1",
                                "selected_executor": "coding_model",
                            },
                            "problem_brief": {"title": "Strict task"},
                            "engineering_state": {
                                "open_issues": [],
                                "conflicts": [],
                            },
                            "task_queue": {"task_queue_id": "queue-1"},
                            "task_packets": [
                                {
                                    "task_packet_id": task_packet_id,
                                    "task_type": "CODEGEN",
                                    "routing_metadata": {
                                        "selected_executor": "coding_model",
                                    },
                                }
                            ],
                            "ready_for_task_decomposition": True,
                            "required_gates": [],
                            "verification_outcome": "PASS",
                            "verification_report": {
                                "verification_report_id": "vr-1",
                            },
                        },
                    },
                )
            )
            resp = client.post(
                "/api/ai/query",
                json={
                    "prompt": (
                        "Design an engineering workflow that refactors multiple files "
                        "and adds deterministic verification gates for the orchestrator."
                    ),
                },
            )
            assert resp.status_code == 200
            payload = json.loads(route.calls[0].request.content.decode("utf-8"))
            assert payload["workflow_name"] == "engineering_workflow"
            assert payload["input_data"]["engineering_session_id"]
            assert payload["input_data"]["task_id"]
            assert payload["input_data"]["run_id"]
            assert payload["input_data"]["knowledge_pool_assessment_ref"]

        session_id = resp.json()["result"]["referential_state"][
            "engineering_session_id"
        ]
        result_payload = resp.json()["result"]
        assert result_payload["knowledge_pool_assessment_ref"]
        assert "knowledge_pool_coverage" in result_payload
        assert "knowledge_candidate_refs" in result_payload
        assert "knowledge_required" in result_payload
        service = get_service()
        task = service.get_task(session_id)
        assert task.current_run_id
        assert task.dossier.engineering_session is not None
        assert (
            task.dossier.engineering_session.problem_brief_ref
            == "artifact://problem_brief/pb-1"
        )
        assert task.dossier.engineering_session.knowledge_pool_assessment_ref
        assert (
            task.dossier.engineering_session.active_task_packet_ref
            == f"artifact://task_packet/{task_packet_id}"
        )
        assert task.dossier.engineering_session.verification_report_ref == (
            "artifact://verification_report/vr-1"
        )
        assert (
            task.dossier.engineering_session.active_selected_executor == "coding_model"
        )

        snapshot = service.load_engineering_session_snapshot(session_id=session_id)
        assert snapshot is not None
        assert (
            snapshot["verification_report_ref"] == "artifact://verification_report/vr-1"
        )
        assert snapshot["active_selected_executor"] == "coding_model"
        assert snapshot["knowledge_pool_assessment_ref"]
        assert "knowledge_pool_coverage" in snapshot

        reset_devplane_service_for_tests()
        with respx.mock(assert_all_called=True) as mock:
            route = mock.post(
                f"{settings.agent_platform_url}/v1/workflows/execute"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "completed",
                        "workflow_id": "weng-chat-2",
                        "workflow_name": "engineering_workflow",
                        "duration": 0.01,
                        "result": {
                            "final_response": "Resume strict session",
                            "referential_state": {},
                            "task_packets": [],
                            "required_gates": [],
                        },
                    },
                )
            )
            resumed = client.post(
                "/api/ai/query",
                json={
                    "prompt": "Continue the strict engineering session",
                    "context": {"engineering_session_id": session_id},
                },
            )
            assert resumed.status_code == 200
            resumed_payload = json.loads(route.calls[0].request.content.decode("utf-8"))
            assert resumed_payload["input_data"]["engineering_session_id"] == session_id
            assert resumed_payload["input_data"]["task_id"] == session_id
    finally:
        settings.devplane_root = original_root
        settings.devplane_db_path = original_db
        reset_devplane_service_for_tests()


def test_ai_query_never_auto_deescalates_without_confirmation(tmp_path):
    original_root = settings.devplane_root
    original_db = settings.devplane_db_path
    settings.devplane_root = str(tmp_path / "devplane")
    settings.devplane_db_path = str(tmp_path / "devplane.sqlite3")
    reset_devplane_service_for_tests()
    client = TestClient(app)
    try:
        service = get_service()
        task, _run = service.ensure_engineering_chat_session(
            user_intent="Strict engineering session",
            engagement_mode="strict_engineering",
            engagement_mode_source="explicit",
            minimum_engagement_mode="strict_engineering",
        )
        with respx.mock(assert_all_called=True) as mock:
            route = mock.post(
                f"{settings.agent_platform_url}/v1/workflows/execute"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "completed",
                        "workflow_id": "wresume-floor",
                        "workflow_name": "engineering_workflow",
                        "duration": 0.01,
                        "result": {
                            "final_response": "Continuing governed engineering session.",
                            "referential_state": {},
                            "task_packets": [],
                            "required_gates": [],
                        },
                    },
                )
            )
            resp = client.post(
                "/api/ai/query",
                json={
                    "prompt": "Can we just brainstorm this casually now?",
                    "engagement_mode": "ideation",
                    "context": {"engineering_session_id": task.task_id},
                },
            )
            assert resp.status_code == 200
            payload = json.loads(route.calls[0].request.content.decode("utf-8"))
            assert payload["workflow_name"] == "engineering_workflow"
            assert payload["workflow_config"]["engagement_mode"] == "strict_engineering"
            assert (
                payload["workflow_config"]["pending_mode_change"]["proposed_mode"]
                == "ideation"
            )
            body = resp.json()
            assert body["result"]["pending_mode_change"]["proposed_mode"] == "ideation"
            assert "confirm explicitly" in body["result"]["final_response"]
    finally:
        settings.devplane_root = original_root
        settings.devplane_db_path = original_db
        reset_devplane_service_for_tests()


def test_workflows_code_rag_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        # required MCP tool calls
        mock.post(f"{settings.router_url}/mcp/servers/github-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        mock.post(f"{settings.router_url}/mcp/servers/filesystem-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        mock.post(f"{settings.router_url}/mcp/servers/vector-db-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w3",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={"name": "code-rag", "input": {"query": "test"}},
        )
        assert resp.status_code == 200
        # Assert prompt assembly contains the task card system prompt.
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        assert payload["workflow_name"] == "wrkhrs_chat"
        messages = payload["input_data"]["messages"]
        assert messages[0]["role"] == "system"
        assert "Always cite sources" in messages[0]["content"]


def test_workflows_media_fixups_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.router_url}/mcp/servers/filesystem-mcp/call").mock(
            return_value=httpx.Response(200, json={"result": {"ok": True}})
        )
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w4",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={
                "name": "media-fixups",
                "input": {"file": "/mnt/appdata/addons/documents_processed/a.pdf"},
            },
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        messages = payload["input_data"]["messages"]
        assert messages[0]["role"] == "system"
        assert "media and document fix-ups" in messages[0]["content"]


def test_workflows_sysadmin_ops_calls_router():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "w5",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "ok"},
                },
            )
        )
        resp = client.post(
            "/api/ai/workflows/run",
            json={"name": "sysadmin-ops", "input": {"task": "describe netplan"}},
        )
        assert resp.status_code == 200
        payload = json.loads(route.calls[0].request.content.decode("utf-8"))
        messages = payload["input_data"]["messages"]
        assert messages[0]["role"] == "system"
        assert "sysadmin assistant" in messages[0]["content"]


def test_simulations_analyze_calls_ai_stack():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{settings.agent_platform_url}/v1/workflows/execute").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "completed",
                    "workflow_id": "wsim",
                    "workflow_name": "wrkhrs_chat",
                    "duration": 0.01,
                    "result": {"final_response": "analysis"},
                },
            )
        )
        resp = client.post(
            "/api/ai/simulations/analyze",
            json={"payload": {"a": 1}, "instructions": "analyze"},
        )
        assert resp.status_code == 200
        assert resp.json()["workflow_name"] == "wrkhrs_chat"


def test_workflow_prompt_fallback_uses_query_or_prompt_keys():
    from src.routes.ai import _workflow_prompt_from_card

    assert _workflow_prompt_from_card("other-workflow", {"prompt": "p"}) == "p"
    assert _workflow_prompt_from_card("other-workflow", {"query": "q"}) == "q"
    assert _workflow_prompt_from_card("other-workflow", {}) == ""
