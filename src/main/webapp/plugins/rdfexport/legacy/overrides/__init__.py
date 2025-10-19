"""Override modules injected into the generated DrawIO parser."""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_ROOT = _PACKAGE_ROOT / "legacy"

for candidate in (_PACKAGE_ROOT, _LEGACY_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

__all__ = [
    "curie_validator",
    "rml_builder",
    "rml_graph_class",
    "rml_metadata",
    "rml_pipeline",
    "rml_state",
]
