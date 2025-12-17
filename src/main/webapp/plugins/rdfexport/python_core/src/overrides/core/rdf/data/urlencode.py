from __future__ import annotations


from python_core.src.draw_io_parser import *  # type: ignore=imported-unused
from aicode.python_core.meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405

# IMPORTANT! Module-level constants are not picked up by meta builder


@override(phase="core", type="rdf", role="data")
def urlencode(text: Any) -> URIRef:
    """
    Encode using `urllib.parse.quote()`, with `unreserved`
    and `unreserved` chars as per RFC 3986 kept safe.

    As `urllib.parse.quote()` puts it:

    > RFC 3986 Uniform Resource Identifier (URI): Generic Syntax lists
    the following (un)reserved characters.
    >
    > unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
    > reserved = gen-delims / sub-delims
    > gen-delims = ":" / "/" / "?" / "#" / "[" / "]" / "@"
    > sub-delims = "!" / "$" / "&" / "'" / "(" / ")"
    >             / "*" / "+" / "," / ";" / "="
    """
    # _invalid_uri_chars = '<>" {}|\\^`'  # from rdflib
    gen_delims = [":", "/", "?", "#", "[", "]", "@"]
    sub_delims = ["!", "$", "&", "'", "(", ")", "*", "+", ",", ";", "="]
    reserved = gen_delims + sub_delims
    safe_chars = "".join(reserved)
    encoded = urllib.parse.quote(str(text), safe=safe_chars)
    return URIRef(encoded)
