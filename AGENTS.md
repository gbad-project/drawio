Work Plan

Feature Description — In-Browser RDF Transformation Pipeline for DrawIO Extension

This feature introduces a full in-browser data transformation pipeline to the DrawIO extension, enabling it to convert diagram models directly into RDF/Turtle representations without external processing. The extension already serializes diagrams as XML; this implementation routes that XML through a new TypeScript “black box” layer, which invokes embedded Python code via Pyodide.

The Python layer uses the existing ecosystem of parsers and converters — notably the DrawIO parser and the map_schema module (found under "src/main/webapp/plugins/rdfexport/legacy/") — to transform serialized XML into an rdflib Graph, then into a Pandas DataFrame, and finally build a new rdflib Graph serialize it as Turtle (RML mapping). The output Turtle text is returned to the extension and saved using the existing RDF/XML save functionality.

The system preserves all legacy functionality while adding optional support for prefix IRI dictionaries and CSV paths, introduced as non-invasive parameters for the DrawIO pipeline. The extraction of two reusable functions from map_schema (graph_to_dataframe and dataframe_to_turtle) allows isolated unit testing and integration with the browser runtime, without disturbing existing ADD/Auth dataset logic or CSV preprocessing routines.

A Node-compatible Pyodide build (run under Bun + Volta) provides a fully local, testable environment for executing and debugging Python code within TypeScript. Robust logging, incremental integration, and fine-grained test coverage (via Bun and pytest) ensure a stable, transparent, and extensible foundation for RDF data transformation directly within the DrawIO extension.

⸻

Contributor Guidelines

- Take the first unimplemented task from the list below (if no status is indicated, assume it has not been implemented yet).
- Stick to your selected task. Going sideways to contribute to another task in passing is discouraged. If you desperately feel the urge to, you may leave a comment marking it as one of: AICODE-TODO (an unidentified task emerged), AICODE-ASK (stakeholder input is requested), AICODE-NOTE (important but no action requested).
- Once the task is completed and all planned tests pass, document all your efforts extensively under "docs/aicode/{your-name}-report-{timestamp}.md". Also, update the task status here in AGENTS.md. Finally, update the task status summary below.

⸻

Task Status Summary

Task 1 – DrawIO Black Box Integration: ✅ Completed on 2025-10-08 by gpt-5-codex
Task 2 – Extend DrawIO Parser (stdin → rdflib Graph): ⏳ Not started
Task 3 – Expose and Extend map_schema Functions for Testing and DrawIO Integration: ⏳ Not started
Task 4 – Browser Execution Pipeline (Pyodide Integration): ⏳ Not started

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

Task 2 – Extend DrawIO Parser (stdin → rdflib Graph)

Goal
Keep stdin input unchanged, extend parser to handle extra parameters and augment its rdflib Graph output with metadata.

Steps
	1.	Retain stdin input as is.
	2.	Add new parameter handlers for IRI prefixes and CSV path.
	3.	Embed metadata (prefixes, CSV path) as triples or a metadata dictionary.
	4.	Preserve existing parsing and graph construction logic.
	5.	Output = rdflib Graph.

Testing (Python / pytest)
	•	Add tests for IRI prefix handling, CSV path parsing, and metadata embedding.
	•	Validate graph structure and serialization stability.

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
