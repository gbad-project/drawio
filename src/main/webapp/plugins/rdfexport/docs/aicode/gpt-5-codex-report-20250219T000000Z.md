# Debug CLI regression follow-up — manual scenario verification

## Summary
- Updated `debug/debug_cli_regression.py` to add `_scenario_slug_from_command` helper and enhance the manual follow-up test so it re-runs scenarios, reloads `debug/map.json`, and inspects errors, allowing only `py_legacy` issues.
- Recorded Bun test log for Linux via `bun run test:log:linux` per contributor guidelines.

## Commands executed
- `bun install`
- `bun run setup:uv`
- `bun run setup:pyodide`
- `bun run test` *(fails in baseline due to known parser regressions)*
- `bun run check` *(fails because Prettier flags existing formatting on debug/map.json; not modified)*
- `bun run test:log:linux` *(produces failing test log matching baseline expectation)*

## Notes
- The manual follow-up test now mirrors the primary regression test flow, relying on scenario data instead of process exit codes.
- Existing Prettier warnings for `debug/map.json` remain unresolved to avoid a repository-wide formatting churn; behaviour matches prior runs.
- Bun test suite continues to report the known failure for `runDrawioPipeline preserves literal HTML when stripHtml disabled`.
