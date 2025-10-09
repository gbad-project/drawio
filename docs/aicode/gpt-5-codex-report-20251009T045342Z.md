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

## Follow-up Automation (2025-10-09)
- Added `regenerate_baselines.py` to replay the legacy parser from historical commits, backfill missing property classifications, and materialise `.nt` graphs for pristine fixtures when baselines are absent.
- Defaulted the helper to skip overwriting existing baselines while still executing `pytest` so the regression suite runs against the freshly generated fixtures.
- Confirmed the helper against HEAD^, observed the static-property failure, and documented the automatic fallback behaviour plus the ability to force regeneration via `--force-overwrite` when required.

## Additional Testing
- `python src/main/webapp/plugins/rdfexport/legacy/tests/regenerate_baselines.py --max-commits 50`

## Baseline Regeneration Script Invocation (2025-10-09)
- Added a convenience shell wrapper `run_regeneration.sh` under `src/main/webapp/plugins/rdfexport/legacy/tests/` that invokes the reproducible baseline helper with the requested commit, window, and overwrite flags.
- Attempted to execute the wrapper to confirm behaviour; execution failed because the sandbox image does not include the `rdflib` dependency required by `regenerate_baselines.py`.
- Left the failure details in the execution log so downstream runs can install dependencies or supply a virtual environment before rerunning the helper.

## Additional Testing
- `src/main/webapp/plugins/rdfexport/legacy/tests/run_regeneration.sh`
## Baseline Regeneration Wrapper Verification (2025-10-10)
- Installed the missing `rdflib` dependency in the sandbox environment and re-ran `run_regeneration.sh` without modifying repository files.
- Confirmed that the helper replays commit `cf8f84bb84ff83843b6726ac96aff3a2055f4275`, regenerates all pristine fixture baselines with forced overwrites, and executes `pytest` to verify the regenerated outputs.

## Additional Testing
- `src/main/webapp/plugins/rdfexport/legacy/tests/run_regeneration.sh`
