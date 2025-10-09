import pathlib

import pytest
import pathlib

import pytest
from rdflib import Graph, Literal as RDFLiteral, Namespace, RDF, RDFS, URIRef
from rdflib.compare import to_isomorphic

from .draw_io_parser import (
    Arrow,
    Individual,
    NotInKnownException,
    get_prefixes,
    individual_blocks,
    parse_drawio_to_graph,
)


def _make_generator(*items):
    for item in items:
        yield item


def test_individual_blocks_accepts_custom_prefix():
    prefixes = get_prefixes()
    prefixes = dict(prefixes)
    prefixes["ex"] = "http://example.com/ns#"

    blocks, property_types = individual_blocks(
        _make_generator(
            Individual("Person1", "ex:CustomClass"),
            Arrow("ex:relatesTo", "Person1", "Literal value", True),
        ),
        [],
        None,
        "none",
        prefixes,
    )

    block_key = ("Person1", "Person1")
    assert block_key in blocks
    assert "Types" in blocks[block_key]
    assert "ex:CustomClass" in blocks[block_key]["Types"]
    assert property_types["ex:relatesTo"] == "datatype"


def test_individual_blocks_unknown_prefix_raises():
    prefixes = get_prefixes()

    with pytest.raises(NotInKnownException):
        individual_blocks(
            _make_generator(
                Arrow("foo:relatesTo", "source", "value", True),
            ),
            [],
            None,
            "none",
            prefixes,
        )


def test_parse_drawio_to_graph_matches_fixture():
    fixtures_dir = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    drawio_path = fixtures_dir / "AA37 Department of Health.drawio"

    graph = parse_drawio_to_graph(
        str(drawio_path),
        metacharacter_substitute=["remove"],
    )

    assert len(graph) == 72

    prefixes = get_prefixes()
    rico_ns = Namespace(prefixes["rico"])

    activity_uri = URIRef("https://example.com/id/AuthorityRecordCreation")
    assert (activity_uri, RDF.type, rico_ns.Activity) in graph
    assert (activity_uri, RDFS.label, RDFLiteral("Authority Record Creation")) in graph
