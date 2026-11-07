"""Text sources. load_text(book_id, clean) returns the text of any registered book as the cleaning version
reads it (thorp/cleaning.py; "raw" is the source's own stripped text)."""

from __future__ import annotations

from thorp import manifest, paths


def load_text(book_id: str, clean: str = "raw") -> str:
    from thorp import cleaning

    return cleaning.clean(_source_text(book_id), clean)


def _source_text(book_id: str) -> str:
    book = manifest.get(book_id)
    source = book.source if book else "gutenberg"
    if source == "gutenberg":
        from thorp.sources import gutenberg

        return gutenberg.book_text(book_id)
    return (paths.texts_dir(source) / f"{book_id}.txt").read_text(
        encoding="utf-8"
    )  # any other source
