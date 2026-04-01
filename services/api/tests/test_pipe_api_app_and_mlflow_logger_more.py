from __future__ import annotations

import contextlib
import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _request_with_headers(headers: dict[str, str] | None = None) -> Request:
    raw = []
    for k, v in (headers or {}).items():
        raw.append((k.encode("latin-1"), v.encode("latin-1")))
    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/v1/chat/completions",
        "raw_path": b"/v1/chat/completions",
        "headers": raw,
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
    }
    return Request(scope)


def test_app_metrics_disabled_404(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.app as app_mod

    monkeypatch.setattr(app_mod.settings, "enable_metrics", False, raising=False)
    with pytest.raises(HTTPException) as exc2:
        import anyio

        anyio.run(app_mod.metrics)
    assert exc2.value.status_code == 404


@pytest.mark.asyncio
async def test_chat_completions_validation_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.app as app_mod

    req = _request_with_headers(
        {"x-trace-id": "t", "x-run-id": "r", "x-policy-set": "p"}
    )

    monkeypatch.setattr(app_mod, "openai_client", None)
    with pytest.raises(HTTPException) as exc1:
        await app_mod.chat_completions(
            app_mod.ChatRequest(
                model="m", messages=[app_mod.ChatMessage(role="user", content="hi")]
            ),
            req,
        )
    assert exc1.value.status_code == 503

    class _OpenAI:
        class _Chat:
            class _Completions:
                async def create(self, **_: Any) -> Any:
                    return SimpleNamespace(choices=[], usage=None)

            completions = _Completions()

        chat = _Chat()

    monkeypatch.setattr(app_mod, "openai_client", _OpenAI())
    with pytest.raises(HTTPException) as exc2:
        await app_mod.chat_completions(app_mod.ChatRequest(model="m", messages=[]), req)
    assert exc2.value.status_code == 422

    with pytest.raises(HTTPException) as exc3:
        await app_mod.chat_completions(
            app_mod.ChatRequest(
                model="m",
                messages=[app_mod.ChatMessage(role="user", content="hi")],
                stream=True,
            ),
            req,
        )
    assert exc3.value.status_code == 501


@pytest.mark.asyncio
async def test_chat_completions_success_includes_policy_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.app as app_mod

    # Ensure request context contains trace/run IDs for logging branch.
    monkeypatch.setattr(
        app_mod,
        "get_request_context",
        lambda _req: {"trace_id": "t1", "run_id": "r1", "policy_set": "default"},
    )

    class _Completion:
        def __init__(self):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content="ok"))]
            self.usage = {"total_tokens": 1}
            self.id = "c1"
            self.object = "chat.completion"
            self.created = 1
            self.model = "m"

        def dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "choices": [{"message": {"content": "ok"}}],
                "usage": self.usage,
            }

    class _OpenAI:
        class _Chat:
            class _Completions:
                async def create(self, **_: Any) -> Any:
                    return _Completion()

            completions = _Completions()

        chat = _Chat()

    monkeypatch.setattr(app_mod, "openai_client", _OpenAI())

    class _Verdict:
        overall_passed = True
        overall_score = 0.99
        total_violations = 0
        total_suggestions = 0
        policy_results: dict[str, Any] = {}

        def model_dump(self) -> dict[str, Any]:
            return {"overall_passed": True}

    async def _validate(**_: Any) -> Any:
        return _Verdict()

    monkeypatch.setattr(app_mod.policy_enforcer, "validate", _validate)

    # Cover MLflow logging branch without real MLflow.
    class _ML:  # minimal module-like object
        @staticmethod
        def start_run(**_: Any):
            return contextlib.nullcontext()

        @staticmethod
        def set_tag(*_: Any, **__: Any) -> None:
            return None

        @staticmethod
        def log_metrics(*_: Any, **__: Any) -> None:
            return None

        @staticmethod
        def log_metric(*_: Any, **__: Any) -> None:
            return None

    monkeypatch.setattr(app_mod, "mlflow_logger", object())

    # The handler imports mlflow inside the function, so patch sys.modules.
    monkeypatch.setitem(sys.modules, "mlflow", _ML)

    # Cover span attribute propagation branch.
    class _Span:
        def __init__(self) -> None:
            self.attrs: dict[str, Any] = {}

        def is_recording(self) -> bool:
            return True

        def set_attribute(self, k: str, v: Any) -> None:
            self.attrs[k] = v

    monkeypatch.setattr(app_mod.trace, "get_current_span", lambda: _Span())

    resp = await app_mod.chat_completions(
        app_mod.ChatRequest(
            model="m",
            messages=[app_mod.ChatMessage(role="user", content="hi")],
        ),
        _request_with_headers(
            {"x-trace-id": "t1", "x-run-id": "r1", "x-policy-set": "default"}
        ),
    )
    assert resp.headers["x-policy-verdict"] == "True"
    assert float(resp.headers["x-policy-score"]) == pytest.approx(0.99)


