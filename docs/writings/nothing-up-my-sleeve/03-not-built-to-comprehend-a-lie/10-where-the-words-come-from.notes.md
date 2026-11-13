# Notes on: Where the Words Come From

Sidecar to `10-where-the-words-come-from.md`: what belongs beside the chapter without being in it. Sections are keyed to the
chapter's headings by anchor (`@` and the heading's slug); `@chapter` is the whole. Each anchor may carry three
blocks, any of them absent: **Quentin** (his page, or a remark on the section), **Pictures** (the `peek:` ids the
section uses and their files in `../pictures/`; the caption lives in `essayPeeks.ts` until the reader reads it from here),
**References** (what the section rests on). The contract is in `docs/writings/README.md`.

## @chapter

### Quentin

- First draft, from the Kindle note at loc 471 (5 November 2026), on Common Crawl: this is the biggest attack
  vector there is. Fuck with these guys' backups, or manipulate the content the crawl takes, and the models are
  fucked. Keep it secret, or publish a mitigation? The chapter is the mitigation: a kernel that never read the
  web, raised on a manifest of public works, so that a leak has a row.
- From loc 513: as you add more data you get shittier models, if, as he does, you think the crowd is dumb as
  shit. The chapter's arithmetic agrees with him for a different reason, which is that four passes over a
  small shelf chosen by the world beats one pass over a crawl chosen by nobody.
- From loc 535: all he wants the training to do is predict the next token; pretraining should be the smallest
  amount of training and post-training the most; ontology of language first, then curated sources on those
  concepts; now we have a pure form of the trick, now we can imbue nature. The ladder section is that note
  turned into an instrument, and the post-training pile is the shelf he is asking for, named and empty.
- On the people introduced here, to be written: Hart; Jack Rae and the PG-19 team; Wilson Taylor; Shannon
  and his wife with the pencil; Flesch, Dale and Chall, Gunning, McLaughlin, Kincaid, the old mates with
  rulers; Muennighoff and the four passes; Hoffmann and Chinchilla; Eldan and Li; Lalley and Weyl; Buterin,
  Hitzig and Gitcoin; Ostrom; Michels, back again.

### References

- The Kindle notes of 5 November 2026 at loc 471, 476, 513 and 535, and of 6 November at loc 59, 74, 79 and
  92, in `../kindle-notes-2026-11-05.md` and `../kindle-notes-2026-11-06.md`.
- The decisions this chapter lands or carries: D14 (the corpus is a register), D17 (the two rules), D23 (the
  rule binds books only), D25 (the weight), D26 (the commons as a kind), D31 (who chooses, open), D33 and
  D35 (the hole cards), D41 (three piles) and D42 (the ladder), in `../decisions.md`.
- Charles Darwin, *Journal of Researches into the Natural History and Geology of the Countries Visited
  during the Voyage of H.M.S. Beagle*, 1839; second edition 1845; Darwin died 1882. The opening row's token
  count and the edition Gutenberg's clean text follows are both to verify.

## @the-pool

### References

