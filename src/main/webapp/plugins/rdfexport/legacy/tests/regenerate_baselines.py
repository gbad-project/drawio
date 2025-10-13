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

from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[5]
LEGACY_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = LEGACY_DIR.parent / "tests" / "fixtures"
BASELINES_DIR = LEGACY_DIR.parent / "tests" / "baselines"
TEST_PATH = LEGACY_DIR / "tests" / "test_patched_parser.py"
PARSER_RELATIVE_PATH = Path(
    "src/main/webapp/plugins/rdfexport/legacy/draw_io_parser.py"
)


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

        spec = importlib.util.spec_from_file_location(
            "_legacy_draw_io_parser", parser_path
        )
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
    """Discover all fixture files that need baseline generation."""
    for fixture in sorted(FIXTURES_DIR.glob("*.drawio")):
        # AICODE-NOTE:
        # Never remove the below commented out block.
        # It must stay. Signed-off: human
        #
        # if "-with-metadata" in fixture.name:
        #    continue
        yield fixture


def _serialise_graph(graph: Graph) -> str:
    """Serialize a graph to N-Triples deterministically (sorted lexicographically)."""
    raw = graph.serialize(format="nt")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    lines = sorted(line for line in raw.splitlines() if line.strip())
    return "\n".join(lines) + "\n"


def _candidate_commits(start_ref: str, limit: int) -> Sequence[str]:
    """Get a list of candidate commits to try for baseline generation."""
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
        raise RuntimeError(
            f"No commits found when traversing from reference {start_ref}"
        )
    return commits


def _generate_graphs_from_commit(
    commit: str, substitute: List[str]
) -> Tuple[List[Tuple[Path, Graph]], List[Tuple[Path, Exception]]]:
    """Generate baseline graphs using the parser from a specific commit.

    This loads the historical parser code exactly as it was, with no modifications.
    Returns (successful_graphs, failed_fixtures).
    """
    with (
        PreviousParserLoader(commit) as legacy_parser,
        PreviousParserLoader("HEAD") as current_parser,
    ):
        parse_drawio = getattr(legacy_parser, "parse_drawio_to_graph", None)
        if parse_drawio is None:
            raise AttributeError("Legacy parser does not expose parse_drawio_to_graph")

        get_ontology_iri = getattr(current_parser, "get_ontology_iri", None)
        mock_ontology_iri = get_ontology_iri("mock")

        graphs: List[Tuple[Path, Graph]] = []
        failures: List[Tuple[Path, Exception]] = []
        for fixture in _discover_pristine_fixtures():
            try:
                graph = parse_drawio(
                    str(fixture),
                    ontology_iri=mock_ontology_iri,
                    metacharacter_substitute=substitute,
                )
                graphs.append((fixture, graph))
            except Exception as exc:
                failures.append((fixture, exc))
    return graphs, failures


def regenerate_baselines(
    commit_candidates: Sequence[str],
    *,
    substitute: List[str],
    overwrite: bool,
) -> Tuple[str, List[Tuple[Path, Path]], List[Tuple[Path, Exception]], List[str]]:
    """Attempt to regenerate baselines from candidate commits.

    Tries each commit in order until one successfully generates at least some baselines.
    Returns the successful commit, list of generated files, failed fixtures, and commit failures.

    Raises BaselineGenerationError if no commit succeeds in generating ANY baselines.
    """
    failed_commits: List[str] = []
    last_error: Exception | None = None

    for commit in commit_candidates:
        try:
            graphs, fixture_failures = _generate_graphs_from_commit(
                commit, substitute=substitute
            )
        except Exception as exc:
            failed_commits.append(f"{commit}: {exc}")
            last_error = exc
            continue

        # If we got at least one graph, consider it a success
        if not graphs:
            failed_commits.append(f"{commit}: No fixtures could be parsed")
            continue

        # Success - write baselines for what we could parse
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        generated: List[Tuple[Path, Path]] = []
        for fixture, graph in graphs:
            baseline_path = BASELINES_DIR / f"{fixture.stem}.nt"
            if baseline_path.exists() and not overwrite:
                generated.append((fixture, baseline_path))
                continue
            baseline_path.write_text(_serialise_graph(graph), encoding="utf-8")
            generated.append((fixture, baseline_path))
        return commit, generated, fixture_failures, failed_commits

    # No commit succeeded
    if last_error is not None:
        raise BaselineGenerationError(
            f"Unable to generate baselines from any candidate commit. "
            f"Tried {len(commit_candidates)} commit(s). Last error: {last_error}"
        )
    raise BaselineGenerationError("No commits were attempted when generating baselines")


def run_pytest(pytest_args: List[str]) -> None:
    """Execute pytest with the given arguments."""
    command = [sys.executable, "-m", "pytest"] + pytest_args
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        required=True,
        help="Git reference to start searching for a legacy draw_io_parser (e.g., commit hash or HEAD^)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=1,
        help="Maximum number of commits to traverse when searching for a usable parser (default: 1)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Regenerate baselines without executing pytest afterwards",
    )
    parser.add_argument(
        "--metacharacter-substitute",
        nargs="*",
        default=["url"],
        help="Value forwarded to parse_drawio_to_graph(metacharacter_substitute=...)",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Rewrite existing baselines instead of leaving them unchanged",
    )
    args = parser.parse_args()

    commit_candidates = _candidate_commits(args.commit, args.max_commits)

    print(
        f"Attempting to regenerate baselines from {len(commit_candidates)} commit(s)..."
    )
    print(f"Starting at: {args.commit}")

    try:
        chosen_commit, generated, fixture_failures, failures = regenerate_baselines(
            commit_candidates,
            substitute=list(args.metacharacter_substitute),
            overwrite=args.force_overwrite,
        )
    except BaselineGenerationError as exc:
        print(f"\n❌ FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    if failures:
        print("\n⚠️  Failed commits during baseline regeneration:")
        for failure in failures:
            print(f"  {failure}")

    print(f"\n✅ Baselines regenerated using commit {chosen_commit}")
    for fixture, baseline in generated:
        relative_fixture = fixture.relative_to(REPO_ROOT)
        relative_baseline = baseline.relative_to(REPO_ROOT)
        action = "overwrote" if args.force_overwrite else "created"
        print(f"  {action}: {relative_fixture} -> {relative_baseline}")

    if fixture_failures:
        print(
            f"\n⚠️  Failed to generate baselines for {len(fixture_failures)} fixture(s):"
        )
        for fixture, exc in fixture_failures:
            relative_fixture = fixture.relative_to(REPO_ROOT)
            print(f"  ❌ {relative_fixture}")
            print(f"     {exc}")

    if not args.skip_tests:
        print(f"\n🧪 Running tests: {TEST_PATH.relative_to(REPO_ROOT)}")
        run_pytest([str(TEST_PATH.relative_to(REPO_ROOT)), "-v"])


if __name__ == "__main__":
    main()
