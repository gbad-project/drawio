# rdfexport Flowchart metadata regression fix

## Summary
- Investigated pytest failure `ArrowWithoutIndividualAsSourceException` triggered when metadata preamble on Flowchart_tweaked.drawio used a legacy `<object>` wrapper.
- Added `legacy/overrides/metadata.py` override so `_extract_drawio_metadata` collects prefixes from both `<UserObject>` and `<object>` preambles and `_strip_metadata_user_object` replaces each wrapper with an `mxCell` stub.
- Regenerated the parser via `meta_builder` and verified Flowchart fixtures parse with metadata patcher output.

## Testing
- `.venv/bin/python -m pytest legacy/tests/test_patched_parser.py::test_generated_metadata_fixtures_round_trip`
- `bun run test`
- `CI=1 bun run check`
- `bun run test:log:linux`
