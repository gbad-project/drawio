from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
PYODIDE_WHEELS_DIR = Path(__file__).resolve().parents[2] / "pyodide" / "wheels"


def _ensure_wheel_installed(package: str, wheel_filename: str) -> None:
    if importlib.util.find_spec(package) is not None:
        return

    base64_path = PYODIDE_WHEELS_DIR / f"{wheel_filename}.base64"
    if not base64_path.exists():
        raise ModuleNotFoundError(
            f"{package} is required for the rdfexport tests but the vendored wheel "
            f"{base64_path.name} was not found. Run 'bun run setup:pyodide' to fetch "
            "Pyodide assets before executing pytest."
        )

    VENDOR_DIR.mkdir(exist_ok=True)
    wheel_path = VENDOR_DIR / wheel_filename

    if not wheel_path.exists():
        wheel_bytes = base64.b64decode(base64_path.read_bytes())
        wheel_path.write_bytes(wheel_bytes)

    wheel_path_str = str(wheel_path)
    if wheel_path_str not in sys.path:
        sys.path.insert(0, wheel_path_str)


# Ensure transitive dependencies are available before rdflib imports
_ensure_wheel_installed("pyparsing", "pyparsing-3.2.5-py3-none-any.whl")
_ensure_wheel_installed("rdflib", "rdflib-7.2.1-py3-none-any.whl")
