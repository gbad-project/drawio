# Map Schema Workflow Graph Artifacts

This directory captures Turtle graphs generated while preparing the `MapSchemaWorkflow` fixtures for review.

* `graphs/general-*-left.ttl` files: produced end-to-end via `run_map_schema_workflow`, using the DrawIO scenario, legacy `map_schema.py`, and RMLMapper.
* `graphs/general-*-right.ttl` files: generated directly by RMLMapper using the published RML fixture with its CSV preprocessed by `SourceCSVPreprocessor`.

The committed outputs allow reviewers to diff the "left" (workflow) and "right" (fixture) graphs without having to reproduce the full workflow locally.
