from legacy.draw_io_parser import pipeline
from meta_builder.drawio_meta_builder import override


@override(type="control", role="control", phase="core")
def individual_blocks_new():
    pipeline.core.internal.control.individual_blocks()
    print("hello there")
