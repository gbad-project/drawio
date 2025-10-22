from __future__ import annotations

from collections.abc import Generator

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="xml", role="data")
class DrawIOXmlNavigator:
    """Utility wrapper around the Draw.io XML tree.

    The navigator centralises the XPath lookups and geometry helpers that were
    previously embedded inside the classifier so that XML traversal stays
    isolated from the classification rules.
    """

    def __init__(
        self, draw_io_xml_tree: Element, html_parser: NodeHTMLParser | None = None
    ) -> None:
        self._tree = draw_io_xml_tree
        self._html_parser = html_parser or NodeHTMLParser()

    # region element lookups -------------------------------------------------
    def iter_cells(self) -> list[Element]:
        return list(self._tree.findall(".//mxCell"))

    def iter_edges(self) -> list[Element]:
        return list(self._tree.findall(".//*[@edge='1']"))

    def cell_with_id(self, cell_id: str) -> Element:
        cell = self._tree.find(f".//*[@id='{cell_id}']")
        if cell is None:
            raise ValueError(f"No cell with id: {cell_id}")
        return cell

    def parent_of(self, cell: Element) -> Element:
        parent_id = cell.attrib.get("parent")
        if not parent_id:
            raise ParseException(
                f"Cell {cell.attrib.get('id')} has no parent attribute."
            )
        return self.cell_with_id(parent_id)

    def children_of(self, parent_id: str) -> Generator[Element, None, None]:
        yield from self._tree.findall(f".//*[@parent='{parent_id}']")

    # endregion --------------------------------------------------------------

    # region content helpers -------------------------------------------------
    def value_of(self, cell: Element) -> str:
        value = cell.attrib.get("value")
        if value is None:
            raise _NoValueException
        self._html_parser.clear()
        self._html_parser.feed(value)
        return self._html_parser.content()

    def arrow_label(self, arrow_cell: Element) -> str:
        label_cell = self._tree.find(f".//mxCell[@parent='{arrow_cell.attrib['id']}']")
        if label_cell is not None:
            try:
                return self.value_of(label_cell)
            except _NoValueException:
                pass
        raise _NoValueException("No label found for arrow")

    # endregion --------------------------------------------------------------

    # region geometry --------------------------------------------------------
    @staticmethod
    def _geometry(cell: Element) -> Element:
        geom = cell.find("mxGeometry")
        if geom is None:
            raise ParseException(
                f"Cell {cell.attrib.get('id')} has no mxGeometry sub-element."
            )
        return geom

    def dimensions(self, cell: Element) -> Dimensions:
        geom = self._geometry(cell)
        return (
            float(geom.attrib.get("x", 0.0)),
            float(geom.attrib.get("y", 0.0)),
            float(geom.attrib.get("width", 0.0)),
            float(geom.attrib.get("height", 0.0)),
        )

    def start_or_end(
        self, cell: Element, as_attribute: str | None
    ) -> tuple[float, float] | None:
        geometry = self._geometry(cell)
        if as_attribute is None:
            x = float(geometry.attrib.get("x", 0.0))
            y = float(geometry.attrib.get("y", 0.0))
            parent_id = cell.attrib.get("parent")
            if parent_id is None or parent_id == "1":
                return x, y
            try:
                parent_coords = self.start_or_end(self.parent_of(cell), None)
                if parent_coords:
                    return x + parent_coords[0], y + parent_coords[1]
                return x, y
            except (ParseException, ValueError):
                return x, y

        point = geometry.find(f"mxPoint[@as='{as_attribute}']")
        if point is None:
            return None
        x = float(point.attrib.get("x", 0.0))
        y = float(point.attrib.get("y", 0.0))
        return x, y

    # endregion --------------------------------------------------------------

    # region cached lookups --------------------------------------------------
    def edge_incidence(self) -> set[str]:
        return {
            identifier
            for edge in self.iter_edges()
            for key in ("source", "target")
            if (identifier := edge.attrib.get(key))
        }

    # endregion --------------------------------------------------------------
