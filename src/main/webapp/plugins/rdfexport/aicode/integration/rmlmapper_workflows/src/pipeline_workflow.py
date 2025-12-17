"""Pipeline-based workflow for generating RML outputs via the debug CLI."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Literal
from pydantic import AnyUrl

import uuid
import base64
import hashlib

import pandas as pd
from rdflib import URIRef

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
DEBUG_DATA_DIR = PLUGIN_ROOT / "data" / "debug"
DEBUG_RESULTS_DIR = DEBUG_DATA_DIR / "results"
LEGACY_DIR = PLUGIN_ROOT / "python_core" / "src" / "legacy"
PYTHON_BIN = PLUGIN_ROOT / ".venv" / "bin" / "python"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from python_core.src.legacy.gbad.converter.preprocessors import (  # type: ignore  # noqa: E402
    SourceCSVPreprocessor,
)

from aicode.integration.rmlmapper_workflows.src.map_schema_workflow import (  # type: ignore  # noqa: E402
    MapSchemaFixtureConfig,
    RMLMapperEnvironment,
    _get_base_uri,
)

import python_core.src.legacy.map_schema as legacy_map_schema  # type: ignore  # noqa: E402


def generate_uuid_from_file_and_url(file_path: Path, any_url: AnyUrl) -> uuid.UUID:
    encoding_to_use = "utf-8"
    file_content = file_path.read_text(encoding=encoding_to_use)
    file_hash = hashlib.sha256(file_content.encode(encoding_to_use))
    print(
        f"\nSHA256 hash '{file_hash.hexdigest()}' generated for '{encoding_to_use}' encoded plain text contents of: '{file_path.relative_to(Path.cwd())}'"
    )
    print(f"Base64: {base64.b64encode(file_hash.digest()).decode()}")

    # https://www.rfc-editor.org/rfc/rfc6920.html
    # Figure 4: ni Name Syntax
    # NI-URI         = ni-scheme ":" ni-hier-part [ "?" query ]
    # ni-scheme      = "ni"
    # ni-hier-part   = "//" [ authority ] "/" alg-val
    # alg-val        = alg ";" val
    # The "val" field MUST contain the output of base64url encoding
    # (with no "=" padding characters)
    # Note also that ni val must be generated from bytes and URL safe
    ni_val = base64.urlsafe_b64encode(file_hash.digest()).decode().rstrip("=")
    ni_uri = f"ni:///sha-256;{ni_val}"
    print(f"Valid ni URI (RFC6920-compliant): <{ni_uri}>")

    # Generate a UUID v5 for ni URI
    uuid_ns = uuid.uuid5(uuid.NAMESPACE_URL, str(any_url))
    print(f"UUID v5 Namespace generated from ns:URL and URL <{any_url}>: {uuid_ns}")
    uuid_obj = uuid.uuid5(uuid_ns, ni_uri)
    print(f"UUID v5 generated from this namespace and ni URI: {uuid_obj}")
    print("""Ten steps to verify (ONLY for public data!):
