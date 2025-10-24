from __future__ import annotations

from typing import Optional

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="pre", type="xml", role="metadata")
def _strip_metadata_user_object(raw_xml: str, root: Optional[Element]) -> str:
    if root is None:
        return raw_xml

    working_root = deepcopy(root)
    graph_root = working_root.find(".//mxGraphModel/root")
    if graph_root is None:
        return raw_xml

    metadata_node: Optional[Element] = None
    for tag in ("gbadMetadata", "UserObject", "object"):
        metadata_node = graph_root.find(f"{tag}[@id='0']")
        if metadata_node is not None:
            break
        metadata_node = graph_root.find(tag)
        if metadata_node is not None:
            break

    if metadata_node is None:
        return raw_xml

    replacement = Element("mxCell", {"id": "0"})
    children = list(graph_root)
    for index, child in enumerate(children):
        if child is metadata_node:
            graph_root.remove(metadata_node)
            graph_root.insert(index, replacement)
            break

    return tostring(working_root, encoding="unicode")
