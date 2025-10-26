# rdfexport Task Report – 2025-10-26

## Summary
- Hardened `SourceCSVPreprocessor.dump` to tolerate direct file targets by guarding the directory creation step.
- Normalised increment handling now excludes base columns that collide with grouped suffixes so the generated 1NF tables no longer duplicate fields.
- Regenerated debug artefacts and consolidated test logs after the full `bun run test:all:log:linux` sweep.

## Tests
- `bun run lint`
- `bun run format:check`
- `bun run test:all:log:linux`
- `bun run test:all:log:show`
