from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import legacy.draw_io_parser as parser
from pyodide_pipeline.drawio_pipeline import _default_parser_config


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"

EXPECTED_FAILURES: dict[str, type[Exception]] = {
    "AA37-with-metadata-severely-mocked": parser.rdf_data_core.NotInKnownException,
    "General_Authority_bleep_mock": parser.rdf_data_core.NotInKnownException,
}


def _expected_candidate_ids(raw_xml: str) -> set[str]:
    metadata_module = parser.pipeline.pre.xml.metadata  # type: ignore[attr-defined]
    _, _, _, parsed_root = metadata_module._extract_drawio_metadata(raw_xml)
    working_xml = metadata_module._strip_metadata_user_object(raw_xml, parsed_root)

    candidate_ids: set[str] = set()
    document = ET.fromstring(working_xml)
    for cell in document.findall(".//mxCell"):
        cell_id = cell.attrib.get("id")
        if not cell_id:
            continue
        if cell.attrib.get("edge") == "1":
            candidate_ids.add(cell_id)
            continue
        value = cell.attrib.get("value", "").strip()
        if value:
            candidate_ids.add(cell_id)
    return candidate_ids


@pytest.mark.parametrize(
    "fixture_path",
    sorted(FIXTURE_DIR.glob("*.drawio")),
    ids=lambda path: path.stem,
)
def test_all_mxcell_accounted_for(fixture_path: Path) -> None:
    xml = fixture_path.read_text(encoding="utf-8")
    failure_exc = EXPECTED_FAILURES.get(fixture_path.stem)
    if failure_exc is not None:
        with pytest.raises(failure_exc):
            parser._build_graph_from_raw_xml(xml, _default_parser_config())
        return

    config = _default_parser_config()
    graph = parser._build_graph_from_raw_xml(xml, config)

    processed = getattr(graph, "_drawio_processed_cells", set())
    candidate = getattr(graph, "_drawio_candidate_cells", set())

    assert candidate, "Expected candidate mxCell identifiers to be captured"
    assert processed == candidate

    expected = _expected_candidate_ids(xml)
    assert candidate == expected
