# Template-aware RML typed individual handling (2025-11-04)

## Summary
- Allowed DrawIO typed-individual classifications to tolerate `{template}` placeholders when explicitly enabled, ensuring RML serialisation can emit `rr:template` terms without tripping literal guards.
- Updated the RML serializer override to reuse central template detection for subjects and predicate/object maps so template-bearing identifiers round-trip into RML while Turtle emission still skips them.
- Propagated the new `allow_template_types` flag through the parser pipeline, debug CLI, and scenario metadata, refreshing associated baselines/logs and capturing regenerated RML workflow artefacts for General ADD/Authority fixtures.
- Added pytest coverage for template-typed individuals and RML output plus Bun regression baselines for the General ADD no-rr fixture; refreshed debug scenario expectations and logs accordingly.

## Testing
- `bun run check`
- `./.venv/bin/python -m rmlmapper_workflows.pipeline_workflow`
- `bun run test:all:log:linux`
- `bun run test:all:log:show`
