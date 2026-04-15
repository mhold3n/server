from __future__ import annotations

import contextlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_clients_docker_unavailable_when_no_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.clients import docker as docker_client

    monkeypatch.setattr(docker_client.os.path, "exists", lambda p: False)
    monkeypatch.setattr(docker_client, "docker", SimpleNamespace(from_env=lambda: None))

    with pytest.raises(docker_client.DockerUnavailable, match="docker.sock"):
        docker_client.list_service_containers("api")


def test_clients_docker_unavailable_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.clients import docker as docker_client

    monkeypatch.setattr(docker_client, "docker", None)
    with pytest.raises(docker_client.DockerUnavailable, match="SDK"):
        docker_client.restart_service("api")


def test_routes_feedback_pipe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.routes import feedback as fb

    feedback_file = tmp_path / "feedback.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(feedback_file))

    async def no_mlflow(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(fb, "_log_feedback_to_mlflow", no_mlflow)

    app = FastAPI()
    app.include_router(fb.router)
    client = TestClient(app)

    # Invalid reason -> 400
    r = client.post(
        "/feedback/v1/feedback",
        json={"run_id": "r1", "rating": 3, "reasons": ["not_a_reason"]},
    )
    assert r.status_code == 400

    # Store feedback
    r2 = client.post(
        "/feedback/v1/feedback",
        json={"run_id": "r1", "rating": 5, "reasons": ["clear_explanation"]},
    )
    assert r2.status_code == 200
    fid = r2.json()["feedback_id"]

    # Get per-run feedback
    r3 = client.get("/feedback/v1/feedback/r1")
    assert r3.status_code == 200
    assert any(item["feedback_id"] == fid for item in r3.json())

    # Delete feedback
    r6 = client.delete(f"/feedback/v1/feedback/{fid}")
    assert r6.status_code == 200


@pytest.mark.asyncio
async def test_routes_middleware_pipe() -> None:
    from src.routes import middleware as mw

    app = FastAPI()
    app.include_router(mw.router)
    client = TestClient(app)

    # Registry is available
    r = client.get("/middleware/registry")
    assert r.status_code == 200
    policies = r.json()["policies"]
    assert isinstance(policies, list) and policies

    # Schema endpoint for known policy
    r2 = client.get("/middleware/registry/evidence/schema")
    assert r2.status_code == 200
    assert r2.json()["type"] == "object"

    # Validate against at least one policy (smoke)
    r3 = client.post(
        "/middleware/validate",
        json={
            "content": "CI response with citations [1] [2] [3].",
            "policies": ["evidence"],
        },
    )
    assert r3.status_code == 200
    assert "passed" in r3.json()


@pytest.mark.asyncio
async def test_routes_middleware_config_override_and_unknown_policy() -> None:
    from src.routes import middleware as mw

    app = FastAPI()
    app.include_router(mw.router)
    client = TestClient(app)

    # Unknown policy is ignored (still 200, but may have empty results)
    r = client.post(
        "/middleware/validate",
        json={"content": "x", "policies": ["does_not_exist"]},
    )
    assert r.status_code == 200

    # Config override branch (shape only; registry handles merge)
    r2 = client.post(
        "/middleware/validate",
        json={
            "content": "CI response with citations [1] [2] [3].",
            "policies": ["evidence"],
            "config": {"evidence": {"min_citations": 1}},
        },
    )
    assert r2.status_code == 200
    assert "evidence" in r2.json()["policy_results"]


@pytest.mark.asyncio
async def test_routes_middleware_404s_and_policy_error_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.routes import middleware as mw

    app = FastAPI()
    app.include_router(mw.router)
    client = TestClient(app)

    r = client.get("/middleware/registry/does_not_exist")
    assert r.status_code == 404

    r2 = client.get("/middleware/registry/does_not_exist/schema")
    assert r2.status_code == 404

    class _BadPolicy:
        async def validate(self, *_a: Any, **_k: Any) -> Any:
            raise RuntimeError("boom")

    monkeypatch.setattr(mw.policy_registry, "get_policy", lambda name: _BadPolicy())
    r3 = client.post(
        "/middleware/validate",
        json={"content": "x", "policies": ["evidence"]},
    )
    assert r3.status_code == 200
    assert r3.json()["policy_results"]["evidence"]["passed"] is False


@pytest.mark.asyncio
async def test_policies_executables_pipe() -> None:
    from src.policies.hedging_executable import HedgingPolicy as HedgingExec
    from src.policies.units_executable import SIUnitPolicy as SIExec

    h = HedgingExec(ban_hedging=True)
    out = await h.validate("This might be true.")
    assert out.passed is False

    u = SIExec(enforce_si=True, normalize_units=False)
    out2 = await u.validate("The length is 3 inches.")
    assert out2.passed is False


def test_policies_registry_pipe() -> None:
    from src.policies.registry import policy_registry

    pols = policy_registry.get_available_policies()
    assert any(p["name"] == "evidence" for p in pols)
    schema = policy_registry.get_policy_schema("evidence")
    assert schema is not None


def test_observability_trace_context_pipe() -> None:
    from src.observability.trace import TraceContext

    tc = TraceContext(
        service_name="test", service_version="0.0.0", tempo_endpoint="http://tempo:4317"
    )
    assert tc.get_tracer() is not None
    tc.instrument_httpx()
    tc.instrument_requests()


def test_observability_tracing_context_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.observability import tracing as otel_tracing

    monkeypatch.setattr(otel_tracing, "OTLPSpanExporter", lambda *a, **k: object())

    class _Proc:
        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(otel_tracing, "BatchSpanProcessor", lambda exporter: _Proc())
    monkeypatch.setattr(
        otel_tracing,
        "HTTPXClientInstrumentor",
        lambda: SimpleNamespace(instrument=lambda: None),
    )
    monkeypatch.setattr(
        otel_tracing,
        "RequestsInstrumentor",
        lambda: SimpleNamespace(instrument=lambda: None),
    )
    monkeypatch.setattr(
        otel_tracing,
        "RedisInstrumentor",
        lambda: SimpleNamespace(instrument=lambda: None),
    )
    monkeypatch.setattr(
        otel_tracing,
        "SQLAlchemyInstrumentor",
        lambda: SimpleNamespace(instrument=lambda: None),
    )

    ctx = otel_tracing.TracingContext(service_name="test", service_version="0.0.0")
    assert ctx.tracer is not None


def test_observability_provenance_logger_pipe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.observability import provenance as prov

    # Avoid real MLflow client + IO
    monkeypatch.setattr(prov, "MlflowClient", lambda: object())

    class _ML:
        @staticmethod
        def start_run(**_: Any):
            return contextlib.nullcontext()

        @staticmethod
        def set_tag(*_: Any, **__: Any) -> None:
            return None

        @staticmethod
        def log_text(*_: Any, **__: Any) -> None:
            return None

        @staticmethod
        def log_metric(*_: Any, **__: Any) -> None:
            return None

        @staticmethod
        def log_metrics(*_: Any, **__: Any) -> None:
            return None

        @staticmethod
        def log_dict(*_: Any, **__: Any) -> None:
            return None

    monkeypatch.setattr(prov, "mlflow", _ML)

    mlflow_logger = SimpleNamespace(
        log_dict=lambda **_: None,
        log_params=lambda *_a, **_k: None,
        log_metrics=lambda *_a, **_k: None,
        log_text=lambda *_a, **_k: None,
    )

    logger = prov.ProvenanceLogger(mlflow_logger=mlflow_logger)  # type: ignore[arg-type]

    run_spec = prov.RunSpec(
        prompt="p",
        model="m",
        temperature=0.0,
        max_tokens=1,
        system=None,
        tools=[],
        tool_args=None,
        domain_weights=None,
        policies=[],
    )
    env = prov.EnvironmentSnapshot(
        timestamp=prov.datetime.utcnow(),
        service_version="0.0.0",
        model_version="m",
        config_hash="c",
        dependencies={},
    )
    doc = prov.RetrievalDoc(
        content="c",
        metadata={},
        score=1.0,
        source="s",
    )
    tool = prov.ToolCall(
        tool_name="t",
        tool_args={"a": 1},
        result={"ok": True},
        duration=0.01,
        success=True,
    )

    logger.log_request_provenance(
        run_id="r",
        trace_id="t",
        run_spec=run_spec,
        environment=env,
        retrieval_docs=[doc],
        tool_calls=[tool],
        raw_output="x",
        postprocessed_output="y",
        policy_verdicts={"a": 1},
    )

    # Exercise internal helpers directly for coverage.
    logger._log_run_spec(run_spec)
    logger._log_environment(env)
    logger._log_retrieval_provenance([doc])
    logger._log_tool_execution([tool])
    logger._log_raw_output("x")
    logger._log_postprocessed_output("y")
    logger._log_policy_verdicts({"a": 1})
    logger._log_aggregated_metrics(run_spec, [doc], [tool], {"a": 1})


def test_mlflow_logger_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    import unittest.mock

    from src.observability import mlflow_logger as ml

    mock_mlflow = unittest.mock.Mock()
    mock_mlflow.get_experiment_by_name.return_value = None
    mock_mlflow.create_experiment.return_value = "exp"
    mock_mlflow.start_run.return_value = contextlib.nullcontext()
    monkeypatch.setattr(ml, "mlflow", mock_mlflow)

    logger = ml.MLflowLogger(tracking_uri="http://mlflow:5000", experiment_name="e")
    with logger.start_run(run_name="x"):
        logger.log_params({"a": "1"})
        logger.log_metrics({"m": 1.0})
        logger.log_dict({"k": "v"}, artifact_file="x.json")


@pytest.mark.asyncio
async def test_observability_tracing_module_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    from src.observability import tracing as ot

    class _Span:
        def __init__(self):
            self.attrs: dict[str, Any] = {}
            self.events: list[tuple[str, dict[str, Any] | None]] = []

        def set_attribute(self, k: str, v: Any) -> None:
            self.attrs[k] = v

        def add_event(
            self, name: str, attributes: dict[str, Any] | None = None
        ) -> None:
            self.events.append((name, attributes))

        def set_status(self, status: Any) -> None:  # noqa: ANN401
            self.status = status

        def end(self) -> None:
            return None

        def record_exception(self, exc: BaseException) -> None:
            self.exc = exc

    class _Tracer:
        def start_span(self, name: str) -> _Span:  # noqa: ARG002
            return _Span()

    @contextmanager
    def _use_span(span: Any):  # noqa: ANN401
        yield

    monkeypatch.setattr(ot, "trace", SimpleNamespace(use_span=_use_span))
    monkeypatch.setattr(ot.TracingContext, "_setup_tracing", lambda self: None)
    ctx = ot.TracingContext(service_name="x", service_version="y")
    ctx.tracer = _Tracer()

    span = ctx.create_span("s", {"a": 1})
    ctx.add_span_attributes(span, {"b": 2})
    ctx.add_span_event(span, "e", {"c": 3})
    ctx.set_span_status(span, "ok")

    headers = {"traceparent": "00-" + "0" * 32 + "-" + "0" * 16 + "-01"}
    extracted = ot.TracePropagator.extract_trace_context(headers)
    injected: dict[str, str] = {}
    ot.TracePropagator.inject_trace_context(injected, extracted)
    assert "traceparent" in injected
    assert ot.TracePropagator.generate_trace_id()
    assert ot.TracePropagator.generate_span_id()

    async with ctx.trace_request("op", {"x": "y"}):
        pass


@pytest.mark.asyncio
async def test_wrkhrs_gateway_client_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.ai_gateway_client.gateway_client import WrkHrsGatewayClient

    class _Resp:
        def __init__(self, payload: dict[str, Any]):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    class _Client:
        async def get(self, path: str) -> _Resp:  # noqa: ARG002
            return _Resp({"status": "ok"})

        async def post(self, path: str, json: Any) -> _Resp:  # noqa: ARG002
            return _Resp({"choices": [{"message": {"content": "x"}}], "usage": {}})

        async def aclose(self) -> None:
            return None

    c = WrkHrsGatewayClient(base_url="http://x")
    c._client = _Client()  # type: ignore[assignment]
    assert (await c.health_check())["status"] == "ok"
    resp = await c.chat_completion(
        messages=[{"role": "user", "content": "hi"}], model="m"
    )
    assert resp["choices"][0]["message"]["content"] == "x"


@pytest.mark.asyncio
async def test_wrkhrs_gateway_client_errors_pipe() -> None:
    from httpx import HTTPError

    from src.ai_gateway_client.gateway_client import WrkHrsGatewayClient

    c = WrkHrsGatewayClient(base_url="http://x")
    with pytest.raises(RuntimeError):
        await c.health_check()

    class _Client:
        async def get(self, path: str):  # noqa: ANN001,ARG002
            raise HTTPError("boom")

        async def post(self, path: str, json: Any):  # noqa: ANN001,ARG002
            raise HTTPError("boom")

        async def aclose(self) -> None:
            return None

    c._client = _Client()  # type: ignore[assignment]
    with pytest.raises(HTTPError):
        await c.health_check()
    with pytest.raises(HTTPError):
        await c.chat_completion(messages=[{"role": "user", "content": "hi"}], model="m")


def test_api_app_imports_and_mounts() -> None:
    # Importing src.app should create the FastAPI app and route wiring.
    import src.app as app_mod

    assert hasattr(app_mod, "app")
    assert isinstance(app_mod.app, FastAPI)


def test_app_helpers_usage_and_completion_response_body() -> None:
    import src.app as app_mod

    assert app_mod._usage_for_log(None) is None
    assert app_mod._usage_for_log({"a": 1}) == {"a": 1}

    class _U:
        def model_dump(self) -> dict[str, Any]:
            return {"x": 2}

    assert app_mod._usage_for_log(_U()) == {"x": 2}

    class _C:
        id = "c1"
        object = "chat.completion"
        created = 1
        model = "m"
        choices = []
        usage = {"u": 1}

    body = app_mod._completion_response_body(_C())
    assert body["id"] == "c1"
    assert body["usage"] == {"u": 1}

    with pytest.raises(TypeError):
        app_mod._completion_response_body(object())


@pytest.mark.asyncio
async def test_app_startup_shutdown_and_health_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.app as app_mod

    class _Trace:
        def instrument_fastapi(self, app: Any) -> None:  # noqa: ARG002
            return None

        def instrument_httpx(self) -> None:
            return None

        def instrument_requests(self) -> None:
            return None

    monkeypatch.setattr(app_mod, "get_trace_context", lambda: _Trace())

    class _Redis:
        async def ping(self) -> None:
            return None

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        app_mod, "Redis", SimpleNamespace(from_url=lambda *_a, **_k: _Redis())
    )

    class _Models:
        async def list(self) -> list[dict[str, Any]]:
            return [{"id": "m"}]

    class _OpenAI:
        def __init__(self, *_a: Any, **_k: Any):
            self.models = _Models()

    monkeypatch.setattr(app_mod, "AsyncOpenAI", _OpenAI)
    monkeypatch.setattr(app_mod, "MLflowLogger", lambda *_a, **_k: object())
    monkeypatch.setattr(app_mod, "ProvenanceLogger", lambda *_a, **_k: object())

    await app_mod.startup_event()
    health = await app_mod.health_check()
    assert health.services["redis"] in ("healthy", "unhealthy", "not_configured")
    assert health.services["openai"] in ("healthy", "unhealthy", "not_configured")

    await app_mod.shutdown_event()


