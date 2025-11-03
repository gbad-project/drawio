from __future__ import annotations

from enum import Enum, auto
import typing
from typing import Iterable

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="core", type="xml", role="data")
class DrawIOXMLTree:
    pass


@override(phase="core", type="xml", role="data")
class DrawIOCellClassifier:
    """
    A self-contained class to parse Draw.io XML into graph elements.
    It supersedes DrawIOXMLTree by handling XML parsing, cell classification,
    and graph element generation in a single place.
    """

    class CellKind(Enum):
        ARROW_LABEL = auto()
        TYPED_INDIVIDUAL = auto()
        STANDALONE_INDIVIDUAL = auto()
        LITERAL = auto()
        DECORATION = auto()

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

    DECORATION_REGISTRY_ATTR = "__drawio_literal_registry"
    DEFAULT_STANDALONE_TYPE = "owl:NamedIndividual"

    def __init__(
        self,
        raw_xml: typing.Any,
        prefixes: dict[str, str],
        *,
        strict_mode: bool = False,
        max_gap: float | None = None,
        strip_html: bool = True,
    ):
        source_tree = getattr(raw_xml, "draw_io_xml_tree", None)
        if isinstance(source_tree, Element):
            self.draw_io_xml_tree = source_tree
        else:
            if isinstance(raw_xml, bytes):
                parsed_xml = raw_xml.decode("utf-8")
            else:
                parsed_xml = str(raw_xml)
            self.draw_io_xml_tree = fromstring(parsed_xml)
        self._prefixes = prefixes
        self._namespace_manager = Graph().namespace_manager
        for prefix, iri in prefixes.items():
            self._namespace_manager.bind(prefix, iri, replace=True)

        self._strict_mode = bool(strict_mode)
        default_gap = 10.0
        gap_candidate = default_gap if max_gap is None else max_gap
        try:
            coerced_gap = float(gap_candidate)
        except (TypeError, ValueError):
            coerced_gap = float(default_gap)
        if coerced_gap != coerced_gap or coerced_gap < 0.0:  # NaN or negative
            coerced_gap = float(default_gap)
        self._max_gap = coerced_gap

        self._strip_html = bool(strip_html)
        self._html_parser = NodeHTMLParser()
        self._edge_incidence = self._build_edge_incidence()
        self._child_token_cache: dict[str, list[str]] = {}

        self.classifications: dict[str, Any] = {}
        self.decorations: dict[str, dict[str, Any]] = {}
        self._literals_by_id: dict[str, Element] = {}

        # Set the registry for the serializer to find
        setattr(
            pipeline.core.internal.data, self.DECORATION_REGISTRY_ATTR, self.decorations
        )

        # Main processing call
        self._process_graph()

    def _arrow_is_object_property(self, arrow_cell: Element) -> bool:
        """Determines if an arrow is an object property."""
        target_id = arrow_cell.attrib.get("target")
        if not target_id:
            return False

        target_classification = self.classifications.get(target_id)
        if not target_classification:
            return False

        return target_classification.kind in (
            self.CellKind.TYPED_INDIVIDUAL,
            self.CellKind.STANDALONE_INDIVIDUAL,
        )

    def _process_graph(self):
        """
        Main processing loop. First classifies all nodes (vertices), then
        resolves all arrows (edges).
        """
        try:
            cells = self.draw_io_xml_tree.findall(".//mxCell")
            if not cells:
                raise NothingToParseException
        except (IndexError, NothingToParseException) as e:
            raise NothingToParseException from e

        # First pass: classify and create all nodes (individuals and literals)
        for cell in cells:
            if cell.attrib.get("edge") == "1":
                cell_id = cell.attrib.get("id")
                if cell_id:
                    try:
                        arrow_value = self._arrow_label(cell)
                    except _NoValueException:
                        arrow_value = cell.attrib.get("value", "").strip()
                    self.classifications[cell_id] = self.CellClassification(
                        self.CellKind.ARROW_LABEL,
                        arrow_value,
                        cell,
                    )
                continue  # Skip edges for now

            try:
                cell_value = self._value_of(cell)
            except _NoValueException:
                continue

            raw_html = self._html_parser.raw_html()
            classification = self.classify(cell, cell_value, raw_html)

            cell_id = cell.attrib.get("id")
            if cell_id:
                self.classifications[cell_id] = classification

            kind_name = getattr(classification.kind, "name", "")
            if kind_name in ("LITERAL", "DECORATION"):
                if cell_id:
                    self._literals_by_id[cell_id] = cell
                    self.decorations[cell_id] = {
                        "value": classification.raw_value,
                        "connected": False,
                    }

    def classify(
        self, cell: Element, cell_value: str, raw_html: str | None = None
    ) -> CellClassification:
        """Determines the role of a given mxCell in the graph."""
        CellClassification = self.CellClassification
        CellKind = self.CellKind

        raw_value = cell_value.strip()
        literal_value = raw_value
        if raw_html is not None and not self._strip_html:
            literal_value = raw_html

        def build(
            kind: CellKind,
            value: str = raw_value,
            **kwargs,
        ) -> CellClassification:
            selected_value: str = value.strip() if isinstance(value, str) else value
            if kind == CellKind.LITERAL and isinstance(literal_value, str):
                selected_value = literal_value
            return CellClassification(kind, selected_value, cell, **kwargs)

        if cell.attrib.get("edge") == "1":
            return build(CellKind.ARROW_LABEL)

        style = cell.attrib.get("style", "")
        if "edgeLabel" in style:
            return build(CellKind.ARROW_LABEL)

        if not raw_value:
            return build(CellKind.LITERAL)

        parent_cell, parent_identifier = self._resolve_parent(cell)

        if (
            parent_cell is not None
            and parent_cell.attrib.get("edge") == "1"
            and raw_value
        ):
            return build(
                CellKind.ARROW_LABEL,
                parent_cell=parent_cell,
                parent_identifier=parent_identifier,
            )

        value_tokens = self._tokenise(raw_value)
        tokens_are_valid = self._tokens_are_valid(value_tokens)
        tokens = list(value_tokens)
        single_token = tokens[0] if len(tokens) == 1 else None
        looks_like_curie = any(":" in token for token in tokens)

        if self._style_denotes_literal(cell, style, tokens_are_valid):
            return build(CellKind.LITERAL)

        child_tokens = self._collect_child_tokens(cell)
        if child_tokens:
            if tokens_are_valid:
                tokens.extend(t for t in child_tokens if t not in tokens)
            else:
                tokens = list(child_tokens)
                tokens_are_valid = True

        if parent_cell is not None and parent_identifier and tokens:
            if looks_like_curie:
                return build(
                    CellKind.TYPED_INDIVIDUAL,
                    parent_cell=parent_cell,
                    parent_identifier=parent_identifier,
                    tokens=tokens,
                )

            if not tokens_are_valid and "html=1" in style:
                for token in tokens:
                    candidate = token.strip()
                    if not candidate:
                        continue
                    _verify_is_ric_class(candidate, self._prefixes)

        if parent_cell is None and single_token is not None and tokens_are_valid:
            return build(
                CellKind.STANDALONE_INDIVIDUAL,
                identifier=single_token,
                tokens=[],
                declares_identifier=True,
            )

        if (
            parent_cell is None
            and single_token is not None
            and self._looks_like_curie_candidate(single_token)
            and not tokens_are_valid
        ):
            raise NotInKnownException(
                (
                    "The standalone node '{0}' references a CURIE, "
                    "which is not defined by the available prefixes."
                ).format(single_token)
            )

        if tokens and tokens_are_valid:
            return build(
                CellKind.STANDALONE_INDIVIDUAL,
                identifier=raw_value,
                tokens=tokens,
            )

        if self._looks_like_absolute_uri(raw_value):
            return build(
                CellKind.STANDALONE_INDIVIDUAL,
                identifier=raw_value,
                tokens=[],
                declares_identifier=True,
            )

        if self._is_decoration(cell, raw_value):
            return build(CellKind.DECORATION)

        return build(CellKind.LITERAL)

    # region Helper Methods (Moved from DrawIOXMLTree)
    def _value_of(self, cell: Element, *, raw: bool = False) -> str:
        value = cell.attrib.get("value")
        if value is None:
            raise _NoValueException
        self._html_parser.clear()
        self._html_parser.feed(value)
        if raw and not self._strip_html:
            return self._html_parser.raw_html()
        return self._html_parser.content()

    def _cell_with_id(self, _id: str) -> Element:
        cell = self.draw_io_xml_tree.find(f".//*[@id='{_id}']")
        if cell is None:
            raise ValueError(f"No cell with id: {_id}")
        return cell

    def _parent_of(self, cell: Element) -> Element:
        parent_id = cell.attrib.get("parent")
        if not parent_id:
            raise ParseException(
                f"Cell {cell.attrib.get('id')} has no parent attribute."
            )
        return self._cell_with_id(parent_id)

    def _child_of(self, parent_id: str) -> Generator[Element, None, None]:
        yield from self.draw_io_xml_tree.findall(f".//*[@parent='{parent_id}']")

    @staticmethod
    def _geometry(cell: Element) -> Element:
        geom = cell.find("mxGeometry")
        if geom is None:
            raise ParseException(
                f"Cell {cell.attrib.get('id')} (value='{cell.attrib.get('value')}') has no mxGeometry sub-element."
            )
        return geom

    def _arrow_label(self, arrow_cell: Element) -> str:
        for cell in self._child_of(arrow_cell.attrib["id"]):
            try:
                style = cell.attrib["style"]
            except KeyError:
                style = ""
            has_value = bool(cell.attrib.get("value"))
            if "edgeLabel" in style or has_value:
                try:
                    return self._value_of(cell)
                except _NoValueException:
                    if has_value:
                        return cell.attrib.get("value", "").strip()
        fallback = arrow_cell.attrib.get("value", "").strip()
        if fallback:
            return fallback
        raise _NoValueException("No label found for arrow")

    # endregion

    # region Original Classifier Logic
    def _resolve_parent(self, cell: Element) -> tuple[Optional[Element], Optional[str]]:
        parent_id = cell.attrib.get("parent")
        if parent_id in {None, "1"}:
            return None, None
        try:
            parent = self._parent_of(cell)
            parent_value = self._value_of(parent).strip()
            return parent, parent_value or None
        except (ParseException, _NoValueException):
            return None, None

    @staticmethod
    def _tokenise(value: str) -> list[str]:
        return [
            t.strip()
            for t in value.replace(",", " ").replace(";", " ").split()
            if t.strip()
        ]

    def _tokens_are_valid(self, tokens: Iterable[str]) -> bool:
        if not tokens:
            return False
        for token in tokens:
            if ":" not in token:
                return False
            prefix, remainder = token.split(":", 1)
            if not prefix or not remainder.strip() or prefix not in self._prefixes:
                return False
            try:
                self._namespace_manager.expand_curie(token)
            except Exception:
                return False
        return True

    @staticmethod
    def _looks_like_curie_candidate(value: str) -> bool:
        if not value or ":" not in value or "://" in value:
            return False
        prefix, remainder = value.split(":", 1)
        if not prefix or not remainder:
            return False
        if not (prefix[0].isalpha() or prefix[0] == "_"):
            return False
        if not all(ch.isalnum() or ch in "._-" for ch in prefix[1:]):
            return False
        return not any(char.isspace() for char in remainder)

    @staticmethod
    def _looks_like_absolute_uri(value: str) -> bool:
        if not value or any(ch.isspace() for ch in value):
            return False
        try:
            return str(URIRef(value)) == value and "://" in value
        except Exception:
            return False

    def _collect_child_tokens(self, cell: Element) -> list[str]:
        cell_id = cell.attrib.get("id")
        if not cell_id:
            return []
        if cell_id in self._child_token_cache:
            return list(self._child_token_cache[cell_id])

        tokens = []
        for child in self._child_of(cell_id):
            try:
                child_value = self._value_of(child).strip()
                child_tokens = self._tokenise(child_value)
                if self._tokens_are_valid(child_tokens):
                    tokens.extend(t for t in child_tokens if t not in tokens)
            except (_NoValueException, ParseException):
                continue
        self._child_token_cache[cell_id] = tokens
        return tokens

    def _build_edge_incidence(self) -> set[str]:
        return {
            id
            for edge in self.draw_io_xml_tree.findall(".//*[@edge='1']")
            for key in ("source", "target")
            if (id := edge.attrib.get(key))
        }

    def _has_incident_edge(self, cell: Element) -> bool:
        cell_id = cell.attrib.get("id")
        return cell_id in self._edge_incidence if cell_id else False

    @staticmethod
    def _style_suggests_decoration(style: str) -> bool:
        if not style:
            return False
        return "text;" in style or "shape=text" in style

    @staticmethod
    def _style_denotes_literal(
        cell: Element, style: str, tokens_are_valid: bool
    ) -> bool:
        if not style:
            return False
        if "rounded=1" in style:
            parent_is_root = cell.attrib.get("parent") == "1"
            has_swimlane_style = "swimlane" in style
            if parent_is_root or has_swimlane_style:
                return True
        if cell.attrib.get("parent") != "1":
            return False
        if tokens_are_valid:
            return False
        return False

    def _is_decoration(self, cell: Element, raw_value: str) -> bool:
        if not raw_value:
            return False
        return (
            not self._collect_child_tokens(cell)
            and not self._has_incident_edge(cell)
            and self._style_suggests_decoration(cell.attrib.get("style", ""))
        )
