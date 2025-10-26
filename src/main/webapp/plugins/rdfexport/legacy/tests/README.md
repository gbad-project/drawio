# pytest coverage of Python source

**[pvzhelnov](https://github.com/pvzhelnov)** commented on Oct 26, 2025

> This directory only contains pytest tests for the main `legacy/draw_io_parser.py <-> pyodide_pipeline/drawio_pipeline.py` Python source that actually gets embedded in `dist/rdfexport.js` to be used as a Draw\.io plugin under Pyodide runtime. The Bun script `bun run test` relies on exactly these tests, running them through `scripts/test_legacy.sh` entrypoint.
> 
> pytest tests for dev modules like `meta_builder/` and `debug/` are located under `meta_builder/tests/` and `debug/tests/`, respectively. Tests for `meta_builder/` are also included in `bun run test` (again, through `scripts/test_legacy.sh` entrypoint) because building of `legacy/draw_io_parser.py` depends on metabuilder logic (executed using `bun run build:py`, also performed by the entrypoint). Tests for `debug/`, however, are not included in that script – instead, `bun run test:pytest:all` was designed to run _all_ and any pytest tests found across the repo.
> 
> ## Salient points for test developers
> 
> ### Layer 1 – Python SDK
> 
> `legacy/tests/` features a neat workflow that allows roundtrip testing of the full Python cycle with just a few lines of code and without leaving Python – and could, thus, effectively be considered its SDK.
> 
> Consider this example:
> 
> ```python
> def test_parse_drawio_respects_include_label_toggle() -> None:
>     reset_graph_store()
>     xml_payload = _load_fixture("AA37 Department of Health.drawio")
> 
>     _, graph_without_labels = parse_drawio_xml(xml_payload, {"include_label": False})
>     without_count = sum(
>         1 for _ in graph_without_labels.triples((None, RDFS.label, None))
>     )
>     assert without_count == 0
> 
>     reset_graph_store()
>     _, graph_with_labels = parse_drawio_xml(xml_payload, {"include_label": True})
>     with_count = sum(1 for _ in graph_with_labels.triples((None, RDFS.label, None)))
>     assert with_count > 0
> ```
> 
> As a bit of context, this snippet relies on functions from `pyodide_pipeline/drawio_pipeline.py` module, which is a wrapper for the core `legacy/draw_io_parser.py` that ultimately gets invoked by TypeScript runtime. In particular, `src/pyodideRuntime.ts` module does the job:
> 
> After setting up paths, it invokes `from pyodide_pipeline import reset_graph_store; reset_graph_store()`, which unsets global graph vars, and then does this: `from pyodide_pipeline.drawio_pipeline import parse_drawio_xml_to_json; import json; parse_drawio_xml_to_json(${JSON.stringify(serializedXml)}, json.loads(${JSON.stringify(configJson)})` – and "the returned promise will resolve to the value of this expression" (quote from Pyodide docs).
> 
> `_load_fixture`, by the way, is a test-specific method that simply reads a file from `tests/fixtures/` dir.
> 
> ### Layers 2 & 3 – Python/TypeScript CLI and REPL
> 
> In contrast, tooling from `debug/` exposes a comprehensive roundtrip suite that goes beyond within-Python testing and actually runs inputs through the outer TypeScript layers, of which there are two:
> 
> _Layer 2:_ TypeScript/Pyodide wrapper exposing `mockBlackBoxModule.runDrawioPipeline` from `src/mockBlackBox.ts`.
> 
> _Layer 3:_ The outermost layer – plugin export hooks defined in `rdfexport.ts` itself.
> 
> `debug/` triggers both layers using a custom `run_scenario.ts` harness. For the plugin layer, it effectively simulates Draw\.io logic (or, at least I hope it does).
> 
> As a pleasant compliment, `debug/` also offers a within-Python round trip for regression testing that runs the given fixture through an older `draw_io_parser.py` extracted from an arbitrary historical commit (_Layer 0?_). The commit it defaults to is not the original version from Richard Williamson’s release, but the core there is still largely intact.
> 
> Of note, `bun run test` includes a Bun test suite (from `tests/rdfexport.test.ts`) that runs its own implementation of Layer 0–2–3 roundtrips for all-fixture regression tests. `debug/` specialized on manual/injections but also has a runner (slow) that does all fixtures at once (`debug/debug_cli_regression.py`).
> 
> This directory only contains pytest tests for the main `legacy/draw_io_parser.py <-> pyodide_pipeline/drawio_pipeline.py` Python source that actually gets embedded in `dist/rdfexport.js` to be used as a Draw\.io plugin under Pyodide runtime. The Bun script `bun run test` relies on exactly these tests, running them through `scripts/test_legacy.sh` entrypoint.
> 
> pytest tests for dev modules like `meta_builder/` and `debug/` are located under `meta_builder/tests/` and `debug/tests/`, respectively. Tests for `meta_builder/` are also included in `bun run test` (again, through `scripts/test_legacy.sh` entrypoint) because building of `legacy/draw_io_parser.py` depends on metabuilder logic (executed using `bun run build:py`, also performed by the entrypoint). Tests for `debug/`, however, are not included in that script – instead, `bun run test:pytest:all` was designed to run _all_ and any pytest tests found across the repo.
> 
> ## Salient points for test developers
> 
> ### Layer 1 – Python SDK
> 
> `legacy/tests/` features a neat workflow that allows roundtrip testing of the full Python cycle with just a few lines of code and without leaving Python – and could, thus, effectively be considered its SDK.
> 
> Consider this example:
> 
> ```python
> def test_parse_drawio_respects_include_label_toggle() -> None:
>     reset_graph_store()
>     xml_payload = _load_fixture("AA37 Department of Health.drawio")
> 
>     _, graph_without_labels = parse_drawio_xml(xml_payload, {"include_label": False})
>     without_count = sum(
>         1 for _ in graph_without_labels.triples((None, RDFS.label, None))
>     )
>     assert without_count == 0
> 
>     reset_graph_store()
>     _, graph_with_labels = parse_drawio_xml(xml_payload, {"include_label": True})
>     with_count = sum(1 for _ in graph_with_labels.triples((None, RDFS.label, None)))
>     assert with_count > 0
> ```
> 
> As a bit of context, this snippet relies on functions from `pyodide_pipeline/drawio_pipeline.py` module, which is a wrapper for the core `legacy/draw_io_parser.py` that ultimately gets invoked by TypeScript runtime. In particular, `src/pyodideRuntime.ts` module does the job:
> 
> After setting up paths, it invokes `from pyodide_pipeline import reset_graph_store; reset_graph_store()`, which unsets global graph vars, and then does this: `from pyodide_pipeline.drawio_pipeline import parse_drawio_xml_to_json; import json; parse_drawio_xml_to_json(${JSON.stringify(serializedXml)}, json.loads(${JSON.stringify(configJson)})` – and "the returned promise will resolve to the value of this expression" (quote from Pyodide docs).
> 
> `_load_fixture`, by the way, is a test-specific method that simply reads a file from `tests/fixtures/` dir.
> 
> ### Layers 2 & 3 – Python/TypeScript CLI and REPL
> 
> In contrast, tooling from `debug/` exposes a comprehensive roundtrip suite that goes beyond within-Python testing and actually runs inputs through the outer TypeScript layers, of which there are two:
> 
> _Layer 2:_ TypeScript/Pyodide wrapper exposing `mockBlackBoxModule.runDrawioPipeline` from `src/mockBlackBox.ts`.
> 
> _Layer 3:_ The outermost layer – plugin export hooks defined in `rdfexport.ts` itself.
> 
> `debug/` triggers both layers using a custom `run_scenario.ts` harness. For the plugin layer, it effectively simulates Draw\.io logic (or, at least I hope it does).
> 
> As a pleasant compliment, `debug/` also offers a within-Python round trip for regression testing that runs the given fixture through an older `draw_io_parser.py` extracted from an arbitrary historical commit (_Layer 0?_). The commit it defaults to is not the original version from Richard Williamson’s release, but the core there is still largely intact.
> 
> Of note, `bun run test` includes a Bun test suite (from `tests/rdfexport.test.ts`) that runs its own implementation of Layer 0–2–3 roundtrips for all-fixture regression tests. `debug/` specialized on manual/injections but also has a runner (slow) that does all fixtures at once (`debug/debug_cli_regression.py`).
