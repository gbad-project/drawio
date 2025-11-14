from __future__ import annotations


from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder

from legacy.overrides.core.rdf.control.serialization_helper import (
    RDFSerializationHelper,
)


@override(phase="core", type="rdf", role="control")
def coerce_to_uriref(
    cfg: RDFSerializationHelper,
    value: str,
    mint_from_literal: bool = True,
) -> URIRef:
    """
    Resolve an individual ID/type/object fact to its URI.

    If what looks like a Literal is passed, urlencodes and mints
    entity to default namespace unless mint_from_literal = False;
    in the latter case raises UnableToCoerceException.
    """
    _split_curie = pipeline.core.internal.data._split_curie
    looks_like_iri = pipeline.core.internal.data.looks_like_iri
    UnableToCoerceException = pipeline.core.rdf.data.UnableToCoerceException

    def normalize(value) -> tuple[str, str]:
        if value is None:
            raise UnableToCoerceException(
                value, Literal, "Unexpected for a URIRef candidate"
            )
        norm_value = str(value).strip()
        decoded_norm_value = urllib.parse.unquote(norm_value)
        return norm_value, decoded_norm_value

    norm_value, decoded_norm_value = normalize(value)
    if not decoded_norm_value:
        raise UnableToCoerceException(value, URIRef, "Entity is empty")
    for candidate in (norm_value, decoded_norm_value):
        iri_variant = looks_like_iri(candidate)
        if iri_variant == "absolute-iri":
            return URIRef(candidate)
        elif iri_variant == "relative-iri":
            if cfg.prefix_iri:
                return Namespace(cfg.prefix_iri)[candidate]
            else:
                if candidate == norm_value:  # try decoded value
                    continue
                raise UnableToCoerceException(
                    candidate,
                    URIRef,
                    "Unable to resolve what looks like a relative IRI because prefix IRI is not set or could not pass through to the serializer",
                )
        elif iri_variant == "curie":
            try:
                prefix, reference = _split_curie(candidate, cfg.prefixes)
                return cfg.namespace_map[prefix][reference]
            except (
                ValueError,
                NotInKnownException,
                KeyError,
                TypeError,
            ) as e:
                if candidate == norm_value:  # try decoded value
                    continue
                raise UnableToCoerceException(
                    candidate,
                    URIRef,
                    f"Unable to resolve what looks like a CURIE: {e}",
                )
        elif isinstance(iri_variant, bool) and (not iri_variant):
            if mint_from_literal:
                return Namespace(cfg.prefix_iri)[candidate]
            else:
                if candidate == norm_value:  # try decoded value
                    continue
                raise UnableToCoerceException(
                    candidate,
                    URIRef,
                    "Exhausted all possibilities: Does not look like any of: absolute IRI, relative IRI, CURIE",
                )
        else:
            raise RuntimeError(f"Unhandled IRI variant: {iri_variant!r}")
