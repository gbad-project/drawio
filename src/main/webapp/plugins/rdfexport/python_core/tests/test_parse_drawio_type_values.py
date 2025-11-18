import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from textwrap import dedent
from typing import Optional

import pytest
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import draw_io_parser  # noqa: E402


@pytest.mark.parametrize(
    "rml_enabled, individual_label, type_value, expected_type_term, expect_exception",
    [
        # Non-RML cases
        (
            False,
            "Template Individual Only Reference",
            "{RICO_AUTHTP_CLASS}",
            None,
            True,
        ),
        (
            False,
            "Template Individual URIRef Encoded",
            "https://example.com/%7BRICO_AUTHTP_CLASS%7D",
            URIRef("https://example.com/%7BRICO_AUTHTP_CLASS%7D"),
            False,
        ),
        # Not encoded should not get here - dealt with upstream
        # at metacharacter replacements; so not testing it
        # (
        #     False,
        #     "Template Individual URIRef Not Encoded",
        #     "https://example.com/{RICO_AUTHTP_CLASS}",
        #     URIRef("https://example.com/%7BRICO_AUTHTP_CLASS%7D"),
        #     False,
        # ),
        (
            False,
            "Curie Individual",
            "rdfs:Class",
            URIRef("http://www.w3.org/2000/01/rdf-schema#Class"),
            False,
        ),
        (
            False,
            "Abs IRI Individual",
            "http://example.com/exampleClass",
            URIRef("http://example.com/exampleClass"),
            False,
        ),
        (
            False,
            "Rel IRI Individual",
            "/someClass",
            # Note double slash - prefix IRI defined below with a trailing slash
            URIRef("http://example.com//someClass"),
            False,
        ),
        (False, "Nefarious Individual", "Unexpected Literal As Type", None, True),
        # RML-enabled cases
        (
            True,
            "Template Individual Only Reference",
            "{RICO_AUTHTP_CLASS}",
            Literal("{RICO_AUTHTP_CLASS}"),
            False,
        ),
        (
            True,
            "Template Individual URIRef Encoded",
            "https://example.com/%7BRICO_AUTHTP_CLASS%7D",
            Literal("https://example.com/{RICO_AUTHTP_CLASS}"),
            False,
        ),
        # Not encoded should not get here - dealt with upstream
        # at metacharacter replacements; so not testing it
        # (
        #     True,
        #     "Template Individual URIRef Not Encoded",
        #     "https://example.com/{RICO_AUTHTP_CLASS}",
        #     Literal("https://example.com/{RICO_AUTHTP_CLASS}"),
        #     False,
        # ),
        (
            True,
            "Curie Individual",
            "rdfs:Class",
            URIRef("http://www.w3.org/2000/01/rdf-schema#Class"),
            False,
        ),
        (
            True,
            "Abs IRI Individual",
            "http://example.com/exampleClass",
            URIRef("http://example.com/exampleClass"),
            False,
        ),
        (
            True,
            "Rel IRI Individual",
            "/someClass",
            # Note double slash - prefix IRI defined below with a trailing slash
            URIRef("http://example.com//someClass"),
            False,
        ),
        (True, "Nefarious Individual", "Unexpected Literal As Type", None, True),
    ],
)
def test_parse_drawio_type_values(
    tmp_path: Path,
    rml_enabled,
    individual_label,
    type_value,
    expected_type_term,
    expect_exception,
):
    """Verify parser handles valid types correctly and raises for literal types."""
    xml_payload = dedent(f"""
        <mxfile>
          <diagram id="template" name="template">
            <mxGraphModel>
              <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
                <mxCell id="parent" value="{individual_label}" style="swimlane;fontStyle=0;html=1;" parent="1" vertex="1">
                  <mxGeometry x="0" y="0" width="160" height="60" as="geometry"/>
                </mxCell>
                <mxCell id="child" value="{type_value}" style="text;html=1;" parent="parent" vertex="1">
                  <mxGeometry x="0" y="0" width="120" height="30" as="geometry"/>
                </mxCell>
              </root>
            </mxGraphModel>
          </diagram>
        </mxfile>
    """).strip()

    fixture_path = tmp_path / "tmp_fixture.drawio"
    fixture_path.write_text(xml_payload, encoding="utf-8")

    parser_args = dict(
        drawio_file_path=str(fixture_path),
        metacharacter_substitute=["remove"],
        prefix="ex",
        prefix_iri="http://example.com/",
        rml_enabled=rml_enabled,
        include_label=False,
    )

    if expect_exception:
        with pytest.raises(
            draw_io_parser.pipeline.core.rdf.data.UnableToCoerceException
        ):
            draw_io_parser.parse_drawio_to_graph(**parser_args)
    else:
        graph = draw_io_parser.parse_drawio_to_graph(**parser_args)
        rr = Namespace("http://www.w3.org/ns/r2rml#")
        expected_triples_any_of = (
            [
                (None, rr.constant, expected_type_term),
                (None, rr.template, expected_type_term),
            ]
            if rml_enabled
            else [
                (None, RDF.type, expected_type_term),
            ]
        )
        triples = []
        for triple_pattern in expected_triples_any_of:
            triples.extend(graph.triples(triple_pattern))
        assert len(triples) == 1, (
            f"Expected 1 triple with any of {[p for _, p, _ in expected_triples_any_of]} as predicate, but found {len(triples)}: {triples}"
        )

