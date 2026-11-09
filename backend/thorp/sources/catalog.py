"""The sources beyond Gutenberg, as S4 sees them (acquisition's intelligence): what each holds, what it
takes to get it, what Thorp's period rule leaves of it, and the wall where there is one.

The catalogue is data, not a promise. `status` says whether the pipeline may fetch a source now:

- **admitted**: an open source the acquisition gate has admitted (an entry in DECISIONS.md names it).
- **gated**: open only after an agreement or a token; the adapter exists, the fetch fails until the
  terms are met.
- **walled**: no lawful bulk full text reaches Thorp (a licence, an institution, or no full-text API).
  The wall says why, so a later reader does not fetch it by accident.
- **awaits S5**: the text is open but the policy question is Justin's (unsigned newspapers, whose
  authors cannot be checked against the death rule).

`adapter` names a bulk source in thorp/sources/bulk.py; `how` is the command that fetches a pilot.
Sizes and token counts are the estimates measured in ships/plans/corpus-ceiling.md, with the tokeniser
named there; they are estimates, not a count of what was fetched.
"""

from __future__ import annotations

SOURCES: list[dict] = [
    {
        "key": "gutenberg",
        "name": "Project Gutenberg",
        "holds": "transcribed books; the catalogue gives every person's life dates",
        "after_rule": "3.9–5.3B tokens",
        "licence": "public domain; Gutenberg's own licence text stripped",
        "access": "open; one request every 2 s",
        "status": "admitted",
        "kind": "api",
        "adapter": "gutenberg",
        "unsigned": False,
        "url": "https://www.gutenberg.org/",
        "how": "uv run thorp acquire lists/<list>.csv",
    },
    {
        "key": "archive",
        "name": "Internet Archive",
        "holds": "scans, item by item (the precursors); a collection can be harvested by query",
        "after_rule": "item by item",
        "licence": "per item; IA's metadata is not reliable enough for public-domain status in bulk",
        "access": "open; one request every 2 s (a 650,000-item set would take about a month)",
        "status": "admitted",
        "kind": "api",
        "adapter": "archive",
        "unsigned": False,
        "url": "https://archive.org/",
        "how": "uv run thorp gather archive --collection 'americana AND year:[1850 TO 1929] AND language:eng' --limit 50",
    },
    {
        "key": "common-pile-pre-1929",
        "name": "Common Pile: pre-1929 books",
        "holds": "124,898 HathiTrust books printed in the US before 1929, OCR-filtered; authors with life dates",
        "after_rule": "8–11B tokens",
        "licence": "public domain in the US by printing date; no licence on the card",
        "access": "open Hugging Face download (16.6 GB, 27 gzip shards)",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "common-pile-pre-1929",
        "unsigned": False,
        "tokens": [8e9, 11e9],
        "books": 124898,
        "url": "https://huggingface.co/datasets/common-pile/pre_1929_books_filtered",
        "how": "uv run thorp gather common-pile-pre-1929 --limit 500",
    },
    {
        "key": "common-pile-loc",
        "name": "Common Pile: Library of Congress books",
        "holds": "129,052 English books from the LoC's Selected Digitized Books, OCR-filtered; most authors undated",
        "after_rule": "3–7B tokens",
        "licence": "CC-BY-4.0 on the compilation; per-record public domain",
        "access": "open Hugging Face download (18 GB, 50 gzip shards)",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "common-pile-loc",
        "unsigned": False,
        "tokens": [3e9, 7e9],
        "books": 129052,
        "url": "https://huggingface.co/datasets/common-pile/library_of_congress",
        "how": "uv run thorp gather common-pile-loc --limit 500",
    },
    {
        "key": "blbooks",
        "name": "British Library books",
        "holds": "49,455 books (65,227 volumes), c.1510–1900; 10M English pages, grouped into volumes",
        "after_rule": "0.9–5B tokens",
        "licence": "CC0 1.0",
        "access": "open Hugging Face download (parquet, 13.7 GB)",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "blbooks",
        "unsigned": False,
        "tokens": [0.9e9, 5e9],
        "books": 49455,
        "url": "https://huggingface.co/datasets/TheBritishLibrary/blbooks",
        "how": "uv run thorp gather blbooks --limit 200",
    },
    {
        "key": "incunabula",
        "name": "Incunabula (pre-1501 printing)",
        "holds": "315 books printed 1450–1500 in the Boston Public Library's incunabula set; 180 pass the strict "
                 "filter (152 Latin, 12 German, 8 Italian, 3 Greek, 2 Hebrew, 1 French, 1 English)",
        "after_rule": "a discovery shelf, not a training recipe (152 of 180 are Latin)",
        "licence": "public-domain mark on 307 of 315; ProQuest's Early European Books and EEBO sets excluded",
        "access": "open Internet Archive collection bplscinc; OCR, with the archive's noisy dates filtered",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "incunabula",
        "unsigned": True,
        "books": 315,
        "url": "https://archive.org/details/bplscinc",
        "how": "uv run thorp gather incunabula --limit 100 --set incunabula --allow-unsigned",
    },
    {
        "key": "perseus-latin",
        "name": "Perseus Latin",
        "holds": "364 TEI editions of Latin texts from the Perseus Digital Library (canonical-latinLit), "
                 "with the ancient author, the editor and the edition's imprint",
        "after_rule": "a classics discovery shelf, not an English recipe",
        "licence": "CC BY-SA 4.0 (Perseus Digital Library)",
        "access": "open GitHub archive (48 MB zip); one download, then local XML",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "perseus-latin",
        "unsigned": False,
        "books": 364,
        "url": "https://github.com/PerseusDL/canonical-latinLit",
        "how": "uv run thorp gather perseus-latin --set classics",
    },
    {
        "key": "perseus-greek",
        "name": "Perseus Greek",
        "holds": "814 TEI editions of Ancient Greek texts from the Perseus Digital Library (canonical-greekLit)",
        "after_rule": "a classics discovery shelf, not an English recipe",
        "licence": "CC BY-SA 4.0 (Perseus Digital Library)",
        "access": "open GitHub archive (75 MB zip); one download, then local XML",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "perseus-greek",
        "unsigned": False,
        "books": 814,
        "url": "https://github.com/PerseusDL/canonical-greekLit",
        "how": "uv run thorp gather perseus-greek --set classics",
    },
    {
        "key": "etcsl",
        "name": "ETCSL (Sumerian)",
        "holds": "243 Sumerian literary compositions with transliteration and English translation, "
                 "from the Electronic Text Corpus of Sumerian Literature",
        "after_rule": "a cuneiform discovery shelf, not an English recipe",
        "licence": "free for research and teaching; cite ETCSL (Oxford)",
        "access": "open web, two requests a composition; the catalogue is one page",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "etcsl",
        "unsigned": True,
        "books": 243,
        "url": "https://etcsl.orinst.ox.ac.uk/",
        "how": "uv run thorp gather etcsl --set cuneiform --allow-unsigned",
    },
    {
        "key": "cdli",
        "name": "CDLI (cuneiform)",
        "holds": "135,254 cuneiform tablets from the Cuneiform Digital Library Initiative's ATF dump: "
                 "93k Sumerian, 20k Akkadian, 7.8k proto-cuneiform, grouped into language volumes",
        "after_rule": "a cuneiform discovery shelf, not an English recipe",
        "licence": "CDLI data, open for research (CC BY-SA where stated); cite CDLI",
        "access": "open GitHub LFS (83 MB ATF), then local; volumes of 2M characters",
        "status": "admitted",
        "kind": "bulk",
        "adapter": "cdli",
        "unsigned": True,
        "books": 135254,
        "url": "https://cdli.mpiwg-berlin.mpg.de/",
        "how": "uv run thorp gather cdli --set cuneiform --allow-unsigned --language sux --limit 5",
    },
    {
        "key": "institutional-books",
        "name": "Institutional Books 1.0 (Harvard)",
        "holds": "983,004 volumes, 242B tokens (all languages); printing dates, two OCR scores",
        "after_rule": "30–50B tokens",
        "licence": "early-access terms: non-commercial; AI training needs contact@institutional.org; no redistribution",
        "access": "gated Hugging Face; set HF_TOKEN after accepting the terms",
        "status": "gated",
        "kind": "bulk",
        "adapter": "institutional-books",
        "wall": "The terms are early-access: non-commercial only, AI training needs an email to "
        "contact@institutional.org first, no redistribution. Accept them on Hugging Face and set "
        "HF_TOKEN; the adapter then reads the parquet under those terms.",
        "unsigned": False,
        "tokens": [30e9, 50e9],
        "books": 983004,
        "url": "https://huggingface.co/datasets/institutional/institutional-books-1.0",
        "how": "uv run thorp gather institutional-books --limit 10 (after the agreement)",
    },
    {
        "key": "hathitrust",
        "name": "HathiTrust public-domain full text",
        "holds": "the largest holding; MARC records with author dates; 4.8M public-domain volumes in 2015",
        "after_rule": "not counted",
        "licence": "non-commercial research; Google scans need an institution's agreement",
        "access": "institutional; no open bulk full text",
        "status": "walled",
        "kind": "walled",
        "adapter": None,
        "unsigned": False,
        "url": "https://hathitrust.org/datasets",
        "wall": "Full text is behind a researcher agreement. The public Extracted Features are page-level token "
        "counts, not text, so they cannot train a model. Its scans reach Thorp through the Common Pile "
        "pre-1929 set, which is HathiTrust-derived.",
        "how": "use common-pile-pre-1929; write to contact@institutional.org for the gated Institutional set",
    },
    {
        "key": "google-books",
        "name": "Google Books",
        "holds": "the largest commercial scan corpus, mostly in copyright",
        "after_rule": "not counted",
        "licence": "per volume; the API gives metadata and snippets, not full text",
        "access": "no full-text API; the Books API is metadata and search snippets",
        "status": "walled",
        "kind": "walled",
        "adapter": None,
        "unsigned": False,
        "url": "https://developers.google.com/books",
        "wall": "There is no lawful bulk full-text download. Google's public-domain scans are what the Common "
        "Pile pre-1929 and Institutional Books sets redistribute under their own terms.",
        "how": "use common-pile-pre-1929 or institutional-books",
    },
    {
        "key": "eebo",
        "name": "EEBO and EEBO-TCP",
        "holds": "125,000+ English works printed 1475–1700, transcribed (TCP) from the Early English Books microfilm; "
                 "the English incunabula (Caxton, de Worde) are mostly here",
        "after_rule": "not counted; the earliest English printing",
        "licence": "EEBO images and TCP texts are licensed by ProQuest and the Text Creation Partnership; "
        "the texts are not open",
        "access": "institutional subscription; the TCP texts are in the Oxford Text Archive under licence",
        "status": "walled",
        "kind": "walled",
        "adapter": None,
        "unsigned": False,
        "url": "https://textcreationpartnership.org/tcp-texts/",
        "wall": "No open bulk text. A subscribing institution can export the TCP texts; if Justin has that "
        "access, drop the .txt files in data/texts/eebo/ with a metadata CSV and `thorp gather folder` "
        "puts them through the same gate.",
        "how": "thorp gather folder --path data/texts/eebo --metadata <csv> (only with licensed texts)",
    },
    {
        "key": "americanstories",
        "name": "AmericanStories (Chronicling America newspapers)",
        "holds": "about 20M newspaper pages, 1774–1963; 65.6B tokens, page-level OCR and article boxes",
        "after_rule": "40–55B if S5 admits unsigned work",
        "licence": "CC-BY 4.0",
        "access": "open Hugging Face download (yearly tar.gz; 1900 and 1920 are about 6 GB each)",
        "status": "awaits S5 (unsigned work)",
        "kind": "bulk",
        "adapter": "americanstories",
        "unsigned": True,
        "tokens": [40e9, 55e9],
        "books": 20000000,
        "url": "https://huggingface.co/datasets/dell-research-harvard/AmericanStories",
        "wall": "Articles are mostly unsigned, so the death rule cannot speak to them. The printing date is "
        "known, which is the proposed 'signed' rule's condition. The adapter exists; a gather needs "
        "`--allow-unsigned` until Justin adopts the rule.",
        "how": "uv run thorp gather americanstories --year 1770 --allow-unsigned",
    },
    {
        "key": "chronicling-america",
        "name": "Chronicling America (direct)",
        "holds": "the same newspaper pages as AmericanStories, by LCCN and issue",
        "after_rule": "not counted separately (it overlaps AmericanStories)",
        "licence": "public domain; the site is now served by loc.gov",
        "access": "the old OCR endpoints redirect to loc.gov behind Cloudflare; no polite bulk fetch",
        "status": "walled",
        "kind": "walled",
        "adapter": None,
        "unsigned": True,
        "url": "https://www.loc.gov/collections/chronicling-america/",
        "wall": "The direct OCR API now returns 403 behind Cloudflare. AmericanStories is the same text, "
        "already page- and article-segmented, and is the admitted route.",
        "how": "uv run thorp gather americanstories --year 1770 --allow-unsigned",
    },
    {
        "key": "trove",
        "name": "Trove (Australian newspapers)",
        "holds": "millions of pages from 1803",
        "after_rule": "not counted",
        "licence": "API open; commercial use needs permission; bulk text may need an exemption",
        "access": "API key and a harvester",
        "status": "awaits S5 (unsigned work) and the NLA's terms",
        "kind": "walled",
        "adapter": None,
        "unsigned": True,
        "url": "https://trove.nla.gov.au/about/create-something/using-the-api/what-is-the-trove-api",
        "wall": "Unsigned work and the NLA's bulk-text terms are both unresolved.",
        "how": "not yet",
    },
]


def get(key: str) -> dict:
    for s in SOURCES:
        if s["key"] == key:
            return s
    raise KeyError(f"no source {key!r}; the catalogue: {', '.join(s['key'] for s in SOURCES)}")


def admitted() -> list[dict]:
    return [s for s in SOURCES if s["status"] == "admitted"]


def fetchable() -> list[dict]:
    """The sources the pipeline can fetch now: admitted and with an adapter (or Gutenberg's list fetch)."""
    return [s for s in SOURCES if s["status"] == "admitted" and s.get("adapter")]


def walls() -> list[dict]:
    return [s for s in SOURCES if s["status"] in ("walled", "gated", "awaits S5 (unsigned work)")]
