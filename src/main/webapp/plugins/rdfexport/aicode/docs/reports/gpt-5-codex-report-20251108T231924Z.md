# RML Template Decoding Report

## Context
- **Agent:** gpt-5-codex
- **Date (UTC):** 2025-11-08 23:19:24
- **Task:** Decode URL-substituted templates during RML serialization while preserving upstream metacharacter handling, refresh pipeline artifacts, and regenerate regression logs.

## Summary of Work
1. Followed contributor workflow inside `src/main/webapp/plugins/rdfexport/`:
   - `bun run setup:uv`
   - `.venv/bin/python -m rmlmapper_workflows.pipeline_workflow` (captures existing failures)
   - `bun run test:all:log:show` (baseline status quo)
2. Implemented metacharacter-mode propagation and literal normalization:
   - Extended `DrawIOParserGraph` to store `metacharacter_mode`.
   - Passed the mode from `_build_graph_from_raw_xml` when URL substitution is active.
   - Centralized triple addition in `legacy/overrides/serialisers.py`, decoding literals for RML serializers when the graph indicates URL substitution.
   - Updated RDF serializer helpers to reuse the centralized insertion path.
   - Added a regression test asserting decoded templates in `serialise_to_rml`.
3. Regenerated `legacy/draw_io_parser.py` via `bun run build:py` to incorporate overrides.
4. Regenerated RML pipeline artifacts for General ADD and General Authority fixtures using `.venv/bin/python` helper script that calls `run_pipeline_workflow`.
5. Reviewed regenerated `pipeline_map.rml`, `pipeline_mapped.ttl`, and `pipeline_preprocessed.csv` outputs to confirm decoded templates and clean literals.
6. Executed `python -m rmlmapper_workflows.pipeline_workflow` with `.venv/bin/python` to validate artifacts and document expected failures (missing legacy commit and authority CSV).
7. Ran the full regression workflow `bun run test:all:log:linux`, noted expected failures (legacy Git commit absence and missing CSV), and staged refreshed logs under `tests/demo_logs/`.
8. Documented efforts (this report) and updated `CHANGELOG.md` with the fix entry.

## Testing Evidence
- `.venv/bin/python -m rmlmapper_workflows.pipeline_workflow` → expected failures due to missing legacy commit and authority CSV but regenerated artifacts confirmed decoded templates.
- `bun run test:all:log:linux` → exercised Bun + pytest suites; legacy commit and CSV absence produce recurring, expected failures while other tests pass or xfail as before.
