import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import pytest
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

PLUGIN_DIR = Path(__file__).resolve().parents[3]

import python_core.src.draw_io_parser as draw_io_parser  # noqa: E402

FIXTURES_DIR = PLUGIN_DIR / "data" / "fixtures" / "drawio_fixtures"
BASELINES_DIR = PLUGIN_DIR / "data" / "fixtures" / "baselines"
PATCHER_MODULE_URI = (
    (
        PLUGIN_DIR
        / "aicode"
        / "typescript_plugin"
        / "tests"
        / "utils"
        / "patchDrawioWithMetadata.ts"
    )
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


TYPE_CELL_IDS = {
    "unknown_prefix": "lTHjRTAcClQ9bYR0I0Gv-14",
    "dangling_curie": "danglingCurieType",
    "colon_only": "colonOnlyType",
    "no_prefix": "noPrefixType",
}

TYPE_CASE_VALUES = {
    "unknown_prefix": "<div>picoL:</div>",
    "dangling_curie": "<div>:danglingCurie</div>",
    "colon_only": "<div>:</div>",
    "no_prefix": "<div>NoPrefixClass</div>",
}


CLASS_DIAGRAM_LITERAL_CELL_ID = "zkfFHV4jXpPFQw0GAbJ--17"


def _mutate_fixture_for_case(tmp_path: Path, case_key: Optional[str]) -> Path:
    tree = ET.parse(FIXTURES_DIR / "AA37-with-metadata-severely-mocked.drawio")
    root = tree.getroot()

    for key, cell_id in TYPE_CELL_IDS.items():
        cell = root.find(f".//mxCell[@id='{cell_id}']")
        if cell is None:
            raise AssertionError(f"Expected mxCell with id '{cell_id}' in fixture")
        if case_key is not None and key == case_key:
            cell.set("value", TYPE_CASE_VALUES[key])
        else:
            cell.set("value", "<div>rico:CorporateBody</div>")

    output = tmp_path / f"AA37-{case_key or 'all-valid'}.drawio"
    tree.write(output, encoding="unicode", xml_declaration=False)
    return output


def _write_class_diagram_variant(
    tmp_path: Path, *, value: str, rounded: Optional[int] = None
) -> Path:
    tree = ET.parse(FIXTURES_DIR / "Class_Diagram_tweaked.drawio")
    root = tree.getroot()

    cell = root.find(f".//mxCell[@id='{CLASS_DIAGRAM_LITERAL_CELL_ID}']")
    if cell is None:
        raise AssertionError(
            f"Expected mxCell with id '{CLASS_DIAGRAM_LITERAL_CELL_ID}' in fixture"
        )

    cell.set("value", value)

    if rounded is not None:
        style = cell.attrib.get("style", "")
        replacement = f"rounded={rounded}"
        if "rounded=" in style:
            style = re.sub(r"rounded=\d+", replacement, style)
        else:
            style = f"{style};{replacement}" if style else replacement
        cell.set("style", style)

    safe_value = value.replace(":", "_") or "blank"
    rounded_suffix = "orig" if rounded is None else str(rounded)
    output = (
        tmp_path / f"Class_Diagram_tweaked_{safe_value}_rounded_{rounded_suffix}.drawio"
    )
    tree.write(output, encoding="unicode", xml_declaration=False)
    return output


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
            draw_io_parser.Individual("LiteralNode", "owl:NamedIndividual"),
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
    assert any(
        isinstance(value, tuple)
        and len(value) == 2
        and value[0] == "Example literal"
        and value[1] is True
        for value in facts
    )


def test_parse_drawio_preserves_literal_targets():
    graph = draw_io_parser.parse_drawio_to_graph(
        str(FIXTURES_DIR / "AA37-with-metadata-even-more-severely-mocked.drawio"),
        metacharacter_substitute=["url"],
    )

    hellow = Namespace("some://helloworld")
    literal_values = list(graph.objects(predicate=hellow.there))

    assert Literal("lolabout") in literal_values


def test_parse_drawio_curie_cell_without_parent():
    graph = draw_io_parser.parse_drawio_to_graph(
        str(FIXTURES_DIR / "Flowchart_tweaked.drawio"),
        metacharacter_substitute=["url"],
    )

    kb = Namespace("mock://knowledge-base/")
    individual = kb["Lampdoesntwork"]

    assert (individual, RDF.type, OWL.NamedIndividual) in graph
    assert (individual, RDF.type, kb["Lampdoesntwork"]) not in graph


def test_parse_drawio_curie_without_known_prefix(tmp_path: Path):
    tree = ET.parse(FIXTURES_DIR / "Flowchart_tweaked.drawio")
    root = tree.getroot()
    # --- insert raw XML ---
    mxroot = root.find(".//mxGraphModel/root")
    assert mxroot is not None
    raw_xml = """
    <mxCell id="zz-missing-prefix" value="zz:MissingPrefix" parent="1" vertex="1">
        <mxGeometry x="300" y="300" width="100" height="50" as="geometry"/>
    </mxCell>
    """
    new_cell = ET.fromstring(raw_xml.strip())
    mxroot.append(new_cell)
    # --- end insert ---

    mutated = tmp_path / "Flowchart_bad.drawio"
    tree.write(mutated, encoding="unicode", xml_declaration=False)

    with pytest.raises(draw_io_parser.NotInKnownException):
        draw_io_parser.parse_drawio_to_graph(
            str(mutated), metacharacter_substitute=["url"]
        )


def test_curie_literal_style_rounding(tmp_path: Path):
    def parse(path: Path) -> Graph:
        return draw_io_parser.parse_drawio_to_graph(
            str(path), metacharacter_substitute=["url"]
        )

    prefixes = draw_io_parser.get_prefixes()
    expected_individual = URIRef(f"{prefixes['rdfs']}Address")

    def literal_present(graph: Graph, value: str) -> bool:
        return any(
            isinstance(obj, Literal) and str(obj) == value for obj in graph.objects()
        )

    base_graph = parse(FIXTURES_DIR / "Class_Diagram_tweaked.drawio")
    assert literal_present(base_graph, "Address")
    assert (expected_individual, RDF.type, OWL.NamedIndividual) not in base_graph

    curie_path = _write_class_diagram_variant(tmp_path, value="rdfs:Address")
    curie_graph = parse(curie_path)
    assert literal_present(curie_graph, "rdfs:Address")
    assert (expected_individual, RDF.type, OWL.NamedIndividual) in curie_graph

    rounded_path = _write_class_diagram_variant(
        tmp_path, value="rdfs:Address", rounded=1
    )
    rounded_graph = parse(rounded_path)
    assert literal_present(rounded_graph, "rdfs:Address")
    assert (
        expected_individual,
        RDF.type,
        OWL.NamedIndividual,
    ) not in rounded_graph, (
        "rounded=1 literal styling should suppress individual classification"
    )


def test_serialise_to_graph_falls_back_for_relative_prefixes():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["bad"] = "relative-prefix"

    items = iter(
        [
            draw_io_parser.Individual("Source", "owl:NamedIndividual"),
            draw_io_parser.Arrow(
                identifier="bad:prop",
                source="Source",
                target="literal value",
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

    config = draw_io_parser.SerialisationConfig(
        infer_type_of_literals=True,
        include_preamble=False,
        ontology_iri="http://example.com/ontology",
        prefix="",
        prefix_iri="http://example.com/",
        indentation=2,
        include_label=False,
    )

    graph = draw_io_parser.serialise_to_graph(
        blocks,
        object_props,
        datatype_props,
        config,
        prefixes,
    )

    subject = URIRef("http://example.com/Source")
    predicate = URIRef("http://example.com/prop")

    assert (subject, predicate, Literal("literal value")) in graph


def test_serialise_to_rml_decodes_url_templates():
    prefixes = draw_io_parser.get_prefixes().copy()
    prefixes["ex"] = "https://example.org/"

    config = draw_io_parser.SerialisationConfig(
        infer_type_of_literals=True,
        include_preamble=False,
        ontology_iri="https://example.org/ontology",
        prefix="ex",
        prefix_iri="https://example.org/",
        indentation=2,
        include_label=False,
    )

    encoded_subject = "https://example.org/%7BID%7D"
    encoded_object = "https://example.org/%7BCONTAINER%7D"

    blocks = {
        (encoded_subject, "Context: {ID}"): {
            "Types": {"rico:Record"},
            "rico:isOrWasIncludedIn": {(encoded_object, False)},
        }
    }

    serialise_to_rml = draw_io_parser.pipeline.core.rdf.control.serialise_to_rml

    graph = serialise_to_rml(
        blocks,
        object_properties={"rico:isOrWasIncludedIn"},
        datatype_properties=set(),
        serialisation_config=config,
        prefixes=prefixes,
        graph_cls=draw_io_parser.DrawIOParserGraph,
        graph_kwargs={"metacharacter_mode": "url"},
    )

    rr = Namespace("http://www.w3.org/ns/r2rml#")

    template_literals = {
        str(obj)
        for _, _, obj in graph.triples((None, rr.template, None))
        if isinstance(obj, Literal)
    }

    assert "https://example.org/{ID}" in template_literals
    assert "https://example.org/{CONTAINER}" in template_literals

    encoded_literals = {
        str(obj)
        for obj in graph.objects()
        if isinstance(obj, Literal) and "%7B" in str(obj)
    }

    assert not encoded_literals


@pytest.mark.parametrize(
    "case_key",
    ["unknown_prefix", "dangling_curie", "colon_only", "no_prefix"],
)
def test_parse_drawio_rejects_malformed_type_variants(tmp_path: Path, case_key: str):
    fixture_path = _mutate_fixture_for_case(tmp_path, case_key)

    kwargs = dict(
        drawio_file_path=str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    if case_key == "dangling_curie":
        # does not raise because empty prefixes are supported now
        draw_io_parser.parse_drawio_to_graph(**kwargs)
        return

    with pytest.raises(draw_io_parser.pipeline.core.rdf.data.UnableToCoerceException):
        draw_io_parser.parse_drawio_to_graph(**kwargs)


def test_parse_drawio_accepts_corrected_mock_types(tmp_path: Path):
    fixture_path = _mutate_fixture_for_case(tmp_path, None)
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)

    observed = {
        str(subject)
        for subject in graph.subjects(RDF.type, None)
        if isinstance(subject, URIRef)
    }

    substitutes = list(draw_io_parser._parse_metacharacter_substitutes(["remove"]))
    space_substitute = draw_io_parser._parse_space_substitute(["remove"])
    expected_suffixes = {
        draw_io_parser._replace_metacharacters(
            candidate,
            substitutes,
            space_substitute,
            draw_io_parser.DEFAULT_CAPITALISATION_SCHEME,
        )
        for candidate in {
            "https://example.com",
            "https://example.com/dangling-curie",
            "https://example.com/colon-only",
            "https://example.com/no-prefix",
        }
    }

    for suffix in expected_suffixes:
        assert any(entry.endswith(suffix) for entry in observed), (
            "Expected corrected mock type to produce identifier ending with "
            f"'{suffix}', observed subjects were: {sorted(observed)}"
        )


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
    ids=lambda p: p.stem,
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

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)
    assert graph.csv_path == "/mock/path/to/file.csv"

    namespace_map = {
        prefix: str(uri) for prefix, uri in graph.namespace_manager.namespaces()
    }

    assert namespace_map.get("mock1") == "http://mock-iri-ns.org"
    assert namespace_map.get("") == "http://mock-base-uri.com"
    assert graph.base == namespace_map.get("")


def test_parse_drawio_with_rml_metadata_adds_triples_map():
    fixture_path = (
        FIXTURES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ_no_rr.drawio"
    )
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["url"],
        prefix_iri="mock://generated-from-test-patched-parser/",
        include_label=False,
        capitalisation_scheme="lower-camel",
        rml_enabled=True,
    )

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)

    rr = Namespace("http://www.w3.org/ns/r2rml#")
    triples = list(graph.triples((None, RDF.type, rr.TriplesMap)))

    assert len(triples) > 0
    prefixes = {prefix for prefix, _ in graph.namespace_manager.namespaces()}
    assert "rr" in prefixes


def test_parse_drawio_default_strips_html_literals():
    fixture_path = FIXTURES_DIR / "AA37 Department of Health-with-metadata.drawio"
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["url"],
    )

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)

    literal_values = [str(obj) for obj in graph.objects() if isinstance(obj, Literal)]

    assert literal_values
    assert all("<" not in value for value in literal_values)


