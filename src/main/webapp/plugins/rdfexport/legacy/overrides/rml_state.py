"""Shared state helpers for RML override coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class RmlMetadata:
    """Tracks DrawIO metadata relevant for RML generation."""

    rml_enabled: bool = False
    base_uri: Optional[str] = None
    csv_path: Optional[str] = None
    prefixes: Dict[str, str] = field(default_factory=dict)

    def merge_prefixes(self, updates: Dict[str, str]) -> None:
        self.prefixes.update({key: value for key, value in updates.items() if value})


_STATE = RmlMetadata()
_UNSET: Any = object()


def current() -> RmlMetadata:
    """Return a mutable reference to the shared metadata instance."""

    return _STATE


def reset() -> None:
    """Clear captured state (primarily for tests)."""

    _STATE.rml_enabled = False
    _STATE.base_uri = None
    _STATE.csv_path = None
    _STATE.prefixes.clear()


def update(
    *,
    rml_enabled: Optional[bool] = None,
    base_uri: Optional[str] = _UNSET,
    csv_path: Optional[str] = _UNSET,
    prefixes: Optional[Dict[str, str]] = None,
) -> None:
    """Update state in place, allowing explicit resets."""

    if rml_enabled is not None:
        _STATE.rml_enabled = rml_enabled
    if base_uri is not _UNSET:
        _STATE.base_uri = base_uri  # type: ignore[assignment]
    if csv_path is not _UNSET:
        _STATE.csv_path = csv_path  # type: ignore[assignment]
    if prefixes is not None:
        _STATE.prefixes.clear()
        if prefixes:
            _STATE.merge_prefixes(prefixes)
