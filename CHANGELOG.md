# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
### Added
- **Task 1 – DrawIO Black Box Integration (completed 2025-10-08 by gpt-5-codex)** — Routed the DrawIO export workflow through the new `runMockBlackBox` helper so serialized XML is annotated with deterministic `[BLACKBOX] len=<n>` wrappers before invoking the existing save routine, restored the checksum-guarded regression harness, and expanded Bun tests to cover the annotated payload end-to-end (commits 56fe128, 1fa6390; report `docs/aicode/gpt-5-codex-report-20251008T180943Z.md`).
- **Task 2a – Remove Hardcoded Classes and Property CURIEs from DrawIO Parser (completed 2025-10-09 by gpt-5-codex)** — Replaced static RiC-O property allowlists with prefix-driven CURIE validation via `_split_curie`/`_ensure_known_curie`, reworked edge classification so literal/object detection comes from parsed nodes, and produced deterministic `.nt` baselines with new pytest suites and regeneration tooling to prove graph isomorphism (commits 3087ac1, dbc1f14, da3ee356; report `docs/aicode/gpt-5-codex-report-20251009T045342Z.md`).
- **Task 2b – Extend DrawIO Parser to Support Embedded Metadata (stdin → DrawIOParserGraph) (completed 2025-10-09 by gpt-5-codex)** — Introduced the `DrawIOParserGraph` subclass that persists CSV paths, base URIs, and namespace bindings, centralized parsing via `_build_graph_from_raw_xml`, and added metadata-patched fixture regressions plus pytest coverage to verify rdflib integration and metadata propagation (commits f1b812c, da3ee356, a28a81a; report `docs/aicode/gpt-5-codex-report-20250214T120000Z.md`).
- **Task 4 – Phase 1 – Pyodide Integration & Debug Infrastructure (completed 2025-10-09 by gpt-5-codex)** — Bootstrapped a Node-compatible Pyodide runtime with structured logging, an async mock pipeline that prefixes outputs with `mock:`, Bun tests that exercise the Pyodide bridge, and dependency management via `uv`/`bun.lock` updates to satisfy the in-browser execution harness (commit b46b82f; report `docs/aicode/gpt-5-codex-report-20251009T123258Z.md`).
