"""Raise coverage for docker, mlflow, provenance, trace, tracing, conditioning, gateway_client."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
import respx

from src.clients import docker as docker_client_mod
from src.observability import mlflow_logger as mlflow_logger_mod
from src.observability.mlflow_logger import (
    EnvironmentSnapshot,
    MLflowLogger,
    RetrievalDoc,
    RunSpec,
    ToolCall,
)
from src.observability.provenance import ProvenanceLogger
from src.observability.trace import TraceContext
from src.observability.tracing import (
    GoldenTraceValidator,
    TracePropagator,
    TracingContext,
    get_golden_trace_validator,
    get_trace_propagator,
    get_tracing_context,
)
from ai_shared_service.conditioning import NonGenerativeConditioning, RequestConditioner
from ai_shared_service.gateway_client import WrkHrsGatewayClient


def test_docker_unavailable_no_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docker_client_mod, "docker", None)
    with pytest.raises(docker_client_mod.DockerUnavailable, match="docker SDK"):
        docker_client_mod.list_service_containers("api")


def test_docker_unavailable_no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_mod = Mock()
    monkeypatch.setattr(docker_client_mod, "docker", fake_mod)
    monkeypatch.setattr(docker_client_mod.os.path, "exists", lambda _p: False)
    with pytest.raises(docker_client_mod.DockerUnavailable, match="docker.sock"):
        docker_client_mod.list_service_containers("api")


def test_docker_list_and_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    container = Mock()
    container.id = "abcd"
    container.name = "proj-api-1"
    container.status = "running"
    container.labels = {"com.docker.compose.service": "api"}

    client = Mock()
    client.containers.list.return_value = [container]
    client.close = Mock(side_effect=RuntimeError("ignore"))
    fake_docker = Mock()
    fake_docker.from_env.return_value = client
    monkeypatch.setattr(docker_client_mod, "docker", fake_docker)
    monkeypatch.setattr(docker_client_mod.os.path, "exists", lambda _p: True)

    out = docker_client_mod.list_service_containers("api")
    assert len(out) == 1
    assert out[0]["id"] == "abcd"
    client.close.assert_called()

    restart_out = docker_client_mod.restart_service("api", timeout=3)
    assert restart_out["service"] == "api"
    container.restart.assert_called_once_with(timeout=3)


@pytest.mark.asyncio
async def test_mlflow_logger_log_run_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_mlflow = MagicMock()
    active_run = Mock()
    active_run.info.run_id = "run-abc"
    ctx = MagicMock()
    ctx.__enter__.return_value = active_run
    ctx.__exit__.return_value = None
    mock_mlflow.start_run.return_value = ctx
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)

    logger = MLflowLogger()
    logger.experiment_id = "exp-1"

    log_artifacts = AsyncMock()
    monkeypatch.setattr(logger, "_log_artifacts", log_artifacts)

    run_spec = RunSpec(prompt="hi", model="m")
    env = EnvironmentSnapshot(
        timestamp=datetime.utcnow(),
        service_version="1",
        model_version="2",
        config_hash="h",
        dependencies={},
    )
    rid = await logger.log_run(
        run_spec,
        retrieval_docs=[],
        raw_output="raw",
        postprocessed_output="out",
        tool_calls=[],
        environment=env,
    )
    assert rid == "run-abc"
    log_artifacts.assert_awaited_once()
    mock_mlflow.log_params.assert_called()
    mock_mlflow.log_metrics.assert_called()
    mock_mlflow.set_tags.assert_called()


@pytest.mark.asyncio
async def test_mlflow_logger_log_run_returns_error_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_mlflow = MagicMock()
    mock_mlflow.start_run.side_effect = RuntimeError("boom")
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)
    logger = MLflowLogger()
    logger.experiment_id = "exp-1"
    env = EnvironmentSnapshot(
        timestamp=datetime.utcnow(),
        service_version="1",
        model_version="2",
        config_hash="h",
        dependencies={},
    )
    run_spec = RunSpec(prompt="x", model="m")
    rid = await logger.log_run(
        run_spec,
        [],
        "r",
        "p",
        [],
        env,
    )
    assert rid == "error"


def test_mlflow_logger_tracking_unreachable_sets_no_experiment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_mlflow = MagicMock()
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)
    monkeypatch.setattr(
        MLflowLogger, "_tracking_server_reachable", lambda self, timeout_s=1.0: False
    )
    logger = MLflowLogger()
    assert logger.experiment_id is None


def test_mlflow_logger_start_run_named(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_mlflow = MagicMock()
    ctx = MagicMock()
    mock_mlflow.start_run.return_value = ctx
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)
    logger = MLflowLogger()
    logger.experiment_id = "e1"
    out = logger.start_run(run_name="n1")
    mock_mlflow.start_run.assert_called_once()
    assert out is ctx


def test_mlflow_logger_log_dict_and_params_swallow_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_mlflow = MagicMock()
    mock_mlflow.log_dict.side_effect = RuntimeError("x")
    mock_mlflow.log_params.side_effect = RuntimeError("y")
    mock_mlflow.log_metrics.side_effect = RuntimeError("z")
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)
    logger = MLflowLogger()
    logger.experiment_id = "e1"
    logger.log_dict({"a": 1}, "f.json")
    logger.log_params({"a": "b"})
    logger.log_metrics({"m": 1})


def test_mlflow_logger_log_feedback_success(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_mlflow = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = None
    ctx.__exit__.return_value = None
    mock_mlflow.start_run.return_value = ctx
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)
    monkeypatch.setattr(mlflow_logger_mod.os, "remove", lambda *_a, **_k: None)
    logger = MLflowLogger()
    logger.experiment_id = "e1"
    assert (
        logger.log_feedback("r1", {"rating": 5, "reasons": ["ok"], "notes": "n"})
        is True
    )


def test_mlflow_logger_search_runs_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_mlflow = MagicMock()
    mock_mlflow.search_runs.side_effect = RuntimeError("x")
    monkeypatch.setattr(mlflow_logger_mod, "mlflow", mock_mlflow)
    logger = MLflowLogger()
    logger.experiment_id = "e1"
    assert logger.search_runs() == []


def test_provenance_logger_log_request_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_mlflow = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = None
    ctx.__exit__.return_value = None
    mock_mlflow.start_run.return_value = ctx
    with patch("src.observability.provenance.mlflow", mock_mlflow), patch(
        "src.observability.provenance.MlflowClient"
    ):
        base = MLflowLogger()
        base.experiment_id = "e1"
        pl = ProvenanceLogger(base)
        run_spec = RunSpec(prompt="p", model="m")
        env = EnvironmentSnapshot(
            timestamp=datetime.utcnow(),
            service_version="1",
            model_version="2",
            config_hash="h",
            dependencies={},
        )
        docs = [
            RetrievalDoc(
                content="x" * 300,
                metadata={},
                score=0.5,
                source="s",
                chunk_id="c",
            )
        ]
        tools = [
            ToolCall(
                tool_name="t",
                tool_args={},
                result="r",
                duration=1.0,
                success=True,
            )
        ]
        pl.log_request_provenance(
            "rid",
            "trace",
            run_spec,
            env,
            retrieval_docs=docs,
            tool_calls=tools,
            raw_output="raw",
            postprocessed_output="post",
            policy_verdicts={
                "overall_passed": True,
                "overall_score": 0.9,
                "total_violations": 0,
            },
        )
        mock_mlflow.set_tag.assert_called()
        mock_mlflow.log_text.assert_called()
        mock_mlflow.log_metrics.assert_called()


def test_provenance_logger_log_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_mlflow = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = None
    ctx.__exit__.return_value = None
    mock_mlflow.start_run.return_value = ctx
    with patch("src.observability.provenance.mlflow", mock_mlflow), patch(
        "src.observability.provenance.MlflowClient"
    ):
        base = MLflowLogger()
        pl = ProvenanceLogger(base)
        pl.log_feedback("r1", 4, ["a"], notes="n")


def test_trace_context_setup_failure_uses_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.observability.trace.OTLPSpanExporter",
        Mock(side_effect=RuntimeError("no otlp")),
    )
    tc = TraceContext()
    assert tc.tracer is not None


def test_trace_context_instrument_and_span_helpers() -> None:
    tc = TraceContext()
    mock_app = Mock()
    tc.instrument_fastapi(mock_app)

    mock_span = Mock()
    mock_span.is_recording.return_value = False
    tc.add_span_attributes(mock_span, {"a": 1})
    tc.add_span_event(mock_span, "ev", None)
    tc.set_span_status(mock_span, "UNSET", "d")

    mock_span.is_recording.return_value = True
    tc.set_span_status(mock_span, "ERROR", "bad")


def test_tracing_context_trace_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    ctx = TracingContext.__new__(TracingContext)
    ctx.service_name = "s"
    ctx.service_version = "1"
    tracer = Mock()
    span = Mock()
    tracer.start_span.return_value = span
    ctx.tracer = tracer

    @contextmanager
    def _use_span(_s):  # noqa: ANN001
        yield _s

    monkeypatch.setattr(
        "src.observability.tracing.trace.use_span",
        _use_span,
    )

    async def boom():
        async with ctx.trace_request("op"):
            raise ValueError("x")

    with pytest.raises(ValueError):
        asyncio.run(boom())
    span.record_exception.assert_called_once()
    span.set_status.assert_called()
    span.end.assert_called()


def test_tracing_context_add_span_event_and_status() -> None:
    ctx = TracingContext()
    sp = Mock()
    ctx.add_span_attributes(sp, {"k": "v"})
    ctx.add_span_event(sp, "n", {"a": "b"})
    ctx.set_span_status(sp, "OK", "")
    ctx.set_span_status(sp, "ERROR", "e")
    ctx.set_span_status(sp, "OTHER", "")


def test_trace_propagator_and_module_getters() -> None:
    assert TracePropagator.extract_trace_context({}) == {}
    h = {"traceparent": "t", "tracestate": "s", "x-trace-id": "x"}
    assert "traceparent" in TracePropagator.extract_trace_context(h)
    out = {}
    TracePropagator.inject_trace_context(out, {"a": "b"})
    assert out["a"] == "b"
    assert len(TracePropagator.generate_trace_id()) > 10
    assert get_tracing_context() is not None
    assert get_trace_propagator() is not None
    assert get_golden_trace_validator() is not None


@pytest.mark.asyncio
@respx.mock
async def test_golden_trace_validator_branches() -> None:
    v = GoldenTraceValidator(TracingContext())
    respx.get("http://tempo:3200/api/traces/t1").mock(return_value=httpx.Response(404))
    out = await v.validate_golden_trace("t1", ["a"])
    assert out["valid"] is False
    assert "Tempo" in out.get("error", "")

    sample = {
        "duration": 100,
        "spans": [
            {"operationName": "a", "spanID": "1", "parentSpanID": None},
            {"operationName": "b", "spanID": "2", "parentSpanID": "1"},
        ],
    }
    respx.get("http://tempo:3200/api/traces/t2").mock(
        return_value=httpx.Response(200, json=sample)
    )
    out2 = await v.validate_golden_trace("t2", ["a", "b"])
    assert out2["hierarchy_valid"] is True
    assert out2["duration_valid"] is True

    bad_h = v._validate_span_hierarchy(
        [
            {"spanID": "1", "parentSpanID": None},
            {"spanID": "2", "parentSpanID": None},
        ]
    )
    assert bad_h is False


def test_conditioning_request_conditioner_alias_and_paths() -> None:
    assert RequestConditioner is NonGenerativeConditioning
    c = NonGenerativeConditioning()
    w = c.apply_domain_weighting(
        "q", {"mechanical": 0.9, "chemistry": 0.05}, context="extra"
    )
    assert "system_context" in w
    det = c.apply_si_normalization("10 psi here", normalize=False)
    assert det["has_units"] is True
    norm = c.apply_si_normalization("2 psi", normalize=True)
    assert "normalized_text" in norm
    cons = c.apply_constraint_detection("safety pressure limit operating cost")
    assert cons["has_safety_constraints"]
    insuf = c.apply_evidence_weighting("p", [], min_sources=2)
    assert insuf["evidence_sufficient"] is False
    suf = c.apply_evidence_weighting(
        "p",
        [
            {"title": "A", "score": 0.9, "snippet": "s" * 120},
            {"title": "B", "score": 0.8, "snippet": ""},
            {"title": "C", "score": 0.7},
        ],
        min_sources=2,
    )
    assert suf["evidence_sufficient"] is True


@pytest.mark.asyncio
@respx.mock
async def test_wrkhrs_gateway_client_success_paths() -> None:
    base = "http://gw.test"
    respx.get(f"{base}/health").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    respx.post(f"{base}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"usage": {}})
    )
    respx.get(f"{base}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{base}/v1/classify/domain").mock(
        return_value=httpx.Response(200, json={"domains": []})
    )
    respx.post(f"{base}/v1/conditioning/apply").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    async with WrkHrsGatewayClient(base_url=base) as client:
        assert await client.health_check() == {"ok": True}
        r = await client.chat_completion(
            [{"role": "user", "content": "hi"}], max_tokens=10, extra="x"
        )
        assert "usage" in r
        assert "data" in await client.get_models()
        assert await client.domain_classify("t", domains=["a"]) == {"domains": []}
        assert await client.apply_conditioning("p") == {"ok": True}


@pytest.mark.asyncio
async def test_wrkhrs_gateway_client_requires_context() -> None:
    c = WrkHrsGatewayClient(base_url="http://x")
    with pytest.raises(RuntimeError, match="context manager"):
        await c.health_check()
    with pytest.raises(RuntimeError, match="context manager"):
        await c.chat_completion([{"role": "user", "content": "h"}])
    with pytest.raises(RuntimeError, match="context manager"):
        await c.get_models()
    with pytest.raises(RuntimeError, match="context manager"):
        await c.domain_classify("t")
    with pytest.raises(RuntimeError, match="context manager"):
        await c.apply_conditioning("p")


@pytest.mark.asyncio
@respx.mock
async def test_wrkhrs_gateway_client_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = "http://gw.err"
    route = respx.post(f"{base}/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="no")
    )
    async with WrkHrsGatewayClient(base_url=base) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat_completion([{"role": "user", "content": "h"}])
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_wrkhrs_gateway_client_other_endpoints_http_errors() -> None:
    """Cover health/models/domain/conditioning HTTPError branches."""
    base = "http://gw.multierr"
    respx.get(f"{base}/health").mock(return_value=httpx.Response(503, text="down"))
    respx.get(f"{base}/v1/models").mock(return_value=httpx.Response(500, text="m"))
    respx.post(f"{base}/v1/classify/domain").mock(
        return_value=httpx.Response(502, text="d")
    )
    respx.post(f"{base}/v1/conditioning/apply").mock(
        return_value=httpx.Response(500, text="c")
    )

    async with WrkHrsGatewayClient(base_url=base) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.health_check()
    async with WrkHrsGatewayClient(base_url=base) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_models()
    async with WrkHrsGatewayClient(base_url=base) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.domain_classify("t", domains=["x"])
    async with WrkHrsGatewayClient(base_url=base) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.apply_conditioning("p")
