# RDF Export Node Classification Update — 2025-02-14

## Overview
- Introduced a central `DrawIONodeClassifier` helper to normalise CURIE, URI, individual, and literal handling across overrides.
- Extended parser overrides to record literal connectivity, enforce literal-source validation, and surface decoration notes via `skos:note`.
- Added regression coverage capturing typed individuals, standalone CURIE/URI nodes, literal decorations, and error scenarios.

## Key Changes
1. `legacy/overrides/node_classifier.py`
   - Added classification utilities (`NodeKind`, `NodeClassification`, `LiteralInfo`).
   - Ensures CURIE expansion leverages shared rdflib namespace manager bindings.
2. `legacy/overrides/curie_validator.py`
   - Routed `_extract_individual_and_arrow_and_literal_cells`, `_source_or_target`, and `_arrow` through the new classifier.
   - Ensured individual blocks register untyped individuals and mark literal decorations for downstream serialisation.
   - Added SKOS note emission for disconnected literal decorations.
3. `legacy/tests/test_node_classifier.py`
   - Crafted targeted XML payloads that validate typed nodes, CURIE/URI individuals, literal decorations, and literal-source rejection.
4. `ChangeLog`
   - Documented the classifier overhaul and decoration handling.

## Testing
- `bun run lint`
- `ruff format --check .`
- `prettier --check .`
- `bun run test:log:linux`
