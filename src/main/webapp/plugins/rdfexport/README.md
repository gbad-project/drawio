# DrawRDF

A draw\.io plugin that adds an option to export diagrams to RDF graphs.

Supports export to [RDF Mapping Language](https://rml.io/docs/rml/introduction/) graphs.

Example usage scenario: [AA37-with-metadata-severely-mocked fixture](data/fixtures/drawio_fixtures/AA37-with-metadata-severely-mocked-README.md)

## Environment

draw\.io version [24.7.5 release](https://github.com/jgraph/drawio/releases/tag/v24.7.5) (Jul 25, 2024)

rdfexport extension unreleased version [29afe9e1](https://github.com/gbad-project/drawio/tree/29afe9e1a7cfd647a63d2a4982523b5da7c871d2/src/main/webapp/plugins/rdfexport) (Dec 17, 2025)

> [!TIP]
> 🎉 Available online! Public and free, no registration or credit card required. Hosted complimentary by GitHub Pages.
> Permalink: <https://gbad-project.github.io/drawio/src/main/webapp/?p=rdf>

The online version runs fully in the client web browser and does not require any installation except that JavaScript should be turned on (on by default in modern browsers like Chrome).

The entire rdfexport extension is condensed to a single file: [rdfexport.js](../rdfexport.js). If you would like to learn more about how it was built and/or modify it using modern tooling, refer to the section below.

**For developers:**

rdfexport extension itself is open source: [Apache-2.0 license](https://github.com/gbad-project/drawio/blob/gbad/LICENSE).
drawio parser fork embedded inside also is (see [discussion here](https://github.com/williamsonrichard/records_in_contexts_draw_io_parser/issues/4#issuecomment-2781104389)).
Pyodide is under [Mozilla Public License 2.0](https://github.com/pyodide/pyodide/blob/main/LICENSE).
RDFLib is under [BSD 3-Clause "New" or "Revised" License](https://github.com/RDFLib/rdflib/blob/main/LICENSE).

Installation instructions (Linux or macOS):

- Install Node via Volta on your system:
  - Bash (Linux default): `curl https://get.volta.sh | bash && source ~/.bashrc && volta install`
  - Zsh (macOS default): `curl https://get.volta.sh | bash && source ~/.zshrc && volta install`
- Install Bun on your system:
  - Bash (Linux default): `curl -fsSL https://bun.sh/install | bash && source ~/.bashrc`
  - Zsh (macOS default): `curl -fsSL https://bun.sh/install | bash && source ~/.zshrc`
- Navigate to rdfexport plugin dir: `cd src/main/webapp/plugins/rdfexport`
- Review demo test log (optional, shows how a successful test run looks like): `bun run test:log:show`
- Run setup scripts (explore what these commands do in [package.json](https://github.com/gbad-project/drawio/blob/gbad/src/main/webapp/plugins/rdfexport/package.json))
  - `bun install`
  - `bun run setup` (installs Python dependencies via uv and procures Pyodide runtime with an rdflib wheel)
    - If this command gives you an error because Python is not installed or not found, try installing Python via uv: `uv python install`
    - If the Pyodide assets are missing at runtime, the plugin should fall back to the public Pyodide CDN (`https://cdn.jsdelivr.net/pyodide/v0.29.0/full/`), although this fallback is untested
  - `bun run test` (optional, test coverage for both the Python and TypeScript codebase using diverse ground truth fixtures and artifacts obtained from a [fork](https://github.com/gbad-project/drawio/blob/cf8f84bb84ff83843b6726ac96aff3a2055f4275/src/main/webapp/plugins/rdfexport/legacy/draw_io_parser.py) of the [original](https://github.com/williamsonrichard/records_in_contexts_draw_io_parser) Records in Contexts parser for draw\.io)
  - `bun run build` (optional, rebuilds the extension bundle [rdfexport.js](https://github.com/gbad-project/drawio/blob/gbad/src/main/webapp/plugins/rdfexport.js))
  - `bun run serve`
- Open in your web browser (e.g., Chrome): <http://[::]:8000/src/main/webapp/?p=rdf>

## Repository structure

Most of the code for rdfexport extension was systematically developed using an asynchronous AI coding agent ([OpenAI Codex](https://openai.com/index/introducing-codex/), with a little bit of [Google Jules](https://blog.google/technology/google-labs/jules/)).

AI coding agents are known to produce noisy code. Although the best effort was made to polish it – both via context engineering and post hoc code review, to reflect the generational difference from handwritten code, most of the agentic code is placed under `aicode/` directory in hopes that clear separation is helpful for future maintainers. Its nested tree structure mirrors that of the root plugin dir to minimize friction when importing and switching between human and AI code. The code outside of `aicode/` has primarily been written manually – albeit usually still with code completion, but at the function or statement/expression rather than module or class level. Upon sufficient refactoring, some code from `aicode/` might sometimes become a first-class repo citizen and as such emigrate outside of the reserved dir.

You may review the development process using the repo [commit history](https://github.com/gbad-project/drawio/commits/gbad/) and [AICODE reports](https://github.com/gbad-project/drawio/tree/gbad/docs/aicode). Kudoz to [@abdullin](https://github.com/abdullin) for the AICODE mnemonics.

This project was created using `bun init` in bun v1.2.21. [Bun](https://bun.com) is a fast all-in-one JavaScript runtime.
