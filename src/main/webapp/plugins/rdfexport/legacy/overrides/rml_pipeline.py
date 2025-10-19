from __future__ import annotations

from typing import Any

from legacy.draw_io_parser import *  # noqa: F401,F403,F405
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F401, F403, F405


@override(phase="core", type="internal", role="control")
def _build_graph_from_raw_xml(
    raw_xml: str, config_args: dict[str, Any]
) -> DrawIOParserGraph:
    import sys
    from pathlib import Path

    module_root = Path(__file__).resolve().parent
    package_root = module_root.parent
    overrides_dir = module_root / "overrides"
    for candidate in (package_root, module_root, overrides_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    try:
        from legacy.overrides import (
            rml_state as _rml_state,
        )  # local import for generated file
        from legacy.overrides import rml_builder as _rml_builder
    except ModuleNotFoundError:  # pragma: no cover - Pyodide fallback path
        import importlib

        _rml_state = importlib.import_module("rml_state")
        _rml_builder = importlib.import_module("rml_builder")

    metadata_prefixes, base_uri, csv_path, parsed_root = _extract_drawio_metadata(
        raw_xml
    )
    prefixes = get_prefixes()
    prefixes.update(metadata_prefixes)

    _rml_state.update(prefixes=prefixes)

    working_xml = _strip_metadata_user_object(raw_xml, parsed_root)

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

    metadata = _rml_state.current()
    graph.rml_metadata = {
        "base_uri": base_uri,
        "csv_path": csv_path,
        "ontology_iri": ontology_iri,
    }

    if metadata.rml_enabled:
        rml_graph = _rml_builder.build_rml_graph(
            ontology_iri=ontology_iri,
            base_uri=base_uri,
            csv_path=csv_path,
            prefixes=metadata.prefixes,
            blocks=blocks,
        )
        graph.rml_enabled = True
        graph.rml_graph = rml_graph
        graph.rml_triple_count = len(rml_graph)
        graph.rml_serialization = rml_graph.serialize(format="turtle")
    else:
        graph.rml_enabled = False
        graph.rml_graph = None
        graph.rml_triple_count = 0
        graph.rml_serialization = None

    return graph
