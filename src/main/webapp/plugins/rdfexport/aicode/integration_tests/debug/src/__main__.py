from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, Any
from xml.etree import ElementTree as ET
import io
import contextlib

import yaml
from rdflib import Graph, RDF, OWL
from rdflib.compare import to_isomorphic
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from aicode.python_core.scripts.regenerate_baselines import (
    PreviousParserLoader,
    _serialise_graph as regenerate_baselines_serialise_graph,
    ORIGINAL_PARSER_RELATIVE_PATH,
    CURRENT_PARSER_RELATIVE_PATH,
)

# Import directly from the metabuilt parser
from python_core.src.draw_io_parser import (
    _extract_drawio_metadata,
    get_prefixes,
    pipeline,
)

DrawIOCellClassifier = pipeline.core.xml.data.DrawIOCellClassifier
DrawIOParserGraph = pipeline.core.rdf.control.DrawIOParserGraph

DEFAULT_CSV_PATH = "/mock/path/to/file.csv"
DEFAULT_BASE_URI = "ontology://generated-from-draw-io/mock#"
DEFAULT_PREFIXES = [("mock1", "http://mock-uri.com")]
DEFAULT_METADATA_ATTRIBUTES = {
    "csvPath": DEFAULT_CSV_PATH,
    "baseUri": DEFAULT_BASE_URI,
}
DEFAULT_LEGACY_COMMIT = "cf8f84bb84ff83843b6726ac96aff3a2055f4275"
DEFAULT_SERIALIZATION_FORMAT = "nt"
DEFAULT_METACHARACTER_SUBSTITUTE = ["url"]
DEFAULT_PARSER_CONFIG = {"ontology_iri": "mock://debug-ontology"}
_MISSING = object()
UNCLASSIFIED_KIND = "UNCLASSIFIED"  # not found among classifications
UNKNOWN_KIND = "UNKNOWN"  # "kind" not found in classification entry


def sorted_fixture_paths(
    root_dir: Path, default_dir: str | Path = "drawio_fixtures", extra: bool = True
) -> list[Path]:
    """
    Search for "*.drawio" recursively in `root_dir / default_dir`

    If `extra` is True, also search in any other dirs
    as defined in this function.
    """
    default_fixtures = list((root_dir / default_dir).rglob("*.drawio"))
    additional_fixtures = (
        list((root_dir / "external" / "ICA-EGAD" / "RiC-O" / "diagrams").rglob("*.xml"))
        if extra is True
        else []
    )
    fixtures = sorted(
        set(default_fixtures + additional_fixtures),
        key=lambda p: p.name,
    )
    return fixtures


@dataclass
class ScenarioConfig:
    slug: str
    drawio_path: Path
    legacy_commit: str
    serialization_format: str
    metadata_attributes: dict[str, object | None]
    prefixes: list[tuple[str, str]]
    parser_config: dict[str, object]

    @property
    def csv_path(self) -> str | None:
        value = self.metadata_attributes.get("csvPath")
        if value is None:
            return None
        return str(value)

    @property
    def base_uri(self) -> str | None:
        value = self.metadata_attributes.get("baseUri")
        if value is None:
            return None
        return str(value)


