from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from rdflib import Graph

PLUGIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PLUGIN_DIR.parents[4]
for candidate in (REPO_ROOT, PLUGIN_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from debug.__main__ import (  # noqa: E402
    DEFAULT_BASE_URI,
    DEFAULT_CSV_PATH,
    DEFAULT_LEGACY_COMMIT,
    DEFAULT_PREFIXES,
    Debugger,
    ScenarioConfig,
)

FIXTURES_DIR = PLUGIN_DIR / "tests" / "fixtures"


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

    config = ScenarioConfig(
        slug=slug,
        drawio_path=drawio_path,
        csv_path=DEFAULT_CSV_PATH,
        base_uri=DEFAULT_BASE_URI,
        prefixes=list(DEFAULT_PREFIXES),
        legacy_commit=DEFAULT_LEGACY_COMMIT,
        serialization_format="nt",
    )

    results_dir = debugger.results_dir / slug
    try:
        debugger._run_scenario(config)

        assert results_dir.exists()
        outputs = {
            name: results_dir / f"{name}.nt" for name in ("legacy", "current", "plugin")
        }
        for path in outputs.values():
            assert path.exists()
            content = path.read_text(encoding="utf-8").strip()
            assert content

        map_data = json.loads(debugger.map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"][slug]

        for key in ("legacy", "current", "plugin"):
            result_info = scenario_entry["results"][key]
            assert Path(result_info["path"]).name == f"{key}.nt"
            assert result_info["triples"] > 0
            assert len(result_info["nt_sha256"]) == 64

        assert scenario_entry["isomorphism"]["current_vs_plugin"] is True

    finally:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()


def test_outputs_are_isomorphic_across_sources():
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / "AA37 Department of Health.drawio"

    config = ScenarioConfig(
        slug=slug,
        drawio_path=drawio_path,
        csv_path=DEFAULT_CSV_PATH,
        base_uri=DEFAULT_BASE_URI,
        prefixes=list(DEFAULT_PREFIXES),
        legacy_commit=DEFAULT_LEGACY_COMMIT,
        serialization_format="nt",
    )

    results_dir = debugger.results_dir / slug
    try:
        debugger._run_scenario(config)
        legacy_graph = Graph().parse(
            data=(results_dir / "legacy.nt").read_text(encoding="utf-8"),
            format="nt",
        )
        current_graph = Graph().parse(
            data=(results_dir / "current.nt").read_text(encoding="utf-8"),
            format="nt",
        )
        plugin_graph = Graph().parse(
            data=(results_dir / "plugin.nt").read_text(encoding="utf-8"),
            format="nt",
        )

        assert len(legacy_graph) > 0
        assert len(current_graph) == len(plugin_graph) > 0

        plugin_matches_pipeline = current_graph.isomorphic(plugin_graph)

        map_data = json.loads(debugger.map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"][slug]
        assert (
            scenario_entry["isomorphism"]["current_vs_plugin"]
            is plugin_matches_pipeline
        )

    finally:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()
