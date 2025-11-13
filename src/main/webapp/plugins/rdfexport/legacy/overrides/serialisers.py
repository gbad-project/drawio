from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional, Type

from rdflib import BNode, SKOS
from rdflib.term import Node

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
        self.metacharacter_substitution_mode = getattr(
            graph, "metacharacter_mode", None
        )
        self._should_decode_literals = False

    def _normalize_candidate(self, candidate: str) -> str:
        if self._should_decode_literals and isinstance(candidate, str) and candidate:
            return urllib.parse.unquote(candidate)
        return candidate

    def _normalize_literal(self, literal: Literal) -> Literal:
        if not self._should_decode_literals:
            return literal

        lexical_form = str(literal)
        decoded = urllib.parse.unquote(lexical_form)
        if decoded == lexical_form:
            return literal

        literal_kwargs: dict[str, Any] = {}
        if getattr(literal, "datatype", None):
            literal_kwargs["datatype"] = literal.datatype
        if getattr(literal, "language", None):
            literal_kwargs["lang"] = literal.language

        return literal.__class__(decoded, **literal_kwargs)

    def _normalize_node(self, node: Node) -> Node:
        if isinstance(node, Literal):
            return self._normalize_literal(node)
        return node

    def _normalize_triple(
        self, triple: tuple[Node, Node, Node]
    ) -> tuple[Node, Node, Node]:
        subject, predicate, obj = triple
        return (
            self._normalize_node(subject),
            self._normalize_node(predicate),
            self._normalize_node(obj),
        )

    def _add_triple(self, triple: tuple[Node, Node, Node]) -> tuple[Node, Node, Node]:
        normalized = self._normalize_triple(triple)
        self.graph.add(normalized)
        return normalized

    def _add_triples(
        self, triples: list[tuple[Node, Node, Node]]
    ) -> list[tuple[Node, Node, Node]]:
        normalized = [self._normalize_triple(triple) for triple in triples]
        for triple in normalized:
            self.graph.add(triple)
        return normalized

    def _add_n1(
        self,
        triple_1: tuple[Node, Node, Node],
        triples_n: list[tuple[Node, Node, Node]],
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        normalized_first = self._normalize_triple(triple_1)
        normalized_rest = [self._normalize_triple(triple) for triple in triples_n]

        addn1 = getattr(self.graph, "addN1", None)
        if callable(addn1):
            addn1(normalized_first, normalized_rest)
        else:
            self.graph.add(normalized_first)
            if normalized_rest:
                self.graph.addN((s, p, o, self.graph) for s, p, o in normalized_rest)

        return normalized_first, normalized_rest

    def setup_namespaces(self) -> None:
        """Bind namespaces to the graph."""
        looks_like_iri = pipeline.core.internal.data.looks_like_iri

        if self.prefix_iri and looks_like_iri(self.prefix_iri) == "absolute-iri":
            self.fallback_namespace = Namespace(self.prefix_iri)

        for prefix_key, uri in self.prefixes.items():
            if looks_like_iri(uri) == "absolute-iri":
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
            self._add_triple((URIRef(ontology_iri), RDF.type, OWL.Ontology))
            self._add_triple(
                (URIRef(ontology_iri), OWL.imports, URIRef(self.prefixes["rico"]))
            )

    def resolve_predicate(self, prop: str) -> URIRef:
        """Resolve a predicate string (property IRI) to a URIRef."""
        return self.coerce_to_uriref(prop, mint_from_literal=False)

    def resolve_type(self, rdf_type: str) -> Any:
        return self.coerce_to_uriref(rdf_type, mint_from_literal=False)

    def declare_properties(self) -> None:
        """Declare object and datatype properties in the graph."""
        for prop in sorted(self.object_properties):
            prop_uri = self.resolve_predicate(prop)
            self._add_triple((prop_uri, RDF.type, OWL.ObjectProperty))

        for prop in sorted(self.datatype_properties):
            prop_uri = self.resolve_predicate(prop)
            self._add_triple((prop_uri, RDF.type, OWL.DatatypeProperty))

    def coerce_to_uriref(self, value: str, mint_from_literal: bool = True) -> URIRef:
        """
        Resolve an individual ID/type/object fact to its URI.

        If mint_from_literal = False, raises NotInKnownException,
        otherwise urlencodes and mints entity to default namespace.
        """
        _ensure_known_curie = pipeline.core.internal.data._ensure_known_curie
        looks_like_iri = pipeline.core.internal.data.looks_like_iri

        individual_label = urllib.parse.unquote(value)
        trimmed_label = individual_label.strip()
        if not trimmed_label:
            raise NotInKnownException(f"Entity {value!r} is empty")

        if looks_like_iri(trimmed_label) == "absolute-iri":
            return URIRef(trimmed_label)

        if looks_like_iri(trimmed_label) == "relative-iri":
            if self.prefix_iri:
                return Namespace(self.prefix_iri)[value]
            else:
                raise NotInKnownException(
                    f"Failed to coerce {value!r} to URIRef because prefix IRI is {self.prefix_iri!r}"
                )

        try:
            prefix, reference = _ensure_known_curie(
                trimmed_label,
                self.prefixes,
                ("Unable to coerce entity '{0}' to a CURIE").format(trimmed_label),
            )
            return self.namespace_map[prefix][reference]
        except NotInKnownException:
            if looks_like_iri(trimmed_label) == "curie":
                raise
            if mint_from_literal:
                return Namespace(self.prefix_iri)[value]
            else:
                raise

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
                self._add_triple((decoration_subject, SKOS.note, Literal(note)))

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
        individual_uri = self.coerce_to_uriref(individual_id)

        # Add NamedIndividual type
        self._add_triple((individual_uri, RDF.type, OWL.NamedIndividual))

        # Add RDF types
        for rdf_type in types_and_facts.get("Types", set()):
            self._add_triple(
                (individual_uri, RDF.type, self.resolve_type(str(rdf_type)))
            )

        # Add label if configured
        if self.serialisation_config.include_label:
            self._add_triple((individual_uri, RDFS.label, Literal(individual_label)))

        # Add properties
        for prop, values in types_and_facts.items():
            if prop == "Types":
                continue

            prop_uri = self.resolve_predicate(prop)

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
                    target_identifier = str(value)
                    target_uri = self.coerce_to_uriref(target_identifier)
                    self._add_triple((individual_uri, prop_uri, target_uri))
                else:
                    # Datatype property - create literal
                    literal_value = self.coerce_to_literal(value)
                    self._add_triple((individual_uri, prop_uri, literal_value))

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
        if self.metacharacter_substitution_mode == "url":
            self._should_decode_literals = True

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

    def _is_template_string(self, candidate: str) -> bool:
        normalized = self._normalize_candidate(candidate)
        return bool(self.detect_string_template(normalized))

    def _build_fact_predicate_object_map(
        self, predicate_uri: URIRef, fact: Any
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        """
        Build a predicateObjectMap BNode for a fact and return it with all related triples.

        No triples are added to the graph; they can be inserted later with addN1().
        """
        predicate_object_map = BNode()
        object_map = BNode()

        has_template = self._is_template_string(str(fact))
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
        self, class_term: Any
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        """
        Build predicateObjectMap BNode for rdf:type mapping and
        return all related triples for direct graph insertion.
        """
        object_map = BNode()
        predicate_object_map = BNode()

        text_value = str(class_term)
        has_template = self._is_template_string(text_value)
        class_predicate = self.rr["template"] if has_template else self.rr["constant"]

        class_object = (
            Literal(class_term) if isinstance(class_term, self.FakeURIRef) else URIRef
        )
        triples = [
            (object_map, class_predicate, class_object),
            (object_map, self.rr["termType"], self.rr["IRI"]),
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
        has_template = self._is_template_string(str(subject_uri))
        subject_predicate = self.rr["template"] if has_template else self.rr["constant"]

        triples = [
            (subject_map, self.rr["termType"], self.rr["IRI"]),
            (subject_map, subject_predicate, Literal(subject_uri)),
        ]

        return subject_map, triples

    def coerce_to_uriref(self, value: str, mint_from_literal: bool = True) -> URIRef:
        if self._is_template_string(value):
            return self.FakeURIRef(value)
        return super().coerce_to_uriref(value, mint_from_literal)

    def add_individual_triples(
        self, individual_id: str, individual_label: str, types_and_facts: dict
    ) -> None:
        """Add RML triples for a single individual."""
        # Create TriplesMap
        triples_map = BNode()
        self._add_triple((triples_map, RDF.type, self.rr.TriplesMap))

        # Add logical source
        logical_source = BNode()
        self._add_triple((triples_map, self.rml_ns.logicalSource, logical_source))
        self._add_triple(
            (logical_source, self.rml_ns.source, self._get_logical_source_value())
        )
        self._add_triple(
            (logical_source, self.rml_ns.referenceFormulation, self.ql.CSV)
        )

        # Add subject map
        subject_uri = self.coerce_to_uriref(individual_id)
        subject_map, subject_map_triples = self._build_subject_map(subject_uri)
        self._add_n1(
            (triples_map, self.rr["subjectMap"], subject_map), subject_map_triples
        )

        # Add RDF types as rr:class
        for rdf_type in sorted(
            types_and_facts.get("Types", set()), key=lambda value: str(value)
        ):
            class_term = self.resolve_type(str(rdf_type))
            type_predicate_object_map, type_predicate_object_map_triples = (
                self._build_type_predicate_object_map(class_term)
            )
            self._add_n1(
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
            self._add_n1(
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

            prop_uri = self.resolve_predicate(prop)

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
                    target_uri = self.coerce_to_uriref(str(value))
                    fact_predicate_object_map, fact_predicate_object_map_triples = (
                        self._build_fact_predicate_object_map(prop_uri, target_uri)
                    )
                    self._add_n1(
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
                    self._add_n1(
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


@override(phase="core", type="internal", role="control")
def dump_blocks(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    dump_path: str,
):
    import json
    from pathlib import Path

    def make_json_safe(obj):
        if isinstance(obj, dict):
            return {
                (
                    k if isinstance(k, (str, int, float, bool, type(None))) else str(k)
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
    Path(dump_path).write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )


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

    if os.getenv("DEBUG") == "true":
        dump_blocks = pipeline.core.internal.control.dump_blocks
        dump_blocks(blocks, object_properties, datatype_properties, "tmp/blocks.json")

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

    if os.getenv("DEBUG") == "true":
        # from rdflib.compare import to_canonical_graph
        # graph = to_canonical_graph(graph)
        graph.serialize("tmp/graph.ttl", format="turtle")

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
        dump_blocks = pipeline.core.internal.control.dump_blocks
        dump_blocks(blocks, object_properties, datatype_properties, "tmp/blocks.json")

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
