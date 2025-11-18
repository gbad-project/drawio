from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="core", type="rdf", role="data")
class UnableToCoerceException(Exception):
    """
    Can be raised on any attempted coercion to any set of target types.
    """

    default_message = "Failed to coerce {0!r} to {1!s}"

    def __init__(self, candidate: Any, target: set[type] | type, message: str) -> None:
        target_types = target if isinstance(target, set) else {target}
        self.message = self.default_message.format(
            candidate, str([t.__name__ for t in target_types])
        )
        if message:
            self.message += f": {message}"
        super().__init__(self.message)


@override(phase="core", type="rdf", role="data")
def _infer_literal_type(literal: str | int | float) -> Literal:
    """
    Augmented rdflib port of `_infer_type` function from the
    original `5d85cf0` Draw.io parser.

    Return type adjusted accordingly to rdflib.term.Literal.

    Augmentations:

    - Fixed an incidental IndexError when strings were sliced.
    - Added support for int | float inputs in addition to str.
    - Raises UnableToCoerceException if input is of unexpected type.
    """
    UnableToCoerceException = pipeline.core.rdf.data.UnableToCoerceException

    expected_types = {str, int, float}
    if isinstance(literal, int) or literal.isnumeric():
        return Literal(literal, datatype=XSD.integer)
    elif isinstance(literal, float):
        return Literal(literal, datatype=XSD.float)
    elif isinstance(literal, str):
        pass
    else:
        if not any(isinstance(literal, t) for t in expected_types):
            raise UnableToCoerceException(
                literal,
                expected_types,
                "Not any of expected Python types for a Literal candidate",
            )
    try:
        datetime.strptime(literal, "%Y-%m-%d")
        return Literal(literal, datatype=XSD.date)
    except ValueError:
        pass
    try:
        if literal[-1] == "Z":
            try:
                datetime.strptime(literal[-1], "%Y-%m-%dT%H-%M-%S")
                return Literal(literal, datatype=XSD.dateTime)
            except ValueError:
                pass
        elif literal[-6] == "+" or literal[-6] == "-":
            try:
                datetime.strptime(literal[:-6], "%Y-%m-%dT%H-%M-%S")
                datetime.strptime(literal[-5:], "%H:%M")
                return Literal(literal, datatype=XSD.dateTime)
            except ValueError:
                pass
        else:
            try:
                datetime.strptime("%Y-%m-%dT%H-%M-%S", literal)
                return Literal(literal, datatype=XSD.dateTime)
            except ValueError:
                pass
    except IndexError:
        pass
    return Literal(literal)
