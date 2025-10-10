Work Plan

Feature Description — In-Browser RDF Transformation Pipeline for DrawIO Extension

This feature introduces an in-browser data transformation pipeline to the DrawIO extension so serialized diagram XML can be round-tripped to Turtle without leaving the editor. The extension still serializes diagrams as XML, but that payload now flows through a TypeScript “black box” bridge (`src/main/webapp/plugins/rdfexport/src/mockBlackBox.ts`) that boots a Pyodide-backed Python runtime (`pyodidePipeline.ts`) before delegating to the patched DrawIO parser living in `legacy/draw_io_parser.py`.

Inside Pyodide, `pyodide_pipeline/drawio_pipeline.py` normalizes the XML, calls `_build_graph_from_raw_xml`, and caches the resulting `DrawioParserGraph` plus its derived Turtle serialization. The bridge returns a JSON summary (graph id, namespaces, CSV path metadata, and Turtle payload) so the plugin can save a `.ttl` export using the existing RDF/XML save logic, with the hard switch to Turtle defaults now exercised by `runDrawioPipeline` in the Bun tests.

Task 3 will still expose pure `graph_to_dataframe` / `dataframe_to_turtle` helpers out of `legacy/map_schema.py` so the pipeline can expand beyond the direct DrawIO parser output. Until that work lands, map_schema remains untouched in production flows and the Pyodide bridge focuses on faithfully reproducing the DrawIO parser’s Turtle output (guarded by the Bun + rdflib isomorphism harness).

A Node-compatible Pyodide build (run under Bun + Volta) provides a fully local, testable environment for executing and debugging Python code within TypeScript. Robust logging, incremental integration, and fine-grained test coverage (via Bun and pytest) ensure a stable, transparent, and extensible foundation for RDF data transformation directly within the DrawIO extension.

Historical context (feat/rml branch milestones): the branch introduced the custom RDF/XML export plugin, followed by CSV path controls and deterministic regression fixtures (`1e4582a` → `5d2b0fb`). Subsequent merges added metadata-aware parser flows, reproducible baseline generators, and the mock black box annotated save path (through commits such as `f2034d1`, `a28a81a`, `gpt-5-codex` task reports). Latest `work` commit `9e073ca` (2025-10-09) aligned Turtle export metadata and ported rdflib isomorphism checks into the Bun regression harness to guard Pyodide outputs. The same-day stabilization commit `6fc153c` reconciled the Pyodide pipeline with the restored mock black box tests after the experimental Turtle download spike in `4952510`, ensuring Bun coverage stayed authoritative while the UI flipped to Turtle defaults.

⸻

Contributor Guidelines

- Take the first unimplemented task from the list below (if no status is indicated, assume it has not been implemented yet).
- Stick to your selected task. Going sideways to contribute to another task in passing is discouraged. If you desperately feel the urge to, you may leave a comment marking it as one of: AICODE-TODO (an unidentified task emerged), AICODE-ASK (stakeholder input is requested), AICODE-NOTE (important but no action requested).
- Once the task is completed and all planned tests pass, document all your efforts extensively under "docs/aicode/{your-name}-report-{timestamp}.md". Also, update the task status here in AGENTS.md. Finally, update the task status summary below.
- Keep tooling aligned with the historical workflow captured in the codex reports: install JavaScript dependencies with `bun install`, hydrate Python deps with `bun run setup:uv`, sync Pyodide assets via `bun run setup:pyodide`, then exercise Bun coverage with `bun run test` from `src/main/webapp/plugins/rdfexport`.
- **Always** be sure to run `bun run check` before committing and fix any issues before committing.

⸻

Task Status Summary

Task 1 – DrawIO Black Box Integration: ✅ Completed on 2025-10-08 by gpt-5-codex
Task 2a - Remove Hardcoded Classes and Property CURIEs from DrawIO Parser: ✅ Completed on 2025-10-09 by gpt-5-codex
Task 2b - Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawioParserGraph): ✅ Completed on 2025-02-14 by gpt-5-codex
Bugfix – Base URI minted individuals: ✅ Completed on 2025-10-10 by chatgpt
Task 3 – Expose and Extend map_schema Functions for Testing and DrawIO Integration: ⏳ Not started
Task 4 – Browser Execution Pipeline (Pyodide Integration): 🚧 Phase 1 completed 2025-02-15 by gpt-5-codex (Phase 2 pending)

⸻

Task 1 – DrawIO Black Box Integration

Status: ✅ Completed on 2025-10-08 by gpt-5-codex

Goal
Enhance the DrawIO save flow so that, after XML serialization, the serialized XML is passed through a mock black box function that returns an arbitrary string, which is then saved using the existing RDF/XML save logic.

Steps
	1.	Update Save Flow
	•	Current: interface → parameters → serialized XML → save.
	•	New: interface → serialized XML → black box → arbitrary string → save via existing RDF/XML functionality.
	2.	Implement Mock Black Box
	•	Input = serialized XML string.
	•	Output = arbitrary string (not necessarily XML).
	3.	Reuse Existing Save Logic
	•	Reuse existing RDF/XML save routine verbatim; ensure it accepts any string payload.
	4.	Backward compatibility must be preserved.

