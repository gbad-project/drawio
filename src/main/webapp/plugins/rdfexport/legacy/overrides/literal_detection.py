from __future__ import annotations

from xml.etree.ElementTree import Element

from meta_builder.drawio_meta_builder import override


@override(phase="core", type="xml", role="data")
def _is_possible_literal(cell: Element) -> bool:
    """Heuristically flag top-level text decorations as literals."""
    parent = cell.attrib.get("parent")
    if parent != "1":
        return False

    style = cell.attrib.get("style", "")
    if "rounded=1" in style:
        return True

    style_lower = style.lower()
    decoration_tokens = (
        "text;",
        "shape=text",
        "shape=mxgraph.basic.text",
    )
    return any(token in style_lower for token in decoration_tokens)
