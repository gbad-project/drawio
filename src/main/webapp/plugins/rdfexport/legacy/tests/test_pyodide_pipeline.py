from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree

from typing import Any

import pytest
from rdflib import Graph
from rdflib.namespace import RDFS

LEGACY_TESTS_DIR = Path(__file__).resolve().parent
RDFEXPORT_DIR = LEGACY_TESTS_DIR.parents[1]

if str(RDFEXPORT_DIR) not in sys.path:
    sys.path.insert(0, str(RDFEXPORT_DIR))

from pyodide_pipeline import (  # type: ignore[attr-defined]  # noqa: E402
    get_graph_summary,
    list_graph_ids,
    parse_drawio_xml_to_json,
    reset_graph_store,
)

FIXTURES_DIR = RDFEXPORT_DIR / "tests" / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _graph_from_summary(summary_json: str) -> Graph:
    summary = json.loads(summary_json)
    turtle_payload = json.loads(summary["raw_turtle"])
    graph = Graph()
    graph.parse(data=turtle_payload, format="turtle")
    return graph


def test_parse_drawio_xml_to_json_produces_summary() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")
    summary_json = parse_drawio_xml_to_json(xml_payload)
    summary = json.loads(summary_json)

    assert summary["graph_id"].startswith("graph-")
    assert summary["triple_count"] > 0
    assert any(ns["prefix"] == "rico" for ns in summary["namespaces"])


def test_graph_store_tracks_parsed_graphs() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")
    summary_json = parse_drawio_xml_to_json(xml_payload)
    summary = json.loads(summary_json)

    graph_ids = list_graph_ids()
    assert graph_ids == [summary["graph_id"]]

    cached = get_graph_summary(summary["graph_id"])
    assert cached["triple_count"] == summary["triple_count"]
    assert cached["csv_path"] == summary["csv_path"]
    assert cached["base_uri"] == summary["base_uri"]


def test_parse_drawio_accepts_graph_model_payload() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")
    xml_root = ElementTree.fromstring(xml_payload)
    graph_model = xml_root.find(".//mxGraphModel")

    assert graph_model is not None

    graph_model_xml = ElementTree.tostring(graph_model, encoding="unicode")
    summary_json = parse_drawio_xml_to_json(graph_model_xml)
    summary = json.loads(summary_json)

    assert summary["triple_count"] > 0
    assert any(ns["prefix"] == "rico" for ns in summary["namespaces"])


def test_duplicate_payloads_reuse_graph_identifier() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    first_summary = json.loads(parse_drawio_xml_to_json(xml_payload))
    second_summary = json.loads(parse_drawio_xml_to_json(xml_payload))

    assert first_summary["graph_id"] == second_summary["graph_id"]
    assert list_graph_ids() == [first_summary["graph_id"]]


def test_parse_drawio_respects_label_flags() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    default_graph = _graph_from_summary(parse_drawio_xml_to_json(xml_payload))
    default_label_count = len(list(default_graph.triples((None, RDFS.label, None))))
    assert default_label_count > 0

    reset_graph_store()
    without_labels = _graph_from_summary(
        parse_drawio_xml_to_json(xml_payload, {"include_label": False})
    )
    assert not list(without_labels.triples((None, RDFS.label, None)))

    reset_graph_store()
    without_labels_via_disable = _graph_from_summary(
        parse_drawio_xml_to_json(xml_payload, {"label_disable": True})
    )
    assert not list(without_labels_via_disable.triples((None, RDFS.label, None)))


def test_parse_drawio_passes_strict_mode_to_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    import legacy.draw_io_parser as parser_module

    captured: list[bool | None] = []
    original_classifier = parser_module.pipeline.core.xml.data.DrawIOCellClassifier

    class RecordingClassifier(original_classifier):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured.append(kwargs.get("strict_mode"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(
        parser_module.pipeline.core.xml.data,
        "DrawIOCellClassifier",
        RecordingClassifier,
    )

    parse_drawio_xml_to_json(xml_payload, {"strict_mode": True})
    assert captured[-1] is True

    reset_graph_store()
    parse_drawio_xml_to_json(xml_payload, {"strict_mode": False})
    assert captured[-1] is False


def test_serialisation_config_reflects_boolean_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import legacy.overrides.rml_export as rml_override

    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    captured_configs: list[Any] = []
    original_serialise = rml_override.serialise_to_graph

    def recording_serialise_to_graph(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_configs.append(args[3])
        return original_serialise(*args, **kwargs)

    monkeypatch.setattr(
        rml_override,
        "serialise_to_graph",
        recording_serialise_to_graph,
    )

    parse_drawio_xml_to_json(
        xml_payload,
        {
            "include_label": False,
            "include_preamble": False,
            "infer_type_of_literals": False,
        },
    )

    assert captured_configs, "serialise_to_graph was not invoked"
    config = captured_configs[-1]
    assert config.include_label is False
    assert config.include_preamble is False
    assert config.infer_type_of_literals is False

    reset_graph_store()
    captured_configs.clear()

    parse_drawio_xml_to_json(
        xml_payload,
        {
            "label_disable": True,
            "preamble_disable": True,
            "infer_types_disable": True,
        },
    )

    assert captured_configs, "serialise_to_graph was not invoked for disable flags"
    config = captured_configs[-1]
    assert config.include_label is False
    assert config.include_preamble is False
    assert config.infer_type_of_literals is False
