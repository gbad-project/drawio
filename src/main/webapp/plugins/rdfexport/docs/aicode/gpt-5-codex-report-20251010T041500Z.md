# Codex Report — 2025-10-10T04:15:00Z

## Objective

- Validate that every file/function reference in `AGENTS.md` still matches the current DrawIO RDF export implementation.
- Identify stale descriptions introduced after the Turtle-first pivot and align the documentation with the Pyodide bridge that shipped in commits `4952510` → `6fc153c` → `9e073ca`.
- Record the investigation and document updates for future maintainers.

## Materials Reviewed

- `git log --oneline -10` to cross-check the recent Turtle export alignment commits.
- Python sources: `pyodide_pipeline/drawio_pipeline.py`, `legacy/draw_io_parser.py`, and `legacy/map_schema.py`.
- TypeScript bridge modules: `src/mockBlackBox.ts` and `src/pyodideRuntime.ts`.
- Bun integration tests in `tests/rdfexport.test.ts` and package scripts in `package.json`.
- Existing codex reports through 2025-10-10T02:00:45Z.

## Actions

- Traced the Pyodide pipeline to confirm it currently normalizes XML, caches `DrawioParserGraph` objects, and emits Turtle via `parse_drawio_xml_to_json`, without yet invoking `map_schema` DataFrame helpers.
- Audited the Bun test harness to verify `runDrawioPipeline` drives Turtle exports and the rdflib isomorphism comparisons now guard the Pyodide output.
- Reviewed tooling scripts to replace the obsolete `bun run uv` reference with the active `setup:uv` / `setup:pyodide` workflow.
- Updated `AGENTS.md` to describe the present bridge architecture, call out the cached Turtle summary, and clarify that Task 3 still needs to expose the map_schema helpers before DataFrame transforms enter the browser runtime.
- Logged these findings in this codex report.

## Testing

- Documentation-only changes; no automated tests were executed.

## Follow-up Notes

- When Task 3 begins, reassess the Feature Description to confirm the new helpers are wired into Pyodide before advertising DataFrame support.
- Continue to run `bun run test` from `src/main/webapp/plugins/rdfexport` so the rdflib isomorphism harness stays authoritative during Turtle-focused work.
