#!/usr/bin/env python3
"""Run legacy and pipeline RML workflows and capture RMLMapper outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from legacy.tests import rmlmapper_workflows as workflows  # noqa: E402


def _normalise_csv_choices(values: list[str]) -> list[str]:
    lookup = {"csv": "csv_path", "normalized": "normalized_csv_path"}
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key not in lookup:
            raise ValueError(f"Unsupported CSV selector: {value}")
        result.append(lookup[key])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=workflows.PLUGIN_DIR / "debug" / "results" / "rmlmapper",
        help="Directory where workflow artefacts will be written.",
    )
    parser.add_argument(
        "--csv",
        action="append",
        choices=["csv", "normalized"],
        default=["csv", "normalized"],
        help="Select which CSV inputs to feed into map_schema (default: both).",
    )
    parser.add_argument(
        "--keep-debug",
        action="store_true",
        help="Retain intermediate debug scenario outputs under debug/results.",
    )
    args = parser.parse_args()

    manifest = workflows.ensure_rmlmapper_setup()
    csv_attributes = _normalise_csv_choices(args.csv)

    output_root: Path = args.output
    output_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict[str, object]] = {}

    for fixture in workflows.FIXTURES:
        fixture_dir = output_root / fixture.slug
        fixture_dir.mkdir(parents=True, exist_ok=True)

        map_schema_results: dict[str, workflows.WorkflowResult] = {}
        for attr in csv_attributes:
            result = workflows.run_map_schema_workflow(
                fixture,
                manifest=manifest,
                csv_path=getattr(fixture, attr),
                output_dir=fixture_dir / "map-schema" / attr,
            )
            map_schema_results[attr] = result

        pipeline_result = workflows.run_pipeline_workflow(
            fixture,
            manifest=manifest,
            drawio_path=fixture.normalized_drawio_path,
            csv_path=fixture.normalized_csv_path,
            output_dir=fixture_dir / "pipeline",
            persist_results=args.keep_debug,
        )

        comparison = {}
        canonical_reference = map_schema_results.get("normalized_csv_path")
        canonical_result = None
        if canonical_reference is not None:
            canonical_result = workflows.canonicalize_for_comparison(
                canonical_reference.turtle_graph, pipeline_result.turtle_graph
            )
            comparison["normalized_csv_path"] = {
                "isomorphic": workflows.graphs_are_isomorphic(
                    canonical_result.map_graph, canonical_result.pipeline_graph
                ),
                "shared_triples": len(canonical_result.shared_graph),
                "map_only": canonical_result.map_only_count,
                "pipeline_only": canonical_result.pipeline_only_count,
                "map_triples": len(canonical_result.map_graph),
                "pipeline_triples": len(canonical_result.pipeline_graph),
            }
        for attr, result in map_schema_results.items():
            if attr == "normalized_csv_path" and canonical_result is not None:
                continue
            comparison[attr] = workflows.graphs_are_isomorphic(
                pipeline_result.turtle_graph, result.turtle_graph
            )

        summary[fixture.slug] = {
            "map_schema": {
                attr: {
                    "rml": str(res.rml_path.relative_to(workflows.PLUGIN_DIR)),
                    "turtle": str(res.turtle_path.relative_to(workflows.PLUGIN_DIR)),
                    "triples": len(res.turtle_graph),
                    "source": res.source,
                }
                for attr, res in map_schema_results.items()
            },
            "pipeline": {
                "rml": str(pipeline_result.rml_path.relative_to(workflows.PLUGIN_DIR)),
                "turtle": str(
                    pipeline_result.turtle_path.relative_to(workflows.PLUGIN_DIR)
                ),
                "triples": len(pipeline_result.turtle_graph),
                "source": pipeline_result.source,
            },
            "isomorphism": comparison,
        }

    report_path = output_root / "report.json"
    report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
