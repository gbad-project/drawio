# Work Summary

- Investigated Pyodide parser flag handling and confirmed `_build_graph_from_raw_xml` only honoured legacy `*_disable` keys.
- Updated the override to reconcile include/disable flags so TypeScript-provided booleans are respected without breaking CLI callers.
- Added pytest coverage that inspects emitted graphs and serialisation configs to assert strict-mode propagation and label toggles.
- Extended Bun tests to exercise the includeLabel switch end-to-end through the plugin and Pyodide runtime.
- Refreshed the changelog with the regression fix and ensured tooling setup plus command logs were captured per guidelines.

# Testing

- `bun run check`
- `bun run test:all:log:show`
- `bun run test:all:log:linux`
