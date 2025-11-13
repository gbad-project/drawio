from __future__ import annotations

from rdflib.namespace import NamespaceManager

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="data")
def _split_curie(curie: str, prefixes: dict[str, str]) -> tuple[str, str]:
    if ":" not in curie:
        raise ValueError(f"CURIE {curie!r} must include a prefix separator")

    prefix, remainder = curie.split(":", 1)
    remainder = remainder.strip()

    if not remainder:
        raise ValueError(f"CURIE {curie!r} is missing a reference component")

    try:
        manager = NamespaceManager(Graph())
        if isinstance(prefixes, dict):
            for p, i in prefixes.items():
                manager.bind(p, i, replace=True)
        manager.expand_curie(curie)
    except Exception as exc:  # pragma: no cover - defensive re-raise from rdflib
        raise ValueError(f"Failed to expand CURIE '{curie}'") from exc

    return prefix, remainder


@override(phase="core", type="internal", role="data")
def _ensure_known_curie(
    curie: str, prefixes: dict[str, str], error_message: str
) -> tuple[str, str]:
    try:
        prefix, reference = _split_curie(curie, prefixes)
    except ValueError as e:
        raise NotInKnownException(error_message) from e

    return prefix, reference


@override(phase="core", type="internal", role="data")
def looks_like_iri(candidate: str) -> str | bool:
    """Check if a string is an absolute IRI."""
    if not candidate or any(ch.isspace() for ch in candidate):
        return False
    if "://" in candidate:
        return "absolute-iri"
    scheme, _, remainder = candidate.partition(":")
    if bool(remainder.strip()):
        if scheme.lower() in {"urn", "tag", "ni"}:
            return "absolute-iri"
        elif len(remainder.split()) == 1:
            return "curie"
    if candidate.startswith(("/", "#")):
        return "relative-iri"
    return False
