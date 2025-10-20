# Debugging AA37-with-metadata-even-more-severely-mocked scenario

## Context
- Ran `python -m debug --scenario aa37-with-metadata-even-more-severely-mocked` after preparing the environment (Bun install, uv sync, Pyodide assets). Observed misclassified cells in `debug/map.json`.
- Verified examples:
  - `EUA9VVVl7iRi0US9AbU_-2` ("List pnnpni") lacked all type tokens and appeared as a literal despite having child type rows.
  - `EUA9VVVl7iRi0US9AbU_-16` ("Vertical Container") failed to surface its type `lol:index`.
  - `EUA9VVVl7iRi0US9AbU_-9` (decoration text) showed up as a literal rather than a decoration.
- Confirmed that `_apply_metadata_overrides` stripped the diagram’s prefix metadata before classification and that parent containers were not promoted to individuals when their typed children resolved to valid CURIEs.

## Changes made
1. Updated `Debugger._run_scenario` to classify cells using the original DrawIO XML so metadata-derived prefixes remain available.
2. Enhanced `_extract_cell_classifications`:
   - Track edge connectivity and typed-child relationships before classifying cells.
   - Promote parents of typed individuals to `STANDALONE_INDIVIDUAL`, merging the child tokens and recording `derived_type_cells`.
   - Reclassify unconnected literals as `DECORATION` (mirrors `legacy/tests/test_cell_classifier.py`).
   - Record `parent_cell_id` on typed children for traceability.
3. Regenerated `debug/map.json` via the debugger run; confirmed the examples now read as expected (individual tokens aggregated, decorations marked correctly).

## Verification
- Re-ran `python -m debug --scenario debug/scenarios/aa37-with-metadata-even-more-severely-mocked.yml` to refresh the map and inspect the corrected entries.
- Executed `bun run check` (lint + formatting) and `bun run test:log:linux`.
  - The latter exercises pytest suites (`legacy/tests/test_cell_classifier.py` checks the same decoration logic) and the Bun integration tests that drive the Pyodide pipeline, ensuring the classification semantics line up with the debug output.

## Notes
- Symlinked the macOS-specific fixture path under `/Volumes/home/anonymous/...` to reuse the existing scenario YAML.
- No changes were required in the generated parser; all adjustments live in the debugger helper.
