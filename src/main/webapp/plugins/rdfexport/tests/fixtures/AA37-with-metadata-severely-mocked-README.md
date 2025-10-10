# Fixture: AA37-with-metadata-severely-mocked

## Contents

- Input: [AA37-with-metadata-severely-mocked.drawio](AA37-with-metadata-severely-mocked.drawio)
- Output: [AA37-with-metadata-severely-mocked.ttl](AA37-with-metadata-severely-mocked.ttl)

Note: Output Turtle file successfully validates (e.g., with `GBAD: Validate and Serialize` button from GBAD VS Code Extension [version 0.0.2-prerelease.2](https://github.com/gbad-project/records_in_contexts_draw_io_parser/blob/cd4f0f692cec8a2096b1b596161b2f53c50e9091/vs_code_extension/gbad-vsce-0.0.2-prerelease.2.vsix)) once the prefix IRI on Line 7 is fixed.

## Preparation process

Please refer to the [main plugin readme](../../README.md) for launch/installation instuctions.

Pavel: I produced this fixture in the web browser interface by executing these steps:

- Using `Open Existing Diagram` button to load an existing fixture: [AA37 Department of Health-with-metadata.drawio](AA37%20Department%20of%20Health-with-metadata.drawio)
- I *manually* changed node and arrow values to different kinds of weird values.
- After the changes, I tried to dump using `Menu > File > Export as > GBAD: Export as RDF/Turtle (.ttl)`
- The user interface helpfully showed me the error if there was one, with a trace back to the original error coming from within the Python drawio parser code, so I fixed values in nodes and arrows according to what the error said and retried dumping to Turtle until this was successful.