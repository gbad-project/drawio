from __future__ import annotations

from pathlib import Path
import sys
from textwrap import dedent

import pytest
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, OWL

LEGACY_DIR = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = LEGACY_DIR.parent
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import draw_io_parser  # noqa: E402
import original.draw_io_parser as original_draw_io_parser  # noqa: E402

DrawIOCellClassifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier
DECORATION_REGISTRY_ATTR = getattr(
    DrawIOCellClassifier, "DECORATION_REGISTRY_ATTR", "__drawio_literal_registry"
)
DEFAULT_STANDALONE_TYPE = getattr(
    DrawIOCellClassifier, "DEFAULT_STANDALONE_TYPE", "owl:NamedIndividual"
)

FIXTURES_DIR = PACKAGE_ROOT / "tests" / "fixtures"


def _vertex_cell(
    cell_id: str,
    value: str,
    *,
    parent: str = "1",
    style: str = "text",
    geometry: dict[str, float | int] | None = None,
) -> str:
    geometry = geometry or {"x": 0, "y": 0, "width": 80, "height": 30}
    geometry_attrs = " ".join(f"{key}='{value}'" for key, value in geometry.items())
    return dedent(
        f"""
        <mxCell id='{cell_id}' value='{value}' style='{style}' parent='{parent}' vertex='1'>
          <mxGeometry {geometry_attrs} as='geometry'/>
        </mxCell>
        """
    ).strip()


def _edge_cell(
    cell_id: str,
    value: str,
    *,
    source: str,
    target: str,
    parent: str = "1",
) -> str:
    return dedent(
        f"""
        <mxCell id='{cell_id}' value='{value}' style='endArrow=classic;html=1;' parent='{parent}' source='{source}' target='{target}' edge='1'>
          <mxGeometry relative='1' as='geometry'>
            <mxPoint x='0' y='0' as='sourcePoint'/>
            <mxPoint x='0' y='0' as='targetPoint'/>
          </mxGeometry>
        </mxCell>
        """
    ).strip()


def _edge_label(cell_id: str, *, parent: str, value: str) -> str:
    return dedent(
        f"""
        <mxCell id='{cell_id}' value='{value}' style='edgeLabel;html=1;' parent='{parent}' vertex='1'>
          <mxGeometry x='0' y='0' width='0' height='0' as='geometry'/>
        </mxCell>
        """
    ).strip()


def _edge_label_without_edge_style(cell_id: str, *, parent: str, value: str) -> str:
    return dedent(
        f"""
        <mxCell id='{cell_id}' value='{value}' style='text;html=1;resizable=0;points=[];align=center;verticalAlign=middle;labelBackgroundColor=none;rounded=0;shadow=0;strokeWidth=1;fontSize=12;' parent='{parent}' vertex='1' connectable='0'>
          <mxGeometry x='0.5' y='0.5' relative='1' as='geometry'>
            <mxPoint x='-20' y='16' as='offset'/>
          </mxGeometry>
        </mxCell>
        """
    ).strip()


def _drawio_xml(*cells: str) -> str:
    body = "\n        ".join(cells)
    return dedent(
        f"""
        <mxfile>
          <diagram id='classifier' name='classifier'>
            <mxGraphModel>
              <root>
                <mxCell id='0'/>
                <mxCell id='1' parent='0'/>
                {body}
              </root>
            </mxGraphModel>
          </diagram>
        </mxfile>
        """
    ).strip()


@pytest.fixture(autouse=True)
def _clear_literal_registry():
    attr = DECORATION_REGISTRY_ATTR
    if hasattr(draw_io_parser.pipeline.core.internal.data, attr):
        delattr(draw_io_parser.pipeline.core.internal.data, attr)
    yield
    if hasattr(draw_io_parser.pipeline.core.internal.data, attr):
        delattr(draw_io_parser.pipeline.core.internal.data, attr)


def test_classifier_detects_typed_individuals_and_literals():
    xml = _drawio_xml(
        _vertex_cell("parent", "My Individual", style="rounded=1"),
        _vertex_cell("type", "owl:NamedIndividual", parent="parent"),
        _vertex_cell("decor", "Decoration literal"),
    )

    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        xml,
        draw_io_parser.get_prefixes(),
    )

    observed = {
        (individual.identifier, individual.ric_class)
        for individual in classifier.individuals
    }
    assert ("My Individual", "owl:NamedIndividual") in observed

    registry = getattr(
        draw_io_parser.pipeline.core.internal.data,
        classifier.DECORATION_REGISTRY_ATTR,
        {},
    )
    assert registry["decor"]["value"] == "Decoration literal"
    assert registry["decor"]["connected"] is False


