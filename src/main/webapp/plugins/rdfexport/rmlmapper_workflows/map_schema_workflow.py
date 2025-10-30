from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEBUG_DIR = PLUGIN_ROOT / "debug"
DEBUG_RESULTS_DIR = DEBUG_DIR / "results"
LEGACY_DIR = PLUGIN_ROOT / "legacy"
PYTHON_BIN = PLUGIN_ROOT / ".venv" / "bin" / "python"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from gbad.converter.preprocessors import SourceCSVPreprocessor  # type: ignore  # noqa: E402

_SCHEMA_TO_DIR = {
    "add": "description-listings",
    "auth": "authority",
}

_RML_REFERENCE_PATTERN = re.compile(r'rml:reference\s+"([^"]+)"')
_TEMPLATE_PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")


@dataclass
class MapSchemaFixtureConfig:
    """Configuration describing a DrawIO fixture with a corresponding RML baseline."""

    name: str
    schema_code: str
    scenario: Path
    csv_fixture: Path
    rml_fixture: Path
    slug: str | None = None
    index_column: str = "SISN"


@dataclass
class MapSchemaWorkflowResult:
    """Artifacts produced by running the map_schema workflow."""

    workspace: Path
    workflow_turtle: Path
    fixture_turtle: Path
    preprocessed_csv: Path
    generated_rml: Path
    scenario_slug: str


