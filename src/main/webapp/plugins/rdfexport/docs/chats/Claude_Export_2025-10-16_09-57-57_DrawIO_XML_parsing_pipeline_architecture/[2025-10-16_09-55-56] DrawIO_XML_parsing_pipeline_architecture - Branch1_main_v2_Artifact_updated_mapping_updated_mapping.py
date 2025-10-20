# Artifact ID: updated_mapping
# Branch: 1 (main) (6ae7dc60...)
# Version: 2
# Command: rewrite
# UUID: bc85c379-c7dc-4cb0-8b1d-b23f252d49d4
# Created: 10/16/2025, 9:55:56 AM
# Change: Rewritten

# ---

MAPPING: List[Tuple[str, str, str, str]] = [
    # ===== PRE PHASE =====
    
    # xml.metadata.pre - Extract metadata from XML
    ("_extract_drawio_metadata", "xml", "metadata", "pre"),
    ("_strip_metadata_user_object", "xml", "metadata", "pre"),
    
    # internal.metadata.pre - Constants, defaults, type aliases, getters
    ("DEFAULT_CAPITALISATION_SCHEME", "internal", "metadata", "pre"),
    ("DEFAULT_INDENTATION", "internal", "metadata", "pre"),
    ("DEFAULT_MAX_GAP", "internal", "metadata", "pre"),
    ("OWL_METACHARACTERS", "internal", "metadata", "pre"),
    ("Blocks", "internal", "metadata", "pre"),
    ("CellID", "internal", "metadata", "pre"),
    ("XCoordinate", "internal", "metadata", "pre"),
    ("YCoordinate", "internal", "metadata", "pre"),
    ("Width", "internal", "metadata", "pre"),
    ("Height", "internal", "metadata", "pre"),
    ("ArrowStart", "internal", "metadata", "pre"),
    ("ArrowEnd", "internal", "metadata", "pre"),
    ("Label", "internal", "metadata", "pre"),
    ("ArrowData", "internal", "metadata", "pre"),
    ("Dimensions", "internal", "metadata", "pre"),
    ("Paragraph", "internal", "metadata", "pre"),
    ("Metacharacter", "internal", "metadata", "pre"),
    ("Replacement", "internal", "metadata", "pre"),
    ("get_prefixes", "internal", "metadata", "pre"),
    ("get_ontology_iri", "internal", "metadata", "pre"),
    ("get_prefix", "internal", "metadata", "pre"),
    ("get_prefix_iri", "internal", "metadata", "pre"),
    ("SerialisationConfig", "internal", "metadata", "pre"),
    
    # internal.control.pre - User input via CLI
    ("_arguments_parser", "internal", "control", "pre"),
    
    # rdf.data.pre - String manipulation for RDF compliance
    ("_handle_spaces", "rdf", "data", "pre"),
    ("_replace_metacharacter", "rdf", "data", "pre"),
    ("_replace_metacharacters", "rdf", "data", "pre"),
    
    # rdf.control.pre - Validation of RDF config
    ("_parse_capitalisation_scheme", "rdf", "control", "pre"),
    
    # ===== CORE PHASE =====
    
    # xml.data.core - ALL XML parsing to Individual/Arrow instances
    ("NothingToParseException", "xml", "data", "core"),
    ("NoSourceException", "xml", "data", "core"),
    ("NoTargetException", "xml", "data", "core"),
    ("_NoValueException", "xml", "data", "core"),
    ("_NoCellCloseEnoughException", "xml", "data", "core"),
    ("ParseException", "xml", "data", "core"),
    ("NodeHTMLParser", "xml", "data", "core"),
    ("DrawIOXMLTree", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_with_id", "xml", "data", "core"),
    ("DrawIOXMLTree._value_of", "xml", "data", "core"),
    ("DrawIOXMLTree._parent_of", "xml", "data", "core"),
    ("DrawIOXMLTree._child_of", "xml", "data", "core"),
    ("DrawIOXMLTree._geometry", "xml", "data", "core"),
    ("DrawIOXMLTree._x_and_y_in_geometry", "xml", "data", "core"),
    ("DrawIOXMLTree._has_correct_as_attribute", "xml", "data", "core"),
    ("DrawIOXMLTree._is_locked", "xml", "data", "core"),
    ("DrawIOXMLTree._start_or_end", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_start", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_end", "xml", "data", "core"),
    ("DrawIOXMLTree._dimensions", "xml", "data", "core"),
    ("DrawIOXMLTree._is_possible_literal", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_label", "xml", "data", "core"),
    ("DrawIOXMLTree._add_arrow_if_find_label", "xml", "data", "core"),
    ("DrawIOXMLTree._extract_individual_and_arrow_and_literal_cells", "xml", "data", "core"),
    ("DrawIOXMLTree._close_enough", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_close_to", "xml", "data", "core"),
    ("DrawIOXMLTree._defines_individual", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_is_literal", "xml", "data", "core"),
    ("DrawIOXMLTree._source_or_target", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow", "xml", "data", "core"),
    ("DrawIOXMLTree.individuals_and_arrows", "xml", "data", "core"),
    
    # internal.data.core - Internal model classes and data operations
    ("Individual", "internal", "data", "core"),
    ("Arrow", "internal", "data", "core"),
    ("_split_curie", "internal", "data", "core"),
    ("_ensure_known_curie", "internal", "data", "core"),
    ("_verify_is_ric_class", "internal", "data", "core"),
    ("_SourceNotIndividualException", "internal", "data", "core"),
    ("ArrowWithoutIndividualAsSourceException", "internal", "data", "core"),
    ("_add_individual_type", "internal", "data", "core"),
    
    # internal.control.core - Orchestration: couples data with metadata, produces blocks/props
    ("_parse_space_substitute", "internal", "control", "core"),
    ("_parse_metacharacter_substitutes", "internal", "control", "core"),
    ("individual_blocks", "internal", "control", "core"),
    ("_build_graph_from_raw_xml", "internal", "control", "core"),
    
    # rdf.data.core - RDF-specific exceptions
    ("NotInKnownException", "rdf", "data", "core"),
    ("_MetacharacterSubstituteParseException", "rdf", "data", "core"),
    ("MetacharacterException", "rdf", "data", "core"),
    ("_InvalidCapitalisationSchemeException", "rdf", "data", "core"),
    
    # rdf.control.core - Graph class and serialization (called from _build_graph_from_raw_xml)
    ("DrawIOParserGraph", "rdf", "control", "core"),
    ("serialise_to_graph", "rdf", "control", "core"),
    
    # ===== POST PHASE =====
    
    # internal.control.post - SDK/CLI wrappers
    ("parse_drawio_to_graph", "internal", "control", "post"),
    ("_run", "internal", "control", "post"),
    ("main", "internal", "control", "post"),
]