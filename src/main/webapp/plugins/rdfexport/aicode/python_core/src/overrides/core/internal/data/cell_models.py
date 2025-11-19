from __future__ import annotations

from enum import Enum, auto

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="core", type="internal", role="data")
class CellKind(Enum):
    ARROW = auto()
    ARROW_LABEL = auto()
    TYPED_INDIVIDUAL = auto()
    STANDALONE_INDIVIDUAL = auto()
    LITERAL = auto()
    DECORATION = auto()
    EMPTY_CELL = auto()


@override(phase="core", type="internal", role="data")
@dataclass(slots=True)
class CellClassification:
    kind: Enum
    raw_value: str
    cell: Element
    parent_cell: Optional[Element] = None
    parent_identifier: Optional[str] = None
    identifier: Optional[str] = None
    tokens: list[str] = field(default_factory=list)
    declares_identifier: bool = False
