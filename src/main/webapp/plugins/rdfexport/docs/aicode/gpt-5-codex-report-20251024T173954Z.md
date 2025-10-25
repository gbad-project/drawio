# RDF Export Strict Mode / Label Flag Investigation – 2025-10-24

## Summary
- Reproduced existing Bun pipeline logs via `bun run test:all:log:show` to establish baseline (all passing/expected skips).
- Installed project dependencies with `bun install`, hydrated Python environment with `bun run setup:uv`, and refreshed Pyodide assets through `bun run setup:pyodide` per contributor workflow.
- Audited TypeScript configuration plumbing and Python overrides to locate the gap between stored parser settings (`includeLabel`, `strictMode`, etc.) and `_build_graph_from_raw_xml` expectations (`*_disable` flags).
- Updated the TypeScript Pyodide payload to ship both positive booleans and legacy `*_disable` flags so metadata travels consistently, and taught the `_build_graph_from_raw_xml` override to honour either convention when constructing its `SerialisationConfig`.
- Extended Bun and pytest coverage to assert that disabling labels actually removes `rdfs:label` triples and that strict-mode parsing now raises when expected, preventing silent regressions across UI, Pyodide, and CLI pathways.
- Recorded the fix in `CHANGELOG.md`.

## Testing
- `bun run test:all:log:show` (baseline log review)
- `bun install`
- `bun run setup:uv`
- `bun run setup:pyodide`
- `bun run test`
- `bun run check`
- `bun run test:all:log:linux`
- `uv run pytest`

## Follow-up Considerations
- New tests explicitly cover include-label and strict-mode behaviour; consider adding similar coverage for `include_preamble`/`infer_type_of_literals` if future regressions occur.
- The Pyodide payload now includes redundant disable flags—keep both conventions until legacy CLI paths are confirmed to rely solely on the new booleans.
