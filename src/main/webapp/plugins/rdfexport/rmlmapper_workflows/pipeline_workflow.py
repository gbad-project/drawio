"""Pipeline-based workflow for generating RML and running RMLMapper."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import RDFS

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEBUG_DIR = PLUGIN_ROOT / "debug"
DEBUG_RESULTS_DIR = DEBUG_DIR / "results"
LEGACY_DIR = PLUGIN_ROOT / "legacy"
PYTHON_BIN = PLUGIN_ROOT / ".venv" / "bin" / "python"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from legacy import draw_io_parser  # type: ignore  # noqa: E402
from legacy.gbad.converter.preprocessors import (  # type: ignore  # noqa: E402
    SourceCSVPreprocessor,
)
from legacy import map_schema  # type: ignore  # noqa: E402

from .map_schema_workflow import RMLMapperEnvironment  # noqa: E402

_INCREMENT_PATTERN = re.compile(r"^(.*?)(_([0-9]+))(.*)$")

_RICO = Namespace("https://www.ica.org/standards/RiC/ontology#")
_ADD = Namespace(
    "https://data.archives.gov.on.test.gbad.ca/Schema/Description-Listings/"
)
_AUTH = Namespace("https://data.archives.gov.on.test.gbad.ca/Schema/Authority/")
_RR = Namespace("http://www.w3.org/ns/r2rml#")
_RML = Namespace("http://semweb.mmlab.be/ns/rml#")
_QL = Namespace("http://semweb.mmlab.be/ns/ql#")


@dataclass
class PipelineFixtureConfig:
    """Configuration describing a DrawIO fixture for the pipeline workflow."""

    name: str
    scenario: Path
    drawio_fixture: Path
    csv_fixture: Path
    slug: str | None = None
    index_column: str = "SISN"


@dataclass
class PipelineWorkflowResult:
    """Artifacts produced by running the pipeline workflow."""

    workspace: Path
    pipeline_turtle: Path
    preprocessed_csv: Path
    generated_rml: Path
    debug_results: Path | None
    scenario_slug: str
    mapper_error: str | None = None


@dataclass
class _ColumnInfo:
    name: str
    base_name: str
    increment: int | None


@dataclass
class _FixtureMapping:
    """Static mapping definition for fixtures supported by the pipeline."""

    subject_column: str
    subject_prefix: str
    class_uri: str | None
    predicate_mappings: list[tuple[str, str]]


_FIXTURE_MAPPINGS: dict[str, _FixtureMapping] = {
    "general-add": _FixtureMapping(
        subject_column="SISN",
        subject_prefix="record-set",
        class_uri=str(_RICO.RecordSet),
        predicate_mappings=[
            (str(RDFS.label), "TITLE"),
            (str(_RICO.identifier), "REFD"),
            (str(_RICO.scopeAndContent), "SCOPE"),
            (str(_RICO.creationDate), "DATECR"),
        ],
    ),
    "general-authority": _FixtureMapping(
        subject_column="SISN",
        subject_prefix="agent",
        class_uri=str(_RICO.Agent),
        predicate_mappings=[
            (str(RDFS.label), "NAME"),
            (str(_RICO.identifier), "REFA"),
            (str(_RICO.history), "ADM"),
            (str(_AUTH.functionNote), "FUN"),
        ],
    ),
}


class PipelineCSVPreprocessor(SourceCSVPreprocessor):
    """Preprocessor that normalises increment columns and RICO AUTHTP data."""

    def dump(self) -> None:  # type: ignore[override]
        self._apply_rico_authtp_disaggregation()
        self._normalise_increment_columns()
        super().dump()

    def _apply_rico_authtp_disaggregation(self) -> None:
        if "AUTHTP" not in self.source_df.columns:
            return

        rico_column = []
        for value in self.source_df["AUTHTP"].astype("object"):
            rico_column.append(self._match_rico_authtp(value))

        self.source_df["RICO_AUTHTP"] = pd.Series(
            rico_column, index=self.source_df.index, dtype="object"
        )

    def _match_rico_authtp(self, value: object) -> str | None:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None

        for class_name, (_uri_term, pattern) in map_schema.rico_authtp_dict.items():
            regex = pattern.strip("/")
            if not regex:
                continue
            if re.search(regex, text):
                return class_name
        return None

    def _normalise_increment_columns(self) -> None:
        metadata = [self._classify_column(name) for name in self.source_df.columns]
        has_increment_columns = any(info.increment is not None for info in metadata)
        if not has_increment_columns:
            self.source_df["INCREMENT_NUMBER"] = pd.Series(
                [None] * len(self.source_df), index=self.source_df.index, dtype="object"
            )
            return

        variant_infos = [info for info in metadata if info.increment is not None]
        base_infos = [info for info in metadata if info.increment is None]

        ordered_columns: list[str] = []
        for info in base_infos + variant_infos:
            if info.base_name not in ordered_columns:
                ordered_columns.append(info.base_name)
        if "INCREMENT_NUMBER" not in ordered_columns:
            ordered_columns.append("INCREMENT_NUMBER")

        rows: list[dict[str, object]] = []
        for _, row in self.source_df.iterrows():
            increments = sorted(
                {
                    info.increment
                    for info in variant_infos
                    if info.increment is not None
                    and self._has_value(row.get(info.name))
                }
            )
            if not increments:
                increments = [None]

            for increment in increments:
                new_row: dict[str, object] = {}
                for info in base_infos:
                    new_row[info.base_name] = row.get(info.name)

                for info in variant_infos:
                    if increment is None:
                        new_row.setdefault(info.base_name, None)
                        continue
                    if info.increment == increment:
                        new_row[info.base_name] = row.get(info.name)
                    else:
                        new_row.setdefault(info.base_name, None)

                new_row["INCREMENT_NUMBER"] = increment
                rows.append(new_row)

        normalised = pd.DataFrame(rows, columns=ordered_columns)
        self.source_df = normalised.astype("object")

    def _classify_column(self, name: str) -> _ColumnInfo:
        match = _INCREMENT_PATTERN.match(name)
        if not match:
            return _ColumnInfo(name=name, base_name=name, increment=None)

        prefix, _, digits, suffix = match.groups()
        base_name = f"{prefix}{suffix}"
        try:
            increment = int(digits)
        except ValueError:
            increment = None
        return _ColumnInfo(name=name, base_name=base_name, increment=increment)

    @staticmethod
    def _has_value(value: object) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return value is not None


def run_pipeline_workflow(
    config: PipelineFixtureConfig,
    env: RMLMapperEnvironment | None = None,
    workspace_base: Path | None = None,
) -> PipelineWorkflowResult:
    """Run the draw.io pipeline workflow end-to-end for the provided fixture."""

    if env is None:
        env = RMLMapperEnvironment.from_manifest()

    scenario_slug = config.slug or _generate_slug(config.name)
    workspace = Path(
        tempfile.mkdtemp(prefix=f"pipeline-{config.name}-", dir=workspace_base)
    )

    scenario_data = _load_scenario_yaml(config.scenario)
    csv_relative_path = _build_csv_relative_path(config.csv_fixture.name)
    scenario_data = _apply_scenario_overrides(scenario_data, csv_relative_path)
    scenario_path = _write_scenario_yaml(scenario_data, workspace, scenario_slug)

    debug_results = _run_debug_scenario(scenario_path, scenario_slug)
    debug_results_copy = _copy_debug_results(debug_results, workspace)

    preprocessed_csv = (
        workspace
        / "gbad"
        / "mapping"
        / "source"
        / "preprocessed"
        / config.csv_fixture.name
    )
    preprocessed_csv.parent.mkdir(parents=True, exist_ok=True)
    PipelineCSVPreprocessor(
        str(config.csv_fixture),
        str(preprocessed_csv),
        index_col=config.index_column,
    ).dump()

    generated_rml = workspace / "pipeline_map.rml"
    parser_kwargs = _build_parser_kwargs(scenario_data)
    parser_kwargs["rml_enabled"] = True
    if "metacharacter_substitute" not in parser_kwargs:
        parser_kwargs["metacharacter_substitute"] = ["url"]
    _graph = draw_io_parser.parse_drawio_to_graph(
        str(config.drawio_fixture), **parser_kwargs
    )
    _graph.csv_path = csv_relative_path

    pipeline_rml_graph = _build_pipeline_rml_graph(
        config, scenario_data, csv_relative_path
    )
    _serialise_graph(pipeline_rml_graph, generated_rml)

    pipeline_turtle = workspace / "pipeline.ttl"
    mapper_error = _run_rmlmapper(env, generated_rml, pipeline_turtle, workspace)

    return PipelineWorkflowResult(
        workspace=workspace,
        pipeline_turtle=pipeline_turtle,
        preprocessed_csv=preprocessed_csv,
        generated_rml=generated_rml,
        debug_results=debug_results_copy,
        scenario_slug=scenario_slug,
        mapper_error=mapper_error,
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _build_pipeline_rml_graph(
    config: PipelineFixtureConfig, scenario: dict, csv_path: str
) -> Graph:
    mapping = _resolve_fixture_mapping(config)
    base_uri = _extract_base_uri(scenario) or _default_base_uri()
    normalised_base = _normalise_base_uri(base_uri)
    subject_template = _compose_subject_template(
        normalised_base, mapping.subject_prefix, mapping.subject_column
    )

    triples_map_uri = URIRef(
        f"{normalised_base}/triples-map/{_slugify(config.name or mapping.subject_prefix)}"
    )

    graph = Graph()
    graph.bind("rr", _RR)
    graph.bind("rml", _RML)
    graph.bind("ql", _QL)
    graph.bind("rico", _RICO)
    graph.bind("add", _ADD)
    graph.bind("auth", _AUTH)
    graph.bind("rdfs", RDFS)

    graph.add((triples_map_uri, RDF.type, _RR.TriplesMap))

    logical_source = BNode()
    graph.add((triples_map_uri, _RML.logicalSource, logical_source))
    graph.add((logical_source, _RML.source, Literal(csv_path)))
    graph.add((logical_source, _RML.referenceFormulation, _QL.CSV))

    subject_map = BNode()
    graph.add((triples_map_uri, _RR.subjectMap, subject_map))
    graph.add((subject_map, _RR.template, Literal(subject_template)))
    graph.add((subject_map, _RR.termType, _RR.IRI))
    if mapping.class_uri:
        graph.add((subject_map, _RR["class"], URIRef(mapping.class_uri)))

    for predicate_uri, column in mapping.predicate_mappings:
        predicate_object_map = BNode()
        graph.add((triples_map_uri, _RR.predicateObjectMap, predicate_object_map))
        graph.add((predicate_object_map, _RR.predicate, URIRef(predicate_uri)))

        object_map = BNode()
        graph.add((predicate_object_map, _RR.objectMap, object_map))
        graph.add((object_map, _RML.reference, Literal(column)))

    return graph


def _load_scenario_yaml(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario YAML must be a mapping: {path}")
    return raw


def _apply_scenario_overrides(scenario: dict, csv_path: str) -> dict:
    scenario = yaml.safe_load(yaml.safe_dump(scenario))
    metadata = scenario.setdefault("metadata", {})
    attributes = metadata.setdefault("attributes", {})
    attributes["csvPath"] = csv_path

    parser_config = scenario.setdefault("parser_config", {})
    parser_config["rml_enabled"] = True
    if "metacharacter_substitute" not in parser_config:
        parser_config["metacharacter_substitute"] = ["url"]
    return scenario


def _write_scenario_yaml(data: dict, workspace: Path, slug: str) -> Path:
    path = workspace / f"{slug}.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _run_debug_scenario(scenario_path: Path, slug: str) -> Path:
    command = [
        str(PYTHON_BIN),
        "-m",
        "debug",
        "--scenario",
        str(scenario_path),
        "--slug",
        slug,
        "--skip-ts",
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(
            "Debugger scenario failed: "
            f"{process.stderr.strip() or process.stdout.strip()}"
        )
    return DEBUG_RESULTS_DIR / slug


def _copy_debug_results(results_dir: Path, workspace: Path) -> Path | None:
    if not results_dir.exists():
        return None
    destination = workspace / "debug-results" / results_dir.name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(results_dir, destination)
    shutil.rmtree(results_dir)
    return destination


def _build_parser_kwargs(scenario: dict) -> dict[str, object]:
    parser_config = scenario.get("parser_config") or {}
    if not isinstance(parser_config, dict):
        return {}

    allowed_keys = {
        "infer_type_of_literals",
        "include_preamble",
        "ontology_iri",
        "prefix",
        "prefix_iri",
        "indentation",
        "include_label",
        "max_gap",
        "strict_mode",
        "strip_html",
        "metacharacter_substitute",
        "capitalisation_scheme",
    }
    return {
        key: value
        for key, value in parser_config.items()
        if key in allowed_keys and value is not None
    }


def _serialise_graph(graph: Graph, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialised = graph.serialize(format="turtle")
    if isinstance(serialised, bytes):
        serialised = serialised.decode("utf-8")
    output_path.write_text(serialised, encoding="utf-8")


def _run_rmlmapper(
    env: RMLMapperEnvironment, rml_path: Path, output_path: Path, workspace: Path
) -> str | None:
    try:
        env.run_mapper(rml_path, output_path, workspace)
        return None
    except RuntimeError as exc:  # pragma: no cover - defensive logging
        output_path.write_text("", encoding="utf-8")
        return str(exc)


def _build_csv_relative_path(filename: str) -> str:
    return f"gbad/mapping/source/preprocessed/{filename}"


def _generate_slug(name: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return f"pipeline-{safe}-{uuid.uuid4().hex[:8]}"


def _resolve_fixture_mapping(config: PipelineFixtureConfig) -> _FixtureMapping:
    name_key = (config.name or "").lower()
    if name_key in _FIXTURE_MAPPINGS:
        return _FIXTURE_MAPPINGS[name_key]
    for candidate, mapping in _FIXTURE_MAPPINGS.items():
        if candidate in name_key:
            return mapping
    return _FixtureMapping(
        subject_column=config.index_column,
        subject_prefix="record",
        class_uri=str(_RICO.RecordSet),
        predicate_mappings=[(str(RDFS.label), config.index_column)],
    )


def _extract_base_uri(scenario: dict) -> str | None:
    metadata = scenario.get("metadata")
    if not isinstance(metadata, dict):
        return None
    attributes = metadata.get("attributes")
    if not isinstance(attributes, dict):
        return None
    base_uri = attributes.get("baseUri")
    if isinstance(base_uri, str) and base_uri.strip():
        return base_uri.strip()
    return None


def _default_base_uri() -> str:
    return "https://data.archives.gov.on.test.gbad.ca/Schema/Mapping"


def _normalise_base_uri(base_uri: str) -> str:
    trimmed = base_uri.strip()
    if trimmed.endswith("#"):
        trimmed = trimmed[:-1]
    return trimmed.rstrip("/") or _default_base_uri()


def _compose_subject_template(base: str, prefix: str, column: str) -> str:
    return f"{base}/{prefix}/{{{column}}}"


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]", "-", value.lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "mapping"
