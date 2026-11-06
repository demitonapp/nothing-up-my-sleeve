from thorp.sources.gutenberg import norm, strip

HEAD = "The Project Gutenberg eBook of Test\r\n\r\n*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\r\n"
BODY = "Chapter 1\r\n\r\nIt was a dark night.\r\n"
TAIL = "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\r\n\r\nSection 1. General Terms of Use\r\n"


def test_strip_with_end_marker():
    assert strip(HEAD + BODY + TAIL) == "Chapter 1\n\nIt was a dark night.\n"


def test_strip_without_end_marker_drops_licence():
    raw = HEAD + BODY + "\r\nEnd of the Project Gutenberg EBook of Test\r\nlicence text\r\n"
    assert strip(raw) == "Chapter 1\n\nIt was a dark night.\n"


def test_strip_without_any_markers_keeps_text():
    assert strip(BODY) == "Chapter 1\n\nIt was a dark night.\n"


def test_norm():
    assert norm("Les Misérables!") == "les miserables"
    assert norm("西遊記") == "西遊記"
