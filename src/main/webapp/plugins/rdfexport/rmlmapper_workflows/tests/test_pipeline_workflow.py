from __future__ import annotations

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
    PipelineFixtureConfig,
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


def _save_artifacts(slug: str, pipeline_path: Path, map_schema_path: Path) -> None:
    destination = ARTIFACTS_DIR / slug
    destination.mkdir(parents=True, exist_ok=True)

    import shutil

    shutil.copy2(pipeline_path, destination / "pipeline_output.ttl")
    shutil.copy2(map_schema_path, destination / "map_schema_output.ttl")


@pytest.fixture(scope="session")
def rmlmapper_env() -> RMLMapperEnvironment:
    return RMLMapperEnvironment.from_manifest()


@pytest.mark.xfail(reason="Pipeline workflow alignment pending", strict=False)
def test_pipeline_workflow_general_add(
    rmlmapper_env: RMLMapperEnvironment, tmp_path: Path
) -> None:
    pipeline_config = PipelineFixtureConfig(
        name="general-add",
        scenario=SCENARIO_DIR
        / "general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.csv",
        schema_code="add",
        slug="pytest-pipeline-general-add",
    )
    pipeline_result = run_pipeline_workflow(pipeline_config, rmlmapper_env, tmp_path)

    map_config = MapSchemaFixtureConfig(
        name="general-add",
        schema_code="add",
        scenario=SCENARIO_DIR
        / "general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.rml",
        slug="pytest-map-schema-general-add-pipeline",
    )
    map_result = run_map_schema_workflow(
        map_config, rmlmapper_env, workspace_base=tmp_path
    )

    _save_artifacts(
        "pipeline_general_add",
        pipeline_result.workflow_turtle,
        map_result.workflow_turtle,
    )

    _assert_isomorphic(pipeline_result.workflow_turtle, map_result.workflow_turtle)


@pytest.mark.xfail(reason="Pipeline workflow alignment pending", strict=False)
def test_pipeline_workflow_general_authority(
    rmlmapper_env: RMLMapperEnvironment, tmp_path: Path
) -> None:
    pipeline_config = PipelineFixtureConfig(
        name="general-authority",
        scenario=SCENARIO_DIR / "general-authority-to-ric-o-model-2025-06-25-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.csv",
        schema_code="auth",
        slug="pytest-pipeline-general-authority",
    )
    pipeline_result = run_pipeline_workflow(pipeline_config, rmlmapper_env, tmp_path)

    map_config = MapSchemaFixtureConfig(
        name="general-authority",
        schema_code="auth",
        scenario=SCENARIO_DIR / "general-authority-to-ric-o-model-2025-06-25-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.rml",
        slug="pytest-map-schema-general-authority-pipeline",
    )
    map_result = run_map_schema_workflow(
        map_config, rmlmapper_env, workspace_base=tmp_path
    )

    _save_artifacts(
        "pipeline_general_authority",
        pipeline_result.workflow_turtle,
        map_result.workflow_turtle,
    )

    _assert_isomorphic(pipeline_result.workflow_turtle, map_result.workflow_turtle)
