# The Leonardo pilot (plan, 6 November 2026; not started)

## The question

Leonardo's notebooks were almost unread until the 19th century, and much of what he worked out
was found again by other people who never saw them. So for each of his ideas there is a year the
world caught up. The pilot asks: **trained only on English written before a cutoff year, does the
model bet on Leonardo's version of an idea over the view of his own time, and does that preference
switch on at the cutoff where the idea was rediscovered?** It is a betting claim, not a claim that
the model discovers anything.

The pilot is free (this Mac) and exists to answer one thing before any money is spent: do the
matched pairs give a signal that is larger than seed-to-seed noise? If they do, the full test runs
at 100m (about $5 a run rented). If they do not, the pairs or the claims are fixed first.

## The shelves: one per cutoff, the same bytes

The catalogue has no first-publication dates, so a book counts as written before a cutoff when
**every person in its Authors field (translators and editors included) died by that year**. A
person without dates is refused, as now. This is strict: it loses books written before the cutoff
by people who died after it, but nothing it admits can be later than the cutoff.

Counted on the local catalogue (English, text, no periodicals), with tokens estimated from the
mean fetched English book (495 KB, 3.6 bytes a token):

| cutoff | books | tokens (estimate) |
| --- | ---: | ---: |
| 1700 | 513 | about 0.07B |
| 1800 | 1,152 | about 0.16B |
| 1858 | 2,919 | about 0.40B |
| 1900 | 10,926 | about 1.5B |
| 1930 | 24,209 | about 3.3B |

1700 is too thin to train on and is dropped. **Four shelves: 1800, 1858, 1900 and 1930, each cut
to the same bytes as the 1800 shelf** (about 0.16B tokens, about 1,150 books' worth), the later
shelves as seeded random draws from their own eligible books. Holding bytes equal is the harness's
own method: the only thing that differs between shelves is what had been written by then.

This count also corrects the Origin plan's estimate in `DECISIONS.md`: by the same rule, English
written before 1858 is about 0.4B tokens, not 1 to 1.5B.

## What is refused on every shelf

Anything that would let the model read Leonardo instead of rediscovering him:

- Every catalogue book with Leonardo in its Authors or Subjects: the Notebooks (4998, 4999, 5000),
  *A Treatise on Painting* (46915: Leonardo's own text, printed in Italian in 1651 and in English
  in 1721 and 1802, so it was readable before some cutoffs; refused anyway, because the test is
  independent rediscovery), *Thoughts on Art and Life* (29904), Gillette's *Pathfinder of
  Science* (54827), Brockwell (7785), Hind's *Drawings* (56844), Freud (34300), Merezhkovsky
  (47902), Hubbard's *Little Journeys* (artists).
- Vasari's *Lives* (all volumes; 21212 is on the content experiment's Renaissance shelf), whose
  life of Leonardo describes his work.
- The leak check runs on every shelf before training: "Leonardo", "Lionardo", "da Vinci",
  "Vinci", plus each claim's own giveaway phrases. Every hit is read by hand.

## The claims

Each claim has a year it was rediscovered, so a predicted cutoff where the preference should switch
on. The wrong ones are controls: a model that simply likes Leonardo's style would prefer those too.

| # | Leonardo's claim | the rival view of his day | rediscovered | should switch on by |
| --- | --- | --- | --- | --- |
| 1 | Shells on mountains are animals that lived where they lie, in sea that once covered the land | they were carried there by Noah's flood, or grew in the rock | Steno 1669, Hutton 1788, Lyell 1830 | 1800, firm by 1858 |
| 2 | The moon's faint glow is sunlight reflected from the earth | the moon has a light of its own, or is translucent | Maestlin and Kepler, about 1604 | 1800 |
| 3 | Friction grows with the load, not with the area in contact | a broader surface rubs harder | Amontons 1699, Coulomb 1785 | 1800 |
| 4 | No machine can move itself for ever | perpetual motion can be built | Paris Academy's refusal 1775; energy conservation 1840s | 1800, firm by 1858 |
| 5 | A wave's shape travels while the water stays in place | the water itself runs along with the wave | Weber brothers 1825 | 1858 |
| 6 | The sky is blue because the air between us and the dark beyond is lit | blue is the colour of the air, or of the heavens | Tyndall 1869, Rayleigh 1871 | 1900 |
| 7 | A tree's rings count its years, and their width records wet and dry years | rings are not annual, or tell nothing of weather | Douglass, 1900s | 1930 |
| 8 (control) | A man can fly by beating wings with his own muscles | he cannot; flight needs other power or fixed wings | wrong; fixed-wing powered flight 1903 | never; the rival should win by 1930 |
| 9 (control) | The moon's surface is water that shines like a mirror | the moon is dry and rough | wrong; Galileo's mountains 1610 | never |

This table is a first draft. Each claim's wording, and that the rival really was the view of
Leonardo's day, gets checked against the notebooks and a history of the subject before any pair is
written.

## The measurement

- **Matched pairs.** For each claim, 12 pairs of short passages in plain 19th-century prose: the
  same opening sentence, then Leonardo's version or the rival, matched in length and in rare words.
  Twelve paraphrases per claim so the result is about the idea, not one wording. Neither side
  quotes the notebooks.
- **Score.** For each pair, the rival's bits per byte minus Leonardo's on the differing
  continuation (bits per byte, because each shelf trains its own tokeniser). Positive means the
  model bets on Leonardo. A claim's score is the mean over its pairs.
- **Floors**, as the probes have them: the same pairs scored by the untrained model and by a
  unigram model of the same shelf, so a preference that is only word frequency is visible.
- **The notebooks as a hole card.** The bits per byte of each claim's own notebook passages on
  each shelf, as a second reading that uses Leonardo's words.
- **Signal rule, set before any run:** a claim shows a signal at a cutoff when its two-seed mean is
  more than twice the seed range from zero and from both floors. The pilot passes when at least
  three of claims 1 to 7 show a signal at some cutoff and neither control does.

The pairs live in `lists/leonardo-pairs.csv` (claim, pair, prompt, leonardo, rival), scored by a
new `pairs` evaluator. The 21m rung's grammar minimal pairs will use the same evaluator.

## Runs and time

**9m first.** *Earn each size* (DECISIONS.md) says no run at 21m until 9m is used up, so the pilot
starts at 9m: four shelves × two seeds, about 0.6B tokens seen each (four passes of the 1800
shelf's bytes), about 1.5 hours a run, about 12 hours in all. 9m probably cannot hold facts like
these. If it shows nothing, that is recorded as the 9m observation and is the case for running
21m. If it already shows a signal, that is a finding in itself.

**Then 21m, if the 9m readings warrant it:** the same eight runs, about 5 to 6 hours each, about
two nights.

## Steps

1. Build the shelves: a `scripts/cut_eras.py` that applies the death-year rule and the refusals,
   draws each shelf to the 1800 shelf's bytes, and writes `lists/era-1800.csv` and the rest.
2. Fetch about 4,600 books (about 2.3 GB) and run the leak check.
3. Check the claims against the notebooks and a history, then write and review the pairs.
4. Write the `pairs` evaluator with its floors, and its tests.
5. Write the eight 9m specs and queue them after tonight's queue.
6. Read the 9m results against the signal rule, then decide on 21m.

The claims and the signal rule go into DECISIONS.md before the shelves are cut, as the content
experiment's rule did.
