from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from xml.etree import ElementTree as ET

import yaml
from rdflib import Graph
from rdflib.compare import to_isomorphic
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.main.webapp.plugins.rdfexport.legacy.tests.regenerate_baselines import (
    PreviousParserLoader,
    _serialise_graph,
)
from src.main.webapp.plugins.rdfexport.pyodide_pipeline import drawio_pipeline

DEFAULT_CSV_PATH = "/mock/path/to/file.csv"
DEFAULT_BASE_URI = "ontology://generated-from-draw-io/mock#"
DEFAULT_PREFIXES = [("mock1", "http://mock-uri.com")]
DEFAULT_LEGACY_COMMIT = "cf8f84bb84ff83843b6726ac96aff3a2055f4275"
DEFAULT_SERIALIZATION_FORMAT = "nt"
DEFAULT_METACHARACTER_SUBSTITUTE = ["url"]


@dataclass
class ScenarioConfig:
    slug: str
    drawio_path: Path
    csv_path: str
    base_uri: str
    prefixes: list[tuple[str, str]]
    legacy_commit: str
    serialization_format: str


class Debugger:
    """Rich-powered CLI for generating parser comparison artifacts."""

    def __init__(self, fixtures_dir: Path) -> None:
        self.console = Console()
        self.debug_dir = Path(__file__).resolve().parent
        self.fixtures_dir = fixtures_dir.resolve()
        self.scenarios_dir = self.debug_dir / "scenarios"
        self.results_dir = self.debug_dir / "results"
        self.map_path = self.debug_dir / "map.json"

        self.scenarios_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._map_data: dict[str, dict] = self._load_map()
        self._refresh_fixture_inventory()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, args: argparse.Namespace) -> None:
        if args.scenario:
            config = self._load_scenario_file(Path(args.scenario), args.slug)
            self._run_scenario(config)
            return

        config = self._config_from_args(args)
        if config is None:
            config = self._run_repl()
        self._run_scenario(config)

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
        for fixture in sorted(self.fixtures_dir.glob("*.drawio")):
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
        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

        raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Scenario YAML must define a mapping of options")

        slug = slug_override or raw.get("slug") or scenario_path.stem
        drawio_value = raw.get("drawio") or raw.get("fixture")
        if not drawio_value:
            raise ValueError("Scenario must include a 'drawio' key")

        csv_path = str(raw.get("csv_path", raw.get("csvPath", DEFAULT_CSV_PATH)))
        base_uri = str(raw.get("base_uri", raw.get("baseUri", DEFAULT_BASE_URI)))
        legacy_commit = str(
            raw.get("legacy_commit", raw.get("legacyCommit", DEFAULT_LEGACY_COMMIT))
        )
        serialization_format = self._normalise_format(
            raw.get(
                "format", raw.get("serialization_format", DEFAULT_SERIALIZATION_FORMAT)
            )
        )

        prefixes = self._normalise_prefixes(raw.get("prefixes"))

        config = ScenarioConfig(
            slug=self._slugify(slug),
            drawio_path=self._resolve_drawio_path(drawio_value),
            csv_path=csv_path,
            base_uri=base_uri,
            prefixes=prefixes,
            legacy_commit=legacy_commit,
            serialization_format=serialization_format,
        )
        return config

    def _config_from_args(self, args: argparse.Namespace) -> ScenarioConfig | None:
        if not args.drawio:
            return None

        prefixes = self._normalise_prefixes(args.prefix)
        serialization_format = self._normalise_format(
            args.format or DEFAULT_SERIALIZATION_FORMAT
        )

        slug_source = args.slug or Path(args.drawio).stem
        config = ScenarioConfig(
            slug=self._slugify(slug_source),
            drawio_path=self._resolve_drawio_path(args.drawio),
            csv_path=args.csv_path or DEFAULT_CSV_PATH,
            base_uri=args.base_uri or DEFAULT_BASE_URI,
            prefixes=prefixes,
            legacy_commit=args.legacy_commit or DEFAULT_LEGACY_COMMIT,
            serialization_format=serialization_format,
        )
        return config

    def _run_repl(self) -> ScenarioConfig:
        fixtures = list(sorted(self.fixtures_dir.glob("*.drawio")))
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
        prefix_default = ",".join(f"{p}={i}" for p, i in DEFAULT_PREFIXES)
        prefix_input = Prompt.ask(
            "Prefix mappings (comma-separated prefix=iri entries)",
            default=prefix_default,
        )
        prefixes = self._parse_prefix_string(prefix_input)
        legacy_commit = Prompt.ask(
            "Legacy parser commit", default=DEFAULT_LEGACY_COMMIT
        )
        serialization_format = Prompt.ask(
            "Serialization format", default=DEFAULT_SERIALIZATION_FORMAT
        )

        return ScenarioConfig(
            slug=self._slugify(slug),
            drawio_path=drawio_path,
            csv_path=csv_path,
            base_uri=base_uri,
            prefixes=prefixes,
            legacy_commit=legacy_commit,
            serialization_format=self._normalise_format(serialization_format),
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _run_scenario(self, config: ScenarioConfig) -> None:
        self.console.rule(f"Scenario: {config.slug}")
        self.console.print(
            f"[bold]Fixture:[/bold] {config.drawio_path}\n"
            f"[bold]CSV path:[/bold] {config.csv_path}\n"
            f"[bold]Base URI:[/bold] {config.base_uri}\n"
            f"[bold]Legacy commit:[/bold] {config.legacy_commit}\n"
            f"[bold]Format:[/bold] {config.serialization_format}"
        )

        xml_text = config.drawio_path.read_text(encoding="utf-8")
        patched_xml = self._apply_metadata_overrides(xml_text, config)

        with tempfile.NamedTemporaryFile(
            "w", suffix=".drawio", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(patched_xml)
            temp_file_path = Path(temp_file.name)

        try:
            legacy_graph = self._generate_legacy_graph(
                temp_file_path, config.legacy_commit
            )
        finally:
            temp_file_path.unlink(missing_ok=True)

        current_graph = self._generate_pipeline_graph(patched_xml)
        plugin_graph = self._generate_plugin_graph(patched_xml)

        graphs = {
            "legacy": legacy_graph,
            "current": current_graph,
            "plugin": plugin_graph,
        }

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

            nt_serialised = _serialise_graph(graph)
            nt_hashes[name] = hashlib.sha256(nt_serialised.encode("utf-8")).hexdigest()
            triple_counts[name] = len(graph)

        isomorphism = {
            "legacy_vs_current": self._are_isomorphic(
                graphs["legacy"], graphs["current"]
            ),
            "legacy_vs_plugin": self._are_isomorphic(
                graphs["legacy"], graphs["plugin"]
            ),
            "current_vs_plugin": self._are_isomorphic(
                graphs["current"], graphs["plugin"]
            ),
        }

        self._update_map_entry(
            config,
            serialised_paths,
            triple_counts,
            nt_hashes,
            isomorphism,
        )

        summary_table = Table(title="Scenario results")
        summary_table.add_column("Graph")
        summary_table.add_column("Triples", justify="right")
        summary_table.add_column("Output")
        summary_table.add_column("N-Triples SHA256")
        for name in ("legacy", "current", "plugin"):
            summary_table.add_row(
                name,
                str(triple_counts[name]),
                str(serialised_paths[name].relative_to(self.debug_dir)),
                nt_hashes[name],
            )
        self.console.print(summary_table)
        self.console.print("Isomorphism checks:")
        for key, value in isomorphism.items():
            status = "✅" if value else "❌"
            self.console.print(f"  {status} {key}")

    # ------------------------------------------------------------------
    # Graph generation helpers
    # ------------------------------------------------------------------
    def _generate_legacy_graph(self, drawio_path: Path, commit: str) -> Graph:
        with (
            PreviousParserLoader(commit) as legacy_parser,
            PreviousParserLoader("HEAD") as current_parser,
        ):
            parse_drawio = getattr(legacy_parser, "parse_drawio_to_graph", None)
            if parse_drawio is None:
                raise AttributeError(
                    "Legacy parser does not expose parse_drawio_to_graph"
                )

            current_get_prefixes = getattr(current_parser, "get_prefixes", None)
            if current_get_prefixes is not None:
                setattr(legacy_parser, "get_prefixes", current_get_prefixes)

            get_ontology_iri = getattr(current_parser, "get_ontology_iri", None)
            ontology_iri = None
            if get_ontology_iri is not None:
                ontology_iri = get_ontology_iri("mock")

            graph = parse_drawio(
                str(drawio_path),
                ontology_iri=ontology_iri,
                metacharacter_substitute=list(DEFAULT_METACHARACTER_SUBSTITUTE),
            )

            if not isinstance(graph, Graph):
                raise TypeError("Legacy parser did not return an rdflib Graph")

            return graph

    def _generate_pipeline_graph(self, serialized_xml: str) -> Graph:
        graph_id, graph = drawio_pipeline.parse_drawio_xml(serialized_xml)
        if not isinstance(graph, Graph):
            raise TypeError(
                f"Pipeline returned unexpected graph type for {graph_id}: {type(graph)!r}"
            )
        return graph

    def _generate_plugin_graph(self, serialized_xml: str) -> Graph:
        graph = self._generate_pipeline_graph(serialized_xml)
        plugin_graph = Graph()
        plugin_graph.parse(data=graph.serialize(format="turtle"), format="turtle")
        return plugin_graph

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------
    def _serialise_graph(self, graph: Graph, fmt: str) -> str:
        fmt_lower = fmt.lower()
        if fmt_lower in {"nt", "ntriples", "n-triples"}:
            return _serialise_graph(graph)

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
    ) -> None:
        scenario_entry = {
            "drawio": str(self._relative_to_debug(config.drawio_path)),
            "csv_path": config.csv_path,
            "base_uri": config.base_uri,
            "prefixes": [
                {"prefix": prefix, "iri": iri} for prefix, iri in config.prefixes
            ],
            "legacy_commit": config.legacy_commit,
            "format": config.serialization_format,
            "results": {
                name: {
                    "path": str(outputs[name].relative_to(self.debug_dir)),
                    "triples": triple_counts[name],
                    "nt_sha256": nt_hashes[name],
                }
                for name in outputs
            },
            "isomorphism": isomorphism,
        }

        self._map_data.setdefault("scenarios", {})[config.slug] = scenario_entry
        self._write_map()

    def _relative_to_debug(self, path: Path) -> Path:
        try:
            return path.relative_to(self.debug_dir)
        except ValueError:
            return path.resolve()

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

        metadata = graph_root.find("UserObject[@id='0']")
        if metadata is None:
            metadata = ET.Element("UserObject", {"id": "0", "label": ""})
            metadata.append(ET.Element("mxCell"))
            graph_root.insert(0, metadata)

        if config.csv_path:
            metadata.set("csvPath", config.csv_path)
        elif "csvPath" in metadata.attrib:
            metadata.attrib.pop("csvPath")

        if config.base_uri:
            metadata.set("baseUri", config.base_uri)
        elif "baseUri" in metadata.attrib:
            metadata.attrib.pop("baseUri")

        for child in list(metadata.findall("userObjectPreambleElement")):
            metadata.remove(child)

        if config.prefixes:
            insertion_index = 0
            existing_children = list(metadata)
            for index, child in enumerate(existing_children):
                if child.tag != "userObjectPreambleElement":
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
        path = Path(value)
        if not path.is_absolute():
            fixture_candidate = self.fixtures_dir / path
            if fixture_candidate.exists():
                return fixture_candidate.resolve()
            path = Path(value).expanduser().resolve()
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
            return list(DEFAULT_PREFIXES)

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
        return prefixes or list(DEFAULT_PREFIXES)

    def _parse_prefix_string(self, value: str) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for item in filter(None, (segment.strip() for segment in value.split(","))):
            if "=" not in item:
                continue
            prefix, iri = item.split("=", 1)
            prefix = prefix.strip()
            iri = iri.strip()
            if prefix and iri:
                entries.append((prefix, iri))
        return entries

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
        slug = slug.lower()
        return slug or "scenario"

    def _are_isomorphic(self, first: Graph, second: Graph) -> bool:
        return to_isomorphic(first) == to_isomorphic(second)


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
        help="Prefix mapping in the form prefix=IRI (can be repeated)",
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
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    debug_dir = Path(__file__).resolve().parent
    default_fixtures = debug_dir.parent / "tests" / "fixtures"
    fixtures_dir = (
        Path(args.fixtures).expanduser() if args.fixtures else default_fixtures
    )

    debugger = Debugger(fixtures_dir)
    debugger.run(args)


if __name__ == "__main__":
    main()
