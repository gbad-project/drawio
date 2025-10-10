# Fixture: AA37-with-metadata-severely-mocked

## 1. Contents

- Input: [AA37-with-metadata-severely-mocked.drawio](AA37-with-metadata-severely-mocked.drawio)
- Output: [AA37-with-metadata-severely-mocked.ttl](AA37-with-metadata-severely-mocked.ttl)

Note: Output Turtle file successfully validates (e.g., with `GBAD: Validate and Serialize` button from GBAD VS Code Extension [version 0.0.2-prerelease.2](https://github.com/gbad-project/records_in_contexts_draw_io_parser/blob/cd4f0f692cec8a2096b1b596161b2f53c50e9091/vs_code_extension/gbad-vsce-0.0.2-prerelease.2.vsix)) once the prefix IRI on Line 7 is fixed.

## 2. Preparation process

## 2.1. Environment

draw\.io version [24.7.5 release](https://github.com/jgraph/drawio/releases/tag/v24.7.5) (Jul 25, 2024)

rdfexport extension unreleased version [26d193c](https://github.com/gbad-project/drawio/commit/26d193ca4937dfe650079dab0e33a3c2801093dc) (Oct 10, 2025)

Available online! <https://gbad-project.github.io/drawio/src/main/webapp/?p=rdf>

The online version runs fully in the client web browser and does not require any installation except that JavaScript should be turned on (on by default in modern browsers like Chrome).

**For developers:**

Installation instructions (Linux or macOS):

- Install Node via Volta on your system:
  - Bash (Linux default): `curl https://get.volta.sh | bash && source ~/.bashrc && volta install`
  - Zsh (macOS default): `curl https://get.volta.sh | bash && source ~/.zshrc && volta install`
- Install Bun on your system:
  - Bash (Linux default): `curl -fsSL https://bun.sh/install | bash && source ~/.bashrc`
  - Zsh (macOS default): `curl -fsSL https://bun.sh/install | bash && source ~/.zshrc`
- Navigate to rdfexport plugin dir: `cd src/main/webapp/plugins/rdfexport`
- Review demo test log (optional, shows how a successful test run looks like): `bun run test:log:show`
- Run setup scripts (explore what these commands do in [package.json](../../package.json))
  - `bun install`
  - `bun run setup` (installs Python via uv and procures Pyodide runtime with an rdflib wheel)
  - `bun run test` (optional, test coverage for both the Python and TypeScript codebase using diverse ground truth fixtures and artifacts obtained from a [fork](https://github.com/gbad-project/drawio/blob/cf8f84bb84ff83843b6726ac96aff3a2055f4275/src/main/webapp/plugins/rdfexport/legacy/draw_io_parser.py) of the [original](https://github.com/williamsonrichard/records_in_contexts_draw_io_parser) Records in Contexts parser for draw\.io)
  - `bun run build` (optional, rebuilds the extension bundle [rdfexport.js](../../../rdfexport.js))
  - `bun run serve`
- Open in your web browser (e.g., Chrome): <http://[::]:8000/src/main/webapp/?p=rdf>

### 2.2. Input & Output

Pavel: I produced this fixture in the web browser interface by executing these steps:

- Using `Open Existing Diagram` button to load an existing fixture: [AA37 Department of Health-with-metadata.drawio](AA37%20Department%20of%20Health-with-metadata.drawio)
- I *manually* changed node and arrow values to different kinds of weird values.
- After the changes, I tried to dump using `Menu > File > Export as > GBAD: Export as RDF/Turtle (.ttl)`
- The user interface helpfully showed me the error if there was one, with a trace back to the original error coming from within the Python drawio parser code, so I fixed values in nodes and arrows according to what the error said and retried dumping to Turtle until this was successful.