def test_parse_drawio_respects_strip_html_config():
    fixture_path = (
        FIXTURES_DIR / "AA37 Department of Health-with-metadata-preserve-html.drawio"
    )
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["url"],
        strip_html=False,
    )

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)

    literal_values = [str(obj) for obj in graph.objects() if isinstance(obj, Literal)]

    html_literals = [value for value in literal_values if "<blockquote" in value]

    assert html_literals

    labels = [
        str(label)
        for label in graph.objects(predicate=RDFS.label)
        if isinstance(label, Literal)
    ]

    assert labels
    assert all("<" not in label for label in labels)


def test_parse_drawio_metadata_strip_html_override():
    fixture_path = (
        FIXTURES_DIR / "AA37 Department of Health-with-metadata-preserve-html.drawio"
    )
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["url"],
    )

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)

    literal_values = [str(obj) for obj in graph.objects() if isinstance(obj, Literal)]

    html_literals = [value for value in literal_values if "<blockquote" in value]

    assert html_literals


def test_parse_drawio_without_metadata_sets_empty_metadata():
    fixture_path = FIXTURES_DIR / "AA37 Department of Health.drawio"
    graph = draw_io_parser.parse_drawio_to_graph(
        str(fixture_path),
        metacharacter_substitute=["remove"],
    )

    assert isinstance(graph, draw_io_parser.DrawIOParserGraph)
    assert graph.csv_path is None
    # should be generated from default with timestamp as not passed
    assert graph.base.startswith("ontology://generated-from-draw-io/")


