"""Pipeline-based workflow for producing RMLMapper artifacts."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

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
from legacy import map_schema  # type: ignore  # noqa: E402

from .map_schema_workflow import RMLMapperEnvironment  # noqa: E402

_RICO_AUTHTP_DICT: dict[str, tuple[str, str]] = {
    key: (value, pattern[1:-1])
    for key, (value, pattern) in map_schema.rico_authtp_dict.items()
}

_INCREMENTED_COLUMN_PATTERN = re.compile(
    r"^(?P<prefix>.+?)_(?P<num>\d+)(?P<suffix>(?:_.+)?)$"
)


@dataclass
class PipelineFixtureConfig:
    """Configuration for running the pipeline workflow against a fixture."""

    name: str
    scenario: Path
    csv_fixture: Path
    schema_code: str
    slug: str | None = None
    index_column: str | bool = "SISN"


@dataclass
class PipelineWorkflowResult:
    """Artifacts produced by the pipeline workflow."""

    workspace: Path
    generated_rml: Path
    preprocessed_csv: Path
    workflow_turtle: Path
    scenario_slug: str
    pipeline_turtle: Path


class NormalisedCSVPreprocessor(SourceCSVPreprocessor):
    """CSV preprocessor that normalises incremented columns and adds RiC-O hints."""

    def __init__(
        self,
        source_csv_path: str,
        preprocessed_csv_path: str,
        index_col: str | bool = False,
    ) -> None:
        super().__init__(source_csv_path, preprocessed_csv_path, index_col=index_col)

    def run(self) -> None:
        self._normalise_increment_columns()
        self._add_rico_authtp_column()

    def _normalise_increment_columns(self) -> None:
        df = self.source_df.copy()
        index_name = df.index.name
        if index_name is not None:
            df = df.reset_index()

        grouped: dict[str, dict[int, str]] = {}
        for column in df.columns:
            match = _INCREMENTED_COLUMN_PATTERN.match(column)
            if not match:
                continue
            base = match.group("prefix") + (match.group("suffix") or "")
            num = int(match.group("num"))
            grouped.setdefault(base, {})[num] = column

        if not grouped:
            self.source_df = df.set_index(index_name) if index_name is not None else df
            return

        static_columns = [
            column
            for column in df.columns
            if not _INCREMENTED_COLUMN_PATTERN.match(column)
        ]

        # Ensure base columns exist in static data for consistent ordering
        base_columns = sorted(grouped.keys())
        normalised_rows: list[dict[str, object]] = []

        for _, row in df.iterrows():
            base_row = {column: row[column] for column in static_columns}
            increments: set[int] = set()
            for mapping in grouped.values():
                for num, column in mapping.items():
                    value = row[column]
                    if pd.notna(value) and f"{value}".strip():
                        increments.add(num)

            if not increments:
                new_row = dict(base_row)
                new_row["INCREMENT_NUMBER"] = None
                for base_column in base_columns:
                    new_row[base_column] = None
                normalised_rows.append(new_row)
                continue

            for increment in sorted(increments):
                new_row = dict(base_row)
                new_row["INCREMENT_NUMBER"] = increment
                for base_column in base_columns:
                    source_column = grouped[base_column].get(increment)
                    value = row[source_column] if source_column is not None else None
                    if pd.isna(value):
                        value = None
                    new_row[base_column] = value
                normalised_rows.append(new_row)

        normalised_df = pd.DataFrame(normalised_rows)
        if index_name is not None and index_name in normalised_df.columns:
            normalised_df = normalised_df.set_index(index_name)
        self.source_df = normalised_df

    def _add_rico_authtp_column(self) -> None:
        if "AUTHTP" not in self.source_df.columns:
            return

        def _resolve(value: object) -> object:
            if pd.isna(value) or value is None:
                return None
            text = str(value)
            for mapped_value, pattern in _RICO_AUTHTP_DICT.values():
                if re.search(pattern, text):
                    return mapped_value
            return None

        self.source_df["RICO_AUTHTP"] = self.source_df["AUTHTP"].map(_resolve)


def run_pipeline_workflow(
    config: PipelineFixtureConfig,
    env: RMLMapperEnvironment | None = None,
    workspace_base: Path | None = None,
) -> PipelineWorkflowResult:
    """Execute the pipeline workflow for a fixture."""

    if env is None:
        env = RMLMapperEnvironment.from_manifest()

    scenario_slug = config.slug or _generate_slug(config.name)
    scenario_path = _prepare_rml_enabled_scenario(config.scenario, scenario_slug)
    results_dir = _run_debug_scenario(scenario_path, scenario_slug)

    try:
        workspace = _prepare_workspace(config.name, workspace_base)
        pipeline_ttl = results_dir / "ts_pipeline.ttl"
        if not pipeline_ttl.exists():
            raise FileNotFoundError(
                f"Pipeline scenario did not produce expected output: {pipeline_ttl}"
            )

        preprocessed_csv = (
            workspace / "preprocessed" / f"{config.name}-preprocessed.csv"
        )
        preprocessed_csv.parent.mkdir(parents=True, exist_ok=True)
        preprocessor = NormalisedCSVPreprocessor(
            str(config.csv_fixture),
            str(preprocessed_csv),
            index_col=config.index_column,
        )
        preprocessor.run()
        preprocessor.dump()

        pipeline_copy = workspace / "pipeline-ts-output.ttl"
        shutil.copy2(pipeline_ttl, pipeline_copy)

        generated_rml = workspace / "pipeline-map.rml.ttl"
        _prepare_rml_artifact(pipeline_copy, generated_rml, preprocessed_csv)

        workflow_turtle = workspace / "pipeline-output.ttl"
        env.run_mapper(generated_rml, workflow_turtle, workspace)

        return PipelineWorkflowResult(
            workspace=workspace,
            generated_rml=generated_rml,
            preprocessed_csv=preprocessed_csv,
            workflow_turtle=workflow_turtle,
            scenario_slug=scenario_slug,
            pipeline_turtle=pipeline_copy,
        )
    finally:
        _cleanup_results_dir(results_dir)
        _cleanup_file(scenario_path)


def _prepare_workspace(name: str, workspace_base: Path | None) -> Path:
    base = workspace_base or Path(tempfile.mkdtemp(prefix="pipeline-workflow-"))
    if workspace_base is None:
        return base
    workspace = workspace_base / f"pipeline-{_slugify(name)}"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _prepare_rml_artifact(
    pipeline_ttl: Path, generated_rml: Path, csv_path: Path
) -> None:
    generated_rml.write_text(
        _rewrite_rml_csv_path(pipeline_ttl.read_text(encoding="utf-8"), csv_path),
        encoding="utf-8",
    )


def _rewrite_rml_csv_path(content: str, csv_path: Path) -> str:
    pattern = re.compile(r'(rml:source\s+")([^\"]+)(")')
    return pattern.sub(
        lambda match: f"{match.group(1)}{csv_path}{match.group(3)}",
        content,
    )


def _cleanup_results_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _cleanup_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def _generate_slug(name: str) -> str:
    return f"pipeline-{_slugify(name)}-{next(_slug_counter)}"


def _slugify(value: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", value.lower())
    return re.sub(r"-+", "-", safe).strip("-")


def _prepare_rml_enabled_scenario(original: Path, slug: str) -> Path:
    data = yaml.safe_load(original.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Scenario YAML must define a mapping")

    parser_config = data.setdefault("parser_config", {})
    if not isinstance(parser_config, dict):
        raise ValueError("Scenario parser_config must be a mapping")
    parser_config["rml_enabled"] = True

    metadata = data.setdefault("metadata", {})
    if isinstance(metadata, dict):
        attributes = metadata.setdefault("attributes", {})
        if isinstance(attributes, dict):
            attributes["rmlEnabled"] = True

    scenario_copy = DEBUG_DIR / "scenarios" / f"{slug}-rml.yml"
    scenario_copy.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return scenario_copy


def _run_debug_scenario(scenario_path: Path, slug: str) -> Path:
    command = [
        str(PYTHON_BIN),
        "-m",
        "debug",
        "--scenario",
        str(scenario_path),
        "--slug",
        slug,
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(
            "Debugger scenario failed: "
            f"{process.stderr.strip() or process.stdout.strip()}"
        )
    return DEBUG_RESULTS_DIR / slug


_slug_counter = (i for i in range(1, 10_000))