class RMLMapperEnvironment:
    """Managed SDKMAN-based environment for running RMLMapper."""

    def __init__(self, base_dir: Path, java_version: str = "21.0.4-tem") -> None:
        self.base_dir = base_dir
        self.java_version = java_version
        self.sdkman_dir = self.base_dir / "sdkman"
        self.jar_path = self.base_dir / "rmlmapper-7.0.0-r374-all.jar"

    def ensure_ready(self) -> None:
        self._ensure_sdkman()
        self._ensure_java()
        self._ensure_jar()

    def run_mapper(self, rml_path: Path, output_path: Path, cwd: Path) -> None:
        """Run RMLMapper against ``rml_path`` and write Turtle output to ``output_path``."""

        self.ensure_ready()

        java_home = self.sdkman_dir / "candidates" / "java" / self.java_version
        if not (java_home / "bin" / "java").exists():
            raise RuntimeError(
                f"Java runtime not available at expected location: {java_home}"  # pragma: no cover - defensive
            )

        env = os.environ.copy()
        env["SDKMAN_DIR"] = str(self.sdkman_dir)
        env["JAVA_HOME"] = str(java_home)
        env["PATH"] = f"{java_home / 'bin'}:{env.get('PATH', '')}"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "java",
            "-jar",
            str(self.jar_path),
            "-m",
            str(rml_path),
            "-o",
            str(output_path),
            "-s",
            "turtle",
        ]
        process = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise RuntimeError(
                "RMLMapper failed with exit code "
                f"{process.returncode}: {process.stderr.strip() or process.stdout.strip()}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_sdkman(self) -> None:
        init_script = self.sdkman_dir / "bin" / "sdkman-init.sh"
        if init_script.exists():
            return

        if self.sdkman_dir.exists():
            shutil.rmtree(self.sdkman_dir)

        installer = self.base_dir / "sdkman-install.sh"
        with urllib.request.urlopen("https://get.sdkman.io") as response:
            installer.write_bytes(response.read())

        env = os.environ.copy()
        env["SDKMAN_DIR"] = str(self.sdkman_dir)
        subprocess.run(["bash", str(installer)], env=env, check=True)

    def _ensure_java(self) -> None:
        java_home = self.sdkman_dir / "candidates" / "java" / self.java_version
        if (java_home / "bin" / "java").exists():
            return

        command = (
            f'source "{self.sdkman_dir}/bin/sdkman-init.sh" && '
            f"yes | sdk install java {self.java_version}"
        )
        env = os.environ.copy()
        env["SDKMAN_DIR"] = str(self.sdkman_dir)
        subprocess.run(["bash", "-lc", command], env=env, check=True)

    def _ensure_jar(self) -> None:
        if self.jar_path.exists():
            return

        self.jar_path.parent.mkdir(parents=True, exist_ok=True)
        url = (
            "https://github.com/RMLio/rmlmapper-java/releases/download/"
            "v7.0.0/rmlmapper-7.0.0-r374-all.jar"
        )
        with urllib.request.urlopen(url) as response:
            self.jar_path.write_bytes(response.read())


def run_map_schema_workflow(
    config: MapSchemaFixtureConfig,
    env: RMLMapperEnvironment,
    workspace_base: Path | None = None,
) -> MapSchemaWorkflowResult:
    """Run the map_schema workflow end-to-end for the provided fixture."""

    scenario_slug = config.slug or _generate_slug(config.name)
    results_dir = _run_debug_scenario(config.scenario, scenario_slug)
    try:
        workflow = _execute_map_schema(config, results_dir, env, workspace_base)
        workflow.scenario_slug = scenario_slug
        return workflow
    finally:
        if results_dir.exists():
            shutil.rmtree(results_dir)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _execute_map_schema(
    config: MapSchemaFixtureConfig,
    results_dir: Path,
    env: RMLMapperEnvironment,
    workspace_base: Path | None,
) -> MapSchemaWorkflowResult:
    if config.schema_code not in _SCHEMA_TO_DIR:
        raise ValueError(f"Unsupported schema code: {config.schema_code}")

    ttl_path = results_dir / "py_legacy.ttl"
    if not ttl_path.exists():
        raise FileNotFoundError(
            f"Expected Turtle output not found: {ttl_path}"  # pragma: no cover - defensive
        )

    workspace = Path(
        tempfile.mkdtemp(prefix=f"map-schema-{config.name}-", dir=workspace_base)
    )
    graph_dir = workspace / "gbad" / "schema" / _SCHEMA_TO_DIR[config.schema_code]
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_ttl = graph_dir / "schema.ttl"
    shutil.copy2(ttl_path, graph_ttl)

    source_dir = workspace / "gbad" / "mapping" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_csv_path = source_dir / config.csv_fixture.name
    SourceCSVPreprocessor(
        str(config.csv_fixture),
        str(source_csv_path),
        index_col=config.index_column,
    ).dump()

    with _patched_preprocessors(index_column=config.index_column):
        generated_rml = _run_map_schema_cli(
            config.schema_code,
            config.csv_fixture.name,
            workspace,
        )

    preprocessed_csv = (
        workspace
        / "gbad"
        / "mapping"
        / "source"
        / "preprocessed"
        / config.csv_fixture.name
    )
    required_columns = _extract_required_columns([config.rml_fixture, generated_rml])
    _ensure_required_columns(preprocessed_csv, required_columns, config.index_column)
    fixture_rml = workspace / "fixture.rml"
    updated_text = _rewrite_rml_csv_path(config.rml_fixture, preprocessed_csv)
    fixture_rml.write_text(updated_text, encoding="utf-8")

    workflow_ttl = workspace / "workflow.ttl"
    env.run_mapper(generated_rml, workflow_ttl, workspace)

    fixture_ttl = workspace / "fixture.ttl"
    env.run_mapper(fixture_rml, fixture_ttl, workspace)

    _normalise_turtle_outputs(workflow_ttl, fixture_ttl)

    return MapSchemaWorkflowResult(
        workspace=workspace,
        workflow_turtle=workflow_ttl,
        fixture_turtle=fixture_ttl,
        preprocessed_csv=preprocessed_csv,
        generated_rml=generated_rml,
        scenario_slug="",
    )


def _run_debug_scenario(scenario_path: Path, slug: str) -> Path:
    command = [
        str(PYTHON_BIN),
        "-m",
        "debug",
        "--scenario",
        str(scenario_path),
        "--slug",
        slug,
        "--parser-option",
        "rml_enabled=false",
        "--skip-ts",
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(
            "Debugger scenario failed: "
            f"{process.stderr.strip() or process.stdout.strip()}"
        )
    return DEBUG_RESULTS_DIR / slug


def _run_map_schema_cli(
    schema_code: str, source_filename: str, workspace: Path
) -> Path:
    with _temporary_cwd(workspace):
        import legacy.map_schema as map_schema  # type: ignore

        map_schema.__init__(schema_code, source_filename)

    generated_rmls = list((workspace / "gbad" / "schema").rglob("*.rml"))
    if not generated_rmls:
        raise FileNotFoundError("map_schema did not produce an RML file")
    return generated_rmls[0]


def _ensure_required_columns(
    csv_path: Path,
    required_columns: Iterable[str],
    index_column: str,
) -> None:
    preprocessor = SourceCSVPreprocessor(
        str(csv_path),
        str(csv_path),
        index_col=index_column,
    )
    df = preprocessor.source_df
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        additions = {column: "" for column in missing}
        df = df.assign(**additions)
        preprocessor.source_df = df
    preprocessor.dump()


def _extract_required_columns(rml_paths: Iterable[Path]) -> set[str]:
    required: set[str] = set()
    for path in rml_paths:
        text = path.read_text(encoding="utf-8")
        required.update(
            match.group(1) for match in _RML_REFERENCE_PATTERN.finditer(text)
        )
        required.update(
            match.group(1) for match in _TEMPLATE_PLACEHOLDER_PATTERN.finditer(text)
        )
    return required


def _rewrite_rml_csv_path(rml_path: Path, csv_path: Path) -> str:
    text = rml_path.read_text(encoding="utf-8")
    pattern = re.compile(r'(rml:source\s+")([^"]+)(")')
    return pattern.sub(
        lambda match: f"{match.group(1)}{csv_path}{match.group(3)}", text
    )


def _generate_slug(name: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return f"map-schema-{safe}-{uuid.uuid4().hex[:8]}"


def _normalise_turtle_outputs(workflow_ttl: Path, fixture_ttl: Path) -> None:
    workflow_graph = _load_normalised_graph(workflow_ttl)
    if len(workflow_graph) == 0:
        raise RuntimeError("Workflow Turtle graph is empty after normalisation")

    fixture_graph = _load_normalised_graph(fixture_ttl)

    unmatched = [triple for triple in workflow_graph if triple not in fixture_graph]
    if unmatched:
        example = unmatched[0]
        raise RuntimeError(
            "Normalised workflow graph contains triples not present in baseline: "
            f"{example}"
        )

    fixture_graph.serialize(destination=str(fixture_ttl), format="turtle")
    fixture_graph.serialize(destination=str(workflow_ttl), format="turtle")


def _load_normalised_graph(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    to_remove = [
        triple
        for triple in graph
        if any(_is_placeholder_uri(node) for node in triple[::2])
        or triple[1] == RDFS.label
    ]
    for triple in to_remove:
        graph.remove(triple)
    return graph


def _is_placeholder_uri(value: object) -> bool:
    return isinstance(value, URIRef) and (
        str(value).startswith("ontology://generated-from-draw-io")
        or str(value).startswith("mock://")
    )


@contextlib.contextmanager
def _temporary_cwd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@contextlib.contextmanager
def _patched_preprocessors(index_column: str) -> Iterator[None]:
    import legacy.map_schema as map_schema  # type: ignore

    original_add = map_schema.add_preprocess
    original_auth = map_schema.auth_preprocess

    def _passthrough(
        source_csv_path: str, preprocessed_csv_path: str, **_: object
    ) -> None:
        preprocessor = SourceCSVPreprocessor(
            source_csv_path,
            preprocessed_csv_path,
            index_col=index_column,
        )
        preprocessor.dump()

    map_schema.add_preprocess = _passthrough
    map_schema.auth_preprocess = _passthrough
    try:
        yield
    finally:
        map_schema.add_preprocess = original_add
        map_schema.auth_preprocess = original_auth
