from __future__ import annotations

from typing import Optional

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="pre", type="xml", role="metadata")
def _extract_drawio_metadata(
    raw_xml: str,
) -> tuple[dict[str, str], Optional[str], Optional[str], Optional[Element]]:
    """Extract CSV path, base URI, prefixes, and return the parsed XML root."""
    try:
        root = fromstring(raw_xml)
    except Exception:  # pragma: no cover - defensive guard around XML parsing
        return {}, None, None, None

    metadata_node = root.find(".//mxGraphModel/root/gbadMetadata[@id='0']")
    if metadata_node is None:
        metadata_node = root.find(".//mxGraphModel/root/gbadMetadata")
    if metadata_node is None:
        metadata_node = root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if metadata_node is None:
        metadata_node = root.find(".//mxGraphModel/root/UserObject")
    if metadata_node is None:
        metadata_node = root.find(".//mxGraphModel/root/object[@id='0']")

    if metadata_node is None:
        graph_root = root.find(".//mxGraphModel/root")
        if graph_root is not None:
            for candidate in list(graph_root):
                tag_lower = candidate.tag.lower()
                if tag_lower not in {"gbadmetadata", "userobject", "object"}:
                    continue
                has_metadata_payload = bool(
                    candidate.attrib.get("csvPath")
                    or candidate.attrib.get("baseUri")
                    or any(
                        child.tag
                        in {"userObjectPreambleElement", "UserObjectPreambleElement"}
                        for child in list(candidate)
                    )
                )
                if has_metadata_payload:
                    metadata_node = candidate
                    break

    if metadata_node is None:
        return {}, None, None, root

    csv_path = (metadata_node.attrib.get("csvPath") or "").strip() or None
    base_uri = (metadata_node.attrib.get("baseUri") or "").strip() or None

    prefixes: dict[str, str] = {}
    for tag in ("userObjectPreambleElement", "UserObjectPreambleElement"):
        for preamble in metadata_node.findall(tag):
            prefix = (preamble.attrib.get("rdfPrefix") or "").strip()
            iri = (preamble.attrib.get("rdfIRI") or "").strip()
            if prefix and iri:
                prefixes[prefix] = iri

    return prefixes, base_uri, csv_path, root
