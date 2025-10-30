from __future__ import annotations

from rdflib import BNode, SKOS

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="rdf", role="control")
class RDFSerializationHelper:
    """Shared helper methods for RDF and RML serialization."""

    def __init__(
        self,
        blocks,
        object_properties: set[str],
        datatype_properties: set[str],
        serialisation_config,
        prefixes: dict,
        graph: Graph,
    ):
        self.blocks = blocks
        self.object_properties = object_properties
        self.datatype_properties = datatype_properties
        self.serialisation_config = serialisation_config
        self.prefixes = prefixes
        self.graph = graph

        self.prefix = serialisation_config.prefix
        self.prefix_iri = serialisation_config.prefix_iri or get_prefix_iri(
            serialisation_config.ontology_iri
        )

        self.namespace_map: dict[str, Namespace] = {}
        self.fallback_namespace: Namespace | None = None
        self.explicit_overrides: dict[str, URIRef] = {}

    @staticmethod
    def _is_absolute_iri(candidate: str) -> bool:
        """Check if a string is an absolute IRI."""
        if not candidate or any(ch.isspace() for ch in candidate):
            return False
        if "://" in candidate:
            return True
        scheme, _, remainder = candidate.partition(":")
        return scheme.lower() in {"urn", "tag"} and bool(remainder.strip())

    def setup_namespaces(self) -> None:
        """Bind namespaces to the graph."""
        if self.prefix_iri and self._is_absolute_iri(self.prefix_iri):
            self.fallback_namespace = Namespace(self.prefix_iri)

        for prefix_key, uri in self.prefixes.items():
            if self._is_absolute_iri(uri):
                namespace = Namespace(uri)
            elif self.fallback_namespace is not None:
                namespace = self.fallback_namespace
            else:
                raise ParseException(f"Prefix IRI '{uri}' looks invalid")

            self.graph.bind(prefix_key, namespace, replace=True)
            self.namespace_map[prefix_key] = namespace

        if self.prefix:
            self.graph.bind(self.prefix, Namespace(self.prefix_iri), replace=True)

    def add_preamble(self) -> None:
        """Add ontology preamble if configured."""
        if self.serialisation_config.include_preamble:
            ontology_iri = self.serialisation_config.ontology_iri or get_ontology_iri()
            self.graph.add((URIRef(ontology_iri), RDF.type, OWL.Ontology))
            self.graph.add(
                (URIRef(ontology_iri), OWL.imports, URIRef(self.prefixes["rico"]))
            )

    def resolve_property_uri(self, prop: str) -> URIRef:
        """Resolve a property string to a URIRef."""
        if self._is_absolute_iri(prop):
            return URIRef(prop)
        prop_prefix, prop_name = prop.split(":", 1)
        return self.namespace_map[prop_prefix][prop_name]

    def declare_properties(self) -> None:
        """Declare object and datatype properties in the graph."""
        for prop in sorted(
            prop for prop in self.object_properties if not prop.startswith("rico:")
        ):
            prop_uri = self.resolve_property_uri(prop)
            self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))

        for prop in sorted(
            prop for prop in self.datatype_properties if not prop.startswith("rico:")
        ):
            prop_uri = self.resolve_property_uri(prop)
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))

    def compute_explicit_overrides(self) -> None:
        """Compute explicit URI overrides for individuals."""
        for individual_id, individual_label in self.blocks.keys():
            trimmed_label = individual_label.strip()
            if not trimmed_label:
                continue
            if self._is_absolute_iri(trimmed_label):
                self.explicit_overrides[individual_id] = URIRef(trimmed_label)
                continue
            if ":" not in trimmed_label or "://" in trimmed_label:
                continue
            try:
                prefix, reference = _ensure_known_curie(
                    trimmed_label,
                    self.prefixes,
                    (
                        "The standalone node '{0}' references a CURIE, "
                        "which is not defined by the available prefixes."
                    ).format(trimmed_label),
                )
            except NotInKnownException:
                continue
            namespace = self.namespace_map.get(prefix)
            if namespace is None:
                continue
            self.explicit_overrides[individual_id] = namespace[reference]

    def resolve_individual_uri(self, individual_id: str) -> URIRef:
        """Resolve an individual ID to its URI."""
        override_uri = self.explicit_overrides.get(individual_id)
        if override_uri is not None:
            return override_uri
        elif self.prefix and self.serialisation_config.prefix_iri:
            return Namespace(self.serialisation_config.prefix_iri)[individual_id]
        elif self.prefix_iri:
            return URIRef(f"{self.prefix_iri}{individual_id}")
        else:
            return URIRef(individual_id)

    def coerce_to_literal(self, value: Any) -> Literal:
        """Convert a value to a typed Literal."""
        if self.serialisation_config.infer_type_of_literals:
            if isinstance(value, int) or (isinstance(value, str) and value.isnumeric()):
                return Literal(value, datatype=XSD.integer)
            elif isinstance(value, float):
                return Literal(value, datatype=XSD.float)
            else:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                    return Literal(value, datatype=XSD.date)
                except (ValueError, TypeError):
                    return Literal(value)
        else:
            return Literal(value)

    def add_decoration_notes(self) -> None:
        """Add decoration notes from the pipeline registry."""
        decorations_attr = "__drawio_literal_registry"
        decoration_registry = getattr(pipeline.core.internal.data, decorations_attr, {})
        decoration_values = [
            entry.get("value")
            for entry in decoration_registry.values()
            if isinstance(entry, dict)
            and entry.get("value")
            and not entry.get("connected")
        ]
        if decoration_values:
            if self.serialisation_config.ontology_iri:
                decoration_subject = URIRef(self.serialisation_config.ontology_iri)
            else:
                decoration_subject = BNode()
            for note in decoration_values:
                self.graph.add((decoration_subject, SKOS.note, Literal(note)))

        if hasattr(pipeline.core.internal.data, decorations_attr):
            delattr(pipeline.core.internal.data, decorations_attr)


