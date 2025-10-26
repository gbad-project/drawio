from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

RDFEXPORT_DIR = Path(__file__).resolve().parents[1]

if str(RDFEXPORT_DIR) not in sys.path:
    sys.path.insert(0, str(RDFEXPORT_DIR))

from debug.__main__ import estimate_triple_count_from_classifications  # noqa: E402
from legacy import draw_io_parser  # noqa: E402


FIXTURES_DIR = RDFEXPORT_DIR / "tests" / "fixtures"
DEBUG_DIR = RDFEXPORT_DIR / "debug"

EXPECTED_TS_PLUGIN = {
    "AA37-with-metadata-severely-mocked.drawio": {
        "reason": "ts_plugin expectedly fails because picoL: prefix was intentionally not specified in XML UserObject. Run a manual scenario to confirm that this works once all prefixes are supplied (if prefixes are overriden, they are overriden completely, so all prefixes are resupplied through the scenario config).",
        "command": [
            "python",
            "-m",
            "debug",
            "--scenario",
            "aa37-with-metadata-severely-mocked",
        ],
    },
    "AA37-with-metadata-even-more-severely-mocked.drawio": {
        "reason": """ts_plugin expectedly fails because picoL: had invalid prefix IRI in XML UserObject. Run a manual scenario to confirm that this works once all prefixes are supplied (if prefixes are overriden, they are overriden completely, so all prefixes are resupplied through the scenario).

Also, there is a separate reason for within-debug xfail. To quote codex:

### Findings

-   The DrawIO fixture intentionally declares the `picoL` prefix with an invalid IRI (`sdfsdf` has no scheme), so the TypeScript pipeline drops that prefix when it serializes the graph produced by `bun run debug:all`. The generated Turtle therefore types `https://example.com` as `:j` (falling back to the base prefix) and never emits `picoL:j`.

-   Despite the dropped prefix, the classification metadata captured in `debug/map.json` still records `https://example.com` as a standalone individual with the token `picoL:j`, so `_ensure_graph_covers_classifications` insists on seeing that exact type in the Turtle and raises the assertion you observed.

-   When you run the canned manual scenario (`python -m debug --scenario aa37-with-metadata-even-more-severely-mocked`), the scenario file overrides the preamble with a valid `mock://sample-test2` IRI for `picoL`. That lets the pipeline keep the prefix, and the Turtle emitted under `debug/results/aa37-with-metadata-even-more-severely-mocked/` does contain the expected `picoL:j` triple, which explains why that run succeeds.

-   The file you inspected that already had `picoL:j` was almost certainly the manual-scenario output (`debug/results/aa37-with-metadata-even-more-severely-mocked/...`). The artifacts from `bun run debug:all` live beside it but are prefixed with `pytest-...`; those versions still show the sanitized `:j` type and trigger the assertion.

In short, the failure stems from the fixture's deliberately broken prefix IRI: the parser records `picoL:j`, the serializer removes the invalid `picoL` namespace, and the regression check can't reconcile the two unless you supply a valid preamble (as the manual scenario does).""",
        "command": [
            "python",
            "-m",
            "debug",
            "--scenario",
            "aa37-with-metadata-even-more-severely-mocked",
        ],
    },
    "General_Authority_bleep_mock.drawio": {
        "reason": "ts_plugin expectedly fails because bleep: prefix was intentionally not specified in XML UserObject. Run a manual scenario to confirm that this works once this prefix is supplied.",
        "command": [
            "python",
            "-m",
            "debug",
            "--scenario",
            "general-authority-bleep-mock",
        ],
    },
    "AA37-with-metadata-even-more-severely-mocked-v2.drawio": {
        "reason": "ts_plugin expectedly fails (for now) because now that rounded=1 is recognized as a literal, arrow lol:kek becomes an arrow between two literals. However, once `http://Some node that should...` is reclassified as an individual as it should, this should pass. Manual command will mirror the outcome.",
        "command": [
            "python",
            "-m",
            "debug",
            "--scenario",
            "aa37-with-metadata-even-more-severely-mocked-v2",
        ],
    },
}

ALLOWED_XFAILS_FOLLOWUP = {
    "AA37-with-metadata-even-more-severely-mocked-v2.drawio": {
        "reason": "Failure of manual command mirrors the outcome of pytest run: ts_plugin expectedly fails (for now) because now that rounded=1 is recognized as a literal, arrow lol:kek becomes an arrow between two literals. However, once `http://Some node that should...` is reclassified as an individual as it should, this should pass.",
    },
    "Flowchart_tweaked.drawio": {
        "reason": "Failure of manual command mirrors the outcome of pytest run: ts_plugin expectedly fails (for now) because IRIs in arrows are currently unrecognized.",
    },
}

