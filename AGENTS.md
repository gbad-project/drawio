Work Plan

Contributor Guidelines
- If you bring your own task, please ignore the rest of this file except for these contributor guidelines. **You must honour the contributor guidelines regardless.** If you don't have a task yet, take the first unimplemented task from the list below (if no status is indicated, assume it has not been implemented yet).
- Stick to your selected task. Going sideways to contribute to another task in passing is discouraged. If you desperately feel the urge to, you may leave a comment marking it as one of: AICODE-TODO (an unidentified task emerged), AICODE-ASK (stakeholder input is requested), AICODE-NOTE (important but no action requested).
- Once the task is completed and all planned tests pass, document all your efforts extensively under `docs/aicode/{your-name}-report-{timestamp}.md`. If applicable, update the task status here in AGENTS.md and update the task status summary below.
- Before starting to work on your task, navigate to `src/main/webapp/plugins/rdfexport/`. Keep tooling aligned with the `package.json` scripts vetted workflow: install JavaScript dependencies with `bun install`, hydrate Python deps with `bun run setup:uv`, sync Pyodide assets via `bun run setup:pyodide`, then exercise Bun coverage with `bun run test`. To obtain precise regression diffs for a particular fixture, `bun run debug:help` is at your service.
- **Always** be sure to run `bun run check` before committing and `bun run fix` and/or fix any issues before committing. Run `bun run test:log:linux` to capture your final test log and be sure to stage it in the commit.
- When modifying the DrawIO parser, treat `legacy/draw_io_parser.py` as generated output. Compose Python overrides in `src/main/webapp/plugins/rdfexport/legacy/overrides/` (one module per concern) and decorate replacement symbols with `meta_builder.drawio_meta_builder.override` so the CLI can merge them during regeneration.
- Create an appropriate changelog entry in `CHANGELOG.md` whenever you complete a task.

⸻

Feature Description — In-Browser RDF Transformation Pipeline for DrawIO Extension

This feature introduces an in-browser data transformation pipeline to the DrawIO extension so serialized diagram XML can be round-tripped to Turtle without leaving the editor. The extension still serializes diagrams as XML, but that payload now flows through a TypeScript “black box” bridge (`src/main/webapp/plugins/rdfexport/src/mockBlackBox.ts`) that boots a Pyodide-backed Python runtime (`pyodidePipeline.ts`) before delegating to the patched DrawIO parser living in `legacy/draw_io_parser.py`.

Inside Pyodide, `pyodide_pipeline/drawio_pipeline.py` normalizes the XML, calls `_build_graph_from_raw_xml`, and caches the resulting `DrawIOParserGraph` plus its derived Turtle serialization. The bridge returns a JSON summary (graph id, namespaces, CSV path metadata, and Turtle payload) so the plugin can save a `.ttl` export using the existing RDF/XML save logic, with the hard switch to Turtle defaults now exercised by `runDrawioPipeline` in the Bun tests.

Task 3 now targets RML emission through DrawIO parser overrides. `legacy/map_schema.py` stays the reference implementation for CURIE expansion, URI encoding, and template handling—mirror its battle-tested patterns when designing overrides, but keep the module itself untouched while the Pyodide bridge continues validating the existing Turtle pathway with the Bun + rdflib isomorphism harness.

A Node-compatible Pyodide build (run under Bun + Volta) provides a fully local, testable environment for executing and debugging Python code within TypeScript. Robust logging, incremental integration, and fine-grained test coverage (via Bun and pytest) ensure a stable, transparent, and extensible foundation for RDF data transformation directly within the DrawIO extension.

