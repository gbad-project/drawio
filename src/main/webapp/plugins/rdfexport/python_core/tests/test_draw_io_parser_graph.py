import pytest

from rdflib import URIRef, Graph

from python_core.src.overrides.core.rdf.control.draw_io_parser_graph import (
    DrawIOParserGraph,
)


class SampleTurtleWithBase:
    def __init__(self):
        self.base = URIRef("http://mock_test_extract_base_from_turtle")
        self.turtle = """@base <{}> .
</mock_subject> a <#mock_object> .
""".format(self.base)


@pytest.fixture
def fixture():
    return SampleTurtleWithBase()


def test_extract_base_from_turtle(fixture):
    extracted_base = DrawIOParserGraph.extract_base_from_turtle(fixture.turtle)
    assert extracted_base == fixture.base


def test_base_extraction_on_parse(fixture):
    # First, let's confirm that `base` is not set
    # when parsing a Turtle string with a known
    # @base directive to a regular Graph
    g = Graph()
    g.parse(data=fixture.turtle, format="turtle")
    assert g.base is None  # because IRIs are resolved

    # Now, DrawIOParserGraph:
    # parse and serialize
    dpg1 = DrawIOParserGraph()
    dpg1.parse(data=fixture.turtle, format="turtle")
    assert dpg1.base == fixture.base

    # Finally, confirm that base is written into
    # the serialized even if not passed explicitly
    # to `serialize()` - it reads it from attr
    serialized = dpg1.serialize()
    dpg2 = DrawIOParserGraph()
    dpg2.parse(data=serialized, format="turtle")
    assert dpg2.base == fixture.base
