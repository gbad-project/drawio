from __future__ import annotations

import json
import urllib.parse
from datetime import datetime
from typing import Any, Iterator
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

    config_args["include_label"] = include_label
    config_args["label_disable"] = not include_label
    config_args["include_preamble"] = include_preamble
    config_args["preamble_disable"] = not include_preamble
    config_args["infer_type_of_literals"] = infer_type_of_literals
    config_args["infer_types_disable"] = not infer_type_of_literals

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

    metadata_rml_enabled = (
        _is_flag_enabled(metadata_node.attrib.get("rmlEnabled"))
        if metadata_node is not None
        else False
    )
    rml_enabled = (
        _is_flag_enabled(config_args.get("rml_enabled")) or metadata_rml_enabled
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
    graph_kwargs = graph_kwargs or {}

    toolkit_attr = "__drawio_serialisation_toolkit"
    factory_attr = "__drawio_serialisation_toolkit_factory"

    toolkit = getattr(pipeline.core.rdf.control, toolkit_attr, None)
    if toolkit is None:
        factory = getattr(pipeline.core.rdf.control, factory_attr, None)
        if factory is None:

            class DrawIOSerialisationToolkit:
                @staticmethod
                def _is_absolute_iri(candidate: str) -> bool:
                    if not candidate:
                        return False
                    if "://" in candidate:
                        return True
                    scheme, _, remainder = candidate.partition(":")
                    if not scheme or not remainder:
                        return False
                    return scheme.lower() in {"urn", "tag"} and bool(remainder.strip())

                def create_workspace(
                    self,
                    serialisation_config: SerialisationConfig,
                    prefixes: dict[str, str],
                    graph_cls: type[Graph],
                    graph_kwargs: dict[str, Any],
                ) -> tuple[Graph, dict[str, Namespace], str | None, str | None]:
                    graph = graph_cls(**graph_kwargs)

                    prefix = serialisation_config.prefix
                    prefix_iri = serialisation_config.prefix_iri or get_prefix_iri(
                        serialisation_config.ontology_iri
                    )

                    namespace_map: dict[str, Namespace] = {}
                    fallback_namespace: Namespace | None = None
                    if prefix_iri and self._is_absolute_iri(prefix_iri):
                        fallback_namespace = Namespace(prefix_iri)

                    for prefix_key, uri in prefixes.items():
                        if self._is_absolute_iri(uri):
                            namespace = Namespace(uri)
                        elif fallback_namespace is not None:
                            namespace = fallback_namespace
                        else:
                            raise ParseException(f"Prefix IRI '{uri}' looks invalid")

                        graph.bind(prefix_key, namespace, replace=True)
                        namespace_map[prefix_key] = namespace

                    if prefix and prefix_iri:
                        graph.bind(prefix, Namespace(prefix_iri), replace=True)

                    self._namespace_map = namespace_map

                    return graph, namespace_map, prefix, prefix_iri

                @staticmethod
                def extract_absolute_overrides(
                    blocks: Blocks, namespace_map: dict[str, Namespace]
                ) -> dict[str, str]:
                    overrides = {
                        individual_id: individual_label
                        for individual_id, individual_label in blocks.keys()
                        if "://" in individual_label
                    }

                    for individual_id, _ in blocks.keys():
                        decoded = urllib.parse.unquote(individual_id)
                        if ":" not in decoded:
                            continue
                        prefix, reference = decoded.split(":", 1)
                        namespace = namespace_map.get(prefix)
                        if namespace is None:
                            continue
                        overrides.setdefault(individual_id, str(namespace[reference]))

                    return overrides

                @staticmethod
                def _has_placeholder(identifier: str) -> bool:
                    if not identifier:
                        return False
                    if "{" in identifier or "}" in identifier:
                        return True
                    # Identifiers reaching this point may already be percent-encoded.
                    return "%7B" in identifier or "%7D" in identifier

                @staticmethod
                def _ensure_quoted_identifier(identifier: str) -> str:
                    trimmed = identifier.strip()
                    if not trimmed:
                        return trimmed
                    if (trimmed.startswith("%22") and trimmed.endswith("%22")) or (
                        trimmed.startswith('"%22') and trimmed.endswith('%22"')
                    ):
                        return trimmed
                    if not trimmed.startswith('"'):
                        trimmed = f'"{trimmed}'
                    if not trimmed.endswith('"'):
                        trimmed = f'{trimmed}"'
                    return trimmed

                @staticmethod
                def _encode_template_uri(uri: URIRef) -> URIRef:
                    text = str(uri)
                    if "Rr%3Atemplate%20%22" in text or "Rr%3Aconstant%20%22" in text:
                        return uri
                    if "#" in text:
                        base, local = text.split("#", 1)
                    else:
                        base, local = text, ""
                    if not local:
                        return uri
                    if local.startswith("%22"):
                        encoded_local = local
                    elif local.startswith('"'):
                        encoded_local = urllib.parse.quote(local, safe="")
                    else:
                        quoted = urllib.parse.quote(
                            f'"{urllib.parse.unquote(local)}"', safe=""
                        )
                        encoded_local = quoted
                    separator = "#" if base and not base.endswith(("#", "/")) else ""
                    return URIRef(f"{base}{separator}Rr%3Atemplate%20{encoded_local}")

                def resolve_entity_uri(
                    self,
                    identifier: str,
                    prefix: str | None,
                    prefix_iri: str | None,
                    absolute_overrides: dict[str, str],
                    label: str | None = None,
                ) -> URIRef:
                    identifier_text = str(identifier)
                    label_text = str(label) if label is not None else None
                    if identifier_text in absolute_overrides:
                        return URIRef(absolute_overrides[identifier_text])
                    has_placeholder = self._has_placeholder(identifier_text)
                    if not has_placeholder and label_text is not None:
                        has_placeholder = self._has_placeholder(label_text)
                        if has_placeholder:
                            identifier_text = label_text
                    if has_placeholder:
                        identifier_text = self._ensure_quoted_identifier(
                            identifier_text
                        )
                    if prefix and prefix_iri:
                        resolved = Namespace(prefix_iri)[identifier_text]
                        if has_placeholder:
                            resolved = self._encode_template_uri(resolved)
                        return resolved
                    if prefix_iri:
                        resolved = URIRef(f"{prefix_iri}{identifier_text}")
                        if has_placeholder:
                            resolved = self._encode_template_uri(resolved)
                        return resolved
                    return URIRef(identifier_text)

                def _resolve_property_uri(
                    self, prop: str, namespace_map: dict[str, Namespace]
                ) -> URIRef:
                    if self._is_absolute_iri(prop):
                        return URIRef(prop)
                    prefix, name = prop.split(":", 1)
                    return namespace_map[prefix][name]

                @staticmethod
                def coerce_literal(value: Any) -> Literal:
                    if isinstance(value, Literal):
                        return value

                    literal_candidate = value
                    if isinstance(literal_candidate, int) or (
                        isinstance(literal_candidate, str)
                        and literal_candidate.isnumeric()
                    ):
                        return Literal(literal_candidate, datatype=XSD.integer)

                    if isinstance(literal_candidate, float):
                        return Literal(literal_candidate, datatype=XSD.float)

                    if isinstance(literal_candidate, str):
                        try:
                            datetime.strptime(literal_candidate, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            return Literal(literal_candidate)
                        else:
                            return Literal(literal_candidate, datatype=XSD.date)

                    return Literal(literal_candidate)

                @staticmethod
                def value_sort_key(value: Any) -> tuple[int, str]:
                    if isinstance(value, tuple):
                        return (0, f"{value[0]}")
                    return (1, f"{value}")

                @staticmethod
                def unpack_value(
                    prop: str,
                    raw_value: Any,
                    object_properties: set[str],
                    datatype_properties: set[str],
                ) -> tuple[Any, bool]:
                    if (
                        isinstance(raw_value, tuple)
                        and len(raw_value) == 2
                        and isinstance(raw_value[1], bool)
                    ):
                        return raw_value
                    is_literal = (
                        prop in datatype_properties and prop not in object_properties
                    )
                    return raw_value, is_literal

                def iter_subjects(
                    self,
                    blocks: Blocks,
                    prefix: str | None,
                    prefix_iri: str | None,
                    absolute_overrides: dict[str, str],
                ) -> Iterator[tuple[str, str, URIRef, dict[str, set[Any]]]]:
                    for (
                        individual_id,
                        individual_label,
                    ), types_and_facts in blocks.items():
                        yield (
                            individual_id,
                            individual_label,
                            self.resolve_entity_uri(
                                individual_id,
                                prefix,
                                prefix_iri,
                                absolute_overrides,
                                individual_label,
                            ),
                            types_and_facts,
                        )

            def factory() -> DrawIOSerialisationToolkit:
                return DrawIOSerialisationToolkit()

            setattr(pipeline.core.rdf.control, factory_attr, factory)

        toolkit = factory()
        setattr(pipeline.core.rdf.control, toolkit_attr, toolkit)

    graph, namespace_map, prefix, prefix_iri = toolkit.create_workspace(
        serialisation_config, prefixes, graph_cls, graph_kwargs
    )

    csv_path = graph_kwargs.get("csv_path")
    if csv_path is None and hasattr(graph, "csv_path"):
        csv_path = getattr(graph, "csv_path")

    rr = Namespace("http://www.w3.org/ns/r2rml#")
    rml_ns = Namespace("http://semweb.mmlab.be/ns/rml#")
    ql = Namespace("http://semweb.mmlab.be/ns/ql#")

    graph.bind("rr", rr, replace=False)
    graph.bind("rml", rml_ns, replace=False)
    graph.bind("ql", ql, replace=False)
    graph.bind("rdfs", RDFS, replace=False)

    def _add_constant_object_map(
        predicate_map_owner: Any, predicate_uri: URIRef, constant: Any
    ) -> None:
        predicate_object_map = BNode()
        graph.add((predicate_map_owner, rr.predicateObjectMap, predicate_object_map))
        graph.add((predicate_object_map, rr.predicate, predicate_uri))

        object_map = BNode()
        graph.add((predicate_object_map, rr.objectMap, object_map))
        graph.add((object_map, rr.constant, constant))

        if isinstance(constant, URIRef):
            graph.add((object_map, rr.termType, rr.IRI))
        elif isinstance(constant, Literal):
            graph.add((object_map, rr.termType, rr.Literal))
            if constant.datatype:
                graph.add((object_map, rr.datatype, constant.datatype))
            if constant.language:
                graph.add((object_map, rr.language, Literal(constant.language)))

    def _resolve_property_uri(prop: str) -> URIRef:
        if toolkit._is_absolute_iri(prop):
            return URIRef(prop)
        prefix, name = prop.split(":", 1)
        return namespace_map[prefix][name]

    absolute_overrides = toolkit.extract_absolute_overrides(blocks, namespace_map)

    logical_source_default = Literal("drawio")
    if csv_path:
        logical_source_value = Literal(csv_path)
    elif serialisation_config.ontology_iri:
        logical_source_value = Literal(serialisation_config.ontology_iri)
    else:
        logical_source_value = logical_source_default

    for (
        individual_id,
        individual_label,
        subject_uri,
        types_and_facts,
    ) in toolkit.iter_subjects(blocks, prefix, prefix_iri, absolute_overrides):
        triples_map = BNode()
        graph.add((triples_map, RDF.type, rr.TriplesMap))

        logical_source = BNode()
        graph.add((triples_map, rml_ns.logicalSource, logical_source))
        graph.add((logical_source, rml_ns.source, logical_source_value))
        graph.add((logical_source, rml_ns.referenceFormulation, ql.CSV))

        subject_map = BNode()
        graph.add((triples_map, rr.subjectMap, subject_map))
        graph.add((subject_map, rr.termType, rr.IRI))
        graph.add((subject_map, rr.constant, subject_uri))

        for rdf_type in sorted(types_and_facts.get("Types", set())):
            type_prefix, type_name = rdf_type.split(":", 1)
            class_uri = namespace_map[type_prefix][type_name]
            graph.add((subject_map, rr["class"], class_uri))

        if serialisation_config.include_label:
            _add_constant_object_map(triples_map, RDFS.label, Literal(individual_label))

        for prop, values in sorted(types_and_facts.items()):
            if prop == "Types":
                continue

            predicate_uri = _resolve_property_uri(prop)

            for raw_value in sorted(values, key=toolkit.value_sort_key):
                value, is_literal = toolkit.unpack_value(
                    prop, raw_value, object_properties, datatype_properties
                )

                if not is_literal:
                    target_uri = toolkit.resolve_entity_uri(
                        str(value), prefix, prefix_iri, absolute_overrides
                    )
                    _add_constant_object_map(triples_map, predicate_uri, target_uri)
                else:
                    if serialisation_config.infer_type_of_literals:
                        literal_value = toolkit.coerce_literal(value)
                    elif isinstance(value, Literal):
                        literal_value = value
                    else:
                        literal_value = Literal(value)
                    _add_constant_object_map(triples_map, predicate_uri, literal_value)

    return graph


pipeline.core.rdf.control.serialise_to_rml = serialise_to_rml
