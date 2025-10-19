from typing import Optional
from xml.etree.ElementTree import Element, fromstring

from legacy.draw_io_parser import *  # noqa: F401,F403,F405
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F401, F403, F405


@override(phase="pre", type="xml", role="metadata")
def _extract_drawio_metadata(
    raw_xml: str,
) -> tuple[dict[str, str], Optional[str], Optional[str], Optional[Element]]:
    """Parse DrawIO metadata while tracking RML settings."""

    import sys
    from pathlib import Path

    module_root = Path(__file__).resolve().parent
    package_root = module_root.parent
    overrides_dir = module_root / "overrides"
    for candidate in (package_root, module_root, overrides_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)

    try:
        from legacy.overrides import (
            rml_state as _rml_state,
        )  # local import for generated file
    except ModuleNotFoundError:  # pragma: no cover - Pyodide fallback path
        import importlib

        _rml_state = importlib.import_module("rml_state")

    try:
        root = fromstring(raw_xml)
    except Exception:  # pragma: no cover - defensive guard around XML parsing
        _rml_state.update(rml_enabled=False, base_uri=None, csv_path=None, prefixes={})
        return {}, None, None, None

    metadata_node = root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if metadata_node is None:
        _rml_state.update(rml_enabled=False, base_uri=None, csv_path=None, prefixes={})
        return {}, None, None, root

    csv_path_raw = metadata_node.attrib.get("csvPath", "")
    base_uri_raw = metadata_node.attrib.get("baseUri", "")

    csv_path = csv_path_raw.strip() or None
    base_uri = base_uri_raw.strip() or None

    prefixes: dict[str, str] = {}
    for preamble in metadata_node.findall("userObjectPreambleElement"):
        prefix = (preamble.attrib.get("rdfPrefix") or "").strip()
        iri = (preamble.attrib.get("rdfIRI") or "").strip()
        if prefix and iri:
            prefixes[prefix] = iri

    rml_enabled_raw = metadata_node.attrib.get("rmlEnabled")
    if rml_enabled_raw is None:
        rml_enabled = False
    else:
        lowered = rml_enabled_raw.strip().lower()
        rml_enabled = lowered in {"1", "true", "yes", "on"}

    _rml_state.update(
        rml_enabled=rml_enabled,
        base_uri=base_uri,
        csv_path=csv_path,
        prefixes=prefixes,
    )

    return prefixes, base_uri, csv_path, root