XFAlLED_FIXTURES: list[str] = []


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"pytest-{slug or 'scenario'}"


def _load_prefixes(xml_text: str) -> dict[str, str]:
    metadata_prefixes, _, _, _ = draw_io_parser._extract_drawio_metadata(xml_text)
    prefixes = draw_io_parser.get_prefixes()
    prefixes.update(metadata_prefixes)
    return prefixes


def _ensure_graph_covers_classifications(
    graph: Graph,
    classifications: dict[str, dict],
    xml_text: str,
) -> None:
    prefixes = _load_prefixes(xml_text)
    namespace_manager = Graph().namespace_manager
    for prefix, iri in prefixes.items():
        namespace_manager.bind(prefix, iri, replace=True)

    classifier_cls = draw_io_parser.pipeline.core.xml.data.DrawIOCellClassifier
    default_type = getattr(
        classifier_cls, "DEFAULT_STANDALONE_TYPE", "owl:NamedIndividual"
    )

    identifiers: set[str] = set()
    for cell_data in classifications.values():
        kind = cell_data.get("kind")
        raw_value = (cell_data.get("raw_value") or "").strip()
        if not raw_value:
            continue
        if kind == "STANDALONE_INDIVIDUAL":
            identifier = cell_data.get("identifier") or raw_value
            if identifier:
                identifiers.add(identifier)
        if kind == "TYPED_INDIVIDUAL":
            identifier = cell_data.get("parent_identifier") or cell_data.get(
                "identifier"
            )
            if identifier:
                identifiers.add(identifier)

    identifier_subjects: dict[str, set] = {}
    for identifier in identifiers:
        subjects = {
            subject for subject in graph.subjects(RDFS.label, Literal(identifier))
        }
        identifier_subjects[identifier] = subjects
        assert subjects, f"Missing label triple for identifier '{identifier}'"

    for cell_id, cell_data in classifications.items():
        raw_value = (cell_data.get("raw_value") or "").strip()
        if not raw_value:
            continue

        kind = cell_data.get("kind")

        if kind == "STANDALONE_INDIVIDUAL":
            identifier = cell_data.get("identifier") or raw_value
            subjects = identifier_subjects.get(identifier, set())
            assert subjects, f"No subjects found for standalone '{identifier}'"
            tokens = [token for token in cell_data.get("tokens", []) if token]
            if not tokens:
                tokens = [default_type]
            for token in tokens:
                expanded = namespace_manager.expand_curie(token)
                assert any(
                    (subject, RDF.type, URIRef(expanded)) in graph
                    for subject in subjects
                ), f"Missing rdf:type '{token}' for '{identifier}'"
            continue

        if kind == "TYPED_INDIVIDUAL":
            identifier = cell_data.get("parent_identifier") or cell_data.get(
                "identifier"
            )
            if not identifier:
                continue
            subjects = identifier_subjects.get(identifier, set())
            assert subjects, f"No subjects found for typed '{identifier}'"
            for token in cell_data.get("tokens", []):
                if not token:
                    continue
                expanded = namespace_manager.expand_curie(token)
                assert any(
                    (subject, RDF.type, URIRef(expanded)) in graph
                    for subject in subjects
                ), f"Missing rdf:type '{token}' for '{identifier}'"
            continue

        if kind == "LITERAL":
            assert any(
                str(obj) == raw_value for _, _, obj in graph.triples((None, None, None))
            ), f"Literal '{raw_value}' not found in graph"
            continue

        if kind == "DECORATION":
            assert any(
                obj == Literal(raw_value)
                for _, _, obj in graph.triples((None, SKOS.note, None))
            ), f"Decoration '{raw_value}' missing from SKOS notes"
            continue

        if kind == "ARROW_LABEL":
            if ":" not in raw_value:
                continue
            prefix = raw_value.split(":", 1)[0]
            if prefix not in prefixes:
                continue
            expanded = namespace_manager.expand_curie(raw_value)
            assert any(
                predicate == URIRef(expanded)
                for _, predicate, _ in graph.triples((None, None, None))
            ), f"Property '{raw_value}' not used in graph"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(FIXTURES_DIR.glob("*.drawio"), key=lambda path: path.name),
    ids=lambda path: path.name,
)
def test_debug_cli_matches_expected_triple_counts(fixture_path: Path) -> None:
    slug = _slugify(fixture_path.stem)
    cmd = [
        sys.executable,
        "-m",
        "debug",
        "--drawio",
        str(fixture_path),
        "--slug",
        slug,
        "--format",
        "turtle",
        "--parser-option",
        "ontology_iri=mock://pytest-debug-ontology",
    ]

    # This exits 1 on any error, so we set check=False
    subprocess.run(cmd, cwd=RDFEXPORT_DIR, check=False, capture_output=True)

    map_path = DEBUG_DIR / "map.json"
    map_data = json.loads(map_path.read_text(encoding="utf-8"))
    scenario_entry = map_data["scenarios"].get(slug)
    assert scenario_entry is not None, f"Scenario '{slug}' not recorded"

    classifications = scenario_entry.get("cell_classifications", {})
    xml_text = fixture_path.read_text(encoding="utf-8")

    results = scenario_entry.get("results", {})
    if "ts_plugin" not in results:
        errors = scenario_entry.get("errors", {})
        assert "ts_plugin" in errors, "ts_plugin graph missing without recorded error"
        fname = fixture_path.name
        if fname in EXPECTED_TS_PLUGIN:
            entry = EXPECTED_TS_PLUGIN[fname]
            reason = f"{entry['reason']}  |  Command: python {' '.join(entry.get('command', []))}"
            XFAlLED_FIXTURES.append(fname)
            pytest.xfail(reason)
        pytest.fail(
            f"Unexpected skip: ts_plugin graph unavailable for {fname}. Errors: {errors.get('ts_plugin')}"
        )

    ttl_path = DEBUG_DIR / results["ts_plugin"]["path"]
    assert ttl_path.exists(), f"Turtle output missing for {fixture_path.name}"

    graph = Graph()
    graph.parse(ttl_path, format="turtle")

    expected_triples = estimate_triple_count_from_classifications(
        xml_text, classifications, graph=graph
    )
    actual_triples = results["ts_plugin"]["triples"]
    assert actual_triples == expected_triples, (
        f"Triple count mismatch for {fixture_path.name}"
    )

    try:
        _ensure_graph_covers_classifications(graph, classifications, xml_text)
    except AssertionError as e:
        fname = fixture_path.name
        msg = f"Graph/classification mismatch in {fname}: {e}"
        if fname in EXPECTED_TS_PLUGIN:
            XFAlLED_FIXTURES.append(fname)
            pytest.xfail(msg)
        else:
            pytest.fail(msg)


