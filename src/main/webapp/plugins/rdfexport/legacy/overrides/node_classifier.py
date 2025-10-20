from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, TYPE_CHECKING
from xml.etree.ElementTree import Element

from rdflib import Graph, URIRef

from legacy.draw_io_parser import _NoValueException

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from legacy.draw_io_parser import DrawIOXMLTree


class NodeKind(Enum):
    """Classification buckets for mxCell nodes."""

    TYPED_INDIVIDUAL = "typed_individual"
    INDIVIDUAL = "individual"
    LITERAL = "literal"


@dataclass(frozen=True)
class NodeClassification:
    """Result returned by :class:`DrawIONodeClassifier`."""

    kind: NodeKind
    identifier: str | None = None
    types: tuple[str, ...] = ()
    literal: str | None = None
    parent_cell: Element | None = None


@dataclass
class LiteralInfo:
    """Bookkeeping structure for literal nodes."""

    value: str
    connected: bool = False


class DrawIONodeClassifier:
    """Centralised helper that classifies mxCells according to parser rules."""

    def __init__(self, prefixes: dict[str, str]):
        self._prefixes = prefixes
        self._namespace_manager = Graph().namespace_manager
        for prefix, iri in prefixes.items():
            self._namespace_manager.bind(prefix, iri, replace=True)

    def classify(
        self, cell: Element, raw_value: str, tree: "DrawIOXMLTree"
    ) -> NodeClassification | None:
        trimmed = raw_value.strip()
        if not trimmed:
            return None

        curie_tokens = self._curie_tokens(trimmed)
        curie_valid = bool(curie_tokens)

        parent_cell = None
        parent_identifier = None
        if curie_valid:
            parent_cell = self._resolve_parent_cell(tree, cell)
            if parent_cell is not None:
                parent_identifier = self._safe_value_of(tree, parent_cell)
                if not parent_identifier:
                    parent_cell = None

        if curie_valid and parent_cell is not None:
            return NodeClassification(
                kind=NodeKind.TYPED_INDIVIDUAL,
                identifier=parent_identifier,
                types=tuple(curie_tokens),
                parent_cell=parent_cell,
            )

        if curie_valid or self._is_valid_uri(trimmed):
            return NodeClassification(
                kind=NodeKind.INDIVIDUAL,
                identifier=trimmed,
            )

        return NodeClassification(kind=NodeKind.LITERAL, literal=trimmed)

    def _curie_tokens(self, candidate: str) -> tuple[str, ...]:
        if ":" not in candidate:
            return ()
        raw_tokens: Iterable[str] = (
            token.strip()
            for token in candidate.replace(",", " ").replace(";", " ").split()
        )
        tokens: list[str] = []
        for token in raw_tokens:
            if not token:
                continue
            try:
                self._namespace_manager.expand_curie(token)
            except Exception:  # pragma: no cover - rdflib may raise different errors
                return ()
            if token not in tokens:
                tokens.append(token)
        return tuple(tokens)

    def _resolve_parent_cell(
        self, tree: "DrawIOXMLTree", cell: Element
    ) -> Element | None:
        parent_id = cell.attrib.get("parent")
        if not parent_id or parent_id in {"0", "1"}:
            return None
        try:
            parent = tree._parent_of(cell)
        except Exception:
            return None
        return parent

    @staticmethod
    def _safe_value_of(tree: "DrawIOXMLTree", cell: Element) -> str | None:
        try:
            return tree._value_of(cell)
        except _NoValueException:
            return None

    @staticmethod
    def _is_valid_uri(candidate: str) -> bool:
        if not candidate or any(char.isspace() for char in candidate):
            return False
        try:
            uri = URIRef(candidate)
        except Exception:  # pragma: no cover - rdflib defensive guard
            return False
        return bool(uri) and ":" in candidate
