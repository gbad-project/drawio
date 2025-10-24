from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="pre", type="xml", role="metadata")
def _strip_metadata_user_object(raw_xml: str, root: Element | None) -> str:
    """Remove metadata wrapper regardless of tag choice."""

    if root is None:
        return raw_xml

    working_root = deepcopy(root)
    graph_root = working_root.find(".//mxGraphModel/root")
    if graph_root is None:
        return raw_xml

    replacements: list[tuple[Element, Element]] = []
    for child in list(graph_root):
        tag = (child.tag or "").lower()

        if tag == "userobject":
            if child.attrib.get("id") != "0":
                continue
            replacement_id = child.attrib.get("id", "0") or "0"
            replacements.append((child, Element("mxCell", {"id": replacement_id})))
            continue

        if tag == "gbadmetadata":
            replacement_id = child.attrib.get("id", "0") or "0"
            replacements.append((child, Element("mxCell", {"id": replacement_id})))
            continue

        if tag == "object":
            has_preamble = any(
                child.find(candidate) is not None
                for candidate in (
                    "userObjectPreambleElement",
                    "UserObjectPreambleElement",
                )
            )
            is_metadata_stub = has_preamble or child.attrib.get("id") == "0"
            if not is_metadata_stub:
                continue

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
