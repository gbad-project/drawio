"""Helpers to run the DrawIO parser inside Pyodide."""

from __future__ import annotations

import hashlib
import json
import itertools
import sys
from pathlib import Path
from copy import deepcopy
from typing import Any, Dict, Iterable
from xml.etree import ElementTree
from typing import TYPE_CHECKING
import yaml

# ruff: noqa: F403, F405

if TYPE_CHECKING:
    from python_core.src.draw_io_parser import *


class NonexistentPath(Path):
    """Dummy whose `Path.exists()` is always False."""

    def exists(self):
        return False


REAL_ROOT_DIR = NonexistentPath()
REAL_DRAW_IO_PARSER_DIR = NonexistentPath()
VIRTUAL_ROOT_DIR = NonexistentPath()
VIRTUAL_DRAW_IO_PARSER_DIR = NonexistentPath()

try:
    REAL_ROOT_DIR = Path(__file__).resolve().parents[3]
    REAL_DRAW_IO_PARSER_DIR = REAL_ROOT_DIR / "python_core" / "src"
    if not REAL_DRAW_IO_PARSER_DIR.exists():
        raise FileNotFoundError
    else:
        pass  # global vars now point to existing paths
    if str(REAL_DRAW_IO_PARSER_DIR) not in sys.path:
        sys.path.insert(0, str(REAL_DRAW_IO_PARSER_DIR))
except (IndexError, FileNotFoundError):
    # When resolve parents index out of bounds or parser dir not exists
    pass
try:
    # Pyodide specific - on virtual FS (see `pyodideRuntime.ts` to change)
    VIRTUAL_ROOT_DIR = Path(__file__).resolve().parents[1]
    VIRTUAL_DRAW_IO_PARSER_DIR = VIRTUAL_ROOT_DIR / "src"
    if not VIRTUAL_DRAW_IO_PARSER_DIR.exists():
        raise FileNotFoundError
    else:
        pass  # global vars now point to existing paths
    if str(VIRTUAL_DRAW_IO_PARSER_DIR) not in sys.path:
        sys.path.insert(0, str(VIRTUAL_DRAW_IO_PARSER_DIR))
except (IndexError, FileNotFoundError):
    # When resolve parents index out of bounds or parser dir not exists
    pass


from draw_io_parser import (  # type: ignore[attr-defined]  # noqa: E402
    DrawIOParserGraph,
    _build_graph_from_raw_xml,
)

DEFAULT_METACHARACTER_SUBSTITUTE = ["url"]

_LAST_PARSER_CONFIG: dict[str, Any] | None = None

GraphSummary = Dict[str, Any]

_GRAPH_STORE: dict[str, DrawIOParserGraph] = {}
_GRAPH_CACHE: dict[str, str] = {}
_GRAPH_ID_COUNTER = itertools.count()


class RootPathNotFound(Exception):
    def __init__(self, message="[drawio_pipeline.py]: Root path not found"):
        super().__init__(message)


def _get_root_dir() -> tuple[Path, str]:
    # Note: REAL_DRAW_IO_PARSER_DIR comes first in source code
    # because we yield to virtual iif real does not exist
    if REAL_DRAW_IO_PARSER_DIR.exists():
        return REAL_ROOT_DIR, "real"
    elif VIRTUAL_DRAW_IO_PARSER_DIR.exists():
        return VIRTUAL_ROOT_DIR, "virtual"
    else:
        raise RootPathNotFound


def _next_graph_id() -> str:
    return f"graph-{next(_GRAPH_ID_COUNTER)}"


def reset_graph_store() -> None:
    """Clear cached graphs and reset identifiers (useful for tests)."""
    global _GRAPH_ID_COUNTER
    _GRAPH_STORE.clear()
    _GRAPH_CACHE.clear()
    _GRAPH_ID_COUNTER = itertools.count()


def list_graph_ids() -> list[str]:
    """Return the identifiers of cached graphs."""
    return list(_GRAPH_STORE.keys())


