#!/usr/bin/env python3
"""Utility to regenerate parser baselines from a previous commit and rerun tests."""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF


REPO_ROOT = Path(__file__).resolve().parents[5]
LEGACY_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = LEGACY_DIR.parent / "tests" / "fixtures"
BASELINES_DIR = LEGACY_DIR.parent / "tests" / "baselines"
TEST_PATH = LEGACY_DIR / "tests" / "test_curie_validation.py"
PARSER_RELATIVE_PATH = Path("src/main/webapp/plugins/rdfexport/legacy/draw_io_parser.py")

LEGACY_OBJECT_PROPERTY_BACKFILL: set[str] = set()
LEGACY_DATATYPE_PROPERTY_BACKFILL = {
    "rdfs:isDefinedBy",
}


class PreviousParserLoader:
    """Context manager that loads draw_io_parser.py from a specific commit."""

    def __init__(self, commit: str) -> None:
        self.commit = commit
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.module = None

    def __enter__(self):  # type: ignore[override]
        self._temp_dir = tempfile.TemporaryDirectory()
        parser_source = self._read_parser_from_commit()
        parser_path = Path(self._temp_dir.name) / "draw_io_parser.py"
        parser_path.write_text(parser_source, encoding="utf-8")

        spec = importlib.util.spec_from_file_location("_legacy_draw_io_parser", parser_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to create import spec for legacy draw_io_parser")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.module = module
        return module

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
        if self.module is not None:
            sys.modules.pop(self.module.__name__, None)

    def _read_parser_from_commit(self) -> str:
        commit_path = f"{self.commit}:{PARSER_RELATIVE_PATH.as_posix()}"
        try:
            result = subprocess.run(
                ["git", "show", commit_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=REPO_ROOT,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to read draw_io_parser.py from commit {self.commit}: {exc.stderr.strip()}"
            ) from exc
        return result.stdout


class BaselineGenerationError(RuntimeError):
    """Raised when no suitable commit can be used to regenerate baselines."""


def _discover_pristine_fixtures() -> Iterable[Path]:
    for fixture in sorted(FIXTURES_DIR.glob("*.drawio")):
        if "-with-metadata" in fixture.name:
            continue
        yield fixture


def _serialise_graph(graph: Graph) -> str:
    raw = graph.serialize(format="nt")
    return raw if raw.endswith("\n") else f"{raw}\n"


def _candidate_commits(start_ref: str, limit: int) -> Sequence[str]:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--max-count", str(limit), start_ref],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Unable to enumerate commits from reference {start_ref}: {exc.stderr.strip()}"
        ) from exc
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not commits:
        raise RuntimeError(f"No commits found when traversing from reference {start_ref}")
    return commits


def _extend_property_collection(collection, additions: Iterable[str]) -> None:
    if isinstance(collection, list):
        for item in additions:
            if item not in collection:
                collection.append(item)
    elif isinstance(collection, set):
        collection.update(additions)
    elif isinstance(collection, tuple):
        buffer = list(collection)
        _extend_property_collection(buffer, additions)
        collection = type(collection)(buffer)  # type: ignore[assignment]
    # Unexpected types are ignored.


def _backfill_legacy_property_sets(module) -> None:
    object_props = getattr(module, "_object_properties", None)
    if object_props is not None:
        _extend_property_collection(object_props, LEGACY_OBJECT_PROPERTY_BACKFILL)
    datatype_props = getattr(module, "_datatype_properties", None)
    if datatype_props is not None:
        _extend_property_collection(datatype_props, LEGACY_DATATYPE_PROPERTY_BACKFILL)


def _strip_backfill_property_declarations(graph: Graph) -> None:
    nm = graph.namespace_manager
    for curie in LEGACY_OBJECT_PROPERTY_BACKFILL:
        try:
            uri = nm.expand_curie(curie, strict=False)
        except Exception:  # pragma: no cover - defensive path
            continue
        if isinstance(uri, URIRef):
            graph.remove((uri, RDF.type, OWL.ObjectProperty))
    for curie in LEGACY_DATATYPE_PROPERTY_BACKFILL:
        try:
            uri = nm.expand_curie(curie, strict=False)
        except Exception:  # pragma: no cover - defensive path
            continue
        if isinstance(uri, URIRef):
            graph.remove((uri, RDF.type, OWL.DatatypeProperty))


def _generate_graphs_from_commit(commit: str, substitute: List[str]) -> List[Tuple[Path, Graph]]:
    with PreviousParserLoader(commit) as legacy_parser:
        parse_drawio = getattr(legacy_parser, "parse_drawio_to_graph", None)
        if parse_drawio is None:
            raise AttributeError("Legacy parser does not expose parse_drawio_to_graph")

        _backfill_legacy_property_sets(legacy_parser)

        graphs: List[Tuple[Path, Graph]] = []
        for fixture in _discover_pristine_fixtures():
            try:
                graph = parse_drawio(str(fixture), metacharacter_substitute=substitute)
            except Exception as exc:  # pylint: disable=broad-except
                raise RuntimeError(
                    f"Commit {commit} failed while parsing {fixture.relative_to(REPO_ROOT)}: {exc}"
                ) from exc
            _strip_backfill_property_declarations(graph)
            graphs.append((fixture, graph))
    return graphs


def regenerate_baselines(
    commit_candidates: Sequence[str],
    *,
    substitute: List[str],
    allow_head_fallback: bool,
    overwrite: bool,
) -> Tuple[str, List[Tuple[Path, Path]], List[str]]:
    failed_commits: List[str] = []
    last_error: Exception | None = None
    for commit in commit_candidates:
        try:
            graphs = _generate_graphs_from_commit(commit, substitute=substitute)
        except Exception as exc:  # pylint: disable=broad-except
            failed_commits.append(f"{commit}: {exc}")
            last_error = exc
            continue

        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        generated: List[Tuple[Path, Path]] = []
        for fixture, graph in graphs:
            baseline_path = BASELINES_DIR / f"{fixture.stem}.nt"
            if baseline_path.exists() and not overwrite:
                generated.append((fixture, baseline_path))
                continue
            baseline_path.write_text(_serialise_graph(graph), encoding="utf-8")
            generated.append((fixture, baseline_path))
        return commit, generated, failed_commits

    if allow_head_fallback:
        graphs = _generate_graphs_from_commit("HEAD", substitute=substitute)
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        generated: List[Tuple[Path, Path]] = []
        for fixture, graph in graphs:
            baseline_path = BASELINES_DIR / f"{fixture.stem}.nt"
            if baseline_path.exists() and not overwrite:
                generated.append((fixture, baseline_path))
                continue
            baseline_path.write_text(_serialise_graph(graph), encoding="utf-8")
            generated.append((fixture, baseline_path))
        return "HEAD", generated, failed_commits

    if last_error is not None:
        raise BaselineGenerationError(
            "Unable to generate baselines from any candidate commit. Last error: "
            f"{last_error}"
        )
    raise BaselineGenerationError("No commits were attempted when generating baselines")


def run_pytest(pytest_args: List[str]) -> None:
    command = [sys.executable, "-m", "pytest"] + pytest_args
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        default="HEAD^",
        help="Git reference to start searching for a legacy draw_io_parser (default: HEAD^)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=50,
        help="Maximum number of commits to traverse when searching for a usable parser",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Regenerate baselines without executing pytest afterwards",
    )
    parser.add_argument(
        "--metacharacter-substitute",
        nargs="*",
        default=["remove"],
        help="Value forwarded to parse_drawio_to_graph(metacharacter_substitute=...)",
    )
    parser.add_argument(
        "--no-head-fallback",
        action="store_true",
        help="Fail instead of falling back to the current commit when no legacy parser succeeds",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Rewrite existing baselines instead of leaving them unchanged",
    )
    args = parser.parse_args()

    commit_candidates = _candidate_commits(args.commit, args.max_commits)
    chosen_commit, generated, failures = regenerate_baselines(
        commit_candidates,
        substitute=list(args.metacharacter_substitute),
        allow_head_fallback=not args.no_head_fallback,
        overwrite=args.force_overwrite,
    )

    if failures:
        print("Failed commits during baseline regeneration:")
        for failure in failures:
            print(f"  {failure}")

    print(f"Baselines regenerated using commit {chosen_commit}")
    for fixture, baseline in generated:
        relative_fixture = fixture.relative_to(REPO_ROOT)
        relative_baseline = baseline.relative_to(REPO_ROOT)
        print(f"  {relative_fixture} -> {relative_baseline}")

    if not args.skip_tests:
        run_pytest([str(TEST_PATH.relative_to(REPO_ROOT))])


if __name__ == "__main__":
    main()
