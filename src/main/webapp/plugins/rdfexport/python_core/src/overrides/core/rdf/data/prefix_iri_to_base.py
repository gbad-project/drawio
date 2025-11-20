from __future__ import annotations


from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="core", type="rdf", role="data")
def prefix_iri_to_base(prefix_iri: str) -> str:
    """
    This removes one char from established prefix_iri, thus
    making it a base IRI-looking string.
    """
    if not prefix_iri:
        return
    # Somehow rstip want a string, not a tuple
    return str(prefix_iri).rstrip("".join(("#", "/")))
