from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="control")
def dump_blocks(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    dump_path: str,
):
    import json
    from pathlib import Path

    def make_json_safe(obj):
        if isinstance(obj, dict):
            return {
                (
                    k if isinstance(k, (str, int, float, bool, type(None))) else str(k)
                ): make_json_safe(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, (list, tuple, set)):
            return [make_json_safe(i) for i in obj]
        else:
            return obj

    data = {
        "blocks": make_json_safe(blocks),
        "object_properties": make_json_safe(object_properties),
        "datatype_properties": make_json_safe(datatype_properties),
    }
    Path(dump_path).write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