Meta builder now supports override discovery so the DrawIO parser can be extended safely without editing generated artifacts. Add new Python files under `src/main/webapp/plugins/rdfexport/legacy/overrides/`, decorate exported replacements with `@meta_builder.drawio_meta_builder.override`, and regenerate—the Mermaid pipeline diagram at `src/main/webapp/plugins/rdfexport/meta_builder/assets/mermaid-diagram-2025-10-16-100316.svg` (with editable Mermaid source at `src/main/webapp/plugins/rdfexport/meta_builder/assets/mermaid-diagram-2025-10-16-100316.mmd`, referenced in `meta_builder/readme.md`) shows how override modules weave into the build and where each namespace hook lands.

Historical context (feat/rml branch milestones): the branch introduced the custom RDF/XML export plugin, followed by CSV path controls and deterministic regression fixtures (`1e4582a` → `5d2b0fb`). Subsequent merges added metadata-aware parser flows, reproducible baseline generators, and the mock black box annotated save path (through commits such as `f2034d1`, `a28a81a`, `gpt-5-codex` task reports). Latest `work` commit `9e073ca` (2025-10-09) aligned Turtle export metadata and ported rdflib isomorphism checks into the Bun regression harness to guard Pyodide outputs. The same-day stabilization commit `6fc153c` reconciled the Pyodide pipeline with the restored mock black box tests after the experimental Turtle download spike in `4952510`, ensuring Bun coverage stayed authoritative while the UI flipped to Turtle defaults.

⸻

Task Status Summary
- Task 1 – DrawIO Black Box Integration: ✅ Completed on 2025-10-08 by gpt-5-codex
- Task 2a - Remove Hardcoded Classes and Property CURIEs from DrawIO Parser: ✅ Completed on 2025-10-09 by gpt-5-codex
- Task 2b - Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawIOParserGraph): ✅ Completed on 2025-02-14 by gpt-5-codex
- Task 3 – RML Generation via DrawIO Parser Overrides: ⏳ Not started
- Task 4 – Browser Execution Pipeline (Pyodide Integration): 🚧 Phase 1 completed 2025-02-15 by gpt-5-codex (Phase 2 pending)
- Task 5 – RML export alignment: ⏳ Not started (defer until DrawIO parser override surface stabilizes)

⸻

:::task-stub{title="Task 1 – DrawIO Black Box Integration ✅"}
Status: ✅ Completed on 2025-10-08 by gpt-5-codex

Goal
Enhance the DrawIO save flow so that, after XML serialization, the serialized XML is passed through a mock black box function that returns an arbitrary string, which is then saved using the existing RDF/XML save logic.

Steps
1. Update Save Flow
   - Current: interface → parameters → serialized XML → save.
   - New: interface → serialized XML → black box → arbitrary string → save via existing RDF/XML functionality.
2. Implement Mock Black Box
   - Input = serialized XML string.
   - Output = arbitrary string (not necessarily XML).
3. Reuse Existing Save Logic
   - Reuse existing RDF/XML save routine verbatim; ensure it accepts any string payload.
4. Backward compatibility must be preserved.

Testing (TypeScript / DrawIO Extension – Bun)
- Extend Bun tests:
- Unit – black box I/O behavior.
- Integration – serialize → black box → save flow.
- Regression – legacy XML save unaffected.
- E2E – simulate full workflow with arbitrary string output.
:::

:::task-stub{title="Task 2a – Remove Hardcoded Classes and Property CURIEs from DrawIO Parser ✅"}
Status: ✅ Completed on 2025-10-09 by gpt-5-codex

Goal
Refactor the DrawIO parser to eliminate hardcoded lists of allowed classes, object properties, and datatype properties. The parser must instead accept any CURIE whose prefix exists in the parsed prefix–IRI mapping. Changes should be minimal and backward-compatible.

Implementation Steps
1. Locate Hardcoded Elements
   * Identify the code sections where class and property CURIEs are explicitly enumerated.
   * Note them for documentation but remove them from runtime validation.
2. Replace with Dynamic Validation
   * Obtain known prefixes from the parser’s `prefix_iri_dict` (namespace manager).
   * Accept any CURIE whose prefix appears in that mapping and resolves to a valid IRI.
   * Preserve all existing error-handling behavior for undeclared or malformed prefixes.
