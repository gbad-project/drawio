from __future__ import annotations

import os
import re
from collections import OrderedDict
from typing import Iterable

import pandas as pd


INCREMENT_NUMBER_COLUMN = "INCREMENT_NUMBER"
_NUMBERED_COLUMN_PATTERN = re.compile(
    r"^(?P<prefix>.+?)_(?P<index>\d+)(?P<suffix>(?:_.+)?)$"
)


class SourceCSVPreprocessor:
    def __init__(
        self, source_csv_path: str, preprocessed_csv_path: str, index_col=False
    ):
        self.source_csv_path = source_csv_path
        self.preprocessed_csv_path = preprocessed_csv_path
        self.index_col = index_col
        self.source_df = pd.read_csv(
            self.source_csv_path, index_col=index_col, dtype="object"
        )
        self._numbered_column_groups: dict[str, OrderedDict[int, str]] = {}
        self._numbered_column_order: list[str] = []
        self._column_to_base: dict[str, str] = {}
        self._normalised = False

    def update(self, df):
        self.source_df.update(df)

    def get(self, colnames: list[str]):
        missing = [col for col in colnames if col not in self.source_df.columns]
        if missing:
            for col in missing:
                self.source_df[col] = pd.Series(
                    None, index=self.source_df.index, dtype="object"
                )
            self._register_numbered_columns(missing)
        return self.source_df[colnames].copy()

    def add(self, colname: str, series: pd.Series):
        self.source_df[colname] = series
        self._register_numbered_columns([colname])

    def dump(self):
        self._normalise_numbered_columns()
        self._add_rico_authtp_column()

        index = self.index_col is not False
        header = True

        print(f"Saving preprocessed to: '{self.preprocessed_csv_path}'\n")
        os.makedirs(os.path.dirname(self.preprocessed_csv_path), exist_ok=True)
        self.source_df.to_csv(self.preprocessed_csv_path, index=index, header=header)

    def register_existing_numbered_columns(self, prefixes: Iterable[str]) -> None:
        for prefix in prefixes:
            prefix = prefix.strip()
            if not prefix:
                continue
            matching = [
                column
                for column in self.source_df.columns
                if column.startswith(f"{prefix}_")
            ]
            self._register_numbered_columns(matching)

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
        self._register_numbered_columns(separate_cols_list)

    def _register_numbered_columns(self, column_names: Iterable[str]) -> None:
        for column in column_names:
            if column not in self.source_df.columns:
                continue
            match = _NUMBERED_COLUMN_PATTERN.match(column)
            if match is None:
                continue

            prefix = match.group("prefix")
            index = int(match.group("index"))
            suffix = match.group("suffix") or ""
            base_name = f"{prefix}{suffix}"

            group = self._numbered_column_groups.setdefault(base_name, OrderedDict())
            if base_name not in self._numbered_column_order:
                self._numbered_column_order.append(base_name)
            group[index] = column
            self._column_to_base[column] = base_name

    @staticmethod
    def _value_present(value) -> bool:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return False
        if isinstance(value, str):
            return value.strip() != ""
        return True

    def _normalise_numbered_columns(self) -> None:
        if self._normalised or not self._numbered_column_groups:
            return

        base_names = [
            name
            for name in self._numbered_column_order
            if name in self._numbered_column_groups
        ]
        if not base_names:
            return

        numbered_columns = set(self._column_to_base.keys())
        static_columns = [
            column
            for column in self.source_df.columns
            if column not in numbered_columns and column not in base_names
        ]

        new_rows: list[dict[str, object]] = []
        new_index: list[object] = []

        for idx, row in self.source_df.iterrows():
            increments = sorted(
                {
                    increment
                    for group in self._numbered_column_groups.values()
                    for increment, column_name in group.items()
                    if self._value_present(row.get(column_name))
                }
            )

            if not increments:
                increments = [1]

            for increment in increments:
                new_row: dict[str, object] = {}
                for column in static_columns:
                    new_row[column] = row[column]

                for base_name in base_names:
                    group = self._numbered_column_groups[base_name]
                    column_name = group.get(increment)
                    new_row[base_name] = row[column_name] if column_name else None

                new_row[INCREMENT_NUMBER_COLUMN] = increment

                new_rows.append(new_row)
                new_index.append(idx)

        self.source_df = pd.DataFrame(
            new_rows, index=pd.Index(new_index, name=self.source_df.index.name)
        )

        ordered_columns = static_columns + [
            name for name in base_names if name not in static_columns
        ]
        if INCREMENT_NUMBER_COLUMN not in ordered_columns:
            ordered_columns.append(INCREMENT_NUMBER_COLUMN)
        self.source_df = self.source_df.loc[:, ordered_columns]
        self._normalised = True

    def _add_rico_authtp_column(self) -> None:
        if "AUTHTP" not in self.source_df.columns:
            return

        import importlib

        map_schema = None
        for module_name in ("legacy.map_schema", "map_schema"):
            try:
                map_schema = importlib.import_module(module_name)
                break
            except ModuleNotFoundError:
                continue

        if map_schema is None:  # pragma: no cover - defensive path
            return

        mapping = getattr(map_schema, "rico_authtp_dict", None)
        if not isinstance(mapping, dict):
            return

        compiled_patterns: list[tuple[str, re.Pattern[str]]] = []
        for value, pattern in mapping.values():
            regex = re.compile(pattern.strip("/"), flags=re.IGNORECASE)
            compiled_patterns.append((value, regex))

        def to_rico_class(raw):
            if not self._value_present(raw):
                return None
            text = str(raw)
            for mapped_value, regex in compiled_patterns:
                if regex.search(text):
                    return mapped_value
            return None

        self.source_df["RICO_AUTHTP"] = self.source_df["AUTHTP"].map(to_rico_class)
