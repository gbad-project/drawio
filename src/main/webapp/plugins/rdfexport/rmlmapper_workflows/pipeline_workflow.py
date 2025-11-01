"""Pipeline-based workflow for generating RML outputs via the debug CLI."""

from __future__ import annotations

import re
import uuid
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Callable, Iterable

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
    BASE_MAPPING_URI = "https://data.archives.gov.on.test.gbad.ca/Schema/Mapping"
    _SUFFIX_PATTERN = re.compile(
        r"^(?P<prefix>.+?)_(?P<number>\d+)(?P<suffix>(?:_.+)?)$"
    )
    _RANGE_SUFFIX_PATTERN = re.compile(
        r"^(?P<base>.+?)_(?P<range>\d+\.\.\d+)(?:_(?P<suffix>.+))?$"
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
        self._uuid_lookup = self._compute_static_uuid_map()

    def run(self) -> Path:
        """Execute preprocessing and return the path to the written CSV."""
        processed = self._prepare_columns(self.source_df.copy())
        processed = self._normalise_increment_columns(processed)
        processed = self._assign_normalised_columns(processed)
        processed = self._derive_dateoff_column(processed)
        processed = self._annotate_rico_authtp(processed)
        processed = self._inject_uuid_columns(processed)
        processed = self._finalise_columns(processed)
        processed[self.INCREMENT_COLUMN] = processed[self.INCREMENT_COLUMN].astype(
            "Int64"
        )
        self.source_df = processed
        super().dump()
        return Path(self.preprocessed_csv_path)

    # ------------------------------------------------------------------
    # Column preparation helpers
    # ------------------------------------------------------------------

    def _prepare_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        prepared = frame.copy()

        self._split_column(
            prepared,
            "FINDAID:FINDAIDLINK:FINDAID_URL",
            ["FINDAID", "FINDAIDLINK", "FINDAID_URL"],
            self._split_by_colon,
        )
        self._split_column(
            prepared,
            "IIL:IIL_URL",
            ["IIL", "IIL_URL"],
            self._split_by_colon,
        )

        for base in ["INDEXPROV", "INDEXNAME", "INDEXSUB"]:
            targets = [f"{base}_{i}" for i in range(1, 31)]
            self._split_column(
                prepared,
                base,
                targets,
                self._split_by_adjacent_case,
                keep_source=True,
            )

        office_targets: list[str] = []
        office_components = ["DATEOFF", "OFFICEAB", "AB_REFA", "OFFICEC", "C_REFA"]
        for idx in range(1, 21):
            office_targets.extend(
                f"{component}_{idx}" for component in office_components
            )
        self._split_column(
            prepared,
            "DATEOFF:OFFICEAB:AB_REFA:OFFICEC:C_REFA",
            office_targets,
            self._split_by_colon,
        )

        for idx in range(1, 21):
            date_col = f"DATEOFF_{idx}"
            if date_col in prepared.columns:
                self._split_column(
                    prepared,
                    date_col,
                    [f"{date_col}_BEGINNING", f"{date_col}_END"],
                    self._split_by_hyphen,
                )

        self._expand_office_columns(prepared)

        if "REFD" in prepared.columns:
            prepared["REFD_FILE"] = prepared["REFD"]

        return prepared

    def _split_column(
        self,
        frame: pd.DataFrame,
        source_column: str,
        target_columns: Iterable[str],
        splitter: Callable[[str, int], list[str | None]],
        *,
        keep_source: bool = False,
    ) -> None:
        if source_column not in frame.columns:
            return

        values = frame[source_column]
        targets = list(target_columns)
        size = len(targets)

        def _split(value: object) -> list[str | None]:
            if pd.isna(value):
                return [None] * size
            text = str(value)
            if not text.strip():
                return [None] * size
            return splitter(text, size)

        splitted = pd.DataFrame(
            [_split(val) for val in values],
            columns=targets,
            index=frame.index,
        )
        for column in splitted.columns:
            frame[column] = splitted[column]

        if not keep_source:
            frame.drop(columns=[source_column], inplace=True)

    @staticmethod
    def _split_by_colon(value: str, expect_num_cols: int) -> list[str | None]:
        separator = " : "

        def _normalise(text: str) -> str:
            trimmed = text.strip()
            while "::" in trimmed:
                trimmed = trimmed.replace("::", ": :")
            while ": :" in trimmed:
                trimmed = trimmed.replace(": :", ":  :")
            if trimmed.endswith(" :"):
                trimmed = trimmed[:-2]
            if trimmed.startswith(": "):
                trimmed = trimmed[2:]
            return trimmed

        normalised = _normalise(value)
        parts = [part.strip() for part in normalised.split(separator)]
        parts = [part if part else None for part in parts]
        if len(parts) < expect_num_cols:
            parts.extend([None] * (expect_num_cols - len(parts)))
        elif len(parts) > expect_num_cols:
            parts = parts[:expect_num_cols]
        return parts

    @staticmethod
    def _split_by_adjacent_case(value: str, expect_num_cols: int) -> list[str | None]:
        if not value:
            return [None] * expect_num_cols
        separator = "<split-by-adjacent-case>"
        pattern = re.compile(r"([^A-Z\s\(\[])([A-Z])")
        prepared = pattern.sub(rf"\1{separator}\2", value)
        parts = [part.strip() for part in prepared.split(separator)]
        parts = [part if part else None for part in parts]
        if len(parts) < expect_num_cols:
            parts.extend([None] * (expect_num_cols - len(parts)))
        else:
            parts = parts[:expect_num_cols]
        return parts

    @staticmethod
    def _split_by_hyphen(value: str, expect_num_cols: int) -> list[str | None]:
        pattern = re.compile(r"^\d{4}-\d{4}$")
        if not value or pattern.fullmatch(value) is None:
            return [None] * expect_num_cols
        parts = value.split("-")
        if len(parts) < expect_num_cols:
            parts.extend([None] * (expect_num_cols - len(parts)))
        return [part if part else None for part in parts[:expect_num_cols]]

    def _expand_office_columns(self, frame: pd.DataFrame) -> None:
        for index in range(1, 21):
            ab_refa = frame.get(f"AB_REFA_{index}")
            c_refa = frame.get(f"C_REFA_{index}")
            if ab_refa is None and c_refa is None:
                continue
            ab_series = (
                ab_refa if ab_refa is not None else pd.Series(None, index=frame.index)
            )
            c_series = (
                c_refa if c_refa is not None else pd.Series(None, index=frame.index)
            )
            combined = c_series.combine_first(ab_series)
            frame[f"ABC_REFA_{index}"] = combined

            office_type = combined.str[0].str.upper()
            frame[f"OFFICE_TYPE_{index}"] = office_type

            officeab_col = frame.get(f"OFFICEAB_{index}")
            officec_col = frame.get(f"OFFICEC_{index}")
            officeabc = pd.Series(None, index=frame.index, dtype="object")
            if officeab_col is not None:
                officeabc.loc[office_type.isin(["A", "B"])] = officeab_col.loc[
                    office_type.isin(["A", "B"])
                ]
            if officec_col is not None:
                officeabc.loc[office_type == "C"] = officec_col.loc[office_type == "C"]
            frame[f"OFFICEABC_{index}"] = officeabc

    def _assign_normalised_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalised = frame.copy()
        if "FINDAID" in normalised.columns and "FINDAIDLINK" not in normalised.columns:
            normalised["FINDAIDLINK"] = pd.Series(
                [None] * len(normalised), dtype="object"
            )
        return normalised

    def _derive_dateoff_column(self, frame: pd.DataFrame) -> pd.DataFrame:
        derived = frame.copy()

        begin = derived.get("DATEOFF_BEGINNING")
        end = derived.get("DATEOFF_END")

        if begin is None and end is None:
            derived["DATEOFF"] = pd.Series([None] * len(derived), dtype="object")
            return derived

        if begin is None:
            begin = pd.Series([pd.NA] * len(derived), index=derived.index)
        if end is None:
            end = pd.Series([pd.NA] * len(derived), index=derived.index)

        def _format(value: object) -> str | None:
            if pd.isna(value):
                return None
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            text = str(value).strip()
            return text or None

        combined: list[str | None] = []
        for start_value, end_value in zip(begin, end):
            start_text = _format(start_value)
            end_text = _format(end_value)
            if start_text and end_text:
                combined.append(f"{start_text}-{end_text}")
            elif start_text:
                combined.append(start_text)
            elif end_text:
                combined.append(end_text)
            else:
                combined.append(None)

        derived["DATEOFF"] = pd.Series(combined, index=derived.index, dtype="object")
        return derived

    def _inject_uuid_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        enriched = frame.copy()
        inst_uuid = self._uuid_lookup["UUID_INSTANTIATION"]
        enriched["UUID_INSTANTIATION"] = inst_uuid

        fallback_uuid = self._uuid_lookup.get("UUID_INSTANTIATION_1")
        if fallback_uuid is not None:
            enriched["UUID_INSTANTIATION_1"] = fallback_uuid

        office_map = self._uuid_lookup["UUID_OFFICEABC"]
        uuid_series = pd.Series(None, index=enriched.index, dtype="object")
        increment_series = enriched[self.INCREMENT_COLUMN]
        for index, uuid_value in office_map.items():
            mask = increment_series == index
            if mask.any():
                uuid_series.loc[mask] = uuid_value
        enriched["UUID_OFFICEABC"] = uuid_series
        return enriched

    def _finalise_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        finalised = frame.copy()
        if "Unnamed: 0" in finalised.columns:
            finalised = finalised.drop(columns=["Unnamed: 0"])
        return finalised

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

    def _compute_static_uuid_map(self) -> dict[str, object]:
        instantiation_tm = (
            "rr_template___KB_Instantiation__REFD__urn_uuid__UUID_INSTANTIATION_1__"
        )
        inst_uuid = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{self.BASE_MAPPING_URI}#{instantiation_tm}",
            )
        )

        office_map: dict[int, str] = {}
        for index in range(1, 21):
            triples_map = (
                f"rr_template___KB_CreationRelation__REFD___OFFICEABC_{index}__"
                "urn_uuid__UUID_OFFICEABC__"
            )
            office_map[index] = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{self.BASE_MAPPING_URI}#{triples_map}",
                )
            )

        return {
            "UUID_INSTANTIATION": inst_uuid,
            "UUID_INSTANTIATION_1": inst_uuid,
            "UUID_OFFICEABC": office_map,
        }


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
        text = text.replace(placeholder, str(csv_path))
    return _normalise_label_templates(text)


