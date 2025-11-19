from __future__ import annotations

from typing import Callable

from rdflib import BNode, SKOS

from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="rdf", role="control")
class RDFSerializationHelper:
    """Shared helper methods for RDF and RML serialization."""

    coerce_to_uriref: Callable
    coerce_to_literal: Callable

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
            self.graph.add((URIRef(ontology_iri), RDF.type, OWL.Ontology))
            self.graph.add(
                (URIRef(ontology_iri), OWL.imports, URIRef(self.prefixes["rico"]))
            )

    def resolve_predicate(self, prop: str) -> URIRef:
        """Resolve a predicate string (property IRI) to a URIRef."""
        return self.coerce_to_uriref(
            cfg=self,
            value=prop,
            mint_from_literal=False,
        )

    def resolve_type(self, rdf_type: str) -> Any:
        return self.coerce_to_uriref(
            cfg=self,
            value=rdf_type,
            mint_from_literal=False,
        )

    def declare_properties(self) -> None:
        """Declare object and datatype properties in the graph."""
        for prop in sorted(self.object_properties):
            prop_uri = self.resolve_predicate(prop)
            self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))

        for prop in sorted(self.datatype_properties):
            prop_uri = self.resolve_predicate(prop)
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))

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
        """Serialize all individuals in blocks."""
        for (individual_id, individual_label), types_and_facts in self.blocks.items():
            self.add_individual_triples(
                individual_id, individual_label, types_and_facts
            )
