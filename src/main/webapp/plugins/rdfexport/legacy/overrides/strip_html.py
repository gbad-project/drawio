from __future__ import annotations

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="xml", role="data")
class NodeHTMLParser(HTMLParser):
    """HTML parser mirroring the legacy behaviour while tracking raw markup."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._raw_html = ""

    def handle_starttag(self, tag: str, _: list[tuple[str, str | None]]) -> None:
        if tag in ["div", "blockquote", "p", "br"]:
            self._chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ["div", "blockquote", "p"]:
            self._chunks.append(" ")

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def feed(self, data: str) -> None:  # type: ignore[override]
        from html import unescape

        self._raw_html = unescape(data)
        super().feed(data)

    def _prettify_linebreaks(self) -> Generator[Paragraph, None, None]:
        previous_was_empty = False
        paragraph_already_handled = False
        current = ""
        for chunk in self._chunks:
            if not chunk:
                if current:
                    yield current
                current = ""
                if previous_was_empty and not paragraph_already_handled:
                    yield "\n\n"
                    paragraph_already_handled = True
                else:
                    previous_was_empty = True
                continue
            current += chunk
            previous_was_empty = False
            paragraph_already_handled = False
        if current:
            yield current

    def content(self) -> str:
        return "".join(self._prettify_linebreaks()).strip()

    def raw_html(self) -> str:
        return self._raw_html

    def clear(self) -> None:
        self._chunks = []
        self._raw_html = ""
        self.reset()
