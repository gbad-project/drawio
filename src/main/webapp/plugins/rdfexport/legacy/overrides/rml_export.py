from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import Element

from rdflib import Namespace
from rdflib.namespace import RDF

from legacy.draw_io_parser import *  # type: ignore=imported-unused, redefined-builtin
from legacy.draw_io_parser import DrawIOParserGraph, pipeline  # type: ignore[attr-defined]
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="control")
def _build_graph_from_raw_xml(
    raw_xml: str, config_args: dict[str, Any]
) -> DrawIOParserGraph:
    metadata_prefixes, base_uri, csv_path, parsed_root = (
        pipeline.pre.xml.metadata._extract_drawio_metadata(  # type: ignore[attr-defined]
            raw_xml
        )
    )
    prefixes = get_prefixes()
    prefixes.update(metadata_prefixes)

    working_xml = pipeline.pre.xml.metadata._strip_metadata_user_object(
        raw_xml, parsed_root
    )  # type: ignore[attr-defined]

    ontology_iri = config_args["ontology_iri"] or get_ontology_iri()
    prefix = config_args["prefix"] or get_prefix()
    prefix_iri = config_args["prefix_iri"] or base_uri or get_prefix_iri(ontology_iri)

    serialisation_config = SerialisationConfig(
        infer_type_of_literals=config_args["infer_type_of_literals"],
        include_preamble=config_args["include_preamble"],
        ontology_iri=ontology_iri,
        prefix=prefix,
        prefix_iri=prefix_iri,
        indentation=config_args["indentation"],
        include_label=config_args["include_label"],
    )

    space_substitute = internal_control_core._parse_space_substitute(  # type: ignore[attr-defined]
        config_args["metacharacter_substitute"]
    )
    metacharacter_substitutes = list(
        internal_control_core._parse_metacharacter_substitutes(  # type: ignore[attr-defined]
            config_args["metacharacter_substitute"]
        )
    )

    _parse_capitalisation_scheme(  # type: ignore[name-defined]
        config_args["capitalisation_scheme"]
    )

    draw_io_xml_tree = DrawIOXMLTree(working_xml, prefixes)
    blocks, object_properties, datatype_properties = (
        internal_control_core.individual_blocks(  # type: ignore[attr-defined]
            draw_io_xml_tree.individuals_and_arrows(
                config_args["strict_mode"], config_args["max_gap"]
            ),
            metacharacter_substitutes,
            space_substitute,
            config_args["capitalisation_scheme"],
            prefixes,
        )
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

    def _coerce_flag(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        if value is None:
            return False
        return bool(value)

    def _metadata_enables_rml(parsed: Element | None) -> bool:
        if parsed is None:
            return False

        metadata_node = parsed.find(".//mxGraphModel/root/UserObject[@id='0']")
        if metadata_node is None:
            return False

        flag = metadata_node.attrib.get("rmlEnabled")
        if flag is None:
            return False

        return flag.strip().lower() in {"true", "1", "yes", "on"}

    rml_from_config = False
    if isinstance(config_args, dict):
        rml_from_config = _coerce_flag(config_args.get("rml_enabled"))

    if rml_from_config or _metadata_enables_rml(parsed_root):
        rr = Namespace("http://www.w3.org/ns/r2rml#")
        graph.namespace_manager.bind("rr", rr, replace=False)
        from rdflib import BNode

        graph.add((BNode(), RDF.type, rr.TriplesMap))

    return graph