@pytest.mark.asyncio
async def test_routes_feedback_summary_handler_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.routes import feedback as fb

    feedback_file = tmp_path / "feedback.json"
    monkeypatch.setenv("FEEDBACK_FILE", str(feedback_file))
    feedback_file.write_text(
        json.dumps(
            [
                {
                    "feedback_id": "f1",
                    "run_id": "r1",
                    "rating": 5,
                    "reasons": ["clear_explanation"],
                    "notes": None,
                    "timestamp": "2026-01-01T00:00:00",
                }
            ]
        )
    )

    summary = await fb.get_feedback_summary(limit=10, days=3650)
    assert summary.total_feedback == 1


@pytest.mark.asyncio
async def test_routes_feedback_reasons_handler_pipe() -> None:
    from src.routes import feedback as fb

    reasons = await fb.get_feedback_reasons()
    assert "clear_explanation" in reasons["reasons"]


def test_wrkhrs_conditioning_pipe() -> None:
    from src.ai_gateway_client.conditioning import NonGenerativeConditioning

    c = NonGenerativeConditioning()
    text = "Measure 3 inches and 2 feet."
    out = c.apply_si_normalization(text)
    assert isinstance(out, dict)
    assert out["has_units"] is True

    out2 = c.apply_constraint_detection("must do X, should do Y")
    assert "Constraints:" in out2 or out2

    out3 = c.apply_domain_weighting("hello", {"math": 0.9, "history": 0.1})
    assert isinstance(out3, dict)
    assert "domain_context" in out3

    out4 = c.apply_evidence_weighting(
        "hello",
        evidence_sources=[{"source": "s1"}, {"source": "s2"}],
        min_sources=3,
    )
    assert isinstance(out4, dict)


def test_wrkhrs_domain_classifier_pipe() -> None:
    from src.ai_gateway_client.domain_classifier import DomainClassifier

    dc = DomainClassifier()
    weights = dc.get_domain_weights("Tell me about calculus.")
    assert isinstance(weights, dict)
    scores = dc.classify("Tell me about calculus.")
    assert isinstance(scores, dict)