@override(phase="core", type="rdf", role="control")
class RDFSerializer(RDFSerializationHelper):
    """Standard RDF serialization (regular triples)."""

    def __init__(self, *args, **kwargs):
        RDFSerializationHelper = pipeline.core.rdf.control.RDFSerializationHelper
        RDFSerializationHelper.__init__(self, *args, **kwargs)

    def add_individual_triples(
        self, individual_id: str, individual_label: str, types_and_facts: dict
    ) -> None:
        """Add triples for a single individual."""
        individual_uri = self.resolve_individual_uri(individual_id)

        # Add NamedIndividual type
        self.graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Add RDF types
        for rdf_type in types_and_facts.get("Types", set()):
            type_prefix, type_name = rdf_type.split(":")
            self.graph.add(
                (individual_uri, RDF.type, self.namespace_map[type_prefix][type_name])
            )

        # Add label if configured
        if self.serialisation_config.include_label:
            self.graph.add((individual_uri, RDFS.label, Literal(individual_label)))

        # Add properties
        for prop, values in types_and_facts.items():
            if prop == "Types":
                continue

            prop_uri = self.resolve_property_uri(prop)

            for raw_value in values:
                # Determine if value is literal
                if (
                    isinstance(raw_value, tuple)
                    and len(raw_value) == 2
                    and isinstance(raw_value[1], bool)
                ):
                    value, is_literal = raw_value
                else:
                    value = raw_value
                    is_literal = (
                        prop in self.datatype_properties
                        and prop not in self.object_properties
                    )

                if not is_literal:
                    # Object property - create URI reference
                    target_uri = self.resolve_individual_uri(value)
                    self.graph.add((individual_uri, prop_uri, target_uri))
                else:
                    # Datatype property - create literal
                    literal_value = self.coerce_to_literal(value)
                    self.graph.add((individual_uri, prop_uri, literal_value))

    def serialize_all_individuals(self) -> None:
        """Serialize all individuals in blocks."""
        for (individual_id, individual_label), types_and_facts in self.blocks.items():
            self.add_individual_triples(
                individual_id, individual_label, types_and_facts
            )


