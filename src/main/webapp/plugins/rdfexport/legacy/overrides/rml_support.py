from __future__ import annotations

from typing import Any

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="rdf", role="control")
def maybe_enable_rml(
    graph: DrawIOParserGraph,
    config_args: dict[str, Any],
    parsed_root: Element | None,
) -> DrawIOParserGraph:
    """Toggle RML enhancements on the generated graph when requested."""

    def _is_flag_enabled(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)

    metadata_flag = False
    if parsed_root is not None:
        user_object = parsed_root.find(".//UserObject[@id='0']")
        if user_object is not None:
            metadata_flag = _is_flag_enabled(user_object.attrib.get("rmlEnabled"))

    rml_enabled = _is_flag_enabled(config_args.get("rml_enabled")) or metadata_flag
    if not rml_enabled:
        return graph

    rr = Namespace("http://www.w3.org/ns/r2rml#")
    graph.namespace_manager.bind("rr", rr, replace=False)
    graph.add((BNode(), RDF.type, rr.TriplesMap))
    return graph
