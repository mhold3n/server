import subprocess
import sys
from pathlib import Path


def test_wiki_orchestration_drift() -> None:
    """Ensure orchestration JSONs are in sync with Wiki markdown (after domain sync)."""
    here = Path(__file__).resolve()
    repo_root = None
    for path in [here, *here.parents]:
        if (path / "services" / "response-control-framework").exists():
            repo_root = path
            break

    assert repo_root is not None, "Could not locate repo root"

    sync = repo_root / "scripts" / "sync_domain_orchestration_wiki.py"
    subprocess.run([sys.executable, str(sync)], cwd=str(repo_root), check=True)

    tool_path = repo_root / "services" / "response-control-framework" / "tools" / "wiki_compile.py"
    assert tool_path.exists(), f"Wiki compile tool not found at {tool_path}"

    result = subprocess.run(
        [sys.executable, str(tool_path), "--check"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Wiki check failed:\n{result.stderr}\n{result.stdout}"
