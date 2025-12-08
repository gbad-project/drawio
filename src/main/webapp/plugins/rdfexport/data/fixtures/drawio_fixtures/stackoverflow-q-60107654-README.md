# Fixture: stackoverflow-q-60107654

## Contents

- Input: [stackoverflow-q-60107654.drawio](./stackoverflow-q-60107654.drawio)
- Output: ⚠️ Unavailable. See **Errors** below.

## Preparation process

**[paveljee](https://github.com/paveljee)** commented on Dec 8, 2025

> This was inspired by an original question on Stack Overflow <<https://stackoverflow.com/q/60107654>> licensed under CC BY-SA 4.0. I saved HTML and PDF versions of it as of 2025-12-08 03:32 AM UTC-5:
> 
> - [stackoverflow-q-60107654-source.html](./stackoverflow-q-60107654-source.html)
> - [stackoverflow-q-60107654-source.pdf](./stackoverflow-q-60107654-source.pdf)
> 
> Also, I archived the image <<https://i.sstatic.net/jBvaA.png>> referenced in the original question:
> 
> - [stackoverflow-q-60107654-source.png](./stackoverflow-q-60107654-source.png)
> 
> The fixture itself was generated using a reference image and a top-tier (at the time) LLM. Current path to chat with generation: `src/main/webapp/plugins/rdfexport/aicode/docs/chats/2025-12-07_claude/`
> 
> The sample DrawIO XML file I used in the prompt is [TBL.drawio](https://github.com/gbad-project/drawio/blob/f61de50e02563220e77dc99ac4e27024eaaa4300/src/main/webapp/plugins/rdfexport/data/fixtures/drawio_fixtures/TBL.drawio)
> 
> **Errors:**
> 
> At first attempt, gpt-4.1-mini (if I recall correctly, via chatgpt.com interface) produced a diagram that would give an error when trying to open in Draw\.io GUI.
> 
> Claude Sonnet 4.5 produced a diagram that would load with Draw.\.io GUI and looked like a relatively faithful diagram, except that it reversed the source and target of `vcard:FN` arrow, which I then manually fixed.
> 
> However, the DrawRDF parser would not parse this when called usign `GBAD: Export as RDF/Turtle (.ttl)...` button due to:
> 
> ```
> arrow = self._resolve_arrow(cell)
> File "/app/src/draw_io_parser.py", line 660, in _resolve_arrow
> raise ArrowWithoutIndividualAsSourceException(
> f"Arrow '{arrow_label}' ({arrow_id}) has a literal ('{self._value_of(self._cell_with_id(source_id))}') as source."
> )
> draw_io_parser.internal_data_core.ArrowWithoutIndividualAsSourceException: Arrow 'vcard:Given' (edge-middle-john) has a literal ('') as source.
> ```
> 
> This was obviously because the source of `vcard:Given` was an empty ellipse. This made me consider that an `EMPTY_CELL` classification may be allowed to mint a blank node unless `mint_from_literals is False`.
