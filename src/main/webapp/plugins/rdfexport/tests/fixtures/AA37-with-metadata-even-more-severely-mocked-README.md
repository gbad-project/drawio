# Fixture: AA37-with-metadata-even-more-severely-mocked

## Contents

- Input: [AA37-with-metadata-even-more-severely-mocked.drawio](AA37-with-metadata-even-more-severely-mocked.drawio)
- Output: [AA37-with-metadata-even-more-severely-mocked.ttl](AA37-with-metadata-even-more-severely-mocked.ttl)

Note: Output Turtle file successfully validates (e.g., with `GBAD: Validate and Serialize` button from GBAD VS Code Extension [version 0.0.2-prerelease.2](https://github.com/gbad-project/records_in_contexts_draw_io_parser/blob/cd4f0f692cec8a2096b1b596161b2f53c50e9091/vs_code_extension/gbad-vsce-0.0.2-prerelease.2.vsix)).

## Preparation process

Please refer to the [main plugin readme](../../README.md) for launch/installation instructions.

**[pvzhelnov](https://github.com/pvzhelnov)** commented on Oct 20, 2025

> I produced this fixture in the web browser interface by executing these steps:
>
> - Using `Open Existing Diagram` button to load an existing fixture: [AA37-with-metadata-severely-mocked.drawio](AA37-with-metadata-severely-mocked.drawio)
> - Fixed the prefix `@prefix somprefix: <://hello>` on Line 7 that prevented the original `AA37-with-metadata-severely-mocked.ttl` from successfully validating.
> - I _manually_ changed node and arrow values to different kinds of weird values. This includes, among other things, various shapes (like `cylinder3` and stock general shapes like that of "Vertical Container" or "List pnnpni"), various attempts to subvert typed node parsing, and decorator nodes (i.e., nodes not intended to be captured in the ontology).
> - After the changes, I tried to dump using `Menu > File > Export as > GBAD: Export as RDF/Turtle (.ttl)`
> - The user interface helpfully showed me the error if there was one, with a trace back to the original error coming from within the Python drawio parser code, so I fixed values in nodes and arrows according to what the error said and retried dumping to Turtle until this was successful.
> - Attempts to connect literals as arrow sources have largely failed and have not been included.
> - Notably, `python -m debug --scenario aa37-with-metadata-even-more-severely-mocked` command fails both the pipeline and plugin generations.
>
> As a result of this experiment, it has become obvious that the parsing logic is currently obscure. For example, "lolabout" node gets parsed as an individual whereas "Some node" gets parsed as a literal (but intuitively, both should probably be parsed as literals because do not feature a type nor a IRI/curie). As another example of inconsistency, type CURIEs do not allow spaces whereas individual node values handle spaces predictably via metacharacter substitution. Finally, it is quite notable that nodes that do not have valid connections are silently ignored (whereas it would perhaps make sense to still include them in the export – for example, as `skos:note` comments; retaining HTML markup would also perhaps be desirable/should be customizable in these instances).
>
> All of this underscores the need to introduce a new, unified and streamlined entrypoint for mxCell classification. It is also important that the new implementation is not dependent on the [Records in Contexts shape library](https://github.com/williamsonrichard/records_in_contexts_draw_io_shape_library) anymore and imposes minimal limitations on how users design their diagrams to be able to use the plugin.
