from __future__ import annotations

from io import StringIO

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

from rdflib.term import Node
from rdflib import Graph
from rdflib.parser import InputSource, create_input_source
from rdflib.plugins.parsers.notation3 import RDFSink, SinkParser

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

    @staticmethod
    def _extract_base_from_inputsource(source: InputSource):
        """
        Reuses some code from `TurtleParser.parse()`:
        https://rdflib.readthedocs.io/en/7.1.1/_modules/rdflib/plugins/parsers/notation3.html#TurtleParser

        The need for this function is dictated by the fact that
        rdflib seems NOT to read @base with `TurtleParser`
        into `base` property but rather resolves IRIs
        using base upon serialization. This leads to problems
        if graph is serialized and then parsed again repeatedly
        (i.e., `@base` is lost on repeat serialization).

        <https://stackoverflow.com/questions/43739259/how-do-i-get-the-base-uri-of-an-xml-file-using-rdflib>
        """
        graph = Graph()
        sink = RDFSink(graph)
        baseURI = graph.absolutize(source.getPublicId() or source.getSystemId() or "")
        p = SinkParser(
            sink,
            baseURI=graph.absolutize(
                source.getPublicId() or source.getSystemId() or ""
            ),
            turtle=True,
        )
        stream = source.getCharacterStream()
        if not stream:
            stream = source.getByteStream()
        p.loadStream(stream)
        baseURI = p._baseURI
        return baseURI

    @classmethod
    def extract_base_from_turtle(cls, turtle_str: str) -> str:
        """
        Parse the given Turtle document (string) and return
        the base URI used during parsing.
        """
        source = InputSource()
        source.setCharacterStream(StringIO(turtle_str))
        return cls._extract_base_from_inputsource(source)

    def _inject_base_from_parse_kwargs(self, **kwargs):
        if self.base:
            return
        self.base = self._extract_base_from_inputsource(
            create_input_source(
                source=kwargs.get("source"),
                publicID=kwargs.get("publicID"),
                location=kwargs.get("location"),
                file=kwargs.get("file"),
                data=kwargs.get("data"),
                format=kwargs.get("format"),
            )
        )

    def parse(self, *args, **kwargs):
        """
        Same as in `super()` but injects `base` from Turtle
        if not already set and if available, thus making
        it persist across reserialiation/parsing cycles.

        Also see docstring for `_extract_base_from_inputsource()`.
        """
        super().parse(*args, **kwargs)
        self._inject_base_from_parse_kwargs(**kwargs)
