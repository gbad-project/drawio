# Codex Report (2025-10-14T07:00:00Z)

## Summary
- Investigated pipeline URI handling and confirmed `runDrawioPipeline` returned Turtle that did not honor the diagram base when present.
- Added Turtle post-processing in `src/mockBlackBox.ts` to rewrite relative IRIs using the parser-supplied base URI.
- Updated `_default_parser_config` in `pyodide_pipeline/drawio_pipeline.py` to stabilize ontology IRIs for baseline comparisons.
- Enhanced `_normalise_graph` in `legacy/tests/test_patched_parser.py` so metadata-patched fixtures canonicalize diagram-specific IRIs before isomorphism checks.
- Regenerated demo test log via `bun run test:log:linux`.

## Testing
- `bun run fix`
- `bun run check`
- `bun run test`
- `bun run test:log:linux`
