from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Type

from rdflib import BNode, SKOS

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="rdf", role="control")
class RDFSerializationHelper:
    """Shared helper methods for RDF and RML serialization."""

    @dataclass(slots=True)
    class SubjectRecord:
        normalized_id: str
        label: str
        types: set[str] = field(default_factory=set)
        properties: dict[str, set[tuple[str, bool]]] = field(default_factory=dict)

        def add_type(self, rdf_type: str) -> None:
            self.types.add(rdf_type)

        def add_property(self, predicate: str, value: tuple[str, bool]) -> None:
            values = self.properties.setdefault(predicate, set())
            values.add(value)

    def __init__(
        self,
        classifier: Any,
        serialisation_config: SerialisationConfig,
        prefixes: dict,
        graph: Graph,
        *,
        metacharacter_substitutes: Iterable[tuple[Metacharacter, Replacement]]
        | None = None,
        space_substitute: Replacement | None = None,
        capitalisation_scheme: str | None = None,
    ) -> None:
        self.classifier = classifier
        self.serialisation_config = serialisation_config
        self.prefixes = prefixes
        self.graph = graph

        self.prefix = serialisation_config.prefix
        self.prefix_iri = serialisation_config.prefix_iri or get_prefix_iri(
            serialisation_config.ontology_iri
        )

        self.metacharacter_substitutes = list(metacharacter_substitutes or [])
        self.space_substitute = space_substitute
        if capitalisation_scheme is None:
            capitalisation_scheme = "upper-camel"
        self.capitalisation_scheme = capitalisation_scheme

        self.namespace_map: dict[str, Namespace] = {}
        self.fallback_namespace: Namespace | None = None
        self.explicit_overrides: dict[str, URIRef] = {}
        self.subjects: "OrderedDict[tuple[str, str], RDFSerializationHelper.SubjectRecord]" = OrderedDict()
        self.object_properties: set[str] = set()
        self.datatype_properties: set[str] = set()

        self._build_serialization_state()

    @staticmethod
    def _is_absolute_iri(candidate: str) -> bool:
        """Check if a string is an absolute IRI."""
        if not candidate or any(ch.isspace() for ch in candidate):
            return False
        if "://" in candidate:
            return True
        scheme, _, remainder = candidate.partition(":")
        return scheme.lower() in {"urn", "tag"} and bool(remainder.strip())

    def _get_or_create_subject(
        self, normalized_id: str, label: str
    ) -> "RDFSerializationHelper.SubjectRecord":
        key = (normalized_id, label)
        record = self.subjects.get(key)
        if record is None:
            record = self.SubjectRecord(normalized_id=normalized_id, label=label)
            self.subjects[key] = record
        return record

    def _register_individual(self, individual: Individual) -> None:
        normalized_id = _replace_metacharacters(
            individual.identifier,
            self.metacharacter_substitutes,
            self.space_substitute,
            self.capitalisation_scheme,
        )
        record = self._get_or_create_subject(normalized_id, individual.identifier)
        record.add_type(individual.ric_class)

    def _validate_literal_curie(self, candidate: str) -> None:
        literal_candidate = candidate.strip()
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
                for known_prefix, iri in self.prefixes.items():
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

    def _register_arrow(self, arrow: Arrow) -> None:
        identifier = arrow.identifier
        normalized_identifier = identifier
        allow_absolute_identifier = False

        if self._is_absolute_iri(identifier):
            for prefix_key, iri in self.prefixes.items():
                if identifier.startswith(iri) and identifier[len(iri) :]:
                    normalized_identifier = f"{prefix_key}:{identifier[len(iri) :]}"
                    break
            else:
                allow_absolute_identifier = True

        if not allow_absolute_identifier:
            _ensure_known_curie(
                normalized_identifier,
                self.prefixes,
                (
                    f"An arrow has label '{normalized_identifier}', "
                    "which is not a known object property or datatype property"
                ),
            )

        if arrow.is_datatype:
            self.datatype_properties.add(normalized_identifier)
            target_identifier = arrow.target
            self._validate_literal_curie(target_identifier)
            property_value = (target_identifier, True)
        else:
            self.object_properties.add(normalized_identifier)
            target_identifier = _replace_metacharacters(
                arrow.target,
                self.metacharacter_substitutes,
                self.space_substitute,
                self.capitalisation_scheme,
            )
            property_value = (target_identifier, False)

        source_identifier = _replace_metacharacters(
            arrow.source,
            self.metacharacter_substitutes,
            self.space_substitute,
            self.capitalisation_scheme,
        )
        record = self._get_or_create_subject(source_identifier, arrow.source)
        record.add_property(normalized_identifier, property_value)

    def _build_serialization_state(self) -> None:
        individuals = getattr(self.classifier, "individuals", [])
        for individual in individuals:
            self._register_individual(individual)

        arrows = getattr(self.classifier, "arrows", [])
        for arrow in arrows:
            self._register_arrow(arrow)

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
        for (individual_id, individual_label), _ in self.subjects.items():
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

    def serialize_all_individuals(self) -> None:
        """Serialize all individuals collected from the classifier."""
        for record in self.subjects.values():
            self.add_individual_triples(record)


