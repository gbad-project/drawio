"""Utilities for preparing legacy CSV fixtures for deterministic RML checks.

These helpers intentionally wrap the ``SourceCSVPreprocessor`` routines that
live in :mod:`legacy.map_schema` so we can reuse the battle-tested column
splitting rules without having to copy them into the Pyodide runtime.  Task 5b
requires the historical Authority and Description/Listing CSV extracts to be
normalised before we compare their legacy RML projections with the output of
the new DrawIO pipeline.  The legacy preprocessing step expands compound
columns (for example ``FINDAID:FINDAIDLINK:FINDAID_URL``) into multiple
columns, but it still leaves a considerable amount of denormalised state –
columns suffixed with ``_2``/``_3``
and so on encode repeating groups that the DrawIO pipeline neither produces nor
consumes.  The helpers below keep the original semantics while coercing the
dataframes into a strict first normal form representation.

The resulting CSVs are stored under
``tests/fixtures/rml/*-normalized.csv`` and feed both the Bun test harness and
the regression generators.  The module lives in ``pyodide_pipeline`` so the
browser runtime can import it directly when we eventually need to perform the
same normalisation step inside Pyodide.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Iterable, Sequence

import pandas as pd

from legacy import map_schema
from legacy.gbad.converter.preprocessors import SourceCSVPreprocessor

NORMALISED_SUFFIX = "-normalized"

logger = logging.getLogger(__name__)

AUTHTP_COLUMN_RE = re.compile(r"^AUTHTP_\d+$")

KNOWN_INCREMENT_PATTERNS = [
    re.compile(r"^INDEXPROV_\d+$"),
    re.compile(r"^INDEXNAME_\d+$"),
    re.compile(r"^INDEXSUB_\d+$"),
    re.compile(r"^DATEOFF_\d+(?:_(BEGINNING|END))?$"),
    re.compile(r"^OFFICEAB_\d+$"),
    re.compile(r"^OFFICEC_\d+$"),
    re.compile(r"^AB_REFA_\d+$"),
    re.compile(r"^C_REFA_\d+$"),
    re.compile(r"^ABC_REFA_\d+$"),
    re.compile(r"^OFFICE_TYPE_\d+$"),
    re.compile(r"^OFFICEABC_\d+$"),
    re.compile(r"^RICO_AUTHTP_[A-Z]+_\d+$"),
]


def _with_suffix(path: Path, suffix: str) -> Path:
    return path.with_name(path.stem + suffix + path.suffix)


def _prepare_destination(source: Path, destination: Path | None) -> Path:
    if destination is not None:
        return destination
    return _with_suffix(source, NORMALISED_SUFFIX)


def _load_dataframe(csv_path: Path, *, index_col: str | None) -> pd.DataFrame:
    kwargs: dict[str, object] = {"dtype": "object"}
    if index_col is not None:
        kwargs["index_col"] = index_col
    return pd.read_csv(csv_path, **kwargs)  # type: ignore[arg-type]


def _identify_generated_columns(
    *,
    dataframe_columns: Sequence[str],
    source_columns: Sequence[str],
) -> Iterable[str]:
    source_column_set = set(source_columns)
    for column in dataframe_columns:
        if column not in source_column_set:
            yield column


def _normalise_preprocessed_csv(
    *,
    source_columns: Sequence[str],
    preprocessed_path: Path,
    destination: Path,
    index_col: str | None,
) -> Path:
    preprocessor = SourceCSVPreprocessor(
        str(preprocessed_path),
        str(destination),
        index_col=index_col or False,
    )

    generated_columns = list(
        _identify_generated_columns(
            dataframe_columns=preprocessor.source_df.columns,
            source_columns=source_columns,
        )
    )
    preprocessor.register_increment_columns(generated_columns)

    authtp_columns = [
        column
        for column in preprocessor.source_df.columns
        if AUTHTP_COLUMN_RE.match(str(column))
    ]
    preprocessor.register_increment_columns(authtp_columns)

    known_columns = [
        column
        for column in preprocessor.source_df.columns
        if any(pattern.match(str(column)) for pattern in KNOWN_INCREMENT_PATTERNS)
    ]
    preprocessor.register_increment_columns(known_columns)

    preprocessor.drop_compound_columns()
    preprocessor.normalise_incremented_columns()
    preprocessor.apply_rico_authtp_mapping()
    preprocessor.drop_columns(
        lambda column: column.startswith("RICO_AUTHTP_") and column != "RICO_AUTHTP"
    )

    preprocessor.dump()
    return destination


def _run_preprocessor(
    processor: Callable[[str, str], None],
    *,
    source: Path,
    preprocessed: Path,
    index_col: str | None,
) -> None:
    try:
        processor(str(source), str(preprocessed))
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning(
            "Falling back to legacy SourceCSVPreprocessor for %s due to %s",
            source,
            exc,
        )
        fallback = SourceCSVPreprocessor(
            str(source), str(preprocessed), index_col=index_col or False
        )
        fallback.dump()


def preprocess_add_csv(
    source: Path,
    destination: Path | None = None,
) -> Path:
    """Return the path to a normalised Description/Listing CSV copy.

    The helper mirrors :func:`legacy.map_schema.add_preprocess` to reuse the
    historical splitting heuristics before enforcing first normal form.
    """

    destination = _prepare_destination(source, destination)
    original_columns = list(_load_dataframe(source, index_col="SISN").columns)
    preprocessed = destination.with_suffix(destination.suffix + ".pre.csv")

    try:
        _run_preprocessor(
            map_schema.add_preprocess,
            source=source,
            preprocessed=preprocessed,
            index_col="SISN",
        )
        return _normalise_preprocessed_csv(
            source_columns=original_columns,
            preprocessed_path=preprocessed,
            destination=destination,
            index_col="SISN",
        )
    finally:
        if preprocessed.exists():
            preprocessed.unlink()


def preprocess_authority_csv(
    source: Path,
    destination: Path | None = None,
) -> Path:
    """Return the path to a normalised Authority CSV copy."""

    destination = _prepare_destination(source, destination)
    original_columns = list(_load_dataframe(source, index_col="SISN").columns)
    preprocessed = destination.with_suffix(destination.suffix + ".pre.csv")

    try:
        _run_preprocessor(
            map_schema.auth_preprocess,
            source=source,
            preprocessed=preprocessed,
            index_col="SISN",
        )
        return _normalise_preprocessed_csv(
            source_columns=original_columns,
            preprocessed_path=preprocessed,
            destination=destination,
            index_col="SISN",
        )
    finally:
        if preprocessed.exists():
            preprocessed.unlink()


def preprocess_csv_for_schema(
    *,
    schema: str,
    source: Path,
    destination: Path | None = None,
) -> Path:
    """Convenience wrapper that dispatches to the schema-specific helper."""

    schema_lower = schema.lower().strip()
    if schema_lower in {"add", "description", "descriptions", "description-listing"}:
        return preprocess_add_csv(source, destination)
    if schema_lower in {"auth", "authority"}:
        return preprocess_authority_csv(source, destination)

    raise ValueError(f"Unsupported schema code: {schema!r}")


__all__ = [
    "NORMALISED_SUFFIX",
    "preprocess_add_csv",
    "preprocess_authority_csv",
    "preprocess_csv_for_schema",
]
