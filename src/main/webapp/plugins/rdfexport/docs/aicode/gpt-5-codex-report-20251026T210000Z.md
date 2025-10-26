# Rdfexport Preprocessor Enhancements – 2025-10-26

## Summary
- Finalised `SourceCSVPreprocessor` so all numbered CSV columns collapse into a first-normal-form representation and append `INCREMENT_NUMBER` rows generated from the suffix index.
- Added RiC-O AUTHTP mapping during preprocessing using the canonical dictionary from `legacy.map_schema`, ensuring downstream consumers receive the derived `RICO_AUTHTP` column.
- Updated the CSV normaliser helper to lean entirely on the enhanced preprocessor and dropped denormalised compound columns before writing fixture snapshots.
- Regenerated normalised RML fixtures to match the new preprocessing behaviour and introduced pytest coverage for numbered-column expansion plus AUTHTP mapping.

## Testing
- `bun run test:all:log:linux`
- `bun run check`
- `bun run test:all:log:show`
