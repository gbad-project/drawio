# RDF serializer refactor to consume classifier output

## Summary
- Updated `serialisers` overrides so `RDFSerializationHelper` builds blocks and property sets from `DrawIOCellClassifier` data rather than the `individual_blocks` helper.
- Propagated the new serializer signature through `_build_graph_from_raw_xml` and removed the now-unused `individual_blocks` override.
- Reworked Python tests to validate object/datatype property handling via the serializer directly.
- Regenerated the patched parser bundle and verified generated artifacts.

## Testing
- `bun run check`
- `bun run test:all:log:linux`