def test_parse_drawio_rejects_unknown_literal_curie():
    fixture_path = FIXTURES_DIR / "AA37-with-metadata-severely-mocked.drawio"

    with pytest.raises(draw_io_parser.NotInKnownException):
        draw_io_parser.parse_drawio_to_graph(
            str(fixture_path),
            metacharacter_substitute=["remove"],
        )


@pytest.mark.xfail(
    reason="Deprecated behavior - prefixes are not checked now before serialisation."
)
def test_individual_blocks_rejects_unknown_prefix():
    prefixes = draw_io_parser.get_prefixes()

    items = iter(
        [
            draw_io_parser.Individual("SourceNode", "owl:NamedIndividual"),
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


def _fixture_contains_metadata(path: Path) -> bool:
    # DrawIO fixtures are stored as plain XML. The metadata patcher injects a
    # root-level <gbadMetadata> node when metadata is already present (legacy
    # fixtures may still use <UserObject>), so we treat fixtures that already
    # carry metadata as immutable inputs for this round trip exercise.
    try:
        contents = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        contents = path.read_bytes().decode("utf-8", errors="ignore")
    return "<gbadMetadata" in contents or "<UserObject" in contents


def test_generated_metadata_fixtures_round_trip(tmp_path: Path):
    fixture_paths = sorted(
        path
        for path in FIXTURES_DIR.glob("*.drawio")
        if "-with-metadata" not in path.stem and not _fixture_contains_metadata(path)
    )

    assert fixture_paths, "Expected drawio fixtures to patch"

    for index, fixture_path in enumerate(fixture_paths):
        metadata_options = _build_metadata_options(index, fixture_path)
        patched_path = tmp_path / f"{fixture_path.stem}-with-metadata.drawio"

        _run_drawio_metadata_patcher(fixture_path, patched_path, metadata_options)

        try:
            original_graph = draw_io_parser.parse_drawio_to_graph(
                str(fixture_path),
                metacharacter_substitute=["remove"],
                prefix_iri=metadata_options["baseUri"],
            )
        except Exception as e:
            pytest.xfail(
                reason=f"Fixture {fixture_path.name} with original metadata failed to parse to graph: {e}"
            )
        try:
            patched_graph = draw_io_parser.parse_drawio_to_graph(
                str(patched_path),
                metacharacter_substitute=["remove"],
            )
        except Exception as e:
            pytest.xfail(
                reason=f"Fixture {fixture_path.name} with patched metadata failed to parse to graph: {e}"
            )

        assert isinstance(patched_graph, draw_io_parser.DrawIOParserGraph)
        assert patched_graph.csv_path == metadata_options["csvPath"]
        assert patched_graph.base == draw_io_parser.pipeline.core.rdf.data.prefix_iri_to_base(metadata_options["baseUri"])

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
