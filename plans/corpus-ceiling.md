# The corpus ceiling (measured 7 November 2026; nothing fetched)

## The question

How many English tokens can Thorp legally train on, counting Gutenberg and the sources beyond it?
`DECISIONS.md` ("Thorp against Qwen") expects "at most a few billion legal pre-1930 tokens", and
the ladder's plans are sized to that figure. Rival period models have trained on far more: GPT-1900
on about 11B unique pre-1900 tokens, TypewriterLM on 54B tokens of English before 1913.

## The rule applied

Thorp's S5 *period* policy (`thorp/vsm.py`): English text printed before 1930, with every person in
the authors field dead by 1955. That is Australia's public-domain line. Tokens are estimated as
bytes ÷ 3.6, the mean for fetched English Gutenberg text under Thorp's 16,384-piece tokeniser. OCR
text will differ somewhat. Counts quoted in another tokeniser's tokens are given as published,
with the tokeniser named.

## Gutenberg, counted from the local catalogue

`data/catalogue/pg_catalog.csv` has 79,712 rows. For English text:

| books | count |
| --- | ---: |
| every named person dated and dead by 1955 (legal) | 38,769 |
| at least one person with no dates (refused by the rule; many are legal) | 11,273 |
| someone died after 1955 | 8,599 |
| unsigned (Anonymous, Various, Unknown, or no author) | 3,473 |

Counted by `thorp.acquisition.persons` (`python -m thorp.acquisition ceiling`). It reads BCE dates,
"active 15th century" and death-only dates, which a plain `1812-1870` pattern misses. The 38,769
legal books hold about **3.9 to 5.3B tokens**. The low figure uses Common Pile's mean
Gutenberg document (20.1 GB over 55,454 books, about 362 KB); the high figure uses the mean fetched
book in the Leonardo pilot (495 KB). About 3,200 of the books are periodicals. Fetched so far: 2,080
Gutenberg books, 0.94 GB. 1,929 of them pass the rule, about **0.22B tokens**, about 5% of the
legal Gutenberg. The catalogue has no
printing dates, so a book printed after 1930 by an author dead by 1955 passes the rule unchecked.

## The sources beyond Gutenberg

