import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF

LEGACY_DIR = Path(__file__).resolve().parents[1]
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import draw_io_parser  # noqa: E402

FIXTURES_DIR = LEGACY_DIR.parent / "tests" / "fixtures"
BASELINES_DIR = LEGACY_DIR.parent / "tests" / "baselines"
PATCHER_MODULE_URI = (
    (LEGACY_DIR.parent / "tests" / "utils" / "patchDrawioWithMetadata.ts")
    .resolve()
    .as_uri()
)
PATCHER_EVAL_SCRIPT = (
    f"""
import {{ readFileSync, writeFileSync }} from 'node:fs';
import {{ patchDrawioWithMetadata }} from '{PATCHER_MODULE_URI}';

const [, inputPath, outputPath, optionsJson] = process.argv;
const options = JSON.parse(optionsJson);

const patched = patchDrawioWithMetadata(readFileSync(inputPath, 'utf8'), options);
writeFileSync(outputPath, patched);
"""
).strip()


def test_individual_blocks_accepts_declared_prefix_curie():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/custom#"

    items = iter(
        [
            draw_io_parser.Individual("SourceNode", "ex:CustomClass"),
            draw_io_parser.Individual("TargetNode", "ex:OtherClass"),
            draw_io_parser.Arrow(
                identifier="ex:connectsTo",
                source="SourceNode",
                target="TargetNode",
                is_datatype=False,
            ),
        ]
    )

    blocks, object_props, datatype_props = draw_io_parser.individual_blocks(
        items,
        [],
        None,
        draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
        prefixes,
    )

    assert ("SourceNode", "SourceNode") in blocks
    assert "ex:CustomClass" in blocks[("SourceNode", "SourceNode")]["Types"]
    assert "ex:connectsTo" in object_props
    assert not datatype_props


def test_individual_blocks_tracks_datatype_properties():
    prefixes = draw_io_parser.get_prefixes()

    items = iter(
        [
            draw_io_parser.Individual("LiteralNode", "rico:Thing"),
            draw_io_parser.Arrow(
                identifier="rdfs:label",
                source="LiteralNode",
                target="Example literal",
                is_datatype=True,
            ),
        ]
    )

    blocks, object_props, datatype_props = draw_io_parser.individual_blocks(
        items,
        [],
        None,
        draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
        prefixes,
    )

    assert not object_props
    assert "rdfs:label" in datatype_props
    facts = blocks[("LiteralNode", "LiteralNode")]["rdfs:label"]
    assert "Example literal" in facts


def _normalise_graph(graph: Graph) -> Graph:
    filtered = Graph()
    for triple in graph:
        subject, predicate, obj = triple
        if predicate == RDF.type and obj in {
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.Ontology,
        }:
            continue
        if predicate == OWL.imports:
            continue
        filtered.add(triple)
    return filtered


@pytest.mark.parametrize(
    "baseline_path",
    sorted(BASELINES_DIR.glob("*.nt")),
)
def test_parse_drawio_matches_baseline_graphs(baseline_path: Path):
    fixture_path = FIXTURES_DIR / f"{baseline_path.stem}.drawio"
    expected = Graph()
    expected.parse(baseline_path, format="nt")

    actual = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        ontology_iri="ontology://generated-from-draw-io/mock",
        metacharacter_substitute=["url"],
    )

    expected_normalised = _normalise_graph(expected)
    actual_normalised = _normalise_graph(actual)

    assert actual_normalised.isomorphic(expected_normalised)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "knut_olborgs_forskningsnotater.drawio",
        "koronakommisjonen.drawio",
    ],
)
def test_parse_drawio_accepts_previous_unknown_properties(fixture_name: str):
    fixture_path = FIXTURES_DIR / fixture_name
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    assert isinstance(graph, Graph)
    assert len(graph) > 0


def test_parse_drawio_with_metadata_exposes_namespace_and_csv_path():
    fixture_path = FIXTURES_DIR / "AA37 Department of Health-with-metadata.drawio"
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    assert isinstance(graph, draw_io_parser.DrawioParserGraph)
    assert graph.csv_path == "/mock/path/to/file.csv"

    namespace_map = {
        prefix: str(uri) for prefix, uri in graph.namespace_manager.namespaces()
    }

    assert namespace_map.get("mock1") == "http://mock-iri-ns.org"
    assert namespace_map.get("") == "http://mock-base-uri.com"
    assert graph.base is None