Testing (TypeScript / DrawIO Extension – Bun)
	•	Extend Bun tests:
	•	Unit – black box I/O behavior.
	•	Integration – serialize → black box → save flow.
	•	Regression – legacy XML save unaffected.
	•	E2E – simulate full workflow with arbitrary string output.

⸻

## **Task 2a – Remove Hardcoded Classes and Property CURIEs from DrawIO Parser**

Status: ✅ Completed on 2025-10-09 by gpt-5-codex

**Goal**
Refactor the DrawIO parser to eliminate hardcoded lists of allowed **classes**, **object properties**, and **datatype properties**.
The parser must instead accept any CURIE whose prefix exists in the parsed prefix–IRI mapping.
Changes should be minimal and backward-compatible.

### **Implementation Steps**

1. **Locate Hardcoded Elements**

   * Identify the code sections where class and property CURIEs are explicitly enumerated.
   * Note them for documentation but remove them from runtime validation.

2. **Replace with Dynamic Validation**

   * Obtain known prefixes from the parser’s `prefix_iri_dict` (namespace manager).
   * Accept any CURIE whose prefix appears in that mapping and resolves to a valid IRI.
   * Preserve all existing error-handling behavior for undeclared or malformed prefixes.

3. **Regression Verification**

   * Run every **pristine `*.drawio` fixture** (exclude any `*-with-metadata.drawio` and all `*.rdf` fixtures, which belong to different code paths) using the unmodified DrawIO parser to produce baseline Graph objects.
   * Re-run the same fixtures using the refactored parser that no longer relies on hardcoded CURIEs.
   * Compare the resulting Graph objects directly — not by string serialization — using **graph isomorphism checks or equivalent semantic equality methods** available in rdflib.
   * Verify that all baseline and refactored Graphs are isomorphic, confirming no structural or semantic regressions.

4. **Testing (pytest)**

   * Add tests for valid arbitrary CURIEs with declared prefixes.
   * Add negative tests for undeclared prefixes.
   * Include automated isomorphism-based regression checks between pre-change and post-change parser outputs for all pristine fixtures.

⸻

Task 2b – Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawioParserGraph)

Status: ✅ Completed on 2025-02-14 by gpt-5-codex

Goal
Enhance the DrawIO parser to correctly process stdin-supplied XML containing embedded metadata (CSV path, prefix–IRI pairs, and base URI) injected by rdfexport.ts.
The parser must extract this information directly from the XML and return a specialized DrawioParserGraph object that:
	•	Is a full subclass of rdflib.Graph,
	•	Has a single declared property csv_path,
	•	Uses the standard rdflib namespace manager to hold prefix IRIs and base URI (no external metadata dict).

Implementation Steps
	1.	Study Metadata Injection Flow
	•	Examine src/main/webapp/plugins/rdfexport/src/rdfexport.ts to see how prefix–IRI mappings, base URI, and CSV path are inserted into the DrawIO DOM.
	•	Inspect
src/main/webapp/plugins/rdfexport/tests/fixtures/AA37 Department of Health-with-metadata.drawio
for the exact node structure.
	2.	Generate Enriched Fixtures
	•	Start with pristine .drawio fixtures under
src/main/webapp/plugins/rdfexport/tests/fixtures/.
	•	Use the existing patcher utility

src/main/webapp/plugins/rdfexport/tests/utils/patchDrawioWithMetadata.ts

to produce corresponding *-with-metadata.drawio files embedding valid CSV path, prefix–IRI mappings, and base URI.

	•	Verify the generated files match the reference format.

	3.	Define DrawioParserGraph Class
	•	Implement a subclass of rdflib.Graph with one declared property for CSV path:

from rdflib import Graph
from typing import Optional

