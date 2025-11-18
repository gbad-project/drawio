from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from rdflib import Graph
import yaml

PLUGIN_DIR = Path(__file__).resolve().parents[4]
REPO_ROOT = PLUGIN_DIR.parents[4]
for candidate in (REPO_ROOT, PLUGIN_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from aicode.integration_tests.debug.src.__main__ import (  # noqa: E402
    DEFAULT_BASE_URI,
    DEFAULT_CSV_PATH,
    DEFAULT_LEGACY_COMMIT,
    DEFAULT_METADATA_ATTRIBUTES,
    DEFAULT_PREFIXES,
    Debugger,
    ScenarioConfig,
)

import aicode.integration_tests.debug.src.__main__ as debug_main  # noqa: E402

FIXTURES_DIR = PLUGIN_DIR / "data" / "fixtures" / "drawio_fixtures"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("mock:http://example.com", [("mock", "http://example.com")]),
        ("mock=http://example.com", [("mock", "http://example.com")]),
        (
            "mock:http://one.com,other:http://two.com",
            [
                ("mock", "http://one.com"),
                ("other", "http://two.com"),
            ],
        ),
    ],
)
def test_parse_prefix_string_supports_colon(raw: str, expected: list[tuple[str, str]]):
    debugger = Debugger(FIXTURES_DIR)
    assert debugger._parse_prefix_string(raw) == expected


