# Fixture: General_Authority_bleep_mock

## Contents

- Input: [General_Authority_bleep_mock.drawio](General_Authority_bleep_mock.drawio)
- Output: [General_Authority_bleep_mock.ttl](General_Authority_bleep_mock.ttl)

Note: Output Turtle file successfully validates (e.g., with `GBAD: Validate and Serialize` button from GBAD VS Code Extension [version 0.0.2-prerelease.2](https://github.com/gbad-project/records_in_contexts_draw_io_parser/blob/cd4f0f692cec8a2096b1b596161b2f53c50e9091/vs_code_extension/gbad-vsce-0.0.2-prerelease.2.vsix)).

## Preparation process

Please refer to the [main plugin readme](../../../../../../data/README.md) for launch/installation instructions.

**[pvzhelnov](https://github.com/pvzhelnov)** commented on Oct 15, 2025

> I produced this fixture in the web browser interface by executing these steps:
>
> - Using `Open Existing Diagram` button to load an existing fixture: [General Authority to RiC-O Model_2025-06-25_PZ.drawio](General%20Authority%20to%20RiC-O%20Model_2025-06-25_PZ.drawio)
> - I _manually_ changed node and arrow values to different kinds of weird values.
> - After the changes, I tried to dump using `Menu > File > Export as > GBAD: Export as RDF/Turtle (.ttl)`
> - I randomly noticed that 1 of 3 `bleep:` nodes I created (`AuthorityRecord2`) would not appear in the Turtle file while silently not producing any error. Visually it looks just like the other one, `AuthorityRecord1`, but the behaviour is apparently different.
> - Notably, `python -m debug --scenario general-authority-bleep-mock` command passes both the pipeline and plugin generations.
