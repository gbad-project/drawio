from __future__ import annotations

import os
import re
from collections import OrderedDict
from typing import Iterable, Sequence

import pandas as pd


class SourceCSVPreprocessor:
    INCREMENT_NUMBER_COLUMN = "INCREMENT_NUMBER"

    _INCREMENTED_COLUMN_RE = re.compile(
        r"^(?P<prefix>.+?)_(?P<index>\d+)(?P<suffix>(?:_.*)?)$"
    )

    def __init__(
        self,
        source_csv_path: str,
        preprocessed_csv_path: str,
        index_col: str | bool | None = False,
    ):
        self.source_csv_path = source_csv_path
        self.preprocessed_csv_path = preprocessed_csv_path
        self.index_col = index_col
        self.source_df = pd.read_csv(
            self.source_csv_path, index_col=index_col, dtype="object"
        )
        self._registered_increment_columns: set[str] = set()

    # ------------------------------------------------------------------
    # bookkeeping helpers
    # ------------------------------------------------------------------

    def register_increment_columns(self, columns: Iterable[str]) -> None:
        """Mark ``columns`` as belonging to an incremented family.

        Only names that match ``*_<number>`` (optionally followed by a suffix)
        are registered.  This keeps the normalisation pass scoped to columns
        produced by our own preprocessing routines or by explicit opt-in from
        callers.
        """

        for column in columns:
            if column in self._registered_increment_columns:
                continue
            if self._INCREMENTED_COLUMN_RE.match(column):
                self._registered_increment_columns.add(column)

    def update(self, df):
        self.source_df.update(df)

    def get(self, colnames: list[str]):
        return self.source_df[colnames].copy()

    def add(self, colname: str, series: pd.Series):
        self.source_df[colname] = series
        self.register_increment_columns([colname])

    def dump(self):
        index = self.index_col is not False
        header = True

        print(f"Saving preprocessed to: '{self.preprocessed_csv_path}'\n")
        os.makedirs(os.path.dirname(self.preprocessed_csv_path), exist_ok=True)
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
        self.register_increment_columns(separate_cols_list)

    # ------------------------------------------------------------------
    # normalisation helpers
    # ------------------------------------------------------------------

    def drop_compound_columns(self) -> None:
        """Remove columns that encode repeating groups in their names."""

        compound_columns = [
            column for column in self.source_df.columns if ":" in str(column)
        ]
        if compound_columns:
            self.source_df = self.source_df.drop(columns=compound_columns)

    def drop_columns(self, predicate) -> None:
        """Drop columns for which ``predicate(name)`` evaluates to ``True``."""

        columns_to_drop = [
            column for column in self.source_df.columns if predicate(column)
        ]
        if columns_to_drop:
            self.source_df = self.source_df.drop(columns=columns_to_drop)

    @staticmethod
    def _clean_value(value):
        if value is None:
            return None
        if isinstance(value, str):
            return value if value != "" else None
        if pd.isna(value):  # type: ignore[arg-type]
            return None
        return value

    def normalise_incremented_columns(self) -> None:
        """Collapse numbered columns into first normal form rows."""

        if not self._registered_increment_columns:
            return

        increment_groups: "OrderedDict[str, OrderedDict[int, str]]" = OrderedDict()
        increment_columns: set[str] = set()

        for column in self.source_df.columns:
            if column not in self._registered_increment_columns:
                continue
            match = self._INCREMENTED_COLUMN_RE.match(column)
            if match is None:
                continue

            prefix = match.group("prefix")
            suffix = match.group("suffix") or ""
            base_name = f"{prefix}{suffix}"
            index = int(match.group("index"))

            if base_name not in increment_groups:
                increment_groups[base_name] = OrderedDict()
            if index not in increment_groups[base_name]:
                increment_groups[base_name][index] = column
            increment_columns.add(column)

        if not increment_groups:
            return

        has_index = self.index_col not in {False, None}
        index_name = self.index_col if isinstance(self.index_col, str) else None

        non_increment_columns = [
            column
            for column in self.source_df.columns
            if column not in increment_columns
        ]

        base_names: Sequence[str] = tuple(increment_groups.keys())
        normalised_rows: list[dict[str, object]] = []

        def _max_increment(row: pd.Series) -> int:
            max_increment = 0
            for mapping in increment_groups.values():
                for idx, column_name in mapping.items():
                    value = row.get(column_name)
                    if isinstance(value, str):
                        if value != "":
                            max_increment = max(max_increment, idx)
                    elif not pd.isna(value):  # type: ignore[arg-type]
                        max_increment = max(max_increment, idx)
            return max_increment

        for row_index, row in self.source_df.iterrows():
            base_payload = {
                column: self._clean_value(row[column])
                for column in non_increment_columns
            }
            if has_index and index_name is not None:
                base_payload[index_name] = row_index

            max_increment = _max_increment(row)
            if max_increment == 0:
                max_increment = 1

            for increment in range(1, max_increment + 1):
                current_row = base_payload.copy()
                current_row[self.INCREMENT_NUMBER_COLUMN] = increment

                for base_name in base_names:
                    column_name = increment_groups[base_name].get(increment)
                    value = row.get(column_name) if column_name is not None else None
                    current_row[base_name] = self._clean_value(value)

                normalised_rows.append(current_row)

        ordered_columns = list(non_increment_columns)
        for base_name in base_names:
            if base_name not in ordered_columns:
                ordered_columns.append(base_name)
        if has_index and index_name is not None and index_name not in ordered_columns:
            ordered_columns.insert(0, index_name)
        ordered_columns.append(self.INCREMENT_NUMBER_COLUMN)

        normalised_df = pd.DataFrame(normalised_rows, columns=ordered_columns)
        if has_index and index_name is not None:
            normalised_df = normalised_df.set_index(index_name)

        normalised_df[self.INCREMENT_NUMBER_COLUMN] = normalised_df[
            self.INCREMENT_NUMBER_COLUMN
        ].astype("Int64")

        self.source_df = normalised_df
        new_columns = set(normalised_df.columns)
        self._registered_increment_columns = {
            column
            for column in self._registered_increment_columns
            if column in new_columns
        }

    def apply_rico_authtp_mapping(self, column: str = "AUTHTP") -> None:
        """Populate ``RICO_AUTHTP`` using the legacy regex mapping."""

        if column not in self.source_df.columns:
            return

        from legacy import map_schema  # Imported lazily to avoid circular deps.

        compiled_patterns = [
            (value, re.compile(pattern[1:-1]))
            for value, pattern in map_schema.rico_authtp_dict.values()
        ]

        def _map_value(raw_value):
            if raw_value is None or (
                isinstance(raw_value, float) and pd.isna(raw_value)
            ):
                return None
            raw_str = str(raw_value)
            for mapped_value, regex in compiled_patterns:
                if regex.search(raw_str):
                    return mapped_value
            return None

        self.source_df["RICO_AUTHTP"] = self.source_df[column].map(_map_value)

    def column_split(
        self, split_method, joint_col, separate_cols_list
    ):  # Generated with o4-mini on 2025-04-20, modified
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
        self.register_increment_columns(separate_cols_list)