# @pytest.mark.dependency(depends=["test_debug_cli_matches_expected_triple_counts"])
def _scenario_slug_from_command(command: list[str]) -> str | None:
    try:
        index = command.index("--scenario")
    except ValueError:
        return None
    try:
        return command[index + 1]
    except IndexError:
        return None


def test_run_manual_scenarios_after_xfails() -> None:
    if not XFAlLED_FIXTURES:
        pytest.skip("No expected xfails to rerun manually.")

    map_path = DEBUG_DIR / "map.json"

    for fname in XFAlLED_FIXTURES:
        entry = EXPECTED_TS_PLUGIN[fname]
        reason = entry["reason"]
        command = entry.get("command")

        print(f"\n[Running follow-up scenario for {fname}]")
        print(f"Reason: {reason}")

        if not command:
            pytest.fail("No command specified for this xfail scenario.")

        scenario_slug = _scenario_slug_from_command(command)
        if not scenario_slug:
            pytest.fail(
                f"Unable to determine scenario slug from follow-up command for {fname}."
            )

        resolved_command = list(command)
        venv_python = RDFEXPORT_DIR / ".venv" / "bin" / "python"
        if (
            resolved_command
            and resolved_command[0] == "python"
            and venv_python.exists()
        ):
            resolved_command[0] = str(venv_python)

        result = subprocess.run(
            resolved_command, cwd=RDFEXPORT_DIR, capture_output=True, text=True
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        map_data = json.loads(map_path.read_text(encoding="utf-8"))
        scenario_entry = map_data["scenarios"].get(scenario_slug)
        if not scenario_entry:
            pytest.fail(
                "Scenario '%s' not recorded after command. stdout:\n%s\nstderr:\n%s"
                % (scenario_slug, result.stdout, result.stderr)
            )

        errors = scenario_entry.get("errors", {}) or {}
        unexpected_errors = {
            name: details
            for name, details in errors.items()
            if name != "py_legacy" and details
        }

        if unexpected_errors:
            if fname in ALLOWED_XFAILS_FOLLOWUP:
                pytest.xfail(ALLOWED_XFAILS_FOLLOWUP[fname]["reason"])
            pytest.fail(
                "Scenario '%s' still reports errors: %s\nstdout:\n%s\nstderr:\n%s"
                % (
                    scenario_slug,
                    unexpected_errors,
                    result.stdout,
                    result.stderr,
                )
            )

        print(f"[OK] {fname} completed successfully.\n")


if __name__ == "__main__":
    import pytest

    # Executes tests verbosely (-v) and, with -rA, displays a detailed summary of all test results — including passed, failed, skipped, xfailed, and xpassed tests — at the end of the run.
    pytest.main(["-v", "-rA", __file__])
