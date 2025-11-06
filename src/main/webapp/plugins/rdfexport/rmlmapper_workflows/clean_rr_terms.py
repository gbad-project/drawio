"""Utility to sanitize DrawIO fixtures by removing rr:/rml: syntax, quoted text, and HTML markup."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET
from urllib.parse import unquote, quote
from sys import stdout
import json

from legacy.draw_io_parser import pipeline

# --- utilities ---

# Use parser’s HTML stripper
NodeHTMLParser = pipeline.core.xml.data.NodeHTMLParser

PATTERNS = {
    # Matches rr:/rml: prefixed tokens and any quoted content immediately after
    "RR_QUOTED_PATTERN": (
        re.compile(r'(?:rr):[A-Za-z0-9_]+\s*(?:(?:"|&quot;)([^"&]+)(?:"|&quot;))'),
        r"\1",
    ),
    "RML_QUOTED_PATTERN": (
        re.compile(r'(?:rml):[A-Za-z0-9_]+\s*(?:(?:"|&quot;)([^"&]+)(?:"|&quot;))'),
        r"{\1}",
    ),
    "INCREMENT_NUMBER": (re.compile(r"_\d+\.\.\d+"), ""),
    "RICO_AUTHTP": (re.compile(r"RICO_AUTHTP([^_])"), r"RICO_AUTHTP_TERM\1"),
}


def color(text, code):
    return f"\033[{code}m{text}\033[0m"


def strip_html(text: str) -> str:
    """Use legacy parser’s NodeHTMLParser to strip HTML markup."""
    parser = NodeHTMLParser()
    parser.feed(text)
    return parser.content()


def sanitize_drawio_text(text: str) -> str:
    """Remove rr:/rml: prefixed tokens, following quoted content, and other patches."""
    for _, (pattern, repl) in PATTERNS.items():
        text = pattern.sub(repl, text)
    return text.strip()


def apply_auth_override(cell: ET.Element) -> dict | None:
    """If mxCell matches auth ID, replace its value and return change record."""
    if cell.attrib.get("id") == "gmwnegnUR_CNORKRYM6Y-2":
        before = cell.attrib.get("value", "")
        after = "{RICO_AUTHTP_CLASS}"
        cell.set("value", after)
        return {"id": cell.attrib.get("id"), "before": before, "after": after}
    return None


# --- core processing ---


def sanitize_fixture(input_path: Path, output_path: Path) -> dict:
    """Parse the DrawIO XML, clean mxCell 'value' attributes, and collect stats + before/after pairs."""
    tree = ET.parse(input_path)
    root = tree.getroot()

    total_cells = 0
    total_with_value = 0
    changed = 0
    changes: list[dict] = []

    for cell in root.findall(".//mxCell"):
        total_cells += 1
        value = cell.attrib.get("value")
        if value is None:
            continue
        total_with_value += 1

        ### Hard value replacements ###
        override_change = apply_auth_override(cell)
        if override_change:
            changed += 1
            changes.append(override_change)
            print(
                f"{color('BEFORE:', '1;33')} {color(override_change['before'], '0;37')}\n"
                f"{color('AFTER: ', '1;32')} {color(override_change['after'], '0;36')}\n"
                f"{color('-' * 60, '2;37')}",
                file=stdout,
            )
            continue

        ### Conditional value editing ###
        decoded = unquote(value)
        stripped = strip_html(decoded)
        cleaned = sanitize_drawio_text(stripped)
        encoded = quote(cleaned) if decoded != value else cleaned

        if cleaned != stripped:
            changed += 1
            changes.append(
                {"id": cell.attrib.get("id"), "before": value, "after": encoded}
            )
            print(
                f"{color('BEFORE:', '1;33')} {color(value, '0;37')}\n"
                f"{color('AFTER: ', '1;32')} {color(encoded or '(removed)', '0;36')}\n"
                f"{color('-' * 60, '2;37')}",
                file=stdout,
            )

        cell.set("value", encoded)

    sanitized_text = ET.tostring(root, encoding="unicode")
    output_path.write_text(sanitized_text, encoding="utf-8")

    return {
        "file": input_path.name,
        "total_cells": total_cells,
        "with_value": total_with_value,
        "changed": changed,
        "unchanged": total_with_value - changed,
        "changes": changes,
    }


def sanitize_fixtures(fixtures: Iterable[tuple[Path, Path]]) -> None:
    """Sanitize multiple fixtures and dump JSON summary."""
    stats: list[dict] = []

    for input_path, output_path in fixtures:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = sanitize_fixture(input_path, output_path)
        stats.append(result)

    # --- print combined summary ---
    print(f"\n{color('SUMMARY OF ALL FILES', '1;44')}\n", file=stdout)
    for result in stats:
        print(
            f"{color(result['file'], '1;36')}\n"
            f"  {color('Total mxCells:', '1;34')} {result['total_cells']}\n"
            f"  {color('With value:', '1;33')} {result['with_value']}\n"
            f"  {color('Changed:', '1;32')} {result['changed']}\n"
            f"  {color('Unchanged:', '1;37')} {result['unchanged']}\n"
            f"{color('-' * 60, '2;37')}",
            file=stdout,
        )
    print(f"{color('DONE ✅', '1;32')}\n", file=stdout)

    # --- dump JSON ---
    dump_path = Path(__file__).resolve().parent / "rr_terms.json"
    dump_payload = {
        "summary": stats,
        "totals": {
            "files": len(stats),
            "total_cells": sum(s["total_cells"] for s in stats),
            "total_with_value": sum(s["with_value"] for s in stats),
            "total_changed": sum(s["changed"] for s in stats),
            "total_unchanged": sum(s["unchanged"] for s in stats),
        },
    }
    dump_path.write_text(
        json.dumps(dump_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{color('JSON report written to:', '1;35')} {dump_path}\n", file=stdout)


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
