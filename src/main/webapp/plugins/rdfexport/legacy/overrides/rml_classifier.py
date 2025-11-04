from __future__ import annotations
from legacy.draw_io_parser import *
from ._cell_classifier_helper import CellClassifierHelper
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F4-3, F405

@override(phase="core", type="rml", role="control")
class RmlClassifier(CellClassifierHelper):
    """Classifies DrawIO cells for RML serialization."""

    def __init__(self, xml_graph: etree.ElementTree, prefixes: dict, strip_html: bool = False):
        super().__init__(xml_graph, prefixes, strip_html)
        self._process_graph()

    def classify(self, cell: dict, cell_value: str, raw_html: str) -> str:
        """Classifies a cell as a Literal, Individual, or Class, with special handling for RML templates."""
        style = cell.get("style", "")
        if "rounded=1" in style:
            return "Literal"
        if "shape=ellipse" in style:
            return "Individual"
        if self.detect_string_template(cell_value):
            return "Class"
        if cell_value and ":" in cell_value:
            try:
                _verify_is_ric_class(cell_value, self.prefixes)
                return "Class"
            except NotInKnownException:
                pass
        return "Individual"
