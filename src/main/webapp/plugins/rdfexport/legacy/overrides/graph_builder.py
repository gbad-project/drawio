from __future__ import annotations

from typing import Any

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="control")
def _build_graph_from_raw_xml(
    raw_xml: str, config_args: dict[str, Any]
) -> DrawIOParserGraph:
    """Assemble a parser graph from Draw.io XML using the classifier override."""

    classifier_cls = getattr(pipeline.core.xml.data, "DrawIOCellClassifier", None)
    if classifier_cls is None:
        raise RuntimeError("DrawIOCellClassifier override is not available")

    metadata_prefixes, base_uri, csv_path, parsed_root = (
        pipeline.pre.xml.metadata._extract_drawio_metadata(raw_xml)
    )
    prefixes = pipeline.pre.internal.metadata.get_prefixes()
    prefixes.update(metadata_prefixes)
    working_xml = pipeline.pre.xml.metadata._strip_metadata_user_object(
        raw_xml, parsed_root
    )

    ontology_iri = config_args["ontology_iri"] or get_ontology_iri()
    prefix = config_args["prefix"] or get_prefix()
    prefix_iri = config_args["prefix_iri"] or base_uri or get_prefix_iri(ontology_iri)

    serialisation_config = SerialisationConfig(
        infer_type_of_literals=not config_args.get("infer_types_disable", False),
        include_preamble=not config_args.get("preamble_disable", False),
        ontology_iri=ontology_iri,
        prefix=prefix,
        prefix_iri=prefix_iri,
        indentation=config_args["indentation"],
        include_label=not config_args.get("label_disable", False),
    )
    _parse_capitalisation_scheme(config_args["capitalisation_scheme"])

    classifier = classifier_cls(working_xml, prefixes)

    control = pipeline.core.internal.control
    space_substitute = control._parse_space_substitute(
        config_args["metacharacter_substitute"]
    )
    metacharacter_substitutes = list(
        control._parse_metacharacter_substitutes(
            config_args["metacharacter_substitute"]
        )
    )

    blocks, object_properties, datatype_properties = control.individual_blocks(
        classifier.get_graph_elements(),
        metacharacter_substitutes,
        space_substitute,
        config_args["capitalisation_scheme"],
        prefixes,
    )

    graph = serialise_to_graph(
        blocks,
        object_properties,
        datatype_properties,
        serialisation_config,
        prefixes,
        graph_cls=DrawIOParserGraph,
        graph_kwargs={"csv_path": csv_path},
    )

    if base_uri:
        graph.namespace_manager.bind("", Namespace(base_uri), replace=True)

    rml_hook = getattr(pipeline.core.rdf.control, "maybe_enable_rml", None)
    if callable(rml_hook):
        rml_hook(graph, config_args, parsed_root)

    return graph
