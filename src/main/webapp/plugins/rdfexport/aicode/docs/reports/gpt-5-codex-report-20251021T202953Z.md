# Debug Harness Dynamic Config Enhancements – Worklog

## Summary
- Verified the expanded debugger scenario harness that now persists arbitrary `metadata_attributes` and `parser_config` payloads from CLI arguments, scenario YAML, and REPL prompts into the Bun runner.
- Confirmed `debug/run_scenario.ts` propagates the new parser overrides to `runDrawioPipeline`, storing derived settings on the XML metadata payload when appropriate.
- Exercised the new pytest coverage (`debug/tests/test_dynamic_config.py`) to ensure JSON handoff payloads and XML metadata reflect dynamic overrides, including forward-compatible parser knobs.
- Ran Bun linting/formatting checks and acknowledged outstanding Bun test failures stemming from legacy baseline drift; captured updated `tests/demo_logs/test.log` via the required scripted run.

## Testing
- `.venv/bin/pytest debug/tests -q`
- `bun run check`
- `bun run test` *(fails: legacy parser baselines and Bun integration expectations diverge; see collected log in tests/demo_logs/test.log)*
- `bun run test:log:linux` *(fails for the same reasons as `bun run test`; new log recorded with interrupted run)*

## Notes
- Formatting adjustments were applied via Prettier to satisfy repository style checks.
- Legacy Bun tests currently regenerate fixtures and report numerous mismatches; addressed by documenting the failures without attempting fixture regeneration.
