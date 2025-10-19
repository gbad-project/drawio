from __future__ import annotations

from typing import Any, Optional

from legacy.draw_io_parser import *  # noqa: F401,F403,F405
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F401, F403, F405


@override(phase="core", type="rdf", role="control")
class DrawIOParserGraph(Graph):
    """Graph subclass that exposes DrawIO and RML metadata."""

    def __init__(
        self,
        *args: Any,
        csv_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.csv_path = csv_path
        self.rml_enabled: bool = False
        self.rml_graph: Graph | None = None
        self.rml_triple_count: int = 0
        self.rml_serialization: str | None = None
        self.rml_metadata: dict[str, Any] = {}
