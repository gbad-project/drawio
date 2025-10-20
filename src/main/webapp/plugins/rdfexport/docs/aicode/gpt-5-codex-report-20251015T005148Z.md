# RDF Export Regression Harness Alignment – 2025-10-15

## Summary

- Normalised the Pyodide-backed regression test isomorphism checks in `tests/rdfexport.test.ts` to filter ontology and import triples before comparing plugin output with the in-process pipeline, eliminating timestamp-related false negatives.
- Regenerated the authoritative Linux `bun run test` transcript after the fix to document passing pytest and Bun suites in `tests/demo_logs/test.log`.

## Testing

- `source src/main/webapp/plugins/rdfexport/.venv/bin/activate && bun run test`
- `source src/main/webapp/plugins/rdfexport/.venv/bin/activate && bun run check`
- `source src/main/webapp/plugins/rdfexport/.venv/bin/activate && bun run test:log:linux`
