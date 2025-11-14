from __future__ import annotations


from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


from legacy.overrides.core.rdf.control.serialization_helper import (
    RDFSerializationHelper,
)


@override(phase="core", type="rdf", role="control")
class RDFSerializer(RDFSerializationHelper):
    """Standard RDF serialization (regular triples)."""

    def __init__(self, *args, **kwargs):
        RDFSerializationHelper = pipeline.core.rdf.control.RDFSerializationHelper
        RDFSerializationHelper.__init__(self, *args, **kwargs)
        self.coerce_to_uriref = pipeline.core.rdf.control.coerce_to_uriref
        self.coerce_to_literal = pipeline.core.rdf.control.coerce_to_literal

    def add_individual_triples(
        self, individual_id: str, individual_label: str, types_and_facts: dict
    ) -> None:
        """Add triples for a single individual."""
        individual_uri = self.coerce_to_uriref(self, individual_id)

        # Add NamedIndividual type
        self.graph.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Add RDF types
        for rdf_type in types_and_facts.get("Types", set()):
            self.graph.add((individual_uri, RDF.type, self.resolve_type(rdf_type)))

        # Add label if configured
        if self.serialisation_config.include_label:
            self.graph.add((individual_uri, RDFS.label, Literal(individual_label)))

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
                    target_uri = self.coerce_to_uriref(self, value)
                    self.graph.add((individual_uri, prop_uri, target_uri))
                else:
                    # Datatype property - create literal
                    literal_value = self.coerce_to_literal(self, value)
                    self.graph.add((individual_uri, prop_uri, literal_value))

    def serialize_all_individuals(self) -> None:
        """
        Serialize all individuals in blocks.

        Will pick up this subclass's `add_individual_triples` at runtime.
        """
        super().serialize_all_individuals()


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
