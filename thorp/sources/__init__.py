"""Text sources. load_text(book_id) returns the stripped text of any registered book."""

from __future__ import annotations

from thorp import manifest, paths


def load_text(book_id: str) -> str:
    book = manifest.get(book_id)
    source = book.source if book else "gutenberg"
    if source == "gutenberg":
        from thorp.sources import gutenberg

        return gutenberg.book_text(book_id)
    return (paths.texts_dir(source) / f"{book_id}.txt").read_text(encoding="utf-8")
