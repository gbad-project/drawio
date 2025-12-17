from __future__ import annotations


from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="pre", type="xml", role="metadata")
def _flatten_object_wrappers(raw_xml: str, root: Optional[Element]) -> str:
    if root is None:
        return raw_xml

    working_root = deepcopy(root)
    graph_root = working_root.find(".//mxGraphModel/root")
    if graph_root is None:
        return raw_xml

    for obj in graph_root.findall(".//object"):
        mxcell = obj.find("mxCell")
        if mxcell is not None:
            # Transfer 'label' → 'value'
            if "label" in obj.attrib:
                mxcell.attrib["value"] = obj.attrib["label"]
            # Transfer 'id'
            if "id" in obj.attrib:
                mxcell.attrib["id"] = obj.attrib["id"]
            # Transfer any other attributes without overwriting existing mxCell attrs
            for key, value in obj.attrib.items():
                if key not in ("label", "id") and key not in mxcell.attrib:
                    mxcell.attrib[key] = value
            # Replace <object> with <mxCell>
            parent = graph_root
            for idx, child in enumerate(list(parent)):
                if child is obj:
                    parent.remove(obj)
                    parent.insert(idx, mxcell)
                    break

    return tostring(working_root, encoding="unicode")
