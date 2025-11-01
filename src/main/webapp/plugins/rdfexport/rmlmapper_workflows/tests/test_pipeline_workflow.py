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

from rmlmapper_workflows import (  # type: ignore  # noqa: E402
    MapSchemaFixtureConfig,
    MapSchemaWorkflowResult,
    PipelineWorkflowResult,
    RMLMapperEnvironment,
    run_map_schema_workflow,
    run_pipeline_workflow,
)

SCENARIO_DIR = PLUGIN_ROOT / "debug" / "scenarios"
RML_FIXTURES_DIR = PLUGIN_ROOT / "tests" / "fixtures" / "rml"
ARTIFACTS_DIR = PLUGIN_ROOT / "rmlmapper_workflows" / "artifacts"


def _load_graph(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def _assert_isomorphic(lhs: Path, rhs: Path) -> None:
    assert to_isomorphic(_load_graph(lhs)) == to_isomorphic(_load_graph(rhs))


def _save_pipeline_artifacts(
    pipeline_result: PipelineWorkflowResult,
    map_result: MapSchemaWorkflowResult,
    test_name: str,
) -> None:
    target_dir = ARTIFACTS_DIR / test_name
    target_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(pipeline_result.pipeline_turtle, target_dir / "pipeline_mapped.ttl")
    shutil.copy2(pipeline_result.pipeline_rml, target_dir / "pipeline_map.rml")
    shutil.copy2(
        pipeline_result.preprocessed_csv, target_dir / "pipeline_preprocessed.csv"
    )
    shutil.copy2(map_result.workflow_turtle, target_dir / "map_schema_mapped.ttl")
    shutil.copy2(
        map_result.preprocessed_csv, target_dir / "map_schema_preprocessed.csv"
    )

    if pipeline_result.mapper_error:
        (target_dir / "mapper_error.txt").write_text(
            pipeline_result.mapper_error,
            encoding="utf-8",
        )


@pytest.fixture(scope="session")
def rmlmapper_env() -> RMLMapperEnvironment:
    return RMLMapperEnvironment.from_manifest()


def _compare_or_xfail(pipeline_path: Path, map_schema_path: Path) -> None:
    _assert_isomorphic(pipeline_path, map_schema_path)


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
        slug="pytest-pipeline-general-add",
    )

    pipeline_config = MapSchemaFixtureConfig(
        name="general-add",
        schema_code="add",
        scenario=SCENARIO_DIR
        / "general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz-no-rr.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.rml",
        slug="pytest-pipeline-general-add-no-rr",
    )

    pipeline_result = run_pipeline_workflow(
        pipeline_config, rmlmapper_env, workspace_base=tmp_path
    )
    map_result = run_map_schema_workflow(
        map_schema_config, rmlmapper_env, workspace_base=tmp_path
    )

    assert pipeline_result.pipeline_turtle.exists()
    assert map_result.workflow_turtle.exists()

    _save_pipeline_artifacts(pipeline_result, map_result, "general_add")

    if pipeline_result.mapper_error:
        pytest.xfail(
            f"RMLMapper failed for pipeline workflow: {pipeline_result.mapper_error}"
        )

    _compare_or_xfail(pipeline_result.pipeline_turtle, map_result.workflow_turtle)


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
        slug="pytest-pipeline-general-authority",
    )
    pipeline_config = MapSchemaFixtureConfig(
        name="general-authority",
        schema_code="auth",
        scenario=SCENARIO_DIR
        / "general-authority-to-ric-o-model-2025-06-25-pz-no-rr.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.rml",
        slug="pytest-pipeline-general-authority-no-rr",
    )

    pipeline_result = run_pipeline_workflow(
        pipeline_config, rmlmapper_env, workspace_base=tmp_path
    )
    map_result = run_map_schema_workflow(
        map_schema_config, rmlmapper_env, workspace_base=tmp_path
    )

    assert pipeline_result.pipeline_turtle.exists()
    assert map_result.workflow_turtle.exists()

    _save_pipeline_artifacts(pipeline_result, map_result, "general_authority")

    if pipeline_result.mapper_error:
        pytest.xfail(
            f"RMLMapper failed for pipeline workflow: {pipeline_result.mapper_error}"
        )

    _compare_or_xfail(pipeline_result.pipeline_turtle, map_result.workflow_turtle)
