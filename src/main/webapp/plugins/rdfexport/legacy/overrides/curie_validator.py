from __future__ import annotations

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


@override(phase="core", type="internal", role="data")
def _verify_is_ric_class(ric_class: str, prefixes: dict[str, str]):
    detector = getattr(
        getattr(pipeline.core.rdf.control, "RMLSerializer", None),
        "detect_string_template",
        None,
    )
    if callable(detector):
        try:
            if detector(ric_class):
                return
        except Exception:
            pass

    _ensure_known_curie(ric_class, prefixes, f"Not a known class: {ric_class}")


@override(phase="core", type="xml", role="data")
def _cell_is_literal(self, candidate: Element) -> bool:
    is_literal = any(
        literal_cell is candidate for literal_cell, _ in self.literal_cells
    )
    if is_literal:
        decorations_attr = "__drawio_literal_registry"
        registry = getattr(pipeline.core.internal.data, decorations_attr, None)
        if isinstance(registry, dict):
            cell_id = candidate.attrib.get("id")
            if cell_id in registry:
                registry[cell_id]["connected"] = True
    return is_literal


@override(phase="core", type="internal", role="control")
def individual_blocks(
    individuals_and_arrows: Iterator[Individual | Arrow],
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
    prefixes: dict[str, str],
    *,
    apply_metacharacter_substitution: bool = True,
) -> tuple[Blocks, set[str], set[str]]:
    blocks: Blocks = {}
    object_properties: set[str] = set()
    datatype_properties: set[str] = set()

    def _looks_like_absolute_uri(value: str) -> bool:
        if not value or any(ch.isspace() for ch in value):
            return False
        if "://" in value:
            return True
        scheme, _, remainder = value.partition(":")
        return scheme.lower() in {"urn", "tag"} and bool(remainder.strip())

    def _add_individual_without_substitution(individual: Individual) -> None:
        identifier = individual.identifier
        try:
            block = blocks[(identifier, individual.identifier)]
        except KeyError:
            blocks[(identifier, individual.identifier)] = {
                "Types": {individual.ric_class}
            }
            return

        try:
            block["Types"].add(individual.ric_class)
        except KeyError:
            block["Types"] = {individual.ric_class}

    def _maybe_replace(identifier: str) -> str:
        if not apply_metacharacter_substitution:
            return identifier
        return _replace_metacharacters(
            identifier,
            metacharacter_substitutes,
            space_substitute,
            capitalisation_scheme,
        )

    for individual_or_arrow in individuals_and_arrows:
        if isinstance(individual_or_arrow, Individual):
            if apply_metacharacter_substitution:
                _add_individual_type(
                    blocks,
                    individual_or_arrow,
                    metacharacter_substitutes,
                    space_substitute,
                    capitalisation_scheme,
                )
            else:
                _add_individual_without_substitution(individual_or_arrow)
            continue

        identifier = individual_or_arrow.identifier
        normalized_identifier = identifier
        allow_absolute_identifier = False
        if _looks_like_absolute_uri(identifier):
            for prefix_key, iri in prefixes.items():
                if identifier.startswith(iri) and identifier[len(iri) :]:
                    normalized_identifier = f"{prefix_key}:{identifier[len(iri) :]}"
                    break
            else:
                allow_absolute_identifier = True

        if not allow_absolute_identifier:
            _ensure_known_curie(
                normalized_identifier,
                prefixes,
                (
                    f"An arrow has label '{normalized_identifier}', "
                    "which is not a known object property or datatype property"
                ),
            )

        if individual_or_arrow.is_datatype:
            datatype_properties.add(normalized_identifier)
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
            property_value = (target_identifier, True)
        else:
            object_properties.add(normalized_identifier)
            target_identifier = _maybe_replace(individual_or_arrow.target)
            property_value = (target_identifier, False)

        source_identifier = _maybe_replace(individual_or_arrow.source)

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
