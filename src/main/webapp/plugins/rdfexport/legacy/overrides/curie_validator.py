from __future__ import annotations

from rdflib import Graph

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="data")
def _split_curie(curie: str) -> tuple[str, str]:
    active_attr = "__curie_validator_active_prefixes"
    prefixes = getattr(pipeline.core.internal.data, active_attr, None)
    manager = Graph().namespace_manager
    if isinstance(prefixes, dict):
        for prefix, iri in prefixes.items():
            manager.bind(prefix, iri, replace=True)

    if ":" not in curie:
        raise ValueError(f"CURIE '{curie}' must include a prefix separator")

    prefix, remainder = curie.split(":", 1)
    remainder = remainder.strip()

    try:
        manager.expand_curie(curie)
    except Exception as exc:  # pragma: no cover - defensive re-raise from rdflib
        raise ValueError(f"Failed to expand CURIE '{curie}'") from exc

    if not remainder:
        raise ValueError(f"CURIE '{curie}' is missing a reference component")

    return prefix, remainder


@override(phase="core", type="internal", role="data")
def _ensure_known_curie(
    curie: str, prefixes: dict[str, str], error_message: str
) -> tuple[str, str]:
    active_attr = "__curie_validator_active_prefixes"
    setattr(pipeline.core.internal.data, active_attr, prefixes)
    try:
        prefix, reference = _split_curie(curie)
    except ValueError as exc:
        raise NotInKnownException(error_message) from exc
    finally:
        if hasattr(pipeline.core.internal.data, active_attr):
            delattr(pipeline.core.internal.data, active_attr)

    if prefix not in prefixes:
        raise NotInKnownException(error_message)

    return prefix, reference


@override(phase="core", type="internal", role="control")
def individual_blocks(
    individuals_and_arrows: Iterator[Individual | Arrow],
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
    prefixes: dict[str, str],
) -> tuple[Blocks, set[str], set[str]]:
    blocks: Blocks = {}
    object_properties: set[str] = set()
    datatype_properties: set[str] = set()

    for individual_or_arrow in individuals_and_arrows:
        if isinstance(individual_or_arrow, Individual):
            _add_individual_type(
                blocks,
                individual_or_arrow,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )
            continue

        _ensure_known_curie(
            individual_or_arrow.identifier,
            prefixes,
            (
                f"An arrow has label '{individual_or_arrow.identifier}', "
                "which is not a known object property or datatype property"
            ),
        )

        if individual_or_arrow.is_datatype:
            datatype_properties.add(individual_or_arrow.identifier)
            target_identifier = individual_or_arrow.target
            literal_candidate = target_identifier.strip()
            if (
                ":" in literal_candidate
                and "://" not in literal_candidate
                and literal_candidate
            ):
                prefix, reference = literal_candidate.split(":", 1)
                if (
                    prefix
                    and (prefix[0].isalpha() or prefix[0] == "_")
                    and all(ch.isalnum() or ch in "._-" for ch in prefix[1:])
                    and not (reference and any(char.isspace() for char in reference))
                ):
                    manager = Graph().namespace_manager
                    for known_prefix, iri in prefixes.items():
                        manager.bind(known_prefix, iri, replace=True)
                    try:
                        manager.expand_curie(literal_candidate)
                    except Exception as exc:  # pragma: no cover - defensive re-raise
                        raise NotInKnownException(
                            (
                                "The literal value "
                                f"'{literal_candidate}' does not correspond to a known CURIE"
                            )
                        ) from exc
        else:
            object_properties.add(individual_or_arrow.identifier)
            target_identifier = _replace_metacharacters(
                individual_or_arrow.target,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )

        source_identifier = _replace_metacharacters(
            individual_or_arrow.source,
            metacharacter_substitutes,
            space_substitute,
            capitalisation_scheme,
        )

        try:
            block = blocks[(source_identifier, individual_or_arrow.source)]
        except KeyError:
            blocks[(source_identifier, individual_or_arrow.source)] = {
                individual_or_arrow.identifier: {target_identifier}
            }
            continue

        try:
            block[individual_or_arrow.identifier].add(target_identifier)
        except KeyError:
            block[individual_or_arrow.identifier] = {target_identifier}

    return blocks, object_properties, datatype_properties
