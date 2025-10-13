"""Helpers to run the DrawIO parser inside Pyodide."""

from __future__ import annotations

import hashlib
import json
import itertools
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable
from xml.etree import ElementTree

LEGACY_DIR = Path(__file__).resolve().parents[1] / "legacy"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from draw_io_parser import (  # type: ignore[attr-defined]  # noqa: E402
    DrawioParserGraph,
    DEFAULT_CAPITALISATION_SCHEME,
    DEFAULT_INDENTATION,
    DEFAULT_MAX_GAP,
    _build_graph_from_raw_xml,
)

DEFAULT_METACHARACTER_SUBSTITUTE = ["url"]

GraphSummary = Dict[str, Any]

_GRAPH_STORE: dict[str, DrawioParserGraph] = {}
_GRAPH_CACHE: dict[str, str] = {}
_GRAPH_ID_COUNTER = itertools.count()


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
    """Return parser defaults matching the CLI behaviour."""
    return {
        "infer_type_of_literals": True,
        "include_preamble": True,
        "ontology_iri": None,
        "prefix": None,
        "prefix_iri": None,
        "indentation": DEFAULT_INDENTATION,
        "include_label": True,
        "max_gap": DEFAULT_MAX_GAP,
        "strict_mode": False,
        "metacharacter_substitute": DEFAULT_METACHARACTER_SUBSTITUTE,
        "capitalisation_scheme": DEFAULT_CAPITALISATION_SCHEME,
    }


def _store_graph(graph: DrawioParserGraph, payload_hash: str | None = None) -> str:
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


def _sorted_namespaces(graph: DrawioParserGraph) -> Iterable[tuple[str | None, Any]]:
    namespaces = list(graph.namespace_manager.namespaces())
    namespaces.sort(key=lambda item: ("" if item[0] is None else item[0]))
    return namespaces


def _build_summary(graph_id: str, graph: DrawioParserGraph) -> GraphSummary:
    base = getattr(graph, "base", None)
    csv_path = getattr(graph, "csv_path", None)

    namespaces = [
        {"prefix": prefix or "", "iri": str(iri)}
        for prefix, iri in _sorted_namespaces(graph)
    ]

    return {
        "graph_id": graph_id,
        "triple_count": len(graph),
        "csv_path": csv_path,
        "base_uri": str(base) if base else None,
        "namespaces": namespaces,
        "raw_turtle": json.dumps(graph.serialize(format="turtle"), sort_keys=True),
    }


def get_graph_summary(graph_id: str) -> GraphSummary:
    """Return a cached graph summary."""
    graph = _GRAPH_STORE[graph_id]
    return _build_summary(graph_id, graph)


def parse_drawio_xml(serialized_xml: str) -> tuple[str, DrawioParserGraph]:
    """Parse DrawIO XML into a DrawioParserGraph and cache it."""
    normalized_xml = _normalize_drawio_xml(serialized_xml)
    config = _default_parser_config()
    graph = _build_graph_from_raw_xml(normalized_xml, config)
    payload_hash = hashlib.sha256(normalized_xml.encode("utf-8")).hexdigest()
    graph_id = _store_graph(graph, payload_hash)
    return graph_id, graph


def parse_drawio_xml_to_json(serialized_xml: str) -> str:
    """Parse DrawIO XML and return a JSON payload describing the graph."""
    graph_id, graph = parse_drawio_xml(serialized_xml)
    summary = _build_summary(graph_id, graph)
    return json.dumps(summary, sort_keys=True)