def test_classifier_accepts_template_class_tokens():
    xml = _drawio_xml(
        _vertex_cell("parent", "Authority", style="swimlane"),
        _vertex_cell("type", "{RICO_AUTHTP_CLASS}", parent="parent"),
    )

    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        xml,
        draw_io_parser.get_prefixes(),
    )

    observed = {
        individual.ric_class
        for individual in classifier.individuals
        if individual.identifier == "Authority"
    }

    assert "{RICO_AUTHTP_CLASS}" in observed


def test_top_level_rounded_text_treated_as_literal():
    xml = _drawio_xml(
        _vertex_cell(
            "literal",
            "Custom:Value",
            style="text;rounded=1;whiteSpace=wrap;html=1;",
        )
    )

    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        xml,
        draw_io_parser.get_prefixes(),
    )

    literal_ids = set(classifier._literals_by_id.keys())
    assert "literal" in literal_ids

    registry = getattr(
        draw_io_parser.pipeline.core.internal.data,
        classifier.DECORATION_REGISTRY_ATTR,
        {},
    )
    assert registry["literal"]["value"] == "Custom:Value"
    assert registry["literal"]["connected"] is False


def test_classifier_parent_cell_collects_child_type_tokens():
    xml = _drawio_xml(
        _vertex_cell("parent", "List pnnpni", style="swimlane"),
        _vertex_cell("type1", "owl:NamedIndividual", parent="parent"),
        _vertex_cell("type2", "rdf:Resource", parent="parent"),
    )

    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        xml,
        draw_io_parser.get_prefixes(),
    )

    observed = {
        individual.ric_class
        for individual in classifier.individuals
        if individual.identifier == "List pnnpni"
    }

    assert observed == {"owl:NamedIndividual", "rdf:Resource"}


def test_classifier_standalone_curie_node_creates_individual_without_parent():
    xml = _drawio_xml(_vertex_cell("solo", "owl:NamedIndividual"))

    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        xml,
        draw_io_parser.get_prefixes(),
    )

    observed = {
        (individual.identifier, individual.ric_class)
        for individual in classifier.individuals
    }
    assert ("owl:NamedIndividual", "owl:NamedIndividual") in observed


def test_absolute_uri_node_uses_default_type_with_classifier():
    uri_value = "http://example.com/resources/A"
    xml = _drawio_xml(_vertex_cell("abs", uri_value))
    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        xml, draw_io_parser.pipeline.pre.internal.metadata.get_prefixes()
    )
    observed = {(ind.identifier, ind.ric_class) for ind in classifier.individuals}
    assert (uri_value, classifier.DEFAULT_STANDALONE_TYPE) in observed


def test_decorations_serialise_to_skos_note(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("parent", "Subject"),
        _vertex_cell("type", "owl:NamedIndividual", parent="parent"),
        _vertex_cell("decor", "Loose literal"),
    )
    path = tmp_path / "decorations.drawio"
    path.write_text(xml, encoding="utf-8")

    graph = draw_io_parser.parse_drawio_to_graph(
        str(path),
        ontology_iri="ontology://test",  # ensure deterministic attachment
        metacharacter_substitute=["remove"],
    )

    notes = list(graph.objects(URIRef("ontology://test"), SKOS.note))
    assert Literal("Loose literal") in notes


def test_connected_literal_not_treated_as_decoration(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("parent", "Node A"),
        _vertex_cell("type", "owl:NamedIndividual", parent="parent"),
        _vertex_cell("literal", "Some literal"),
        _edge_cell("arrow", "", source="parent", target="literal"),
        _edge_label("label", parent="arrow", value="rdfs:label"),
    )
    path = tmp_path / "connected.drawio"
    path.write_text(xml, encoding="utf-8")

    graph = draw_io_parser.parse_drawio_to_graph(
        str(path),
        ontology_iri="ontology://connected",
        metacharacter_substitute=["remove"],
    )

    assert not list(graph.triples((None, SKOS.note, Literal("Some literal"))))

    labels = list(graph.triples((None, RDFS.label, Literal("Node A"))))
    assert labels  # the individual should still exist
    literal_triples = list(graph.triples((None, RDFS.label, Literal("Some literal"))))
    assert literal_triples


