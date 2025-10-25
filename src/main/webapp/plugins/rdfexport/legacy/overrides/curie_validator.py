from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from meta_builder.drawio_meta_builder import override
from rdflib import BNode
from rdflib.namespace import SKOS
import urllib.parse

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
            property_value = (target_identifier, True)
        else:
            object_properties.add(individual_or_arrow.identifier)
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
                individual_or_arrow.identifier: {property_value}
            }
            continue

        values = block.get(individual_or_arrow.identifier)
        if values is None:
            block[individual_or_arrow.identifier] = {property_value}
        else:
            values.add(property_value)

    return blocks, object_properties, datatype_properties


@override(phase="core", type="rdf", role="control")
def serialise_to_graph(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    graph_cls: type[Graph] = Graph,
    graph_kwargs: dict[str, Any] | None = None,
) -> Graph:
    graph_kwargs = graph_kwargs or {}

    toolkit_attr = "__drawio_serialisation_toolkit"
    factory_attr = "__drawio_serialisation_toolkit_factory"

    toolkit = getattr(pipeline.core.rdf.control, toolkit_attr, None)
    if toolkit is None:
        factory = getattr(pipeline.core.rdf.control, factory_attr, None)
        if factory is None:

            class DrawIOSerialisationToolkit:
                @staticmethod
                def _is_absolute_iri(candidate: str) -> bool:
                    if not candidate:
                        return False
                    try:
                        parsed = urllib.parse.urlparse(candidate)
                    except Exception:
                        return False
                    return bool(parsed.scheme and (parsed.netloc or parsed.path))

                def create_workspace(
                    self,
                    serialisation_config: SerialisationConfig,
                    prefixes: dict[str, str],
                    graph_cls: type[Graph],
                    graph_kwargs: dict[str, Any],
                ) -> tuple[Graph, dict[str, Namespace], str | None, str | None]:
                    graph = graph_cls(**graph_kwargs)

                    prefix = serialisation_config.prefix
                    prefix_iri = serialisation_config.prefix_iri or get_prefix_iri(
                        serialisation_config.ontology_iri
                    )

                    namespace_map: dict[str, Namespace] = {}
                    fallback_namespace: Namespace | None = None
                    if prefix_iri and self._is_absolute_iri(prefix_iri):
                        fallback_namespace = Namespace(prefix_iri)

                    for prefix_key, uri in prefixes.items():
                        if self._is_absolute_iri(uri):
                            namespace = Namespace(uri)
                        elif fallback_namespace is not None:
                            namespace = fallback_namespace
                        else:
                            raise ParseException(f"Prefix IRI '{uri}' looks invalid")

                        graph.bind(prefix_key, namespace, replace=True)
                        namespace_map[prefix_key] = namespace

                    if prefix and prefix_iri:
                        graph.bind(prefix, Namespace(prefix_iri), replace=True)

                    return graph, namespace_map, prefix, prefix_iri

                @staticmethod
                def extract_absolute_overrides(blocks: Blocks) -> dict[str, str]:
                    return {
                        individual_id: individual_label
                        for individual_id, individual_label in blocks.keys()
                        if "://" in individual_label
                    }

                def resolve_entity_uri(
                    self,
                    identifier: str,
                    prefix: str | None,
                    prefix_iri: str | None,
                    absolute_overrides: dict[str, str],
                ) -> URIRef:
                    if identifier in absolute_overrides:
                        return URIRef(absolute_overrides[identifier])
                    if prefix and prefix_iri:
                        return Namespace(prefix_iri)[identifier]
                    if prefix_iri:
                        return URIRef(f"{prefix_iri}{identifier}")
                    return URIRef(identifier)

                @staticmethod
                def coerce_literal(value: Any) -> Literal:
                    if isinstance(value, Literal):
                        return value

                    literal_candidate = value
                    if isinstance(literal_candidate, int) or (
                        isinstance(literal_candidate, str)
                        and literal_candidate.isnumeric()
                    ):
                        return Literal(literal_candidate, datatype=XSD.integer)

                    if isinstance(literal_candidate, float):
                        return Literal(literal_candidate, datatype=XSD.float)

                    if isinstance(literal_candidate, str):
                        try:
                            datetime.strptime(literal_candidate, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            return Literal(literal_candidate)
                        else:
                            return Literal(literal_candidate, datatype=XSD.date)

                    return Literal(literal_candidate)

                @staticmethod
                def value_sort_key(value: Any) -> tuple[int, str]:
                    if isinstance(value, tuple):
                        return (0, f"{value[0]}")
                    return (1, f"{value}")

                @staticmethod
                def unpack_value(
                    prop: str,
                    raw_value: Any,
                    object_properties: set[str],
                    datatype_properties: set[str],
                ) -> tuple[Any, bool]:
                    if (
                        isinstance(raw_value, tuple)
                        and len(raw_value) == 2
                        and isinstance(raw_value[1], bool)
                    ):
                        return raw_value
                    is_literal = (
                        prop in datatype_properties and prop not in object_properties
                    )
                    return raw_value, is_literal

                def iter_subjects(
                    self,
                    blocks: Blocks,
                    prefix: str | None,
                    prefix_iri: str | None,
                    absolute_overrides: dict[str, str],
                ) -> Iterator[tuple[str, str, URIRef, dict[str, set[Any]]]]:
                    for (
                        individual_id,
                        individual_label,
                    ), types_and_facts in blocks.items():
                        yield (
                            individual_id,
                            individual_label,
                            self.resolve_entity_uri(
                                individual_id,
                                prefix,
                                prefix_iri,
                                absolute_overrides,
                            ),
                            types_and_facts,
                        )

            def factory() -> DrawIOSerialisationToolkit:
                return DrawIOSerialisationToolkit()

            setattr(pipeline.core.rdf.control, factory_attr, factory)

        toolkit = factory()
        setattr(pipeline.core.rdf.control, toolkit_attr, toolkit)

    graph, namespace_map, prefix, prefix_iri = toolkit.create_workspace(
        serialisation_config, prefixes, graph_cls, graph_kwargs
    )

    if serialisation_config.include_preamble:
        ontology_iri = serialisation_config.ontology_iri or get_ontology_iri()
        graph.add((URIRef(ontology_iri), RDF.type, OWL.Ontology))
        graph.add((URIRef(ontology_iri), OWL.imports, URIRef(prefixes["rico"])))

    for prop in sorted(
        prop for prop in object_properties if not prop.startswith("rico:")
    ):
        prop_prefix, prop_name = prop.split(":")
        prop_uri = namespace_map[prop_prefix][prop_name]
        graph.add((prop_uri, RDF.type, OWL.ObjectProperty))

    for prop in sorted(
        prop for prop in datatype_properties if not prop.startswith("rico:")
    ):
        prop_prefix, prop_name = prop.split(":")
        prop_uri = namespace_map[prop_prefix][prop_name]
        graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))

    absolute_overrides = toolkit.extract_absolute_overrides(blocks)

    for (
        individual_id,
        individual_label,
        individual_uri,
        types_and_facts,
    ) in toolkit.iter_subjects(blocks, prefix, prefix_iri, absolute_overrides):
        graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        for rdf_type in types_and_facts.get("Types", set()):
            type_prefix, type_name = rdf_type.split(":", 1)
            graph.add((individual_uri, RDF.type, namespace_map[type_prefix][type_name]))

        if serialisation_config.include_label:
            graph.add((individual_uri, RDFS.label, Literal(individual_label)))

        for prop, values in types_and_facts.items():
            if prop == "Types":
                continue

            prop_prefix, prop_name = prop.split(":", 1)
            prop_uri = namespace_map[prop_prefix][prop_name]

            for raw_value in values:
                value, is_literal = toolkit.unpack_value(
                    prop, raw_value, object_properties, datatype_properties
                )

                if not is_literal:
                    target_uri = toolkit.resolve_entity_uri(
                        str(value), prefix, prefix_iri, absolute_overrides
                    )
                    graph.add((individual_uri, prop_uri, target_uri))
                else:
                    literal_value = toolkit.coerce_literal(value)
                    graph.add((individual_uri, prop_uri, literal_value))

    decorations_attr = "__drawio_literal_registry"
    decoration_registry = getattr(pipeline.core.internal.data, decorations_attr, {})
    decoration_values = [
        entry.get("value")
        for entry in decoration_registry.values()
        if isinstance(entry, dict) and entry.get("value") and not entry.get("connected")
    ]
    if decoration_values:
        if serialisation_config.ontology_iri:
            decoration_subject = URIRef(serialisation_config.ontology_iri)
        else:
            decoration_subject = BNode()
        for note in decoration_values:
            graph.add((decoration_subject, SKOS.note, Literal(note)))

    if hasattr(pipeline.core.internal.data, decorations_attr):
        delattr(pipeline.core.internal.data, decorations_attr)

    return graph
