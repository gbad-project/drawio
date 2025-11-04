from __future__ import annotations

from legacy.draw_io_parser import (  # type: ignore=imported-unused
    OWL_METACHARACTERS,
    Metacharacter,
    MetacharacterException,
    Replacement,
    _handle_spaces,
    _replace_metacharacter,
)
from meta_builder.drawio_meta_builder import override


@override(phase="pre", type="rdf", role="data")
def _replace_metacharacters(
    identifier: str,
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
) -> str:
    candidate = identifier.strip()
    if "://" in candidate or candidate.lower().startswith(("urn:", "tag:")):
        return candidate

    identifier = candidate

    if " " in identifier:
        if space_substitute is None:
            raise MetacharacterException(
                "The following contains a space, but how to handle spaces in "
                "individual nodes has not been specified (spaces cannot be "
                f"used in OWL IRIs): '{identifier}'. Use the "
                "-m/--metacharacter-substitute and -c/--capitalisation-scheme "
                "options to define how to handle spaces"
            )
        identifier = _handle_spaces(identifier, space_substitute, capitalisation_scheme)
    elif capitalisation_scheme in ["lower-camel", "flat"]:
        identifier = identifier[0].lower() + identifier[1:]
    for metacharacter in OWL_METACHARACTERS:
        identifier = _replace_metacharacter(
            metacharacter, identifier, metacharacter_substitutes
        )
    return identifier