def test_literal_as_arrow_source_raises(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("parent", "Node"),
        _vertex_cell("type", "owl:NamedIndividual", parent="parent"),
        _vertex_cell("literal", "Literal source"),
        _edge_cell("arrow", "", source="literal", target="parent"),
        _edge_label("label", parent="arrow", value="rdfs:label"),
    )
    path = tmp_path / "invalid.drawio"
    path.write_text(xml, encoding="utf-8")

    with pytest.raises(draw_io_parser.ArrowWithoutIndividualAsSourceException):
        draw_io_parser.parse_drawio_to_graph(str(path))


def test_arrow_label_without_edge_style_is_not_individual(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("source", "Source"),
        _vertex_cell("source_type", "rico:Record", parent="source"),
        _vertex_cell("literal", "Address"),
        _edge_cell("arrow", "", source="source", target="literal"),
        _edge_label_without_edge_style("label", parent="arrow", value="rdfs:mock"),
    )
    path = tmp_path / "class-diagram-property.drawio"
    path.write_text(xml, encoding="utf-8")

    graph = draw_io_parser.parse_drawio_to_graph(
        str(path),
        ontology_iri="ontology://test",
        prefix="mock",
        prefix_iri="http://example.com/mock#",
        metacharacter_substitute=["remove"],
    )

    property_uri = URIRef("http://www.w3.org/2000/01/rdf-schema#mock")
    assert not list(graph.triples((property_uri, RDF.type, OWL.NamedIndividual)))
    assert list(graph.triples((property_uri, RDF.type, OWL.DatatypeProperty)))


def test_blank_node_used_for_decorations_without_ontology(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("parent", "Subject"),
        _vertex_cell("type", "owl:NamedIndividual", parent="parent"),
        _vertex_cell("decor", "Detached"),
    )
    path = tmp_path / "blank.drawio"
    path.write_text(xml, encoding="utf-8")

    graph = draw_io_parser.parse_drawio_to_graph(
        str(path), metacharacter_substitute=["remove"]
    )

    triples = list(graph.triples((None, SKOS.note, Literal("Detached"))))
    assert triples
    for subject, _, _ in triples:
        assert isinstance(subject, (BNode, URIRef))
        break


def _arrow_signature(arrow: object) -> tuple[str, str, str, bool]:
    return (
        arrow.identifier,
        arrow.source,
        arrow.target,
        bool(getattr(arrow, "is_datatype", False)),
    )


@pytest.mark.parametrize(
    "fixture_name",
    [
        "knut_olborgs_forskningsnotater.drawio",
        "RG 18-210 Walkerton Inquiry in RiC-O (original).drawio",
    ],
)
def test_classifier_arrows_align_with_legacy_parser(fixture_name: str):
    xml_path = FIXTURES_DIR / fixture_name
    raw_xml = xml_path.read_text(encoding="utf-8")
    prefixes = draw_io_parser.get_prefixes()

    classifier = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier(
        raw_xml,
        prefixes,
        strict_mode=False,
        max_gap=draw_io_parser.DEFAULT_MAX_GAP,
    )
    patched_arrows = {_arrow_signature(arrow) for arrow in classifier.arrows}

    legacy_tree = original_draw_io_parser.DrawIOXMLTree(raw_xml, prefixes)
    legacy_arrows = {
        _arrow_signature(arrow)
        for arrow in legacy_tree.individuals_and_arrows(
            False, draw_io_parser.DEFAULT_MAX_GAP
        )
        if isinstance(arrow, original_draw_io_parser.Arrow)
    }

    assert patched_arrows == legacy_arrows


def test_classifier_strict_mode_raises_for_invalid_arrows():
    xml_path = FIXTURES_DIR / "RG 18-210 Walkerton Inquiry in RiC-O (original).drawio"
    raw_xml = xml_path.read_text(encoding="utf-8")
    prefixes = draw_io_parser.get_prefixes()

    with pytest.raises(
        (
            draw_io_parser.NoSourceException,
            draw_io_parser.NoTargetException,
            draw_io_parser.ArrowWithoutIndividualAsSourceException,
        )
    ):
        DrawIOCellClassifier(raw_xml, prefixes, strict_mode=True)
