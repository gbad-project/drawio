from __future__ import annotations

from pathlib import Path
import sys
from urllib.parse import unquote

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import draw_io_parser  # type: ignore=import-not-found  # noqa: E402
from draw_io_parser import pipeline  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(FIXTURES_DIR.glob("*.drawio")),
)
def test_all_cells_reflected_in_graph(fixture_path: Path) -> None:
    try:
        graph = draw_io_parser.parse_drawio_to_graph(
            str(fixture_path),
            metacharacter_substitute=["url"],
        )
    except draw_io_parser.NotInKnownException as exc:  # type: ignore[attr-defined]
        pytest.skip(f"parser rejected fixture: {exc}")

    raw_xml = fixture_path.read_text(encoding="utf-8")
    metadata_prefixes, base_uri, _, parsed_root = (
        pipeline.pre.xml.metadata._extract_drawio_metadata(raw_xml)
    )
    working_xml = pipeline.pre.xml.metadata._strip_metadata_user_object(
        raw_xml, parsed_root
    )

    prefixes = draw_io_parser.get_prefixes()
    prefixes.update(metadata_prefixes)

    tree = draw_io_parser.DrawIOXMLTree(working_xml, prefixes)
    classifier = pipeline.core.xml.data.DrawIOCellClassifier(tree, prefixes)

    predicate_uris = {pred for pred in graph.predicates() if isinstance(pred, URIRef)}
    type_uris = {
        obj for obj in graph.objects(predicate=RDF.type) if isinstance(obj, URIRef)
    }

    base_candidates = set()
    if base_uri:
        base_candidates.add(base_uri)
        base_candidates.add(base_uri.split("://", 1)[-1])
    uri_names: set[str] = set()
    for node in set(graph.subjects()) | set(graph.objects()):
        if isinstance(node, URIRef):
            segment = str(node)
            if "#" in segment:
                segment = segment.rsplit("#", 1)[-1]
            else:
                segment = segment.rstrip("/").rsplit("/", 1)[-1]
            uri_names.add(unquote(segment))
            for candidate in base_candidates:
                if segment.startswith(candidate):
                    remainder = segment[len(candidate) :]
                    if remainder:
                        uri_names.add(unquote(remainder))

    unresolved: list[tuple[str | None, str, str]] = []

    for cell in tree.draw_io_xml_tree[0][0][0]:
        try:
            raw_value = tree._value_of(cell)
        except draw_io_parser._NoValueException:
            continue
        value = raw_value.strip()
        if not value:
            continue

        classification = classifier.classify(cell, raw_value)
        kind = getattr(classification.kind, "name", "")

        if kind == "ARROW_LABEL":
            if ":" not in value:
                unresolved.append((cell.attrib.get("id"), value, "arrow label"))
                continue
            prefix, reference = value.split(":", 1)
            base = prefixes.get(prefix)
            if not base:
                unresolved.append((cell.attrib.get("id"), value, "arrow prefix"))
                continue
            predicate_uri = URIRef(f"{base}{reference}")
            if predicate_uri not in predicate_uris:
                unresolved.append((cell.attrib.get("id"), value, "missing predicate"))
            continue

        if kind in {"TYPED_INDIVIDUAL", "STANDALONE_INDIVIDUAL"}:
            missing_reference = False
            for token in classification.tokens:
                if ":" not in token:
                    missing_reference = True
                    break
                prefix, reference = token.split(":", 1)
                base = prefixes.get(prefix)
                if not base:
                    missing_reference = True
                    break
                candidate = URIRef(f"{base}{reference}")
                if (
                    candidate not in type_uris
                    and candidate not in predicate_uris
                    and candidate not in graph.objects()
                ):
                    missing_reference = True
                    break
            if missing_reference:
                unresolved.append((cell.attrib.get("id"), value, "reference"))
            continue

        if any(
            value in str(obj) for obj in graph.objects() if isinstance(obj, Literal)
        ):
            continue
        if value in uri_names:
            continue
        unresolved.append((cell.attrib.get("id"), value, "literal"))

    assert not unresolved, (
        f"Unreflected mxCell values for {fixture_path.name}: {unresolved[:5]}"
    )
