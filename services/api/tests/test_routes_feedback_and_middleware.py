"""Exercise feedback and policy-middleware routes for coverage."""

from __future__ import annotations

import builtins
import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes import feedback as feedback_routes
from src.routes import middleware as middleware_routes
from src.routes.feedback import FEEDBACK_REASONS


@pytest.fixture
def feedback_app(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fb_file = tmp_path / "feedback.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))

    mock_ml = Mock()
    mock_ml.log_dict = Mock()
    mock_ml.log_params = Mock()
    monkeypatch.setattr(feedback_routes, "mlflow_logger", mock_ml)

    app = FastAPI()
    app.include_router(feedback_routes.router)
    return TestClient(app)


def test_feedback_reasons_list(feedback_app: TestClient) -> None:
    r = feedback_app.get("/feedback/v1/feedback/reasons")
    assert r.status_code == 200
    body = r.json()
    assert "reasons" in body
    assert FEEDBACK_REASONS[0] in body["reasons"]


def test_feedback_summary_empty_when_no_entries(
    feedback_app: TestClient,
) -> None:
    r = feedback_app.get("/feedback/v1/feedback/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_feedback"] == 0
    assert body["average_rating"] == 0.0


def test_feedback_summary_days_zero_returns_all(
    feedback_app: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fb_file = tmp_path / "feedback.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))
    old = datetime.now(UTC).timestamp() - (400 * 24 * 60 * 60)
    raw = [
        {
            "feedback_id": "old",
            "run_id": "r-old",
            "rating": 3,
            "reasons": [],
            "notes": "",
            "timestamp": datetime.fromtimestamp(old, tz=UTC).isoformat(),
        }
    ]
    fb_file.write_text(json.dumps(raw))
    r = feedback_app.get("/feedback/v1/feedback/summary?days=0")
    assert r.status_code == 200
    assert r.json()["total_feedback"] == 1


def test_feedback_get_for_run_invalid_json_file(
    feedback_app: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fb_file = tmp_path / "feedback.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))
    fb_file.write_text("not-json")
    r = feedback_app.get("/feedback/v1/feedback/some-run")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_all_feedback_corrupt_file_returns_empty(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fb_file = tmp_path / "corrupt.json"
    fb_file.write_text("{not valid")
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))
    from src.routes.feedback import _get_all_feedback

    assert await _get_all_feedback(days=7) == []


@pytest.mark.asyncio
async def test_store_feedback_write_failure_propagates(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fb_file = tmp_path / "ro.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))
    from src.routes import feedback as fr

    real_open = builtins.open

    def guarded_open(
        path: str | int,
        mode: str = "r",
        *a: object,
        **kw: object,
    ) -> object:
        if str(path) == str(fb_file) and "w" in mode:
            raise OSError("write failed")
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr(builtins, "open", guarded_open)
    with pytest.raises(OSError, match="write failed"):
        await fr._store_feedback(
            {
                "feedback_id": "f",
                "run_id": "r",
                "rating": 3,
                "reasons": [],
                "notes": "",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )


@pytest.mark.asyncio
async def test_delete_feedback_write_failure_returns_false(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fb_file = tmp_path / "fb.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))
    ts = datetime.now(UTC).isoformat()
    fb_file.write_text(
        json.dumps(
            [
                {
                    "feedback_id": "to-remove",
                    "run_id": "r",
                    "rating": 2,
                    "reasons": [],
                    "notes": "",
                    "timestamp": ts,
                }
            ]
        )
    )
    real_open = builtins.open

    def guarded_open(
        path: str | int,
        mode: str = "r",
        *a: object,
        **kw: object,
    ) -> object:
        if str(path) == str(fb_file) and "w" in mode:
            raise OSError("cannot save")
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr(builtins, "open", guarded_open)
    from src.routes.feedback import _delete_feedback

    assert await _delete_feedback("to-remove") is False


def test_feedback_submit_get_summary_delete_flow(feedback_app: TestClient) -> None:
    payload = {
        "run_id": "run-1",
        "rating": 5,
        "reasons": ["accurate_information"],
        "notes": "ok",
    }
    r = feedback_app.post("/feedback/v1/feedback", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == "run-1"
    fid = data["feedback_id"]

    r_bad = feedback_app.post(
        "/feedback/v1/feedback",
        json={**payload, "reasons": ["not_a_valid_reason"]},
    )
    assert r_bad.status_code == 400

    listed = feedback_app.get("/feedback/v1/feedback/run-1")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    summary = feedback_app.get("/feedback/v1/feedback/summary?limit=10&days=30")
    assert summary.status_code == 200
    s = summary.json()
    assert s["total_feedback"] >= 1

    deleted = feedback_app.delete(f"/feedback/v1/feedback/{fid}")
    assert deleted.status_code == 200

    missing = feedback_app.delete("/feedback/v1/feedback/nonexistent-id")
    assert missing.status_code == 404


@pytest.fixture
def policy_mw_app() -> TestClient:
    app = FastAPI()
    app.include_router(middleware_routes.router)
    return TestClient(app)


def test_middleware_registry_and_policy_info(policy_mw_app: TestClient) -> None:
    r = policy_mw_app.get("/middleware/registry")
    assert r.status_code == 200
    body = r.json()
    assert "policies" in body
    assert "summary" in body

    if body["policies"]:
        name = body["policies"][0]["name"]
        one = policy_mw_app.get(f"/middleware/registry/{name}")
        assert one.status_code == 200
        sch = policy_mw_app.get(f"/middleware/registry/{name}/schema")
        assert sch.status_code in (200, 404)

    nf = policy_mw_app.get("/middleware/registry/__definitely_missing_policy__")
    assert nf.status_code == 404


def test_middleware_validate_empty_policies(policy_mw_app: TestClient) -> None:
    r = policy_mw_app.post(
        "/middleware/validate",
        json={"content": "hello", "policies": []},
    )
    assert r.status_code == 200
    out = r.json()
    assert out["passed"] is True


def test_middleware_health(policy_mw_app: TestClient) -> None:
    r = policy_mw_app.get("/middleware/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "policies" in body


def test_middleware_schema_not_found(policy_mw_app: TestClient) -> None:
    r = policy_mw_app.get("/middleware/registry/__no_such__/schema")
    assert r.status_code == 404


def test_middleware_validate_and_config_with_registry(
    policy_mw_app: TestClient,
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p0 = names[0]
    r = policy_mw_app.post(
        "/middleware/validate",
        json={"content": "test output with [1] citation.", "policies": [p0]},
    )
    assert r.status_code == 200
    body = r.json()
    assert "policy_results" in body

    r2 = policy_mw_app.post(
        f"/middleware/registry/{p0}/config",
        json={"_note": "noop-for-test"},
    )
    assert r2.status_code in (200, 404, 500)

    en = policy_mw_app.post(f"/middleware/registry/{p0}/enable")
    dis = policy_mw_app.post(f"/middleware/registry/{p0}/disable")
    assert en.status_code == 200
    assert dis.status_code == 200


def test_feedback_submit_still_ok_when_mlflow_logs_fail(
    feedback_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ml = Mock()
    mock_ml.log_dict = Mock(side_effect=RuntimeError("mlflow down"))
    mock_ml.log_params = Mock()
    monkeypatch.setattr(feedback_routes, "mlflow_logger", mock_ml)
    payload = {
        "run_id": "run-mlf",
        "rating": 4,
        "reasons": ["accurate_information"],
    }
    r = feedback_app.post("/feedback/v1/feedback", json=payload)
    assert r.status_code == 200


async def _async_boom(*_a, **_k) -> None:
    raise RuntimeError("store failed")


def test_feedback_submit_500_when_store_fails(
    feedback_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feedback_routes, "_store_feedback", _async_boom)
    r = feedback_app.post(
        "/feedback/v1/feedback",
        json={
            "run_id": "r",
            "rating": 3,
            "reasons": ["accurate_information"],
        },
    )
    assert r.status_code == 500


async def _async_boom2(*_a, **_k) -> list:
    raise RuntimeError("summary failed")


def test_feedback_summary_500_when_list_fails(
    feedback_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feedback_routes, "_get_all_feedback", _async_boom2)
    r = feedback_app.get("/feedback/v1/feedback/summary")
    assert r.status_code == 500


async def _async_boom3(_run_id: str) -> list:
    raise RuntimeError("run lookup failed")


def test_feedback_get_for_run_500(
    feedback_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feedback_routes, "_get_feedback_for_run", _async_boom3)
    r = feedback_app.get("/feedback/v1/feedback/some-run")
    assert r.status_code == 500


async def _async_boom4(_fid: str) -> bool:
    raise RuntimeError("delete internal")


def test_feedback_delete_500(
    feedback_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feedback_routes, "_delete_feedback", _async_boom4)
    r = feedback_app.delete("/feedback/v1/feedback/fb-1")
    assert r.status_code == 500


def test_feedback_summary_skips_malformed_timestamps(
    feedback_app: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fb_file = tmp_path / "feedback.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(fb_file))
    good = datetime.now(UTC).isoformat()
    raw = [
        {
            "feedback_id": "f1",
            "run_id": "a",
            "rating": 5,
            "reasons": ["accurate_information"],
            "notes": "",
            "timestamp": good,
        },
        {
            "feedback_id": "f2",
            "run_id": "b",
            "rating": 2,
            "reasons": [],
            "notes": "",
            "timestamp": "not-valid-iso",
        },
    ]
    fb_file.write_text(json.dumps(raw))
    r = feedback_app.get("/feedback/v1/feedback/summary?days=30")
    assert r.status_code == 200
    assert r.json()["total_feedback"] == 1


def test_middleware_registry_500(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "get_available_policies",
        boom,
    )
    r = policy_mw_app.get("/middleware/registry")
    assert r.status_code == 500


def test_middleware_health_unhealthy(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise RuntimeError("no summary")

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "get_policy_summary",
        boom,
    )
    r = policy_mw_app.get("/middleware/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unhealthy"
    assert "error" in body


def test_middleware_policy_schema_route_500(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p = names[0]

    def bad_schema(name: str) -> dict | None:
        if name == p:
            raise ValueError("schema boom")
        return None

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "get_policy_schema",
        bad_schema,
    )
    r = policy_mw_app.get(f"/middleware/registry/{p}/schema")
    assert r.status_code == 500


def test_middleware_policy_info_internal_error(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p = names[0]
    orig_schema = policy_registry.get_policy_schema

    def bad_schema(name: str) -> dict | None:
        if name == p:
            raise ValueError("info boom")
        return orig_schema(name)

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "get_policy_schema",
        bad_schema,
    )
    r = policy_mw_app.get(f"/middleware/registry/{p}")
    assert r.status_code == 500


def test_middleware_validate_logs_then_fails_500(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p0 = names[0]

    def boom(*_a, **_k) -> None:
        raise RuntimeError("after validate")

    monkeypatch.setattr(middleware_routes.logger, "info", boom)
    r = policy_mw_app.post(
        "/middleware/validate",
        json={"content": "hello world [1] cited.", "policies": [p0]},
    )
    assert r.status_code == 500


def test_middleware_update_config_500_when_update_returns_false(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p0 = names[0]

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "update_policy_config",
        lambda _n, _c: False,
    )
    r = policy_mw_app.post(
        f"/middleware/registry/{p0}/config",
        json={"x": 1},
    )
    assert r.status_code == 500


def test_middleware_enable_internal_error_500(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p0 = names[0]

    def bad(_name: str) -> bool:
        raise RuntimeError("enable boom")

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "enable_policy",
        bad,
    )
    r = policy_mw_app.post(f"/middleware/registry/{p0}/enable")
    assert r.status_code == 500


def test_middleware_disable_internal_error_500(
    policy_mw_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.policies.registry import policy_registry

    names = list(policy_registry.policies.keys())
    if not names:
        pytest.skip("no policies registered")
    for n in names:
        policy_registry.enable_policy(n)
    p0 = names[0]

    def bad(_name: str) -> bool:
        raise RuntimeError("disable boom")

    monkeypatch.setattr(
        middleware_routes.policy_registry,
        "disable_policy",
        bad,
    )
    r = policy_mw_app.post(f"/middleware/registry/{p0}/disable")
    assert r.status_code == 500
