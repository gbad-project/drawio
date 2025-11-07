# Parser Overrides

Place Python modules in this directory to override or extend parts of the legacy
DrawIO parser during meta builder generation. Functions or classes decorated
with `@override` from `meta_builder.drawio_meta_builder` will replace the
corresponding implementation defined in the original parser or will be attached
to the generated pipeline namespace when no original mapping exists.
