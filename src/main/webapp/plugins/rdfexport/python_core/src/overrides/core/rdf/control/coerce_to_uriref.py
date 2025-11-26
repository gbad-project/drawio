from __future__ import annotations

import typing
import logging

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder

from aicode.python_core.src.overrides.core.rdf.control.serialization_helper import (
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
    resolve_curie = pipeline.core.internal.data.resolve_curie
    looks_like_iri = pipeline.core.internal.data.looks_like_iri
    UnableToCoerceException = pipeline.core.rdf.data.UnableToCoerceException
    UnknownCuriePrefixException = pipeline.core.rdf.data.UnknownCuriePrefixException

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

    def coerce_candidate(
        candidate: str,
    ) -> tuple[
        URIRef,
        typing.Literal["absolute-iri", "relative-iri", "curie", "mint-from-literal"],
    ]:
        """
        Returns a meaningful value or raises an appropriate exception.

        Note that `mint-from-literal` only occurs here as a value
        and not in `pipeline.core.internal.data.looks_like_iri()`
        """
        iri_variant = looks_like_iri(candidate)
        namespace_map: dict[str, Namespace] = cfg.namespace_map()
        # Note that this is set to empty string at RDFSerializationHelper
        # init if is None, so the correct default prefix is always there
        default_ns: Namespace = namespace_map.get(cfg.prefix)
        coerced = None
        if iri_variant == "absolute-iri":
            coerced = URIRef(candidate)
        elif iri_variant == "relative-iri":
            base_uri: str | None = getattr(cfg.graph, "base", None)
            if base_uri:
                coerced = Namespace(base_uri)[candidate]
            else:
                raise UnableToCoerceException(
                    candidate,
                    URIRef,
                    "Unable to resolve what looks like a relative IRI because the base IRI is not set or could not pass it through to the serializer",
                )
        elif iri_variant == "curie":
            try:
                coerced = resolve_curie(candidate, cfg.graph.namespace_manager)
            except (
                ValueError,
                NotInKnownException,
                KeyError,
                TypeError,
            ) as e:
                raise UnknownCuriePrefixException(candidate, URIRef, e)
        elif isinstance(iri_variant, bool) and (not iri_variant):
            if mint_from_literal:
                iri_variant = "mint-from-literal"
                if default_ns:
                    # Not catching TypeError here because .namespace_map()
                    # upstream guarantees Namespace() objects as map values,
                    # and candidate is guaranteed to be a str by host function
                    coerced = default_ns[candidate]
                else:
                    raise UnableToCoerceException(
                        candidate,
                        URIRef,
                        "Unable to mint an individual from literal because the default namespace is not set or could not pass it through to the serializer",
                    )
            else:
                raise UnableToCoerceException(
                    candidate,
                    URIRef,
                    "Exhausted all possibilities: Does not look like any of: absolute IRI, relative IRI, CURIE",
                )
        else:
            raise RuntimeError from UnableToCoerceException(
                iri_variant, URIRef, "Unhandled IRI variant"
            )
        return coerced, iri_variant

    def best_guess(norm_value, decoded_norm_value) -> URIRef:
        """Return our single best guess of an IRI,
        or raise an appropriate error."""
        norm_coerced = decoded_norm_coerced = None
        err_norm = err_decoded_norm = None
        norm_iri_variant = decoded_norm_iri_variant = None
        try:
            norm_coerced, norm_iri_variant = coerce_candidate(norm_value)
            if (
                norm_value == decoded_norm_value
            ):  # wicked case! used to break everything
                return norm_coerced
        except Exception as e:
            err_norm = e

        # disable all logging to silence invalid URIRef warnings,
        # as for decoded these are not expected to be valid anyway
        logging.disable(logging.CRITICAL)
        try:
            decoded_norm_coerced, decoded_norm_iri_variant = coerce_candidate(
                decoded_norm_value
            )
        except Exception as e:
            err_decoded_norm = e
        finally:
            # restore logging
            logging.disable(logging.NOTSET)

        matched = (bool(norm_coerced), bool(decoded_norm_coerced))
        if matched == (False, False):
            # both failed — raise from raw
            raise err_norm
        elif matched == (False, True):
            # raw failed, decoded succeeded
            return decoded_norm_coerced
        else:
            if norm_iri_variant == "mint-from-literal":
                # Exploring curie options
                if isinstance(err_decoded_norm, UnknownCuriePrefixException):
                    # looks like a curie but could not expand - deny to coerce
                    raise err_decoded_norm
                elif decoded_norm_iri_variant == "curie":
                    # ..then perhaps we did a great job decoding
                    # and caught a curie! Return it
                    return decoded_norm_coerced
            # whenever else we have coerced raw, return it
            return norm_coerced
            # Tentatively, for abs and rel IRIs
            # as well as minted-from-literal, no
            # decoding is required at serialization
            # because the value will already have been
            # appropriately metacharacter-replaced

    return best_guess(norm_value, decoded_norm_value)
