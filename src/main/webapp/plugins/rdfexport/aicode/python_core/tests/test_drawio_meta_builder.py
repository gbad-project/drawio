import sys
from pathlib import Path
import importlib.util

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

    builder.MODULE_LEVEL_ALIASES_FOR_NEW = True

    try:
        collection = builder.collect_overrides(overrides_dir=str(tmp_path))

        key = ("internal", "control", "core", "individual_blocks")
        assert key in collection.replacements
        assert collection.replacement_count == 1
        assert collection.addition_count == 1
        assert collection.external_imports == []

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
    finally:
        builder.MODULE_LEVEL_ALIASES_FOR_NEW = False


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


def _import_from_path(path: Path, name: str = "drawio_meta"):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def _dotget(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        cur = getattr(cur, part)
    return cur


@pytest.mark.parametrize("use_overrides", [False, True])
def test_pipeline_symbols_and_overrides_exposed(tmp_path, use_overrides):
    # 1) build the module source (captures any current overrides)
    src, overrides = builder.build_output(
        use_overrides=use_overrides, overrides_dir=None
    )
    mod_path = tmp_path / "drawio_meta.py"
    mod_path.write_text(src, encoding="utf-8")

    # 2) import generated module
    dm = _import_from_path(mod_path)

    # 3) all mapped items exist in nested pipeline AND via module-level alias
    for dotted, dt, dr, ph in builder.MAPPING:
        base = dotted.split(".")[-1]
        # nested
        nested_path = f"pipeline.{ph}.{dt}.{dr}.{base}"
        assert hasattr(dm.pipeline, ph), f"missing pipeline.{ph}"
        assert hasattr(_dotget(dm.pipeline, f"{ph}.{dt}"), dr), (
            f"missing {ph}.{dt}.{dr}"
        )
        nested_obj = _dotget(dm, nested_path)
        # module-level alias points to same object
        alias_obj = getattr(dm, base)
        assert nested_obj is alias_obj, f"alias mismatch for {base}"

    # 4) any *new* override additions (not in MAPPING) are available under pipeline.*.*.*.*
    #    (module-level aliases for new items are intentionally OFF by default)
    for (dt, dr, ph), records in overrides.extras.items():
        for rec in records:
            path = f"pipeline.{ph}.{dt}.{dr}.{rec.name}"
            obj = _dotget(dm, path)
            assert obj is not None, f"missing extra override at {path}"
            # sanity: unless explicitly enabled in builder, no top-level alias for new
            assert not hasattr(dm, rec.name), (
                f"unexpected module-level alias for new override {rec.name}; "
                "set MODULE_LEVEL_ALIASES_FOR_NEW=True if desired."
            )


def test_existing_override_external_imports_included():
    generated, overrides = builder.build_output(use_overrides=True, overrides_dir=None)

    assert overrides.external_imports, "expected external imports from overrides"

    for import_line in overrides.external_imports:
        assert import_line in generated, (
            f"missing override import '{import_line}' in generated module"
        )
