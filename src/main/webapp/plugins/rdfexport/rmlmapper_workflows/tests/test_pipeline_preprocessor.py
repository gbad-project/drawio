from __future__ import annotations

from pathlib import Path
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import pandas as pd  # noqa: E402

from rmlmapper_workflows.pipeline_workflow import (  # noqa: E402
    PipelineCSVPreprocessor,
)


def test_normalise_increment_columns_populates_placeholder_columns(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "dest.csv"

    data = pd.DataFrame(
        [
            {
                "SISN": "row-1",
                "REF_FILE": "REF-A",
                "INDEXPROV_1": "prov-a",
                "INDEXNAME_1": "name-a",
                "INDEXSUB_1": "sub-a",
                "INDEXGEO_1": "geo-a",
                "OFFICEABC_1": "office-a",
                "ABC_REFA_1": "refa-a",
                "DATEOFF_1": "1999-01-01 - 1999-12-31",
                "DATEOFF_1_BEGINNING": "1999-01-01",
                "DATEOFF_1_END": "1999-12-31",
                "GMD_1": "Textual records",
            },
            {
                "SISN": "row-2",
                "REF_FILE": "REF-B",
                "INDEXPROV_2": "prov-b",
                "INDEXNAME_2": "name-b",
                "INDEXSUB_2": "sub-b",
                "INDEXGEO_2": "geo-b",
                "OFFICEABC_2": "office-b",
                "ABC_REFA_2": "refa-b",
                "DATEOFF_2": "2000-01-01 - 2000-12-31",
                "DATEOFF_2_BEGINNING": "2000-01-01",
                "DATEOFF_2_END": "2000-12-31",
                "GMD_2": "Microfilm",
            },
        ]
    )
    data.to_csv(source, index=False)

    preprocessor = PipelineCSVPreprocessor(
        str(source),
        str(destination),
        schema_code="add",
        index_col="SISN",
    )
    preprocessor.source_df = data.copy()

    normalised = preprocessor._normalise_increment_columns(data.copy())
    normalised = normalised.reset_index()

    assert "REFD_FILE" in normalised.columns
    assert list(normalised["REFD_FILE"]) == ["REF-A", "REF-B"]

    assert "INDEXPROV_1..20" in normalised.columns
    assert normalised.loc[0, "INDEXPROV_1..20"] == "prov-a"
    assert normalised.loc[1, "INDEXPROV_1..20"] == "prov-b"

    assert "DATEOFF_1..20_BEGINNING" in normalised.columns
    assert normalised.loc[0, "DATEOFF_1..20_BEGINNING"] == "1999-01-01"

    assert "UUID_INSTANTIATION_1" in normalised.columns
    assert normalised["UUID_INSTANTIATION_1"].nunique() == 1

    assert "UUID_OFFICEABC" in normalised.columns
    assert normalised.loc[0, "UUID_OFFICEABC"] != normalised.loc[1, "UUID_OFFICEABC"]
