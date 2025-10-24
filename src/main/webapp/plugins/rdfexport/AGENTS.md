# Work Plan

## Contributor Guidelines

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

Progress: [██████████░░░░░░░░] 6/8 (75%)

- Task 1 – DrawIO Black Box Integration: ✅ Completed on 2025-10-08 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 2a - Remove Hardcoded Classes and Property CURIEs from DrawIO Parser: ✅ Completed on 2025-10-09 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 2b - Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawIOParserGraph): ✅ Completed on 2025-10-09 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 3 – Initial RML Generation via DrawIO Parser Overrides: ✅ Completed 2025-10-20 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 4 Phase 1 – Initial Browser Execution Pipeline (Pyodide Integration): ✅ Completed 2025-10-09 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 4 Phase 2 – Full Browser Execution Pipeline (Pyodide Integration): ✅ Completed 2025-10-23 by gpt-5-codex (recorded in CHANGELOG.md)
- Task 5a – Full RML Generation via DrawIO Parser Overrides: ⏳ Not started
- Task 5b – RML export alignment: ⏳ Not started

## Task Stubs

:::task-stub{title="Task 5a – RML Generation via DrawIO Parser Overrides"}

Goal
Enable RML output alongside Turtle by extending the DrawIO parser through meta builder overrides only. Generated artifacts such as `legacy/draw_io_parser.py` must remain untouched; new functionality should come from purpose-built modules in `src/main/webapp/plugins/rdfexport/legacy/overrides/`.

Guidance
- Compose one override module per concern. Start working from `rml_export.py` but feel free to add more files as necessary for the functionality to live in focused, swappable units. Use the existing overrides as the canonical injection points for namespace logic.
- Consult `meta_builder/readme.md` plus the Mermaid pipeline diagram at `meta_builder/assets/mermaid-diagram-2025-10-23-140512.mmd` to understand how overrides are discovered, ordered, and composed before writing code.
- Propagate RML-specific metadata via overrides. The metadata contract must use an `rmlEnabled` flag that gates RML graph construction and can be toggled from the TypeScript UI (see `legacy/overrides/rml_export.py` and `tests/rdfexport.test.ts`).
- Engineer a new `serialise_to_rml` override that will copycat `serialise_to_graph` from `legacy/overrides/curie_validator.py` but will surgically replace statements added to the graph with appropriate RML triples. Refer to `legacy/map_schema.py` (in particular its `for i, subject_row in subjects_df.drop_duplicates().iterrows()` loop) for examples of valid RML construction.
- BEWARE that map_schema comes from a very different code base and has LOTS of logic absolutely not applicable here! So the only canonical thing you might want to get from there is how it builds rr:TriplesMap -> rr:predicateObjectMap etc. graphs. HOWEVER, note that while map_schema deduced which predicate to use (e.g., rml:reference vs rr:template) by splitting values from nodes, **this is not what we are doing here.** Here, we must map such that whenever in our graph there is a predicate/arrow, we construct an rr:predicate/rr:predicateObjectMap there; when there is a literal object in our graph, we construct a rml:reference or rr:constant as appropriate, etc. So the RML serialiser we are building *actually* mirrors what is present in the original Turtle graph – just by utilizing RML syntax.
- This is exactly why we have a sophisticated and robust `DrawIOCellClassifier` (from `legacy/cell_classifier.py` override) that allows for the precise determination of the mxCell kind -> accurate further graph construction be it Turtle or RML. It's already been implemented for Turtle - your task is just to get RML syntax right. And map_schema is great at getting RML syntax exactly right (that's about the only thing in which map_schema is great at).
- Integrate the new RML serializer into `_build_graph_from_raw_xml` (overriden from `rml_export`) to make sure this function switches to the correct serializer based on flag.
- Coordinate with the Pyodide harness: the TypeScript plugin should now return the new RML graph to the user instead of the previous proof-of-concept solution where Turtle was returned with a few mock RML triples added.

Tests (pytest / bun)
- Unit – sanity checks for the validity of generated RML and to ensure that the new RML behavior doesn't break our existing Turtle serialisation logic that should function just the same as it does now when the RML flag is not passed.
- Integration – ensure that the pipeline and plugin debugs still work and return valid Turtle when initiated without RML flag; add new checks for running everything with RML flag.
- Run `bun run test:all:log:show` to see the status quo from last (successful!) run. Capture `bun run test:all:log:linux` for review and compare what changed. **Note** that this master test command **used to completely pass/xfail as appropriate** before your changes, so you can be 100% sure that if there are errors/failures, that's your changes that introduced them!
:::

:::task-stub{title="Task 5b – RML Export Alignment"}

Goal
Ensure every consumer of DrawIO-derived RDF (Pyodide UI, Bun CLI, pytest harness, downstream exporters) can flip between Turtle and RML without divergence once overrides land. Further, this must also confirm no regression vs pre-existing battle-tested (yet fairly distinct) `legacy/map_schema.py`.

Guidance
- Use the authoritative DrawIO inputs for regression: the General Authority and General ADD diagrams already live under `src/main/webapp/plugins/rdfexport/tests/fixtures/`. Pair them with the retired RML baselines and CSVs under `src/main/webapp/plugins/rdfexport/tests/fixtures/rml/` to understand how `map_schema.py` shaped the canonical output before overrides existed.
- Extend the existing baseline generator instead of hand-authoring RML samples. You may call into `legacy/map_schema.py` to regenerate `.rml` from the authority/ADD CSVs after preprocessing them with a small helper (factor this helper into a dedicated module so the DrawIO pipeline can reuse it). The preprocessing will include applying `SourceCSVPreprocessor` to break down cluttered columns, and then applying **an additional preprocessor** to convert the resulting dataframe into 1NF normal form. This will allow you to use current rdfexport pipeline logic that does not support (nor should it support) node disaggregation by increment nor by any other factor. Those regenerated artifacts become the golden references for validating the override-powered pipeline. In summary, you will have to keep two version of CSV for each fixture: original and preprocessed+normalized using your custom helper utility (note: the helper utility is bespoke for these two fixtures and does not need to generalize).
- Note that differences will be in place due to the differences in how map_schema approached parsing (i.e., rr:/rml: prefixes were indicated directly in the node whereas *we* will deduce them from our `blocks`, `object_properties`, and `datatype_properties`), but you must work around these differences to still be able to extract value from the legacy fixtures for regression. One approach could be keeping two drawio graphs for each existing golden standard fixture: original drawio (with RR/RML terms in nodes) and drawio compatible with current pipeline while ensuring the final RML outputs are identical.
- There should also be a deterministic check in place that will compare Turtle to RML in a logical way, much like `debug/debug_cli_regression.py` currently provides sanity checks for XML -> Turtle alignment.

Testing (pytest / bun)
- Regression – Run `bun run test:all:log:show` to see the status quo from last run. Run your tests together with ALL preexisting tests (i.e., `bun run test:all:log:linux` command) to compare what changed and make sure everything passes.
:::
