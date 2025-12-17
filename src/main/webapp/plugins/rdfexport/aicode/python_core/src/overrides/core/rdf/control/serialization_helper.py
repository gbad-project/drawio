from __future__ import annotations

from typing import Callable

from rdflib import BNode, SKOS
from rdflib.collection import Collection

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

        self.prefix = serialisation_config.prefix or ""
        self.prefix_iri = serialisation_config.prefix_iri

        self._should_decode_literals = False

    def _set_default_prefix(self, ns: Namespace):
        """
        Sets either the actual default (`:`) prefix
        or whatever prefix is passed in parser config.
        """
        default_prefix = self.prefix if getattr(self, "prefix", None) else ""
        self.graph.bind(default_prefix, ns, replace=True)

    def setup_namespaces(self) -> None:
        """
        Bind namespaces to the graph.

        Note that *no* IRI trailing check is performed for prefix IRIs,
        which is fully in line with how permissively rdflib (and Turtle
        1.1 also?) defines prefixes. For example:
        ```
        @prefix hi: <http://example.com/hi>
        hi:there [] [] .
        ```
        -> serializes as: <http://example.com/hithere>
        That is kept permissive intentionally to support cases
        where anyone might want to use prefixes in this way.
        """
        looks_like_iri = pipeline.core.internal.data.looks_like_iri

        # Movement #1
        if getattr(self, "prefix_iri", None):
            if looks_like_iri(self.prefix_iri) == "absolute-iri":
                self._set_default_prefix(Namespace(self.prefix_iri))
            else:
                raise ParseException(
                    f"Failed to apply parser settings: Prefix IRI '{self.prefix_iri}' looks invalid"
                )
        elif getattr(self.graph, "base", None):
            self._set_default_prefix(Namespace(self.graph.base))
        else:  # ok to have no default namespace
            pass

        # Movement #2
        for prefix_key, uri in self.prefixes.items():
            if looks_like_iri(uri) == "absolute-iri":
                namespace = Namespace(uri)
            else:
                raise ParseException(
                    f"Failed to bind prefixes: IRI '{uri}' looks invalid"
                )
            self.graph.bind(prefix_key, namespace, replace=True)

        # Movement #3
        if getattr(self.graph, "base", None) is None:
            self.graph.base = pipeline.core.rdf.data.prefix_iri_to_base(self.prefix_iri)

    def namespace_map(self):
        return {
            prefix: Namespace(iri)
            for prefix, iri in list(self.graph.namespace_manager.namespaces())
        }

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
            mint_from_literal=self.serialisation_config.mint_from_arrows,
        )

    def resolve_type(self, rdf_type: str) -> Any:
        return self.coerce_to_uriref(
            cfg=self,
            value=rdf_type,
            mint_from_literal=self.serialisation_config.mint_from_types,
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
        UnableToCoerceException = pipeline.core.rdf.data.UnableToCoerceException

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
                if isinstance(note, str):
                    self.graph.add((decoration_subject, SKOS.note, Literal(note)))
                elif isinstance(note, list):
                    # It's okay to use an ordered list (Collection) because
                    # how child tokens are added to `tokens` list upstream
                    # is in XML document order: `f".//*[@parent='{parent_id}']")`
                    list_node = BNode()
                    # attach the list to the subject
                    # Note that skos:note does support object properties:
                    # https://www.w3.org/TR/skos-reference/#L1812
                    self.graph.add((decoration_subject, SKOS.note, list_node))
                    # build the rdf:List structure
                    Collection(self.graph, list_node, [Literal(item) for item in note])
                else:
                    raise UnableToCoerceException(
                        repr(note),
                        Literal,
                        "Decoration of an unsupported Python type",
                    )

        if hasattr(pipeline.core.internal.data, decorations_attr):
            delattr(pipeline.core.internal.data, decorations_attr)

    def serialize_all_individuals(self) -> None:
        """Serialize all individuals in blocks."""
        for (individual_id, individual_label), types_and_facts in self.blocks.items():
            self.add_individual_triples(
                individual_id, individual_label, types_and_facts
            )
