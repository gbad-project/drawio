from __future__ import annotations

from rdflib import Graph
from xml.etree.ElementTree import Element

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from legacy.draw_io_parser import pipeline
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


@override(phase="core", type="xml", role="data")
def _extract_individual_and_arrow_and_literal_cells(self, prefixes) -> None:
    classifier_cls = pipeline.core.xml.data.DrawIOCellClassifier
    decorations_attr = getattr(
        classifier_cls,
        "DECORATION_REGISTRY_ATTR",
        "__drawio_literal_registry",
    )
    default_standalone_type = getattr(
        classifier_cls,
        "DEFAULT_STANDALONE_TYPE",
        "rico:Thing",
    )
    classifier = classifier_cls(self, prefixes)
    decorations: dict[str, dict[str, object]] = {}
    setattr(pipeline.core.internal.data, decorations_attr, decorations)
    registered_individuals: set[tuple[str, str]] = set()

    try:
        if len(self.draw_io_xml_tree[0][0][0]) == 0:
            raise NothingToParseException
    except IndexError as key_error:
        raise NothingToParseException from key_error

    for cell in self.draw_io_xml_tree[0][0][0]:
        if cell.tag != "mxCell":
            raise ParseException(
                "Could not parse XML tree: expecting an element with tag "
                f"'mxCell', but had tag '{cell.tag}'"
            )

        try:
            cell_value = self._value_of(cell)
        except _NoValueException:
            continue

        if not cell_value:
            self._add_arrow_if_find_label(cell)
            continue

        classification = classifier.classify(cell, cell_value)
        kind_name = getattr(classification.kind, "name", "")

        if kind_name == "ARROW_LABEL":
            continue

        if kind_name == "TYPED_INDIVIDUAL":
            parent = classification.parent_cell
            identifier = classification.parent_identifier
            if parent is None or not identifier:
                continue

            dimensions = self._dimensions(parent)
            seen_classes: set[str] = set()
            had_tokens = False
            for token in classification.tokens:
                candidate = token.strip()
                if not candidate:
                    continue
                had_tokens = True
                if candidate in seen_classes:
                    continue
                try:
                    _verify_is_ric_class(candidate, prefixes)
                except NotInKnownException as exc:
                    raise NotInKnownException(
                        (
                            f"The node '{identifier}' declares rdf:type "
                            f"'{candidate}', which is not defined by the available prefixes.'"
                        )
                    ) from exc
                seen_classes.add(candidate)
                key = (identifier, candidate)
                if key in registered_individuals:
                    continue
                individual = Individual(identifier, candidate)
                self.individual_cells.append((cell, individual, dimensions))
                registered_individuals.add(key)

            if not had_tokens:
                raise NotInKnownException(
                    (
                        f"The node '{identifier}' declares an rdf:type value "
                        "but no CURIE tokens could be parsed."
                    )
                )
            continue

        if kind_name == "STANDALONE_INDIVIDUAL":
            identifier = classification.identifier or classification.raw_value
            dimensions = self._dimensions(cell)
            types = classification.tokens or [default_standalone_type]
            seen_types: set[str] = set()
            for rdf_type in types:
                candidate = rdf_type.strip()
                if not candidate:
                    continue
                if candidate in seen_types:
                    continue
                try:
                    _verify_is_ric_class(candidate, prefixes)
                except NotInKnownException as exc:
                    raise NotInKnownException(
                        (
                            f"The standalone node '{identifier}' declares rdf:type "
                            f"'{candidate}', which is not defined by the available prefixes.'"
                        )
                    ) from exc
                seen_types.add(candidate)
                key = (identifier, candidate)
                if key in registered_individuals:
                    continue
                individual = Individual(identifier, candidate)
                self.individual_cells.append((cell, individual, dimensions))
                registered_individuals.add(key)
            continue

        if kind_name == "DECORATION":
            cell_id = cell.attrib.get("id")
            if cell_id:
                decorations[cell_id] = {
                    "value": classification.raw_value,
                    "connected": False,
                }
            continue

        self.literal_cells.append((cell, self._dimensions(cell)))
        cell_id = cell.attrib.get("id")
        if cell_id:
            decorations[cell_id] = {
                "value": classification.raw_value,
                "connected": False,
            }


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
    from rdflib import BNode
    from rdflib.namespace import SKOS

    graph_kwargs = graph_kwargs or {}
    graph = graph_cls(**graph_kwargs)

    for prefix, uri in prefixes.items():
        graph.bind(prefix, Namespace(uri), replace=True)
    if serialisation_config.prefix:
        graph.bind(
            serialisation_config.prefix,
            Namespace(
                serialisation_config.prefix_iri
                or get_prefix_iri(serialisation_config.ontology_iri)
            ),
        )

    if serialisation_config.include_preamble:
        ontology_iri = serialisation_config.ontology_iri or get_ontology_iri()
        graph.add((URIRef(ontology_iri), RDF.type, OWL.Ontology))
        graph.add((URIRef(ontology_iri), OWL.imports, URIRef(prefixes["rico"])))

    for prop in sorted(
        prop for prop in object_properties if not prop.startswith("rico:")
    ):
        prop_prefix, prop_name = prop.split(":")
        prop_uri = Namespace(prefixes[prop_prefix])[prop_name]
        graph.add((prop_uri, RDF.type, OWL.ObjectProperty))

    for prop in sorted(
        prop for prop in datatype_properties if not prop.startswith("rico:")
    ):
        prop_prefix, prop_name = prop.split(":")
        prop_uri = Namespace(prefixes[prop_prefix])[prop_name]
        graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))

    absolute_overrides = {
        individual_id: individual_label
        for individual_id, individual_label in blocks.keys()
        if "://" in individual_label
    }

    prefix = serialisation_config.prefix
    prefix_iri = serialisation_config.prefix_iri or get_prefix_iri(
        serialisation_config.ontology_iri
    )

    for (individual_id, individual_label), types_and_facts in blocks.items():
        if individual_id in absolute_overrides:
            individual_uri = URIRef(absolute_overrides[individual_id])
        elif prefix and serialisation_config.prefix_iri:
            individual_uri = Namespace(serialisation_config.prefix_iri)[individual_id]
        elif prefix_iri:
            individual_uri = URIRef(f"{prefix_iri}{individual_id}")
        else:
            individual_uri = URIRef(individual_id)

        graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        for rdf_type in types_and_facts.get("Types", set()):
            type_prefix, type_name = rdf_type.split(":")
            graph.add(
                (individual_uri, RDF.type, Namespace(prefixes[type_prefix])[type_name])
            )

        if serialisation_config.include_label:
            graph.add((individual_uri, RDFS.label, Literal(individual_label)))

        for prop, values in types_and_facts.items():
            if prop == "Types":
                continue

            prop_prefix, prop_name = prop.split(":")
            prop_uri = Namespace(prefixes[prop_prefix])[prop_name]

            for value in values:
                if prop in object_properties:
                    if value in absolute_overrides:
                        target_uri = URIRef(absolute_overrides[value])
                    elif prefix and serialisation_config.prefix_iri:
                        target_uri = Namespace(serialisation_config.prefix_iri)[value]
                    elif prefix_iri:
                        target_uri = URIRef(f"{prefix_iri}{value}")
                    else:
                        target_uri = URIRef(value)
                    graph.add((individual_uri, prop_uri, target_uri))
                elif prop in datatype_properties:
                    if isinstance(value, int) or (
                        isinstance(value, str) and value.isnumeric()
                    ):
                        literal_value = Literal(value, datatype=XSD.integer)
                    elif isinstance(value, float):
                        literal_value = Literal(value, datatype=XSD.float)
                    else:
                        try:
                            datetime.strptime(value, "%Y-%m-%d")
                            literal_value = Literal(value, datatype=XSD.date)
                        except (ValueError, TypeError):
                            literal_value = Literal(value)
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
