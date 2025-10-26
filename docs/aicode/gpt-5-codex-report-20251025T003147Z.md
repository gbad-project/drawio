# RDF Export Overrides Update Report

## Summary
- Investigated classification of literal vs CURIE nodes in the Class_Diagram_tweaked fixture.
- Added regression coverage in `legacy/tests/test_patched_parser.py` to capture literal → CURIE → literal transitions and the rounded style regression.
- Adjusted `_style_denotes_literal` override to respect `rounded=1` only for top-level cells or swimlane-styled attribute containers.
- Regenerated the parser via `meta_builder`, ran lint/format pipelines, and refreshed debug/test logs.

## Testing
- Targeted pytest for the new regression and affected flowchart tests.
- `bun run test:all:log:linux` (refresh pytest, debug CLI, and Bun suites).
- `bun run test:all:log:show` to inspect the latest captured logs.

## Notes
- Logs under `tests/demo_logs/` were updated as part of the mandated workflow.
- No changes were committed to generated debug map artefacts beyond required log refresh.