- Jack Rae et al., "Compressive Transformers for Long-Range Sequence Modelling", DeepMind, 2019: the PG-19
  dataset, Gutenberg books published before 1919, about 28,752 books [verify the count and the token figure
  against the paper's table].
- Project Gutenberg, Michael Hart, 1971; the Project Gutenberg Literary Archive Foundation's trademark
  licence, which attaches to texts distributed with the header [verify the current terms and whether a
  stripped text is free of them].
- Standard Ebooks, Alex Cabal, 2015; its public-domain dedication for its own additions [verify].
- HathiTrust, 2008; the HathiTrust Research Center's extracted-features and dataset terms [verify]; the
  share of full-view volumes [verify].
- Trove, National Library of Australia, 2009; the digitised newspapers from 1803; the API terms [verify].
- Chronicling America, Library of Congress and the National Endowment for the Humanities, 1770 to 1963.
- Hansard from 1803 (Cobbett's *Parliamentary Debates*) and the Australian Hansard from 1901; the law reports
  through AustLII and its siblings; Crown copyright's open licences [verify per jurisdiction].
- Aozora Bunko, 1997; the Chinese Text Project (Donald Sturgeon, 2006); al-Maktaba al-Shamela; Gallica (the
  Bibliothèque nationale de France, 1997); the Deutsches Textarchiv (Berlin-Brandenburg Academy); Lib.ru
  (Maxim Moshkov, 1994); GRETIL (Göttingen); Wikisource, 2003. Each archive's terms are to verify before any
  text from it is published in the manifest.
- The Index Translationum (1932; UNESCO from 1946) and its export; Open Library's editions by language; the
  Internet Archive, Brewster Kahle, 1996.

## @the-arithmetic

### References

- Niklas Muennighoff et al., "Scaling Data-Constrained Language Models", 2023: up to about four epochs of
  repeated data cost little against unique data [verify the exact figure the paper gives].
- Jordan Hoffmann et al., "Training Compute-Optimal Large Language Models" (Chinchilla), DeepMind, 2022:
  about twenty tokens per parameter.
- The corpus arithmetic: 12,500 books at 120,000 tokens is 1.5 billion unique tokens; four passes is 6
  billion; at twenty tokens a parameter, 300 million parameters (chapter 8).

## @cleaning

### References

- The standard cleaning literature for Gutenberg-derived corpora: header and footer stripping, language
  identification, MinHash deduplication across editions [cite the tools actually used when the pipeline
  runs]; OCR of long-s and Fraktur as the known failure cases.
- Darwin's revised editions (*Journal of Researches* 1845; *On the Origin of Species*, sixth edition 1872) as
  the exception that keeps the author's last text.

## @the-legal-row

### References

- The two rules as chapter 9 states them (D17), with the Australian term from the Copyright Act 1968 as
  amended in 2004; Arthur Waley (died 1966) as the worked exclusion.
- The exclusions file and the unresolved state are this chapter's additions to D14's row.

## @the-weight

### References

- Johan Heilbron, "Towards a Sociology of Translation: Book Translations as a Cultural World-System",
  *European Journal of Social Theory* 2(4), 1999.
- The Index Translationum's coverage by year, and the year its updates thinned [verify; around 2009].
- Open Library's editions-by-language data, through the Internet Archive's API.

## @three-piles-not-one

### References

- D41 (three piles), proposed 2026-11-06 from the conversation of that day; the pile is a column of the
  manifest.
- D9 and chapter 12 for the long-context material as pretraining or post-training; chapter 17 for the
  constitution as the one push; chapter 16 for the trait probes and the counter-selves kept in the corpus;
  D17 for the horizon test; D21 for the quantum rungs and the death years of Heisenberg (1976), Schrödinger
  (1961) and Dirac (1984) that remove the answer by rule.

## @a-ladder-of-difficulty

### References

- Wilson L. Taylor, "'Cloze Procedure': A New Tool for Measuring Readability", *Journalism Quarterly* 30,
  1953.
- Claude E. Shannon, "Prediction and Entropy of Printed English", *Bell System Technical Journal* 30, 1951;
  about one bit per letter, the range he reported being wider [verify, and verify who did the guessing].
- Rudolf Flesch, "A New Readability Yardstick", *Journal of Applied Psychology* 32, 1948; Edgar Dale and
  Jeanne Chall, "A Formula for Predicting Readability", *Educational Research Bulletin*, 1948; Robert
  Gunning, *The Technique of Clear Writing*, 1952; G. Harry McLaughlin, "SMOG Grading", *Journal of Reading*,
  1969; J. Peter Kincaid et al., "Derivation of New Readability Formulas for Navy Enlisted Personnel", 1975.
- Marcus Hutter, the Hutter Prize, 2006 onward, for compression as prediction.
- Ronen Eldan and Yuanzhi Li, "TinyStories: How Small Can Language Models Be and Still Speak Coherent
  English?", 2023; the stub's epigraph, now in the prose.
- Yoshua Bengio et al., "Curriculum Learning", ICML 2009, for the ordering the band serves; chapter 11 for
  the stages.
- D42 (the ladder), proposed 2026-11-06.

## @sorting-by-sample

### References

- The classifier's cost: 12,500 samples of 10,000 tokens, 125 million input tokens, at the prices of
  November 2026 [verify and date in the row; the chapter's "tens of dollars" and "a few hundred" are
  estimates].

## @filling-and-the-coverage-report

### References

- Chapter 9's coverage report, here given its columns: kind, language, self, band and interval, with the
  shortfall as a number.
- D43 (Seeds is chosen by hand), decided 2026-11-06: the first fill by a person, by kind, each pick a row
  with its reason; the weight for every fill after. Timnit Gebru et al., "Datasheets for Datasets", 2018;
  Emily Bender and Batya Friedman, "Data Statements for Natural Language Processing", 2018; Shayne Longpre
  et al., the Data Provenance Initiative, 2023, as the literature that describes a dataset and judges none.

## @the-human-read

### References

- D7 and D22 for Quentin's verdicts beside Justin's; chapter 23's ask for the job's place on the list.

## @the-manifest

### References

- D14 for the row; D32 for publication with the kernel; D33 for Seeds as the first fill's name.
- Roger Grosse et al., "Studying Large Language Model Generalization with Influence Functions", Anthropic,
  2023, for the method the closing paragraph promises to chapter 16: tracing a behaviour to the training
  rows that most moved it.

## @who-decides

### References

- D31, open.
- Steven P. Lalley and E. Glen Weyl, "Quadratic Voting", working paper 2012; "Quadratic Voting: How
  Mechanism Design Can Radicalize Democracy", *AEA Papers and Proceedings* 108, 2018. Eric Posner and Glen
  Weyl, *Radical Markets*, 2018.
- Vitalik Buterin, Zoë Hitzig and E. Glen Weyl, "A Flexible Design for Funding Public Goods" (Liberal
  Radicalism), 2018; Gitcoin Grants' quadratic funding rounds from 2019.
- Elinor Ostrom, *Governing the Commons*, 1990: the design principles, graduated sanctions among them.
- Robert Michels, *Political Parties*, 1911, for the guild; chapter 20 carries him.
- The Haudenosaunee seventh-generation principle, as chapter 14 borrows it.

## @what-this-does-to-truth

### References

- Chapter 7's register, and Harry Frankfurt's *On Bullshit* behind it; the manifest as the register of the
  past.