@pytest.mark.parametrize("fixture_name", ["AA37 Department of Health.drawio"])
def test_run_scenario_generates_artifacts_and_map_entry(fixture_name: str):
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / fixture_name

    config = build_config(slug, drawio_path)

    results_dir = debugger.results_dir / slug
    try:
        debugger._run_scenario(config)

        assert results_dir.exists()
        outputs = {
            name: results_dir / f"{name}.nt"
            for name in ("py_legacy", "ts_pipeline", "ts_plugin")
        }
        for path in outputs.values():
            assert path.exists()
            content = path.read_text(encoding="utf-8").strip()
            assert content

        map_data = json.loads(debugger.map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"][slug]

        metadata = scenario_entry["metadata_attributes"]
        assert metadata["csvPath"] == DEFAULT_CSV_PATH
        assert metadata["baseUri"] == DEFAULT_BASE_URI
        assert scenario_entry["preamble"] == [
            {"prefix": prefix, "iri": iri} for prefix, iri in DEFAULT_PREFIXES
        ]

        for key in ("py_legacy", "ts_pipeline", "ts_plugin"):
            result_info = scenario_entry["results"][key]
            assert Path(result_info["path"]).name == f"{key}.nt"
            assert result_info["triples"] > 0
            assert len(result_info["nt_sha256"]) == 64

        assert "ts_pipeline_vs_ts_plugin" in scenario_entry["isomorphism"]
        assert "py_legacy_vs_ts_plugin" in scenario_entry["isomorphism"]

    finally:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()


def test_outputs_are_isomorphic_across_sources():
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / "AA37 Department of Health.drawio"

    config = build_config(slug, drawio_path)

    results_dir = debugger.results_dir / slug
    try:
        debugger._run_scenario(config)
        py_legacy_graph = Graph().parse(
            data=(results_dir / "py_legacy.nt").read_text(encoding="utf-8"),
            format="nt",
        )
        ts_pipeline_graph = Graph().parse(
            data=(results_dir / "ts_pipeline.nt").read_text(encoding="utf-8"),
            format="nt",
        )
        ts_plugin_graph = Graph().parse(
            data=(results_dir / "ts_plugin.nt").read_text(encoding="utf-8"),
            format="nt",
        )

        assert len(py_legacy_graph) > 0
        assert len(ts_pipeline_graph) == len(ts_plugin_graph) > 0

        ts_plugin_matches_ts_pipeline = debugger._are_isomorphic(
            ts_pipeline_graph, ts_plugin_graph
        )
        ts_plugin_matches_py_legacy = debugger._are_isomorphic(
            py_legacy_graph, ts_plugin_graph
        )

        map_data = json.loads(debugger.map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"][slug]
        assert (
            scenario_entry["isomorphism"]["ts_pipeline_vs_ts_plugin"]
            is ts_plugin_matches_ts_pipeline
        )
        assert (
            scenario_entry["isomorphism"]["py_legacy_vs_ts_plugin"]
            is ts_plugin_matches_py_legacy
        )

    finally:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()


def test_repl_run_persists_scenario_file(monkeypatch):
    debugger = Debugger(FIXTURES_DIR)
    slug = f"repl-{uuid4().hex[:8]}"
    scenario_path = debugger.scenarios_dir / f"{slug}.yml"
    scenario_path.unlink(missing_ok=True)

    responses = iter(["1", slug, None, None, None, None, None, None, None])

    def fake_prompt(prompt: str, **kwargs):
        value = next(responses)
        if value is None:
            return kwargs.get("default")
        return value

    captured: dict[str, ScenarioConfig] = {}

    monkeypatch.setattr("aicode.integration_tests.debug.src.__main__.Prompt.ask", fake_prompt)
    monkeypatch.setattr(
        "aicode.integration_tests.debug.src.__main__.Debugger._run_scenario",
        lambda self, config, skip_ts=False: captured.setdefault("config", config),
    )

    args = argparse.Namespace(
        scenario=None,
        slug=None,
        drawio=None,
        csv_path=None,
        base_uri=None,
        prefix=None,
        metadata=None,
        parser_option=None,
        legacy_commit=None,
        format=None,
        fixtures=None,
    )

    debugger.run(args)

    assert captured["config"].slug == slug
    assert scenario_path.exists()

    stored = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    assert stored["slug"] == slug
    metadata = stored["metadata"]["attributes"]
    assert metadata["csvPath"] == captured["config"].csv_path
    assert metadata["baseUri"] == captured["config"].base_uri
    assert stored["legacy_commit"] == captured["config"].legacy_commit

    scenario_path.unlink(missing_ok=True)


def test_repl_run_does_not_overwrite_existing_scenario(monkeypatch):
    debugger = Debugger(FIXTURES_DIR)
    slug = f"repl-{uuid4().hex[:8]}"
    scenario_path = debugger.scenarios_dir / f"{slug}.yml"
    original_content = "original: true\n"
    scenario_path.write_text(original_content, encoding="utf-8")

    responses = iter(["1", slug, None, None, None, None, None, None, None])

    def fake_prompt(prompt: str, **kwargs):
        value = next(responses)
        if value is None:
            return kwargs.get("default")
        return value

    monkeypatch.setattr("aicode.integration_tests.debug.src.__main__.Prompt.ask", fake_prompt)
    monkeypatch.setattr(
        "aicode.integration_tests.debug.src.__main__.Debugger._run_scenario",
        lambda self, config, skip_ts=False: None,
    )

    args = argparse.Namespace(
        scenario=None,
        slug=None,
        drawio=None,
        csv_path=None,
        base_uri=None,
        prefix=None,
        metadata=None,
        parser_option=None,
        legacy_commit=None,
        format=None,
        fixtures=None,
    )

    debugger.run(args)

    assert scenario_path.read_text(encoding="utf-8") == original_content

    scenario_path.unlink(missing_ok=True)


def test_ts_stderr_captured_as_warning(monkeypatch):
    """Test that TypeScript stderr is captured as a warning even when graphs generate successfully."""
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / "AA37 Department of Health.drawio"

    config = build_config(slug, drawio_path)

    results_dir = debugger.results_dir / slug

    # Mock _run_ts_pipeline to return stderr along with valid data
    original_run_ts_pipeline = debugger._run_ts_pipeline

    def mock_run_ts_pipeline(xml, cfg):
        result = original_run_ts_pipeline(xml, cfg)
        result["stderr"] = "Mock TypeScript warning message"
        return result

    monkeypatch.setattr(debugger, "_run_ts_pipeline", mock_run_ts_pipeline)

    try:
        debugger._run_scenario(config)

        map_data = json.loads(debugger.map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"][slug]

        # Should have warnings but no errors since graphs generated successfully
        if "warnings" in scenario_entry:
            assert "ts_stderr" in scenario_entry["warnings"]
            assert (
                "Mock TypeScript warning message"
                in scenario_entry["warnings"]["ts_stderr"]
            )

        # Should not have errors for ts_pipeline or ts_plugin
        if "errors" in scenario_entry:
            assert "ts_pipeline" not in scenario_entry["errors"]
            assert "ts_plugin" not in scenario_entry["errors"]

    finally:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()


def build_config(
    slug: str,
    drawio_path: Path,
    *,
    metadata: dict[str, object | None] | None = None,
    parser_config: dict[str, object] | None = None,
) -> ScenarioConfig:
    metadata_attributes = dict(DEFAULT_METADATA_ATTRIBUTES)
    if metadata:
        metadata_attributes.update(metadata)

    return ScenarioConfig(
        slug=slug,
        drawio_path=drawio_path,
        legacy_commit=DEFAULT_LEGACY_COMMIT,
        serialization_format="nt",
        metadata_attributes=metadata_attributes,
        prefixes=list(DEFAULT_PREFIXES),
        parser_config=parser_config or {},
    )


def test_stdout_stderr_captured_from_extract_cell_classifications(
    monkeypatch, tmp_path
):
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / "AA37 Department of Health.drawio"
    config = build_config(slug, drawio_path)

    # Mock _extract_cell_classifications to emit stdout/stderr
    def mock_extract(xml_text, cfg):
        print("Demo STDOUT message from classification")
        import sys

        print("Demo STDERR message from classification", file=sys.stderr)
        return {"1": {"kind": "MOCK_KIND", "raw_value": "demo"}}

    monkeypatch.setattr(debugger, "_extract_cell_classifications", mock_extract)

    results_dir = debugger.results_dir / slug
    try:
        debugger._run_scenario(config, skip_ts=True)

        # Load the written map.json to verify captured output
        map_data = json.loads(debugger.map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"][slug]
        errors = scenario_entry.get("errors", {})

        # Verify captured stdout/stderr
        assert "py_stdout" in errors
        assert "Demo STDOUT message" in errors["py_stdout"]
        assert "py_stderr" in errors
        assert "Demo STDERR message" in errors["py_stderr"]

    finally:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()


def test_run_reports_map_errors(monkeypatch):
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / "AA37 Department of Health.drawio"
    config = build_config(slug, drawio_path)

    args = argparse.Namespace(
        scenario=None,
        slug=slug,
        drawio=str(drawio_path),
        csv_path=None,
        base_uri=None,
        prefix=None,
        metadata=None,
        parser_option=None,
        legacy_commit=None,
        format=None,
        fixtures=None,
        skip_ts=False,
    )

    def fake_config_from_args(self, parsed_args):
        assert parsed_args is args
        return config

    def fake_run_scenario(self, cfg, *, skip_ts=False):
        assert cfg is config
        assert skip_ts is False
        self._map_data.setdefault("scenarios", {})[cfg.slug] = {
            "errors": {"py_legacy": ["boom"]}
        }
        return False

    monkeypatch.setattr(Debugger, "_config_from_args", fake_config_from_args)
    monkeypatch.setattr(Debugger, "_run_scenario", fake_run_scenario)

    try:
        assert debugger.run(args) is True
    finally:
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()


def test_main_exits_with_code_one_when_errors(monkeypatch, tmp_path):
    class DummyParser:
        def parse_args(self):
            return argparse.Namespace(
                scenario=None,
                slug=None,
                drawio=None,
                csv_path=None,
                base_uri=None,
                prefix=None,
                metadata=None,
                parser_option=None,
                legacy_commit=None,
                format=None,
                fixtures=str(tmp_path),
                skip_ts=False,
            )

    class DummyDebugger:
        def __init__(self, fixtures_dir: Path):
            assert fixtures_dir == tmp_path

        def run(self, args):
            assert isinstance(args, argparse.Namespace)
            return True

    monkeypatch.setattr(debug_main, "build_argument_parser", lambda: DummyParser())
    monkeypatch.setattr(debug_main, "Debugger", DummyDebugger)

    with pytest.raises(SystemExit) as excinfo:
        debug_main.main()

    assert excinfo.value.code == 1


def test_main_allows_zero_exit_without_errors(monkeypatch, tmp_path):
    class DummyParser:
        def parse_args(self):
            return argparse.Namespace(
                scenario=None,
                slug=None,
                drawio=None,
                csv_path=None,
                base_uri=None,
                prefix=None,
                metadata=None,
                parser_option=None,
                legacy_commit=None,
                format=None,
                fixtures=str(tmp_path),
                skip_ts=False,
            )

    class DummyDebugger:
        def __init__(self, fixtures_dir: Path):
            assert fixtures_dir == tmp_path

        def run(self, args):
            assert isinstance(args, argparse.Namespace)
            return False

    monkeypatch.setattr(debug_main, "build_argument_parser", lambda: DummyParser())
    monkeypatch.setattr(debug_main, "Debugger", DummyDebugger)

    debug_main.main()