1. Generate a custom UUID Namespace using your URL here: https://www.uuidtools.com/v5
2. Make sure you select 'Enter identifier for pre-defined UUIDs' and choose 'ns:URL - for URLs', and enter your URL as Name
3. Copy the generated UUID into the Namespace field and leave the browser tab open
4. In a new tab, copy and paste file contents into: https://emn178.github.io/online-tools/sha256.html
5. Make sure input encoding is set to UTF-8 and output encoding to Base64
6. Review the output - should be identical to Base64 in function outputs
7. Once the hash is verified, go back to the other tab and copy and paste entire ni URI to Name field
8. Make sure the UUID you generated earlier is still entered in Namespace field
9. Generate UUID v5 for ni URI using the earlier UUID as Namespace and ni URI as Name
10. Both UUIDs should match the function outputs""")
    return uuid_obj


def construct_named_graph_uri(uuid_obj: uuid.UUID, base_uri: str) -> URIRef:
    return URIRef(f"{base_uri}/graph/urn:uuid:{uuid_obj}")


class PipelineCSVPreprocessor(SourceCSVPreprocessor):
    """Preprocessor that normalises incremented columns for the pipeline workflow."""

    INCREMENT_COLUMN = "INCREMENT_NUMBER"
    RICO_AUTHTP_CLASS_COLUMN = "RICO_AUTHTP_CLASS"
    RICO_AUTHTP_TERM_COLUMN = "RICO_AUTHTP_TERM"

    _SUFFIX_PATTERN = re.compile(
        r"^(?P<prefix>.+?)_(?P<number>\d+)(?P<suffix>(?:_.+)?)$"
    )

    def __init__(
        self,
        source_csv_path: str,
        preprocessed_csv_path: str,
        schema_code: Literal["add", "auth"],
        *,
        index_col: str | bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            source_csv_path,
            preprocessed_csv_path,
            index_col=index_col,
        )
        self._schema_code = schema_code
        self._constants = kwargs.get("constants", [])
        self._rico_authtp_patterns = self._compile_rico_patterns()
        # Auth-specific
        self._correct_dateex_path = kwargs.get("correct_dateex_path")

    def run(self) -> Path:
        """Execute preprocessing and return the path to the written CSV."""
        if self._schema_code == "auth":
            self._auth_preprocess()
        elif self._schema_code == "add":
            self._add_preprocess()

        processed = self._normalise_increment_columns(self.source_df.copy())
        processed[self.INCREMENT_COLUMN] = processed[self.INCREMENT_COLUMN].astype(
            "Int64"
        )

        self.source_df = processed

        if self._schema_code == "auth":
            self._auth_post_preprocess()

        self._append_constant_columns()

        super().dump()
        return Path(self.preprocessed_csv_path)

    # Overrides original
    def column_split(self, split_method, joint_col, separate_cols_list):
        mask = self.source_df[joint_col].notna()
        split_vals = (
            self.source_df.loc[mask, joint_col]
            .astype(str)
            .map(lambda x: split_method(x, len(separate_cols_list)))
            .tolist()
        )
        split_df = pd.DataFrame(
            split_vals,
            index=self.source_df.loc[mask].index,
            columns=separate_cols_list,
        )
        # Drop existing columns first to avoid duplicates
        self.source_df = self.source_df.drop(
            columns=[col for col in separate_cols_list if col in self.source_df.columns]
        )
        self.source_df = pd.concat([self.source_df, split_df], axis=1)
        print(f"Splitting column '{joint_col}' into {separate_cols_list}\n")

    def _append_constant_columns(self):
        if not self._constants:
            return
        try:
            for colname, value in self._constants:
                self.add(
                    colname,
                    pd.Series(str(value), index=self.source_df.index, dtype="object"),
                )
        except Exception as e:
            print(f"Could not add constant columns '{self._constants}': {e}")

    ### Auth-specific processing ###
    def _auth_preprocess(self):
        self._pull_correct_dateex()

    def _auth_post_preprocess(self):
        self._annotate_rico_authtp()

    def _annotate_rico_authtp(self):
        """Annotate with RiC-O AUTHTP class and term based on AUTHTP column."""
        if "AUTHTP" not in self.source_df.columns:  # defensive fallback
            self.add(
                self.RICO_AUTHTP_CLASS_COLUMN,
                pd.Series([None] * len(self.source_df), dtype="object"),
            )
            self.add(
                self.RICO_AUTHTP_TERM_COLUMN,
                pd.Series([None] * len(self.source_df), dtype="object"),
            )
            return

        def _resolve(value: object) -> tuple[str | None, str | None]:
            """Return (class_uri, term) tuple."""
            if pd.isna(value):
                return (None, None)
            text = str(value).strip()
            if not text:
                return (None, None)
            for label, (term, pattern) in self._rico_authtp_patterns:
                if pattern.search(text):
                    class_uri = f"https://www.ica.org/standards/RiC/ontology#{label}"
                    return (class_uri, term)
            return (None, None)

        results = self.get(["AUTHTP"]).map(_resolve)

        self.add(self.RICO_AUTHTP_CLASS_COLUMN, results.map(lambda x: x[0]))
        self.add(self.RICO_AUTHTP_TERM_COLUMN, results.map(lambda x: x[1]))

        for label, (term, pattern) in self._rico_authtp_patterns:
            colname = f"RICO_AUTHTP_{label.upper()}"
            self.add(
                colname,
                self.get(["AUTHTP"]).apply(
                    lambda x: term if pattern.search(str(x["AUTHTP"])) else None, axis=1
                ),
            )

    def _pull_correct_dateex(self):
        DATEEX_COLS = ["DATEEX_BEGINNING", "DATEEX_END"]
        SISN = "SISN"
        correct_dateex_path = self._correct_dateex_path
        if correct_dateex_path is None:
            return
        try:
            correct_dateex_name = Path(correct_dateex_path).name
            correct_dateex_df = pd.read_csv(
                correct_dateex_path, index_col=SISN, dtype="object"
            )
            self.update(correct_dateex_df[DATEEX_COLS])

            print(
                f"Source preprocessed by updating {DATEEX_COLS} with values from '{correct_dateex_name}'\n"
            )
        except Exception as e:
            print(f"Failed to update Authority DATEEX with correct values: '{e}'")

    ### ADD-specific processing ###
    def _add_refd_file_column(self):
        if (
            "REFD" not in self.source_df.columns
            and "REF_FILE" not in self.source_df.columns
        ):
            raise ValueError("Neither REFD nor REF_FILE found in ADD CSV")
        refd = self.source_df.get("REFD")
        ref_file = self.source_df.get("REF_FILE")
        both_non_null = refd.notna() & ref_file.notna()
        if both_non_null.any():
            raise ValueError("Both REFD and REF_FILE present and non-null in some rows")
        refd_file = refd.combine_first(ref_file)
        self.add("REFD_FILE", refd_file)

    def _add_preprocess(self):
        DATEOFF_COLNAME = "DATEOFF"
        DATE_BEGINNING_SUFFIX = "_BEGINNING"
        DATE_END_SUFFIX = "_END"

        # Column split #1
        joint_findaid_col = "FINDAID:FINDAIDLINK:FINDAID_URL"
        separate_findaid_cols = ["FINDAID", "FINDAIDLINK", "FINDAID_URL"]
        self.column_split(
            self._split_by_colon, joint_findaid_col, separate_findaid_cols
        )

        # Column split #2
        joint_iil_col = "IIL:IIL_URL"
        separate_iil_cols = ["IIL", "IIL_URL"]
        self.column_split(self._split_by_colon, joint_iil_col, separate_iil_cols)

        # Column split #3
        indexprov_col = "INDEXPROV"
        numbered_indexprov_cols = [f"{indexprov_col}_{i}" for i in range(1, 31)]
        self.column_split(
            self._split_by_adjacent_case, indexprov_col, numbered_indexprov_cols
        )

        # Column split #4
        indexname_col = "INDEXNAME"
        numbered_indexname_cols = [f"{indexname_col}_{i}" for i in range(1, 31)]
        self.column_split(
            self._split_by_adjacent_case, indexname_col, numbered_indexname_cols
        )

        # Column split #5
        indexsub_col = "INDEXSUB"
        numbered_indexsub_cols = [f"{indexsub_col}_{i}" for i in range(1, 31)]
        self.column_split(
            self._split_by_adjacent_case, indexsub_col, numbered_indexsub_cols
        )

        # Column split #6
        joint_office_col = "DATEOFF:OFFICEAB:AB_REFA:OFFICEC:C_REFA"
        separate_office_cols = ["DATEOFF", "OFFICEAB", "AB_REFA", "OFFICEC", "C_REFA"]
        numbered_office_cols = []
        for i in range(1, 21):
            numbered_office_cols.extend([f"{col}_{i}" for col in separate_office_cols])
        len(numbered_office_cols)
        self.column_split(self._split_by_colon, joint_office_col, numbered_office_cols)

        # Column split #7
        joint_dateoff_colnames = [f"{DATEOFF_COLNAME}_{i}" for i in range(1, 21)]
        for col in joint_dateoff_colnames:
            separate_dateoff_cols = [
                f"{col}{DATE_BEGINNING_SUFFIX}",
                f"{col}{DATE_END_SUFFIX}",
            ]
            self.column_split(self._split_by_hyphen, col, separate_dateoff_cols)

        # Column logic (not split) #8, co-created with Claude 3.7 Sonnet on 2025-04-21
        for i in range(1, 21):
            # REFA based (main) logic
            ab_refa_colname = f"AB_REFA_{i}"
            c_refa_colname = f"C_REFA_{i}"
            abc_refa_colname = f"ABC_REFA_{i}"
            refa_df = self.get([ab_refa_colname, c_refa_colname])
            abc_refa_series = refa_df[c_refa_colname].combine_first(
                refa_df[ab_refa_colname]
            )
            self.add(abc_refa_colname, abc_refa_series)

            # 1. OFFICE_TYPE: determine by first character
            office_type_colname = f"OFFICE_TYPE_{i}"
            office_type_series = (
                abc_refa_series.str[0]
                .str.upper()
                .map(lambda x: x if x in {"A", "B", "C"} else None)
            )
            self.add(office_type_colname, office_type_series)

            # 2. OFFICEABC: pick office_ab or office_c based on office type
            officeab_colname = f"OFFICEAB_{i}"
            officec_colname = f"OFFICEC_{i}"
            officeabc_colname = f"OFFICEABC_{i}"
            office_df = self.get([officeab_colname, officec_colname])

            # Initialize the result series with None values (same index as other series)
            officeabc_series = pd.Series(None, index=office_df.index, dtype="object")

            # Fill in values based on office type
            # For A or B types, use OFFICEAB
            officeabc_series.loc[office_type_series.isin(["A", "B"])] = office_df.loc[
                office_type_series.isin(["A", "B"]), officeab_colname
            ]

            # For C type, use OFFICEC
            officeabc_series.loc[office_type_series == "C"] = office_df.loc[
                office_type_series == "C", officec_colname
            ]

            # Add the combined series to the preprocessor
            self.add(officeabc_colname, officeabc_series)

        self._add_refd_file_column()

    def _split_by_colon(self, value: str, expect_num_cols: int):
        SEP = " : "

        def fix_colon_spacing(value: str) -> str:
            while ": :" in value:
                value = value.replace(": :", ":  :")
            value = (
                value[:-2] if value.endswith(" :") else value
            )  # to fix any ending colon
            value = (
                value[2:] if value.startswith(": ") else value
            )  # to fix any starting colon
            return value

        return self.separate_value(fix_colon_spacing(value), expect_num_cols, sep=SEP)

    def _split_by_adjacent_case(self, value: str, expect_num_cols: int):
        unique_separator = "<split-by-adjacent-case>"
        value = re.sub(r"([^A-Z\s\(\[])([A-Z])", rf"\1{unique_separator}\2", value)
        return self.separate_value(value, expect_num_cols, sep=unique_separator)

    def _split_by_hyphen(self, value: str, expect_num_cols: int):
        if re.fullmatch(r"\d{4}-\d{4}", value) is None:
            value = ""  # won't try to separate these for now
        return self.separate_value(value, expect_num_cols, sep="-")

    ### Shared Auth/ADD processing ###
    def _compile_rico_patterns(self) -> list[tuple[str, tuple[str, re.Pattern[str]]]]:
        """Compile RiC-O AUTHTP patterns from legacy schema."""
        patterns: list[tuple[str, tuple[str, re.Pattern[str]]]] = []
        for label, (term, raw_pattern) in legacy_map_schema.rico_authtp_dict.items():
            pythonic = raw_pattern
            if pythonic.startswith("/") and pythonic.endswith("/"):
                pythonic = pythonic[1:-1]
            patterns.append((label, (term, re.compile(pythonic))))
        return patterns

    def _normalise_increment_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Normalise incremented columns by creating rows per increment number."""
        frame.reset_index(inplace=True)
        increment_groups = self._collect_increment_groups(frame.columns)

        if not increment_groups:
            frame[self.INCREMENT_COLUMN] = pd.Series(
                [pd.NA] * len(frame), dtype="Int64"
            )
            return frame

        # Identify non-incremented columns
        non_increment_columns = [
            column
            for column in frame.columns
            if all(
                column not in mapping.values() for mapping in increment_groups.values()
            )
        ]

        records: list[dict[str, object]] = []

        for _, row in frame.iterrows():
            # Find max increment number with actual data in this row
            max_increment = self._get_max_increment_with_data(row, increment_groups)

            if max_increment is None:
                # No incremented data in this row, create single row with no increment
                record: dict[str, object] = {
                    column: row[column] for column in non_increment_columns
                }
                record[self.INCREMENT_COLUMN] = pd.NA
                for base in increment_groups.keys():
                    record[base] = None
                records.append(record)
                continue

            # Create rows for each increment number from 1 to max
            for increment_num in range(1, max_increment + 1):
                record: dict[str, object] = {
                    column: row[column] for column in non_increment_columns
                }
                record[self.INCREMENT_COLUMN] = increment_num

                # Check if this increment has any data
                has_data = False
                for base, mapping in increment_groups.items():
                    source_column = mapping.get(increment_num)
                    if source_column is not None:
                        value = row[source_column]
                        if not pd.isna(value) and str(value).strip():
                            record[base] = value
                            has_data = True
                        else:
                            record[base] = None
                    else:
                        record[base] = None

                # Only keep this row if it has at least one value from incremented columns
                if has_data:
                    records.append(record)

        normalised = pd.DataFrame.from_records(records)

        # Order columns: non-increment cols, INCREMENT_COLUMN, then base columns
        ordered_columns = non_increment_columns + [self.INCREMENT_COLUMN]
        for base in increment_groups.keys():
            if base not in ordered_columns:
                ordered_columns.append(base)
        for column in normalised.columns:
            if column not in ordered_columns:
                ordered_columns.append(column)

        normalised = normalised.reindex(columns=ordered_columns)
        normalised.set_index(self.index_col, inplace=True)
        return normalised

    def _collect_increment_groups(
        self, columns: pd.Index | list[str]
    ) -> dict[str, dict[int, str]]:
        """Group columns by their base name and increment numbers."""
        groups: dict[str, dict[int, str]] = {}
        for column in columns:
            match = self._SUFFIX_PATTERN.match(column)
            if not match:
                continue
            base = f"{match.group('prefix')}{match.group('suffix') or ''}"
            number = int(match.group("number"))
            groups.setdefault(base, {})[number] = column
        return groups

    def _get_max_increment_with_data(
        self,
        row: pd.Series,
        groups: dict[str, dict[int, str]],
    ) -> int | None:
        """Find the maximum increment number that has data in any column for this row."""
        max_increment = None
        for mapping in groups.values():
            for number, column in mapping.items():
                value = row.get(column)
                if pd.isna(value):
                    continue
                text = str(value).strip()
                if text:
                    if max_increment is None or number > max_increment:
                        max_increment = number
        return max_increment


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
    **kwargs,
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

        base_uri = _get_base_uri(config.scenario)
        try:
            # Using actual debug.__main__ output that
            # contains real CSV path - important because
            # UUID will be generated from the file contents.
            # The RML itself now persists also.
            file_path = pipeline_rml_source
            uuid_obj = generate_uuid_from_file_and_url(
                file_path=file_path,
                any_url=base_uri,
            )
        except Exception as e:
            uuid_obj = uuid.uuid4()
            print(
                f"Failed to generate UUID from file and URL - falling back to UUID v4: {uuid_obj}. Error: {e}"
            )
        named_graph_uri = construct_named_graph_uri(uuid_obj, base_uri)

        preprocessed_csv = _run_pipeline_preprocessor(
            config,
            workspace,
            constants=[
                ("NAMED_GRAPH_IRI", str(named_graph_uri)),
                ("UUID", str(uuid_obj)),
            ],
            **kwargs,
        )

        pipeline_rml = workspace / "pipeline_map.ttl"
        updated_text = _rewrite_pipeline_csv_path(
            pipeline_rml_source.read_text(encoding="utf-8"),
            preprocessed_csv,
        )
        pipeline_rml.write_text(updated_text, encoding="utf-8")

        pipeline_turtle = workspace / "pipeline_output.ttl"
        mapper_error: str | None = None
        try:
            env.run_mapper(pipeline_rml, pipeline_turtle, workspace, base_uri)
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
        pass
        # Preserve pytest debug outputs -
        # see above rationale for UUID generation
        # if results_dir.exists():
        #     shutil.rmtree(results_dir)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _run_pipeline_preprocessor(
    config: MapSchemaFixtureConfig,
    workspace: Path,
    **kwargs,
) -> Path:
    source_dir = workspace / "gbad" / "mapping" / "source"
    preprocessed_dir = source_dir / "preprocessed"
    preprocessed_dir.mkdir(parents=True, exist_ok=True)

    destination = preprocessed_dir / config.csv_fixture.name
    preprocessor = PipelineCSVPreprocessor(
        str(config.csv_fixture),
        str(destination),
        schema_code=config.schema_code,
        index_col=config.index_column,
        **kwargs,
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
        "aicode.integration.debug.src",
        "--scenario",
        str(scenario_path),
        "--slug",
        slug,
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    map_path = DEBUG_DATA_DIR / "map.json"
    map_data = json.loads(map_path.read_text(encoding="utf-8"))
    scenario_entry = map_data["scenarios"].get(slug)
    if not scenario_entry:
        raise RuntimeError(
            f"Scenario '{slug}' not recorded after command.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    errors = scenario_entry.get("errors", {}) or {}
    unexpected_errors = {
        name: details
        for name, details in errors.items()
        if name != "py_legacy" and details
    }

    if unexpected_errors:
        raise RuntimeError(
            f"Unexpected debugger errors in scenario '{slug}': {unexpected_errors}"
        )
    return DEBUG_RESULTS_DIR / slug


def _generate_slug(name: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return f"pipeline-{safe}"


if __name__ == "__main__":
    import pytest
    from pathlib import Path

    current = Path(__file__).resolve()
    test_file = current.parent / "tests" / f"test_{current.stem}.py"

    # verbose (-v), stdout, and, with -rA, displays a detailed summary of all test results — including passed, failed, skipped, xfailed, and xpassed tests — at the end of the run.
    pytest.main(["-v", "-s", "-rA", test_file])
