from __future__ import annotations

from typing import Any

from rdflib import BNode, Namespace
from rdflib.namespace import RDF
from xml.etree.ElementTree import Element

from legacy.draw_io_parser import *
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F401, F403, F405


@override(phase="core", type="internal", role="control")
def _build_graph_from_raw_xml(
    raw_xml: str, config_args: dict[str, Any]
) -> DrawIOParserGraph:
    metadata_prefixes, base_uri, csv_path, parsed_root = _extract_drawio_metadata(
        raw_xml
    )
    prefixes = get_prefixes()
    prefixes.update(metadata_prefixes)

    working_xml = _strip_metadata_user_object(raw_xml, parsed_root)

    ontology_iri = config_args.get("ontology_iri") or get_ontology_iri()
    prefix = config_args.get("prefix") or get_prefix()
    prefix_iri = (
        config_args.get("prefix_iri") or base_uri or get_prefix_iri(ontology_iri)
    )

    serialisation_config = SerialisationConfig(
        infer_type_of_literals=config_args["infer_type_of_literals"],
        include_preamble=config_args["include_preamble"],
        ontology_iri=ontology_iri,
        prefix=prefix,
        prefix_iri=prefix_iri,
        indentation=config_args["indentation"],
        include_label=config_args["include_label"],
    )

    space_substitute = _parse_space_substitute(config_args["metacharacter_substitute"])
    metacharacter_substitutes = list(
        _parse_metacharacter_substitutes(config_args["metacharacter_substitute"])
    )

    _parse_capitalisation_scheme(config_args["capitalisation_scheme"])

    draw_io_xml_tree = DrawIOXMLTree(working_xml, prefixes)
    blocks, object_properties, datatype_properties = individual_blocks(
        draw_io_xml_tree.individuals_and_arrows(
            config_args["strict_mode"], config_args["max_gap"]
        ),
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

    def _interpret_flag(value: Any) -> bool:
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

    def _metadata_enables_rml(root: Element | None) -> bool:
        if root is None:
            return False
        metadata_node = root.find(".//mxGraphModel/root/UserObject[@id='0']")
        if metadata_node is None:
            return False
        flag = metadata_node.attrib.get("rmlEnabled")
        return _interpret_flag(flag)

    raw_flag = config_args.get("rml_enabled")
    rml_enabled = _interpret_flag(raw_flag) or _metadata_enables_rml(parsed_root)
    setattr(graph, "rml_enabled", rml_enabled)

    if rml_enabled:
        rr_ns = Namespace("http://www.w3.org/ns/r2rml#")
        graph.namespace_manager.bind("rr", rr_ns, replace=False)
        from rdflib.term import BNode

        blank_subject = BNode()
        graph.add((blank_subject, RDF.type, rr_ns.TriplesMap))

    return graph
