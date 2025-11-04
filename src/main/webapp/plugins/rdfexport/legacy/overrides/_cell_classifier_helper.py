from __future__ import annotations
import re
from legacy.draw_io_parser import *
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

@override(phase="core", type="internal", role="control")
class CellClassifierHelper:
    """A helper class for classifying DrawIO cells."""

    def __init__(self, xml_graph: etree.ElementTree, prefixes: dict, strip_html: bool = False):
        self.xml_graph = xml_graph
        self.prefixes = prefixes
        self.strip_html = strip_html
        self.cells: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}

    @staticmethod
    def detect_string_template(template: str) -> list[str | None]:
        """
        Detects valid unescaped {reference} patterns in a string template.
        """
        pattern = re.compile(r"(?<!\\)(?<!{){([^{}]+)}(?!})(?!\\)")
        matches = []
        for match in pattern.finditer(template):
            ref = match.group(1).strip()
            if ref:
                matches.append(ref)
        return matches

    def _process_graph(self) -> None:
        """Processes the graph to identify cells and edges."""
        for cell in self.xml_graph.findall(".//mxCell"):
            cell_id = cell.get("id")
            if not cell_id:
                continue

            value = cell.get("value", "")
            if self.strip_html:
                value = strip_html_tags(value)

            entry = {
                "id": cell_id,
                "value": value,
                "style": cell.get("style", ""),
                "parent": cell.get("parent"),
                "source": cell.get("source"),
                "target": cell.get("target"),
                "raw_html": cell.get("value", ""),
            }

            if cell.get("edge"):
                self.edges[cell_id] = entry
            else:
                self.cells[cell_id] = entry

    def classify(self, cell: dict, cell_value: str, raw_html: str) -> str:
        """Classifies a cell based on its properties."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    def get_classifications(self) -> dict[str, str]:
        """Returns a dictionary of cell classifications."""
        classifications = {}
        for cell_id, cell in self.cells.items():
            classification = self.classify(
                cell, cell.get("value", ""), cell.get("raw_html", "")
            )
            classifications[cell_id] = classification
        return classifications
