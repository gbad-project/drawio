from __future__ import annotations

from pathlib import Path
import sys

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[2]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from legacy.tests import rmlmapper_workflows as workflows  # noqa: E402


EXPECTED_DIFFERENCES: dict[str, tuple[int, int]] = {
    "general-authority-to-ric-o-model-2025-06-25-pz": (8, 1),
    "general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz": (10, 5),
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
        csv_path=fixture.normalized_csv_path,
        output_dir=tmp_path / "map-schema",
    )

    pipeline_result = workflows.run_pipeline_workflow(
        fixture,
        manifest=manifest,
        drawio_path=fixture.normalized_drawio_path,
        csv_path=fixture.normalized_csv_path,
        output_dir=tmp_path / "pipeline",
        persist_results=False,
    )

    assert len(map_schema_result.turtle_graph) > 0
    assert len(pipeline_result.turtle_graph) > 0

    canonical = workflows.canonicalize_for_comparison(
        map_schema_result.turtle_graph, pipeline_result.turtle_graph
    )

    expected_map_only, expected_pipeline_only = EXPECTED_DIFFERENCES[fixture.slug]

    assert canonical.map_only_count == expected_map_only
    assert canonical.pipeline_only_count == expected_pipeline_only

    assert len(canonical.map_graph) == len(canonical.shared_graph) + expected_map_only
    assert (
        len(canonical.pipeline_graph)
        == len(canonical.shared_graph) + expected_pipeline_only
    )

    expected_isomorphic = expected_map_only == 0 and expected_pipeline_only == 0
    assert (
        workflows.graphs_are_isomorphic(canonical.map_graph, canonical.pipeline_graph)
        == expected_isomorphic
    )

    assert len(canonical.shared_graph) > 0
