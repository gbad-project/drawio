from __future__ import annotations

from rdflib import BNode, SKOS
import re

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

    def _is_relative_iri(self, candidate: str) -> bool:
        """Check if a string looks like a relative IRI and, if so, expand it."""
        if not candidate or any(ch.isspace() for ch in candidate):
            return False
        if self._is_absolute_iri(candidate):
            return False

        # Relative if it lacks a scheme or known prefix but is non-empty
        if not (":" in candidate or "://" in candidate):
            # Expand by prefix_iri if available
            if self.prefix_iri:
                return True
        return False

    @staticmethod
    def _string_has_template(candidate: str) -> bool:
        if (
            not isinstance(candidate, str)
            or "{" not in candidate
            or "}" not in candidate
        ):
            return False
        RMLSerializer = getattr(pipeline.core.rdf.control, "RMLSerializer", None)
        detector = getattr(RMLSerializer, "detect_string_template", None)
        if not callable(detector):
            return False
        try:
            return bool(detector(candidate))
        except ValueError:
            return False

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

    def _compute_explicit_override(self, individual_id) -> None:
        """Compute explicit URI override for a single individual."""
        pass

    def resolve_individual_uri(self, individual_id: str) -> URIRef:
        """Resolve an individual ID to its URI."""
        override_uri = self._compute_explicit_override(individual_id)
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

    def _compute_explicit_override(self, individual_id) -> None:
        """Compute explicit URI override for a single individual."""
        _ensure_known_curie = pipeline.core.internal.data._ensure_known_curie

        individual_label = urllib.parse.unquote(individual_id)
        trimmed_label = individual_label.strip()
        if not trimmed_label:
            return

        if self._is_absolute_iri(trimmed_label):
            return URIRef(trimmed_label)

        if self._is_relative_iri(trimmed_label):
            pass  # will be handled by resolve_individual_uri

        if ":" not in trimmed_label or "://" in trimmed_label:
            return

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
            return

        namespace = self.namespace_map.get(prefix)
        if namespace is None:
            return

        return namespace[reference]

    def add_individual_triples(
        self, individual_id: str, individual_label: str, types_and_facts: dict
    ) -> None:
        """Add triples for a single individual."""
        individual_uri = self.resolve_individual_uri(individual_id)

        # Add NamedIndividual type
        self.graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Add RDF types
        for rdf_type in types_and_facts.get("Types", set()):
            type_str = str(rdf_type)
            if self._string_has_template(type_str):
                continue
            if ":" not in type_str:
                continue
            type_prefix, type_name = type_str.split(":", 1)
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

    class FakeURIRef(Literal):
        """Helpful for temporary labeling."""

        pass

    def __init__(self, *args, csv_path: Optional[str] = None, **kwargs):
        RDFSerializationHelper = pipeline.core.rdf.control.RDFSerializationHelper
        RDFSerializationHelper.__init__(self, *args, **kwargs)
        self.csv_path = csv_path

        # RML namespaces
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.rml_ns = Namespace("http://semweb.mmlab.be/ns/rml#")
        self.ql = Namespace("http://semweb.mmlab.be/ns/ql#")

        # For IDE hints
        self.graph: pipeline.core.internal.control.DrawIOParserGraph

    def setup_namespaces(self) -> None:
        """Bind namespaces including RML-specific ones."""
        RDFSerializationHelper = pipeline.core.rdf.control.RDFSerializationHelper
        RDFSerializationHelper.setup_namespaces(self)

        self.graph.bind("rr", self.rr, replace=False)
        self.graph.bind("rml", self.rml_ns, replace=False)
        self.graph.bind("ql", self.ql, replace=False)
        self.graph.bind("rdfs", RDFS, replace=False)

    @staticmethod
    def detect_string_template(template: str) -> list[str | None]:
        """
        Detects valid unescaped {reference} patterns in a string template.

        Rules:
        - Double braces {{ }} are ignored.
        - Escaped braces \\{ or \\} are ignored.
        - Must contain at least one valid { ... } pair.
        - Returns a list of references if valid; else [].
        """
        # Matches single unescaped curly braces around content
        # Negative lookbehind avoids \{, and avoids doubling {{ or }}
        pattern = re.compile(r"(?<!\\)(?<!{){([^{}]+)}(?!})(?!\\)")

        matches = []
        spans = []
        for match in pattern.finditer(template):
            ref = match.group(1).strip()
            if ref:
                matches.append(ref)
                spans.append(match.span())

        # Validate: must have at least one valid pair
        if not matches:
            return []

        # Optional: check safe separators between multiple pairs
        # (simplified heuristic — ensures braces don't touch directly)
        for i in range(len(spans) - 1):
            end_prev = spans[i][1]
            start_next = spans[i + 1][0]
            separator = template[end_prev:start_next]
            if not separator.strip():
                raise ValueError(
                    f"Unsafe template: adjacent references not separated — '{template}'"
                )

        return matches

    def _compute_explicit_override(self, individual_id) -> Any:
        """Compute explicit URI override for a single individual."""
        _ensure_known_curie = pipeline.core.internal.data._ensure_known_curie

        individual_label = urllib.parse.unquote(individual_id)
        trimmed_label = individual_label.strip()
        if not trimmed_label:
            return

        if self._is_absolute_iri(trimmed_label) or self._is_relative_iri(
            trimmed_label
        ):  # RMLmapper will convert to abs
            return self.FakeURIRef(trimmed_label)

        if ":" not in trimmed_label or "://" in trimmed_label:
            return

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
            return

        namespace = self.namespace_map.get(prefix)
        if namespace is None:
            return

        return namespace[reference]

    def _build_fact_predicate_object_map(
        self, predicate_uri: URIRef, fact: Any
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        """
        Build a predicateObjectMap BNode for a fact and return it with all related triples.

        No triples are added to the graph; they can be inserted later with addN1().
        """
        predicate_object_map = BNode()
        object_map = BNode()

        has_template = bool(self.detect_string_template(str(fact)))
        fact_predicate = self.rr["template"] if has_template else self.rr["constant"]

        triples = [
            (predicate_object_map, self.rr["predicate"], predicate_uri),
            (predicate_object_map, self.rr["objectMap"], object_map),
            (object_map, fact_predicate, fact),
        ]

        if isinstance(fact, self.FakeURIRef):
            triples.append((object_map, self.rr["termType"], self.rr["IRI"]))
        elif isinstance(fact, Literal):
            triples.append((object_map, self.rr["termType"], self.rr["Literal"]))
            if fact.datatype:
                triples.append((object_map, self.rr["datatype"], fact.datatype))
            if fact.language:
                triples.append(
                    (object_map, self.rr["language"], Literal(fact.language))
                )

        return predicate_object_map, triples

    def _get_logical_source_value(self) -> Literal:
        """Determine the logical source value for RML mappings."""
        if self.csv_path:
            return Literal(self.csv_path)
        elif self.serialisation_config.ontology_iri:
            return Literal(self.serialisation_config.ontology_iri)
        else:
            return Literal("drawio")

    def _build_type_predicate_object_map(
        self, class_value: str
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        """
        Build predicateObjectMap BNode for rdf:type mapping and
        return all related triples for direct graph insertion.
        """
        object_map = BNode()
        predicate_object_map = BNode()

        has_template = bool(self.detect_string_template(class_value))
        class_predicate = self.rr["template"] if has_template else self.rr["constant"]

        triples = [
            (object_map, self.rr["termType"], self.rr["IRI"]),
            (object_map, class_predicate, Literal(class_value)),
            (predicate_object_map, self.rr["predicate"], RDF["type"]),
            (predicate_object_map, self.rr["objectMap"], object_map),
        ]

        return predicate_object_map, triples

    def _build_subject_map(
        self, subject_uri
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        """
        Build a subjectMap BNode and return it with its triples.

        Uses rr:template if the subject URI contains a valid template,
        otherwise rr:constant. Does not modify the graph directly.
        """
        subject_map = BNode()
        has_template = bool(self.detect_string_template(str(subject_uri)))
        subject_predicate = self.rr["template"] if has_template else self.rr["constant"]

        triples = [
            (subject_map, self.rr["termType"], self.rr["IRI"]),
            (subject_map, subject_predicate, Literal(subject_uri)),
        ]

        return subject_map, triples

    def _resolve_class_value(self, rdf_type: Any) -> str:
        class_text = str(rdf_type)
        try:
            if self.detect_string_template(class_text):
                return class_text
        except ValueError:
            pass
        if ":" not in class_text:
            return class_text
        type_prefix, type_name = class_text.split(":", 1)
        namespace = self.namespace_map[type_prefix]
        return str(namespace[type_name])

    def add_individual_triples(
        self, individual_id: str, individual_label: str, types_and_facts: dict
    ) -> None:
        """Add RML triples for a single individual."""
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
        subject_uri = self.resolve_individual_uri(individual_id)
        subject_map, subject_map_triples = self._build_subject_map(subject_uri)
        self.graph.addN1(
            (triples_map, self.rr["subjectMap"], subject_map), subject_map_triples
        )

        # Add RDF types as rr:class
        for rdf_type in sorted(types_and_facts.get("Types", set())):
            class_value = self._resolve_class_value(rdf_type)
            type_predicate_object_map, type_predicate_object_map_triples = (
                self._build_type_predicate_object_map(class_value)
            )
            self.graph.addN1(
                (subject_map, self.rr["predicateObjectMap"], type_predicate_object_map),
                type_predicate_object_map_triples,
            )

        # Add label if configured
        if self.serialisation_config.include_label:
            label_predicate_object_map, label_predicate_object_map_triples = (
                self._build_fact_predicate_object_map(
                    RDFS.label, Literal(individual_label)
                )
            )
            self.graph.addN1(
                (
                    triples_map,
                    self.rr["predicateObjectMap"],
                    label_predicate_object_map,
                ),
                label_predicate_object_map_triples,
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
                    fact_predicate_object_map, fact_predicate_object_map_triples = (
                        self._build_fact_predicate_object_map(prop_uri, target_uri)
                    )
                    self.graph.addN1(
                        (
                            triples_map,
                            self.rr["predicateObjectMap"],
                            fact_predicate_object_map,
                        ),
                        fact_predicate_object_map_triples,
                    )
                else:
                    # Datatype property
                    literal_value = self.coerce_to_literal(value)
                    fact_predicate_object_map, fact_predicate_object_map_triples = (
                        self._build_fact_predicate_object_map(prop_uri, literal_value)
                    )
                    self.graph.addN1(
                        (
                            triples_map,
                            self.rr["predicateObjectMap"],
                            fact_predicate_object_map,
                        ),
                        fact_predicate_object_map_triples,
                    )

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

    if os.getenv("DEBUG") == "true":
        import json

        def make_json_safe(obj):
            if isinstance(obj, dict):
                return {
                    (
                        k
                        if isinstance(k, (str, int, float, bool, type(None)))
                        else str(k)
                    ): make_json_safe(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, (list, tuple, set)):
                return [make_json_safe(i) for i in obj]
            else:
                return obj

        data = {
            "blocks": make_json_safe(blocks),
            "object_properties": make_json_safe(object_properties),
            "datatype_properties": make_json_safe(datatype_properties),
        }
        with open("tmp/blocks.json", "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

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
    serializer.serialize_all_individuals()

    if os.getenv("DEBUG") == "true":
        # from rdflib.compare import to_canonical_graph
        # graph = to_canonical_graph(graph)
        graph.serialize("tmp/graph.ttl", format="turtle")

    return graph
