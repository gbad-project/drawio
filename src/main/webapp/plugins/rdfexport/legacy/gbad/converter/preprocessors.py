import pandas as pd
import os


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

    def update(self, df):
        self.source_df.update(df)

    def get(self, colnames: list[str]):
        return self.source_df[colnames].copy()

    def add(self, colname: str, series: pd.Series):
        self.source_df[colname] = series

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
