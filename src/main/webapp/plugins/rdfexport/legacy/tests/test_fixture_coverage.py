from __future__ import annotations

import html
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import pytest

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import draw_io_parser  # noqa: E402

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures"

_XFAIL_FIXTURES = {
    # Intentional malformed CURIE reference without a local part to ensure
    # error reporting stays wired. The parser rightfully raises
    # NotInKnownException, so treat this as an expected failure here.
    "AA37-with-metadata-severely-mocked.drawio": (
        "fixture contains 'picoL:' without a reference component"
    ),
    # This diagram exercises deliberately bogus prefixes (e.g. rr:constant
    # without a matching prefix declaration) to test debug tooling. Until the
    # parser grows bespoke fallbacks the coverage harness should not fail on it.
    "General_Authority_bleep_mock.drawio": (
        "fixture references prefixes that are intentionally undefined"
    ),
}


def _iter_fixture_params():
    fixtures = sorted(FIXTURES_ROOT.rglob("*.drawio"))
    params = []
    for fixture in fixtures:
        reason = _XFAIL_FIXTURES.get(fixture.name)
        if reason:
            params.append(
                pytest.param(
                    fixture,
                    id=fixture.name,
                    marks=pytest.mark.xfail(strict=True, reason=reason),
                )
            )
        else:
            params.append(pytest.param(fixture, id=fixture.name))
    return params


def _load_parser_settings(fixture_path: Path) -> tuple[list[str], bool | None]:
    raw = fixture_path.read_text(encoding="utf-8")
    root = ET.fromstring(raw)
    metadata = root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if metadata is None:
        return [], None

    settings_attr = metadata.attrib.get("rdfParserSettings")
    if not settings_attr:
        return [], None

    try:
        parsed = json.loads(html.unescape(settings_attr))
    except json.JSONDecodeError:
        return [], None

    settings = parsed.get("settings", {})
    strategy = settings.get("metacharacterStrategy")
    substitutes: list[str] = []
    if strategy in {"url", "remove"}:
        substitutes.append(strategy)

    for entry in settings.get("metacharacterEntries", []):
        if isinstance(entry, dict):
            character = entry.get("character")
            replacement = entry.get("replacement", "")
            if character:
                substitutes.append(f"{character}={replacement}")
        elif isinstance(entry, str):
            substitutes.append(entry)

    strip_html = settings.get("stripHTML")
    return substitutes, strip_html if strip_html is not None else None


@pytest.mark.parametrize("fixture_path", _iter_fixture_params())
def test_all_cells_accounted_for(fixture_path: Path) -> None:
    metacharacter_substitute, strip_html = _load_parser_settings(fixture_path)

    substitutes = list(dict.fromkeys(metacharacter_substitute or []))
    if "url" not in substitutes:
        substitutes.append("url")

    parse_kwargs = {"metacharacter_substitute": substitutes}
    if strip_html is not None:
        parse_kwargs["strip_html"] = strip_html

    graph = draw_io_parser.parse_drawio_to_graph(str(fixture_path), **parse_kwargs)
    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)

    raw_xml = fixture_path.read_text(encoding="utf-8")
    metadata_prefixes, _, _, parsed_root = draw_io_parser._extract_drawio_metadata(
        raw_xml
    )
    working_xml = draw_io_parser._strip_metadata_user_object(raw_xml, parsed_root)

    prefixes = {**draw_io_parser.get_prefixes(), **metadata_prefixes}
    xml_tree = draw_io_parser.DrawIOXMLTree(working_xml, prefixes)

    accounted_ids: set[str] = set()
    for cell, _, _ in xml_tree.individual_cells:
        cell_id = cell.attrib.get("id")
        if cell_id:
            accounted_ids.add(cell_id)
        parent_id = cell.attrib.get("parent")
        if parent_id:
            accounted_ids.add(parent_id)

    for cell, _ in xml_tree.literal_cells:
        cell_id = cell.attrib.get("id")
        if cell_id:
            accounted_ids.add(cell_id)
        parent_id = cell.attrib.get("parent")
        if parent_id:
            accounted_ids.add(parent_id)

    for arrow_cell, *_ in xml_tree.arrow_cells:
        for endpoint in (
            arrow_cell.attrib.get("source"),
            arrow_cell.attrib.get("target"),
        ):
            if endpoint:
                accounted_ids.add(endpoint)

    unaccounted: list[tuple[str | None, str]] = []
    for cell in xml_tree.draw_io_xml_tree[0][0][0]:
        if cell.tag != "mxCell":
            continue
        if cell.attrib.get("edge") == "1":
            continue
        style = cell.attrib.get("style", "")
        if "edgeLabel" in style:
            continue
        try:
            value = xml_tree._value_of(cell)
        except draw_io_parser._NoValueException:
            continue
        if not value:
            continue
        cell_id = cell.attrib.get("id")
        if cell_id not in accounted_ids:
            unaccounted.append((cell_id, value))

    assert not unaccounted, f"Unaccounted mxCells: {unaccounted}"
