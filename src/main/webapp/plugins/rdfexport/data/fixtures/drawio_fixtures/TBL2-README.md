# Fixture: TBL2

## Contents

- Input: [TBL2.drawio](./TBL2.drawio)
- Output: ⚠️ Unavailable. See below.

## Preparation process

**[paveljee](https://github.com/paveljee)** commented on Dec 9, 2025

> Same as [TBL.drawio](./TBL.drawio) but manually manipulated in Draw\.io GUI such that:
> 
> - `Literal definitions` in `Parser Settings...` replaced with:
>     - Attribute key: `rdf_entity`
>     - Attribute value: `literal`
> - Style of "World Wide Web" node changed to `rounded=1`
> - "Tim Berners-Lee" node manipulated such that via `Edit -> Edit Data...`, a Property Name `rdf_entity` was added, with its value set to `literal`
> 
> **Expected outcomes:**
> 
> - Once Property Name `rdf_entity` on "Tim Berners-Lee" was set to another value, e.g. "individual", this would serialize all right, with "World Wide Web" node being minted an **individual** (because `rounded=1` is no longer a definition of a literal)
> - But once `rdf_entity` would be reverted to `literal`, export would fail due to error: `draw_io_parser.internal_data_core.ArrowWithoutIndividualAsSourceException: Arrow 'created' (ZojVrLWr7QVSXUzW-Ien-3) has a literal ('Tim Berners-Lee') as source.`
>
> **Observed outcomes:**
>
> As expected. See debug scenario `uv run python -m aicode.integration.debug.src --scenario tbl2` to confirm that it raises the expected error. `literal_definitions` can be conveniently manipulated using debug `tbl2.yml` file.
