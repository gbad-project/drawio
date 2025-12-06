# RML map-schema workflow integration (2025-10-26)

## Summary
- implemented the `rmlmapper_workflows.map_schema_workflow` helper module to orchestrate the draw.io → Turtle → RML → Turtle pipeline.
- ensured SourceCSVPreprocessor-backed CSV preparation keeps parity with legacy fixtures and rewrote baseline RML CSV paths on the fly.
- added pytest coverage under `legacy/tests/test_map_schema_workflow.py` asserting rdflib graph isomorphism for the General ADD and General Authority fixtures.
- hardened tooling by provisioning SDKMAN + Temurin JDKs and running RMLMapper 7.0.0 inside tests, capturing mapper failures as Python exceptions.

## Testing
- `uv run pytest legacy/tests/test_map_schema_workflow.py`
- `CI=1 bun run check`
- `bun run test:all:log:linux`
- `bun run test:all:log:show`
