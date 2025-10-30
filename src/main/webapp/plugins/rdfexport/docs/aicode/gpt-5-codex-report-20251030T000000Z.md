# Pipeline workflow scaffolding report (2025-10-30)

## Summary

- Implemented a pipeline-driven RMLMapper workflow that reuses the debug CLI to
  generate scenario artifacts with `rml_enabled` toggled on and stores
  workspace outputs for further analysis.
- Added a `NormalisedCSVPreprocessor` helper that extends the legacy CSV
  preprocessor to flatten incremented columns into 1NF rows and to inject
  RiC-O authority type hints.
- Introduced pytest coverage for General ADD and General Authority fixtures to
  compare pipeline-generated Turtle against the legacy map-schema workflow and
  persisted artifacts for manual review.
- Documented the new workflow entry point in the changelog.

## Testing

- `bun run lint:py`
- `bun run lint:ts`
- `bun run format:check:py`
- `bun run format:check:ts`
- `bun run test:all:log:linux`
