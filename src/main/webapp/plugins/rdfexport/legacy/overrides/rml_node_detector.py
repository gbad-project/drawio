"""Overrides for detecting DrawIO metadata relevant to RML exports."""

from __future__ import annotations

from typing import Dict, Optional, Tuple
from xml.etree.ElementTree import Element, fromstring

from meta_builder.drawio_meta_builder import override


def _coerce_bool(value: Optional[str]) -> bool:
    if value is None:
        return False

    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False

    return bool(lowered)


@override(phase="pre", type="xml", role="metadata")
def _extract_drawio_metadata(
    raw_xml: str,
) -> Tuple[Dict[str, str], Optional[str], Optional[str], Optional[Element]]:
    """Extract metadata from the DrawIO document including the RML toggle."""
    try:
        root = fromstring(raw_xml)
    except Exception:  # pragma: no cover - guard around XML parsing
        return {}, None, None, None

    metadata_node = root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if metadata_node is None:
        setattr(root, "_rdfexport_metadata", {"rml_enabled": False})
        return {}, None, None, root

    csv_path_raw = metadata_node.attrib.get("csvPath", "")
    base_uri_raw = metadata_node.attrib.get("baseUri", "")
    rml_enabled_raw = metadata_node.attrib.get("rmlEnabled")

    csv_path = csv_path_raw.strip() or None
    base_uri = base_uri_raw.strip() or None
    rml_enabled = _coerce_bool(rml_enabled_raw)

    prefixes: Dict[str, str] = {}
    for preamble in metadata_node.findall("userObjectPreambleElement"):
        prefix = (preamble.attrib.get("rdfPrefix") or "").strip()
        iri = (preamble.attrib.get("rdfIRI") or "").strip()
        if prefix and iri:
            prefixes[prefix] = iri

    metadata = {
        "rml_enabled": rml_enabled,
        "csv_path": csv_path,
        "base_uri": base_uri,
    }
    setattr(root, "_rdfexport_metadata", metadata)

    return prefixes, base_uri, csv_path, root


__all__ = ["_extract_drawio_metadata"]
