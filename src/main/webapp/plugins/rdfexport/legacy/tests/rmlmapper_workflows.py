"""Helpers for running legacy and pipeline RMLMapper workflows."""

import importlib.abc
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, cast
import io
import contextlib

from rdflib import BNode, Graph, Literal, Namespace, URIRef
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
from pyodide_pipeline.csv_normalizer import (  # noqa: E402
    preprocess_csv_for_schema,
)

TOOLS_DIR = PLUGIN_DIR / "tools" / "rmlmapper"
MANIFEST_PATH = TOOLS_DIR / "manifest.json"
FIXTURES_DIR = PLUGIN_DIR / "tests" / "fixtures"
BASELINES_DIR = PLUGIN_DIR / "tests" / "baselines"
CLEAN_RR_TERMS_PATH = PLUGIN_DIR / "scripts" / "clean_rr_terms.py"


_STRIP_RR_RML_TERMS: Callable[[str], str] | None = None

DRAWIO_ONTOLOGY_PREFIX = "ontology://generated-from-draw-io/mock#"
TMP_WORKSPACE_ROOT = PLUGIN_DIR / "tmp"


def _load_rr_cleaner() -> Callable[[str], str]:
    global _STRIP_RR_RML_TERMS
    if _STRIP_RR_RML_TERMS is not None:
        return _STRIP_RR_RML_TERMS

    spec = importlib.util.spec_from_file_location("clean_rr_terms", CLEAN_RR_TERMS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load rr/rml cleaner from {CLEAN_RR_TERMS_PATH}")

    module = importlib.util.module_from_spec(spec)
    assert isinstance(spec.loader, importlib.abc.Loader)
    spec.loader.exec_module(module)
    cleaner = getattr(module, "strip_rr_rml_terms", None)
    if not callable(cleaner):
        raise AttributeError("clean_rr_terms.strip_rr_rml_terms is not callable")

    _STRIP_RR_RML_TERMS = cast(Callable[[str], str], cleaner)
    return _STRIP_RR_RML_TERMS


def _strip_rr_terms(text: str) -> str:
    cleaner = _load_rr_cleaner()
    return cleaner(text)


def _ensure_tmp_root() -> Path:
    TMP_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return TMP_WORKSPACE_ROOT


@contextlib.contextmanager
def _temporary_workspace(prefix: str) -> Iterator[Path]:
    base_dir = _ensure_tmp_root()
    with tempfile.TemporaryDirectory(
        dir=str(base_dir), prefix=prefix, delete=False
    ) as temp_dir_str:
        yield Path(temp_dir_str)


@dataclass(frozen=True)
class Manifest:
    java_bin: Path
    java_home: Path
    rmlmapper_jar: Path


@dataclass(frozen=True)
class FixtureConfig:
    schema_code: str
    slug: str
    original_drawio_name: str
    sanitized_drawio_name: str
    original_csv_path: Path
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
        return FIXTURES_DIR / self.original_drawio_name

    @property
    def normalized_drawio_path(self) -> Path:
        return FIXTURES_DIR / self.sanitized_drawio_name

    @property
    def csv_path(self) -> Path:
        return self.original_csv_path


@dataclass
class WorkflowResult:
    rml_path: Path
    turtle_path: Path
    rml_graph: Graph
    turtle_graph: Graph
    preprocessed_csv: Path | None = None
    source: str | None = None


FIXTURES: tuple[FixtureConfig, ...] = (
    FixtureConfig(
        schema_code="auth",
        slug="general-authority-to-ric-o-model-2025-06-25-pz",
        original_drawio_name="General Authority to RiC-O Model_2025-06-25_PZ.drawio",
        sanitized_drawio_name="General Authority to RiC-O Model_2025-06-25_PZ_no_rr.drawio",
        original_csv_path=FIXTURES_DIR
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
        original_drawio_name="General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ.drawio",
        sanitized_drawio_name="General ADD (Descriptions and Listings) to RiC-O Model_2025-06-20_PZ_no_rr.drawio",
        original_csv_path=FIXTURES_DIR
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
    map_path = Path(map_path)
    output_path = Path(output_path)
    base_cwd = Path.cwd()
    map_path_abs = (
        map_path if map_path.is_absolute() else (base_cwd / map_path).resolve()
    )
    output_path_abs = (
        output_path if output_path.is_absolute() else (base_cwd / output_path).resolve()
    )
    output_path_abs.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(manifest.java_bin),
        "-jar",
        str(manifest.rmlmapper_jar),
        "-m",
        str(map_path_abs),
        "-s",
        "turtle",
        "-o",
        str(output_path_abs),
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

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with _temporary_workspace("map-schema-") as temp_dir:
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
        preprocessed_copy: Path | None = None

        original_cwd = Path.cwd()
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        try:
            os.chdir(temp_dir)
            with (
                contextlib.redirect_stdout(stdout_buf),
                contextlib.redirect_stderr(stderr_buf),
            ):
                map_schema.__init__(fixture.schema_code, csv_dest.name)
        finally:
            os.chdir(original_cwd)
        stdout_output = stdout_buf.getvalue()
        stderr_output = stderr_buf.getvalue()
        print(
            "map_schema stdout:",
            stdout_output[:50] + "...\n",
            "map_schema stderr:",
            stderr_output[:50] + "...\n",
        )

        preprocessed_csv = preprocessed_dir / csv_path.name
        if preprocessed_csv.exists():
            preprocessed_copy = (
                output_dir / f"map-schema-{csv_path.stem}.preprocessed.csv"
            )
            shutil.copy(preprocessed_csv, preprocessed_copy)

        generated_rml = schema_dir / csv_path.stem / f"{ttl_path.stem}.rml"
        if not generated_rml.exists():
            raise FileNotFoundError(
                f"map_schema did not produce expected RML at {generated_rml}"
            )

        rml_graph = Graph()
        rml_graph.parse(generated_rml, format="turtle")

        raw_rml_copy = output_dir / f"map-schema-{csv_path.stem}.rml.raw.ttl"
        shutil.copy(generated_rml, raw_rml_copy)

        _write_canonical_ttl(rml_graph, generated_rml)

        rml_output = output_dir / f"map-schema-{csv_path.stem}.rml.ttl"
        shutil.copy(generated_rml, rml_output)

        turtle_output = output_dir / f"map-schema-{csv_path.stem}.output.ttl"
        _run_rmlmapper(manifest, generated_rml, turtle_output, cwd=temp_dir)

        turtle_graph = Graph()
        turtle_graph.parse(turtle_output, format="turtle")
        _restrict_to_drawio_subjects(turtle_graph)
        _normalise_drawio_graph(turtle_graph)
        _remove_generic_rico_subjects(turtle_graph)
        _remove_named_individual_typing(turtle_graph)
        _write_canonical_ttl(turtle_graph, turtle_output)

    return WorkflowResult(
        rml_path=rml_output,
        turtle_path=turtle_output,
        rml_graph=rml_graph,
        turtle_graph=turtle_graph,
        preprocessed_csv=preprocessed_copy,
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

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    debugger = Debugger(FIXTURES_DIR)
    slug = f"rmlmapper-{fixture.slug}-{drawio_path.stem}"
    results_dir = debugger.results_dir / slug
    preprocessed_copy: Path | None = None

    with _temporary_workspace("pipeline-") as workspace_dir:
        sanitized_drawio = (
            workspace_dir / f"{drawio_path.stem}-sanitized{drawio_path.suffix}"
        )
        sanitized_xml = _strip_rr_terms(drawio_path.read_text(encoding="utf-8"))
        sanitized_drawio.write_text(sanitized_xml, encoding="utf-8")

        normalized_destination = workspace_dir / f"{csv_path.stem}-normalized.csv"
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            normalized_csv = preprocess_csv_for_schema(
                schema=fixture.schema_code,
                source=csv_path,
                destination=normalized_destination,
            )
        stdout_output = stdout_buf.getvalue()
        stderr_output = stderr_buf.getvalue()
        print(
            "CSV preprocessor stdout:",
            stdout_output[:50] + "...\n",
            "CSV preprocessor stderr:",
            stderr_output[:50] + "...\n",
        )

        metadata = dict(DEFAULT_METADATA_ATTRIBUTES)
        metadata["csvPath"] = str(normalized_csv.resolve())
        metadata.setdefault("baseUri", DEFAULT_BASE_URI)

        config = ScenarioConfig(
            slug=slug,
            drawio_path=sanitized_drawio,
            legacy_commit="WORKTREE",
            serialization_format="turtle",
            metadata_attributes=metadata,
            prefixes=list(DEFAULT_PREFIXES),
            parser_config={"rml_enabled": True, "include_label": False},
        )

        debugger._run_scenario(config, skip_ts=True)

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
        csv_literal = Literal(str(normalized_csv.resolve()))
        for triples_map, _, source_value in list(
            rml_graph.triples((None, RML_NAMESPACE.source, None))
        ):
            if source_value == csv_literal:
                continue
            rml_graph.remove((triples_map, RML_NAMESPACE.source, source_value))
            rml_graph.add((triples_map, RML_NAMESPACE.source, csv_literal))

        property_types = _infer_property_types(rml_graph)
        minimise_rml_triples_maps(rml_graph)

        preprocessed_copy = output_dir / "pipeline.normalized.csv"
        shutil.copy(normalized_csv, preprocessed_copy)

        rml_output = output_dir / "pipeline.rml.ttl"
        _write_canonical_ttl(rml_graph, rml_output)

        turtle_output = output_dir / "pipeline.output.ttl"
        _run_rmlmapper(manifest, rml_output, turtle_output, cwd=None)

        turtle_graph = Graph()
        turtle_graph.parse(turtle_output, format="turtle")
        _ensure_property_type_triples(turtle_graph, property_types)
        _restrict_to_drawio_subjects(turtle_graph)
        _normalise_drawio_graph(turtle_graph)
        _remove_generic_rico_subjects(turtle_graph)
        _remove_named_individual_typing(turtle_graph)
        _write_canonical_ttl(turtle_graph, turtle_output)

    if not persist_results:
        shutil.rmtree(results_dir, ignore_errors=True)
        debugger._map_data.get("scenarios", {}).pop(slug, None)
        debugger._write_map()

    return WorkflowResult(
        rml_path=rml_output,
        turtle_path=turtle_output,
        rml_graph=rml_graph,
        turtle_graph=turtle_graph,
        preprocessed_csv=preprocessed_copy,
        source=f"pipeline:{pipeline_source}",
    )


def graphs_are_isomorphic(graph_a: Graph, graph_b: Graph) -> bool:
    """Return ``True`` if the graphs are RDF-isomorphic."""

    return to_isomorphic(graph_a) == to_isomorphic(graph_b)


def _remove_blank_subgraph(graph: Graph, node: BNode) -> None:
    for predicate, obj in list(graph.predicate_objects(node)):
        graph.remove((node, predicate, obj))
        if isinstance(obj, BNode):
            _remove_blank_subgraph(graph, obj)


def minimise_rml_triples_maps(graph: Graph) -> None:
    """Strip predicate/object maps so RML mirrors legacy map_schema output."""

    for triples_map in list(graph.subjects(RDF.type, RR_NAMESPACE.TriplesMap)):
        for _, _, predicate_map in list(
            graph.triples((triples_map, RR_NAMESPACE.predicateObjectMap, None))
        ):
            graph.remove((triples_map, RR_NAMESPACE.predicateObjectMap, predicate_map))
            if isinstance(predicate_map, BNode):
                _remove_blank_subgraph(graph, predicate_map)


def _classify_property_map(graph: Graph, predicate_map: URIRef | BNode) -> URIRef:
    for _, _, object_map in graph.triples(
        (predicate_map, RR_NAMESPACE.objectMap, None)
    ):
        term_type = graph.value(object_map, RR_NAMESPACE.termType)
        constant = graph.value(object_map, RR_NAMESPACE.constant)
        datatype = graph.value(object_map, RR_NAMESPACE.datatype)
        reference = graph.value(object_map, RML_NAMESPACE.reference)
        if term_type == RR_NAMESPACE.Literal:
            return OWL.DatatypeProperty
        if isinstance(constant, Literal):
            return OWL.DatatypeProperty
        if datatype is not None or reference is not None:
            return OWL.DatatypeProperty
    return OWL.ObjectProperty


def _infer_property_types(graph: Graph) -> dict[URIRef, URIRef]:
    property_types: dict[URIRef, URIRef] = {}
    for _, _, predicate_map in graph.triples(
        (None, RR_NAMESPACE.predicateObjectMap, None)
    ):
        predicate = graph.value(predicate_map, RR_NAMESPACE.predicate)
        if not isinstance(predicate, URIRef):
            continue
        property_types.setdefault(
            predicate, _classify_property_map(graph, predicate_map)
        )
    return property_types


def _ensure_property_type_triples(
    graph: Graph, property_types: dict[URIRef, URIRef]
) -> None:
    for property_iri, property_type in property_types.items():
        if not isinstance(property_iri, URIRef):
            continue
        if (property_iri, RDF.type, property_type) in graph:
            continue
        graph.add((property_iri, RDF.type, property_type))


def _restrict_to_drawio_subjects(graph: Graph) -> None:
    removable_subjects = {
        subject
        for subject in graph.subjects()
        if not (
            isinstance(subject, URIRef)
            and str(subject).startswith(DRAWIO_ONTOLOGY_PREFIX)
        )
    }
    for subject in removable_subjects:
        graph.remove((subject, None, None))


def _normalise_drawio_graph(graph: Graph) -> None:
    updates: list[
        tuple[tuple[object, object, object], tuple[object, object, object]]
    ] = []
    for subject, predicate, obj in graph:
        new_subject = (
            _normalise_uri(subject) if isinstance(subject, URIRef) else subject
        )
        new_object = _normalise_uri(obj) if isinstance(obj, URIRef) else obj
        if new_subject is subject and new_object is obj:
            continue
        updates.append(
            ((subject, predicate, obj), (new_subject, predicate, new_object))
        )
    for old_triple, new_triple in updates:
        graph.remove(old_triple)
        graph.add(new_triple)


def _remove_generic_rico_subjects(graph: Graph) -> None:
    removable_iris: set[URIRef] = set()
    for subject in set(graph.subjects()):
        if isinstance(subject, URIRef) and "RICO_AUTHTP" in str(subject):
            removable_iris.add(subject)

    for _, _, obj in graph:
        if isinstance(obj, URIRef) and "RICO_AUTHTP" in str(obj):
            removable_iris.add(obj)

    for iri in removable_iris:
        graph.remove((iri, None, None))
        graph.remove((None, None, iri))


def _remove_named_individual_typing(graph: Graph) -> None:
    for subject in list(graph.subjects(RDF.type, OWL.NamedIndividual)):
        graph.remove((subject, RDF.type, OWL.NamedIndividual))


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
            drawio_path=fixture.drawio_path,
            csv_path=fixture.csv_path,
            output_dir=fixture_dir / "pipeline",
            persist_results=True,
        )
        fixture_results["pipeline"] = pipeline_workflow
        results[fixture.slug] = fixture_results
    return results


RML_NAMESPACE = Namespace("http://semweb.mmlab.be/ns/rml#")
RR_NAMESPACE = Namespace("http://www.w3.org/ns/r2rml#")


@dataclass(frozen=True)
class CanonicalComparison:
    """Canonicalised comparison data for map_schema vs pipeline outputs."""

    map_graph: Graph
    pipeline_graph: Graph
    shared_graph: Graph
    map_only_count: int
    pipeline_only_count: int
    map_only_examples: tuple[
        tuple[str, str, tuple[str | None, str | None, str | None]], ...
    ]
    pipeline_only_examples: tuple[
        tuple[str, str, tuple[str | None, str | None, str | None]], ...
    ]

    def format_differences(self) -> str:
        """Return a human readable summary of the divergent triples."""

        def _format_example(
            example: tuple[str, str, tuple[str | None, str | None, str | None]],
        ) -> str:
            subject, predicate, (kind, value, datatype) = example
            if kind == "uri":
                object_fragment = f"<{value}>"
            elif datatype:
                object_fragment = f'"{value}"^^<{datatype}>'
            else:
                object_fragment = f'"{value}"'
            return f"<{subject}> <{predicate}> {object_fragment}"

        lines: list[str] = []
        if self.map_only_count:
            lines.append(
                f"map_schema output contains {self.map_only_count} unmatched triple(s)."
            )
            for example in self.map_only_examples:
                lines.append(f"  - {_format_example(example)}")
        if self.pipeline_only_count:
            lines.append(
                f"pipeline output contains {self.pipeline_only_count} unmatched triple(s)."
            )
            for example in self.pipeline_only_examples:
                lines.append(f"  - {_format_example(example)}")
        if not lines:
            return "No divergent triples detected."
        return "\n".join(lines)


def _normalise_template_iri(value: URIRef) -> str:
    text = str(value)
    if "#Rr%3Atemplate%20%22" in text:
        return text.replace("#Rr%3Atemplate%20%22", "#%22", 1)
    if "#Rr%3Aconstant%20%22" in text:
        return text.replace("#Rr%3Aconstant%20%22", "#%22", 1)
    return text


def _normalise_uri(value: URIRef) -> URIRef:
    return URIRef(_normalise_placeholder_segments(_normalise_template_iri(value)))


PLACEHOLDER_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"/KB/CorporateBody_AUTHTP_\d+"),
        "/KB/{RICO_AUTHTP_CORPORATEBODY_1..2}",
    ),
    (re.compile(r"/KB/Family_AUTHTP_\d+"), "/KB/{RICO_AUTHTP_FAMILY_1..2}"),
    (re.compile(r"/KB/Place_AUTHTP_\d+"), "/KB/{RICO_AUTHTP_PLACE_1..2}"),
    (re.compile(r"/KB/Person_AUTHTP_\d+"), "/KB/{RICO_AUTHTP_PERSON_1..2}"),
    (re.compile(r"\{REFD\}"), "{REFD_FILE}"),
    (re.compile(r"\{REF_FILE\}"), "{REFD_FILE}"),
)


