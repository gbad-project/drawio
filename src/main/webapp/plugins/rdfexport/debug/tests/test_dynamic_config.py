import json
import sys
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PLUGIN_DIR.parents[4]
for candidate in (REPO_ROOT, PLUGIN_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from debug.__main__ import (  # noqa: E402
    DEFAULT_LEGACY_COMMIT,
    DEFAULT_METADATA_ATTRIBUTES,
    DEFAULT_PREFIXES,
    Debugger,
    ScenarioConfig,
)

FIXTURES_DIR = PLUGIN_DIR / "tests" / "fixtures"


def build_config(
    slug: str,
    drawio_path: Path,
    *,
    metadata: dict[str, object | None],
    parser_config: dict[str, object],
) -> ScenarioConfig:
    metadata_attributes = dict(DEFAULT_METADATA_ATTRIBUTES)
    metadata_attributes.update(metadata)

    return ScenarioConfig(
        slug=slug,
        drawio_path=drawio_path,
        legacy_commit=DEFAULT_LEGACY_COMMIT,
        serialization_format="nt",
        metadata_attributes=metadata_attributes,
        prefixes=list(DEFAULT_PREFIXES),
        parser_config=parser_config,
    )


def test_dynamic_metadata_and_parser_payloads(monkeypatch: pytest.MonkeyPatch):
    debugger = Debugger(FIXTURES_DIR)
    slug = f"pytest-dynamic-{uuid4().hex[:8]}"
    drawio_path = FIXTURES_DIR / "AA37 Department of Health.drawio"

    metadata_overrides = {
        "stripHtml": False,
        "customAttribute": "example",
    }
    parser_overrides = {
        "strip_html": False,
        "strict_mode": True,
        "metacharacter_substitute": ["remove", "x=y"],
        "future_option": "enabled",
    }

    config = build_config(
        slug,
        drawio_path,
        metadata=metadata_overrides,
        parser_config=parser_overrides,
    )

    original_xml = drawio_path.read_text(encoding="utf-8")
    patched_xml = debugger._apply_metadata_overrides(original_xml, config)

    root = ET.fromstring(patched_xml)
    metadata_element = root.find(".//gbadMetadata[@id='0']")
    if metadata_element is None:
        metadata_element = root.find(".//UserObject[@id='0']")
    assert metadata_element is not None
    assert metadata_element.get("stripHtml") == "false"
    assert metadata_element.get("customAttribute") == "example"

    captured: dict[str, object] = {}

    class DummyResult:
        def __init__(self) -> None:
            self.stdout = json.dumps({"pipeline": "", "plugin": ""})
            self.stderr = ""

    def fake_run(*args, **kwargs):
        command = args[0]
        config_path = Path(command[-1])
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        captured["payload"] = payload
        return DummyResult()

    monkeypatch.setattr("debug.__main__.subprocess.run", fake_run)

    debugger._run_ts_pipeline(patched_xml, config)

    payload = captured["payload"]
    metadata_payload = payload["metadataAttributes"]
    assert metadata_payload["stripHtml"] is False
    assert metadata_payload["customAttribute"] == "example"

    parser_payload = payload["parserConfig"]
    assert parser_payload["strict_mode"] is True
    assert parser_payload["future_option"] == "enabled"
    assert parser_payload["metacharacter_substitute"] == ["remove", "x=y"]

    preamble_payload = payload["preamble"]
    assert preamble_payload == [
        {"prefix": prefix, "iri": iri} for prefix, iri in DEFAULT_PREFIXES
    ]
