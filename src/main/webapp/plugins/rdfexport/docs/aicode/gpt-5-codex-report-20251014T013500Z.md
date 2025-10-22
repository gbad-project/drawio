# Debug CLI Enhancements – 2025-10-14

## Summary
- Reworked the DrawIO RDF export debug CLI to execute the Bun-based pipeline and plugin flows via a new Rich-powered interface.
- Added a Bun TypeScript scenario runner that mirrors the plugin harness and exposes deterministic outputs for pipeline and plugin graphs.
- Persisted fixture inventory metadata to `debug/map.json` and ensured scenario results capture triple counts, SHA-256 hashes, and isomorphism checks across graph variants.
- Introduced a pytest suite exercising prefix parsing, scenario execution, map bookkeeping, and graph isomorphism reporting.
- Automated Bun dependency setup (install + Pyodide assets) from the CLI to stabilize subprocess execution.
- Automatically persist REPL-authored scenarios as YAML files for reuse while leaving pre-existing scenario files untouched.

## Testing
- `uv run pytest debug/tests -q`
- `bun run check`
