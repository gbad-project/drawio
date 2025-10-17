import sys
from pathlib import Path

import pytest

from .. import drawio_meta_builder as builder


def write_override(tmp_path: Path, name: str, body: str) -> Path:
    file_path = tmp_path / f"{name}.py"
    file_path.write_text(body, encoding="utf-8")
    return file_path


def test_override_decorator_validation():
    with pytest.raises(ValueError):

        @builder.override(type="bogus", role="control", phase="core")
        def _invalid():
            pass

    with pytest.raises(TypeError):
        builder.override(type="internal", role="data", phase="pre")(42)


def test_collect_overrides_replacement_and_addition(tmp_path):
    override_src = """
from meta_builder.drawio_meta_builder import override

@override(type="internal", role="control", phase="core")
def individual_blocks():
    return "replacement sentinel"

@override(type="internal", role="control", phase="core")
def individual_blocks_new():
    return "addition sentinel"
"""
    write_override(tmp_path, "custom_override", override_src)

    collection = builder.collect_overrides(overrides_dir=str(tmp_path))

    key = ("internal", "control", "core", "individual_blocks")
    assert key in collection.replacements
    assert collection.replacement_count == 1
    assert collection.addition_count == 1

    generated, used = builder.build_output(
        use_overrides=True, overrides_dir=str(tmp_path)
    )
    assert "replacement sentinel" in generated
    assert "addition sentinel" in generated
    assert (
        "individual_blocks_new = pipeline.core.internal.control.individual_blocks_new"
        in generated
    )
    # ensure the pipeline namespace contains the new callable
    assert "# BEGIN override custom_override.py.individual_blocks_new" in generated
    assert used.replacement_count == 1
    assert used.addition_count == 1


def test_main_prints_summary(tmp_path, monkeypatch, capsys):
    output_file = tmp_path / "out.py"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drawio_meta_builder",
            "--output",
            str(output_file),
            "--no-overrides",
        ],
    )
    builder.main()
    captured = capsys.readouterr()
    assert f"Wrote {output_file}" in captured.out
    assert "overrides off" in captured.out
    assert output_file.exists()
