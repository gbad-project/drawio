from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder

from legacy.overrides.core.rdf.control.serialization_helper import (
    RDFSerializationHelper,
)


@override(phase="core", type="rdf", role="control")
def coerce_to_literal(
    cfg: RDFSerializationHelper,
    value: str | int | float,
) -> Literal:
    """
    Convert a value to a typed Literal.

    Invalid input types raise an UnableToCoerceException.
    """
    UnableToCoerceException = pipeline.core.rdf.data.UnableToCoerceException
    try:

        def normalize(value) -> Literal:
            _infer_literal_type = pipeline.core.rdf.control._infer_literal_type
            if cfg._should_decode_literals:
                if isinstance(value, str):
                    value = urllib.parse.unquote(value)
            if cfg.serialisation_config.infer_type_of_literals:
                literal_object = _infer_literal_type(cfg, value)
            else:
                if value is None:
                    raise UnableToCoerceException(
                        value, Literal, "Unexpected for a Literal candidate"
                    )
                literal_object = Literal(str(value).strip())
            return literal_object

        return normalize(value)
    except UnableToCoerceException:
        raise
    except Exception as e:
        raise UnableToCoerceException(e)