class Debugger:
    """Rich-powered CLI for generating parser comparison artifacts."""

    def __init__(self, fixtures_dir: Path) -> None:
        self.console = Console()
        self.debug_data_dir = Path(__file__).resolve().parents[4] / "data" / "debug"
        self.fixtures_dir = fixtures_dir.resolve()
        self.fixture_paths = sorted_fixture_paths(self.fixtures_dir)
        self.scenarios_dir = self.debug_data_dir / "scenarios"
        self.results_dir = self.debug_data_dir / "results"
        self.map_path = self.debug_data_dir / "map.json"

        self.scenarios_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._map_data: dict[str, dict] = self._load_map()
        self._refresh_fixture_inventory()
        self._pyodide_ready = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, args: argparse.Namespace) -> bool:
        skip_ts = getattr(args, "skip_ts", False)
        if args.scenario:
            config = self._load_scenario_file(Path(args.scenario), args.slug)
            had_errors = self._run_scenario(config, skip_ts=skip_ts)
            return had_errors or self._scenario_has_errors(config.slug)

        config = self._config_from_args(args)
        if config is None:
            config = self._run_repl()
        had_errors = self._run_scenario(config, skip_ts=skip_ts)
        return had_errors or self._scenario_has_errors(config.slug)

    # ------------------------------------------------------------------
    # Internal helpers: configuration loading
    # ------------------------------------------------------------------
    def _load_map(self) -> dict[str, dict]:
        if self.map_path.exists():
            try:
                data = json.loads(self.map_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError
            except Exception:
                data = {}
        else:
            data = {}

        data.setdefault("fixtures", {})
        data.setdefault("scenarios", {})
        return data

    def _write_map(self) -> None:
        self.map_path.write_text(
            json.dumps(self._map_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _refresh_fixture_inventory(self) -> None:
        fixtures_info: dict[str, dict[str, object]] = {}
        for fixture in sorted(self.fixture_paths):
            content = fixture.read_bytes()
            fixtures_info[fixture.name] = {
                "path": str(fixture.relative_to(self.fixtures_dir)),
                "size_bytes": fixture.stat().st_size,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        self._map_data["fixtures"] = fixtures_info
        self._write_map()

    def _load_scenario_file(
        self, scenario_path: Path, slug_override: str | None
    ) -> ScenarioConfig:
        # If scenario_path doesn't exist and has no extension, try finding by slug
        if not scenario_path.exists() and not scenario_path.suffix:
            slug_candidate = self.scenarios_dir / f"{scenario_path.name}.yml"
            if slug_candidate.exists():
                scenario_path = slug_candidate

        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

        raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Scenario YAML must define a mapping of options")

        slug = slug_override or raw.get("slug") or scenario_path.stem
        drawio_value = raw.get("drawio") or raw.get("fixture")
        if not drawio_value:
            raise ValueError("Scenario must include a 'drawio' key")

        csv_path_key_present = "csv_path" in raw or "csvPath" in raw
        base_uri_key_present = "base_uri" in raw or "baseUri" in raw
        csv_path_value = raw.get("csv_path", raw.get("csvPath"))
        base_uri_value = raw.get("base_uri", raw.get("baseUri"))
        legacy_commit = str(
            raw.get("legacy_commit", raw.get("legacyCommit", DEFAULT_LEGACY_COMMIT))
        )
        serialization_format = self._normalise_format(
            raw.get(
                "format", raw.get("serialization_format", DEFAULT_SERIALIZATION_FORMAT)
            )
        )

        metadata_section = raw.get("metadata", {})
        raw_attributes = {}
        raw_preamble = None
        if isinstance(metadata_section, dict):
            raw_attributes = metadata_section.get("attributes", {}) or {}
            raw_preamble = metadata_section.get("preamble")

        prefixes_source = raw.get("preamble", raw.get("prefixes"))
        if raw_preamble is not None:
            prefixes_source = raw_preamble

        prefixes = self._normalise_prefixes(prefixes_source)

        metadata_attributes = self._normalise_metadata_attributes(
            raw_attributes,
            csv_path=(csv_path_value if csv_path_key_present else _MISSING),
            base_uri=(base_uri_value if base_uri_key_present else _MISSING),
        )

        parser_config = self._normalise_parser_config(
            raw.get("parser_config")
            or raw.get("parserConfig")
            or (
                metadata_section.get("parser_config")
                if isinstance(metadata_section, dict)
                else None
            )
        )

        config = ScenarioConfig(
            slug=self._slugify(slug),
            drawio_path=self._resolve_drawio_path(drawio_value),
            legacy_commit=legacy_commit,
            serialization_format=serialization_format,
            metadata_attributes=metadata_attributes,
            prefixes=prefixes,
            parser_config=parser_config,
        )
        return config

    def _config_from_args(self, args: argparse.Namespace) -> ScenarioConfig | None:
        if not args.drawio:
            return None

        prefixes = self._normalise_prefixes(args.prefix)
        serialization_format = self._normalise_format(
            args.format or DEFAULT_SERIALIZATION_FORMAT
        )

        metadata_overrides = self._parse_key_value_entries(args.metadata)
        parser_overrides = self._parse_key_value_entries(args.parser_option)

        metadata_attributes = self._normalise_metadata_attributes(
            metadata_overrides,
            csv_path=(args.csv_path if args.csv_path is not None else _MISSING),
            base_uri=(args.base_uri if args.base_uri is not None else _MISSING),
        )

        parser_config = self._normalise_parser_config(parser_overrides)

        slug_source = args.slug or Path(args.drawio).stem
        config = ScenarioConfig(
            slug=self._slugify(slug_source),
            drawio_path=self._resolve_drawio_path(args.drawio),
            legacy_commit=args.legacy_commit or DEFAULT_LEGACY_COMMIT,
            serialization_format=serialization_format,
            metadata_attributes=metadata_attributes,
            prefixes=prefixes,
            parser_config=parser_config,
        )
        return config

    def _run_repl(self) -> ScenarioConfig:
        fixtures = self.fixture_paths
        if not fixtures:
            raise RuntimeError(f"No .drawio fixtures found in {self.fixtures_dir}")

        table = Table(title="Available DrawIO fixtures")
        table.add_column("#", justify="right")
        table.add_column("File")
        table.add_column("Size (KB)", justify="right")
        for index, fixture in enumerate(fixtures, start=1):
            size_kb = fixture.stat().st_size / 1024
            table.add_row(str(index), fixture.name, f"{size_kb:.1f}")
        self.console.print(table)

        choice = Prompt.ask(
            "Select fixture (number) or enter a custom path",
            default="1",
        )
        drawio_path = self._resolve_drawio_choice(choice, fixtures)

        default_slug = self._slugify(drawio_path.stem)
        slug = Prompt.ask("Scenario slug", default=default_slug)
        csv_path = Prompt.ask("CSV path", default=DEFAULT_CSV_PATH)
        base_uri = Prompt.ask("Base URI", default=DEFAULT_BASE_URI)
        prefix_default = ",".join(f"{p}:{i}" for p, i in DEFAULT_PREFIXES)
        prefix_input = Prompt.ask(
            "Prefix mappings (comma-separated prefix:iri entries)",
            default=prefix_default,
        )
        prefixes = self._parse_prefix_string(prefix_input)
        legacy_commit = Prompt.ask(
            "Legacy parser commit", default=DEFAULT_LEGACY_COMMIT
        )
        serialization_format = Prompt.ask(
            "Serialization format", default=DEFAULT_SERIALIZATION_FORMAT
        )

        metadata_input = Prompt.ask(
            "Additional metadata attributes (comma-separated key=value pairs)",
            default="",
        )
        metadata_overrides = self._parse_key_value_entries(
            self._split_inline_pairs(metadata_input)
        )
        parser_input = Prompt.ask(
            "Parser config overrides (comma-separated key=value pairs)",
            default="",
        )
        parser_overrides = self._parse_key_value_entries(
            self._split_inline_pairs(parser_input)
        )

        metadata_attributes = self._normalise_metadata_attributes(
            metadata_overrides,
            csv_path=csv_path,
            base_uri=base_uri,
        )
        parser_config = self._normalise_parser_config(parser_overrides)

        config = ScenarioConfig(
            slug=self._slugify(slug),
            drawio_path=drawio_path,
            legacy_commit=legacy_commit,
            serialization_format=self._normalise_format(serialization_format),
            metadata_attributes=metadata_attributes,
            prefixes=prefixes,
            parser_config=parser_config,
        )

        # Save scenario config if it doesn't exist
        scenario_file = self.scenarios_dir / f"{config.slug}.yml"
        if not scenario_file.exists():
            saved_path = self._save_scenario_config(config)
            self.console.print(
                f"[green]✓[/green] Saved scenario config to {saved_path.relative_to(self.debug_data_dir)}"
            )

        return config

    def _save_scenario_config(self, config: ScenarioConfig) -> Path:
        scenario_path = self.scenarios_dir / f"{config.slug}.yml"

        metadata_payload = self._prepare_metadata_payload(config.metadata_attributes)
        preamble_payload = [
            {"prefix": prefix, "iri": iri} for prefix, iri in config.prefixes
        ]

        scenario_data: dict[str, object] = {
            "slug": config.slug,
            "drawio": str(self._relative_to_plugin_dir(config.drawio_path)),
            "legacy_commit": config.legacy_commit,
            "format": config.serialization_format,
        }

        if metadata_payload:
            scenario_data["metadata"] = {"attributes": metadata_payload}

        if preamble_payload:
            scenario_data.setdefault("metadata", {}).setdefault(
                "preamble", preamble_payload
            )

        parser_payload = self._prepare_parser_payload(config.parser_config)
        if parser_payload:
            scenario_data["parser_config"] = parser_payload

        scenario_path.write_text(
            yaml.dump(scenario_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        return scenario_path

        self._persist_repl_scenario(config)

        return config

    # ------------------------------------------------------------------
    # mxCell sanity checks
    # ------------------------------------------------------------------
    def _extract_mxcell_trace(self, xml_text: str) -> dict[str, dict]:
        """Parse XML and return mxCell trace info keyed by id."""
        xml_tree = ET.fromstring(xml_text)
        return {
            cell.attrib["id"]: {
                "tag": cell.tag,
                "attrs": dict(cell.attrib),
                "text": (cell.text or "").strip(),
            }
            for cell in xml_tree.findall(".//mxCell")
            if "id" in cell.attrib
        }

    def _fill_missing_classifications(
        self, classifications: dict[str, dict], all_mxcells: dict[str, dict]
    ):
        cell_classifications = classifications.copy()
        unclassified = [
            (cid, info)
            for cid, info in all_mxcells.items()
            if cid not in cell_classifications
        ]

        for cell_id, info in unclassified:
            cell_classifications[cell_id] = {
                "kind": UNCLASSIFIED_KIND,
                "raw_value": info.get("attrs", {}).get(
                    "value"
                ),  # note that this is unprocessed by _value_of unlike classified cells
                "identifier": None,
                "parent_identifier": info.get("attrs", {}).get("parent"),
                "declares_identifier": info.get("attrs", {}).get("declares_identifier"),
                "tokens": [],
            }

        if unclassified:
            self.console.print(
                f"[yellow]Injected {len(unclassified)} unclassified mxCells (using unprocessed values)[/yellow]"
            )

        return cell_classifications

    def _classification_counts(
        self, classifications: dict[str, dict], total_cells: int
    ) -> dict:
        """Compute per-kind counts plus totals for console + map."""
        classification_count = len(classifications)
        if total_cells != classification_count:
            sign = "<" if classification_count < total_cells else ">"
            raise RuntimeError(
                f"Cell classification count does not match total mxCells: {classification_count} {sign} {total_cells}"
            )

        by_kind: dict[str, int] = {}
        for c in classifications.values():
            k = c.get("kind", UNKNOWN_KIND)
            by_kind[k] = by_kind.get(k, 0) + 1
        unclassified = by_kind.get(UNCLASSIFIED_KIND, 0)
        counts = {
            "by_kind": dict(sorted(by_kind.items())),
            "total_cells": int(total_cells),
            "classified": int(total_cells - unclassified),
            "unclassified": int(unclassified),
        }
        # Console breakdown
        if counts:
            self.console.print(
                f"[green]✓[/green] Extracted {counts['total_cells']} cell classifications:"
            )
            for kind, count in counts["by_kind"].items():
                self.console.print(f"  {kind}: {count}")
        return counts

    def _graph_diff(self, g1: Graph, g2: Graph):
        ng1 = Debugger.normalise(g1)
        ng2 = Debugger.normalise(g2)
        only_in_g1 = ng1 - ng2
        only_in_g2 = ng2 - ng1
        return only_in_g1, only_in_g2

    def _triples_to_json(self, triples: tuple[Any, Any, Any]):
        return [[repr(s), repr(p), repr(o)] for s, p, o in triples]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _run_scenario(self, config: ScenarioConfig, skip_ts: bool = False) -> None:
        self.console.rule(f"Scenario: {config.slug}")
        self.console.print(
            f"[bold]Fixture:[/bold] {config.drawio_path}\n"
            f"[bold]CSV path:[/bold] {config.csv_path}\n"
            f"[bold]Base URI:[/bold] {config.base_uri}\n"
            f"[bold]Legacy commit:[/bold] {config.legacy_commit}\n"
            f"[bold]Format:[/bold] {config.serialization_format}"
        )

        original_xml = config.drawio_path.read_text(encoding="utf-8")
        patched_xml = self._apply_metadata_overrides(original_xml, config)

        # ------------------------------------------------------------------
        # Before classification extraction, always load and count all mxCells
        # ------------------------------------------------------------------
        try:
            all_mxcells = self._extract_mxcell_trace(original_xml)
            self.console.print(
                f"[green]✓[/green] Loaded {len(all_mxcells)} mxCells from XML"
            )
        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to parse DrawIO XML: {e}")
            all_mxcells = {}

        # Extract cell classifications before generating graphs - always try to get them
        self.console.print("Starting cell classifications...")
        try:
            ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
            stdout_buf, stderr_buf = io.StringIO(), io.StringIO()

            def cleanse_ansi(text: str) -> str:
                return ansi_re.sub("", text)

            with (
                contextlib.redirect_stdout(stdout_buf),
                contextlib.redirect_stderr(stderr_buf),
            ):
                cell_classifications = self._extract_cell_classifications(
                    patched_xml, config
                )
            py_stdout, py_stderr = (
                cleanse_ansi(stdout_buf.getvalue()),
                cleanse_ansi(stderr_buf.getvalue()),
            )
            self.console.print(
                f"[green]✓[/green] Classified {len(cell_classifications)} mxCells"
            )
            if py_stdout.strip():
                self.console.print(
                    f"[cyan]Classifier stdout:[/cyan]\n[dim]{py_stdout.strip()}[/dim]"
                )
            if py_stderr.strip():
                self.console.print(
                    f"[magenta]Classifier stderr:[/magenta]\n[dim]{py_stderr.strip()}[/dim]"
                )
        except Exception as e:
            self.console.print(
                f"[yellow]Warning:[/yellow] Cell classification extraction failed: {e}"
            )
            cell_classifications = {}

        # Ensure all mxCells are tracked, even if unclassified
        cell_classifications = self._fill_missing_classifications(
            cell_classifications, all_mxcells
        )

        # Calculate and print to console
        classification_counts = self._classification_counts(
            cell_classifications, total_cells=len(all_mxcells)
        )

        with tempfile.NamedTemporaryFile(
            "w", suffix=".drawio", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(original_xml)
            temp_file_path = Path(temp_file.name)

        try:
            py_legacy_graph = self._generate_py_legacy_graph(
                temp_file_path, config.legacy_commit, config
            )
            py_legacy_error = None
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            self.console.print(
                f"[yellow]Warning:[/yellow] Legacy Python parser failed to parse DrawIO file"
                f"{'. Error message:' if error_msg else ''}\n"
                f"[dim]{error_msg if error_msg else ''}[/dim]"
            )
            py_legacy_error = error_msg
            py_legacy_graph = None
        finally:
            temp_file_path.unlink(missing_ok=True)

        ts_pipeline_graph = None
        ts_plugin_graph = None
        ts_error = None
        if not skip_ts:
            try:
                (
                    ts_pipeline_graph,
                    ts_plugin_graph,
                    ts_stderr,
                ) = self._generate_bun_graphs(patched_xml, config)
                ts_error = ts_stderr  # Capture stderr even on success
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                self.console.print(
                    "[yellow]Warning:[/yellow] TypeScript pipeline failed to generate graphs\n"
                    f"[dim]{error_msg}[/dim]"
                )
                ts_pipeline_graph = None
                ts_plugin_graph = None
                ts_error = error_msg

        errors = {}

        # Cell classification
        if py_stdout.strip() or py_stderr.strip():
            errors.update(
                {
                    k: v
                    for k, v in {
                        "py_stdout": py_stdout.strip() or None,
                        "py_stderr": py_stderr.strip() or None,
                    }.items()
                    if v
                }
            )

        # Output from runs
        if py_legacy_graph is None:
            error_details = ["Legacy Python graph is None"]
            if py_legacy_error:
                error_details.append(py_legacy_error)
            errors["py_legacy"] = error_details
        if not skip_ts:
            if ts_pipeline_graph is None:
                error_details = ["TypeScript pipeline graph is None"]
                if ts_error:
                    error_details.append(ts_error)
                errors["ts_pipeline"] = error_details
            if ts_plugin_graph is None:
                error_details = ["TypeScript plugin graph is None"]
                if ts_error:
                    error_details.append(ts_error)
                errors["ts_plugin"] = error_details

            # Capture stderr even if graphs generated successfully
            if ts_error and ts_pipeline_graph is not None:
                errors["ts_stderr"] = ts_error

        graphs = {}
        if py_legacy_graph is not None:
            graphs["py_legacy"] = py_legacy_graph
        if ts_pipeline_graph is not None:
            graphs["ts_pipeline"] = ts_pipeline_graph
        if ts_plugin_graph is not None:
            graphs["ts_plugin"] = ts_plugin_graph

        had_errors = bool(errors)

        if not graphs:
            self.console.print("[red]Error:[/red] All graph generation methods failed")
            scenario_entry = {
                "drawio": str(self._relative_to_plugin_dir(config.drawio_path)),
                "legacy_commit": config.legacy_commit,
                "format": config.serialization_format,
                "metadata_attributes": self._prepare_metadata_payload(
                    config.metadata_attributes
                ),
                "preamble": [
                    {"prefix": prefix, "iri": iri} for prefix, iri in config.prefixes
                ],
                "parser_config": self._prepare_parser_payload(config.parser_config),
                "cell_classifications": cell_classifications,
                "results": {},
                "isomorphism": {},
                "errors": errors,
            }
            self._map_data.setdefault("scenarios", {})[config.slug] = scenario_entry
            self._write_map()
            return True

        results_directory = self.results_dir / config.slug
        results_directory.mkdir(parents=True, exist_ok=True)

        extension = self._format_extension(config.serialization_format)

        serialised_outputs: dict[str, str] = {}
        serialised_paths: dict[str, Path] = {}
        nt_hashes: dict[str, str] = {}
        triple_counts: dict[str, int] = {}

        for name, graph in graphs.items():
            serialised = self._serialise_graph(graph, config.serialization_format)
            serialised_outputs[name] = serialised
            output_path = results_directory / f"{name}.{extension}"
            output_path.write_text(serialised, encoding="utf-8")
            serialised_paths[name] = output_path

            nt_serialised = regenerate_baselines_serialise_graph(graph)
            nt_hashes[name] = hashlib.sha256(nt_serialised.encode("utf-8")).hexdigest()
            triple_counts[name] = len(graph)

        isomorphism = {}
        if "py_legacy" in graphs and "ts_pipeline" in graphs:
            isomorphism["py_legacy_vs_ts_pipeline"] = self._are_isomorphic(
                graphs["py_legacy"], graphs["ts_pipeline"]
            )
        if "py_legacy" in graphs and "ts_plugin" in graphs:
            isomorphism["py_legacy_vs_ts_plugin"] = self._are_isomorphic(
                graphs["py_legacy"], graphs["ts_plugin"]
            )
        if "ts_pipeline" in graphs and "ts_plugin" in graphs:
            isomorphism["ts_pipeline_vs_ts_plugin"] = self._are_isomorphic(
                graphs["ts_pipeline"], graphs["ts_plugin"]
            )

        self._update_map_entry(
            config,
            serialised_paths,
            triple_counts,
            nt_hashes,
            isomorphism,
            errors,
            cell_classifications,
            classification_counts,
        )

        summary_table = Table(title="Debug scenario results")
        summary_table.add_column("Graph")
        summary_table.add_column("Triples", justify="right")
        summary_table.add_column("Output")
        summary_table.add_column("N-Triples SHA256")
        for name in graphs.keys():
            summary_table.add_row(
                name,
                str(triple_counts[name]),
                str(serialised_paths[name].relative_to(self.debug_data_dir)),
                nt_hashes[name],
            )
        self.console.print(summary_table)
        self.console.print("Isomorphism checks:")
        for key, value in isomorphism.items():
            status = "✅" if value else "❌"
            self.console.print(f"  {status} {key}")
            # Commented out the below because not informative in practice
            # if not value:
            #     g1_name, g2_name = key.split("_vs_")
            #     g1, g2 = graphs[g1_name], graphs[g2_name]
            #     only_in_g1, only_in_g2 = self._graph_diff(g1, g2)
            #     only_in_g1_json = json.dumps(
            #         self._triples_to_json(only_in_g1), indent=2
            #     )
            #     only_in_g2_json = json.dumps(
            #         self._triples_to_json(only_in_g2), indent=2
            #     )
            #     self.console.print(
            #         f"    Triples only in {g1_name}:\n```json\n{only_in_g1_json}\n```"
            #     )
            #     self.console.print(
            #         f"    Triples only in {g2_name}:\n```json\n{only_in_g2_json}\n```"
            #     )

        return had_errors

    # ------------------------------------------------------------------
    # Graph generation helpers
    # ------------------------------------------------------------------
    def _generate_py_legacy_graph(
        self, drawio_path: Path, commit: str, config: ScenarioConfig
    ) -> DrawIOParserGraph:
        with (
            PreviousParserLoader(
                commit, ORIGINAL_PARSER_RELATIVE_PATH
            ) as py_legacy_parser,
            PreviousParserLoader(
                "HEAD", CURRENT_PARSER_RELATIVE_PATH
            ) as py_current_parser,
        ):
            parse_drawio = getattr(py_legacy_parser, "parse_drawio_to_graph", None)
            if parse_drawio is None:
                raise AttributeError(
                    "Legacy parser does not expose parse_drawio_to_graph"
                )

            current_get_prefixes = getattr(py_current_parser, "get_prefixes", None)
            if current_get_prefixes is not None:
                setattr(py_legacy_parser, "get_prefixes", current_get_prefixes)

            parser_overrides: dict[str, object] = dict(config.parser_config)

            # Normalise ontology IRI so legacy parser honours scenario overrides
            get_ontology_iri = getattr(py_current_parser, "get_ontology_iri", None)
            ontology_iri_override = parser_overrides.get("ontology_iri")
            if ontology_iri_override:
                parser_overrides["ontology_iri"] = str(ontology_iri_override)
            elif get_ontology_iri is not None:
                parser_overrides["ontology_iri"] = get_ontology_iri("mock")

            # Mirror base URI semantics so prefix IRIs line up with the pipeline
            base_uri = config.base_uri
            prefix_iri_override = parser_overrides.get("prefix_iri")
            if prefix_iri_override:
                parser_overrides["prefix_iri"] = str(prefix_iri_override)
            elif base_uri:
                parser_overrides["prefix_iri"] = base_uri
            else:
                get_prefix_iri = getattr(py_current_parser, "get_prefix_iri", None)
                if get_prefix_iri is not None:
                    parser_overrides["prefix_iri"] = get_prefix_iri(
                        parser_overrides.get("ontology_iri")
                    )

            parser_overrides.setdefault(
                "metacharacter_substitute", list(DEFAULT_METACHARACTER_SUBSTITUTE)
            )

            graph = parse_drawio(str(drawio_path), **parser_overrides)

            if not isinstance(graph, Graph):
                raise TypeError("Legacy Python parser did not return an rdflib Graph")

            return graph

    def _generate_bun_graphs(
        self, serialized_xml: str, config: ScenarioConfig
    ) -> tuple[DrawIOParserGraph, DrawIOParserGraph]:
        outputs = self._run_ts_pipeline(serialized_xml, config)

        pipeline_graph = DrawIOParserGraph()
        pipeline_graph.parse(data=outputs["pipeline"], format="turtle")

        plugin_graph = DrawIOParserGraph()
        plugin_graph.parse(data=outputs["plugin"], format="turtle")

        stderr = outputs.get("stderr")
        return pipeline_graph, plugin_graph, stderr

    def _run_ts_pipeline(
        self, serialized_xml: str, config: ScenarioConfig
    ) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            xml_path = temp_dir_path / "scenario.drawio"
            xml_path.write_text(serialized_xml, encoding="utf-8")

            metadata_payload = self._prepare_metadata_payload(
                config.metadata_attributes
            )
            preamble_payload = [
                {"prefix": prefix, "iri": iri} for prefix, iri in config.prefixes
            ]
            parser_payload = self._prepare_parser_payload(config.parser_config)

            config_payload: dict[str, object] = {
                "xmlPath": str(xml_path),
                "baseFilename": config.drawio_path.stem,
            }

            if metadata_payload:
                config_payload["metadataAttributes"] = metadata_payload
            if preamble_payload:
                config_payload["preamble"] = preamble_payload
            if parser_payload:
                config_payload["parserConfig"] = parser_payload

            # Backwards compatibility for older harness consumers
            if config.csv_path is not None:
                config_payload["csvPath"] = config.csv_path
            if config.base_uri is not None:
                config_payload["baseUri"] = config.base_uri
            if preamble_payload:
                config_payload["prefixes"] = preamble_payload

            config_path = temp_dir_path / "config.json"
            config_path.write_text(json.dumps(config_payload), encoding="utf-8")

            command = [
                "bun",
                "run",
                "aicode/integration_tests/debug/src/run_scenario.ts",
                str(config_path),
            ]

            try:
                plugin_dir = self.debug_data_dir.parent.parent
                result = subprocess.run(
                    command,
                    cwd=plugin_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # Capture stderr even on success
                if result.stderr.strip():
                    self.console.print(
                        f"[yellow]TypeScript stderr:[/yellow]\n"
                        f"[dim]{result.stderr.strip()}[/dim]"
                    )
            except subprocess.CalledProcessError as exc:
                error_output = exc.stderr.strip() or exc.stdout.strip()
                if "pyodide/wheels" in error_output and not self._pyodide_ready:
                    self._ensure_pyodide_assets()
                    plugin_dir = self.debug_data_dir.parent.parent
                    result = subprocess.run(
                        command,
                        cwd=plugin_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                else:
                    raise RuntimeError(
                        "Bun scenario execution failed"
                        + (f": {error_output}" if error_output else "")
                    ) from exc

        stdout = result.stdout.strip()
        json_start = stdout.find("{")
        if json_start == -1:
            raise RuntimeError("Unable to locate JSON payload in Bun output")

        try:
            data = json.loads(stdout[json_start:])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Unable to parse Bun scenario output as JSON") from exc

        for key in ("pipeline", "plugin"):
            if key not in data or not isinstance(data[key], str):
                raise RuntimeError(f"Bun scenario output missing '{key}' payload")

        if result.stderr.strip():
            data["stderr"] = result.stderr.strip()
        return data

    def _ensure_pyodide_assets(self) -> None:
        if self._pyodide_ready:
            return

        for command in (["bun", "install"], ["bun", "run", "setup:pyodide"]):
            plugin_dir = self.debug_data_dir.parent.parent
            subprocess.run(
                command,
                cwd=plugin_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        self._pyodide_ready = True

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------
    def _serialise_graph(self, graph: Graph, fmt: str) -> str:
        fmt_lower = fmt.lower()
        if fmt_lower in {"nt", "ntriples", "n-triples"}:
            return regenerate_baselines_serialise_graph(graph)

        serialised = graph.serialize(format=fmt_lower)
        if isinstance(serialised, bytes):
            serialised = serialised.decode("utf-8")
        return serialised

    def _format_extension(self, fmt: str) -> str:
        fmt_lower = fmt.lower()
        if fmt_lower in {"nt", "ntriples", "n-triples"}:
            return "nt"
        if fmt_lower in {"turtle", "ttl"}:
            return "ttl"
        if fmt_lower in {"xml", "rdfxml", "rdf"}:
            return "rdf"
        return fmt_lower

    # ------------------------------------------------------------------
    # Map bookkeeping
    # ------------------------------------------------------------------
    def _update_map_entry(
        self,
        config: ScenarioConfig,
        outputs: dict[str, Path],
        triple_counts: dict[str, int],
        nt_hashes: dict[str, str],
        isomorphism: dict[str, bool],
        errors: dict[str, str],
        cell_classifications: dict[str, dict],
        classification_counts: dict | None = None,
    ) -> None:
        scenario_entry = {
            "drawio": str(self._relative_to_plugin_dir(config.drawio_path)),
            "legacy_commit": config.legacy_commit,
            "format": config.serialization_format,
            "metadata_attributes": self._prepare_metadata_payload(
                config.metadata_attributes
            ),
            "preamble": [
                {"prefix": prefix, "iri": iri} for prefix, iri in config.prefixes
            ],
            "parser_config": self._prepare_parser_payload(config.parser_config),
            "cell_classifications": cell_classifications,
            "results": {
                name: {
                    "path": str(outputs[name].relative_to(self.debug_data_dir)),
                    "triples": triple_counts[name],
                    "nt_sha256": nt_hashes[name],
                }
                for name in outputs
            },
            "isomorphism": isomorphism,
        }

        if classification_counts:
            scenario_entry["classification_counts"] = classification_counts

        if errors:
            scenario_entry["errors"] = errors

        self._map_data.setdefault("scenarios", {})[config.slug] = scenario_entry
        self._write_map()

    def _scenario_has_errors(self, slug: str) -> bool:
        scenarios = self._map_data.get("scenarios")
        if not isinstance(scenarios, dict):
            return False
        entry = scenarios.get(slug)
        if not isinstance(entry, dict):
            return False
        errors = entry.get("errors")
        if isinstance(errors, dict):
            return bool(errors)
        return bool(errors)

    def _relative_to_plugin_dir(self, path: Path) -> Path:
        try:
            plugin_dir = self.debug_data_dir.parent.parent
            return path.relative_to(plugin_dir)
        except ValueError:
            return path.resolve()

    def _persist_repl_scenario(self, config: ScenarioConfig) -> None:
        """Persist REPL-created scenarios to YAML for future reuse."""

        scenario_path = self.scenarios_dir / f"{config.slug}.yml"
        if scenario_path.exists():
            return

        try:
            drawio_reference = str(config.drawio_path.relative_to(self.fixtures_dir))
        except ValueError:
            drawio_reference = str(config.drawio_path)

        scenario_payload = {
            "slug": config.slug,
            "drawio": drawio_reference,
            "csv_path": config.csv_path,
            "base_uri": config.base_uri,
            "prefixes": [
                {"prefix": prefix, "iri": iri} for prefix, iri in config.prefixes
            ],
            "legacy_commit": config.legacy_commit,
            "format": config.serialization_format,
        }

        scenario_text = yaml.safe_dump(
            scenario_payload,
            sort_keys=False,
        )
        scenario_path.write_text(scenario_text, encoding="utf-8")

    def _extract_cell_classifications(
        self, xml_text: str, config: ScenarioConfig
    ) -> dict[str, dict]:
        """Extract cell classifications using the refactored, self-contained classifier."""

        try:
            # 1. Setup prefixes, same as before
            metadata_prefixes, _, _, _ = _extract_drawio_metadata(xml_text)
            prefixes = get_prefixes()
            prefixes.update(metadata_prefixes)
            for prefix, iri in config.prefixes:
                if prefix and iri:
                    prefixes[prefix] = iri

            # 2. Instantiate the new classifier directly with raw XML
            #    The MockTree is no longer needed.
            classifier = DrawIOCellClassifier(
                xml_text,
                prefixes,
            )

            # 3. Format the stored classifications into the dictionary the script expects
            output_classifications = {}
            for cell_id, classification in classifier.classifications.items():
                output_classifications[cell_id] = {
                    "kind": classification.kind.name
                    if hasattr(classification.kind, "name")
                    else str(classification.kind),
                    "raw_value": classification.raw_value,
                    "identifier": classification.identifier,
                    "parent_identifier": classification.parent_identifier,
                    "declares_identifier": classification.declares_identifier,
                    "tokens": classification.tokens or [],
                }

            return output_classifications

        except Exception as e:
            self.console.print(
                f"[yellow]Warning:[/yellow] Failed to extract cell classifications: {e}"
            )
            import traceback

            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return {}

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _apply_metadata_overrides(self, xml_text: str, config: ScenarioConfig) -> str:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ValueError("Invalid DrawIO XML") from exc

        graph_root = root.find(".//mxGraphModel/root")
        if graph_root is None:
            return xml_text

        metadata: ET.Element | None = None
        search_tags = ("gbadMetadata", "UserObject", "object")

        for tag in search_tags:
            metadata = graph_root.find(f"{tag}[@id='0']")
            if metadata is not None:
                break
            metadata = graph_root.find(tag)
            if metadata is not None:
                break

        if metadata is None:
            metadata = ET.Element("gbadMetadata", {"id": "0", "label": ""})
            metadata.append(ET.Element("mxCell"))
            graph_root.insert(0, metadata)
        else:
            if metadata.tag != "gbadMetadata":
                canonical = ET.Element("gbadMetadata", dict(metadata.attrib))
                for child in list(metadata):
                    canonical.append(child)
                metadata_index = list(graph_root).index(metadata)
                graph_root.remove(metadata)
                graph_root.insert(metadata_index, canonical)
                metadata = canonical

            if not metadata.get("id"):
                metadata.set("id", "0")

            has_mxcell = any(child.tag == "mxCell" for child in list(metadata))
            if not has_mxcell:
                metadata.append(ET.Element("mxCell"))

        for attribute, raw_value in config.metadata_attributes.items():
            if raw_value is None:
                metadata.attrib.pop(attribute, None)
            else:
                metadata.set(attribute, self._stringify_metadata_value(raw_value))

        if config.prefixes:
            for tag_name in ("userObjectPreambleElement", "UserObjectPreambleElement"):
                for child in list(metadata.findall(tag_name)):
                    metadata.remove(child)

            insertion_index = 0
            existing_children = list(metadata)
            for index, child in enumerate(existing_children):
                if child.tag not in {
                    "userObjectPreambleElement",
                    "UserObjectPreambleElement",
                }:
                    insertion_index = index
                    break
            else:
                insertion_index = len(existing_children)

            for offset, (prefix, iri) in enumerate(config.prefixes):
                element = ET.Element("userObjectPreambleElement")
                element.set("rdfPrefix", prefix)
                element.set("rdfIRI", iri)
                metadata.insert(insertion_index + offset, element)

        return ET.tostring(root, encoding="unicode")

    def _resolve_drawio_choice(self, choice: str, fixtures: Sequence[Path]) -> Path:
        choice = choice.strip()
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(fixtures):
                return fixtures[index - 1]
        return self._resolve_drawio_path(choice)

    def _resolve_drawio_path(self, value: str | Path) -> Path:
        """Resolve ``value`` to a concrete ``.drawio`` path.

        Scenarios historically captured absolute paths from contributor
        workstations (for example ``/Volumes/home/...``). When those
        scenarios run in a different environment, the files are unavailable
        even though the fixture exists locally. To keep the debug tool
        portable, fall back to matching fixtures by filename inside the
        repository whenever the provided path cannot be opened.
        """

        raw_value = str(value).strip()
        path = Path(raw_value)

        # First honour the caller's path if it already exists.
        if path.exists():
            return path.resolve()

        # Support relative paths with respect to the fixtures directory.
        if not path.is_absolute():
            fixture_candidate = self.fixtures_dir / path
            if fixture_candidate.exists():
                return fixture_candidate.resolve()

            expanded = Path(raw_value).expanduser()
            if expanded.exists():
                return expanded.resolve()
            path = expanded if expanded.is_absolute() else path
        else:
            expanded = path.expanduser()
            if expanded.exists():
                return expanded.resolve()
            path = expanded

        # Fallback: try resolving by filename within the fixtures inventory.
        fixture_name = Path(raw_value).name
        if fixture_name:
            fixture_candidate = self.fixtures_dir / fixture_name
            if fixture_candidate.exists():
                return fixture_candidate.resolve()

            fixtures = self._map_data.get("fixtures", {})
            lowered_name = fixture_name.lower()
            for info in fixtures.values():
                rel_path = info.get("path")
                if not rel_path:
                    continue
                candidate = self.fixtures_dir / rel_path
                if candidate.exists() and candidate.name.lower() == lowered_name:
                    return candidate.resolve()

        return path

    def _normalise_format(self, fmt: str | None) -> str:
        if not fmt:
            return DEFAULT_SERIALIZATION_FORMAT
        fmt_lower = str(fmt).strip().lower()
        if fmt_lower in {"nt", "ntriples", "n-triples"}:
            return "nt"
        if fmt_lower in {"turtle", "ttl"}:
            return "turtle"
        return fmt_lower

    def _normalise_prefixes(
        self, raw: Iterable[object] | dict | None
    ) -> list[tuple[str, str]]:
        if raw is None:
            return []

        if isinstance(raw, dict):
            return [
                (str(prefix), str(iri)) for prefix, iri in raw.items() if prefix and iri
            ]

        prefixes: list[tuple[str, str]] = []
        for item in raw:
            if isinstance(item, str):
                prefixes.extend(self._parse_prefix_string(item))
            elif isinstance(item, dict):
                prefix = item.get("prefix") or item.get("key")
                iri = item.get("iri") or item.get("value")
                if prefix and iri:
                    prefixes.append((str(prefix), str(iri)))
        return prefixes

    def _split_inline_pairs(self, raw: str | None) -> list[str]:
        if raw is None:
            return []
        return [part.strip() for part in str(raw).split(",") if part.strip()]

    def _parse_scalar_value(self, raw: str) -> object:
        try:
            return yaml.safe_load(raw)
        except Exception:
            return raw

    def _parse_key_value_entries(
        self, entries: Iterable[str] | None
    ) -> dict[str, object | None]:
        result: dict[str, object | None] = {}
        if not entries:
            return result

        for entry in entries:
            if entry is None:
                continue
            text = str(entry).strip()
            if not text:
                continue
            if "=" not in text:
                raise ValueError(
                    f"Invalid key-value pair '{text}'. Expected format KEY=VALUE."
                )
            key, raw_value = text.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(
                    f"Invalid key-value pair '{text}'. Key must not be empty."
                )
            result[key] = self._parse_scalar_value(raw_value)
        return result

    def _normalise_metadata_attributes(
        self,
        overrides: dict[str, object | None] | None,
        *,
        csv_path: object = _MISSING,
        base_uri: object = _MISSING,
    ) -> dict[str, object | None]:
        attributes: dict[str, object | None] = dict(DEFAULT_METADATA_ATTRIBUTES)

        if overrides:
            for key, value in overrides.items():
                if key is None:
                    continue
                attributes[str(key)] = value

        if csv_path is not _MISSING:
            attributes["csvPath"] = csv_path
        if base_uri is not _MISSING:
            attributes["baseUri"] = base_uri

        return attributes

    def _normalise_parser_config(
        self, raw: dict[str, object] | object | None
    ) -> dict[str, object]:
        if not raw:  # handles None or empty dict
            return dict(DEFAULT_PARSER_CONFIG)

        if isinstance(raw, dict):
            return {str(key): value for key, value in raw.items()}

        raise TypeError("Parser configuration overrides must be provided as a mapping")

    def _normalise_json_value(self, value: object) -> object:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple, set)):
            return [self._normalise_json_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._normalise_json_value(val) for key, val in value.items()
            }
        return str(value)

    def _prepare_metadata_payload(
        self, metadata: dict[str, object | None]
    ) -> dict[str, object | None]:
        payload: dict[str, object | None] = {}
        for key, value in metadata.items():
            payload[str(key)] = self._normalise_json_value(value)
        return payload

    def _prepare_parser_payload(
        self, parser_config: dict[str, object]
    ) -> dict[str, object]:
        payload: dict[str, object] = {}
        for key, value in parser_config.items():
            payload[str(key)] = self._normalise_json_value(value)
        return payload

    def _stringify_metadata_value(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _parse_prefix_string(self, value: str) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for item in filter(None, (segment.strip() for segment in value.split(","))):
            separator = "=" if "=" in item else ":"
            if separator not in item:
                continue
            prefix, iri = item.split(separator, 1)
            prefix = prefix.strip()
            iri = iri.strip()
            if prefix and iri:
                entries.append((prefix, iri))
        return entries

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
        slug = slug.lower()
        return slug or "scenario"

    @staticmethod
    def normalise(source: DrawIOParserGraph) -> DrawIOParserGraph:
        """Skip non-essential but differing triples."""
        filtered = DrawIOParserGraph()
        for s, p, o in source:
            if p == RDF.type and o in {
                OWL.ObjectProperty,
                OWL.DatatypeProperty,
                OWL.Ontology,
            }:
                continue
            if p == OWL.imports:
                continue
            filtered.add((s, p, o))
        return filtered

    def _are_isomorphic(self, first: Graph, second: Graph) -> bool:
        return to_isomorphic(Debugger.normalise(first)) == to_isomorphic(
            Debugger.normalise(second)
        )


def estimate_triple_count_from_classifications(
    xml_text: str,
    classifications: dict[str, dict],
    *,
    include_preamble: bool = True,
    graph: Graph | None = None,
) -> int:
    """Predict the expected triple count for a DrawIO payload."""

    from python_core.src.draw_io_parser import (  # type: ignore=imported-unused
        _extract_drawio_metadata,
        get_prefixes,
        pipeline,
    )

    metadata_prefixes, _, _, _ = _extract_drawio_metadata(xml_text)
    prefixes = get_prefixes()
    prefixes.update(metadata_prefixes)

    classifier_cls = pipeline.core.xml.data.DrawIOCellClassifier
    default_type = getattr(
        classifier_cls, "DEFAULT_STANDALONE_TYPE", "owl:NamedIndividual"
    )

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:  # pragma: no cover - caller should supply valid XML
        raise ValueError("Invalid DrawIO XML") from exc

    cell_lookup: dict[str, ET.Element] = {}
    for cell in root.findall(".//mxGraphModel/root//*[@id]"):
        cell_id = cell.attrib.get("id")
        if cell_id:
            cell_lookup[cell_id] = cell

    individuals: dict[str, set[str]] = {}
    decorations: set[str] = set()
    arrow_edges: set[str] = set()
    arrow_triples = 0
    object_properties: set[str] = set()
    datatype_properties: set[str] = set()

    for cell_id, cell_data in classifications.items():
        kind = cell_data.get("kind")
        raw_value = (cell_data.get("raw_value") or "").strip()

        if kind == "STANDALONE_INDIVIDUAL":
            identifier = cell_data.get("identifier") or raw_value
            if not identifier:
                continue
            tokens = [token for token in cell_data.get("tokens", []) if token]
            if not tokens:
                tokens = [default_type]
            individuals.setdefault(identifier, set()).update(tokens)
            continue

        if kind == "TYPE_TOKEN":
            identifier = cell_data.get("parent_identifier") or cell_data.get(
                "identifier"
            )
            if not identifier:
                continue
            tokens = [token for token in cell_data.get("tokens", []) if token]
            if not tokens:
                continue
            individuals.setdefault(identifier, set()).update(tokens)
            continue

        if kind == "DECORATION":
            if raw_value:
                decorations.add(raw_value)
            continue

        if kind == "ARROW_LABEL":
            if not raw_value:
                continue
            cell = cell_lookup.get(cell_id)
            if cell is None:
                continue
            edge_id = cell.attrib.get("parent")
            if not edge_id or edge_id in arrow_edges:
                continue
            edge_cell = cell_lookup.get(edge_id)
            if edge_cell is None:
                continue
            arrow_edges.add(edge_id)
            source_id = edge_cell.attrib.get("source")
            target_id = edge_cell.attrib.get("target")
            if not source_id or not target_id:
                continue
            arrow_triples += 1
            target_kind = classifications.get(target_id, {}).get("kind")
            if ":" in raw_value:
                prop_prefix = raw_value.split(":", 1)[0]
                if prop_prefix in prefixes:
                    if target_kind == "LITERAL":
                        datatype_properties.add(raw_value)
                    else:
                        object_properties.add(raw_value)

    expected = 0
    if include_preamble:
        expected += 2

    for types in individuals.values():
        expected += len(types) + 2  # rdf:type entries + label + NamedIndividual

    expected += arrow_triples

    classification_object_defs = sum(
        1 for prop in object_properties if not prop.startswith("rico:")
    )
    classification_datatype_defs = sum(
        1 for prop in datatype_properties if not prop.startswith("rico:")
    )

    if graph is not None:
        object_defs = sum(
            1 for _ in graph.triples((None, RDF.type, OWL.ObjectProperty))
        )
        datatype_defs = sum(
            1 for _ in graph.triples((None, RDF.type, OWL.DatatypeProperty))
        )
        expected += object_defs + datatype_defs
    else:
        expected += classification_object_defs + classification_datatype_defs

    expected += len(decorations)

    if graph is not None:
        return len(graph)

    return expected


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debugger CLI for DrawIO RDF export comparisons",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Path to a YAML scenario file under debug/scenarios",
    )
    parser.add_argument(
        "--slug",
        type=str,
        help="Scenario slug override (used with --scenario or --drawio)",
    )
    parser.add_argument(
        "--drawio",
        type=str,
        help="Path to a DrawIO fixture (relative to fixtures directory or absolute)",
    )
    parser.add_argument("--csv-path", type=str, help="CSV path override")
    parser.add_argument("--base-uri", type=str, help="Base URI override")
    parser.add_argument(
        "--prefix",
        action="append",
        help="Prefix mapping in the form prefix:IRI (can be repeated)",
    )
    parser.add_argument(
        "--metadata",
        action="append",
        metavar="KEY=VALUE",
        help=(
            "Additional metadata attribute to inject into the DrawIO root. "
            "Repeat the flag to provide multiple entries."
        ),
    )
    parser.add_argument(
        "--parser-option",
        action="append",
        metavar="KEY=VALUE",
        help=(
            "Override parser configuration values passed to the pipeline. "
            "Repeat the flag for multiple options."
        ),
    )
    parser.add_argument(
        "--legacy-commit",
        type=str,
        help="Commit hash for the legacy draw_io_parser",
    )
    parser.add_argument(
        "--format",
        type=str,
        help="Serialization format to use for saved outputs",
    )
    parser.add_argument(
        "--fixtures",
        type=str,
        help="Override the fixtures directory",
    )
    parser.add_argument(
        "--skip-ts",
        action="store_true",
        help="Skip TypeScript pipeline execution",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    debug_data_dir = Path(__file__).resolve().parents[4]
    default_fixtures = debug_data_dir / "data" / "fixtures"
    fixtures_dir = (
        Path(args.fixtures).expanduser() if args.fixtures else default_fixtures
    )

    debugger = Debugger(fixtures_dir)
    had_errors = debugger.run(args)
    if had_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
