from __future__ import annotations

from copy import deepcopy
from typing import Optional
from xml.etree.ElementTree import Element, fromstring, tostring

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="pre", type="xml", role="metadata")
def _extract_drawio_metadata(
    raw_xml: str,
) -> tuple[dict[str, str], Optional[str], Optional[str], Optional[Element]]:
    """Extract metadata preamble while tolerating legacy <object> wrappers."""

    try:
        root = fromstring(raw_xml)
    except Exception:  # pragma: no cover - defensive guard around XML parsing
        return {}, None, None, None

    metadata_nodes: list[Element] = []
    user_object = root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if user_object is not None:
        metadata_nodes.append(user_object)
    for candidate in root.findall(".//mxGraphModel/root/object"):
        if candidate.find("userObjectPreambleElement") is not None:
            metadata_nodes.append(candidate)

    if not metadata_nodes:
        return {}, None, None, root

    primary = metadata_nodes[0]
    csv_path = (primary.attrib.get("csvPath", "") or "").strip() or None
    base_uri = (primary.attrib.get("baseUri", "") or "").strip() or None

    prefixes: dict[str, str] = {}
    for node in metadata_nodes:
        for preamble in node.findall("userObjectPreambleElement"):
            prefix = (preamble.attrib.get("rdfPrefix") or "").strip()
            iri = (preamble.attrib.get("rdfIRI") or "").strip()
            if prefix and iri:
                prefixes[prefix] = iri

    return prefixes, base_uri, csv_path, root


@override(phase="pre", type="xml", role="metadata")
def _strip_metadata_user_object(raw_xml: str, root: Optional[Element]) -> str:
    """Remove metadata wrapper regardless of tag choice."""

    if root is None:
        return raw_xml

    working_root = deepcopy(root)
    graph_root = working_root.find(".//mxGraphModel/root")
    if graph_root is None:
        return raw_xml

    replacements: list[tuple[Element, Element]] = []
    for child in list(graph_root):
        if child.tag == "UserObject" and child.attrib.get("id") == "0":
            replacement_id = child.attrib.get("id", "0") or "0"
            replacements.append((child, Element("mxCell", {"id": replacement_id})))
        elif (
            child.tag.lower() == "object"
            and child.find("userObjectPreambleElement") is not None
        ):
            replacement_source = child.find("mxCell")
            if replacement_source is not None:
                replacement = deepcopy(replacement_source)
            else:
                replacement = Element("mxCell")
            if "id" not in replacement.attrib:
                replacement.attrib["id"] = child.attrib.get("id", "0") or "0"
            replacements.append((child, replacement))

    if not replacements:
        return raw_xml

    snapshot = list(graph_root)
    for original, replacement in replacements:
        if original not in snapshot:
            snapshot = list(graph_root)
        try:
            index = snapshot.index(original)
        except ValueError:
            continue
        graph_root.remove(original)
        graph_root.insert(index, replacement)

    return tostring(working_root, encoding="unicode")
