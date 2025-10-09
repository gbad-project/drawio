# Task 2a – Remove Hardcoded CURIE Validation from DrawIO Parser

## Summary
- Replaced static RiC-O class, object property, and datatype property whitelists with dynamic CURIE validation driven by the parser's prefix dictionary.
- Extended the `Arrow` representation and downstream processing to classify datatype/object properties without relying on global lists.
- Added regression baselines for legacy fixtures and comprehensive pytest coverage, including CURIE acceptance, rejection, and fixture isomorphism checks after normalisation.

## Implementation Notes
- Introduced `_split_curie` and `_ensure_known_curie` helpers to centralise CURIE validation using prefix dictionaries.
- Updated `DrawIOXMLTree._arrow` to track whether an edge targets a literal or an individual by inspecting literal cells and previously parsed individuals.
- Refactored `individual_blocks` to return both the aggregated blocks and dynamically discovered property classifications; downstream serialisation now consumes these sets.
- Normalised graph comparison in tests to exclude ontology preamble and property type declarations that vary with runtime or broad property inventories.
- Generated `.nt` baselines for every pristine `.drawio` fixture (skipping legacy failures) using the unmodified parser prior to refactor for regression purposes.

## Testing
- `pytest src/main/webapp/plugins/rdfexport/legacy/tests/test_curie_validation.py`

## Outstanding Questions / Follow-ups
- Consider extending prefix acquisition beyond the static `get_prefixes()` helper once metadata-driven prefix injection (Task 2b) is implemented.
- Evaluate whether property definition triples should be generated on-demand for non-RiC namespaces or exposed through configuration knobs.