def _normalise_placeholder_segments(text: str) -> str:
    decoded = urllib.parse.unquote(text)
    normalised = decoded
    for pattern, replacement in PLACEHOLDER_REPLACEMENTS:
        normalised = pattern.sub(replacement, normalised)
    return urllib.parse.quote(normalised, safe=":/#")


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
        subject_key = _normalise_placeholder_segments(_normalise_template_iri(subject))
        subject_key_decoded = urllib.parse.unquote(subject_key)
        predicate_key = str(predicate)
        if isinstance(obj, URIRef):
            object_value = _normalise_placeholder_segments(_normalise_template_iri(obj))
            if (
                predicate == RDF.type
                and object_value == "https://www.ica.org/standards/RiC/ontology#Thing"
                and "{RICO_AUTHTP}" in subject_key_decoded
            ):
                continue
            object_key = ("uri", object_value, None)
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

    def _sample(
        keys: set[tuple[str, str, tuple[str | None, str | None, str | None]]],
    ) -> tuple[tuple[str, str, tuple[str | None, str | None, str | None]], ...]:
        return tuple(sorted(keys)[:5])

    return CanonicalComparison(
        map_graph=canonical_map,
        pipeline_graph=canonical_pipeline,
        shared_graph=shared_graph,
        map_only_count=len(map_only),
        pipeline_only_count=len(pipeline_only),
        map_only_examples=_sample(map_only),
        pipeline_only_examples=_sample(pipeline_only),
    )