@override(phase="core", type="rdf", role="control")
class RMLSerializer(RDFSerializationHelper):
    """RML serialization (R2RML mapping triples)."""

    def __init__(self, *args, csv_path: Optional[str] = None, **kwargs):
        RDFSerializationHelper = pipeline.core.rdf.control.RDFSerializationHelper
        RDFSerializationHelper.__init__(self, *args, **kwargs)
        self.csv_path = csv_path

        # RML namespaces
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.rml_ns = Namespace("http://semweb.mmlab.be/ns/rml#")
        self.ql = Namespace("http://semweb.mmlab.be/ns/ql#")

    def setup_namespaces(self) -> None:
        """Bind namespaces including RML-specific ones."""
        RDFSerializationHelper = pipeline.core.rdf.control.RDFSerializationHelper
        RDFSerializationHelper.setup_namespaces(self)

        self.graph.bind("rr", self.rr, replace=False)
        self.graph.bind("rml", self.rml_ns, replace=False)
        self.graph.bind("ql", self.ql, replace=False)
        self.graph.bind("rdfs", RDFS, replace=False)

    def _add_constant_object_map(
        self, predicate_map_owner: Any, predicate_uri: URIRef, constant: Any
    ) -> None:
        """Add a constant object map to a predicate-object map."""
        predicate_object_map = BNode()
        self.graph.add(
            (predicate_map_owner, self.rr.predicateObjectMap, predicate_object_map)
        )
        self.graph.add((predicate_object_map, self.rr.predicate, predicate_uri))

        object_map = BNode()
        self.graph.add((predicate_object_map, self.rr.objectMap, object_map))
        self.graph.add((object_map, self.rr.constant, constant))

        if isinstance(constant, URIRef):
            self.graph.add((object_map, self.rr.termType, self.rr.IRI))
        elif isinstance(constant, Literal):
            self.graph.add((object_map, self.rr.termType, self.rr.Literal))
            if constant.datatype:
                self.graph.add((object_map, self.rr.datatype, constant.datatype))
            if constant.language:
                self.graph.add(
                    (object_map, self.rr.language, Literal(constant.language))
                )

    def _get_logical_source_value(self) -> Literal:
        """Determine the logical source value for RML mappings."""
        if self.csv_path:
            return Literal(self.csv_path)
        elif self.serialisation_config.ontology_iri:
            return Literal(self.serialisation_config.ontology_iri)
        else:
            return Literal("drawio")

    def add_individual_triples(
        self, individual_id: str, individual_label: str, types_and_facts: dict
    ) -> None:
        """Add RML triples for a single individual."""
        subject_uri = self.resolve_individual_uri(individual_id)

        # Create TriplesMap
        triples_map = BNode()
        self.graph.add((triples_map, RDF.type, self.rr.TriplesMap))

        # Add logical source
        logical_source = BNode()
        self.graph.add((triples_map, self.rml_ns.logicalSource, logical_source))
        self.graph.add(
            (logical_source, self.rml_ns.source, self._get_logical_source_value())
        )
        self.graph.add((logical_source, self.rml_ns.referenceFormulation, self.ql.CSV))

        # Add subject map
        subject_map = BNode()
        self.graph.add((triples_map, self.rr.subjectMap, subject_map))
        self.graph.add((subject_map, self.rr.termType, self.rr.IRI))
        self.graph.add((subject_map, self.rr.constant, subject_uri))

        # Add RDF types as rr:class
        for rdf_type in sorted(types_and_facts.get("Types", set())):
            type_prefix, type_name = rdf_type.split(":", 1)
            class_uri = self.namespace_map[type_prefix][type_name]
            self.graph.add((subject_map, self.rr["class"], class_uri))

        # Add label if configured
        if self.serialisation_config.include_label:
            self._add_constant_object_map(
                triples_map, RDFS.label, Literal(individual_label)
            )

        # Add properties
        for prop, values in sorted(types_and_facts.items()):
            if prop == "Types":
                continue

            prop_uri = self.resolve_property_uri(prop)

            for raw_value in sorted(
                values,
                key=lambda v: (0, f"{v[0]}") if isinstance(v, tuple) else (1, f"{v}"),
            ):
                # Determine if value is literal
                if (
                    isinstance(raw_value, tuple)
                    and len(raw_value) == 2
                    and isinstance(raw_value[1], bool)
                ):
                    value, is_literal = raw_value
                else:
                    value = raw_value
                    is_literal = (
                        prop in self.datatype_properties
                        and prop not in self.object_properties
                    )

                if not is_literal:
                    # Object property
                    target_uri = self.resolve_individual_uri(str(value))
                    self._add_constant_object_map(triples_map, prop_uri, target_uri)
                else:
                    # Datatype property
                    literal_value = self.coerce_to_literal(value)
                    self._add_constant_object_map(triples_map, prop_uri, literal_value)

    def serialize_all_individuals(self) -> None:
        """Serialize all individuals as RML mappings."""
        for (individual_id, individual_label), types_and_facts in self.blocks.items():
            self.add_individual_triples(
                individual_id, individual_label, types_and_facts
            )

    def add_preamble(self) -> None:
        """RML doesn't need ontology preamble."""
        pass

    def declare_properties(self) -> None:
        """RML doesn't need property declarations."""
        pass

    def add_decoration_notes(self) -> None:
        """RML doesn't include decoration notes."""
        pass


@override(phase="core", type="rdf", role="control")
def serialise_to_graph(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    graph_cls: Type[Graph] = Graph,
    graph_kwargs: Optional[Dict[str, Any]] = None,
) -> Graph:
    """Serialize blocks to RDF graph with regular triples."""
    RDFSerializer = pipeline.core.rdf.control.RDFSerializer

    graph_kwargs = graph_kwargs or {}
    graph = graph_cls(**graph_kwargs)

    serializer = RDFSerializer(
        blocks,
        object_properties,
        datatype_properties,
        serialisation_config,
        prefixes,
        graph,
    )

    serializer.setup_namespaces()
    serializer.add_preamble()
    serializer.declare_properties()
    serializer.compute_explicit_overrides()
    serializer.serialize_all_individuals()
    serializer.add_decoration_notes()

    return graph


@override(phase="core", type="rdf", role="control")
def serialise_to_rml(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    graph_cls: type[Graph] = Graph,
    graph_kwargs: dict[str, Any] | None = None,
) -> Graph:
    """Serialize blocks to RDF graph with RML mapping triples."""
    RMLSerializer = pipeline.core.rdf.control.RMLSerializer

    graph_kwargs = graph_kwargs or {}
    graph = graph_cls(**graph_kwargs)

    # Extract csv_path if available
    csv_path = graph_kwargs.get("csv_path")
    if csv_path is None and hasattr(graph, "csv_path"):
        csv_path = getattr(graph, "csv_path")

    serializer = RMLSerializer(
        blocks,
        object_properties,
        datatype_properties,
        serialisation_config,
        prefixes,
        graph,
        csv_path=csv_path,
    )

    serializer.setup_namespaces()
    serializer.compute_explicit_overrides()
    serializer.serialize_all_individuals()

    return graph
