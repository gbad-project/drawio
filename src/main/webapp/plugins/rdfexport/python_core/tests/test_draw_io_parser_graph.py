import pytest

from rdflib import URIRef, Graph

from python_core.src.overrides.core.rdf.control.draw_io_parser_graph import (
    DrawIOParserGraph,
)


class SampleTurtleWithBase:
    def __init__(self):
        self.base = URIRef("mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/blank-prefix-is-same-but-with-trailing-slash")
        self.blank_prefix = URIRef(f"{self.base}/")
        self.turtle = """@base <{}> .
@prefix : <{}> .
</not_from_base_uri_rel_slash_subject> a <#not_from_base_uri_rel_hash_object> .
:not_from_base_uri_blank_prefix_curie a <not_from_base_uri_rel_nothing_object> .
""".format(self.base, self.blank_prefix)


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

def test_base_blank_prefix_handling(fixture):
    g1 = Graph()
    g1.parse(data=fixture.turtle, format="turtle")
    g1_serialized = g1.serialize(format="turtle")
    print("\n\n-----RDFLIB GRAPH: BEGIN TURTLE-----")
    print(g1_serialized)
    print("-----RDFLIB GRAPH: END TURTLE-----\n\n")
    
    # stock Graph does not generate @base unless base is explicitly set,
    # which here it is not - neither on parsing nor on serialization
    assert "@base" not in g1_serialized
    # relative IRI resolved against @base in graph and according to RFC 3986
    assert "<mock://base_uri_originally_has_two_terms_after_tld/not_from_base_uri_rel_slash_subject>" in g1_serialized
    # hash IRI is resolved against full base without trimming - as expected
    assert "<mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/blank-prefix-is-same-but-with-trailing-slash#not_from_base_uri_rel_hash_object>" in g1_serialized
    # if relative IRI does not start with a slash nor hash, this replaces the
    # last term from base URI?? okay, perhaps that's also according to RFC 3986
    assert "<mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/not_from_base_uri_rel_nothing_object>" in g1_serialized
    # prefix correctly captured
    assert "@prefix : <mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/blank-prefix-is-same-but-with-trailing-slash/> ." in g1_serialized
    assert ":not_from_base_uri_blank_prefix_curie" in g1_serialized

    g2 = DrawIOParserGraph()
    g2.parse(data=fixture.turtle, format="turtle")
    g2_serialized = g2.serialize(format="turtle")
    print("\n\n-----DRAW IO PARSER GRAPH: BEGIN TURTLE-----")
    print(g2_serialized)
    print("-----DRAW IO PARSER GRAPH: END TURTLE-----\n\n")
    assert "@prefix : <mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/blank-prefix-is-same-but-with-trailing-slash/> ." in g2_serialized
    assert "@base <mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/blank-prefix-is-same-but-with-trailing-slash> ." in g2_serialized
    # rel iris correctly resolved against base using RFC 3986
    assert "<mock://base_uri_originally_has_two_terms_after_tld/not_from_base_uri_rel_slash_subject>" in g2_serialized
    assert "<mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/not_from_base_uri_rel_nothing_object>" in g2_serialized 
    # blank prefix INCORRECTLY serialized as a relative IRI instead of 
    # a curie, which leads to it being parsed with RFC 3986 upon re-parse
    assert "</not_from_base_uri_blank_prefix_curie>" in g2_serialized
    # ..as evidenced below:

    g3 = DrawIOParserGraph()
    g3.parse(data=g2_serialized, format="turtle")
    g3_serialized = g3.serialize(format="turtle")
    print("\n\n-----RE-PARSED DRAW IO PARSER GRAPH: BEGIN TURTLE-----")
    print(g3_serialized)
    print("-----RE-PARSED DRAW IO PARSER GRAPH: END TURTLE-----\n\n")
    # no prefix directive anymore as no :prefixed values left in serialized
    assert "@prefix" not in g3_serialized
    # uri for not_from_base_uri_rel_nothing_object stays correct because
    # it has already been absolutized above - apparently key to success
    assert "<mock://base_uri_originally_has_two_terms_after_tld/no-trailing-slash/not_from_base_uri_rel_nothing_object>" in g3_serialized 
    # incorrect IRI originally from blank prefix but now with all terms trimmed
    assert "<mock://base_uri_originally_has_two_terms_after_tld/not_from_base_uri_blank_prefix_curie>" in g3_serialized
    
