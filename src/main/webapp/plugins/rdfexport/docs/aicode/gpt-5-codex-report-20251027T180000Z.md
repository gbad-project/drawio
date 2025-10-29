# Worklog – 2025-10-27

## Summary
- Updated the RML alignment regression so the legacy `map_schema` and debugger workflows both invoke the bundled RMLMapper jar and compare the generated Turtle graphs directly for isomorphism.
- Added canonicalised diff diagnostics that surface example triples when either workflow emits stray data, making failures actionable.
- Recorded a changelog entry describing the stricter regression guard.

## Testing
- `bun run check`
- `.venv/bin/python -m pytest legacy/tests/test_rmlmapper_alignment.py --maxfail=1 -vv`
- `bun run test:all:log:linux`
