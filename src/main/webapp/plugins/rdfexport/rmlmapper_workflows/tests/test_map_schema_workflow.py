from __future__ import annotations

from pathlib import Path
import sys

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
    MapSchemaWorkflowResult,
)

SCENARIO_DIR = PLUGIN_ROOT / "debug" / "scenarios"
RML_FIXTURES_DIR = PLUGIN_ROOT / "tests" / "fixtures" / "rml"


@pytest.fixture(scope="session")
def rmlmapper_env() -> RMLMapperEnvironment:
    """Provide a session-scoped RMLMapper environment using the manifest."""
    return RMLMapperEnvironment.from_manifest()


def _load_graph(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def _assert_isomorphic(lhs: Path, rhs: Path) -> None:
    left_graph = _load_graph(lhs)
    right_graph = _load_graph(rhs)
    assert to_isomorphic(left_graph) == to_isomorphic(right_graph)


def _save_comparison_artifacts(result: MapSchemaWorkflowResult, test_name: str) -> None:
    """Save workflow and fixture turtle files to artifacts directory for comparison."""
    artifacts_dir = PLUGIN_ROOT / "rmlmapper_workflows" / "artifacts" / test_name
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    import shutil

    shutil.copy2(result.workflow_turtle, artifacts_dir / "map_schema_mapped.ttl")
    shutil.copy2(result.fixture_turtle, artifacts_dir / "fixture_mapped.ttl")
    shutil.copy2(result.preprocessed_csv, artifacts_dir / "map_schema_preprocessed.csv")
    shutil.copy2(result.generated_rml, artifacts_dir / "map_schema_map.rml")

    # Copy the schema.ttl from the workspace
    schema_files = list(result.workspace.glob("gbad/schema/*/schema.ttl"))
    if schema_files:
        shutil.copy2(schema_files[0], artifacts_dir / "pipeline_schema.ttl")


def test_map_schema_workflow_general_add(
    rmlmapper_env: RMLMapperEnvironment, tmp_path: Path
) -> None:
    config = MapSchemaFixtureConfig(
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
    result = run_map_schema_workflow(config, rmlmapper_env, workspace_base=tmp_path)
    assert result.workflow_turtle.exists()
    assert result.fixture_turtle.exists()
    _save_comparison_artifacts(result, "general_add")
    _assert_isomorphic(result.workflow_turtle, result.fixture_turtle)


def test_map_schema_workflow_general_authority(
    rmlmapper_env: RMLMapperEnvironment, tmp_path: Path
) -> None:
    config = MapSchemaFixtureConfig(
        name="general-authority",
        schema_code="auth",
        scenario=SCENARIO_DIR / "general-authority-to-ric-o-model-2025-06-25-pz.yml",
        csv_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.csv",
        rml_fixture=RML_FIXTURES_DIR
        / "General Authority to RiC-O Model_2025-06-25_PZ.rml",
        slug="pytest-map-schema-general-authority",
    )
    result = run_map_schema_workflow(config, rmlmapper_env, workspace_base=tmp_path)
    assert result.workflow_turtle.exists()
    assert result.fixture_turtle.exists()
    _save_comparison_artifacts(result, "general_authority")
    _assert_isomorphic(result.workflow_turtle, result.fixture_turtle)
