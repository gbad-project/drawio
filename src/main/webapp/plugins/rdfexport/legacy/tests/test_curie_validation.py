import sys
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import draw_io_parser  # noqa: E402

FIXTURES_DIR = LEGACY_DIR.parent / "tests" / "fixtures"
BASELINES_DIR = LEGACY_DIR.parent / "tests" / "baselines"


def test_individual_blocks_accepts_declared_prefix_curie():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/custom#"

    items = iter([
        draw_io_parser.Individual("SourceNode", "ex:CustomClass"),
        draw_io_parser.Individual("TargetNode", "ex:OtherClass"),
        draw_io_parser.Arrow(
            identifier="ex:connectsTo",
            source="SourceNode",
            target="TargetNode",
            is_datatype=False,
        ),
    ])

    blocks, object_props, datatype_props = draw_io_parser.individual_blocks(
        items,
        [],
        None,
        draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
        prefixes,
    )

    assert ("SourceNode", "SourceNode") in blocks
    assert "ex:CustomClass" in blocks[("SourceNode", "SourceNode")]["Types"]
    assert "ex:connectsTo" in object_props
    assert not datatype_props


def test_individual_blocks_tracks_datatype_properties():
    prefixes = draw_io_parser.get_prefixes()

    items = iter([
        draw_io_parser.Individual("LiteralNode", "rico:Thing"),
        draw_io_parser.Arrow(
            identifier="rdfs:label",
            source="LiteralNode",
            target="Example literal",
            is_datatype=True,
        ),
    ])

    blocks, object_props, datatype_props = draw_io_parser.individual_blocks(
        items,
        [],
        None,
        draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
        prefixes,
    )

    assert not object_props
    assert "rdfs:label" in datatype_props
    facts = blocks[("LiteralNode", "LiteralNode")]["rdfs:label"]
    assert "Example literal" in facts


def _normalise_graph(graph: Graph) -> Graph:
    filtered = Graph()
    for triple in graph:
        subject, predicate, obj = triple
        if predicate == RDF.type and obj in {
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.Ontology,
        }:
            continue
        if predicate == OWL.imports:
            continue
        filtered.add(triple)
    return filtered


@pytest.mark.parametrize(
    "baseline_path",
    sorted(BASELINES_DIR.glob("*.nt")),
)
def test_parse_drawio_matches_baseline_graphs(baseline_path: Path):
    fixture_path = FIXTURES_DIR / f"{baseline_path.stem}.drawio"
    expected = Graph()
    expected.parse(baseline_path, format="nt")

    actual = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    expected_normalised = _normalise_graph(expected)
    actual_normalised = _normalise_graph(actual)

    assert actual_normalised.isomorphic(expected_normalised)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "knut_olborgs_forskningsnotater.drawio",
        "koronakommisjonen.drawio",
    ],
)
def test_parse_drawio_accepts_previous_unknown_properties(fixture_name: str):
    fixture_path = FIXTURES_DIR / fixture_name
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    assert isinstance(graph, Graph)
    assert len(graph) > 0


def test_individual_blocks_rejects_unknown_prefix():
    prefixes = draw_io_parser.get_prefixes()

    items = iter([
        draw_io_parser.Individual("SourceNode", "rico:Thing"),
        draw_io_parser.Arrow(
            identifier="unknown:prop",
            source="SourceNode",
            target="Value",
            is_datatype=True,
        ),
    ])

    with pytest.raises(draw_io_parser.NotInKnownException):
        draw_io_parser.individual_blocks(
            items,
            [],
            None,
            draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
            prefixes,
        )