def _normalise_label_templates(text: str) -> str:
    """Align RML label templates with map_schema expectations."""

    normalized = text.replace("\u00a0", " ")

    replacements = {
        '"{TITLE} - {OFFICEABC} (Creation Relation). Context:"': (
            '"{TITLE} - {OFFICEABC} (Creation Relation). Context: '
            '<urn:uuid:{UUID_OFFICEABC}>"'
        ),
        '"{REFD_FILE} - {TITLE} (Instantiation). Context:"': (
            '"{REFD_FILE} - {TITLE} (Instantiation). Context: '
            '<urn:uuid:{UUID_INSTANTIATION}>"'
        ),
        '"/{DATEOFF}"': '"https://data.archives.gov.on.test.gbad.ca/{DATEOFF}"',
    }

    for source, target in replacements.items():
        normalized = normalized.replace(source, target)

    return normalized


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
    result = subprocess.run(command, capture_output=True, text=True)

    map_path = DEBUG_DIR / "map.json"
    map_data = json.loads(map_path.read_text(encoding="utf-8"))
    scenario_entry = map_data["scenarios"].get(slug)
    if not scenario_entry:
        raise RuntimeError(
            f"Scenario '{slug}' not recorded after command.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    errors = scenario_entry.get("errors", {}) or {}

    def _is_expected_warning(name: str, details: object) -> bool:
        if name == "ts_stderr" and details:
            if isinstance(details, str):
                lines = [line.strip() for line in details.splitlines() if line.strip()]
            elif isinstance(details, list):
                lines = [str(line).strip() for line in details if str(line).strip()]
            else:
                return False
            return bool(lines) and all(line.startswith("[PYODIDE]") for line in lines)
        return False

    unexpected_errors = {
        name: details
        for name, details in errors.items()
        if name != "py_legacy" and details and not _is_expected_warning(name, details)
    }

    if unexpected_errors:
        raise RuntimeError(
            f"Unexpected debugger errors in scenario '{slug}': {unexpected_errors}"
        )
    return DEBUG_RESULTS_DIR / slug


def _generate_slug(name: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return f"pipeline-{safe}"
