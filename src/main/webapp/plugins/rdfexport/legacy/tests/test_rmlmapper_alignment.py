from __future__ import annotations

from pathlib import Path
import sys

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[2]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from legacy.tests import rmlmapper_workflows as workflows  # noqa: E402


EXPECTED_DIFFERENCES: dict[str, tuple[int, int]] = {
    "general-authority-to-ric-o-model-2025-06-25-pz": (0, 0),
    "general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz": (0, 0),
}


@pytest.fixture(scope="session")
def manifest() -> workflows.Manifest:
    return workflows.ensure_rmlmapper_setup()


@pytest.mark.parametrize("fixture", workflows.FIXTURES)
def test_rmlmapper_workflows_are_isomorphic(
    manifest: workflows.Manifest, tmp_path: Path, fixture: workflows.FixtureConfig
) -> None:
    map_schema_result = workflows.run_map_schema_workflow(
        fixture,
        manifest=manifest,
        csv_path=fixture.csv_path,
        output_dir=tmp_path / "map-schema",
    )

    pipeline_result = workflows.run_pipeline_workflow(
        fixture,
        manifest=manifest,
        drawio_path=fixture.drawio_path,
        csv_path=fixture.csv_path,
        output_dir=tmp_path / "pipeline",
        persist_results=False,
    )

    assert map_schema_result.turtle_path.exists()
    assert pipeline_result.turtle_path.exists()
    assert len(map_schema_result.turtle_graph) > 0
    assert len(pipeline_result.turtle_graph) > 0

    for workflow in (map_schema_result, pipeline_result):
        assert workflow.workspace_dir is not None
        artifacts_dir = workflow.workspace_dir / "artifacts"
        assert artifacts_dir.exists(), "workspace artifacts directory missing"
        assert (artifacts_dir / workflow.rml_path.name).exists(), (
            "canonical RML not copied to workspace"
        )
        assert (artifacts_dir / workflow.turtle_path.name).exists(), (
            "RMLMapper Turtle output not copied to workspace"
        )

    canonical = workflows.canonicalize_for_comparison(
        map_schema_result.turtle_graph, pipeline_result.turtle_graph
    )

    expected_map_only, expected_pipeline_only = EXPECTED_DIFFERENCES[fixture.slug]

    if (
        canonical.map_only_count != expected_map_only
        or canonical.pipeline_only_count != expected_pipeline_only
    ):
        diagnostics = canonical.format_differences()
        pytest.fail(
            "Canonicalised workflow projections diverged:\n"
            f"Expected map_schema-only count {expected_map_only}, observed {canonical.map_only_count}.\n"
            f"Expected pipeline-only count {expected_pipeline_only}, observed {canonical.pipeline_only_count}.\n"
            f"{diagnostics}"
        )

    if not workflows.graphs_are_isomorphic(
        map_schema_result.turtle_graph, pipeline_result.turtle_graph
    ):
        diagnostics = canonical.format_differences()
        pytest.fail(
            "RMLMapper Turtle outputs are not isomorphic despite canonical agreement:\n"
            f"{diagnostics}"
        )

    assert workflows.graphs_are_isomorphic(
        canonical.map_graph, canonical.pipeline_graph
    )
