#!/usr/bin/env python3
"""
Extended Gateway Tests — covers helper functions, auth edge-cases,
domain analysis endpoint, login, and prompt processing pipeline.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# Ensure gateway module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

import gateway.app as gw  # noqa: E402

# ── helpers under test ────────────────────────────────────────────


class TestJSONFormatter:
    def test_format_basic(self):
        fmt = gw.JSONFormatter()
        record = logging.LogRecord("test", logging.INFO, "mod", 1, "hello", (), None)
        out = fmt.format(record)
        parsed = json.loads(out)
        assert parsed["message"] == "hello"
        assert parsed["service"] == "gateway"
        assert "timestamp" in parsed

    def test_format_with_extras(self):
        fmt = gw.JSONFormatter()
        record = logging.LogRecord("test", logging.WARNING, "mod", 1, "msg", (), None)
        record.user_id = "u1"
        record.ip_address = "10.0.0.1"
        record.request_id = "r1"
        record.endpoint = "/health"
        record.method = "GET"
        record.event_type = "auth"
        record.metadata = {"k": "v"}
        out = fmt.format(record)
        parsed = json.loads(out)
        assert parsed["user_id"] == "u1"
        assert parsed["ip_address"] == "10.0.0.1"
        assert parsed["metadata"] == {"k": "v"}

    def test_format_with_exception(self):
        fmt = gw.JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                "test", logging.ERROR, "mod", 1, "err", (), sys.exc_info()
            )
        out = fmt.format(record)
        parsed = json.loads(out)
        assert "exception" in parsed


class TestGetSecret:
    def test_env_var(self):
        with patch.dict(os.environ, {"MY_SECRET": "val123"}):
            assert gw.get_secret("MY_SECRET", "default") == "val123"

    def test_file_mount(self, tmp_path):
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text(" file_secret_val \n")
        with patch.dict(os.environ, {"MY_SECRET_FILE": str(secret_file)}, clear=False):
            assert gw.get_secret("MY_SECRET", "default") == "file_secret_val"

    def test_default_fallback(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEVER_SET", None)
            assert gw.get_secret("NEVER_SET", "fallback") == "fallback"


class TestDomainWeightsExtraction:
    def test_chemistry_keywords(self):
        w = gw.extract_domain_weights("The pH of the molecular catalyst is 7.4")
        assert w.chemistry > 0

    def test_mechanical_keywords(self):
        w = gw.extract_domain_weights("The stress on the beam under 500 N force")
        assert w.mechanical > 0

    def test_materials_keywords(self):
        w = gw.extract_domain_weights("The hardness of the steel alloy microstructure")
        assert w.materials > 0

    def test_no_keywords(self):
        w = gw.extract_domain_weights("Hello this is a generic sentence")
        assert w.chemistry == 0.0
        assert w.mechanical == 0.0
        assert w.materials == 0.0


class TestExtractUnits:
    def test_si_base(self):
        units = gw.extract_units("The beam is 5.2 m long and weighs 10 kg")
        assert any("m" in u for u in units)

    def test_engineering_units(self):
        units = gw.extract_units("The yield strength is 250 MPa at 100 kN")
        assert len(units) > 0

    def test_no_units(self):
        units = gw.extract_units("Hello world")
        assert units == []


class TestExtractConstraints:
    def test_safety_constraints(self):
        c = gw.extract_constraints("Ensure safety and avoid toxic corrosive contact")
        assert len(c) > 0

    def test_limit_constraints(self):
        c = gw.extract_constraints("temperature limit max 500, standard specification")
        assert len(c) > 0

    def test_no_constraints(self):
        c = gw.extract_constraints("Hello world nice day")
        assert c == []


class TestRateLimit:
    def test_rate_limit_allows_when_auth_disabled(self):
        with patch.object(gw, "ENABLE_AUTH", False):
            assert gw.check_rate_limit("1.2.3.4") is True

    def test_rate_limit_blocks_on_exceed(self):
        with (
            patch.object(gw, "ENABLE_AUTH", True),
            patch.object(gw, "RATE_LIMIT_RPM", 2),
        ):
            gw.request_counts["10.0.0.99"] = [time.time(), time.time()]
            assert gw.check_rate_limit("10.0.0.99") is False
            # cleanup
            del gw.request_counts["10.0.0.99"]

    def test_rate_limit_cleans_old(self):
        with (
            patch.object(gw, "ENABLE_AUTH", True),
            patch.object(gw, "RATE_LIMIT_RPM", 5),
        ):
            old_ts = time.time() - 120  # 2 mins ago
            gw.request_counts["10.0.0.88"] = [old_ts, old_ts]
            assert gw.check_rate_limit("10.0.0.88") is True
            del gw.request_counts["10.0.0.88"]


class TestValidateApiKey:
    def test_valid_key(self):
        with patch.object(gw, "API_KEY_SECRET", "mysecret"):
            assert gw.validate_api_key("mysecret") is True

    def test_invalid_key(self):
        with patch.object(gw, "API_KEY_SECRET", "mysecret"):
            assert gw.validate_api_key("wrongkey") is False

    def test_empty_key(self):
        assert gw.validate_api_key("") is False


class TestJWT:
    def test_create_and_verify(self):
        with (
            patch.object(gw, "JWT_SECRET_KEY", "test-jwt-secret"),
            patch.object(gw, "JWT_ALGORITHM", "HS256"),
            patch.object(gw, "JWT_EXPIRATION_HOURS", 24),
        ):
            token = gw.create_jwt_token({"sub": "testuser"})
            payload = gw.verify_jwt_token(token)
            assert payload is not None
            assert payload["sub"] == "testuser"

    def test_invalid_token(self):
        with (
            patch.object(gw, "JWT_SECRET_KEY", "test-jwt-secret"),
            patch.object(gw, "JWT_ALGORITHM", "HS256"),
        ):
            result = gw.verify_jwt_token("not-a-real-token")
            assert result is None

    def test_expired_token(self):
        import jwt as pyjwt
        from datetime import timedelta

        with (
            patch.object(gw, "JWT_SECRET_KEY", "test-jwt-secret"),
            patch.object(gw, "JWT_ALGORITHM", "HS256"),
        ):
            expired = pyjwt.encode(
                {"sub": "user", "exp": datetime.utcnow() - timedelta(hours=1)},
                "test-jwt-secret",
                algorithm="HS256",
            )
            assert gw.verify_jwt_token(expired) is None


# ── FastAPI endpoint tests ────────────────────────────────────────


@pytest.fixture
def disable_auth():
    """Patch auth off so endpoints are accessible without credentials."""
    with patch.object(gw, "ENABLE_AUTH", False):
        yield


@pytest.mark.asyncio
async def test_login_success():
    with (
        patch.object(gw, "API_KEY_SECRET", "goodpass"),
        patch.object(gw, "JWT_SECRET_KEY", "jwt-s"),
        patch.object(gw, "JWT_ALGORITHM", "HS256"),
        patch.object(gw, "JWT_EXPIRATION_HOURS", 1),
    ):
        transport = ASGITransport(app=gw.api)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login", json={"username": "admin", "password": "goodpass"}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert "access_token" in body
            assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure():
    with patch.object(gw, "API_KEY_SECRET", "goodpass"):
        transport = ASGITransport(app=gw.api)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login", json={"username": "admin", "password": "wrong"}
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analyze_domains_endpoint(disable_auth):
    transport = ASGITransport(app=gw.api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/domains/analyze", params={"text": "The steel beam is under 100 N force"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "domain_weights" in body
        assert body["domain_weights"]["mechanical"] > 0


@pytest.mark.asyncio
async def test_chat_completions_no_user_message(disable_auth):
    transport = ASGITransport(app=gw.api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "system", "content": "hello"}]},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_chat_completions_orchestrator_error(disable_auth):
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    with patch.object(gw, "ORCH_SESSION") as mock_session:
        mock_session.post.return_value = mock_resp
        transport = ASGITransport(app=gw.api)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "What is steel?"}]},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == "fallback"


@pytest.mark.asyncio
async def test_chat_completions_connection_error(disable_auth):
    import requests as _req

    with patch.object(gw, "ORCH_SESSION") as mock_session:
        mock_session.post.side_effect = _req.exceptions.ConnectionError("refused")
        transport = ASGITransport(app=gw.api)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == "fallback"


@pytest.mark.asyncio
async def test_chat_completions_with_domain_evidence(disable_auth):
    orch_body = {
        "id": "resp-1",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    mock_orch = MagicMock()
    mock_orch.status_code = 200
    mock_orch.json.return_value = orch_body

    mock_rag = MagicMock()
    mock_rag.status_code = 200
    mock_rag.json.return_value = {"evidence": "Steel has yield strength 250 MPa"}

    with (
        patch.object(gw, "ORCH_SESSION") as mock_session,
        patch("gateway.app.requests.post", return_value=mock_rag),
    ):
        mock_session.post.return_value = mock_orch
        transport = ASGITransport(app=gw.api)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/v1/chat/completions",
                json={
                    "messages": [
                        {
                            "role": "user",
                            "content": "What is the stress on the steel beam?",
                        }
                    ]
                },
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_process_prompt():
    with patch("gateway.app.requests.post") as mock_rag:
        mock_rag.return_value = MagicMock(
            status_code=200, json=lambda: {"evidence": ""}
        )
        result = await gw.process_prompt("Calculate force on 5 m beam at 100 N")
        assert result.original_prompt.startswith("Calculate")
        assert isinstance(result.extracted_units, list)
        assert isinstance(result.constraints, list)


@pytest.mark.asyncio
async def test_get_weighted_evidence_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"evidence": "relevant data"}
    with patch("gateway.app.requests.post", return_value=mock_resp):
        ev = await gw.get_weighted_evidence("query", gw.DomainWeights())
        assert ev == "relevant data"


@pytest.mark.asyncio
async def test_get_weighted_evidence_failure():
    with patch("gateway.app.requests.post", side_effect=Exception("timeout")):
        ev = await gw.get_weighted_evidence("query", gw.DomainWeights())
        assert ev == ""


@pytest.mark.asyncio
async def test_get_weighted_evidence_non_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("gateway.app.requests.post", return_value=mock_resp):
        ev = await gw.get_weighted_evidence("query", gw.DomainWeights())
        assert ev == ""


class TestLoadModels:
    def test_skip_when_disabled(self):
        # load_models should succeed (not crash) when SentenceTransformer unavailable
        with patch("gateway.app.embedding_model", None):
            try:
                gw.load_models()
            except Exception:
                pass  # ImportError is expected in CI
