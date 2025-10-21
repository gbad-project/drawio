from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterable, Optional
from xml.etree.ElementTree import Element

from rdflib import Graph, URIRef

from legacy.draw_io_parser import (  # type: ignore=imported-unused
    _NoValueException,
    ParseException,
    pipeline,
)
from meta_builder.drawio_meta_builder import override

DECORATION_REGISTRY_ATTR = "__drawio_literal_registry"
DEFAULT_STANDALONE_TYPE = "rico:Thing"


@override(phase="core", type="xml", role="data")
class CellKind(Enum):
    ARROW_LABEL = auto()
    TYPED_INDIVIDUAL = auto()
    STANDALONE_INDIVIDUAL = auto()
    LITERAL = auto()
    DECORATION = auto()


@override(phase="core", type="xml", role="data")
@dataclass(slots=True)
class CellClassification:
    kind: Enum
    raw_value: str
    parent_cell: Optional[Element] = None
    parent_identifier: Optional[str] = None
    identifier: Optional[str] = None
    tokens: list[str] = field(default_factory=list)


@override(phase="core", type="xml", role="data")
class DrawIOCellClassifier:
    """Centralised DrawIO mxCell role classification."""

    DECORATION_REGISTRY_ATTR = "__drawio_literal_registry"
    DEFAULT_STANDALONE_TYPE = "rico:Thing"

    def __init__(self, tree, prefixes: dict[str, str]):
        self._tree = tree
        self._prefixes = prefixes
        self._namespace_manager = Graph().namespace_manager
        for prefix, iri in prefixes.items():
            self._namespace_manager.bind(prefix, iri, replace=True)

    def classify(self, cell: Element, cell_value: str):
        CellClassificationType = pipeline.core.xml.data.CellClassification
        Kind = pipeline.core.xml.data.CellKind
        raw_value = cell_value.strip()
        if not raw_value:
            return CellClassificationType(Kind.LITERAL, raw_value)

        style = cell.attrib.get("style", "")
        if "edgeLabel" in style:
            return CellClassificationType(Kind.ARROW_LABEL, raw_value)

        parent_cell, parent_identifier = self._resolve_parent(cell)

        tokens = self._tokenise(raw_value)
        tokens_are_valid = self._tokens_are_valid(tokens)
        child_tokens = self._collect_child_tokens(cell)
        child_tokens_are_valid = self._tokens_are_valid(child_tokens)

        if parent_cell is not None and parent_identifier and tokens:
            return CellClassificationType(
                kind=Kind.TYPED_INDIVIDUAL,
                raw_value=raw_value,
                parent_cell=parent_cell,
                parent_identifier=parent_identifier,
                tokens=tokens,
            )

        if tokens and tokens_are_valid:
            return CellClassificationType(
                kind=Kind.STANDALONE_INDIVIDUAL,
                raw_value=raw_value,
                identifier=raw_value,
                tokens=tokens,
            )

        if child_tokens and child_tokens_are_valid:
            return CellClassificationType(
                kind=Kind.STANDALONE_INDIVIDUAL,
                raw_value=raw_value,
                identifier=raw_value,
                tokens=child_tokens,
            )

        if self._looks_like_absolute_uri(raw_value):
            return CellClassificationType(
                kind=Kind.STANDALONE_INDIVIDUAL,
                raw_value=raw_value,
                identifier=raw_value,
                tokens=[],
            )

        if self._should_classify_as_decoration(cell, raw_value, style):
            return CellClassificationType(Kind.DECORATION, raw_value)

        return CellClassificationType(Kind.LITERAL, raw_value)

    def _resolve_parent(self, cell: Element) -> tuple[Optional[Element], Optional[str]]:
        parent_id = cell.attrib.get("parent")
        if parent_id in {None, "1"}:
            return None, None
        try:
            parent = self._tree._parent_of(cell)
        except ParseException:
            return None, None
        try:
            parent_value = self._tree._value_of(parent).strip()
        except _NoValueException:
            return parent, None
        if not parent_value:
            return parent, None
        return parent, parent_value

    @staticmethod
    def _tokenise(value: str) -> list[str]:
        normalised = value.replace(",", " ").replace(";", " ")
        deduped: dict[str, None] = {}
        for token in normalised.split():
            cleaned = token.strip()
            if not cleaned:
                continue
            deduped.setdefault(cleaned)
        return list(deduped.keys())

    def _tokens_are_valid(self, tokens: Iterable[str]) -> bool:
        has_token = False
        for token in tokens:
            if not token:
                continue
            has_token = True
            if not self._token_is_valid(token):
                return False
        return has_token

    def _token_is_valid(self, token: str) -> bool:
        if ":" not in token:
            return False
        prefix, remainder = token.split(":", 1)
        if not prefix or not remainder.strip():
            return False
        if prefix not in self._prefixes:
            return False
        try:
            self._namespace_manager.expand_curie(token)
        except Exception:
            return False
        return True

    def _collect_child_tokens(self, cell: Element) -> list[str]:
        cell_id = cell.attrib.get("id")
        if not cell_id:
            return []
        collected: dict[str, None] = {}
        try:
            children = list(self._tree._child_of(cell_id))
        except Exception:
            children = []
        for child in children:
            try:
                child_value = self._tree._value_of(child).strip()
            except _NoValueException:
                continue
            if not child_value:
                continue
            for token in self._tokenise(child_value):
                if token and self._token_is_valid(token):
                    collected.setdefault(token)
        return list(collected.keys())

    def _should_classify_as_decoration(
        self, cell: Element, raw_value: str, style: str
    ) -> bool:
        if not raw_value:
            return False
        if "edgeLabel" in style:
            return False
        parent_id = cell.attrib.get("parent")
        if parent_id not in {None, "1"}:
            return False
        looks_like_literal = False
        try:
            looks_like_literal = self._tree._is_possible_literal(cell)
        except Exception:
            looks_like_literal = False
        if looks_like_literal:
            return False
        if "text;" in style:
            return True
        if "autosize=1" in style and "rounded" not in style:
            return True
        if "<" in raw_value and ">" in raw_value:
            return True
        return False

    @staticmethod
    def _looks_like_absolute_uri(value: str) -> bool:
        if not value or any(ch.isspace() for ch in value):
            return False
        try:
            candidate = URIRef(value)
        except Exception:
            return False
        return str(candidate) == value and "://" in value
