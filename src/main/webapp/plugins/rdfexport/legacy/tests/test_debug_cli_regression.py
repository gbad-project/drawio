from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

LEGACY_TESTS_DIR = Path(__file__).resolve().parent
RDFEXPORT_DIR = LEGACY_TESTS_DIR.parents[1]

if str(RDFEXPORT_DIR) not in sys.path:
    sys.path.insert(0, str(RDFEXPORT_DIR))

from debug.__main__ import estimate_triple_count_from_classifications  # noqa: E402
from legacy import draw_io_parser  # noqa: E402


FIXTURES_DIR = RDFEXPORT_DIR / "tests" / "fixtures"
DEBUG_DIR = RDFEXPORT_DIR / "debug"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"pytest-{slug or 'scenario'}"


def _load_prefixes(xml_text: str) -> dict[str, str]:
    metadata_prefixes, _, _, _ = draw_io_parser._extract_drawio_metadata(xml_text)
    prefixes = draw_io_parser.get_prefixes()
    prefixes.update(metadata_prefixes)
    return prefixes


def _ensure_graph_covers_classifications(
    graph: Graph,
    classifications: dict[str, dict],
    xml_text: str,
) -> None:
    prefixes = _load_prefixes(xml_text)
    namespace_manager = Graph().namespace_manager
    for prefix, iri in prefixes.items():
        namespace_manager.bind(prefix, iri, replace=True)

    classifier_cls = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier
    default_type = getattr(classifier_cls, "DEFAULT_STANDALONE_TYPE", "rico:Thing")

    identifiers: set[str] = set()
    for cell_data in classifications.values():
        kind = cell_data.get("kind")
        raw_value = (cell_data.get("raw_value") or "").strip()
        if not raw_value:
            continue
        if kind == "STANDALONE_INDIVIDUAL":
            identifier = cell_data.get("identifier") or raw_value
            if identifier:
                identifiers.add(identifier)
        if kind == "TYPED_INDIVIDUAL":
            identifier = cell_data.get("parent_identifier") or cell_data.get(
                "identifier"
            )
            if identifier:
                identifiers.add(identifier)

    identifier_subjects: dict[str, set] = {}
    for identifier in identifiers:
        subjects = {
            subject for subject in graph.subjects(RDFS.label, Literal(identifier))
        }
        identifier_subjects[identifier] = subjects
        assert subjects, f"Missing label triple for identifier '{identifier}'"

    for cell_id, cell_data in classifications.items():
        raw_value = (cell_data.get("raw_value") or "").strip()
        if not raw_value:
            continue

        kind = cell_data.get("kind")

        if kind == "STANDALONE_INDIVIDUAL":
            identifier = cell_data.get("identifier") or raw_value
            subjects = identifier_subjects.get(identifier, set())
            assert subjects, f"No subjects found for standalone '{identifier}'"
            tokens = [token for token in cell_data.get("tokens", []) if token]
            if not tokens:
                tokens = [default_type]
            for token in tokens:
                expanded = namespace_manager.expand_curie(token)
                assert any(
                    (subject, RDF.type, URIRef(expanded)) in graph
                    for subject in subjects
                ), f"Missing rdf:type '{token}' for '{identifier}'"
            continue

        if kind == "TYPED_INDIVIDUAL":
            identifier = cell_data.get("parent_identifier") or cell_data.get(
                "identifier"
            )
            if not identifier:
                continue
            subjects = identifier_subjects.get(identifier, set())
            assert subjects, f"No subjects found for typed '{identifier}'"
            for token in cell_data.get("tokens", []):
                if not token:
                    continue
                expanded = namespace_manager.expand_curie(token)
                assert any(
                    (subject, RDF.type, URIRef(expanded)) in graph
                    for subject in subjects
                ), f"Missing rdf:type '{token}' for '{identifier}'"
            continue

        if kind == "LITERAL":
            assert any(
                str(obj) == raw_value for _, _, obj in graph.triples((None, None, None))
            ), f"Literal '{raw_value}' not found in graph"
            continue

        if kind == "DECORATION":
            assert any(
                obj == Literal(raw_value)
                for _, _, obj in graph.triples((None, SKOS.note, None))
            ), f"Decoration '{raw_value}' missing from SKOS notes"
            continue

        if kind == "ARROW_LABEL":
            if ":" not in raw_value:
                continue
            prefix = raw_value.split(":", 1)[0]
            if prefix not in prefixes:
                continue
            expanded = namespace_manager.expand_curie(raw_value)
            assert any(
                predicate == URIRef(expanded)
                for _, predicate, _ in graph.triples((None, None, None))
            ), f"Property '{raw_value}' not used in graph"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(FIXTURES_DIR.glob("*.drawio"), key=lambda path: path.name),
)
def test_debug_cli_matches_expected_triple_counts(fixture_path: Path) -> None:
    slug = _slugify(fixture_path.stem)
    cmd = [
        sys.executable,
        "-m",
        "debug",
        "--drawio",
        str(fixture_path),
        "--slug",
        slug,
        "--format",
        "turtle",
    ]

    subprocess.run(cmd, cwd=RDFEXPORT_DIR, check=True, capture_output=True)

    map_path = DEBUG_DIR / "map.json"
    map_data = json.loads(map_path.read_text(encoding="utf-8"))
    scenario_entry = map_data["scenarios"].get(slug)
    assert scenario_entry is not None, f"Scenario '{slug}' not recorded"

    classifications = scenario_entry.get("cell_classifications", {})
    xml_text = fixture_path.read_text(encoding="utf-8")

    results = scenario_entry.get("results", {})
    if "ts_plugin" not in results:
        errors = scenario_entry.get("errors", {})
        assert "ts_plugin" in errors, "ts_plugin graph missing without recorded error"
        pytest.skip("ts_plugin graph unavailable for this fixture")

    ttl_path = DEBUG_DIR / results["ts_plugin"]["path"]
    assert ttl_path.exists(), f"Turtle output missing for {fixture_path.name}"

    graph = Graph()
    graph.parse(ttl_path, format="turtle")

    expected_triples = estimate_triple_count_from_classifications(
        xml_text, classifications, graph=graph
    )
    actual_triples = results["ts_plugin"]["triples"]
    assert actual_triples == expected_triples, (
        f"Triple count mismatch for {fixture_path.name}"
    )

    _ensure_graph_covers_classifications(graph, classifications, xml_text)
