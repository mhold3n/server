from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_automation_path_must_be_under_devplane_root(client: TestClient) -> None:
    res = client.post(
        "/api/automation/larrak/ingest",
        json={
            "source_path": "/etc/passwd",
            "workspace_root": "/etc",
            "source_type": "txt",
            "marker_extra_args": [],
        },
    )
    assert res.status_code == 400


def test_automation_allows_devplane_root_paths(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Point devplane_root to a temp directory and ensure paths under it pass validation.
    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    source = tmp_path / "example.txt"
    source.write_text("hello", encoding="utf-8")
    workspace = tmp_path / "ws"
    workspace.mkdir()

    res = client.post(
        "/api/automation/larrak/ingest",
        json={
            "source_path": str(source),
            "workspace_root": str(workspace),
            "source_type": "txt",
            "marker_extra_args": [],
        },
    )
    # We expect execution to fail because larrak-audio isn't installed in test env,
    # but path validation should pass (so failure is 502 not 400).
    assert res.status_code in (502, 504)


def test_martymedia_captions_writes_artifact_and_can_attach_to_run(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()
    media = ws / "clip.mp4"
    media.write_text("fake", encoding="utf-8")
    out_dir = ws / "out"
    out_dir.mkdir()

    class Proc:
        returncode = 0
        stdout = '{"ok": true, "output_paths": ["x.srt"]}'
        stderr = ""

    def fake_run(*args, **kwargs):  # noqa: ANN001
        return Proc()

    # Prevent needing a real devplane service; just ensure it can be called.
    class FakeService:
        def append_run_event(self, run_id, request):  # noqa: ANN001
            assert run_id == "run_123"
            assert request.artifacts

    import src.routes.automation as automation_mod

    monkeypatch.setattr(automation_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(automation_mod, "get_service", lambda: FakeService())

    res = client.post(
        "/api/automation/martymedia/captions",
        json={
            "input_path": str(media),
            "output_dir": str(out_dir),
            "workspace_root": str(ws),
            "run_id": "run_123",
            "language": "en",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    artifact_path = Path(body["artifact"]["path"])
    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8")


def test_larrak_doctor_writes_artifact_when_workspace_provided(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()

    class Proc:
        returncode = 0
        stdout = "{}"
        stderr = ""

    import src.routes.automation as automation_mod

    monkeypatch.setattr(automation_mod.subprocess, "run", lambda *a, **k: Proc())

    res = client.post(
        "/api/automation/larrak/doctor",
        json={"skip_services": True, "workspace_root": str(ws)},
    )
    assert res.status_code == 200
    body = res.json()
    assert "artifact" in body
    assert Path(body["artifact"]["path"]).exists()


def test_larrak_build_writes_artifact(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()

    class Proc:
        returncode = 0
        stdout = "{}"
        stderr = ""

    import src.routes.automation as automation_mod

    monkeypatch.setattr(automation_mod.subprocess, "run", lambda *a, **k: Proc())

    res = client.post(
        "/api/automation/larrak/build",
        json={"source_id": "abc", "enhance": False, "workspace_root": str(ws)},
    )
    assert res.status_code == 200
    artifact_path = Path(res.json()["artifact"]["path"])
    assert artifact_path.exists()


def test_automation_timeout_returns_504(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()
    src = ws / "example.txt"
    src.write_text("x", encoding="utf-8")

    import src.routes.automation as automation_mod

    def raise_timeout(*args, **kwargs):  # noqa: ANN001
        raise automation_mod.subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(automation_mod.subprocess, "run", raise_timeout)

    res = client.post(
        "/api/automation/larrak/ingest",
        json={
            "source_path": str(src),
            "workspace_root": str(ws),
            "source_type": "txt",
            "marker_extra_args": [],
        },
    )
    assert res.status_code == 504


def test_automation_run_test_files_writes_artifact_and_summary_path(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()
    inp = ws / "input"
    inp.mkdir()
    summary = ws / "summary.json"

    class Proc:
        returncode = 0
        stdout = "{}"
        stderr = ""

    import src.routes.automation as automation_mod

    monkeypatch.setattr(automation_mod.subprocess, "run", lambda *a, **k: Proc())

    res = client.post(
        "/api/automation/larrak/run-test-files",
        json={
            "input_dir": str(inp),
            "glob": "*.pdf",
            "recursive": True,
            "enhance": True,
            "marker_extra_args": ["--max_pages", "5"],
            "summary_path": str(summary),
            "workspace_root": str(ws),
        },
    )
    assert res.status_code == 200
    assert Path(res.json()["artifact"]["path"]).exists()


def test_automation_helpers_clip_and_root_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.routes.automation as automation_mod

    monkeypatch.setattr(settings, "devplane_root", str(tmp_path))
    root = tmp_path.resolve()
    assert automation_mod._ensure_under_devplane_root(str(root)) == str(root)
    assert automation_mod._clip("x" * 10, 5).endswith("...(truncated)")
