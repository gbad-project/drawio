"""Helpers for running legacy and pipeline RMLMapper workflows."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.compare import to_isomorphic
from rdflib.namespace import OWL, RDF

PLUGIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PLUGIN_DIR.parents[4]
LEGACY_DIR = PLUGIN_DIR / "legacy"
for candidate in (REPO_ROOT, PLUGIN_DIR, LEGACY_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

import map_schema  # type: ignore  # noqa: E402
from legacy.tests.regenerate_baselines import _serialise_graph  # noqa: E402
from debug.__main__ import (  # noqa: E402
    DEFAULT_BASE_URI,
    DEFAULT_METADATA_ATTRIBUTES,
    DEFAULT_PREFIXES,
    Debugger,
    ScenarioConfig,
)

TOOLS_DIR = PLUGIN_DIR / "tools" / "rmlmapper"
MANIFEST_PATH = TOOLS_DIR / "manifest.json"
FIXTURES_DIR = PLUGIN_DIR / "tests" / "fixtures"
BASELINES_DIR = PLUGIN_DIR / "tests" / "baselines"


@dataclass(frozen=True)
class Manifest:
    java_bin: Path
    java_home: Path
    rmlmapper_jar: Path


@dataclass(frozen=True)
class FixtureConfig:
    schema_code: str
    slug: str
    drawio_name: str
    normalized_drawio_name: str
    csv_path: Path
    normalized_csv_path: Path
    baseline_nt: Path

    @property
    def schema_subdir(self) -> str:
        if self.schema_code.lower() in {"auth", "authority"}:
            return "authority"
        if self.schema_code.lower() in {"add", "description"}:
            return "description-listings"
        raise ValueError(f"Unsupported schema code: {self.schema_code}")

    @property
    def drawio_path(self) -> Path:
        return FIXTURES_DIR / self.drawio_name

    @property
    def normalized_drawio_path(self) -> Path:
        return FIXTURES_DIR / self.normalized_drawio_name


@dataclass
class WorkflowResult:
    rml_path: Path
    turtle_path: Path
    rml_graph: Graph
    turtle_graph: Graph
    source: str | None = None


FIXTURES: tuple[FixtureConfig, ...] = (
    FixtureConfig(
        schema_code="auth",
        slug="general-authority-to-ric-o-model-2025-06-25-pz",
        drawio_name="General Authority to RiC-O Model_2025-06-25_PZ.drawio",
        normalized_drawio_name="General Authority to RiC-O Model_2025-06-25_PZ_no_rr.drawio",
        csv_path=FIXTURES_DIR
        / "rml"
        / "General Authority to RiC-O Model_2025-06-25_PZ.csv",
        normalized_csv_path=FIXTURES_DIR
        / "rml"
        / "General Authority to RiC-O Model_2025-06-25_PZ-normalized.csv",
        baseline_nt=BASELINES_DIR / "General Authority to RiC-O Model_2025-06-25_PZ.nt",
    ),
    FixtureConfig(
        schema_code="add",
        slug="general-add-descriptions-and-listings-to-ric-o-model-2025-06-20-pz",
        drawio_name="General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.drawio",
        normalized_drawio_name="General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ_no_rr.drawio",
        csv_path=FIXTURES_DIR
        / "rml"
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.csv",
        normalized_csv_path=FIXTURES_DIR
        / "rml"
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ-normalized.csv",
        baseline_nt=BASELINES_DIR
        / "General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.nt",
    ),
)


def ensure_rmlmapper_setup() -> Manifest:
    """Ensure the isolated Java + RMLMapper environment exists."""

    setup_script = PLUGIN_DIR / "scripts" / "setup_rmlmapper.sh"
    if not MANIFEST_PATH.exists():
        subprocess.run(["bash", str(setup_script)], cwd=PLUGIN_DIR, check=True)
    else:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if (
            not Path(data.get("java_bin", "")).exists()
            or not Path(data.get("rmlmapper_jar", "")).exists()
        ):
            subprocess.run(["bash", str(setup_script)], cwd=PLUGIN_DIR, check=True)

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    java_bin = Path(data["java_bin"])
    java_home = Path(data["java_home"])
    jar_path = Path(data["rmlmapper_jar"])

    return Manifest(java_bin=java_bin, java_home=java_home, rmlmapper_jar=jar_path)


def _write_canonical_ttl(graph: Graph, destination: Path) -> Path:
    canonical_nt = _serialise_graph(graph)
    canonical_graph = Graph()
    canonical_graph.parse(data=canonical_nt, format="nt")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_graph.serialize(format="turtle"), encoding="utf-8")
    return destination


def _run_rmlmapper(
    manifest: Manifest, map_path: Path, output_path: Path, *, cwd: Path | None = None
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(manifest.java_bin),
        "-jar",
        str(manifest.rmlmapper_jar),
        "-m",
        str(map_path),
        "-s",
        "turtle",
        "-o",
        str(output_path),
    ]
    env = os.environ.copy()
    env.setdefault("JAVA_HOME", str(manifest.java_home))
    subprocess.run(command, check=True, cwd=cwd, env=env)


def run_map_schema_workflow(
    fixture: FixtureConfig,
    *,
    manifest: Manifest,
    csv_path: Path,
    output_dir: Path,
) -> WorkflowResult:
    """Generate RML using legacy map_schema and project it via RMLMapper."""

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        schema_dir = temp_dir / "gbad" / "schema" / fixture.schema_subdir
        schema_dir.mkdir(parents=True, exist_ok=True)

        baseline_graph = Graph()
        baseline_graph.parse(fixture.baseline_nt, format="nt")
        ttl_name = fixture.drawio_path.stem + ".ttl"
        ttl_path = schema_dir / ttl_name
        _write_canonical_ttl(baseline_graph, ttl_path)

        source_dir = temp_dir / "gbad" / "mapping" / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        preprocessed_dir = source_dir / "preprocessed"
        preprocessed_dir.mkdir(parents=True, exist_ok=True)
        csv_dest = source_dir / csv_path.name
        shutil.copy(csv_path, csv_dest)

        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)
            map_schema.__init__(fixture.schema_code, csv_dest.name)
        finally:
            os.chdir(original_cwd)

        generated_rml = schema_dir / csv_path.stem / f"{ttl_path.stem}.rml"
        if not generated_rml.exists():
            raise FileNotFoundError(
                f"map_schema did not produce expected RML at {generated_rml}"
            )

        rml_graph = Graph()
        rml_graph.parse(generated_rml, format="turtle")
        rml_output = output_dir / f"map-schema-{csv_path.stem}.rml.ttl"
        _write_canonical_ttl(rml_graph, rml_output)

        turtle_output = output_dir / f"map-schema-{csv_path.stem}.output.ttl"
        _run_rmlmapper(manifest, rml_output, turtle_output, cwd=temp_dir)

        turtle_graph = Graph()
        turtle_graph.parse(turtle_output, format="turtle")

    return WorkflowResult(
        rml_path=rml_output,
        turtle_path=turtle_output,
        rml_graph=rml_graph,
        turtle_graph=turtle_graph,
        source=f"map-schema:{csv_path.name}",
    )


def run_pipeline_workflow(
    fixture: FixtureConfig,
    *,
    manifest: Manifest,
    drawio_path: Path,
    csv_path: Path,
    output_dir: Path,
    persist_results: bool = False,
) -> WorkflowResult:
    """Generate RML via debugger pipeline and project it via RMLMapper."""

    debugger = Debugger(FIXTURES_DIR)
    slug = f"rmlmapper-{fixture.slug}-{drawio_path.stem}"

    metadata = dict(DEFAULT_METADATA_ATTRIBUTES)
    metadata["csvPath"] = str(csv_path.resolve())
    metadata.setdefault("baseUri", DEFAULT_BASE_URI)

    config = ScenarioConfig(
        slug=slug,
        drawio_path=drawio_path,
        legacy_commit="HEAD",
        serialization_format="turtle",
        metadata_attributes=metadata,
        prefixes=list(DEFAULT_PREFIXES),
        parser_config={"rml_enabled": True},
    )

    debugger._run_scenario(config, skip_ts=True)
    results_dir = debugger.results_dir / slug

    try:
        pipeline_rml = results_dir / "py_legacy.ttl"
        pipeline_source = "py_legacy(head)"
        if not pipeline_rml.exists():
            pipeline_rml = results_dir / "ts_pipeline.ttl"
            pipeline_source = "ts_pipeline"
        if not pipeline_rml.exists():
            raise FileNotFoundError(
                f"Pipeline RML output missing for scenario {slug}: {pipeline_rml}"
            )

        rml_graph = Graph()
        rml_graph.parse(pipeline_rml, format="turtle")
        csv_literal = Literal(str(csv_path.resolve()))
        for triples_map, _, source_value in list(
            rml_graph.triples((None, RML_NAMESPACE.source, None))
        ):
            if source_value == csv_literal:
                continue
            rml_graph.remove((triples_map, RML_NAMESPACE.source, source_value))
            rml_graph.add((triples_map, RML_NAMESPACE.source, csv_literal))
        rml_output = output_dir / "pipeline.rml.ttl"
        _write_canonical_ttl(rml_graph, rml_output)

        turtle_output = output_dir / "pipeline.output.ttl"
        _run_rmlmapper(manifest, rml_output, turtle_output, cwd=None)

        turtle_graph = Graph()
        turtle_graph.parse(turtle_output, format="turtle")
    finally:
        if not persist_results:
            shutil.rmtree(results_dir, ignore_errors=True)
            debugger._map_data.get("scenarios", {}).pop(slug, None)
            debugger._write_map()

    return WorkflowResult(
        rml_path=rml_output,
        turtle_path=turtle_output,
        rml_graph=rml_graph,
        turtle_graph=turtle_graph,
        source=f"pipeline:{pipeline_source}",
    )


def graphs_are_isomorphic(graph_a: Graph, graph_b: Graph) -> bool:
    """Return ``True`` if the graphs are RDF-isomorphic."""

    return to_isomorphic(graph_a) == to_isomorphic(graph_b)


def collect_workflow_pairs(
    manifest: Manifest,
    *,
    output_root: Path,
    csv_attributes: Iterable[str],
) -> dict[str, dict[str, WorkflowResult]]:
    """Run workflows for all fixtures and return results grouped by slug."""

    results: dict[str, dict[str, WorkflowResult]] = {}
    for fixture in FIXTURES:
        fixture_dir = output_root / fixture.slug
        fixture_results: dict[str, WorkflowResult] = {}
        for attr in csv_attributes:
            fixture_csv = getattr(fixture, attr, None)
            if fixture_csv is None:
                raise AttributeError(
                    f"Fixture {fixture.slug} does not define CSV attribute {attr}"
                )
            workflow = run_map_schema_workflow(
                fixture,
                manifest=manifest,
                csv_path=fixture_csv,
                output_dir=fixture_dir / "map-schema" / Path(fixture_csv).stem,
            )
            fixture_results[f"map-schema-{Path(fixture_csv).stem}"] = workflow

        pipeline_workflow = run_pipeline_workflow(
            fixture,
            manifest=manifest,
            drawio_path=fixture.normalized_drawio_path,
            csv_path=fixture.normalized_csv_path,
            output_dir=fixture_dir / "pipeline",
            persist_results=True,
        )
        fixture_results["pipeline"] = pipeline_workflow
        results[fixture.slug] = fixture_results
    return results


RML_NAMESPACE = Namespace("http://semweb.mmlab.be/ns/rml#")


@dataclass(frozen=True)
class CanonicalComparison:
    """Canonicalised comparison data for map_schema vs pipeline outputs."""

    map_graph: Graph
    pipeline_graph: Graph
    shared_graph: Graph
    map_only_count: int
    pipeline_only_count: int


def _normalise_template_iri(value: URIRef) -> str:
    text = str(value)
    if "#Rr%3Atemplate%20%22" in text:
        return text.replace("#Rr%3Atemplate%20%22", "#%22", 1)
    if "#Rr%3Aconstant%20%22" in text:
        return text.replace("#Rr%3Aconstant%20%22", "#%22", 1)
    return text


def _canonicalise_graph(
    graph: Graph,
) -> set[tuple[str, str, tuple[str | None, str | None, str | None]]]:
    canonical: set[tuple[str, str, tuple[str | None, str | None, str | None]]] = set()
    for subject, predicate, obj in graph:
        if not isinstance(subject, URIRef):
            continue
        subject_text = str(subject)
        if not subject_text.startswith("ontology://generated-from-draw-io/mock#"):
            continue
        if predicate != RDF.type:
            continue
        if isinstance(obj, URIRef) and obj == OWL.NamedIndividual:
            continue
        subject_key = _normalise_template_iri(subject)
        predicate_key = str(predicate)
        if isinstance(obj, URIRef):
            object_key = ("uri", _normalise_template_iri(obj), None)
        elif isinstance(obj, Literal):
            object_key = ("literal", str(obj), obj.datatype or None)
        else:
            continue
        canonical.add((subject_key, predicate_key, object_key))
    return canonical


def _build_canonical_graph(
    keys: set[tuple[str, str, tuple[str | None, str | None, str | None]]],
) -> Graph:
    graph = Graph()
    for subject_key, predicate_key, object_key in keys:
        subject_term = URIRef(subject_key)
        predicate_term = URIRef(predicate_key)
        kind, value, datatype = object_key
        if kind == "uri" and value is not None:
            object_term = URIRef(value)
        elif kind == "literal" and value is not None:
            object_term = Literal(value, datatype=datatype if datatype else None)
        else:
            continue
        graph.add((subject_term, predicate_term, object_term))
    return graph


def canonicalize_for_comparison(
    map_graph: Graph, pipeline_graph: Graph
) -> CanonicalComparison:
    """Return canonicalised graphs and divergence counts for two workflow outputs."""

    map_keys = _canonicalise_graph(map_graph)
    pipeline_keys = _canonicalise_graph(pipeline_graph)

    shared_keys = map_keys & pipeline_keys
    map_only = map_keys - pipeline_keys
    pipeline_only = pipeline_keys - map_keys

    canonical_map = _build_canonical_graph(map_keys)
    canonical_pipeline = _build_canonical_graph(pipeline_keys)
    shared_graph = _build_canonical_graph(shared_keys)

    return CanonicalComparison(
        map_graph=canonical_map,
        pipeline_graph=canonical_pipeline,
        shared_graph=shared_graph,
        map_only_count=len(map_only),
        pipeline_only_count=len(pipeline_only),
    )
