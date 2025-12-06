# Work Plan

> [!CAUTION]
> This file is retired and should **NOT** be used.

## Contributor Guidelines

- **Reviewing `<repo-root>/src/main/webapp/plugins/rdfexport/legacy/tests/README.md` is a MUST!**
- If you bring your own task, please ignore the rest of this file except for these contributor guidelines. **You must honour the contributor guidelines regardless.** If you don't have a task yet, take the first unimplemented task from the list below (if no status is indicated, assume it has not been implemented yet).
- Stick to your selected task. Going sideways to contribute to another task in passing is discouraged. If you desperately feel the urge to, you may leave a comment marking it as one of: AICODE-TODO (an unidentified task emerged), AICODE-ASK (stakeholder input is requested), AICODE-NOTE (important but no action requested).
- Once the task is completed and all planned tests pass, document all your efforts extensively under `docs/aicode/{your-name}-report-{timestamp}.md`. If applicable, update the task status here in AGENTS.md and update the task status summary below.
- Before starting to work on your task, navigate to `src/main/webapp/plugins/rdfexport/`. Keep tooling aligned with the `package.json` scripts vetted workflow: install JavaScript dependencies with `bun install`, hydrate Python deps with `bun run setup:uv`, sync Pyodide assets via `bun run setup:pyodide`, then exercise Bun coverage with `bun run test`. To obtain precise regression diffs for a particular fixture, `bun run debug:help` is at your service.
- If you want a REAL **slow** debug of ALL available *.drawio fixtures (including regression against original Python, TypeScript pipeline, and TypeScript plugin runs, isomorphism checks across, and direct checks against source XML), use this command: `bun run debug:all`. Show last captured log using `bun run debug:all:log:show` and replace it with a new one using `bun run debug:all:log:linux`, and be sure to stage it in the commit.
- **Always** be sure to run `bun run check` before committing and `bun run fix` and/or fix any issues before committing. Show last captured log using `bun run test:log:show` and run `bun run test:log:linux` to replace it with your final test log and be sure to stage it in the commit.
- When modifying the DrawIO parser, treat `legacy/draw_io_parser.py` as generated output. Compose Python overrides in `src/main/webapp/plugins/rdfexport/legacy/overrides/` (one module per concern) and decorate replacement symbols with `meta_builder.drawio_meta_builder.override` so the CLI can merge them during regeneration.
- Create an appropriate changelog entry in `CHANGELOG.md` whenever you complete a task.

## Feature Description

**In-Browser RDF Transformation Pipeline for DrawIO Extension**

This feature introduces an in-browser data transformation pipeline to the DrawIO extension so serialized diagram XML can be round-tripped to Turtle without leaving the editor. The extension still serializes diagrams as XML, but that payload now flows through a TypeScript “black box” bridge (`src/main/webapp/plugins/rdfexport/src/mockBlackBox.ts`) that boots a Pyodide-backed Python runtime (`pyodidePipeline.ts`) before delegating to the patched DrawIO parser living in `legacy/draw_io_parser.py`.

Inside Pyodide, `pyodide_pipeline/drawio_pipeline.py` normalizes the XML, calls `_build_graph_from_raw_xml`, and caches the resulting `DrawIOParserGraph` plus its derived Turtle serialization. The bridge returns a JSON summary (graph id, namespaces, CSV path metadata, and Turtle payload) so the plugin can save a `.ttl` export using the existing RDF/XML save logic, with the hard switch to Turtle defaults now exercised by `runDrawioPipeline` in the Bun tests.

Task 3 now targets RML emission through DrawIO parser overrides. `legacy/map_schema.py` stays the reference implementation for CURIE expansion, URI encoding, and template handling—mirror its battle-tested patterns when designing overrides, but keep the module itself untouched while the Pyodide bridge continues validating the existing Turtle pathway with the Bun + rdflib isomorphism harness.

A Node-compatible Pyodide build (run under Bun + Volta) provides a fully local, testable environment for executing and debugging Python code within TypeScript. Robust logging, incremental integration, and fine-grained test coverage (via Bun and pytest) ensure a stable, transparent, and extensible foundation for RDF data transformation directly within the DrawIO extension.

Meta builder now supports override discovery so the DrawIO parser can be extended safely without editing generated artifacts. Add new Python files under `src/main/webapp/plugins/rdfexport/legacy/overrides/`, decorate exported replacements with `@meta_builder.drawio_meta_builder.override`, and regenerate—the Mermaid pipeline diagram at `src/main/webapp/plugins/rdfexport/meta_builder/assets/mermaid-diagram-2025-10-23-140512.mmd` (referenced in `meta_builder/readme.md`) shows how override modules weave into the build and where each namespace hook lands.

## Task Status Summary

Progress: [██████████████████] 8/8 (100%)

- Task 1 – DrawIO Black Box Integration: ✅ Completed on 2025-10-08 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 2a - Remove Hardcoded Classes and Property CURIEs from DrawIO Parser: ✅ Completed on 2025-10-09 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 2b - Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawIOParserGraph): ✅ Completed on 2025-10-09 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 3 – Initial RML Generation via DrawIO Parser Overrides: ✅ Completed 2025-10-20 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 4 Phase 1 – Initial Browser Execution Pipeline (Pyodide Integration): ✅ Completed 2025-10-09 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 4 Phase 2 – Full Browser Execution Pipeline (Pyodide Integration): ✅ Completed 2025-10-23 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 5a – Full RML Generation via DrawIO Parser Overrides: ✅ Completed 
- Task 5b – RML export alignment: ✅ Completed 
