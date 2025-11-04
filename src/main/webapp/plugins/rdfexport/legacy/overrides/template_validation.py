from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="data")
def _verify_is_ric_class(ric_class: str, prefixes: dict[str, str]):
    detector = None
    if isinstance(ric_class, str) and "{" in ric_class and "}" in ric_class:
        RMLSerializer = getattr(pipeline.core.rdf.control, "RMLSerializer", None)
        detector = getattr(RMLSerializer, "detect_string_template", None)
        if callable(detector):
            try:
                if detector(ric_class):
                    return
            except ValueError:
                pass
    pipeline.core.internal.data._ensure_known_curie(
        ric_class, prefixes, f"Not a known class: {ric_class}"
    )