@pytest.mark.asyncio
async def test_chat_completions_error_maps_to_http_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.app as app_mod

    class _OpenAI:
        class _Chat:
            class _Completions:
                async def create(self, **_: Any) -> Any:
                    raise RuntimeError("boom")

            completions = _Completions()

        chat = _Chat()

    monkeypatch.setattr(app_mod, "openai_client", _OpenAI())
    monkeypatch.setattr(app_mod, "get_request_context", lambda _req: {})

    with pytest.raises(HTTPException) as exc:
        await app_mod.chat_completions(
            app_mod.ChatRequest(
                model="m",
                messages=[app_mod.ChatMessage(role="user", content="hi")],
            ),
            _request_with_headers(),
        )
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_submit_feedback_success_and_failure_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.app as app_mod

    class _Prov:
        def log_feedback(self, **_: Any) -> None:
            return None

    monkeypatch.setattr(app_mod, "provenance_logger", _Prov())
    ok = await app_mod.submit_feedback(
        app_mod.FeedbackRequest(run_id="r", rating=5, reasons=["x"], notes=None)
    )
    assert ok["status"] == "success"

    monkeypatch.setattr(app_mod, "provenance_logger", None)
    with pytest.raises(HTTPException) as exc:
        await app_mod.submit_feedback(
            app_mod.FeedbackRequest(run_id="r", rating=5, reasons=[], notes=None)
        )
    # submit_feedback wraps exceptions as 500
    assert exc.value.status_code == 500


def test_mlflow_logger_tracking_server_reachable_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.observability.mlflow_logger import MLflowLogger

    # Non-http scheme returns True
    logger = MLflowLogger(tracking_uri="file:/tmp/x", experiment_name="e")
    assert logger._tracking_server_reachable() is True  # noqa: SLF001

    # http scheme + socket failure returns False
    logger_http = MLflowLogger(tracking_uri="http://127.0.0.1:1", experiment_name="e")
    monkeypatch.setattr("socket.create_connection", lambda *_a, **_k: (_ for _ in ()).throw(OSError()))  # type: ignore[arg-type]
    assert logger_http._tracking_server_reachable(timeout_s=0.01) is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_mlflow_logger_log_run_and_feedback_pipe(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.observability import mlflow_logger as ml

    # Patch mlflow to avoid real network and to keep it deterministic.
    class _Run:
        info = SimpleNamespace(run_id="rid")

    @contextlib.contextmanager
    def _start_run(**_: Any):
        yield _Run()

    monkeypatch.setattr(
        ml,
        "mlflow",
        SimpleNamespace(
            set_tracking_uri=lambda *_a, **_k: None,
            get_experiment_by_name=lambda *_a, **_k: SimpleNamespace(
                experiment_id="exp"
            ),
            create_experiment=lambda *_a, **_k: "exp",
            start_run=_start_run,
            log_params=lambda *_a, **_k: None,
            log_metrics=lambda *_a, **_k: None,
            set_tags=lambda *_a, **_k: None,
            set_tag=lambda *_a, **_k: None,
            log_artifacts=lambda *_a, **_k: None,
            log_artifact=lambda *_a, **_k: None,
            log_dict=lambda *_a, **_k: None,
        ),
    )

    logger = ml.MLflowLogger(tracking_uri="http://mlflow:5000", experiment_name="e")
    logger.experiment_id = "exp"

    env = ml.EnvironmentSnapshot(
        timestamp=ml.datetime.utcnow(),
        service_version="0.0.0",
        model_version="m",
        config_hash="c",
        dependencies={},
    )
    run_spec = ml.RunSpec(
        prompt="p",
        model="m",
        temperature=0.0,
        max_tokens=1,
        domain_weights={"x": 1.0},
        policies=["evidence"],
        user_id="u",
        session_id="s",
    )
    docs = [ml.RetrievalDoc(content="c", metadata={}, score=1.0, source="s")]
    calls = [
        ml.ToolCall(tool_name="t", tool_args={}, result={}, duration=0.1, success=True)
    ]

    rid = await logger.log_run(
        run_spec=run_spec,
        retrieval_docs=docs,
        raw_output="raw",
        postprocessed_output="post",
        tool_calls=calls,
        environment=env,
        feedback={"rating": 5, "reasons": ["x"]},
    )
    assert rid == "rid"

    # Feedback logging
    monkeypatch.setattr(os, "remove", lambda *_a, **_k: None)
    assert logger.log_feedback("rid", {"rating": 5, "reasons": ["x"]}) is True
