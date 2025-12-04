from __future__ import annotations

import yaml
from pathlib import Path

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


# Load default literal definitions from YAML at module load time
try:
    _config_path = Path(__file__).resolve().parents[5] / "integration_tests" / "config" / "default.yml"
    if _config_path.exists():
        with open(_config_path, 'r') as _f:
            _config = yaml.safe_load(_f)
            _yaml_defs = _config.get('parser_config', {}).get('literal_definitions', [])
            # Convert from YAML format (attr_key/attr_value) to Python format (key/value)
            _DEFAULT_LITERAL_DEFINITIONS = []
            for _item in _yaml_defs:
                if isinstance(_item, dict) and 'attr_key' in _item and 'attr_value' in _item:
                    _DEFAULT_LITERAL_DEFINITIONS.append({
                        "key": _item['attr_key'],
                        "value": _item['attr_value']
                    })
            if not _DEFAULT_LITERAL_DEFINITIONS:
                _DEFAULT_LITERAL_DEFINITIONS = [{"key": "style", "value": "rounded=1"}]
    else:
        _DEFAULT_LITERAL_DEFINITIONS = [{"key": "style", "value": "rounded=1"}]
except Exception:
    _DEFAULT_LITERAL_DEFINITIONS = [{"key": "style", "value": "rounded=1"}]


@override(phase="core", type="xml", role="data")
class DrawIOXMLTree:
    """Deprecated. Use `DrawIOCellClassifier` instead."""

    def __init__(*args, **kwargs):
        raise pipeline.core.internal.data.DeimplementedException(DrawIOXMLTree.__doc__)


