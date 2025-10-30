"""Pipeline-based workflow for generating RML outputs via the debug CLI."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEBUG_DIR = PLUGIN_ROOT / "debug"
DEBUG_RESULTS_DIR = DEBUG_DIR / "results"
LEGACY_DIR = PLUGIN_ROOT / "legacy"
PYTHON_BIN = PLUGIN_ROOT / ".venv" / "bin" / "python"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from legacy.gbad.converter.preprocessors import (  # type: ignore  # noqa: E402
    SourceCSVPreprocessor,
)

from .map_schema_workflow import (  # type: ignore  # noqa: E402
    MapSchemaFixtureConfig,
    RMLMapperEnvironment,
)

import legacy.map_schema as legacy_map_schema  # type: ignore  # noqa: E402


class PipelineCSVPreprocessor(SourceCSVPreprocessor):
    """Preprocessor that normalises incremented columns for the pipeline workflow."""

    INCREMENT_COLUMN = "INCREMENT_NUMBER"
    RICO_AUTHTP_COLUMN = "RICO_AUTHTP"
    _SUFFIX_PATTERN = re.compile(
        r"^(?P<prefix>.+?)_(?P<number>\d+)(?P<suffix>(?:_.+)?)$"
    )

    def __init__(
        self,
        source_csv_path: str,
        preprocessed_csv_path: str,
        *,
        index_col: str | bool = False,
    ) -> None:
        super().__init__(
            source_csv_path,
            preprocessed_csv_path,
            index_col=index_col,
        )
        self._rico_authtp_patterns = self._compile_rico_patterns()

    def run(self) -> Path:
        """Execute preprocessing and return the path to the written CSV."""
        processed = self._normalise_increment_columns(self.source_df.copy())
        processed = self._annotate_rico_authtp(processed)
        processed[self.INCREMENT_COLUMN] = processed[self.INCREMENT_COLUMN].astype(
            "Int64"
        )
        self.source_df = processed
        super().dump()
        return Path(self.preprocessed_csv_path)

    def _annotate_rico_authtp(self, frame: pd.DataFrame) -> pd.DataFrame:
        if "AUTHTP" not in frame.columns:
            frame[self.RICO_AUTHTP_COLUMN] = pd.Series(
                [None] * len(frame), dtype="object"
            )
            return frame

        def _resolve(value: object) -> str | None:
            if pd.isna(value):
                return None
            text = str(value).strip()
            if not text:
                return None
            for label, pattern in self._rico_authtp_patterns:
                if pattern.search(text):
                    return label
            return None

        frame[self.RICO_AUTHTP_COLUMN] = frame["AUTHTP"].map(_resolve)
        return frame

    def _compile_rico_patterns(self) -> list[tuple[str, re.Pattern[str]]]:
        patterns: list[tuple[str, re.Pattern[str]]] = []
        for label, (_, raw_pattern) in legacy_map_schema.rico_authtp_dict.items():
            pythonic = raw_pattern
            if pythonic.startswith("/") and pythonic.endswith("/"):
                pythonic = pythonic[1:-1]
            patterns.append((label, re.compile(pythonic)))
        return patterns

    def _normalise_increment_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        increment_groups = self._collect_increment_groups(frame.columns)
        if not increment_groups:
            frame[self.INCREMENT_COLUMN] = pd.Series(
                [pd.NA] * len(frame), dtype="Int64"
            )
            return frame

        non_increment_columns = [
            column
            for column in frame.columns
            if all(
                column not in mapping.values() for mapping in increment_groups.values()
            )
        ]

        records: list[dict[str, object]] = []
        for _, row in frame.iterrows():
            numbers = self._collect_row_numbers(row, increment_groups)
            if not numbers:
                numbers = [None]
            for number in numbers:
                record: dict[str, object] = {
                    column: row[column] for column in non_increment_columns
                }
                record[self.INCREMENT_COLUMN] = number if number is not None else pd.NA
                for base, mapping in increment_groups.items():
                    source_column = mapping.get(number)
                    record[base] = (
                        row[source_column] if source_column is not None else None
                    )
                records.append(record)

        normalised = pd.DataFrame.from_records(records)
        ordered_columns = non_increment_columns + [self.INCREMENT_COLUMN]
        for base in increment_groups.keys():
            if base not in ordered_columns:
                ordered_columns.append(base)
        for column in normalised.columns:
            if column not in ordered_columns:
                ordered_columns.append(column)
        normalised = normalised.reindex(columns=ordered_columns)
        return normalised

    def _collect_increment_groups(
        self, columns: pd.Index | list[str]
    ) -> dict[str, dict[int, str]]:
        groups: dict[str, dict[int, str]] = {}
        for column in columns:
            match = self._SUFFIX_PATTERN.match(column)
            if not match:
                continue
            base = f"{match.group('prefix')}{match.group('suffix') or ''}"
            number = int(match.group("number"))
            groups.setdefault(base, {})[number] = column
        return groups

    def _collect_row_numbers(
        self,
        row: pd.Series,
        groups: dict[str, dict[int, str]],
    ) -> list[int]:
        numbers: set[int] = set()
        for mapping in groups.values():
            for number, column in mapping.items():
                value = row.get(column)
                if pd.isna(value):
                    continue
                text = str(value).strip()
                if text:
                    numbers.add(number)
        return sorted(numbers)


@dataclass
class PipelineWorkflowResult:
    """Artifacts produced by running the pipeline workflow."""

    workspace: Path
    pipeline_rml: Path
    pipeline_turtle: Path
    preprocessed_csv: Path
    scenario_slug: str
    mapper_error: str | None = None


def run_pipeline_workflow(
    config: MapSchemaFixtureConfig,
    env: RMLMapperEnvironment | None = None,
    workspace_base: Path | None = None,
) -> PipelineWorkflowResult:
    """Execute the pipeline workflow for a DrawIO fixture."""

    if env is None:
        env = RMLMapperEnvironment.from_manifest()

    scenario_slug = config.slug or _generate_slug(config.name)
    results_dir = _run_debug_scenario(config.scenario, scenario_slug)
    try:
        pipeline_rml_source = results_dir / "ts_pipeline.ttl"
        if not pipeline_rml_source.exists():
            raise FileNotFoundError(
                f"Expected pipeline RML output at {pipeline_rml_source}"
            )

        workspace = Path(
            tempfile.mkdtemp(
                prefix=f"pipeline-workflow-{config.name}-", dir=workspace_base
            )
        )

        preprocessed_csv = _run_pipeline_preprocessor(config, workspace)

        pipeline_rml = workspace / "pipeline_map.ttl"
        updated_text = _rewrite_pipeline_csv_path(
            pipeline_rml_source.read_text(encoding="utf-8"),
            preprocessed_csv,
        )
        pipeline_rml.write_text(updated_text, encoding="utf-8")

        pipeline_turtle = workspace / "pipeline_output.ttl"
        mapper_error: str | None = None
        try:
            env.run_mapper(pipeline_rml, pipeline_turtle, workspace)
        except RuntimeError as exc:  # pragma: no cover - defensive path
            mapper_error = str(exc)
            pipeline_turtle.write_text("", encoding="utf-8")

        return PipelineWorkflowResult(
            workspace=workspace,
            pipeline_rml=pipeline_rml,
            pipeline_turtle=pipeline_turtle,
            preprocessed_csv=preprocessed_csv,
            scenario_slug=scenario_slug,
            mapper_error=mapper_error,
        )
    finally:
        if results_dir.exists():
            shutil.rmtree(results_dir)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _run_pipeline_preprocessor(
    config: MapSchemaFixtureConfig,
    workspace: Path,
) -> Path:
    source_dir = workspace / "gbad" / "mapping" / "source"
    preprocessed_dir = source_dir / "preprocessed"
    preprocessed_dir.mkdir(parents=True, exist_ok=True)

    destination = preprocessed_dir / config.csv_fixture.name
    preprocessor = PipelineCSVPreprocessor(
        str(config.csv_fixture),
        str(destination),
        index_col=config.index_column,
    )
    return preprocessor.run()


def _rewrite_pipeline_csv_path(text: str, csv_path: Path) -> str:
    placeholder = f"gbad/mapping/source/preprocessed/{csv_path.name}"
    if placeholder in text:
        return text.replace(placeholder, str(csv_path))
    return text


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


def _generate_slug(name: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return f"pipeline-{safe}"
