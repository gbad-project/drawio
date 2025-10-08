Full Work Plan

Contributor Guidelines

- Take the first unimplemented task from the list below (if no status is indicated, assume it has not been implemented yet).
- Stick to your selected task. Going sideways to contribute to another task in passing is discouraged. If you desperately feel the urge to, you may leave a comment marking it as one of: AICODE-TODO (an unidentified task emerged), AICODE-ASK (stakeholder input is requested), AICODE-NOTE (important but no action requested).
- Once the task is completed and all planned tests pass, document all your efforts extensively under "docs/aicode/{your-name}-report-{timestamp}.md". Also, update the task status here in AGENTS.md. Finally, update the task status summary below.

Task Status Summary

{placeholder}

⸻

Task 1 – DrawIO Black Box Integration

Goal:
Enhance the DrawIO save flow so that, after XML serialization, the serialized XML is passed through a mock black box function that returns an arbitrary string, which is then saved using the existing RDF/XML save logic.

Steps:
	1.	Update Save Flow
	•	Current: interface → parameters → serialized XML → save.
	•	New: interface → serialized XML → black box → arbitrary string → save via existing RDF/XML functionality.
	2.	Implement Mock Black Box
	•	Input: serialized XML string.
	•	Action: perform any arbitrary transformation or return any string.
	•	Output: arbitrary string (not necessarily XML).
	3.	Reuse Existing Save Logic
	•	No new saving method.
	•	Use the current RDF/XML save routine to dump the returned string to file.
	•	Ensure the save path is content-agnostic.
	4.	Maintain backward compatibility when black box is disabled.

Testing (TypeScript / DrawIO Extension – Bun):
	•	Extend existing Bun test suite:
	•	Unit: verify black box I/O behavior.
	•	Integration: check end-to-end serialize → black box → save flow.
	•	Regression: confirm legacy XML save works unchanged.
	•	E2E: simulate full workflow with arbitrary string output.

⸻

Task 2 – Extend DrawIO Parser (stdin → rdflib Graph)

Goal:
Keep stdin input unchanged, but extend the parser to handle additional parameters and enrich its rdflib Graph output with metadata.

Steps:
	1.	Maintain stdin input reading as is.
	2.	Add new parameter handlers for:
	•	IRI prefixes
	•	CSV path
	3.	Embed metadata (prefixes, CSV path):
	•	as triples in rdflib Graph or in a companion dictionary.
	4.	Keep all existing parsing and graph construction logic intact.
	5.	Output: fully populated rdflib Graph.

Testing (Python / pytest):
	•	Extend current tests to cover:
	•	IRI prefix handling.
	•	CSV path processing.
	•	Metadata injection.
	•	Graph structure and serialization integrity.

⸻

Task 3 – Expose RML Converter Functions for Testing

Goal:
From the existing map_schema module, expose two core transformation functions without altering any logic, enabling direct unit testing while keeping module behavior identical.

Steps:
	1.	Identify Code Segments
	•	Locate code that transforms:
	•	an rdflib.Graph → Pandas DataFrame
	•	a Pandas DataFrame → Turtle
	2.	Function Extraction
	•	Encapsulate existing inline code into:
	•	Function A: graph_to_dataframe(graph: rdflib.Graph) → pandas.DataFrame
	•	Function B: dataframe_to_turtle(df: pandas.DataFrame) → str
	•	Keep logic and dependencies unchanged.
	3.	Reintegration
	•	Replace in-module inline logic with calls to these functions.
	•	Preserve identical runtime behavior.
	4.	Preserve Dependencies
	•	Retain all existing imports, helpers, and execution order.
	5.	Regression Artifacts
	•	Generate golden outputs using the unmodified module post-refactor.
	6.	Testing (Python / pytest)
	•	Unit: directly test both new functions.
	•	Regression: verify module outputs unchanged vs. artifacts.
	•	Integration: validate Graph → DataFrame → Turtle pipeline.

⸻

Task 4 – Browser Execution Pipeline (Pyodide Integration)

Goal:
Integrate Python execution into the DrawIO extension using Pyodide, enabling in-browser transformation of DrawIO XML → rdflib Graph → Pandas DataFrame → Turtle.
Implementation proceeds in two structured phases.

⸻

Phase 1 – Pyodide Integration & Debug Infrastructure
	1.	Integrate Pyodide Runtime
	•	Load Pyodide within the TypeScript extension (via web worker or dynamic import).
	•	Ensure async init and non-blocking UI behavior.
	2.	Minimal Python Mock
	•	Add a temporary Python function (e.g., process(text): return "mock:"+text) to validate integration.
	•	Connect the Task 1 black box to call this mock.
	3.	Debug Pipeline Setup
	•	Structured logging (TypeScript + Python).
	•	Capture exceptions, stdout/stderr, tracebacks.
	•	Implement log prefixes ([PYODIDE], [BLACKBOX], [PIPELINE]).
	•	Enable live variable inspection and dumping for Python execution context.
	4.	Validation & Smoke Tests
	•	Test message passing, serialization, async timing, and error handling.
	•	Extend Bun tests for mock invocation, exception propagation, and cleanup.

⸻

Phase 2 – Incremental Functional Integration
	1.	Progressive Function Port-In
	•	Integrate Python components sequentially:
	1.	DrawIO Parser (stdin → rdflib Graph)
	2.	graph_to_dataframe (Function A)
	3.	dataframe_to_turtle (Function B)
	2.	Incremental Debug & Verification
	•	After each integration:
	•	run in isolation within Pyodide,
	•	inspect inputs/outputs,
	•	validate against stand-alone Python execution.
	•	Add fine-grained debug logging for intermediate states (XML text, Graph stats, DataFrame preview, Turtle snippet).
	3.	End-to-End Assembly
	•	Chain all three functions inside the Pyodide black box:
XML → Graph → DataFrame → Turtle.
	•	Return Turtle to TypeScript and save via existing RDF/XML logic.
	4.	Testing & Regression
	•	Bun tests: async integration and E2E pipeline.
	•	pytest: unit + integration for Python functions.
	•	Cross-layer regression: compare browser vs. local Python outputs.

⸻

Testing Summary

Task	Language	Existing Tests	New Coverage	Framework
1	TypeScript	Yes	Black box + arbitrary string save	Bun
2	Python	Yes	IRI prefix + CSV metadata	pytest
3	Python	Partial	Function extraction + unit + regression	pytest
4	TS + Python	Yes	Pyodide integration + debug + E2E	Bun + pytest


⸻

Final Deliverables
	1.	Updated DrawIO extension with black-box routing and arbitrary string saving via existing RDF/XML logic.
	2.	Enhanced DrawIO parser reading from stdin and supporting IRI prefix and CSV metadata parameters.
	3.	map_schema module unchanged in behavior but now exporting graph_to_dataframe and dataframe_to_turtle for direct unit tests.
	4.	Browser-based Pyodide pipeline with robust debug tooling and incremental functional integration.
	5.	Unified Bun + pytest test suite providing granular unit, integration, and regression coverage across all components.
