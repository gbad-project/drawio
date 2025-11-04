from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="data")
def _verify_is_ric_class(ric_class: str, prefixes: dict[str, str]):
    """Allow templated class tokens to bypass strict CURIE validation."""

    helper = getattr(pipeline.core.rdf.control, "RDFSerializationHelper", None)
    detector = getattr(helper, "_is_template_string", None) if helper else None
    if detector:
        try:
            if detector(str(ric_class)):
                return
        except Exception:
            pass

    pipeline.core.internal.data._ensure_known_curie(
        ric_class,
        prefixes,
        f"Not a known class: {ric_class}",
    )
