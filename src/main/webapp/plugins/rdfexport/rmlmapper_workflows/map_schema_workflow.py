from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator
from io import StringIO
from contextlib import redirect_stdout

from rdflib import Graph

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEBUG_DIR = PLUGIN_ROOT / "debug"
DEBUG_RESULTS_DIR = DEBUG_DIR / "results"
LEGACY_DIR = PLUGIN_ROOT / "legacy"
PYTHON_BIN = PLUGIN_ROOT / ".venv" / "bin" / "python"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from legacy.gbad.converter.preprocessors import SourceCSVPreprocessor  # type: ignore  # noqa: E402

_SCHEMA_TO_DIR = {
    "add": "description-listings",
    "auth": "authority",
}

_PLACEHOLDER_BASE = "ontology://generated-from-draw-io/mock#"
_MAPPING_BASE = "https://data.archives.gov.on.test.gbad.ca/Schema/Mapping#"

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


@dataclass
class RMLMapperEnvironment:
    """Managed environment for running RMLMapper via manifest configuration."""

    manifest_path: Path

    @classmethod
    def from_manifest(cls, manifest_path: Path | None = None) -> RMLMapperEnvironment:
        """Create environment from manifest, running setup script if needed."""
        if manifest_path is None:
            manifest_path = PLUGIN_ROOT / "rmlmapper" / "manifest.json"

        env = cls(manifest_path=manifest_path)
        env.ensure_ready()
        return env

    def ensure_ready(self) -> None:
        """Ensure the RMLMapper environment is set up by running the setup script."""
        if not self.manifest_path.exists():
            self._run_setup_script()

        if not self.manifest_path.exists():
            raise RuntimeError(
                f"Setup script completed but manifest not found at {self.manifest_path}"
            )

    def run_mapper(self, rml_path: Path, output_path: Path, cwd: Path) -> None:
        """Run RMLMapper against ``rml_path`` and write Turtle output to ``output_path``."""
        import json

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

        java_bin = Path(manifest["java_bin"])
        if not java_bin.exists():
            raise RuntimeError(f"Java binary not found at: {java_bin}")

        jar_path = Path(manifest["rmlmapper_jar"])
        if not jar_path.exists():
            raise RuntimeError(f"RMLMapper JAR not found at: {jar_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["JAVA_HOME"] = manifest["java_home"]
        env["PATH"] = f"{Path(manifest['java_home']) / 'bin'}:{env.get('PATH', '')}"

        command = [
            str(java_bin),
            "-jar",
            str(jar_path),
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

    def _run_setup_script(self) -> None:
        """Execute the setup-rmlmapper.sh script."""
        setup_script = PLUGIN_ROOT / "scripts" / "setup_rmlmapper.sh"

        if not setup_script.exists():
            raise FileNotFoundError(f"Setup script not found at: {setup_script}")

        process = subprocess.run(
            ["bash", str(setup_script)],
            capture_output=True,
            text=True,
            cwd=str(PLUGIN_ROOT),
        )

        if process.returncode != 0:
            raise RuntimeError(
                f"RMLMapper setup script failed: {process.stderr.strip() or process.stdout.strip()}"
            )


def run_map_schema_workflow(
    config: MapSchemaFixtureConfig,
    env: RMLMapperEnvironment | None = None,
    workspace_base: Path | None = None,
) -> MapSchemaWorkflowResult:
    """Run the map_schema workflow end-to-end for the provided fixture."""

    if env is None:
        env = RMLMapperEnvironment.from_manifest()

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
    _retarget_schema_base(graph_ttl)

    source_dir = workspace / "gbad" / "mapping" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_csv_path = source_dir / config.csv_fixture.name
    buf = StringIO()
    with redirect_stdout(buf):
        SourceCSVPreprocessor(
            str(config.csv_fixture),
            str(source_csv_path),
            index_col=config.index_column,
        ).dump()
    output = buf.getvalue()

    with _patched_preprocessors(index_column=config.index_column):
        generated_rml = _run_map_schema_cli(
            config.schema_code,
            config.csv_fixture.name,
            workspace,
        )
    _rewrite_rml_labels(generated_rml)

    preprocessed_csv = (
        workspace
        / "gbad"
        / "mapping"
        / "source"
        / "preprocessed"
        / config.csv_fixture.name
    )
    required_columns = _extract_required_columns([config.rml_fixture, generated_rml])
    ### DON'T YOU DARE UNCOMMENT THIS ###
    #_ensure_required_columns(preprocessed_csv, required_columns, config.index_column)
    ### DO NOT UNCOMMENT. THIS IS A HALL OF SHAME AND LIES ###
    fixture_rml = workspace / "fixture.rml"
    updated_text = _rewrite_rml_csv_path(config.rml_fixture, preprocessed_csv)
    fixture_rml.write_text(updated_text, encoding="utf-8")

    workflow_ttl = workspace / "workflow.ttl"
    env.run_mapper(generated_rml, workflow_ttl, workspace)

    fixture_ttl = workspace / "fixture.ttl"
    env.run_mapper(fixture_rml, fixture_ttl, workspace)

    _canonicalise_turtle_outputs(workflow_ttl, fixture_ttl)

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

        buf = StringIO()
        with redirect_stdout(buf):
            map_schema.__init__(schema_code, source_filename)
        output = buf.getvalue()

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
    buf = StringIO()
    with redirect_stdout(buf):
        preprocessor.dump()
    output = buf.getvalue()


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


def _canonicalise_turtle_outputs(*paths: Path) -> None:
    for path in paths:
        graph = Graph()
        graph.parse(path, format="turtle")
        if len(graph) == 0:
            raise RuntimeError(
                f"Turtle graph produced at {path} is empty"  # pragma: no cover - defensive
            )
        graph.serialize(destination=str(path), format="turtle")


def _retarget_schema_base(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if _PLACEHOLDER_BASE not in text:
        return

    updated = text.replace(_PLACEHOLDER_BASE, _MAPPING_BASE)
    updated = updated.replace("Rr%3A", "rr%3A").replace("Rml%3A", "rml%3A")

    if "@prefix maps:" not in updated:
        lines = updated.splitlines()
        insertion_index = 0
        for index, line in enumerate(lines):
            if line.startswith("@prefix"):
                insertion_index = index + 1
        prefix_line = f"@prefix maps: <{_MAPPING_BASE}> ."
        lines.insert(insertion_index, prefix_line)
        updated = "\n".join(lines)

    path.write_text(updated, encoding="utf-8")


def _rewrite_rml_labels(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    def _replace(match: re.Match[str]) -> str:
        iri = match.group(2)
        humanised = _humanise_label_from_iri(iri)
        if humanised is None:
            return match.group(0)
        return f"{match.group(1)}{humanised}{match.group(3)}"

    pattern = re.compile(
        r'(rr:constant\s+")(https://data\.archives\.gov\.on\.test\.gbad\.ca/[^"\s]+)(")'
    )
    updated = pattern.sub(_replace, text)
    path.write_text(updated, encoding="utf-8")


def _humanise_label_from_iri(iri: str) -> str | None:
    parsed = urllib.parse.urlparse(iri)
    if not parsed.scheme:
        return None

    candidate = urllib.parse.unquote(parsed.fragment or parsed.path.rsplit("/", 1)[-1])
    if not candidate:
        return None

    if candidate[0].islower():
        return None

    cleaned = candidate.replace("_", " ").replace("-", " ")
    humanised = re.sub(r"(?<!^)(?=[A-Z])", " ", cleaned).strip()
    if not humanised:
        return None

    words = humanised.split()
    if len(words) > 1:
        lower_words = {"and", "or", "for", "of", "in", "on", "to", "the", "a", "an"}
        adjusted = [words[0]]
        for word in words[1:]:
            adjusted.append(word.lower() if word.lower() in lower_words else word)
        humanised = " ".join(adjusted)

    return humanised


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
        buf = StringIO()
        with redirect_stdout(buf):
            preprocessor.dump()
        output = buf.getvalue()

    map_schema.add_preprocess = _passthrough
    map_schema.auth_preprocess = _passthrough
    try:
        yield
    finally:
        map_schema.add_preprocess = original_add
        map_schema.auth_preprocess = original_auth
