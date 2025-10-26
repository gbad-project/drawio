from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from legacy.gbad.converter.preprocessors import SourceCSVPreprocessor


def _write_dataframe(path: Path, dataframe: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=True)


def test_normalise_incremented_columns(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "normalized.csv"

    dataframe = pd.DataFrame(
        {
            "SISN": [1, 2],
            "somecol": ["somecolvalue", "abc"],
            "othercol_1": ["othercol1value", None],
            "othercol_2": ["othercol2value", "lol"],
            "kek_1": [None, "kek1val"],
            "kek_2": [None, "kek2val"],
        }
    ).set_index("SISN")
    _write_dataframe(source, dataframe)

    preprocessor = SourceCSVPreprocessor(
        str(source), str(destination), index_col="SISN"
    )
    preprocessor.register_increment_columns(
        ["othercol_1", "othercol_2", "kek_1", "kek_2"]
    )
    preprocessor.normalise_incremented_columns()

    result = preprocessor.source_df.reset_index()

    expected = pd.DataFrame(
        {
            "SISN": [1, 1, 2, 2],
            "somecol": ["somecolvalue", "somecolvalue", "abc", "abc"],
            "othercol": [
                "othercol1value",
                "othercol2value",
                None,
                "lol",
            ],
            "kek": [None, None, "kek1val", "kek2val"],
            SourceCSVPreprocessor.INCREMENT_NUMBER_COLUMN: [1, 2, 1, 2],
        }
    )
    expected[SourceCSVPreprocessor.INCREMENT_NUMBER_COLUMN] = expected[
        SourceCSVPreprocessor.INCREMENT_NUMBER_COLUMN
    ].astype("Int64")

    assert_frame_equal(result, expected[result.columns])


def test_rico_authtp_mapping(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "normalized.csv"

    dataframe = pd.DataFrame(
        {
            "SISN": [10, 20],
            "somecol": ["value", "another"],
            "AUTHTP_1": ["C Ontario Government Name", "Family Name"],
            "AUTHTP_2": [None, "Geographic Name"],
        }
    ).set_index("SISN")
    _write_dataframe(source, dataframe)

    preprocessor = SourceCSVPreprocessor(
        str(source), str(destination), index_col="SISN"
    )
    preprocessor.register_increment_columns(["AUTHTP_1", "AUTHTP_2"])
    preprocessor.normalise_incremented_columns()
    preprocessor.apply_rico_authtp_mapping()

    result = preprocessor.source_df.reset_index()

    expected = pd.DataFrame(
        {
            "SISN": [10, 20, 20],
            "somecol": ["value", "another", "another"],
            "AUTHTP": [
                "C Ontario Government Name",
                "Family Name",
                "Geographic Name",
            ],
            "RICO_AUTHTP": ["Agent", "Agent", "Place"],
            SourceCSVPreprocessor.INCREMENT_NUMBER_COLUMN: [1, 1, 2],
        }
    )
    expected[SourceCSVPreprocessor.INCREMENT_NUMBER_COLUMN] = expected[
        SourceCSVPreprocessor.INCREMENT_NUMBER_COLUMN
    ].astype("Int64")

    assert_frame_equal(result, expected[result.columns])
