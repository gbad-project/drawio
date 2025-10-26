# pytest coverage of Python source

> [!NOTE]
> All paths are relative to `<repo-root>/src/main/webapp/plugins/rdfexport/`

**[pvzhelnov](https://github.com/pvzhelnov)** commented on Oct 26, 2025

> This directory only contains pytest tests for the main `legacy/draw_io_parser.py <-> pyodide_pipeline/drawio_pipeline.py` Python source that actually gets embedded in `dist/rdfexport.js` to be used as a Draw\.io plugin under Pyodide runtime. The Bun script `bun run test` relies on exactly these tests, running them through `scripts/test_legacy.sh` entrypoint.
> 
> pytest tests for dev modules like `meta_builder/` and `debug/` are located under `meta_builder/tests/` and `debug/tests/`, respectively. Tests for `meta_builder/` are also included in `bun run test` (again, through `scripts/test_legacy.sh` entrypoint) because building of `legacy/draw_io_parser.py` depends on metabuilder logic (executed using `bun run build:py`, also performed by the entrypoint). Tests for `debug/`, however, are not included in that script – instead, `bun run test:pytest:all` was designed to run _all_ and any pytest tests found across the repo.
> 
> ## Salient points for test developers
> 
> ### Layer 0 – Original Records in Contexts parser for draw\.io
>
> This includes both the original [post-v0.2.0 commit 5d85cf0](https://github.com/williamsonrichard/records_in_contexts_draw_io_parser/blob/5d85cf05f47b3e14c3161a3ad2cd57f5fde67d09/draw_io_parser.py) (May 13, 2024) version by Richard Williamson (backed up [here](../original/draw_io_parser_5d85cf0.py) in this repo) and a [modified](../original/draw_io_parser.py) version frozen for `meta_builder/` overrides. They are archived and should not be tested.
>
> `debug/` offers a within-Python round trip for regression testing that runs a given fixture through an older `draw_io_parser.py` extracted from an arbitrary historical commit. The commit it defaults to is not the original version from Richard Williamson’s release, but the core there is still [largely intact](https://github.com/gbad-project/drawio/compare/6834538341f6defde4ed72b6927949e05c41cf8f..0599a6483a54cb6c78429eca52e59058469f5204).
>
> ### Layer 1 – Metabuilder overrides
>
> These provide patches and a bundling mechanism for the modified, frozen version of `legacy/original/draw_io_parser.py` and are amply described here: [meta_builder/readme.md](../../meta_builder/readme.md)
>
> ### Layer 2 – Python testing SDK
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
> As a bit of context, functions in this snippet (except `_load_fixture`, which is a test-specific method that simply reads a file from `tests/fixtures/` dir) come from `pyodide_pipeline/drawio_pipeline.py` module, which is a wrapper for the core `legacy/draw_io_parser.py` that ultimately gets invoked by TypeScript runtime. In particular, `src/pyodideRuntime.ts` module does the job:
> 
> After setting up paths, it invokes `from pyodide_pipeline import reset_graph_store; reset_graph_store()`, which unsets global graph vars, and then does this: `from pyodide_pipeline.drawio_pipeline import parse_drawio_xml_to_json; import json; parse_drawio_xml_to_json(${JSON.stringify(serializedXml)}, json.loads(${JSON.stringify(configJson)})` – and "the returned promise will resolve to the value of this expression" (quote from Pyodide docs).
> 
> ### Layers 3 & 4 – Python/TypeScript CLI and REPL
> 
> In contrast, tooling from `debug/` exposes a comprehensive roundtrip suite that goes beyond within-Python testing and actually runs inputs through the outer TypeScript layers, of which there are two:
> 
> _Layer 3:_ TypeScript/Pyodide wrapper exposing `mockBlackBoxModule.runDrawioPipeline` from `src/mockBlackBox.ts`.
> 
> _Layer 4:_ The outermost source layer – plugin export hooks defined in `src/rdfexport.ts`, main plugin source file.
> 
> `debug/` triggers both layers using a custom `debug/run_scenario.ts` harness. For the plugin layer, it effectively simulates Draw\.io logic (or, at least I hope it does).
> 
> Of note, `bun run test` includes a Bun test suite (from `tests/rdfexport.test.ts`) that runs its own implementation of Layer 0–3–4 roundtrips for all-fixture regression tests. `debug/` specializes in manual/injections but also has a runner (slow) that does all fixtures at once (`debug/debug_cli_regression.py`).
>
> ### Layer 5 – Production plugin
>
> `scripts/build.ts` transpiles `src/rdfexport.ts` and bundles it together with `legacy/draw_io_parser.py` and `pyodide_pipeline/drawio_pipeline.py` code and base64-encoded Python dependency wheels (see the list here: `scripts/download_pyodide_assets.sh`) to produce `dist/rdfexport.js`. When run via `bun run build:ts`, this also conveniently copies the distributable one level higher to ultimately become available to the Draw\.io app for import.
>
> After this, a static server can be run to serve precompiled Draw\.io application files (e.g., using `bun run serve` that just starts a default Python HTTP server). The app is available under `http://localhost:8000/src/main/webapp/`, and the plugin can be accessed by adding `?p=rdf` to the URL or through the app settings.
>
> I have not implemented E2E testing (e.g., using Playwright) because Codex does not seem to support it well. It has also been quite enjoyable to just test comprehensively up until _Layer 4_ and then run sanity checks manually in the browser, especially since the application is highly graphical in nature. However, I recognize that browser automation is still a consideration for apt testers.
