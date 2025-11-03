# RDFExport serialization refactor

## Summary
- Redirected `serialise_to_graph`/`serialise_to_rml` to build graph triples directly from `DrawIOCellClassifier` classifications and introduced structured hooks for RDF/RML serializers.
- Removed the obsolete `individual_blocks` override and refreshed parser tests to validate the new serialization surface instead of the legacy blocks helper.
- Regenerated `legacy/draw_io_parser.py` via meta builder and updated Bun/pytest regression logs.

## Testing
- `bun run check` (fails: repository-wide formatter still reports unformatted `rmlmapper_workflows/*` files outside the override scope.)
- `bun run test:all:log:linux`