| source | what it holds | size as published | after Thorp's rule (estimate) | text quality | death dates checkable | licence or terms | access |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| **Common Pile `pre_1929_books`** (HathiTrust books printed in the US before 1929) | 137,127 books raw; 124,898 after filtering | 73.8 GB raw; 46.3 GB filtered (about 12.9B tokens) | 8–11B | OCR, with Common Pile's unigram-likelihood filter for OCR errors | mostly: author strings carry life dates ("Beecher, Henry Ward, 1813-1887."), some are null | no licence on the card; public domain in the US by printing date | open Hugging Face download (16.6 GB of files, filtered) |
| **Common Pile `library_of_congress`** (LoC Selected Digitized Books) | 135,500 docs raw; 129,052 filtered; "over 130,000 English-language books" | 47.8 GB raw; 35.6 GB filtered (about 9.9B tokens) | 3–7B (overlap with the pre-1929 set unknown) | OCR, filtered as above | poorly: sample authors have no dates ("Abbott, Jacob"); needs a name-authority lookup (LoC names, VIAF or Wikidata) | CC-BY-4.0 on the compilation, per-record "Public Domain", "not a guarantee for individual documents" | open Hugging Face download (18 GB of files) |
| **British Library books** (`TheBritishLibrary/blbooks`) | 49,455 books, 65,227 volumes, c.1510–c.1900; English 10,039,463 pages | the 1800s set alone is 10.3 GB to download, about 30 GB uncompressed | 0.9–5B (TypewriterLM kept 915M tokens for 1700–1913; Living with Machines used about 5.1B for 1760–1900) | OCR, mixed; long s before 1800 (the archive source's repair already handles it) | printing year yes; author dates not confirmed | CC0 1.0 | open Hugging Face download (loading script) |
| **Institutional Books 1.0** (Harvard Library's Google scans) | 983,004 public-domain volumes, 386M pages, 254 languages, "published largely in the 19th and 20th centuries" | 242B `o200k_base` tokens across all languages; TypewriterLM drew 52,736M tokens of English 1700–1913 from it | 30–50B net (adding 1913–29, less the rule and the overlap with the HathiTrust-derived sets above) | OCR with two 0–100 scores per volume (`ocr_score_src`, `ocr_score_gen`) | printing date yes (`date1_src`, from MARC 008); author names merged in `author_src`, dates not a separate field | early-access terms: non-commercial only; commercial use "including AI model training" needs contact@institutional.org first; no redistribution; provisional | gated Hugging Face, after agreeing to the terms |
| HathiTrust full public-domain set | the largest holding (Extracted Features covers 13.7M volumes of all rights; the 2015 release had 4.8M public-domain volumes) | not counted | not counted | OCR | MARC records carry author dates | non-commercial research; Google-digitised volumes need the researcher's institution to hold a Google agreement | institutional; not open to Thorp as it stands |
| Internet Archive | "over one million" public-domain books in Texts (an undated figure) | not counted | item by item only | uneven OCR | creator field sometimes dated | IA asked for a 653,983-text Hugging Face set (US-PD-Books) to be deleted, saying its metadata is too unreliable to establish public-domain status | Thorp's fetcher allows one request every 2 s, so 650,000 items would take about a month; keep it for chosen editions (the precursors) |
| **AmericanStories** (Chronicling America newspapers) | about 20M scans, 1774–1963 | 65.6B tokens (the paper's count) | most of it is before 1930, perhaps 40–55B, if S5 admits unsigned work | layout-aware OCR, noisy | no: articles are mostly unsigned, so the rule doesn't apply as written | CC-BY 4.0 | open Hugging Face download |
| Trove (Australian newspapers, NLA) | "millions of pages" from 1803 | not found | not counted | OCR | unsigned | API open; commercial use needs permission; bulk full text may need an exemption agreement (a secondhand report; check the current terms) | API key and the GLAM Workbench harvester |

Aggregators (they overlap the sources above, so they are not added to the total):

- **GPT-1900's corpus** (`mhla/pre1900-corpus`): 2,074,160 rows, 56.4 GB, from "Institutional books
  (HathiTrust, Internet Archive, and other digitized book collections)", the British Library books
  and AmericanStories. About 11B unique tokens (22B over 2 epochs). Pre-1900 is held by a year
  column and an anachronism filter. The compilation is tagged MIT. No author field is listed, so
  Thorp's death rule cannot be checked from it.
- **TypewriterCorpus**: 53,986M tokens (its own 32,000-piece BPE). Institutional Books is 97.68% of
  it; then the British Library books 915M, Hansard 193M, the Royal Society 70M, the Old Bailey 39M
  and CLMET 31M. "Models and datasets are available at hf.co/typewriter-ai"; no dataset licence was
  found, and Institutional Books' no-redistribution term likely binds it.
- **Common Corpus** (Pleias): about 2T tokens. OpenCulture is 886B to 927B (public-domain books,
  newspapers, Wikisource), and English is about 867B. Dates are mixed and author metadata varies by
  source.

## The total

English, printed before 1930, every person dead by 1955, de-duplicated. These are estimates, with
the overlap between scans of the same book guessed rather than measured:

| what is admitted | tokens |
| --- | ---: |
| Gutenberg only (today's rule, as fetched) | 3.9–5.3B (0.22B of it fetched) |
| **Low: open book sources, no agreement needed** (Gutenberg, Common Pile pre-1929 and LoC, British Library) | **about 12–18B** |
| **High: the above plus Institutional Books 1.0** (under its terms) | **about 40–60B** |
| Newspapers, if S5 admits unsigned work (AmericanStories; Trove not counted) | a further 40B or more |

What this means for the ladder:

- **100m** (about 2B tokens at 20 a parameter): Gutenberg alone is enough. Only 0.26B is fetched.
- **350m** (about 6.4B): the open sources are enough.
- **2.7B** (about 54B): needs Institutional Books or newspapers. Data no longer limits anything
  below this rung.
- **The Origin test** (before 1858): the scanned sources carry printing years, so the cutoff can
  be checked against the printing rather than through the death-year stand-in. The British
  Library's 1760–1900 holdings and Institutional Books (concentrated 1800–1900) should take the
  pre-1858 shelf well past the 0.4B counted in `plans/leonardo-pilot.md`. Not counted here.

## Recommended first source

**Common Pile `pre_1929_books_filtered`.**

- It is an open download, English, dated by printing and already filtered for OCR errors.
- Its author strings carry life dates, so the death rule can be applied by the same kind of parser
  as the Gutenberg catalogue's Authors field.
- It holds about 13B tokens before the rule. The disk has 532 GB free.

Second, the British Library books: CC0, before 1900, and the biggest gain for the Origin test.
Before the 2.7B, write to contact@institutional.org about Institutional Books.

Before any of it is read:

- **The decks must be protected by text, not by id.** The Forgotten Tomes are old books newly
  transcribed on Gutenberg, and scans of the same books may sit in these sets under other names.
  Check every new source against every held-out deck by text overlap (shingles), not by Gutenberg
  id.
- **Remove duplicates across sources.** One book is often scanned by several libraries and also
  transcribed on Gutenberg.
- **Keep scanned books out of the spelling pool.** They go on discovery shelves first, as
  `DECISIONS.md` already rules for the Internet Archive.

## Proposed `DECISIONS.md` entry (for Justin to adopt; not yet added)

> ## The corpus ceiling, measured (7 November)
>
> - The expectation in "Thorp against Qwen" ("at most a few billion legal pre-1930 tokens") is
>   corrected. Gutenberg alone holds about 3.9 to 5.3B tokens under the legal rule: 38,769 English
>   books with every named person dated and dead by 1955, of which 0.22B tokens is fetched. The open
>   scanned-book sources (Common Pile's pre-1929 and Library of Congress books, the British
>   Library's books) take the reachable total to about 12 to 18B tokens with no agreement needed.
>   Institutional Books 1.0, under its non-commercial early-access terms, would take it to about 40
>   to 60B. Newspapers would add another 40B or more if S5 admits unsigned work.
> - Data no longer limits the ladder below the 2.7B rung, and limits the 2.7B only without
>   Institutional Books. Details, sources and the first source to add are in
>   `plans/corpus-ceiling.md`.

## Sources

- Institutional Books 1.0: [arXiv 2506.08300](https://arxiv.org/abs/2506.08300), [dataset card](https://huggingface.co/datasets/institutional/institutional-books-1.0)
- TypewriterLM: [arXiv 2606.02991](https://arxiv.org/abs/2606.02991), [hf.co/typewriter-ai](https://huggingface.co/typewriter-ai)
- GPT-1900: [model](https://huggingface.co/mhla/pre1900_d26_22btok_2epoch), [corpus](https://huggingface.co/datasets/mhla/pre1900-corpus)
- Common Pile v0.1: [arXiv 2506.05209](https://arxiv.org/abs/2506.05209), [pre_1929_books](https://huggingface.co/datasets/common-pile/pre_1929_books), [pre_1929_books_filtered](https://huggingface.co/datasets/common-pile/pre_1929_books_filtered), [library_of_congress](https://huggingface.co/datasets/common-pile/library_of_congress)
- British Library books: [blbooks](https://huggingface.co/datasets/TheBritishLibrary/blbooks/blob/99446b2656f7d6e947378e6fb2364943a50edc1c/README.md); Living with Machines: [Zenodo](https://zenodo.org/records/4782245)
- HathiTrust: [research datasets](https://hathitrust.org/datasets); [Extracted Features](https://old.tei-c.org/?p=1453)
- Internet Archive: [US-PD-Books card, with IA's deletion request](https://huggingface.co/datasets/storytracer/US-PD-Books/blob/main/README.md?code=true)
- AmericanStories: [paper](https://ar5iv.labs.arxiv.org/html/2308.12477), [dataset card](https://huggingface.co/datasets/dell-research-harvard/AmericanStories/blob/refs%2Fpr%2F1/README.md)
- Trove: [API](https://trove.nla.gov.au/about/create-something/using-the-api/what-is-the-trove-api), [GLAM Workbench harvester](https://glam-workbench.net/trove-harvester)
- Common Corpus: [arXiv 2506.01732](https://arxiv.org/pdf/2506.01732), [Hugging Face blog](https://huggingface.co/blog/Pclanglais/two-trillion-tokens-open)
