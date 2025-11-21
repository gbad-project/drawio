from __future__ import annotations

import os
import re

from rdflib import BNode
from rdflib.term import Node

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder

from aicode.python_core.src.overrides.core.rdf.control.serialization_helper import (
    RDFSerializationHelper,
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
        metacharacter_mode = getattr(self.graph, "metacharacter_mode", None)
        if metacharacter_mode == "url":
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

        Returns [] if input is None, otherwise stringifies it.
        """
        if template is None:
            return []

        if not isinstance(template, str):
            template = str(template)

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

    def _resolve_template(self, candidate: str) -> Node | bool:
        """
        Runs `detect_string_template` on raw and unquoted candidate.

        Returns a FakeURIRef with the resolved one, otherwise False.
        """
        decoded = urllib.parse.unquote(str(candidate))
        for value in (candidate, decoded):  # order matters - check raw first
            if self.detect_string_template(value):
                return self.FakeURIRef(value)
        return False

    def _is_template_string(self, candidate: str) -> bool:
        """Checks `detect_string_template` on raw and unquoted candidate."""
        return bool(self._resolve_template(candidate))

    def _build_fact_predicate_object_map(
        self, predicate_uri: URIRef, fact: Any
    ) -> tuple[tuple[Node, Node, Node], list[tuple[Node, Node, Node]]]:
        """
        Build a predicateObjectMap BNode for a fact and return it with all related triples.

        No triples are added to the graph; they can be inserted later with addN1().
        """
        predicate_object_map = BNode()
        object_map = BNode()

        has_template = self._is_template_string(fact)
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

        has_template = self._is_template_string(class_term)
        class_predicate = self.rr["template"] if has_template else self.rr["constant"]

        class_object = (
            Literal(class_term)
            if isinstance(class_term, self.FakeURIRef)
            else URIRef(class_term)
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
        has_template = self._is_template_string(subject_uri)
        subject_predicate = self.rr["template"] if has_template else self.rr["constant"]

        triples = [
            (subject_map, self.rr["termType"], self.rr["IRI"]),
            (subject_map, subject_predicate, Literal(subject_uri)),
        ]

        return subject_map, triples

    def coerce_to_literal(self, *args, **kwargs):
        return pipeline.core.rdf.control.coerce_to_literal(*args, **kwargs)

    def coerce_to_uriref(self, cfg, value: str, mint_from_literal: bool = True) -> Node:
        fake_uriref = self._resolve_template(value)  # -> FakeURIRef | False
        if fake_uriref:
            return fake_uriref
        return pipeline.core.rdf.control.coerce_to_uriref(cfg, value, mint_from_literal)

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
        subject_uri = self.coerce_to_uriref(self, individual_id)
        subject_map, subject_map_triples = self._build_subject_map(subject_uri)
        self.graph.addN1(
            (triples_map, self.rr["subjectMap"], subject_map), subject_map_triples
        )

        # Add RDF types as rr:class
        for rdf_type in sorted(
            types_and_facts.get("Types", set()), key=lambda value: value
        ):
            class_term = self.resolve_type(rdf_type)
            type_predicate_object_map, type_predicate_object_map_triples = (
                self._build_type_predicate_object_map(class_term)
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
                    target_uri = self.coerce_to_uriref(self, value)
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
                    literal_value = self.coerce_to_literal(self, value)
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
        """
        Serialize all individuals as RML mappings.

        Will pick up this subclass's `add_individual_triples` at runtime.
        """
        super().serialize_all_individuals()

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
def serialise_to_rml(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    graph_cls: type = Graph,
    graph_kwargs: dict[str, Any] | None = None,
) -> DrawIOParserGraph:
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
