from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from rdflib import Namespace, URIRef
from rdflib.namespace import OWL, RDF, SKOS

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import draw_io_parser  # noqa: E402


def _config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "infer_type_of_literals": True,
        "include_preamble": True,
        "ontology_iri": "https://example.org/ontology",
        "prefix": None,
        "prefix_iri": "https://example.org/ontology#",
        "indentation": draw_io_parser.DEFAULT_INDENTATION,
        "include_label": True,
        "max_gap": draw_io_parser.DEFAULT_MAX_GAP,
        "strict_mode": False,
        "metacharacter_substitute": ["remove"],
        "capitalisation_scheme": draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
    }
    config.update(overrides)
    return config


_VALID_XML = textwrap.dedent(
    """
    <mxfile>
      <diagram id="diagram">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="typedParent" value="Individual One" style="rounded=0" vertex="1" parent="1">
              <mxGeometry x="20" y="20" width="120" height="60" as="geometry" />
            </mxCell>
            <mxCell id="typedType" value="rico:Record" style="rounded=0" vertex="1" parent="typedParent">
              <mxGeometry x="20" y="20" width="120" height="60" as="geometry" />
            </mxCell>
            <mxCell id="curieNode" value="ex:Standalone" style="rounded=0" vertex="1" parent="1">
              <mxGeometry x="220" y="20" width="120" height="60" as="geometry" />
            </mxCell>
            <mxCell id="uriNode" value="https://example.org/resource" style="rounded=0" vertex="1" parent="1">
              <mxGeometry x="420" y="20" width="160" height="60" as="geometry" />
            </mxCell>
            <mxCell id="literalNode" value="Connected literal" style="rounded=1" vertex="1" parent="1">
              <mxGeometry x="20" y="140" width="160" height="60" as="geometry" />
            </mxCell>
            <mxCell id="decorationNode" value="Decoration note" style="rounded=1" vertex="1" parent="1">
              <mxGeometry x="220" y="140" width="160" height="60" as="geometry" />
            </mxCell>
            <mxCell id="arrowDatatype" edge="1" parent="1" source="typedParent" target="literalNode" value="">
              <mxGeometry relative="1" as="geometry">
                <mxPoint x="80" y="80" as="sourcePoint" />
                <mxPoint x="80" y="160" as="targetPoint" />
              </mxGeometry>
            </mxCell>
            <mxCell id="arrowDatatypeLabel" value="rico:hasLiteral" style="edgeLabel" vertex="1" connectable="0" parent="arrowDatatype">
              <mxGeometry relative="1" as="geometry" />
            </mxCell>
            <mxCell id="arrowObject" edge="1" parent="1" source="curieNode" target="uriNode" value="">
              <mxGeometry relative="1" as="geometry">
                <mxPoint x="280" y="20" as="sourcePoint" />
                <mxPoint x="520" y="20" as="targetPoint" />
              </mxGeometry>
            </mxCell>
            <mxCell id="arrowObjectLabel" value="rico:hasPart" style="edgeLabel" vertex="1" connectable="0" parent="arrowObject">
              <mxGeometry relative="1" as="geometry" />
            </mxCell>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>
    """
)


_ERROR_XML = textwrap.dedent(
    """
    <mxfile>
      <diagram id="diagram">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="literalSource" value="Literal source" style="rounded=1" vertex="1" parent="1">
              <mxGeometry x="20" y="20" width="160" height="60" as="geometry" />
            </mxCell>
            <mxCell id="targetParent" value="Target Node" style="rounded=0" vertex="1" parent="1">
              <mxGeometry x="220" y="20" width="160" height="60" as="geometry" />
            </mxCell>
            <mxCell id="targetType" value="rico:Record" style="rounded=0" vertex="1" parent="targetParent">
              <mxGeometry x="220" y="20" width="160" height="60" as="geometry" />
            </mxCell>
            <mxCell id="badArrow" edge="1" parent="1" source="literalSource" target="targetParent" value="">
              <mxGeometry relative="1" as="geometry">
                <mxPoint x="60" y="40" as="sourcePoint" />
                <mxPoint x="260" y="40" as="targetPoint" />
              </mxGeometry>
            </mxCell>
            <mxCell id="badArrowLabel" value="rico:hasPart" style="edgeLabel" vertex="1" connectable="0" parent="badArrow">
              <mxGeometry relative="1" as="geometry" />
            </mxCell>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>
    """
)


@pytest.fixture()
def _patch_prefixes(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/ns/"

    def _patched() -> dict[str, str]:
        return prefixes.copy()

    monkeypatch.setattr(draw_io_parser, "get_prefixes", _patched)
    return prefixes


def test_node_classifier_handles_varied_nodes(_patch_prefixes: dict[str, str]) -> None:
    graph = draw_io_parser._build_graph_from_raw_xml(_VALID_XML, _config())

    prefixes = _patch_prefixes
    rico = Namespace(prefixes["rico"])

    typed_subjects = {
        subject
        for subject in graph.subjects(RDF.type, rico.Record)
        if isinstance(subject, URIRef)
    }
    assert any(str(subject).endswith("IndividualOne") for subject in typed_subjects)

    has_literal = rico.hasLiteral
    typed_uri = next(iter(typed_subjects))
    literal_values = {str(obj) for obj in graph.objects(typed_uri, has_literal)}
    assert "Connected literal" in literal_values

    has_part = rico.hasPart
    resource_uri = URIRef("https://example.org/resource")
    assert any(
        subject == URIRef("https://example.org/ontology#exStandalone")
        for subject in graph.subjects(has_part, resource_uri)
    )

    assert (
        URIRef("https://example.org/ontology#exStandalone"),
        RDF.type,
        OWL.NamedIndividual,
    ) in graph
    assert (
        URIRef("https://example.org/resource"),
        RDF.type,
        OWL.NamedIndividual,
    ) in graph

    notes = {
        str(obj)
        for obj in graph.objects(URIRef("https://example.org/ontology"), SKOS.note)
    }
    assert "Decoration note" in notes
    assert "Connected literal" not in notes


def test_literal_source_arrow_is_rejected(_patch_prefixes: dict[str, str]) -> None:
    with pytest.raises(draw_io_parser.ArrowWithoutIndividualAsSourceException):
        draw_io_parser._build_graph_from_raw_xml(_ERROR_XML, _config())
