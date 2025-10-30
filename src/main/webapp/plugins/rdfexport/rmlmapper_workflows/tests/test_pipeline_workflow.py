"""Tests for the draw.io pipeline-based RML workflow."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import to_isomorphic

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from rmlmapper_workflows import (  # noqa: E402
    MapSchemaFixtureConfig,
    RMLMapperEnvironment,
    run_map_schema_workflow,
)
from rmlmapper_workflows.pipeline_workflow import (  # noqa: E402
    PipelineFixtureConfig,
    PipelineWorkflowResult,
    run_pipeline_workflow,
)

SCENARIO_DIR = PLUGIN_ROOT / "debug" / "scenarios"
FIXTURES_DIR = PLUGIN_ROOT / "tests" / "fixtures"
RML_FIXTURES_DIR = FIXTURES_DIR / "rml"


@pytest.fixture(scope="session")
def rmlmapper_env() -> RMLMapperEnvironment:
    """Provide a shared RMLMapper environment for the pipeline tests."""

    return RMLMapperEnvironment.from_manifest()


def _load_graph(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def _assert_isomorphic(lhs: Path, rhs: Path) -> None:
    left_graph = _load_graph(lhs)
    right_graph = _load_graph(rhs)
    assert to_isomorphic(left_graph) == to_isomorphic(right_graph)


def _save_pipeline_artifacts(
    pipeline: PipelineWorkflowResult,
    map_schema_result,
    test_name: str,
) -> None:
    artifacts_dir = (
        PLUGIN_ROOT / "rmlmapper_workflows" / "artifacts" / "pipeline" / test_name
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(pipeline.pipeline_turtle, artifacts_dir / "pipeline.ttl")
    shutil.copy2(map_schema_result.workflow_turtle, artifacts_dir / "map_schema.ttl")
    shutil.copy2(pipeline.preprocessed_csv, artifacts_dir / "preprocessed.csv")
    shutil.copy2(pipeline.generated_rml, artifacts_dir / "pipeline.rml")

    if pipeline.debug_results and pipeline.debug_results.exists():
        debug_dest = artifacts_dir / "debug-results"
        if debug_dest.exists():
            shutil.rmtree(debug_dest)
        shutil.copytree(pipeline.debug_results, debug_dest)


@pytest.mark.xfail(reason="Pipeline RML alignment pending", strict=False)
def test_pipeline_workflow_general_add(
    rmlmapper_env: RMLMapperEnvironment, tmp_path: Path
) -> None:
    map_schema_config = MapSchemaFixtureConfig(
        name="general-add",
        schema_code="add",
        scenario=SCENARIO_DIR
        / "general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.rml",
        slug="pytest-map-schema-general-add",
    )
    map_schema_result = run_map_schema_workflow(
        map_schema_config, rmlmapper_env, workspace_base=tmp_path
    )

    pipeline_config = PipelineFixtureConfig(
        name="general-add",
        scenario=map_schema_config.scenario,
        drawio_fixture=FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.drawio",
        csv_fixture=map_schema_config.csv_fixture,
        slug="pytest-pipeline-general-add",
        index_column=map_schema_config.index_column,
    )
    pipeline_result = run_pipeline_workflow(
        pipeline_config, rmlmapper_env, workspace_base=tmp_path
    )

    _save_pipeline_artifacts(pipeline_result, map_schema_result, "general_add")
    _assert_isomorphic(
        pipeline_result.pipeline_turtle, map_schema_result.workflow_turtle
    )


@pytest.mark.xfail(reason="Pipeline RML alignment pending", strict=False)
def test_pipeline_workflow_general_authority(
    rmlmapper_env: RMLMapperEnvironment, tmp_path: Path
) -> None:
    map_schema_config = MapSchemaFixtureConfig(
        name="general-authority",
        schema_code="auth",
        scenario=SCENARIO_DIR / "general-authority-to-ric-o-model-2025-06-25-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.rml",
        slug="pytest-map-schema-general-authority",
    )
    map_schema_result = run_map_schema_workflow(
        map_schema_config, rmlmapper_env, workspace_base=tmp_path
    )

    pipeline_config = PipelineFixtureConfig(
        name="general-authority",
        scenario=map_schema_config.scenario,
        drawio_fixture=FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.drawio",
        csv_fixture=map_schema_config.csv_fixture,
        slug="pytest-pipeline-general-authority",
        index_column=map_schema_config.index_column,
    )
    pipeline_result = run_pipeline_workflow(
        pipeline_config, rmlmapper_env, workspace_base=tmp_path
    )

    _save_pipeline_artifacts(pipeline_result, map_schema_result, "general_authority")
    _assert_isomorphic(
        pipeline_result.pipeline_turtle, map_schema_result.workflow_turtle
    )
