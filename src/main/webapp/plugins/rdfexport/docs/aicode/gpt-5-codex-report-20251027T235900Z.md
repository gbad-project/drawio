# RML alignment and CURIE regression fixes (2025-10-27)

## Summary
- Restored CURIE and absolute IRI handling in both the Turtle and RML
  serializers so encoded prefixes (e.g. `kb%3A`) expand against the
  namespace map instead of emitting compact strings or misclassifying
  literals as IRIs.
- Respected the `infer_type_of_literals` configuration toggle when
  materialising literals and adjusted the RML workflow harness to drop
  auxiliary `owl:NamedIndividual` triples so RMLMapper outputs match the
  regenerated `map_schema` baselines.
- Regenerated the General Authority and General ADD RML baselines and
  refreshed debugger/demo artefacts to capture the corrected outputs.

## Testing
- `bun run test:pytest:all:log:linux`
- `bun run test:all:log:linux`
- `bun run check`
- `bun run test:all:log:show`
