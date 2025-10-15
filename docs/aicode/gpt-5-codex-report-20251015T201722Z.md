# Task Report — gpt-5-codex

## Summary
- Added four regression fixtures derived from `AA37-with-metadata-severely-mocked.drawio` that exercise malformed rdf:type labels (`picoL`, `:hs`, `:`, and empty).
- Hardened `DrawIOXMLTree._source_or_target` so arrows targeting malformed nested cells now raise `UndefinedPrefixException` (or a related error) instead of silently producing literals or unhelpful no-source errors.
- Extended `test_patched_parser.py` with parameterised coverage for the new fixtures and ensured fixture metadata is recorded for debug tooling.
- Captured `bun run test:log:linux` output and refreshed `debug/map.json` with the new fixture fingerprints and debug error traces.

## Commands Executed
```bash
# dependency/bootstrap workflow (per CONTRIBUTING guidance)
bun install
bun run setup:uv
bun run setup:pyodide

# lint/format gate
bun run check

# Debug scenarios for new malformed rdf:type fixtures
./.venv/bin/python -m debug --drawio tests/fixtures/AA37-with-metadata-severely-mocked-picoL-without-colon.drawio
./.venv/bin/python -m debug --drawio tests/fixtures/AA37-with-metadata-severely-mocked-colon-prefix-missing.drawio
./.venv/bin/python -m debug --drawio tests/fixtures/AA37-with-metadata-severely-mocked-colon-only.drawio
./.venv/bin/python -m debug --drawio tests/fixtures/AA37-with-metadata-severely-mocked-missing-type.drawio

# Project checks
PATH="/workspace/drawio/src/main/webapp/plugins/rdfexport/.venv/bin:$PATH" bun run test:log:linux
```

## Notes
- Debug CLI runs intentionally surface existing metadata parsing limitations in the legacy parser (UserObject handling) and Pyodide bridge; the raised exceptions are expected for these malformed fixtures and confirm the new guardrails trigger.
- The updated parser guards avoid regressing literal handling by distinguishing top-level and literal cells from nested rdf:type labels before raising exceptions.
- `tests/demo_logs/test.log` is included in the commit per repository policy.
