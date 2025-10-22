from __future__ import annotations

from collections.abc import Iterator

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


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

    validator = pipeline.core.internal.data

    for item in individuals_and_arrows:
        if isinstance(item, Individual):
            _add_individual_type(
                blocks,
                item,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )
            continue

        validator._ensure_known_curie(
            item.identifier,
            prefixes,
            (
                f"An arrow has label '{item.identifier}', "
                "which is not a known object property or datatype property"
            ),
        )

        if item.is_datatype:
            datatype_properties.add(item.identifier)
            target_identifier = item.target
            literal_candidate = target_identifier.strip()
            if (
                literal_candidate
                and ":" in literal_candidate
                and not validator._is_absolute_iri(literal_candidate)
            ):
                validator._ensure_known_curie(
                    literal_candidate,
                    prefixes,
                    (
                        "The literal value "
                        f"'{literal_candidate}' does not correspond to a known CURIE"
                    ),
                )
            property_value = (target_identifier, True)
        else:
            object_properties.add(item.identifier)
            target_identifier = _replace_metacharacters(
                item.target,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )
            property_value = (target_identifier, False)

        source_identifier = _replace_metacharacters(
            item.source,
            metacharacter_substitutes,
            space_substitute,
            capitalisation_scheme,
        )

        block = blocks.setdefault((source_identifier, item.source), {})
        block.setdefault(item.identifier, set()).add(property_value)

    return blocks, object_properties, datatype_properties
