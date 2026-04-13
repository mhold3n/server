from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_module(module_name: str, path: str | Path) -> ModuleType:
    module_path = Path(path).resolve()
    module_dir = str(module_path.parent)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    sys.path.insert(0, module_dir)
    try:
        spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == module_dir:
            sys.path.pop(0)
    return module
