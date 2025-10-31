from __future__ import annotations

import json
from html import unescape

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="control")
def _build_graph_from_raw_xml(
    raw_xml: str, config_args: dict[str, Any]
) -> DrawIOParserGraph:
    """
    Builds an RDF graph from raw Draw.io XML using the new self-contained
    DrawIOCellClassifier, completely bypassing DrawIOXMLTree.
    """
    DrawIOCellClassifier = getattr(pipeline.core.xml.data, "DrawIOCellClassifier", None)

    def _is_flag_enabled(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)

    def _coerce_optional_flag(value: Any) -> bool | None:
        if value is None:
            return None
        return _is_flag_enabled(value)

    def _resolve_enabled_flag(
        config: dict[str, Any],
        enable_key: str,
        disable_key: str,
        default: bool,
    ) -> bool:
        if disable_key in config:
            return not _is_flag_enabled(config[disable_key])
        if enable_key in config:
            return _is_flag_enabled(config[enable_key])
        return default

    # 1. Initial Setup and Configuration
    metadata_prefixes, base_uri, csv_path, parsed_root = (
        pipeline.pre.xml.metadata._extract_drawio_metadata(raw_xml)
    )
    metadata_node = (
        parsed_root.find(".//mxGraphModel/root/gbadMetadata[@id='0']")
        if parsed_root is not None
        else None
    )
    if metadata_node is None and parsed_root is not None:
        metadata_node = parsed_root.find(".//mxGraphModel/root/gbadMetadata")
    if metadata_node is None and parsed_root is not None:
        metadata_node = parsed_root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if metadata_node is None and parsed_root is not None:
        metadata_node = parsed_root.find(".//mxGraphModel/root/UserObject")
    if metadata_node is None and parsed_root is not None:
        metadata_node = parsed_root.find(".//mxGraphModel/root/object[@id='0']")
    prefixes = pipeline.pre.internal.metadata.get_prefixes()
    prefixes.update(metadata_prefixes)
    working_xml = pipeline.pre.xml.metadata._strip_metadata_user_object(
        raw_xml, parsed_root
    )

    ontology_iri = config_args["ontology_iri"] or get_ontology_iri()
    prefix = config_args["prefix"] or get_prefix()
    prefix_iri = config_args["prefix_iri"] or base_uri or get_prefix_iri(ontology_iri)

    include_label = _resolve_enabled_flag(
        config_args,
        "include_label",
        "label_disable",
        True,
    )
    include_preamble = _resolve_enabled_flag(
        config_args,
        "include_preamble",
        "preamble_disable",
        True,
    )
    infer_type_of_literals = _resolve_enabled_flag(
        config_args,
        "infer_type_of_literals",
        "infer_types_disable",
        True,
    )
    rml_enabled = _resolve_enabled_flag(
        config_args,
        "rml_enabled",
        None,
        False,
    )

    config_args["include_label"] = include_label
    config_args["label_disable"] = not include_label
    config_args["include_preamble"] = include_preamble
    config_args["preamble_disable"] = not include_preamble
    config_args["infer_type_of_literals"] = infer_type_of_literals
    config_args["infer_types_disable"] = not infer_type_of_literals
    config_args["rml_enabled"] = rml_enabled

    serialisation_config = SerialisationConfig(
        infer_type_of_literals=infer_type_of_literals,
        include_preamble=include_preamble,
        ontology_iri=ontology_iri,
        prefix=prefix,
        prefix_iri=prefix_iri,
        indentation=config_args["indentation"],
        include_label=include_label,
    )
    _parse_capitalisation_scheme(config_args["capitalisation_scheme"])

    # 2. Instantiate Classifier to process the entire XML
    # All parsing logic is now encapsulated here.
    strict_mode = _is_flag_enabled(config_args.get("strict_mode"))
    try:
        max_gap = float(config_args.get("max_gap", DEFAULT_MAX_GAP))
    except (TypeError, ValueError):
        max_gap = float(DEFAULT_MAX_GAP)

    explicit_strip_html = "strip_html" in config_args
    config_strip_html = config_args.get("strip_html", True)

    metadata_strip_html: bool | None = None
    if metadata_node is not None:
        metadata_strip_html = _coerce_optional_flag(
            metadata_node.attrib.get("stripHtml")
        )
        if metadata_strip_html is None:
            settings_attr = metadata_node.attrib.get("rdfParserSettings")
            if settings_attr:
                try:
                    settings_payload = json.loads(unescape(settings_attr))
                except json.JSONDecodeError:
                    settings_payload = {}
                if isinstance(settings_payload, dict):
                    settings_section = settings_payload.get("settings")
                    if isinstance(settings_section, dict):
                        metadata_strip_html = _coerce_optional_flag(
                            settings_section.get("stripHtml")
                        )

    if explicit_strip_html:
        strip_html_enabled = _is_flag_enabled(config_strip_html)
    elif metadata_strip_html is not None:
        strip_html_enabled = metadata_strip_html
    else:
        strip_html_enabled = _is_flag_enabled(config_strip_html)

    classifier = DrawIOCellClassifier(
        working_xml,
        prefixes,
        strict_mode=strict_mode,
        max_gap=max_gap,
        strip_html=strip_html_enabled,
    )

    # 3. Generate Intermediate Blocks from Classifier's results
    space_substitute = internal_control_core._parse_space_substitute(
        config_args["metacharacter_substitute"]
    )
    metacharacter_substitutes = list(
        internal_control_core._parse_metacharacter_substitutes(
            config_args["metacharacter_substitute"]
        )
    )

    blocks, object_properties, datatype_properties = (
        internal_control_core.individual_blocks(
            classifier.get_graph_elements(),  # Use the new generator
            metacharacter_substitutes,
            space_substitute,
            config_args["capitalisation_scheme"],
            prefixes,
        )
    )

    # 4. Serialize to Final Graph
    serializer = (
        pipeline.core.rdf.control.serialise_to_rml
        if rml_enabled
        else serialise_to_graph
    )
    graph = serializer(
        blocks,
        object_properties,
        datatype_properties,
        serialisation_config,
        prefixes,
        graph_cls=DrawIOParserGraph,
        graph_kwargs={"csv_path": csv_path},
    )

    # 5. Final post-processing (e.g., base URI binding)
    if base_uri:
        graph.namespace_manager.bind("", Namespace(base_uri), replace=True)

    return graph
