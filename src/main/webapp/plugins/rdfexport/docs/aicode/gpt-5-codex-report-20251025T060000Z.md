# Task Report – 2025-10-25

## Overview

Regenerated the legacy CSV preprocessing helper so historical RML fixtures are
normalised into first-normal-form rows that the DrawIO pipeline can ingest
directly.  The work mirrors `legacy/map_schema.py` while embedding the
increment/authority logic into `SourceCSVPreprocessor` for reuse across the
project.

## Key Activities

- Extended `SourceCSVPreprocessor` with increment-aware normalisation that
  collapses numbered columns into a single value plus an `INCREMENT_NUMBER`
  column, allowing downstream logic to consume 1NF data without bespoke
  disaggregation.
- Reimplemented the RiC-O authority type mapping within the preprocessor so the
  new normalised rows ship with a `RICO_AUTHTP` value derived from the legacy
  regex dictionary.
- Hardened the column splitting/preprocessing routines to cope with fixtures
  that omit previously expected columns, ensuring the helper can operate on the
  archived CSVs without manual edits.
- Updated `pyodide_pipeline/csv_normalizer.py` to rely on the enhanced
  preprocessor and regenerated both RML-normalised CSV fixtures.
- Authored pytest coverage (`legacy/tests/test_preprocessors.py`) that verifies
  the increment normalisation and RiC-O mapping behaviour.
- Captured changelog entry documenting the preprocessing overhaul.

## Testing

- `bun run test:all:log:show` (initial status check)
- `bun run test:all:log:linux`
- `bun run check`