@override(phase="core", type="rdf", role="control")
class RDFSerializer(RDFSerializationHelper):
    """Standard RDF serialization (regular triples)."""

    def add_individual_triples(
        self, subject: "RDFSerializationHelper.SubjectRecord"
    ) -> None:
        """Add triples for a single individual."""
        individual_uri = self.resolve_individual_uri(subject.normalized_id)

        # Add NamedIndividual type
        self.graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Add RDF types
        for rdf_type in subject.types:
            type_prefix, type_name = rdf_type.split(":", 1)
            self.graph.add(
                (individual_uri, RDF.type, self.namespace_map[type_prefix][type_name])
            )

        # Add label if configured
        if self.serialisation_config.include_label:
            self.graph.add((individual_uri, RDFS.label, Literal(subject.label)))

        # Add properties
        for prop, values in subject.properties.items():
            prop_uri = self.resolve_property_uri(prop)

            for raw_value in values:
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
                    target_uri = self.resolve_individual_uri(str(value))
                    self.graph.add((individual_uri, prop_uri, target_uri))
                else:
                    # Datatype property - create literal
                    literal_value = self.coerce_to_literal(value)
                    self.graph.add((individual_uri, prop_uri, literal_value))


@override(phase="core", type="rdf", role="control")
class RMLSerializer(RDFSerializationHelper):
    """RML serialization (R2RML mapping triples)."""

    def __init__(self, *args, csv_path: Optional[str] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.csv_path = csv_path

        # RML namespaces
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.rml_ns = Namespace("http://semweb.mmlab.be/ns/rml#")
        self.ql = Namespace("http://semweb.mmlab.be/ns/ql#")

    def setup_namespaces(self) -> None:
        """Bind namespaces including RML-specific ones."""
        super().setup_namespaces()

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
        self, subject: "RDFSerializationHelper.SubjectRecord"
    ) -> None:
        """Add RML triples for a single individual."""
        subject_uri = self.resolve_individual_uri(subject.normalized_id)

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
        for rdf_type in sorted(subject.types):
            type_prefix, type_name = rdf_type.split(":", 1)
            class_uri = self.namespace_map[type_prefix][type_name]
            self.graph.add((subject_map, self.rr["class"], class_uri))

        # Add label if configured
        if self.serialisation_config.include_label:
            self._add_constant_object_map(
                triples_map, RDFS.label, Literal(subject.label)
            )

        # Add properties
        for prop, values in sorted(subject.properties.items()):
            prop_uri = self.resolve_property_uri(prop)

            for raw_value in sorted(
                values,
                key=lambda v: (0, f"{v[0]}") if isinstance(v, tuple) else (1, f"{v}"),
            ):
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
        for record in self.subjects.values():
            self.add_individual_triples(record)

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
    classifier: Any,
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    *,
    metacharacter_substitutes: Iterable[tuple[Metacharacter, Replacement]]
    | None = None,
    space_substitute: Replacement | None = None,
    capitalisation_scheme: str | None = None,
    graph_cls: Type[Graph] = Graph,
    graph_kwargs: Optional[Dict[str, Any]] = None,
) -> Graph:
    """Serialize classifier output to RDF graph with regular triples."""
    RDFSerializer = pipeline.core.rdf.control.RDFSerializer

    graph_kwargs = graph_kwargs or {}
    graph = graph_cls(**graph_kwargs)

    substitutes = list(metacharacter_substitutes or [])

    serializer = RDFSerializer(
        classifier,
        serialisation_config,
        prefixes,
        graph,
        metacharacter_substitutes=substitutes,
        space_substitute=space_substitute,
        capitalisation_scheme=capitalisation_scheme,
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
    classifier: Any,
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    *,
    metacharacter_substitutes: Iterable[tuple[Metacharacter, Replacement]]
    | None = None,
    space_substitute: Replacement | None = None,
    capitalisation_scheme: str | None = None,
    graph_cls: type[Graph] = Graph,
    graph_kwargs: dict[str, Any] | None = None,
) -> Graph:
    """Serialize classifier output to RDF graph with RML mapping triples."""
    RMLSerializer = pipeline.core.rdf.control.RMLSerializer

    graph_kwargs = graph_kwargs or {}
    graph = graph_cls(**graph_kwargs)

    csv_path = graph_kwargs.get("csv_path")
    if csv_path is None and hasattr(graph, "csv_path"):
        csv_path = getattr(graph, "csv_path")

    substitutes = list(metacharacter_substitutes or [])

    serializer = RMLSerializer(
        classifier,
        serialisation_config,
        prefixes,
        graph,
        metacharacter_substitutes=substitutes,
        space_substitute=space_substitute,
        capitalisation_scheme=capitalisation_scheme,
        csv_path=csv_path,
    )

    serializer.setup_namespaces()
    serializer.compute_explicit_overrides()
    serializer.serialize_all_individuals()

    return graph
