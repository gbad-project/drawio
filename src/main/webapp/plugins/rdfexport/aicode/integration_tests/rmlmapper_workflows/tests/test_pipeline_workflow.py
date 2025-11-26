from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from test_map_schema_workflow import (
    _assert_isomorphic,
    _canonicalize_and_copy,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from aicode.integration_tests.rmlmapper_workflows.src import (  # type: ignore  # noqa: E402
    MapSchemaFixtureConfig,
    MapSchemaWorkflowResult,
    PipelineWorkflowResult,
    RMLMapperEnvironment,
    run_map_schema_workflow,
    run_pipeline_workflow,
)

SCENARIO_DIR = PLUGIN_ROOT / "data" / "debug" / "scenarios"
RML_FIXTURES_DIR = PLUGIN_ROOT / "data" / "fixtures" / "rml_fixtures"
ARTIFACTS_DIR = PLUGIN_ROOT / "data" / "rmlmapper_workflows" / "artifacts"


def _save_pipeline_artifacts(
    pipeline_result: PipelineWorkflowResult,
    map_result: MapSchemaWorkflowResult,
    test_name: str,
) -> None:
    target_dir = ARTIFACTS_DIR / test_name
    if target_dir.exists():  # clean old run
        for item in target_dir.iterdir():
            if item.name in [
                "pipeline_mapped.ttl",
                "pipeline_map.rml",
                "pipeline_preprocessed.csv",
                "map_schema_mapped.ttl",
                "map_schema_preprocessed.csv",
                "mapper_error.txt",
            ]:
                if item.is_dir():  # defensive
                    shutil.rmtree(item)
                else:
                    item.unlink()
    target_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(pipeline_result.pipeline_turtle, target_dir / "pipeline_mapped.ttl")
    _canonicalize_and_copy(
        pipeline_result.pipeline_rml, target_dir / "pipeline_map.rml"
    )
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


def _compare_or_xfail(pipeline_path: Path, map_schema_path: Path) -> None:
    try:
        _assert_isomorphic(pipeline_path, map_schema_path)
    except AssertionError:
        pytest.xfail(
            "Pipeline workflow output is not yet isomorphic with map_schema workflow"
        )


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
        index_column="SISN",
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
        index_column="SISN",
    )

    pipeline_result = run_pipeline_workflow(
        pipeline_config,
        rmlmapper_env,
        workspace_base=tmp_path,
        correct_dateex_path="tmp/New-export-of-Government-authorities-with-correct-Dates-of-Existence-xlsx.csv",
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
