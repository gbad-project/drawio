# Cell classifier override refactor — implementation report

## Overview
- Converted the `CellKind`, `CellClassification`, and `DrawIOCellClassifier` helpers into proper DrawIO meta builder overrides so they are emitted via the generated pipeline namespace instead of being imported directly from `legacy/overrides`.
- Updated the `curie_validator` override to bind the classifier via `pipeline.core.internal.data` and to read the default standalone type from the pipeline registry, ensuring override discovery is authoritative.
- Regenerated `legacy/draw_io_parser.py` so the injected overrides appear inside `pipeline.core.internal.data` and removed the ad-hoc import shim previously baked into `_extract_individual_and_arrow_and_literal_cells`.

## Testing
- `bun run check` — ✅ (lint + format suites). Output trimmed to `/tmp/bun_check.log` tail for brevity.
- `bun run test:log:linux` — ❌ fails because the legacy baseline regeneration script now re-runs `python -m meta_builder` and `pytest`, which detect hundreds of baseline `.nt` differences before aborting. The downstream Bun test also aborts while trying to load prebuilt Pyodide wheels (rdflib) that are absent in this environment. Captured failure details in `tests/demo_logs/test.log` for review.
