#!/usr/bin/env python3
"""Delegate to the xlotyl copy of ``response-control-framework/tools/wiki_compile.py``.

Editable orchestration sources live under ``xlotyl/knowledge/wiki/orchestration/``; compiled
JSON is written to ``xlotyl/knowledge/response-control/``. See that module for flags
(``--check``, ``--migrate-from-json``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "xlotyl" / "services" / "response-control-framework" / "tools" / "wiki_compile.py"
if not _TOOL.is_file():
    _TOOL = _ROOT / "services" / "response-control-framework" / "tools" / "wiki_compile.py"


def main() -> None:
    if not _TOOL.is_file():
        raise SystemExit(f"Missing wiki compile tool: {_TOOL}")
    raise SystemExit(subprocess.call([sys.executable, str(_TOOL), *sys.argv[1:]]))


if __name__ == "__main__":
    main()
