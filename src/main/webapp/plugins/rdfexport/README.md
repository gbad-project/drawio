# rdfexport

To install dependencies:

```bash
bun install
```

To build dist:

```bash
bun run build
```

## Pyodide assets

The bundled plugin expects the Pyodide runtime to be hosted locally at
`plugins/rdfexport/pyodide/`. Download the distribution before serving the
plugin:

```bash
./scripts/download_pyodide_assets.sh
```

If the assets are missing at runtime the plugin will fall back to the public
Pyodide CDN (`https://cdn.pyodide.org/v0.28.3/full/`).

This project was created using `bun init` in bun v1.2.21. [Bun](https://bun.com) is a fast all-in-one JavaScript runtime.
