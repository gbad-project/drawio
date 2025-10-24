from __future__ import annotations

from typing import Optional

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="pre", type="xml", role="metadata")
class MetadataNodeNotFoundError(Exception):
    """Raised when no metadata node is found in the provided Draw.io XML."""


@override(phase="pre", type="xml", role="metadata")
def _find_metadata_node(raw_xml: str) -> tuple[Element, Element]:
    """Find and return the metadata node and root element from a Draw.io XML document.

    Args:
        raw_xml (str): The raw XML string representing the Draw.io diagram.

    Returns:
        tuple[Element, Element]: A tuple containing:
            - The metadata node element found.
            - The root XML element parsed from the document.

    Raises:
        MetadataNodeNotFoundError: If no metadata node is found within the provided XML.
    """
    MetadataNodeNotFoundError = pipeline.pre.xml.metadata.MetadataNodeNotFoundError

    root = fromstring(raw_xml)
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
                    return metadata_node, root
        raise MetadataNodeNotFoundError("No metadata node found in this raw XML")

    return metadata_node, root


@override(phase="pre", type="xml", role="metadata")
def _extract_drawio_metadata(
    raw_xml: str,
) -> tuple[dict[str, str], Optional[str], Optional[str], Optional[Element]]:
    """Extract CSV path, base URI, prefixes, and return the parsed XML root."""
    try:
        metadata_node, root = pipeline.pre.xml.metadata._find_metadata_node(raw_xml)
    except Exception:  # pragma: no cover - defensive guard around XML parsing
        return {}, None, None, None

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
