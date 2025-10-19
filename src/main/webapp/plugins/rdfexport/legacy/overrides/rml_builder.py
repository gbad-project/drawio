"""Utilities for deriving an RML mapping graph from DrawIO blocks."""

from __future__ import annotations

from typing import Iterable, Mapping, MutableMapping
from urllib.parse import unquote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF


RML = Namespace("http://semweb.mmlab.be/ns/rml#")
RR = Namespace("http://www.w3.org/ns/r2rml#")
QL = Namespace("http://semweb.mmlab.be/ns/ql#")
CSVW = Namespace("http://www.w3.org/ns/csvw#")


def _expand_curie(value: str, prefixes: Mapping[str, str]) -> URIRef | None:
    if ":" not in value:
        return None
    prefix, remainder = value.split(":", 1)
    iri = prefixes.get(prefix)
    if not iri or not remainder:
        return None
    return URIRef(f"{iri}{remainder}")


def _as_resource(
    value: str, prefixes: Mapping[str, str], subject_prefix: str
) -> URIRef | Literal:
    curie_target = _expand_curie(value, prefixes)
    if curie_target is not None:
        return curie_target

    if value.startswith("Rr%3A") or value.startswith("Rr%3a"):
        return URIRef(f"{subject_prefix}{value}")

    decoded = unquote(value)
    if decoded.startswith("http://") or decoded.startswith("https://"):
        return URIRef(decoded)

    return Literal(decoded)


def build_rml_graph(
    *,
    ontology_iri: str,
    base_uri: str | None,
    csv_path: str | None,
    prefixes: MutableMapping[str, str],
    blocks: Mapping[tuple[str, str], Mapping[str, Iterable[str]]],
) -> Graph:
    """Generate an RML graph based on parsed DrawIO blocks."""

    graph = Graph()
    for prefix, iri in prefixes.items():
        if iri:
            graph.bind(prefix, Namespace(iri), replace=True)
    if base_uri:
        graph.bind("", Namespace(base_uri), replace=True)
    graph.bind("rml", RML, replace=True)
    graph.bind("rr", RR, replace=True)
    graph.bind("ql", QL, replace=True)
    graph.bind("csvw", CSVW, replace=True)

    subject_prefix = f"{ontology_iri}#"

    for (encoded_identifier, _), properties in blocks.items():
        subject = URIRef(f"{subject_prefix}{encoded_identifier}")
        for predicate_label, targets in properties.items():
            if predicate_label == "Types":
                predicate = RDF.type
            else:
                predicate = _expand_curie(predicate_label, prefixes)
                if predicate is None:
                    continue
            for target in sorted(targets):
                if predicate_label == "Types":
                    obj = _expand_curie(target, prefixes)
                    if obj is None:
                        obj = URIRef(f"{subject_prefix}{target}")
                    graph.add((subject, predicate, obj))
                    continue
                if target.startswith("rml:") or target.startswith("rr:"):
                    graph.add((subject, predicate, Literal(unquote(target))))
                    continue
                obj = _as_resource(target, prefixes, subject_prefix)
                graph.add((subject, predicate, obj))

    if csv_path:
        logical_source = URIRef(f"{subject_prefix}LogicalSource")
        graph.add((logical_source, RDF.type, RR.LogicalTable))
        graph.add((logical_source, RML.source, Literal(csv_path)))
        graph.add((logical_source, RML.referenceFormulation, QL.CSV))

    return graph