@override(phase="core", type="xml", role="data")
class DrawIOCellClassifier:
    """
    A self-contained class to parse Draw.io XML into graph elements.
    It supersedes DrawIOXMLTree by handling XML parsing, cell classification,
    and graph element generation in a single place.
    """

    DECORATION_REGISTRY_ATTR = "__drawio_literal_registry"
    DEFAULT_STANDALONE_TYPE = "owl:NamedIndividual"
    DEFAULT_LITERAL_DEFINITIONS = _DEFAULT_LITERAL_DEFINITIONS

    def __init__(
        self,
        raw_xml: Any,
        prefixes: dict[str, str],
        *,
        strict_mode: bool = False,
        max_gap: float | None = None,
        strip_html: bool = True,
        literal_definitions: list[dict[str, str]] | None = None,
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
        # Store as-is: None means use default, [] means no detection, list means use it
        self._literal_definitions = literal_definitions
        self._html_parser = NodeHTMLParser()
        self._edge_incidence = self._build_edge_incidence()
        self._child_value_cache: dict[str, list[str]] = {}

        self.classifications: dict[str, Any] = {}

        # These will be populated by _process_graph
        self.individuals: list[Individual] = []
        self.arrows: list[Arrow] = []
        self.decorations: dict[str, dict[str, Any]] = {}
        self._nodes_by_id: dict[str, tuple[Element, Individual]] = {}
        self._literals_by_id: dict[str, Element] = {}
        self._declared_individual_identifiers: set[str] = set()

        # Set the registry for the serializer to find
        setattr(
            pipeline.core.internal.data, self.DECORATION_REGISTRY_ATTR, self.decorations
        )

        # Main processing call
        self._process_graph()

    def get_graph_elements(self) -> Generator[Individual | Arrow, None, None]:
        """Yields all parsed Individual and Arrow objects."""
        yield from self.individuals
        yield from self.arrows

    def _record_literal_decorations(self, cell):
        cell_id = cell.attrib.get("id")
        classification = self.classifications[cell_id]

        # Record as a literal
        self._literals_by_id[cell_id] = cell

        # Note that raw_value is NOT passed among tokens,
        # so it must be explicitly added here for all cases
        value = (
            [classification.raw_value] + classification.tokens
            if len(classification.tokens) > 0
            else classification.raw_value
        )  # tokens here actually contain literalized typed individuals (from `_collect_child_values()`), untokenized
        self.decorations[cell_id] = {
            "value": value,
            "connected": False,
        }

    def _process_graph(self):
        """
        Main processing loop. First classifies all nodes (vertices), then
        resolves all arrows (edges).
        """
        _NoValueException = pipeline.core.xml.data._NoValueException
        CellKind = pipeline.core.internal.data.CellKind
        CellClassification = pipeline.core.internal.data.CellClassification

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
                    self.classifications[cell_id] = CellClassification(
                        CellKind.ARROW_LABEL,
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
            cell_id = cell.attrib.get("id")

            parent = classification.parent_cell
            parent_identifier = parent_cell_id = None
            if parent is not None:
                if self._is_layer(parent):
                    pass  # for now; later good to implement named graphs
                else:
                    parent_identifier = classification.parent_identifier
                    parent_cell_id = parent.attrib.get("id")

            if kind_name == "TYPE_TOKEN":
                identifier = parent_identifier
                if cell_id is None or parent_cell_id in self._literals_by_id:
                    # Truly nothing to collect
                    continue
                elif parent is None or identifier is None:
                    self._record_literal_decorations(cell)
                    continue
                for token in classification.tokens:
                    individual = Individual(identifier, token)
                    # Check for duplicates before adding
                    if not any(
                        ind == individual
                        for ind in self.individuals
                        if ind.identifier == identifier
                    ):
                        self.individuals.append(individual)
                    self._declared_individual_identifiers.add(identifier)
                    self._nodes_by_id[parent.attrib["id"]] = (parent, individual)
                    # Some arrows reference the typed child cell directly instead of
                    # the swimlane/container node. Retain a lookup for both so either
                    # identifier can be resolved during edge reconstruction.
                    self._nodes_by_id[cell_id] = (cell, individual)

            elif kind_name == "STANDALONE_INDIVIDUAL":
                identifier = classification.identifier or classification.raw_value
                if not cell_id:
                    continue
                types = classification.tokens or [self.DEFAULT_STANDALONE_TYPE]
                for rdf_type in types:
                    individual = Individual(identifier, rdf_type)
                    if not any(
                        ind == individual
                        for ind in self.individuals
                        if ind.identifier == identifier
                    ):
                        self.individuals.append(individual)
                    if classification.tokens or classification.declares_identifier:
                        self._declared_individual_identifiers.add(identifier)
                    self._nodes_by_id[cell_id] = (cell, individual)

            elif kind_name in ("LITERAL", "DECORATION", "EMPTY_CELL"):
                if cell_id:
                    self._record_literal_decorations(cell)

        # Second pass: resolve all edges now that nodes are mapped
        for cell in self.draw_io_xml_tree.findall(".//*[@edge='1']"):
            try:
                arrow = self._resolve_arrow(cell)
                if arrow:
                    self.arrows.append(arrow)
            except ArrowWithoutIndividualAsSourceException:
                raise
            except (NoSourceException, NoTargetException) as e:
                if self._strict_mode:
                    raise
                print(f"Warning: Skipping arrow due to error: {e}")

    def classify(self, cell: Element, cell_value: str, raw_html: str | None = None):
        """Determines the role of a given mxCell in the graph."""
        CellKind = pipeline.core.internal.data.CellKind
        CellClassification = pipeline.core.internal.data.CellClassification

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
            if (kind == CellKind.LITERAL or kind == CellKind.DECORATION) and isinstance(
                literal_value, str
            ):
                selected_value = literal_value
            return CellClassification(kind, selected_value, cell, **kwargs)

        if cell.attrib.get("edge") == "1":
            return build(CellKind.ARROW)

        style = cell.attrib.get("style", "")
        if "edgeLabel" in style:
            return build(CellKind.ARROW_LABEL)

        if not raw_value:
            return build(CellKind.EMPTY_CELL)

        if self._is_layer(cell):
            return build(CellKind.LAYER)

        parent_cell, parent_identifier = self._resolve_parent(cell)

        # the below line is cursed in that just `if parent_cell` does not work
        if parent_cell is not None and self._is_layer(parent_cell):
            parent_cell = parent_identifier = None

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

        tokens = self._tokenise(raw_value)
        child_values = self._collect_child_values(cell)
        child_tokens = [self._tokenise(t) for t in child_values]
        if child_tokens:
            tokens.extend(t for t in child_tokens if t not in tokens)

        if self._style_denotes_literal(cell, style):
            # using untokenized values
            return build(CellKind.LITERAL, tokens=child_values)

        if parent_cell is not None and parent_identifier:
            return build(
                CellKind.TYPE_TOKEN,
                parent_cell=parent_cell,
                parent_identifier=parent_identifier,
                tokens=tokens,
            )
        elif self._is_decoration(cell, raw_value):
            # using untokenized values
            return build(CellKind.DECORATION, tokens=child_values)
        else:
            # This was originally used but probably does
            # not make sense because untyped standalone
            # individuals are to be considered declared
            # anyway (this leads to arrows resolving as
            # object and not datatype props, for example)
            # declares_identifier = bool(child_tokens)
            return build(
                CellKind.STANDALONE_INDIVIDUAL,
                identifier=raw_value,
                tokens=[],
                declares_identifier=True,
            )

    # region Helper Methods (Moved from DrawIOXMLTree)
    def _value_of(self, cell: Element, *, raw: bool = False) -> str:
        _NoValueException = pipeline.core.xml.data._NoValueException

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

    @staticmethod
    def _has_correct_as_attribute(
        element: Element, as_attribute: str, cell_id: str
    ) -> bool:
        try:
            return element.attrib["as"] == as_attribute
        except KeyError as key_error:
            raise ParseException(
                "Encountered an mxPoint element of the cell with the "
                f"following id without an 'as' attribute: {cell_id}"
            ) from key_error

    @staticmethod
    def _is_locked(cell: Element, as_attribute: str) -> bool:
        if as_attribute == "sourcePoint" and ("source" in cell.attrib):
            return True
        if as_attribute == "targetPoint" and ("target" in cell.attrib):
            return True
        return False

    @staticmethod
    def _x_and_y_in_geometry(geometry: Element, cell_id: str) -> tuple[float, float]:
        try:
            x = float(geometry.attrib["x"])
        except KeyError as key_error:
            raise ParseException(
                "Encountered an mxGeometry element of the cell with the "
                f"following id without an 'x' attribute: {cell_id}"
            ) from key_error
        try:
            y = float(geometry.attrib["y"])
        except KeyError as key_error:
            raise ParseException(
                "Encountered an mxGeometry element of the cell with the "
                f"following id without a 'y' attribute: {cell_id}"
            ) from key_error
        return x, y

    def _dimensions(self, cell: Element) -> Dimensions:
        geom = self._geometry(cell)
        return (
            float(geom.attrib.get("x", 0.0)),
            float(geom.attrib.get("y", 0.0)),
            float(geom.attrib.get("width", 0.0)),
            float(geom.attrib.get("height", 0.0)),
        )

    def _absolute_dimensions(self, cell: Element) -> Dimensions:
        geom = self._geometry(cell)
        width = float(geom.attrib.get("width", 0.0))
        height = float(geom.attrib.get("height", 0.0))
        x, y = self._start_or_end(cell, None)
        return x, y, width, height

    def _close_enough(self, arrow_point: tuple[float, float], cell: Element) -> bool:
        try:
            x, y, width, height = self._absolute_dimensions(cell)
        except ParseException:
            return False
        arrow_x, arrow_y = arrow_point
        return (
            x - self._max_gap <= arrow_x <= x + width + self._max_gap
            and y - self._max_gap <= arrow_y <= y + height + self._max_gap
        )

    def _resolve_nearby_cell(
        self,
        arrow_point: tuple[float, float] | None,
        *,
        require_individual: bool,
    ) -> tuple[Element, str, bool]:
        _NoValueException = pipeline.core.xml.data._NoValueException
        _NoCellCloseEnoughException = pipeline.core.xml.data._NoCellCloseEnoughException
        if arrow_point is None:
            raise _NoCellCloseEnoughException

        for cell, individual in self._nodes_by_id.values():
            if self._close_enough(arrow_point, cell):
                return cell, individual.identifier, False

        if require_individual:
            raise _NoCellCloseEnoughException

        for literal_cell in self._literals_by_id.values():
            if not self._close_enough(arrow_point, literal_cell):
                continue
            try:
                literal_value = self._value_of(literal_cell, raw=not self._strip_html)
            except _NoValueException as exc:
                raise _NoCellCloseEnoughException from exc
            return literal_cell, literal_value, True

        raise _NoCellCloseEnoughException

    def _defines_individual(self, identifier: str) -> bool:
        return identifier in self._declared_individual_identifiers

    def _start_or_end(
        self, cell: Element, as_attribute: str | None
    ) -> tuple[float, float] | None:
        try:
            geometry = self._geometry(cell)
        except ParseException as exc:
            # Some DrawIO documents include intermediate container cells (e.g. the
            # implicit layer root) that do not define their own geometry block.
            # The legacy parser treated those as originating at the canvas origin,
            # so we mirror that behaviour instead of bailing out with a hard
            # failure.  Returning a zero offset keeps arrow coordinate
            # calculations working while still allowing genuine geometry issues to
            # bubble up.
            if as_attribute is None:
                return 0.0, 0.0
            raise exc

        cell_id = cell.attrib.get("id", "")
        if as_attribute is None:
            return self._x_and_y_in_geometry(geometry, cell_id)
        if len(geometry) == 0:
            raise ParseException(
                "Expecting the mxGeometry element of the cell with the "
                "following id to have sub-elements, but has no sub-elements "
                f"at all: {cell_id}"
            )
        for element in geometry:
            if element.tag != "mxPoint" or not self._has_correct_as_attribute(
                element, as_attribute, cell_id
            ):
                continue
            try:
                x = float(element.attrib["x"])
            except KeyError as key_error:
                if self._is_locked(cell, as_attribute):
                    return None
                raise ParseException(
                    "Encountered an mxPoint element of the cell with the "
                    "following id without an 'x' attribute: "
                    f"{cell_id}"
                ) from key_error
            try:
                y = float(element.attrib["y"])
            except KeyError as key_error:
                if self._is_locked(cell, as_attribute):
                    return None
                raise ParseException(
                    "Encountered an mxPoint element of the cell with the "
                    "following id without a 'y' attribute: "
                    f"{cell_id}"
                ) from key_error
            parent_id = cell.attrib.get("parent")
            if parent_id == "1" or parent_id is None:
                return x, y
            parent_coordinates = self._start_or_end(self._parent_of(cell), None)
            if parent_coordinates is None:
                raise ValueError
            parent_x, parent_y = parent_coordinates
            return x + parent_x, y + parent_y
        raise ParseException(
            "Expecting the mxGeometry element of the cell with the following "
            "id to have an mxPoint sub-element with 'as' attribute having "
            f"value '{as_attribute}', but it does not: {cell_id}"
        )

    def _arrow_label(self, arrow_cell: Element) -> str:
        _NoValueException = pipeline.core.xml.data._NoValueException
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

    def _resolve_arrow(self, arrow_cell: Element) -> Arrow | None:
        _NoValueException = pipeline.core.xml.data._NoValueException
        _NoCellCloseEnoughException = pipeline.core.xml.data._NoCellCloseEnoughException
        try:
            arrow_label = self._arrow_label(arrow_cell)
        except _NoValueException:
            return None  # Arrow has no label, so it's not a property

        arrow_id = arrow_cell.attrib["id"]
        source_id = arrow_cell.attrib.get("source")
        target_id = arrow_cell.attrib.get("target")
        try:
            arrow_start = self._start_or_end(arrow_cell, "sourcePoint")
        except ParseException:
            arrow_start = None

        try:
            arrow_end = self._start_or_end(arrow_cell, "targetPoint")
        except ParseException:
            arrow_end = None

        # Resolve source
        if source_id and source_id in self._nodes_by_id:
            source_cell, source_individual = self._nodes_by_id[source_id]
            source_identifier = source_individual.identifier
        elif source_id and source_id in self._literals_by_id:
            raise ArrowWithoutIndividualAsSourceException(
                f"Arrow '{arrow_label}' ({arrow_id}) has a literal ('{self._value_of(self._cell_with_id(source_id))}') as source."
            )
        else:
            if self._strict_mode:
                raise NoSourceException(
                    f"Arrow '{arrow_label}' ({arrow_id}) has no valid source."
                )
            try:
                _, source_identifier, _ = self._resolve_nearby_cell(
                    arrow_start, require_individual=True
                )
            except _NoCellCloseEnoughException as exc:
                raise NoSourceException(
                    f"Arrow '{arrow_label}' ({arrow_id}) has no valid source."
                ) from exc

        # Resolve target
        target_cell = None
        is_datatype = False
        if target_id:
            if target_id in self._nodes_by_id:
                target_cell, target_individual = self._nodes_by_id[target_id]
                target_identifier = target_individual.identifier
            elif target_id in self._literals_by_id:
                target_cell = self._literals_by_id[target_id]
                target_identifier = self._value_of(
                    target_cell, raw=not self._strip_html
                )
                is_datatype = True
            else:
                if self._strict_mode:
                    raise NoTargetException(
                        f"Arrow '{arrow_label}' ({arrow_id}) target '{target_id}' could not be found."
                    )
                try:
                    candidate_cell, target_identifier, is_datatype = (
                        self._resolve_nearby_cell(arrow_end, require_individual=False)
                    )
                    target_cell = candidate_cell
                except _NoCellCloseEnoughException as exc:
                    raise NoTargetException(
                        f"Arrow '{arrow_label}' ({arrow_id}) target '{target_id}' could not be found."
                    ) from exc
        else:
            if self._strict_mode:
                raise NoTargetException(
                    f"Arrow '{arrow_label}' ({arrow_id}) has no target."
                )
            try:
                candidate_cell, target_identifier, is_datatype = (
                    self._resolve_nearby_cell(arrow_end, require_individual=False)
                )
                target_cell = candidate_cell
            except _NoCellCloseEnoughException as exc:
                raise NoTargetException(
                    f"Arrow '{arrow_label}' ({arrow_id}) has no target."
                ) from exc

        if target_cell is not None and target_cell.attrib.get("id") in self.decorations:
            self.decorations[target_cell.attrib["id"]]["connected"] = True

        if not is_datatype and not self._defines_individual(target_identifier):
            is_datatype = True

        return Arrow(
            str(arrow_label.strip()), source_identifier, target_identifier, is_datatype
        )

    # endregion

    # region Original Classifier Logic
    def _resolve_parent(self, cell: Element) -> tuple[Optional[Element], Optional[str]]:
        _NoValueException = pipeline.core.xml.data._NoValueException
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
        "Split by any whitespace character and strip each token."
        return [t.strip() for t in value.split(" ") if t.strip()]

    def _token_is_template(self, token: str) -> bool:
        try:
            return bool(self._detect_string_template(token))
        except Exception:
            return False

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

    def _collect_child_values(self, cell: Element) -> list[str]:
        _NoValueException = pipeline.core.xml.data._NoValueException
        cell_id = cell.attrib.get("id")
        if not cell_id:
            return []
        if cell_id in self._child_value_cache:
            return list(self._child_value_cache[cell_id])

        values = []
        for child in self._child_of(cell_id):
            try:
                child_value = self._value_of(child).strip()
                values.append(child_value)
            except (_NoValueException, ParseException):
                continue
        self._child_value_cache[cell_id] = values
        return values

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
        if not style:  # is None or empty string
            # Draw IO always seems to always set style when
            # creating elements, but let's say programmatically
            # created elements without style are even more minimal
            # and thus qualify for minting individuals
            return False
        # Original treatment by Codex, but feels restrictive
        # return "text;" in style or "shape=text" in style
        return False

    def _style_denotes_literal(self, cell: Element, style: str) -> bool:
        """Check if cell matches any literal definition.

        - None: Use DEFAULT_LITERAL_DEFINITIONS from default.yml
        - []: Return True (treat everything as literal)
        - [...]: Use provided definitions
        """
        # Handle None - use default
        if self._literal_definitions is None:
            definitions_to_use = self.DEFAULT_LITERAL_DEFINITIONS
        # Handle explicit empty list - everything is literal
        elif (
            isinstance(self._literal_definitions, list)
            and len(self._literal_definitions) == 0
        ):
            return True
        # Use provided definitions
        else:
            definitions_to_use = self._literal_definitions

        # Check each literal definition
        for definition in definitions_to_use:
            attr_name = definition.get("key", "")
            pattern = definition.get("value", "")
            if not attr_name or not pattern:
                continue

            # Get the attribute value from the cell
            attr_value = cell.attrib.get(attr_name, "")
            if not attr_value:
                continue

            # Check if the pattern exists in the attribute value
            if pattern in attr_value:
                return True

        return False

    def _is_decoration(self, cell: Element, raw_value: str) -> bool:
        """Currently always returns False. Yet standalone literals
        are still treated as decorations (added to registry) downstream."""
        if not raw_value:
            return False
        return (
            # not self._collect_child_values(cell)
            # and not self._has_incident_edge(cell)
            # and self._style_suggests_decoration(cell.attrib.get("style", ""))
            self._style_suggests_decoration(cell.attrib.get("style", ""))
        )

    def _is_layer(self, cell: Element) -> bool:
        return cell.attrib.get("parent") == "0"
