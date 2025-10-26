from __future__ import annotations

# ruff: noqa: E402

import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
LEGACY_ROOT = PROJECT_ROOT / "legacy"
if str(LEGACY_ROOT) not in sys.path:
    sys.path.insert(0, str(LEGACY_ROOT))

from legacy import map_schema
from legacy.gbad.converter.preprocessors import (
    PreprocessorOptions,
    SourceCSVPreprocessor,
)


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _split_by_pipe(
    preprocessor: SourceCSVPreprocessor, value: str, count: int
) -> list[str | None]:
    text = "" if value is None else str(value)
    return preprocessor.separate_value(text, count, sep="|")


def test_increment_normalisation_and_rico_mapping(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "normalised.csv"

    _write_csv(
        source,
        """SISN,COMBINED_OTHER,COMBINED_KEK,AUTHTP_1,AUTHTP_2,NOTE\n"
        "1,othercol1value|othercol2value,|,Corporate Name value,Place (Geographic Name),row1\n"
        "2,|lol,kek1val|kek2val,Family Name entry,Personal Name entry,row2\n""",
    )

    options = PreprocessorOptions(
        normalise_increments=True,
        authtp_mapping=map_schema.rico_authtp_dict,
        authtp_columns=["AUTHTP_1", "AUTHTP_2"],
    )

    preprocessor = SourceCSVPreprocessor(
        str(source),
        str(destination),
        index_col="SISN",
        config=options,
    )

    def split(value: str, expected: int) -> list[str | None]:
        return _split_by_pipe(preprocessor, value, expected)

    preprocessor.column_split(split, "COMBINED_OTHER", ["OTHER_1", "OTHER_2"])
    preprocessor.column_split(split, "COMBINED_KEK", ["KEK_1", "KEK_2"])
    preprocessor.dump()

    frame = pd.read_csv(destination, dtype="object")
    assert "INCREMENT_NUMBER" in frame.columns
    assert "AUTHTP" in frame.columns
    assert "RICO_AUTHTP" in frame.columns
    assert not any(
        col.endswith("_1") or col.endswith("_2")
        for col in frame.columns
        if col.startswith("AUTHTP")
    )

    frame["INCREMENT_NUMBER"] = frame["INCREMENT_NUMBER"].astype(int)
    frame = frame.set_index(["SISN", "INCREMENT_NUMBER"]).sort_index()

    expected_index = pd.MultiIndex.from_tuples(
        [("1", 1), ("1", 2), ("2", 1), ("2", 2)],
        names=["SISN", "INCREMENT_NUMBER"],
    )
    expected = pd.DataFrame(
        {
            "NOTE": ["row1", "row1", "row2", "row2"],
            "OTHER": ["othercol1value", "othercol2value", math.nan, "lol"],
            "KEK": [math.nan, math.nan, "kek1val", "kek2val"],
            "AUTHTP": [
                "Corporate Name value",
                "Place (Geographic Name)",
                "Family Name entry",
                "Personal Name entry",
            ],
            "RICO_AUTHTP": ["Agent", "Place", "Agent", "Agent"],
        },
        index=expected_index,
    )

    pd.testing.assert_frame_equal(frame[expected.columns], expected)