def _default_parser_config() -> dict[str, Any]:
    """Read default YAML config and return parser defaults."""
    root_dir, fs_type = _get_root_dir()
    if fs_type == "virtual":
        config_path = root_dir / "config" / "default.yml"
    elif fs_type == "real":
        config_path = root_dir / "integration" / "config" / "default.yml"
    else:
        raise RootPathNotFound
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config.get("parser_config", {})
    except:
        raise


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False

    if value is None:
        return fallback

    return bool(value)


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None

    return str(value)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _normalise_metacharacters(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        return [value] if len(value) > 0 else []

    try:
        result = []
        for item in value:
            if isinstance(item, str) and len(item) > 0:
                result.append(item)
        return result
    except TypeError:
        return []


def _normalise_literal_definitions(
    value: Any,
) -> list[dict[str, str]] | None:
    """Normalise literal_definitions from overrides.

    Returns:
        None: if value is None (use defaults from YAML)
        []: if value is an empty list (user explicitly cleared definitions)
        list of dicts: if value contains valid entries
    """
    if value is None:
        return None

    if not isinstance(value, list):
        return None

    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        attr_key = item.get("attr_key")
        attr_value = item.get("attr_value")
        if isinstance(attr_key, str) and isinstance(attr_value, str):
            result.append({"attr_key": attr_key, "attr_value": attr_value})

    # Return empty list if input was empty list (user explicitly cleared)
    # This is different from None which means "use defaults"
    if len(value) == 0:
        return []

    return result


def _apply_parser_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    config = _default_parser_config()

    if overrides:
        if "infer_type_of_literals" in overrides:
            config["infer_type_of_literals"] = _coerce_bool(
                overrides["infer_type_of_literals"],
                config["infer_type_of_literals"],
            )
        if "include_preamble" in overrides:
            config["include_preamble"] = _coerce_bool(
                overrides["include_preamble"],
                config["include_preamble"],
            )
        if "include_label" in overrides:
            config["include_label"] = _coerce_bool(
                overrides["include_label"],
                config["include_label"],
            )
        if "strict_mode" in overrides:
            config["strict_mode"] = _coerce_bool(
                overrides["strict_mode"],
                config["strict_mode"],
            )
        if "strip_html" in overrides:
            config["strip_html"] = _coerce_bool(
                overrides["strip_html"],
                config["strip_html"],
            )
        if "ontology_iri" in overrides:
            config["ontology_iri"] = _coerce_optional_str(overrides["ontology_iri"])
        if "prefix" in overrides:
            config["prefix"] = _coerce_optional_str(overrides["prefix"])
        if "prefix_iri" in overrides:
            config["prefix_iri"] = _coerce_optional_str(overrides["prefix_iri"])
        if "indentation" in overrides:
            config["indentation"] = _coerce_int(
                overrides["indentation"],
                config["indentation"],
            )
        if "max_gap" in overrides:
            config["max_gap"] = _coerce_float(
                overrides["max_gap"],
                config["max_gap"],
            )
        if "metacharacter_substitute" in overrides:
            config["metacharacter_substitute"] = _normalise_metacharacters(
                overrides["metacharacter_substitute"],
            )
        if "capitalisation_scheme" in overrides and isinstance(
            overrides["capitalisation_scheme"],
            str,
        ):
            config["capitalisation_scheme"] = overrides["capitalisation_scheme"]
        if "rml_enabled" in overrides:
            config["rml_enabled"] = _coerce_bool(
                overrides["rml_enabled"],
                config["rml_enabled"],
            )
        if "literal_definitions" in overrides:
            normalised = _normalise_literal_definitions(
                overrides["literal_definitions"]
            )
            # Only override if normalised is not None
            # None means "use defaults from YAML"
            # Empty list means "user explicitly cleared definitions"
            if normalised is not None:
                config["literal_definitions"] = normalised

    config["metacharacter_substitute"] = _normalise_metacharacters(
        config["metacharacter_substitute"]
    )

    global _LAST_PARSER_CONFIG
    _LAST_PARSER_CONFIG = deepcopy(config)
    return config


def get_last_parser_config() -> dict[str, Any] | None:
    """Return the most recent parser configuration (for testing/debugging)."""

    if _LAST_PARSER_CONFIG is None:
        return None

    return deepcopy(_LAST_PARSER_CONFIG)


def _store_graph(graph: DrawIOParserGraph, payload_hash: str | None = None) -> str:
    if payload_hash and payload_hash in _GRAPH_CACHE:
        graph_id = _GRAPH_CACHE[payload_hash]
        _GRAPH_STORE[graph_id] = graph
        return graph_id

    graph_id = _next_graph_id()
    _GRAPH_STORE[graph_id] = graph

    if payload_hash:
        _GRAPH_CACHE[payload_hash] = graph_id

    return graph_id


def _normalize_drawio_xml(serialized_xml: str) -> str:
    stripped = serialized_xml.strip()

    if not stripped:
        raise ValueError("Serialized DrawIO XML payload is empty")

    try:
        root = ElementTree.fromstring(stripped)
    except ElementTree.ParseError:
        return stripped

    if root.tag == "mxfile":
        return stripped

    if root.tag == "diagram":
        container = ElementTree.Element("mxfile")
        container.append(deepcopy(root))
        return ElementTree.tostring(container, encoding="unicode")

    if root.tag == "mxGraphModel":
        container = ElementTree.Element("mxfile")
        diagram = ElementTree.SubElement(
            container,
            "diagram",
            {
                "name": root.attrib.get("name", "Page-1"),
                "id": root.attrib.get("id", "pyodide"),
            },
        )
        diagram.append(deepcopy(root))
        return ElementTree.tostring(container, encoding="unicode")

    return stripped


def _build_summary(graph_id: str, graph: DrawIOParserGraph) -> GraphSummary:
    def sorted_namespaces(ns_mgr: NamespaceManager) -> Iterable[tuple[str | None, Any]]:
        namespaces = list(ns_mgr.namespaces())
        namespaces.sort(
            key=lambda item: (
                "" if item[0] is None else item[0]  # defensive
            )
        )
        return namespaces

    def namespace_dictl(graph: Graph):
        return [
            {"prefix": prefix or "", "iri": str(iri)}
            for prefix, iri in sorted_namespaces(graph.namespace_manager)
        ]

    payload = {
        "graph_id": graph_id,
        "triple_count": len(graph),
        "csv_path": getattr(graph, "csv_path", None),
        "base_uri": getattr(graph, "base", None),
        "namespaces": namespace_dictl(graph),
        "raw_turtle": json.dumps(graph.serialize(format="turtle")),
    }

    return payload


def get_graph_summary(graph_id: str) -> GraphSummary:
    """Return a cached graph summary."""
    graph = _GRAPH_STORE[graph_id]
    return _build_summary(graph_id, graph)


def parse_drawio_xml(
    serialized_xml: str, parser_config: dict[str, Any] | None = None
) -> tuple[str, DrawIOParserGraph]:
    """Parse DrawIO XML into a DrawIOParserGraph and cache it."""
    normalized_xml = _normalize_drawio_xml(serialized_xml)
    config = _apply_parser_overrides(parser_config)
    payload_descriptor = json.dumps(
        {"xml": normalized_xml, "config": config},
        sort_keys=True,
        separators=(",", ":"),
    )
    payload_hash = hashlib.sha256(payload_descriptor.encode("utf-8")).hexdigest()
    graph = _build_graph_from_raw_xml(normalized_xml, config)
    graph_id = _store_graph(graph, payload_hash)
    return graph_id, graph


def parse_drawio_xml_to_json(
    serialized_xml: str, parser_config: dict[str, Any] | None = None
) -> str:
    """Parse DrawIO XML and return a JSON payload describing the graph."""
    graph_id, graph = parse_drawio_xml(serialized_xml, parser_config)
    summary = _build_summary(graph_id, graph)
    return json.dumps(summary, sort_keys=True)
