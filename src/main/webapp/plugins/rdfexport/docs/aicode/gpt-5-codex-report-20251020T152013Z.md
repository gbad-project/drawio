# Strip HTML preservation option — implementation report

## Overview
- Added a `stripHtml` parser-setting checkbox in the Parser Settings dialog and persisted it into diagram metadata (defaults to stripping markup).
- Propagated the flag through the Pyodide runtime configuration so the Python pipeline can toggle literal sanitization.
- Implemented parser overrides that preserve literal HTML content while keeping identifiers sanitized, regenerating `legacy/draw_io_parser.py` from overrides.
- Expanded Bun integration tests and pytest coverage to validate both default stripping and HTML preservation flows.

## Code changes
- `src/rdfexport.ts` updates the UI, metadata serialization, and pipeline invocation.
- `src/pyodideRuntime.ts` extends the `DrawioPyodideConfig` interface with `stripHtml` and forwards it when booting Pyodide.
- `pyodide_pipeline/drawio_pipeline.py` respects the new flag and threads it through to parser overrides.
- `legacy/overrides/strip_html.py` defines a custom `NodeHTMLParser` that captures raw HTML segments.
- `legacy/overrides/rml_export.py` restores preserved HTML on literal objects while leaving IRIs sanitized.
- `legacy/draw_io_parser.py` regenerated to embed override behavior.
- `legacy/tests/test_patched_parser.py` adds assertions for both sanitized and preserved literal paths.
- `tests/rdfexport.test.ts` adds an end-to-end pipeline test verifying HTML markup appears in Turtle output when stripping is disabled.
- `tests/fixtures/AA37 Department of Health-with-metadata-preserve-html.drawio` fixture augments metadata with `stripHtml="false"`.
- `pyproject.toml` excludes chat transcripts from Ruff linting.

## Testing
- `bun run check`
- `bun run test`
- `bun run test:log:linux`
- `pytest legacy/tests/test_patched_parser.py`

All commands completed successfully (Pytest executed within the project virtual environment).
