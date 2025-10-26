"""Utilities for sanitizing DrawIO fixtures by removing rr:/rml: syntax."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

RR_RML_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(rr|rml):[A-Za-z0-9_]+(?:[ \t]*)")


def strip_rr_rml_terms(text: str) -> str:
    """Return *text* with rr:/rml: prefixed tokens removed.

    The removal keeps surrounding whitespace intact with the exception of
    redundant spaces immediately following the token. Tabs are treated in the
    same way, while newlines and other characters are preserved.
    """

    return RR_RML_TOKEN_PATTERN.sub("", text)


def sanitize_fixture(input_path: Path, output_path: Path) -> str:
    """Sanitize *input_path* and write the result to *output_path*.

    Returns the sanitized text for convenience.
    """

    original_text = input_path.read_text(encoding="utf-8")
    sanitized_text = strip_rr_rml_terms(original_text)
    output_path.write_text(sanitized_text, encoding="utf-8")
    return sanitized_text


def sanitize_fixtures(fixtures: Iterable[tuple[Path, Path]]) -> None:
    """Sanitize multiple fixtures given as (input_path, output_path) pairs."""

    for input_path, output_path in fixtures:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sanitize_fixture(input_path, output_path)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    fixtures_dir = repo_root / "tests" / "fixtures"

    pairs = [
        (
            fixtures_dir / "General Authority to RiC-O Model_2025-06-25_PZ.drawio",
            fixtures_dir
            / "General Authority to RiC-O Model_2025-06-25_PZ_no_rr.drawio",
        ),
        (
            fixtures_dir
            / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.drawio",
            fixtures_dir
            / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ_no_rr.drawio",
        ),
    ]

    sanitize_fixtures(pairs)
