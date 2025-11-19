from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree

# ruff: noqa: E402

PLUGIN_DIR = Path(__file__).resolve().parents[3]


from aicode.python_core.pyodide_pipeline import (  # type: ignore[attr-defined]  # noqa: E402
    get_graph_summary,
    list_graph_ids,
    parse_drawio_xml,
    parse_drawio_xml_to_json,
    reset_graph_store,
)
from rdflib.namespace import OWL, RDFS, XSD, RDF

FIXTURES_DIR = PLUGIN_DIR / "data" / "fixtures" / "drawio_fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


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


def test_parse_drawio_respects_include_label_toggle() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    _, graph_without_labels = parse_drawio_xml(xml_payload, {"include_label": False})
    without_count = sum(
        1 for _ in graph_without_labels.triples((None, RDFS.label, None))
    )
    assert without_count == 0

    reset_graph_store()
    _, graph_with_labels = parse_drawio_xml(xml_payload, {"include_label": True})
    with_count = sum(1 for _ in graph_with_labels.triples((None, RDFS.label, None)))
    assert with_count > 0


def test_parse_drawio_respects_include_preamble_toggle() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    _, graph_without_preamble = parse_drawio_xml(
        xml_payload, {"include_preamble": False}
    )
    assert (
        sum(1 for _ in graph_without_preamble.triples((None, OWL.Ontology, None))) == 0
    )

    reset_graph_store()
    _, graph_with_preamble = parse_drawio_xml(xml_payload, {"include_preamble": True})
    assert (
        sum(1 for _ in graph_with_preamble.triples((None, RDF.type, OWL.Ontology))) > 0
    )


def test_parse_drawio_respects_infer_literal_toggle() -> None:
    reset_graph_store()
    xml_payload = _load_fixture("AA37 Department of Health.drawio")

    _, graph_without_inference = parse_drawio_xml(
        xml_payload, {"infer_type_of_literals": False}
    )
    inferred_disabled = sum(
        1
        for _, _, obj in graph_without_inference
        if getattr(obj, "datatype", None) in {XSD.integer, XSD.float, XSD.date}
    )
    assert inferred_disabled == 0

    reset_graph_store()
    _, graph_with_inference = parse_drawio_xml(
        xml_payload, {"infer_type_of_literals": True}
    )
    inferred_enabled = sum(
        1
        for _, _, obj in graph_with_inference
        if getattr(obj, "datatype", None) in {XSD.integer, XSD.float, XSD.date}
    )
    assert inferred_enabled > 0