def test_parse_drawio_without_metadata_sets_empty_metadata():
    fixture_path = FIXTURES_DIR / "AA37 Department of Health.drawio"
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    assert isinstance(graph, draw_io_parser.DrawioParserGraph)
    assert graph.csv_path is None
    assert graph.base is None


def test_parse_drawio_raises_for_arrow_with_unknown_prefix():
    fixture_path = FIXTURES_DIR / "AA37-with-metadata-severely-mocked.drawio"

    with pytest.raises(draw_io_parser.UndefinedPrefixException) as exc_info:
        draw_io_parser.parse_drawio_to_graph(
            str(fixture_path),
            metacharacter_substitute=["remove"],
        )

    assert "picoL" in str(exc_info.value)


def test_parse_drawio_raises_for_literal_with_unknown_prefix():
    fixture_path = FIXTURES_DIR / "General_Authority_bleep_mock.drawio"

    with pytest.raises(draw_io_parser.UndefinedPrefixException) as exc_info:
        draw_io_parser.parse_drawio_to_graph(
            str(fixture_path),
            metacharacter_substitute=["remove"],
        )

    assert "bleep" in str(exc_info.value)


def test_individual_blocks_rejects_unknown_prefix():
    prefixes = draw_io_parser.get_prefixes()

    items = iter(
        [
            draw_io_parser.Individual("SourceNode", "rico:Thing"),
            draw_io_parser.Arrow(
                identifier="unknown:prop",
                source="SourceNode",
                target="Value",
                is_datatype=True,
            ),
        ]
    )

    with pytest.raises(draw_io_parser.NotInKnownException):
        draw_io_parser.individual_blocks(
            items,
            [],
            None,
            draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
            prefixes,
        )


def _run_drawio_metadata_patcher(
    source: Path, destination: Path, options: dict
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "bun",
            "--eval",
            PATCHER_EVAL_SCRIPT,
            str(source),
            str(destination),
            json.dumps(options),
        ],
        check=True,
    )


def _build_metadata_options(index: int, fixture_path: Path) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "-", fixture_path.stem.lower()).strip("-")
    if not slug:
        slug = f"fixture-{index}"

    csv_path = f"/tmp/{slug}.csv"
    base_uri = f"http://example.org/{slug}/"
    return {
        "csvPath": csv_path,
        "baseUri": base_uri,
        "label": f"{fixture_path.stem} metadata",
        "preamble": [
            {
                "rdfPrefix": f"fx{index}",
                "rdfIRI": f"http://example.org/{slug}/vocab#",
            },
            {
                "rdfPrefix": f"data{index}",
                "rdfIRI": f"http://example.org/{slug}/data/",
            },
        ],
    }


def test_generated_metadata_fixtures_round_trip(tmp_path: Path):
    fixture_paths = sorted(
        path
        for path in FIXTURES_DIR.glob("*.drawio")
        if "-with-metadata" not in path.stem
    )

    assert fixture_paths, "Expected drawio fixtures to patch"

    for index, fixture_path in enumerate(fixture_paths):
        raw_xml = fixture_path.read_text(encoding="utf-8")
        metadata_prefixes, base_uri, *_ = draw_io_parser._extract_drawio_metadata(
            raw_xml
        )
        if metadata_prefixes or base_uri:
            continue

        metadata_options = _build_metadata_options(index, fixture_path)
        patched_path = tmp_path / f"{fixture_path.stem}-with-metadata.drawio"

        _run_drawio_metadata_patcher(fixture_path, patched_path, metadata_options)

        original_graph = draw_io_parser.parse_drawio_to_graph(
            str(fixture_path),
            metacharacter_substitute=["remove"],
            prefix_iri=metadata_options["baseUri"],
        )
        patched_graph = draw_io_parser.parse_drawio_to_graph(
            str(patched_path),
            metacharacter_substitute=["remove"],
        )

        assert isinstance(patched_graph, draw_io_parser.DrawioParserGraph)
        assert patched_graph.csv_path == metadata_options["csvPath"]
        assert patched_graph.base is None

        namespace_map = {
            prefix: str(uri)
            for prefix, uri in patched_graph.namespace_manager.namespaces()
        }
        for preamble_entry in metadata_options["preamble"]:
            assert (
                namespace_map.get(preamble_entry["rdfPrefix"])
                == preamble_entry["rdfIRI"]
            )
        assert namespace_map.get("") == metadata_options["baseUri"]

        assert _normalise_graph(patched_graph).isomorphic(
            _normalise_graph(original_graph)
        )
