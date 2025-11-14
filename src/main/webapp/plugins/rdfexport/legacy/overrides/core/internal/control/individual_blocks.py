from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="control")
def _add_individual_type(
    blocks: Blocks,
    individual: Individual,
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
) -> None:
    _replace_metacharacters = pipeline.pre.rdf.data._replace_metacharacters

    individual_id = _replace_metacharacters(
        individual.identifier,
        metacharacter_substitutes,
        space_substitute,
        capitalisation_scheme,
    )
    rdf_type = individual.ric_class
    try:
        block = blocks[(individual_id, individual.identifier)]
    except KeyError:
        blocks[(individual_id, individual.identifier)] = {"Types": {rdf_type}}
        return
    try:
        block["Types"].add(rdf_type)
    except KeyError:
        block["Types"] = {rdf_type}


@override(phase="core", type="internal", role="control")
def individual_blocks(
    individuals_and_arrows: Iterator[Individual | Arrow],
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
    prefixes: dict[str, str],
) -> tuple[Blocks, set[str], set[str]]:
    _ensure_known_curie = pipeline.core.internal.data._ensure_known_curie
    _replace_metacharacters = pipeline.pre.rdf.data._replace_metacharacters
    _add_individual_type = pipeline.core.internal.control._add_individual_type

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

        identifier = individual_or_arrow.identifier
        normalized_identifier = identifier

        if individual_or_arrow.is_datatype:
            datatype_properties.add(normalized_identifier)
            target_identifier = individual_or_arrow.target
            property_value = (target_identifier, True)
        else:
            object_properties.add(normalized_identifier)
            target_identifier = _replace_metacharacters(
                individual_or_arrow.target,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )
            property_value = (target_identifier, False)

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
                normalized_identifier: {property_value}
            }
            continue

        values = block.get(normalized_identifier)
        if values is None:
            block[normalized_identifier] = {property_value}
        else:
            values.add(property_value)

    return blocks, object_properties, datatype_properties
