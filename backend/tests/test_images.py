"""The Library's images (thorp/images.py): the rule a book's illustrations pass, the size read from a
header, and the photographs of the binding left out."""

import struct

from thorp import images


def _row(authors: str, lang: str = "en", kind: str = "Text") -> dict:
    return {"Text#": "1", "Type": kind, "Language": lang, "Title": "A Book", "Authors": authors}


def test_a_dead_illustrator_passes():
    row = _row("Cervantes Saavedra, Miguel de, 1547-1616; Doré, Gustave, 1832-1883 [Illustrator]")
    assert images.verdict(row) == []
    assert images._illustrators(row["Authors"]) == ["Doré, Gustave"]


def test_the_rule_refuses_late_undated_and_unillustrated():
    assert any("died in 1972" in w for w in images.verdict(_row("Masereel, Frans, 1889-1972 [Illustrator]")))
    assert any("no death year" in w for w in images.verdict(_row("Someone [Illustrator]")))
    assert "no credited illustrator" in images.verdict(_row("Dickens, Charles, 1812-1870"))
    assert "not English" in images.verdict(_row("Doré, Gustave, 1832-1883 [Illustrator]", lang="fr"))


def test_size_from_png_gif_and_jpeg_headers():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 640, 480) + b"\x00" * 8
    gif = b"GIF89a" + struct.pack("<HH", 300, 200) + b"\x00" * 8
    jpeg = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00" + b"\xff\xc0" + struct.pack(">HBHH", 11, 8, 911, 570) + b"\x00" * 8
    assert images.size_of(png) == (640, 480)
    assert images.size_of(gif) == (300, 200)
    assert images.size_of(jpeg) == (570, 911)
    assert images.size_of(b"not an image") is None


def test_binding_photographs_are_not_plates():
    for name in ("bookcover.jpg", "spine.jpg", "cover.jpg", "back.jpg", "i_cover-2.png"):
        assert not images.is_plate(f"https://x/images/{name}")
    for name in ("p003.jpg", "2-16-168.jpg", "background.jpg", "coverly.jpg"):
        assert images.is_plate(f"https://x/images/{name}")
