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
        self._edge_incidence = self._build_edge_incidence()
        self._child_token_cache: dict[str, list[str]] = {}

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

        value_tokens = self._tokenise(raw_value)
        tokens_are_valid = self._tokens_are_valid(value_tokens)
        if tokens_are_valid:
            tokens = list(value_tokens)
        else:
            tokens = []

        child_tokens = self._collect_child_tokens(cell)
        if child_tokens:
            if tokens_are_valid:
                for token in child_tokens:
                    if token not in tokens:
                        tokens.append(token)
            else:
                tokens = list(child_tokens)
                tokens_are_valid = True

        if (
            parent_cell is not None
            and parent_identifier
            and tokens
            and tokens_are_valid
        ):
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

        if self._looks_like_absolute_uri(raw_value):
            return CellClassificationType(
                kind=Kind.STANDALONE_INDIVIDUAL,
                raw_value=raw_value,
                identifier=raw_value,
                tokens=[],
            )

        if self._is_decoration(cell, raw_value):
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
        return has_token

    @staticmethod
    def _looks_like_absolute_uri(value: str) -> bool:
        if not value or any(ch.isspace() for ch in value):
            return False
        try:
            candidate = URIRef(value)
        except Exception:
            return False
        return str(candidate) == value and "://" in value

    def _collect_child_tokens(self, cell: Element) -> list[str]:
        cell_id = cell.attrib.get("id")
        if not cell_id:
            return []
        if cell_id in self._child_token_cache:
            return list(self._child_token_cache[cell_id])

        tokens: list[str] = []
        seen: set[str] = set()
        for child in self._tree._child_of(cell_id):
            try:
                child_value = self._tree._value_of(child).strip()
            except (_NoValueException, ParseException):
                continue
            child_tokens = self._tokenise(child_value)
            if not child_tokens or not self._tokens_are_valid(child_tokens):
                continue
            for token in child_tokens:
                if token and token not in seen:
                    seen.add(token)
                    tokens.append(token)

        self._child_token_cache[cell_id] = list(tokens)
        return list(tokens)

    def _build_edge_incidence(self) -> set[str]:
        incidence: set[str] = set()
        try:
            edges = self._tree.draw_io_xml_tree.findall(".//*[@edge='1']")
        except AttributeError:
            return incidence
        for edge in edges:
            source = edge.attrib.get("source")
            target = edge.attrib.get("target")
            if source:
                incidence.add(source)
            if target:
                incidence.add(target)
        return incidence

    def _has_incident_edge(self, cell: Element) -> bool:
        cell_id = cell.attrib.get("id")
        if not cell_id:
            return False
        return cell_id in self._edge_incidence

    @staticmethod
    def _style_suggests_decoration(style: str) -> bool:
        if not style:
            return False
        if style.startswith("text;"):
            return True
        segments = tuple(segment.strip() for segment in style.split(";") if segment)
        return "shape=text" in segments

    def _is_decoration(self, cell: Element, raw_value: str) -> bool:
        if not raw_value:
            return False
        if self._collect_child_tokens(cell):
            return False
        if self._has_incident_edge(cell):
            return False
        style = cell.attrib.get("style", "")
        if not self._style_suggests_decoration(style):
            return False
        return True