3. Regression Verification
   * Run every pristine `*.drawio` fixture (exclude any `*-with-metadata.drawio` and all `*.rdf` fixtures, which belong to different code paths) using the unmodified DrawIO parser to produce baseline Graph objects.
   * Re-run the same fixtures using the refactored parser that no longer relies on hardcoded CURIEs.
   * Compare the resulting Graph objects directly — not by string serialization — using graph isomorphism checks or equivalent semantic equality methods available in rdflib.
   * Verify that all baseline and refactored Graphs are isomorphic, confirming no structural or semantic regressions.
4. Testing (pytest)
   * Add tests for valid arbitrary CURIEs with declared prefixes.
   * Add negative tests for undeclared prefixes.
   * Include automated isomorphism-based regression checks between pre-change and post-change parser outputs for all pristine fixtures.
:::

:::task-stub{title="Task 2b – Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawIOParserGraph) ✅"}
Status: ✅ Completed on 2025-02-14 by gpt-5-codex

Goal
Enhance the DrawIO parser to correctly process stdin-supplied XML containing embedded metadata (CSV path, prefix–IRI pairs, and base URI) injected by rdfexport.ts. The parser must extract this information directly from the XML and return a specialized DrawIOParserGraph object that:
- Is a full subclass of rdflib.Graph,
- Has a single declared property csv_path,
- Uses the standard rdflib namespace manager to hold prefix IRIs and base URI (no external metadata dict).

Implementation Steps
1. Study Metadata Injection Flow
   - Examine src/main/webapp/plugins/rdfexport/src/rdfexport.ts to see how prefix–IRI mappings, base URI, and CSV path are inserted into the DrawIO DOM.
   - Inspect src/main/webapp/plugins/rdfexport/tests/fixtures/AA37 Department of Health-with-metadata.drawio for the exact node structure.
2. Generate Enriched Fixtures
   - Start with pristine .drawio fixtures under src/main/webapp/plugins/rdfexport/tests/fixtures/.
   - Use the existing patcher utility src/main/webapp/plugins/rdfexport/tests/utils/patchDrawioWithMetadata.ts to produce corresponding *-with-metadata.drawio files embedding valid CSV path, prefix–IRI mappings, and base URI.
   - Verify the generated files match the reference format.
3. Define DrawIOParserGraph Class
   - Implement a subclass of rdflib.Graph with one declared property for CSV path:

from rdflib import Graph
from typing import Optional

