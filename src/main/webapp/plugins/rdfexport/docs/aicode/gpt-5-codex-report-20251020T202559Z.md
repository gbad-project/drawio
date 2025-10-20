# Debug Session Report — DrawIO RDF Export Debugger

## Summary
- Investigated `python -m debug --scenario aa37-department-of-health` failing to classify DrawIO cells as individuals.
- Identified missing prefix expansion in the debugger's cell classification helper which caused all CURIE tokens to be rejected.
- Updated `_extract_cell_classifications` to reuse `legacy.draw_io_parser` metadata utilities so the classifier sees the full prefix map (built-ins + diagram metadata + CLI overrides).
- Normalised the aa37 scenario YAML to reference the repository fixture path so it works cross-platform.

## Investigation Notes
1. Reproduced the issue via `python -m debug --drawio "tests/fixtures/AA37 Department of Health.drawio" --slug aa37-department-of-health` after bootstrapping dependencies with `bun install --force`, `bun run setup:uv`, and `bun run setup:pyodide`.
2. Observed the debugger reporting 83 cell classifications, but only `LITERAL`/`ARROW_LABEL` kinds appeared in `debug/map.json`.
3. Confirmed that `DrawIOCellClassifier` requires known CURIE prefixes to emit `TYPED_INDIVIDUAL`/`STANDALONE_INDIVIDUAL`, yet the debugger only forwarded ad-hoc CLI prefixes (`mock1`) instead of the parser defaults.
4. Verified the DrawIO parser's `_extract_drawio_metadata` and `get_prefixes` helpers merge built-in RiC-O prefixes with metadata-defined ones before parsing.

## Fix Implementation
- Hooked `_extract_cell_classifications` into `_extract_drawio_metadata` to reuse the parser's XML root and metadata prefixes.
- Seeded the prefix map with `get_prefixes()` and layered metadata + CLI overrides to mimic the runtime pipeline.
- Removed the redundant local `ElementTree` import once metadata parsing moved to the parser helper.
- Updated `debug/scenarios/aa37-department-of-health.yml` to quote the fixture path and keep it relative to the repo.

## Verification
- `CI=1 PRETTIER_LOG_LEVEL=error bun run check`
- `CI=1 bun run test:log:linux`
- Manual inspection of `debug/map.json` confirmed 17 `TYPED_INDIVIDUAL` entries and preserved literal counts for the aa37 scenario.

