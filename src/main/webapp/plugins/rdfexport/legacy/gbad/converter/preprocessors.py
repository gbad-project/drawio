import os
import re
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence

import pandas as pd


@dataclass(frozen=True)
class PreprocessorOptions:
    """Runtime configuration applied to :class:`SourceCSVPreprocessor`.

    The defaults preserve the legacy behaviour while callers that need the
    additional normalisation steps can opt in explicitly.  The helper in
    ``pyodide_pipeline.csv_normalizer`` toggles the relevant flags when
    preparing the regression fixtures so the historical preprocessing logic is
    preserved everywhere else.
    """

    normalise_increments: bool = False
    drop_denormalised_columns: bool = False
    authtp_mapping: Mapping[str, tuple[str, str]] | None = None
    authtp_columns: Sequence[str] | None = None
    register_increment_columns: Sequence[str] | None = None
    auto_register_increment_prefixes: Sequence[str] | None = None


@dataclass
class _IncrementColumn:
    original_name: str
    normalised_name: str
    index: int


_INCREMENT_COLUMN_RE = re.compile(
    r"^(?P<prefix>.+?)_(?P<index>\d+)(?P<suffix>(?:_.*)?)$"
)


class SourceCSVPreprocessor:
    _default_options = PreprocessorOptions()

    def __init__(
        self,
        source_csv_path: str,
        preprocessed_csv_path: str,
        index_col=False,
        *,
        config: PreprocessorOptions | None = None,
    ):
        self.source_csv_path = source_csv_path
        self.preprocessed_csv_path = preprocessed_csv_path
        self.index_col = index_col
        self._config = config or self._default_options
        self.source_df = pd.read_csv(
            self.source_csv_path, index_col=index_col, dtype="object"
        )
        self._increment_columns: Dict[str, List[_IncrementColumn]] = defaultdict(list)
        self._auto_register_existing_columns()

    @property
    def config(self) -> PreprocessorOptions:
        """Expose the runtime configuration for compatibility helpers."""

        return self._config

    @classmethod
    @contextmanager
    def use_default_options(cls, options: PreprocessorOptions):
        """Temporarily replace the default configuration for new instances."""

        previous = cls._default_options
        cls._default_options = options
        try:
            yield
        finally:  # pragma: no cover - defensive reset
            cls._default_options = previous

    def update(self, df):
        self.source_df.update(df)

    def get(self, colnames: list[str]):
        existing = [column for column in colnames if column in self.source_df.columns]
        missing = [
            column for column in colnames if column not in self.source_df.columns
        ]

        if existing:
            frame = self.source_df[existing].copy()
        else:
            frame = pd.DataFrame(index=self.source_df.index)

        for column in missing:
            frame[column] = pd.Series(None, index=self.source_df.index, dtype="object")

        return frame[colnames]

    def add(self, colname: str, series: pd.Series):
        self.source_df[colname] = series
        self._register_increment_column(colname)

    def dump(self):
        if self._config.drop_denormalised_columns:
            self._drop_denormalised_columns()
        if self._config.authtp_mapping:
            self._apply_rico_authtp()
        if self._config.normalise_increments:
            self._normalise_incremented_columns()

        index = self.index_col is not False
        header = True

        print(f"Saving preprocessed to: '{self.preprocessed_csv_path}'\n")
        directory = os.path.dirname(self.preprocessed_csv_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.source_df.to_csv(self.preprocessed_csv_path, index=index, header=header)

    def separate_value(self, value: str, expect_num_cols: int, sep=""):
        separated_values = [None if s == "" else s for s in value.split(sep=sep)]
        if len(separated_values) < expect_num_cols:
            separated_values.extend([None] * (expect_num_cols - len(separated_values)))
        elif len(separated_values) != expect_num_cols:
            separated_values = [None] * expect_num_cols
        return separated_values

    # Deprecation warning: This is *really* slow
    def slow_column_split(self, split_method, joint_col, separate_cols_list):
        self.source_df[separate_cols_list] = (
            self.source_df[joint_col]
            .apply(
                lambda x: split_method(
                    "" if pd.isna(x) else str(x), len(separate_cols_list)
                )
            )
            .apply(pd.Series)
        )
        print(f"Splitting column '{joint_col}' into {separate_cols_list}\n")
        # source_df.drop(columns=[joint_col], inplace=True)

    def column_split(
        self, split_method, joint_col, separate_cols_list
    ):  # Generated with o4-mini on 2025-04-20, modified
        if joint_col not in self.source_df.columns:
            print(f"Skipping split for missing column '{joint_col}'\n")
            return
        # 1) Figure out which rows actually need splitting
        mask = self.source_df[joint_col].notna()
        # 2) Extract the non-null values, split them, and collect into a list of tuples
        split_vals = (
            self.source_df.loc[mask, joint_col]
            .astype(str)
            .map(lambda x: split_method(x, len(separate_cols_list)))
            .tolist()
        )
        # 3) Build a small DataFrame of just the split-parts
        split_df = pd.DataFrame(
            split_vals,
            index=self.source_df.loc[mask].index,
            columns=separate_cols_list,
        )
        # 4) Assign those back; non‑mask rows stay NaN (or whatever they were)
        self.source_df = pd.concat(
            [self.source_df, split_df], axis=1
        )  # this adds ALL of split_df’s columns in one operation
        print(f"Splitting column '{joint_col}' into {separate_cols_list}\n")
        # source_df.drop(columns=[joint_col], inplace=True)

        for column_name in separate_cols_list:
            self._register_increment_column(column_name)

    # Internal helpers -------------------------------------------------

    def _register_increment_column(self, column_name: str) -> _IncrementColumn | None:
        match = _INCREMENT_COLUMN_RE.match(column_name)
        if match is None:
            return None

        suffix = match.group("suffix") or ""
        normalised_name = f"{match.group('prefix')}{suffix}"
        index = int(match.group("index"))
        entry = _IncrementColumn(column_name, normalised_name, index)
        existing = self._increment_columns[normalised_name]
        if not any(col.original_name == column_name for col in existing):
            existing.append(entry)
        return entry

    def _auto_register_existing_columns(self) -> None:
        explicit = self._config.register_increment_columns or []
        for column in explicit:
            if column in self.source_df.columns:
                self._register_increment_column(column)

        prefixes = set(self._config.auto_register_increment_prefixes or [])
        if not prefixes:
            return
        for column in self.source_df.columns:
            match = _INCREMENT_COLUMN_RE.match(column)
            if match is None:
                continue
            if match.group("prefix") in prefixes:
                self._register_increment_column(column)

    def _drop_denormalised_columns(self) -> None:
        columns_to_keep = [
            column for column in self.source_df.columns if ":" not in column
        ]
        self.source_df = self.source_df.loc[:, columns_to_keep]

    def _apply_rico_authtp(self) -> None:
        mapping = self._config.authtp_mapping
        columns = self._config.authtp_columns or []
        if not mapping or not columns:
            return

        legacy_pattern = re.compile(
            r"^RICO_AUTHTP_(?:NEW|LABEL|CORPORATEBODY|FAMILY|PLACE|PERSON)_\d+$"
        )
        legacy_columns = [
            column for column in self.source_df.columns if legacy_pattern.match(column)
        ]
        if legacy_columns:
            for column in legacy_columns:
                match = _INCREMENT_COLUMN_RE.match(column)
                if match is None:
                    continue
                suffix = match.group("suffix") or ""
                normalised_name = f"{match.group('prefix')}{suffix}"
                self._increment_columns.pop(normalised_name, None)
            self.source_df = self.source_df.drop(columns=legacy_columns)

        compiled_patterns = []
        for _, (rico_class, pattern) in mapping.items():
            python_pattern = pattern
            if pattern.startswith("/") and pattern.endswith("/"):
                python_pattern = pattern[1:-1]
            compiled_patterns.append((rico_class, re.compile(python_pattern)))

        for column_name in columns:
            if column_name not in self.source_df.columns:
                continue
            info = self._register_increment_column(column_name)
            if info is None:
                continue

            def _map_value(value):
                if pd.isna(value):
                    return None
                text = str(value)
                for rico_class, regex in compiled_patterns:
                    if regex.search(text):
                        return rico_class
                return None

            new_column = f"RICO_AUTHTP_{info.index}"
            self.source_df[new_column] = self.source_df[column_name].map(_map_value)
            self._register_increment_column(new_column)

    def _normalise_incremented_columns(self) -> None:
        if not self._increment_columns:
            return

        for columns in self._increment_columns.values():
            columns.sort(key=lambda col: col.index)

        column_positions = {
            name: idx for idx, name in enumerate(self.source_df.columns)
        }
        increment_names = {
            column.original_name
            for columns in self._increment_columns.values()
            for column in columns
        }
        normalised_names = set(self._increment_columns.keys())
        base_columns = [
            column
            for column in self.source_df.columns
            if column not in increment_names and column not in normalised_names
        ]

        def _group_position(columns: List[_IncrementColumn]) -> int:
            return min(
                column_positions.get(col.original_name, len(column_positions))
                for col in columns
            )

        ordered_groups = sorted(
            self._increment_columns.items(), key=lambda item: _group_position(item[1])
        )
        ordered_normalised_names = [name for name, _ in ordered_groups]

        final_columns = list(base_columns)
        for normalised_name, columns in ordered_groups:
            position = _group_position(columns)
            insert_at = sum(
                1
                for column in final_columns
                if column_positions.get(column, -1) < position
            )
            final_columns.insert(insert_at, normalised_name)

        final_columns_with_increment = final_columns + ["INCREMENT_NUMBER"]

        normalised_rows: List[dict] = []
        normalised_index: List = []

        for idx, row in self.source_df.iterrows():
            base_values = row[base_columns].to_dict()
            group_values: Dict[str, Dict[int, object]] = {
                name: {col.index: row.get(col.original_name) for col in columns}
                for name, columns in self._increment_columns.items()
            }

            candidate_indices: set[int] = set()
            for values in group_values.values():
                candidate_indices.update(values.keys())
            if not candidate_indices:
                candidate_indices = {1}
            else:
                candidate_indices.add(1)

            for increment in sorted(candidate_indices):
                if increment != 1:
                    has_value = any(
                        not pd.isna(values.get(increment))
                        for values in group_values.values()
                    )
                    if not has_value:
                        continue
                new_row = base_values.copy()
                for name in ordered_normalised_names:
                    new_row[name] = group_values.get(name, {}).get(increment)
                new_row["INCREMENT_NUMBER"] = increment
                normalised_rows.append(new_row)
                normalised_index.append(idx)

        normalised_df = pd.DataFrame(normalised_rows, index=normalised_index)
        normalised_df.index.name = self.source_df.index.name
        self.source_df = normalised_df.loc[:, final_columns_with_increment]
        self._increment_columns.clear()
