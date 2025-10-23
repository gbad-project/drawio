# rdfexport Debug Report – 2025-10-23

## Summary
- Regenerated the meta-built DrawIO parser after updating `DrawIOCellClassifier`.
- Tightened rdf:type validation so malformed CURIEs without HTML markup raise `NotInKnownException` while UML labels without prefixes remain literals.
- Refreshed debug outputs and Bun/Pyodide regression logs via `bun run test:log:linux` and `uv run bun run debug:all:log:linux`.

## Tests
- `uv run pytest`
- `bun run test`
- `bun run test:log:linux`
- `uv run bun run debug:all:log:linux`
- `bun run lint`
- `ruff format --check .`
- `prettier --check .` (captured to `/tmp/prettier.log`)
