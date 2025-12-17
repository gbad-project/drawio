from __future__ import annotations

from rdflib.namespace import NamespaceManager

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="data")
class DeimplementedException(Exception):
    """Can be raised when overrides invalidate."""

    default_message = "This has been discontinued by an override"

    def __init__(self, message: str | None = None) -> None:
        self.default_message
        self.message = (
            f"{self.default_message}. {message}" if message else self.default_message
        )
        super().__init__(self.message)


@override(phase="core", type="internal", role="data")
def _split_curie(*args, **kwargs):
    raise pipeline.core.internal.data.DeimplementedException(
        "Use `pipeline.core.internal.data.resolve_curie(curie: str, ns_mgr: NamespaceManager) -> URIRef`"
    )


@override(phase="core", type="internal", role="data")
def _ensure_known_curie(*args, **kwargs):
    raise pipeline.core.internal.data.DeimplementedException(
        "Use `pipeline.core.internal.data.resolve_curie(curie: str, ns_mgr: NamespaceManager) -> URIRef`"
    )


@override(phase="core", type="internal", role="data")
def resolve_curie(curie: str, ns_mgr: NamespaceManager) -> URIRef:
    if ":" not in curie:
        raise ValueError(f"CURIE {curie!r} must include a prefix separator")

    _, remainder = curie.split(":", 1)
    remainder = remainder.strip()

    if not remainder:
        raise ValueError(f"CURIE {curie!r} is missing a reference component")

    try:
        expanded = ns_mgr.expand_curie(curie)
    except Exception as exc:  # pragma: no cover - defensive re-raise from rdflib
        raise NotInKnownException(f"Failed to expand CURIE '{curie}'") from exc

    return expanded


@override(phase="core", type="internal", role="data")
def looks_like_iri(candidate: str) -> str | bool:
    """
    Check if a string looks like an IRI.

    Handles variants: [
        "absolute-iri",
        "curie",
        "relative-iri",
    ]

    Otherwise returns `False`.
    """
    if not candidate or any(ch.isspace() for ch in candidate):
        return False
    scheme, _, remainder = candidate.partition(":")
    if scheme and remainder.startswith("//"):
        return "absolute-iri"
    if candidate.startswith(("/", "#")):
        return "relative-iri"
    if bool(remainder.strip()):
        if scheme.lower() in {"urn", "tag", "ni"}:
            return "absolute-iri"
        # the below supposedly means no whitespaces
        elif len(remainder.split()) == 1:
            return "curie"
    return False
