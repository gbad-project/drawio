from __future__ import annotations

from pathlib import Path
import sys
from textwrap import dedent

import pytest
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

LEGACY_DIR = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = LEGACY_DIR.parent
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import draw_io_parser  # noqa: E402
from legacy.overrides import cell_classifier  # noqa: E402


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
    attr = cell_classifier.DECORATION_REGISTRY_ATTR
    if hasattr(draw_io_parser.pipeline.core.internal.data, attr):
        delattr(draw_io_parser.pipeline.core.internal.data, attr)
    yield
    if hasattr(draw_io_parser.pipeline.core.internal.data, attr):
        delattr(draw_io_parser.pipeline.core.internal.data, attr)


@pytest.fixture(autouse=True)
def _apply_drawio_overrides(monkeypatch):
    override_extract = (
        draw_io_parser.xml_data_core._extract_individual_and_arrow_and_literal_cells
    )
    override_literal = draw_io_parser.xml_data_core._cell_is_literal
    monkeypatch.setattr(
        draw_io_parser.DrawIOXMLTree,
        "_extract_individual_and_arrow_and_literal_cells",
        override_extract,
        raising=False,
    )
    monkeypatch.setattr(
        draw_io_parser.DrawIOXMLTree,
        "_cell_is_literal",
        override_literal,
        raising=False,
    )


def test_classifier_detects_typed_individuals_and_literals():
    xml = _drawio_xml(
        _vertex_cell("parent", "My Individual", style="rounded=1"),
        _vertex_cell("type", "rico:Thing", parent="parent"),
        _vertex_cell("decor", "Decoration literal"),
    )
    tree = draw_io_parser.DrawIOXMLTree(xml, draw_io_parser.get_prefixes())

    observed = {
        (individual.identifier, individual.ric_class)
        for _, individual, _ in tree.individual_cells
    }
    assert ("My Individual", "rico:Thing") in observed

    registry = getattr(
        draw_io_parser.pipeline.core.internal.data,
        cell_classifier.DECORATION_REGISTRY_ATTR,
        {},
    )
    assert registry["decor"]["value"] == "Decoration literal"
    assert registry["decor"]["connected"] is False


def test_standalone_curie_node_creates_individual_without_parent():
    xml = _drawio_xml(_vertex_cell("solo", "rico:Thing"))
    tree = draw_io_parser.DrawIOXMLTree(xml, draw_io_parser.get_prefixes())

    observed = {
        (individual.identifier, individual.ric_class)
        for _, individual, _ in tree.individual_cells
    }
    assert ("rico:Thing", "rico:Thing") in observed


def test_absolute_uri_node_uses_default_type():
    uri_value = "http://example.com/resources/A"
    xml = _drawio_xml(_vertex_cell("abs", uri_value))
    tree = draw_io_parser.DrawIOXMLTree(xml, draw_io_parser.get_prefixes())

    observed = {
        (individual.identifier, individual.ric_class)
        for _, individual, _ in tree.individual_cells
    }
    assert (uri_value, cell_classifier.DEFAULT_STANDALONE_TYPE) in observed


def test_decorations_serialise_to_skos_note(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("parent", "Subject"),
        _vertex_cell("type", "rico:Thing", parent="parent"),
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
        _vertex_cell("type", "rico:Thing", parent="parent"),
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
        _vertex_cell("type", "rico:Thing", parent="parent"),
        _vertex_cell("literal", "Literal source"),
        _edge_cell("arrow", "", source="literal", target="parent"),
        _edge_label("label", parent="arrow", value="rdfs:label"),
    )
    path = tmp_path / "invalid.drawio"
    path.write_text(xml, encoding="utf-8")

    with pytest.raises(draw_io_parser.ArrowWithoutIndividualAsSourceException):
        draw_io_parser.parse_drawio_to_graph(str(path))


def test_blank_node_used_for_decorations_without_ontology(tmp_path: Path):
    xml = _drawio_xml(
        _vertex_cell("parent", "Subject"),
        _vertex_cell("type", "rico:Thing", parent="parent"),
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
