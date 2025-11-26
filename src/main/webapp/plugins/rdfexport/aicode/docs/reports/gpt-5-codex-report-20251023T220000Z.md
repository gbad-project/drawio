# rdfexport metadata canonicalisation follow-up (2025-10-23)

## Summary
- Normalised DrawIO metadata handling around a canonical `<gbadMetadata>`
  container in TypeScript (`src/rdfexport.ts`) so parser settings, stripHtml,
  and strict flags persist across UI actions and serialised XML payloads.
- Synced Python overrides to prefer the new tag while tolerating legacy
  `<UserObject>/<object>` containers (`legacy/overrides/metadata_extraction.py`,
  `metadata_cleanup.py`, and `rml_export.py`).
- Taught the debugger metadata patcher (`debug/__main__.py`) and
  test fixtures (including `tests/fixtures/Flowchart_tweaked.drawio`) to surface
  prefixes via the canonical node, resolving the Flowchart regression and keeping
  regenerated `.drawio` assets consistent with the plugin.
- Regenerated Bun + pytest debug logs and scenario artefacts so CI mirrors the
  updated metadata contract.

## Investigation Notes
- Verified `_strip_metadata_user_object` converts `<gbadMetadata>` back to the
  expected `<mxCell id="0">` during parser regeneration.
- Confirmed `Flowchart_tweaked.drawio` previously lost the `kb` prefix in
  TypeScript pipeline runs because the debugger still injected a legacy
  `<UserObject>` wrapper, overwriting metadata before export.
- Added defensive conversions in the debugger so any existing metadata envelope
  is promoted to canonical form before overrides mutate it.

## Testing
- `bun run test:log:linux`
- `bun run debug:all:log:linux`
- `CI=1 bun run check`

