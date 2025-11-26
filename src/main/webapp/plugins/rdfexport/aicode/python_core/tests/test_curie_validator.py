from __future__ import annotations


import pytest
from rdflib.namespace import NamespaceManager
from rdflib import Graph, Namespace, URIRef

import python_core.src.draw_io_parser as draw_io_parser  # noqa: E402


def _prefixes_to_ns_mgr(prefixes: dict):
    g = Graph()
    namespace_mgr = NamespaceManager(g)
    for prefix, uri in prefixes.items():
        namespace_mgr.bind(prefix, Namespace(uri))

    # bind all prefixes from the dict
    for prefix, uri in prefixes.items():
        namespace_mgr.bind(prefix, Namespace(uri))

    return namespace_mgr


def test_ensure_known_curie_accepts_bound_prefix():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/"

    uri_ref = draw_io_parser.pipeline.core.internal.data.resolve_curie(
        "ex:Thing", _prefixes_to_ns_mgr(prefixes)
    )

    assert uri_ref == URIRef("https://example.org/Thing")


def test_ensure_known_curie_rejects_unknown_prefix():
    prefixes = draw_io_parser.get_prefixes().copy()

    with pytest.raises(draw_io_parser.NotInKnownException):
        draw_io_parser.pipeline.core.internal.data.resolve_curie(
            "unknown:Thing", _prefixes_to_ns_mgr(prefixes)
        )


def test_ensure_known_curie_rejects_empty_reference():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/"

    with pytest.raises(ValueError):
        draw_io_parser.pipeline.core.internal.data.resolve_curie(
            "ex:", _prefixes_to_ns_mgr(prefixes)
        )