class DrawIOParserGraph(Graph):
    def __init__(self, *args, csv_path: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_path = csv_path

   - Ensure the inherited rdflib namespace manager naturally stores prefixes, IRIs, and base URI.
   - csv_path simply records the parsed CSV path value from XML.
4. Modify Parser Logic
   - Continue reading serialized XML from stdin.
   - Parse and extract:
   - Prefix–IRI pairs → register in namespace manager,
   - Base URI → assign to Graph,
   - CSV path → assign to csv_path property.
   - Populate triples as before; all other behavior remains unchanged.
   - Return a fully initialized DrawIOParserGraph instance.
5. Regression Testing (pytest)
   - Extend tests to include both pristine and *-with-metadata.drawio fixtures.
   - For each fixture:
   - Feed via stdin,
   - Assert:
   - Graph parses successfully,
   - Prefixes and base URI are registered in namespace manager,
   - csv_path property matches the injected value.
   - Confirm all fixtures pass and Graph serialization is stable.
:::

:::task-stub{title="Task 3 – RML Generation via DrawIO Parser Overrides"}
Status: ⏳ Not started

Goal
Enable RML output alongside Turtle by extending the DrawIO parser through meta builder overrides only. Generated artifacts such as `legacy/draw_io_parser.py` must remain untouched; new functionality should come from purpose-built modules in `src/main/webapp/plugins/rdfexport/legacy/overrides/`.

Guidance
- Compose one override module per concern. Expect to add files such as `rml_curie_validator.py`, `rml_triplesmap_builder.py`, and `rml_node_detector.py` so CURIE expansion, TriplesMap construction, and diagram metadata live in focused, swappable units. Use the existing `curie_validator.py` override as the canonical injection point for namespace logic until it is replaced.
- Consult `meta_builder/readme.md` plus the Mermaid pipeline diagram at `meta_builder/assets/mermaid-diagram-2025-10-16-100316.svg` (and `.mmd` source) to understand how overrides are discovered, ordered, and composed before writing code.
- Propagate RML-specific metadata through `_extract_drawio_metadata`, `_build_graph_from_raw_xml`, and `DrawIOParserGraph` via overrides. The metadata contract must surface an `rmlEnabled` flag that gates RML graph construction and can be toggled from the TypeScript UI.
- Inject RML graph assembly near `individual_blocks` so DrawIO-specific state is available. Reuse battle-tested patterns from `legacy/map_schema.py` (URI encoding, mnemonic handling, namespace resolution) rather than reimplementing them, and keep new helpers inside overrides.
- Use the authoritative DrawIO inputs for regression: the General Authority and General ADD diagrams already live under `src/main/webapp/plugins/rdfexport/tests/fixtures/`. Pair them with the retired RML baselines and CSVs under `src/main/webapp/plugins/rmlexport/tests/fixtures/` to understand how `map_schema.py` shaped the canonical output before overrides existed.
- Extend the existing baseline generator instead of hand-authoring RML samples. You may call into `legacy/map_schema.py` to regenerate `.rml` from the authority/ADD CSVs after preprocessing them with a small helper (factor this helper into a dedicated module so the DrawIO pipeline can reuse it). Those regenerated artifacts become the golden references for validating the override-powered pipeline.
- Coordinate with the Pyodide harness: the TypeScript plugin should probe `rmlEnabled` before enabling UI affordances (for example an “Export RML” action) and pass a flag into the pipeline runner when RML should be emitted.
- Keep overrides narrowly scoped—one module per concern—to maintain predictable regeneration diffs and simplify review. Document any new override in `docs/aicode/{your-name}-report-{timestamp}.md` and note updates in this task list.

Testing (Python / pytest)
- Unit – CURIE syntax + namespace validation, triples map assembly, metadata propagation. Cross-check behavior against the `map_schema.py` helpers that previously produced the retired plugin’s RML.
- Integration – XML fixture → `DrawIOParserGraph` → RML graph equivalence against baselines (store baselines under `tests/baselines/rml/`). Generate baselines from the General Authority/General ADD diagrams and their canonical CSV companions by invoking the extended baseline generator so the override flow and legacy `map_schema` stay lockstep.
- Regression – ensure Turtle exports remain unchanged when RML is disabled and that overrides do not leak into unrelated tasks. Capture Bun + pytest logs for review.
:::

:::task-stub{title="Task 4 – Browser Execution Pipeline (Pyodide Integration)"}
Goal
Integrate the Python runtime (Pyodide) into the DrawIO extension for in-browser execution of the XML → rdflib → DataFrame → Turtle pipeline. Implementation proceeds in two phases.

:::task-stub{title="Task 4 – Phase 1 – Pyodide Integration & Debug Infrastructure ✅"}
Status: ✅ Completed on 2025-02-15 by gpt-5-codex

1. Integrate Pyodide Runtime
   - Load Pyodide within the TypeScript extension (using Web Worker or dynamic import).
   - Non-blocking UI init.
2. Minimal Python Mock
   - Implement process(text) mock returning "mock:" + text.
   - Connect this mock to the black box from Task 1.
3. Debug Pipeline Setup
   - Structured logging (TypeScript + Python).
   - Capture stdout/stderr and tracebacks.
   - Add log prefixes ([PYODIDE], [BLACKBOX], [PIPELINE]).
   - Expose optional debug REPL or variable dump.
4. Validation & Smoke Tests
   - Verify TS ↔ Pyodide messaging, serialization, and async behavior.
   - Extend Bun tests for mock invocation, error propagation, and cleanup.
   - Important: All tests must use the Node-compatible build of Pyodide configured via Bun + Volta as specified in the repo.
Do not attempt to test via Playwright or Selenium (browser automation is out of scope for this phase).
:::

:::task-stub{title="Task 4 – Phase 2 – Incremental Functional Integration"}
1. Progressive Function Port-In
   - Sequentially integrate:
   - DrawIO Parser (stdin → rdflib Graph)
   - graph_to_dataframe (Function A)
   - dataframe_to_turtle (Function B)
2. Incremental Debug & Verification
   - After each integration:
   - run in isolation inside Pyodide,
   - verify I/O equivalence vs. stand-alone Python.
   - Add fine-grained debug logs for XML, Graph stats, DataFrame preview, Turtle output.
3. End-to-End Assembly
   - Chain all three functions inside Pyodide: XML → Graph → DataFrame → Turtle.
   - Return Turtle string to TypeScript and save via existing RDF/XML logic.
4. Testing & Regression
   - Bun tests: async integration + E2E pipeline.
   - pytest: unit + integration for Python functions.
   - Cross-layer regression: compare browser vs. local Python outputs.
:::
:::

:::task-stub{title="Task 5 – RML Export Alignment"}
Status: ⏳ Not started

Goal
Ensure every consumer of DrawIO-derived RDF (Pyodide UI, Bun CLI, pytest harness, downstream exporters) can flip between Turtle and RML without divergence once overrides land. This task activates after the override surface stabilizes so alignment work is not wasted on moving targets.

Guidance
- Track a single source of truth for golden data: the regenerated RML baselines from Task 3 should drive Bun fixtures, pytest assertions, and any Pyodide smoke tests.
- Extend the export orchestrations (`runDrawioPipeline`, Pyodide worker handlers, and any CLI glue) so they surface both Turtle and RML artifacts while honoring the `rmlEnabled` metadata flag.
- Keep map-schema-backed helpers reusable: the CSV preprocessing module introduced for Task 3 should be callable from alignment tests to ensure parity with the retired `rmlexport` plugin outputs.
- Document the alignment contract in `docs/aicode/{your-name}-report-{timestamp}.md`, describing how to refresh baselines and validate both export formats end-to-end.

Testing
- Bun – simulate UI-triggered Turtle vs. RML downloads for the authority/ADD diagrams.
- pytest – assert the DrawIO pipeline reproduces the regenerated map_schema RML baselines and maintains Turtle isomorphism.
- Optional smoke – run the existing map_schema CLI against the same CSV inputs to prove regenerated fixtures remain faithful to the legacy flow.
:::

⸻

Testing Summary
Task    Language        Existing Tests  New Coverage    Framework
1       TypeScript      Yes     Black box + arbitrary string save       Bun
2       Python  Yes     IRI prefix + CSV metadata       pytest
3       Python  Partial Function extraction + optional params + regression      pytest
4       TS + Python     Yes     Pyodide (Node-build) + debug + E2E      Bun + pytest

⸻

Final Deliverables
1. DrawIO extension with black-box routing and arbitrary string save via existing RDF/XML code.
2. DrawIO parser (stdin input) extended for IRI prefix and CSV metadata.
3. map_schema module unchanged in behavior but now exporting graph_to_dataframe and dataframe_to_turtle (with optional params); ADD/Auth/CSV preprocessing excluded from these functions only.
4. Browser-based Pyodide pipeline with robust debug tooling, incremental integration, and Node-compatible test support (Bun + Volta).
5. Unified Bun + pytest test suite providing full unit, integration, and regression coverage across all components.
