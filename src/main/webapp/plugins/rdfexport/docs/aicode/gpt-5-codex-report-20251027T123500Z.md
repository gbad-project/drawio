# RML Workflow Alignment Adjustments – 2025-10-27

## Summary
- Updated the RML mapper workflow harness to sanitise DrawIO XML on the fly and normalise CSV inputs via the shared helper so both the legacy `map_schema` run and the debugger pipeline start from identical sources, persisting the derived CSV snapshots alongside the generated RML/Turtle artefacts for inspection.
- Loaded the rr/rml token stripper from `scripts/clean_rr_terms.py` and wired it into the pipeline workflow, ensuring fixtures without `_no_rr` variants are cleaned consistently before invoking the debugger scenario.
- Pointed the isomorphism regression test at the original General Authority/ADD diagrams and CSVs, relying on the runtime sanitisation/normalisation path to keep the pipeline and legacy outputs aligned.

## Testing
- `bun run check`
- `.venv/bin/python -m pytest legacy/tests/test_rmlmapper_alignment.py --maxfail=1 -vv`
- `bun run test:all:log:linux`
