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
from typing import Callable

import pandas as pd

from legacy import map_schema
from legacy.gbad.converter.preprocessors import SourceCSVPreprocessor

NORMALISED_SUFFIX = "-normalized"

logger = logging.getLogger(__name__)


def _drop_denormalised_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a dataframe without columns that encode compound values.

    ``SourceCSVPreprocessor`` keeps the source column around after expanding it
    into individual parts.  The original column name always contains ``:``
    separators and retaining it would reintroduce the very same repeating group
    that the expansion resolved.  Dropping these columns keeps the output
    aligned with the DrawIO parser which never emits them in the first place.
    """

    return df.loc[:, [column for column in df.columns if ":" not in column]]


_REPEATING_GROUP_RE = re.compile(
    r"^(?P<prefix>.+?)(?:_(?P<index>\d+))(?:_(?P<suffix>.*))?$"
)


def _normalise_repeating_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse numbered columns so only the first entry for each group remains.

    Legacy CSV exports frequently encode lists by appending an incrementing
    suffix (``INDEXGEO_1`` … ``INDEXGEO_20``).  The DrawIO pipeline represents
    the very same information through separate mxCell nodes, so the CSV inputs
    we rely on for regression must not contain numbered fields.  Retaining the
    ``*_1`` columns preserves the canonical value while discarding ``*_2`` and
    above eliminates the repeating group entirely.
    """

    columns_to_keep: list[str] = []
    seen_prefixes: set[tuple[str, str | None]] = set()

    for column in df.columns:
        match = _REPEATING_GROUP_RE.match(column)
        if match is None:
            columns_to_keep.append(column)
            continue

        prefix = match.group("prefix")
        index = match.group("index")
        suffix = match.group("suffix") or ""

        key = (prefix, suffix)
        if index != "1":
            # Only the first entry for any repeating group survives.
            if key in seen_prefixes:
                continue
            # If we never encountered ``*_1`` we still drop the current column.
            # The helper prioritises deterministic output over silent fallbacks.
            continue

        seen_prefixes.add(key)
        columns_to_keep.append(column)

    return df.loc[:, columns_to_keep]


def _normalise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all normalisation rules while preserving column order."""

    working = _drop_denormalised_columns(df)
    working = _normalise_repeating_groups(working)
    return working


def _write_dataframe(
    df: pd.DataFrame, destination: Path, *, include_index: bool
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destination, index=include_index)


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


def _normalise_preprocessed_csv(
    *,
    preprocessed_path: Path,
    destination: Path,
    index_col: str | None,
) -> Path:
    dataframe = _load_dataframe(preprocessed_path, index_col=index_col)
    normalised = _normalise_dataframe(dataframe)
    _write_dataframe(normalised, destination, include_index=index_col is not None)
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
    preprocessed = destination.with_suffix(destination.suffix + ".pre.csv")

    try:
        _run_preprocessor(
            map_schema.add_preprocess,
            source=source,
            preprocessed=preprocessed,
            index_col="SISN",
        )
        return _normalise_preprocessed_csv(
            preprocessed_path=preprocessed, destination=destination, index_col="SISN"
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
    preprocessed = destination.with_suffix(destination.suffix + ".pre.csv")

    try:
        _run_preprocessor(
            map_schema.auth_preprocess,
            source=source,
            preprocessed=preprocessed,
            index_col="SISN",
        )
        return _normalise_preprocessed_csv(
            preprocessed_path=preprocessed, destination=destination, index_col="SISN"
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
