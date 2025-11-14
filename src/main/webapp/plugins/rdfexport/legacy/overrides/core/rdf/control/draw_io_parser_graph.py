from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

from rdflib.term import Node

# ruff: noqa: F403, F405


@override(phase="core", type="rdf", role="control")
class DrawIOParserGraph(Graph):
    """Graph subclass that records Draw.io specific metadata."""

    def __init__(
        self,
        *args,
        csv_path: Optional[str] = None,
        metacharacter_mode: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.csv_path = csv_path
        self.metacharacter_mode = metacharacter_mode

    def addN1(
        self,
        triple_1: tuple[Node, Node, Node],
        triples_N: list[tuple[Node, Node, Node]],
    ):
        """
        Add N+1: a triple and some other triples to the graph.

        Useful for cases like RR predicate-object map.
        """
        self.add(triple_1)
        self.addN((s, p, o, self) for s, p, o in triples_N)
