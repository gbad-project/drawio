from __future__ import annotations

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="pre", type="internal", role="metadata")
@dataclass(frozen=True)
class SerialisationConfig:
    """
    Holds various user-configurable parameters for configuring the serialisation
    to OWL outputted by the 'serialise' function
    """

    infer_type_of_literals: bool
    include_preamble: bool
    ontology_iri: str | None
    prefix: str | None
    prefix_iri: str | None
    indentation: int
    include_label: bool
    mint_from_literals: bool = True
    mint_from_types: bool = False
    mint_from_arrows: bool = True
