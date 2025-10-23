from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="xml", role="data")
def _start_or_end(
    self, cell: Element, as_attribute: str | None
) -> tuple[XCoordinate, YCoordinate] | None:
    """Resolve the absolute start/end coordinates for a cell."""
    try:
        geometry = DrawIOXMLTree._geometry(cell)
    except ParseException:
        if as_attribute is None:
            parent_id = cell.attrib.get("parent")
            if parent_id in {None, "0", "1"}:
                return 0.0, 0.0
            try:
                parent_cell = self._parent_of(cell)
            except ParseException:
                return 0.0, 0.0
            return self._start_or_end(parent_cell, None)
        if self._is_locked(cell, as_attribute):
            return None
        raise

    if as_attribute is None:
        return self._x_and_y_in_geometry(geometry, cell.attrib.get("id", ""))

    if len(geometry) == 0:
        if self._is_locked(cell, as_attribute):
            return None
        raise ParseException(
            "Expecting the mxGeometry element of the cell with the following id "
            "to have sub-elements, but has no sub-elements at all: "
            f"{cell.attrib.get('id')}"
        )

    cell_id = cell.attrib.get("id", "")
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
                "Encountered an mxPoint element of the cell with the following "
                "id without an 'x' attribute: "
                f"{cell_id}"
            ) from key_error
        try:
            y = float(element.attrib["y"])
        except KeyError as key_error:
            if self._is_locked(cell, as_attribute):
                return None
            raise ParseException(
                "Encountered an mxPoint element of the cell with the following "
                "id without a 'y' attribute: "
                f"{cell_id}"
            ) from key_error
        parent_id = cell.attrib.get("parent")
        if parent_id in {None, "1"}:
            return x, y
        parent_coordinates = self._start_or_end(self._parent_of(cell), None)
        if parent_coordinates is None:
            raise ValueError
        parent_x, parent_y = parent_coordinates
        return x + parent_x, y + parent_y

    if self._is_locked(cell, as_attribute):
        return None

    raise ParseException(
        "Expecting the mxGeometry element of the cell with the following id to "
        "have an mxPoint sub-element with 'as' attribute having value "
        f"'{as_attribute}', but it does not: {cell_id}"
    )


@override(phase="core", type="xml", role="data")
def _arrow_start(self, arrow_cell: Element) -> ArrowStart | None:
    try:
        return self._start_or_end(arrow_cell, "sourcePoint")
    except ParseException:
        if "source" in arrow_cell.attrib:
            return None
        raise


@override(phase="core", type="xml", role="data")
def _arrow_end(self, arrow_cell: Element) -> ArrowEnd | None:
    try:
        return self._start_or_end(arrow_cell, "targetPoint")
    except ParseException:
        if "target" in arrow_cell.attrib:
            return None
        raise
