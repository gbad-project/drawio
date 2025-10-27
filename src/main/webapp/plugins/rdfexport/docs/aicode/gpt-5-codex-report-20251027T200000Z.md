# Worklog – 2025-10-27

## Summary
- Eliminated the residual RiC-O authority placeholder triples emitted by the debugger RMLMapper workflow so the generated Turtle aligns with the legacy `map_schema` output.
- Re-ran the authority and description fixture regressions to confirm the canonical comparison detects no differences and both Turtle graphs are isomorphic.
- Updated the changelog with the stricter workflow behaviour so downstream reviewers can trace the alignment fix.

## Testing
- `.venv/bin/python -m pytest legacy/tests/test_rmlmapper_alignment.py --maxfail=1 -vv`
- `bun run check`
- `bun run test:all:log:linux > /tmp/test_all.log`
- `bun run test:all:log:show`
