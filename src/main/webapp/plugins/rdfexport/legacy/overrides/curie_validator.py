from __future__ import annotations

from rdflib import BNode, Graph
from rdflib.namespace import SKOS
from xml.etree.ElementTree import Element

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

from legacy.overrides.node_classifier import (
    DrawIONodeClassifier,
    LiteralInfo,
    NodeClassification,
    NodeKind,
)


_LITERAL_REGISTRY_ATTR = "__drawio_literal_registry"


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
    try:
        if len(self.draw_io_xml_tree[0][0][0]) == 0:
            raise NothingToParseException
    except IndexError as key_error:
        raise NothingToParseException from key_error

    classifier = DrawIONodeClassifier(prefixes)
    node_classifications: dict[Element, NodeClassification] = {}
    literal_registry: dict[Element, LiteralInfo] = {}
    setattr(self, "_node_classifications", node_classifications)
    setattr(self, "_literal_registry", literal_registry)
    setattr(pipeline.core.internal.data, _LITERAL_REGISTRY_ATTR, literal_registry)

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

        classification = classifier.classify(cell, cell_value, self)
        if classification is None:
            continue

        if classification.kind == NodeKind.TYPED_INDIVIDUAL:
            node_classifications[cell] = classification
            parent = classification.parent_cell
            if parent is None:
                continue
            try:
                dimensions = self._dimensions(parent)
            except ParseException:
                continue
            seen_classes: set[str] = set()
            if not classification.types:
                raise NotInKnownException(
                    (
                        f"The node '{classification.identifier}' declares an rdf:type value "
                        "but no CURIE tokens could be parsed."
                    )
                )
            for candidate in classification.types:
                if candidate in seen_classes:
                    continue
                seen_classes.add(candidate)
                try:
                    _verify_is_ric_class(candidate, prefixes)
                except NotInKnownException as exc:
                    raise NotInKnownException(
                        (
                            f"The node '{classification.identifier}' declares rdf:type "
                            f"'{candidate}', which is not defined by the available prefixes."
                        )
                    ) from exc
                individual = Individual(classification.identifier, candidate)
                self.individual_cells.append((cell, individual, dimensions))
            continue

        if classification.kind == NodeKind.INDIVIDUAL:
            node_classifications[cell] = classification
            try:
                dimensions = self._dimensions(cell)
            except ParseException:
                continue
            individual = Individual(classification.identifier, None)
            self.individual_cells.append((cell, individual, dimensions))
            continue

        if classification.kind == NodeKind.LITERAL:
            if not self._is_possible_literal(cell):
                continue
            try:
                dimensions = self._dimensions(cell)
            except ParseException:
                continue
            node_classifications[cell] = classification
            literal_registry[cell] = LiteralInfo(classification.literal or "")
            self.literal_cells.append((cell, dimensions))


@override(phase="core", type="xml", role="data")
def _source_or_target(
    self, source_or_target_cell: Element, must_be_individual: bool
) -> str:
    node_classifications = getattr(self, "_node_classifications", {})
    classification = node_classifications.get(source_or_target_cell)
    if classification:
        if classification.kind == NodeKind.LITERAL:
            if must_be_individual:
                raise _SourceNotIndividualException
            return classification.literal or self._value_of(source_or_target_cell)
        identifier = classification.identifier
        if identifier:
            if must_be_individual and not self._defines_individual(identifier):
                raise _SourceNotIndividualException
            return identifier

    try:
        value = self._value_of(source_or_target_cell)
    except (_NoValueException, KeyError) as exc:
        raise _NoValueException from exc

    if value.split(":")[0] in self.prefixes.keys():
        parent = self._parent_of(source_or_target_cell)
        identifier = self._value_of(parent)
        if must_be_individual and not self._defines_individual(identifier):
            raise _SourceNotIndividualException
        return identifier

    if must_be_individual and (not self._defines_individual(value)):
        raise _SourceNotIndividualException

    return value


@override(phase="core", type="xml", role="data")
def _arrow(self, arrow_data: ArrowData, strict_mode: bool, max_gap: float) -> Arrow:
    arrow_cell, arrow_start, arrow_end, arrow_label = arrow_data

    try:
        source_cell = self._cell_with_id(arrow_cell.attrib["source"])
    except KeyError as key_error:
        if strict_mode or arrow_start is None:
            raise NoSourceException(
                "The mxCell element with label "
                f"'{arrow_label}' and id {arrow_cell.attrib['id']} seems to be an arrow, but its source was not able to be determined"
            ) from key_error
        try:
            source_cell = self._cell_close_to(arrow_start, max_gap)
        except _NoCellCloseEnoughException as not_close_enough_exception:
            raise NoSourceException(
                "The mxCell element with label "
                f"'{arrow_label}' and id {arrow_cell.attrib['id']} seems to be an arrow, but its source was not able to be determined"
            ) from not_close_enough_exception

    try:
        source = self._source_or_target(source_cell, True)
    except _SourceNotIndividualException as exception:
        raise ArrowWithoutIndividualAsSourceException(
            f"The arrow with id {arrow_cell.attrib['id']} and label {arrow_label} has a source which appears not to be a node defining a RiC-O individual"
        ) from exception

    try:
        target_cell = self._cell_with_id(arrow_cell.attrib["target"])
    except KeyError as key_error:
        if strict_mode or arrow_end is None:
            raise NoSourceException(
                "The mxCell element with label "
                f"'{arrow_label}' and id {arrow_cell.attrib['id']} seems to be an arrow, but its target was not able to be determined"
            ) from key_error
        try:
            target_cell = self._cell_close_to(arrow_end, max_gap)
        except _NoCellCloseEnoughException as not_close_enough_exception:
            raise NoSourceException(
                "The mxCell element with label "
                f"'{arrow_label}' and id {arrow_cell.attrib['id']} seems to be an arrow, but its target was not able to be determined"
            ) from not_close_enough_exception

    target = self._source_or_target(target_cell, False)

    is_datatype = self._cell_is_literal(target_cell)
    if not is_datatype and (not self._defines_individual(target)):
        is_datatype = True

    arrow = Arrow(str(arrow_label).strip(), source, target, is_datatype)

    if is_datatype:
        literal_registry = getattr(self, "_literal_registry", {})
        info = literal_registry.get(target_cell)
        if info is not None:
            info.connected = True

    return arrow


@override(phase="core", type="internal", role="control")
def _add_individual_type(
    blocks: Blocks,
    individual: Individual,
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
) -> None:
    individual_id = _replace_metacharacters(
        individual.identifier,
        metacharacter_substitutes,
        space_substitute,
        capitalisation_scheme,
    )
    block = blocks.setdefault((individual_id, individual.identifier), {})
    types = block.setdefault("Types", set())
    if individual.ric_class:
        types.add(individual.ric_class)


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

    literal_registry = getattr(
        pipeline.core.internal.data, _LITERAL_REGISTRY_ATTR, None
    )
    decorations: list[str] = []
    if isinstance(literal_registry, dict):
        decorations = [
            info.value
            for info in literal_registry.values()
            if isinstance(info, LiteralInfo) and info.value and not info.connected
        ]

    if decorations:
        graph.bind("skos", SKOS, replace=False)
        note_subject = (
            URIRef(serialisation_config.ontology_iri)
            if serialisation_config.ontology_iri
            else BNode()
        )
        for note in dict.fromkeys(decorations):
            graph.add((note_subject, SKOS.note, Literal(note)))

    if hasattr(pipeline.core.internal.data, _LITERAL_REGISTRY_ATTR):
        delattr(pipeline.core.internal.data, _LITERAL_REGISTRY_ATTR)

    return graph
