from __future__ import annotations


import pytest
from rdflib.namespace import NamespaceManager

import python_core.src.draw_io_parser as draw_io_parser  # noqa: E402


def test_ensure_known_curie_accepts_bound_prefix(monkeypatch):
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/"

    called = False
    original_expand = NamespaceManager.expand_curie

    def tracking_expand(self, curie: str, *args, **kwargs):
        nonlocal called
        called = True
        return original_expand(self, curie, *args, **kwargs)

    monkeypatch.setattr(NamespaceManager, "expand_curie", tracking_expand)

    prefix, reference = draw_io_parser._split_curie("ex:Thing", prefixes)

    assert called
    assert prefix == "ex"
    assert reference == "Thing"


def test_ensure_known_curie_rejects_unknown_prefix():
    prefixes = draw_io_parser.get_prefixes().copy()

    with pytest.raises(draw_io_parser.NotInKnownException):
        draw_io_parser._split_curie("unknown:Thing", prefixes)


def test_ensure_known_curie_rejects_empty_reference():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/"

    with pytest.raises(ValueError):
        draw_io_parser._split_curie("ex:", prefixes)