class DrawioParserGraph(Graph):
    def __init__(self, *args, csv_path: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_path = csv_path


	•	Ensure the inherited rdflib namespace manager naturally stores prefixes, IRIs, and base URI.
	•	csv_path simply records the parsed CSV path value from XML.

	4.	Modify Parser Logic
	•	Continue reading serialized XML from stdin.
	•	Parse and extract:
	•	Prefix–IRI pairs → register in namespace manager,
	•	Base URI → assign to Graph,
	•	CSV path → assign to csv_path property.
	•	Populate triples as before; all other behavior remains unchanged.
	•	Return a fully initialized DrawioParserGraph instance.
	5.	Regression Testing (pytest)
	•	Extend tests to include both pristine and *-with-metadata.drawio fixtures.
	•	For each fixture:
	•	Feed via stdin,
	•	Assert:
	•	Graph parses successfully,
	•	Prefixes and base URI are registered in namespace manager,
	•	csv_path property matches the injected value.
	•	Confirm all fixtures pass and Graph serialization is stable.

⸻

Task 3 – Expose and Extend map_schema Functions for Testing and DrawIO Integration

Preface
map_schema currently:
	•	lacks prefix IRI dict support,
	•	has only partial CSV path support,
	•	includes dataset-specific ADD/Auth logic and CSV preprocessing routines.

For this task:
	•	Optional prefix_iri_dict and csv_path knobs are added for DrawIO only.
	•	Existing logic remains untouched for legacy consumers.
	•	CSV preprocessing, ADD, and Auth sections are ignored in the new functions but remain in the module.

Goal
Expose two pure functions—graph_to_dataframe and dataframe_to_turtle—and add optional parameter support while keeping module behavior identical.

Steps
	1.	Introduce Optional Parameters
	•	Add prefix_iri_dict and csv_path kwargs guarded by if checks.
	2.	Identify Core Transformation Code
	•	Extract generic rdflib → DataFrame and DataFrame → Turtle sections; omit ADD/Auth/CSV preprocessing.
	3.	Function Extraction
	•	Function A:

def graph_to_dataframe(graph: rdflib.Graph,
                       prefix_iri_dict: Optional[dict] = None,
                       csv_path: Optional[str] = None) -> pandas.DataFrame


	•	Function B:

def dataframe_to_turtle(df: pandas.DataFrame,
                        prefix_iri_dict: Optional[dict] = None) -> str


	•	Copy logic verbatim from inline code.

	4.	Reintegrate into map_schema
	•	Replace inline sections with calls to A and B.
	•	Leave ADD/Auth and CSV preprocessing paths untouched.
	5.	Preserve Context and Dependencies
	•	No change to imports, helpers, execution order.
	6.	Regression Artifacts
	•	Generate golden outputs before refactor; confirm identical results after.
	7.	Testing (Python / pytest)
	•	Unit – test A and B directly (including optional params).
	•	Regression – compare full-module results pre/post.
	•	Integration – test DrawIO path using optional inputs.

⸻

Task 4 – Browser Execution Pipeline (Pyodide Integration)

Goal
Integrate the Python runtime (Pyodide) into the DrawIO extension for in-browser execution of the XML → rdflib → DataFrame → Turtle pipeline.
Implementation proceeds in two phases.

⸻

Phase 1 – Pyodide Integration & Debug Infrastructure
	Status: ✅ Completed on 2025-02-15 by gpt-5-codex
	1.	Integrate Pyodide Runtime
	•	Load Pyodide within the TypeScript extension (using Web Worker or dynamic import).
	•	Non-blocking UI init.
	2.	Minimal Python Mock
	•	Implement process(text) mock returning "mock:" + text.
	•	Connect this mock to the black box from Task 1.
	3.	Debug Pipeline Setup
	•	Structured logging (TypeScript + Python).
	•	Capture stdout/stderr and tracebacks.
	•	Add log prefixes ([PYODIDE], [BLACKBOX], [PIPELINE]).
	•	Expose optional debug REPL or variable dump.
	4.	Validation & Smoke Tests
	•	Verify TS ↔ Pyodide messaging, serialization, and async behavior.
	•	Extend Bun tests for mock invocation, error propagation, and cleanup.
	•	Important: All tests must use the Node-compatible build of Pyodide configured via Bun + Volta as specified in the repo.
Do not attempt to test via Playwright or Selenium (browser automation is out of scope for this phase).

⸻

Phase 2 – Incremental Functional Integration
	1.	Progressive Function Port-In
	•	Sequentially integrate:
	1.	DrawIO Parser (stdin → rdflib Graph)
	2.	graph_to_dataframe (Function A)
	3.	dataframe_to_turtle (Function B)
	2.	Incremental Debug & Verification
	•	After each integration:
	•	run in isolation inside Pyodide,
	•	verify I/O equivalence vs. stand-alone Python.
	•	Add fine-grained debug logs for XML, Graph stats, DataFrame preview, Turtle output.
	3.	End-to-End Assembly
	•	Chain all three functions inside Pyodide: XML → Graph → DataFrame → Turtle.
	•	Return Turtle string to TypeScript and save via existing RDF/XML logic.
	4.	Testing & Regression
	•	Bun tests: async integration + E2E pipeline.
	•	pytest: unit + integration for Python functions.
	•	Cross-layer regression: compare browser vs. local Python outputs.

⸻

Testing Summary

Task	Language	Existing Tests	New Coverage	Framework
1	TypeScript	Yes	Black box + arbitrary string save	Bun
2	Python	Yes	IRI prefix + CSV metadata	pytest
3	Python	Partial	Function extraction + optional params + regression	pytest
4	TS + Python	Yes	Pyodide (Node-build) + debug + E2E	Bun + pytest


⸻

Final Deliverables
	1.	DrawIO extension with black-box routing and arbitrary string save via existing RDF/XML code.
	2.	DrawIO parser (stdin input) extended for IRI prefix and CSV metadata.
	3.	map_schema module unchanged in behavior but now exporting graph_to_dataframe and dataframe_to_turtle (with optional params); ADD/Auth/CSV preprocessing excluded from these functions only.
	4.	Browser-based Pyodide pipeline with robust debug tooling, incremental integration, and Node-compatible test support (Bun + Volta).
	5.	Unified Bun + pytest test suite providing full unit, integration, and regression coverage across all components.
