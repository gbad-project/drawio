from legacy.draw_io_parser import *
from meta_builder.drawio_meta_builder import override
# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="control")
def _split_curie_old(curie: str) -> tuple[str, str]:
    """This actually is a new override despite _old suffix."""
    if ":" not in curie:
        return "", ""
    prefix, remainder = curie.split(":", 1)
    return prefix, remainder.strip()


@override(phase="core", type="internal", role="data")
def _split_curie(curie: str) -> tuple[str, str]:
    print(
        "[curie_validator] logic from original _split_curie method was manually copied and pasted into a new method, and then the old one was overriden with new; end result same except for this message that was added in override of old with new and will be displayed everywhere the old one was being used. additionally, the new override was placed under a different pipeline namespace class (i.e., control role rather than data) to show the flexibility."
    )
    return pipeline.core.internal.control._split_curie_old(curie)


if __name__ == "__main__":
    # Tests if this actually gets injected - must be run only after bun build:py
    mock_curie = "some:thing"
    print(
        f"Mock input: '{mock_curie}'",
        "Output requested from original _split_curie method:",
        pipeline.core.internal.data._split_curie(mock_curie),
        sep="\n",
    )
