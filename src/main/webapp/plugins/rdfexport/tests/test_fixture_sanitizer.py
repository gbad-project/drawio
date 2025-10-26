"""Tests for scripts.clean_rr_terms utilities."""

from __future__ import annotations

from importlib import util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_RR_TERMS_PATH = PROJECT_ROOT / "scripts" / "clean_rr_terms.py"

spec = util.spec_from_file_location("clean_rr_terms", CLEAN_RR_TERMS_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load clean_rr_terms module")

clean_rr_terms = util.module_from_spec(spec)
spec.loader.exec_module(clean_rr_terms)
strip_rr_rml_terms = clean_rr_terms.strip_rr_rml_terms

FIXTURE_PAIRS = [
    (
        "General Authority to RiC-O Model_2025-06-25_PZ.drawio",
        "General Authority to RiC-O Model_2025-06-25_PZ_no_rr.drawio",
    ),
    (
        "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.drawio",
        "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ_no_rr.drawio",
    ),
]


@pytest.mark.parametrize(
    "original_name", ['rr:template "value"', "rml:reference literal", "rr:TriplesMap"]
)
def test_strip_rr_rml_terms_removes_tokens(original_name: str) -> None:
    text = f"Prefix {original_name} suffix"
    sanitized = strip_rr_rml_terms(text)
    assert "rr:" not in sanitized
    assert "rml:" not in sanitized
    assert "Prefix" in sanitized
    assert "suffix" in sanitized


@pytest.mark.parametrize("original_name, sanitized_name", FIXTURE_PAIRS)
def test_sanitized_fixture_matches_transformation(
    original_name: str, sanitized_name: str
) -> None:
    repo_root = Path(__file__).resolve().parent
    fixtures_dir = repo_root / "fixtures"
    original_path = fixtures_dir / original_name
    sanitized_path = fixtures_dir / sanitized_name

    original_text = original_path.read_text(encoding="utf-8")
    sanitized_text = sanitized_path.read_text(encoding="utf-8")
    expected_text = strip_rr_rml_terms(original_text)

    assert sanitized_text == expected_text
    assert "rr:" not in sanitized_text
    assert "rml:" not in sanitized_text


@pytest.mark.parametrize(
    "sanitized_name",
    [sanitized for _, sanitized in FIXTURE_PAIRS],
)
def test_sanitized_fixture_still_parses(sanitized_name: str) -> None:
    repo_root = Path(__file__).resolve().parent
    fixtures_dir = repo_root / "fixtures"
    sanitized_path = fixtures_dir / sanitized_name
    # Ensure the sanitized XML is still well-formed.
    from xml.etree import ElementTree as ET

    ET.fromstring(sanitized_path.read_text(encoding="utf-8"))
