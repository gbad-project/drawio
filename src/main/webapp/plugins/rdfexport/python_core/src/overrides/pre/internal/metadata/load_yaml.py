from __future__ import annotations

import yaml
from pathlib import Path

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="pre", type="internal", role="metadata")
def _load_config_yml(
    yml_filename="default.yml",
) -> tuple[
    dict[str, str], typing.Literal["pyodide", "metabuilder", "standalone", "unknown"]
]:
    """Loads dict from a YAML file from a config dir, by default `default.yml`.

    Supports two execution contexts:

    1. From Pyodide virtual FS (/app/src/draw_io_parser.py)
    2. Normal repo tree (src/main/webapp/plugins/rdfexport/)

    Returns:
        Tuple of:
            - Dict after YAML loading. Empty dict if file cannot be read.
            - Literal['pyodide','metabuilder','standalone','unknown'] for the detected context.
    """
    REPO_PLUGIN_DIR_PATH = Path("src/main/webapp/plugins/rdfexport")
    NORMAL_CONFIG_DIR_PATH = REPO_PLUGIN_DIR_PATH / "integration" / "config"

    PYODIDE_ROOT_PATH = Path("/app")
    PYODIDE_CONFIG_DIR_PATH = PYODIDE_ROOT_PATH / "config"

    DRAW_IO_PARSER_FILENAME = "draw_io_parser.py"

    config: dict[str, str] = {}
    candidate_path: Path | None = None
    context = "unknown"

    try:
        current_file = Path(__file__).resolve()
        if current_file.is_relative_to(PYODIDE_ROOT_PATH):
            # Assume Pyodide route - we know exact route
            try:
                candidate_path = PYODIDE_CONFIG_DIR_PATH / yml_filename
                if candidate_path.exists():
                    context = "pyodide"
                else:
                    # unknown because '/app' may turn out not to be pyodide fs
                    return config, context  # however init'd above
            except IndexError:
                pass
        else:
            # Standalone/General logic: search upwards for the specific path segment
            # Search from the current file's directory and move up
            # Check current_file.parent first, then all parents
            for parent in [current_file.parent] + list(current_file.parents):
                # Construct the full path to the config file relative to the current parent
                full_config_path = parent / NORMAL_CONFIG_DIR_PATH / yml_filename
                if full_config_path.exists():
                    candidate_path = full_config_path
                    context = (
                        "metabuilder"
                        if current_file.name == DRAW_IO_PARSER_FILENAME
                        else "standalone"
                    )
                    break  # Stop search once the target path is identified and confirmed to exist
    except Exception:
        pass

    # Final loading loop
    try:
        # Note: candidate_path confirmed exists at this point
        with open(candidate_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception:
        pass

    return config, context
