from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from gbad.converter.preprocessors import (  # noqa: E402
    INCREMENT_NUMBER_COLUMN,
    SourceCSVPreprocessor,
)


def _write_csv(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def test_source_csv_preprocessor_normalises_numbered_columns(tmp_path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "preprocessed.csv"

    _write_csv(
        source,
        """ID,somecol,othercol_1,othercol_2,kek_1,kek_2
1,alpha,first,second,value-one,value-two
2,beta,,later,solo,second-two
""",
    )

    preprocessor = SourceCSVPreprocessor(str(source), str(destination))
    preprocessor.register_existing_numbered_columns(["othercol", "kek"])
    preprocessor.dump()

    frame = pd.read_csv(destination, dtype="object")

    assert frame.columns.tolist() == [
        "ID",
        "somecol",
        "othercol",
        "kek",
        INCREMENT_NUMBER_COLUMN,
    ]

    assert frame["ID"].tolist() == ["1", "1", "2", "2"]
    assert list(map(int, frame[INCREMENT_NUMBER_COLUMN].tolist())) == [1, 2, 1, 2]

    assert frame["othercol"].tolist()[:2] == ["first", "second"]
    assert pd.isna(frame["othercol"].iloc[2])
    assert frame["othercol"].iloc[3] == "later"
    assert frame["kek"].tolist() == [
        "value-one",
        "value-two",
        "solo",
        "second-two",
    ]


def test_source_csv_preprocessor_derives_rico_authtp(tmp_path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "preprocessed.csv"

    _write_csv(
        source,
        """ID,AUTHTP_1,AUTHTP_2
1,Corporate Name,Geographic Name
""",
    )

    preprocessor = SourceCSVPreprocessor(str(source), str(destination))
    preprocessor.register_existing_numbered_columns(["AUTHTP"])
    preprocessor.dump()

    frame = pd.read_csv(destination, dtype="object")

    assert frame.columns.tolist() == [
        "ID",
        "AUTHTP",
        INCREMENT_NUMBER_COLUMN,
        "RICO_AUTHTP",
    ]
    assert list(map(int, frame[INCREMENT_NUMBER_COLUMN].tolist())) == [1, 2]
    assert frame["AUTHTP"].tolist() == ["Corporate Name", "Geographic Name"]
    assert frame["RICO_AUTHTP"].tolist() == ["Agent", "Place"]
