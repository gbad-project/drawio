# RDF serializer refactor (2025-11-03)

## Summary

- Ran the standard contributor bootstrap (`bun install`, `bun run setup:uv`,
  `bun run setup:pyodide`) and captured the pre-change regression status via
  `bun run test:all:log:show` before making any edits.
- Reworked `legacy/overrides/serialisers.py` so `RDFSerializationHelper`
  builds blocks/object/datatype property sets directly from
  `DrawIOCellClassifier`, removed the obsolete
  `individual_blocks` override from `curie_validator.py`, and updated
  `legacy/overrides/rml_export.py` plus TypeScript bindings to use the new
  serializer signature.
- Regenerated `legacy/draw_io_parser.py`, refreshed override-driven
  pytest coverage (especially `legacy/tests/test_patched_parser.py`), and
  synced downstream helpers/tests including the RML mapper workflow to the
  classifier-driven API.
- Documented the work in `CHANGELOG.md`, regenerated the demo logs via
  `bun run test:all:log:linux`, and recorded this report.

## Notes

- After the refactor the serializer helpers no longer call into
  `pipeline.core.rdf.control.individual_blocks`; all three code paths (pytest,
  Pyodide pipeline, Bun plugin) now share the classifier output directly.
- `bun run check` was satisfied by running the individual lint/format
  subtasks (`bun run lint:py`, `bun run lint:ts`, `bun run format:check:py`,
  and Prettier with `--check`).
