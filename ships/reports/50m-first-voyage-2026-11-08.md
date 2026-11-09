# The 50m's first voyage: Table Talk's reading stage lands

Report for Justin, 2026-11-08, written about 19:30. Nothing in the queue, specs, runs or ledger was changed; the six `s1.table_talk` rows are the probe's own.

## The short answer

1. **The first 50m finished.** *Table Talk's reading stage* (`fu-ogden-v0-2~table-talk-reading@50m-pre-s1`) read Ogden v0.2 four times — 682.9M tokens, 20,840 steps — in 2h20m on one rented RTX 4090 for **$0.86**. It is the first real Thorp ship above the Mac trained on a GPU (the 9m parity run went first that afternoon).
2. **It is the best language model Thorp has.** Mean **1.3105 bits per byte** on the 16 Forgotten Tomes, **0.1285 under the 9m** on the same corpus and recipe, with every one of the 16 books improved. It is also the best parts-of-speech reader (0.502 at its best) and the first ship above Ogden's keyed table (0.320 vs the table's 0.303).
3. **It cannot answer questions yet.** Five questions at the table: **0 of 5 ended a turn**; 3 of 5 ran to the 200-piece limit; the answers echo or loop the question; "What is a ship?" was answered with a Q/A of its own ("Q: You can see? A: Yes."). The same five as completions are fluent English and ungrounded.
4. **The cards:** 8 of the 11 head cards are lit, but the **Bridge reads 0.063** (mark 0.5; the 9m held 0.569) and the **comparator 0.428** (the 9m 1.000) — the two staged riddles regressed. The mover just misses (0.175 vs 0.2).
5. **The ladder does not skip.** The 50m performs 10 of the 20 discovery cards, every one of them a phrase-level rung of the keel, pilot or speller; it misses **all four of its own paragraph rungs** (nature, mill, between, pigeonhole) and chaining is under the mark (+0.072 against +0.10). Its new job is talk, but the rung it is named for is not earned.
6. **This voyage is the dialogue stage's control**, and it now has a number: the dialogue stage must keep the Tomes at **1.3605** or better (this reading plus 0.05). The dialogue stage itself has not sailed.

## The voyage

| | |
|---|---|
| run | `fu-ogden-v0-2~table-talk-reading@50m-pre-s1`, run id `c353647d` |
| ship | Fitout: Ogden v0.2 @ 50m ~ table-talk-reading (the first 50m, Table Talk's reading stage), the full deck staged, the copy tack, released |
| spec | `ships/specs/fitouts/fu-ogden-v0-2~table-talk-reading@50m-pre-s1.yaml`, seed 1 |
| commit | `fffcfa54`-dirty |
| hardware | NVIDIA RTX 4090 (torch 2.15.0+cu132), Vast.ai instance 59672864, $0.369/h |
| at sea | 2026-11-08 15:44 to 18:46 (Brisbane), 140.3 minutes |
| cost | **$0.86** for the finished instance (two earlier hires did not finish) |
| steps | 20,840 × 32,768 tokens = 682,885,120 tokens (four passes of 170.7M unique) |
| speed | 138,280 tokens/s, 237 ms a step; a full eval 97 s, every 1,024 steps |
| model | 12 layers × 512, 8 heads, context 1,024, a 2,048-piece tokeniser; **38.8M parameters as built** — 17.6 tokens a parameter |
| reading | Ogden v0.2: 1,380 books, four passes, shuffled; the full deck staged; the copy tack (induction, alpha 3); the release at 90% (the last 2,084 steps by heart) |

The preset is called *50m*; with this run's 2,048-piece table it built 38.8M parameters (the README's 46.7M counts the 16,384-piece table, which this run does not use).

**The hire.** The charter lost one instance (59670112) and one failed with exit 1 (59670269) before the third (59672864) finished. The run itself is clean: 20,840 of 20,840 steps, every checkpoint synced, the final 20,840 on disk. The failing hires' cost is not in the ledger's $0.86.

## The language it learnt

Mean on the 16 Forgotten Tomes (all English, so English-only and total are the same):

| step | bpb | cross-entropy (nats/token) |
| ---: | ---: | ---: |
| 1,024 | 1.6835 | 3.4583 |
| 4,096 | 1.5329 | 3.1493 |
| 8,192 | 1.4100 | 2.8971 |
| 12,288 | 1.3591 | 2.7929 |
| 16,384 | 1.3282 | 2.7294 |
| 20,840 | **1.3105** | **2.6930** |

- **Against the 9m**, same corpus and recipe (`fu-ogden-v0-2~staged@9m-pre-s1`, 1.4390): **−0.1285 bits per byte**. All 16 books improve, by 0.10 (pg79535) to 0.16 (pg79475). This is the size curve's second point on Ogden v0.2; the 21m on v0.2 is not in the ledger (the `deck@21m` voyage has not sailed), so the curve has no middle yet.
- **Parts of speech** (the judge books' points, 2,048): `upos_top1` **0.4995** — the best in the lab (21m 0.484, 9m 0.466; Pan 0.372). `ogden_top1` 0.7139.
- **The bigram table**: `keyed_top1` **0.320** at the final step (0.323 at its best). Ogden's keyed table reads **0.303** (DECISIONS, 17:25) and the best Pan ship 0.208. This is the first Thorp ship above the table on Pan's own objective.
- **Loss**: 2.603 (the training distribution); the scaffold's own loss 1.409 once the pull is released (scaffold weight 0.0, phase 3).
- **Not Chinchilla-long**: 17.6 tokens a parameter, under the 20 the corpus plan uses. The curve is still falling at the last step (1.3121 → 1.3105 over the last 360 steps), so the reading is a floor, not a ceiling.

## The cards

The deck's 16, as this run reads them at step 20,840. Marks are the deck's (`fleet.STARS`, the pips' 3.0, the counter's R² 0.5). "9m" is the same corpus and recipe; Qwen3 4B and Pythia-160M are the recorded outside readings (`data/compare.imported/`).

| card | mark | 50m | 9m | Qwen3 4B | Pythia-160M | lit? |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| previous word | 0.50 | **1.000** | 1.000 | 0.804 | 0.837 | ✅ |
| two words back | 0.30 | **1.000** | 1.000 | 0.314 | 0.318 | ✅ |
| duplicate word | 0.30 | **0.865** | 0.635 | 0.915 | 0.647 | ✅ |
| rare word | 0.30 | **0.708** | 0.730 | 0.365 | 0.363 | ✅ |
| the sink | 0.50 | **0.638** | 0.660 | 0.516 | 0.755 | ✅ |
| the delimiter | 3.00 | **10.17** | 8.90 | 4.02 | 7.55 | ✅ |
| comparator | 0.30 | **0.428** | 1.000 | 0.960 | 0.997 | ✅ (weak) |
| nevermore | 0.30 | **0.598** | 0.598 | 0.852 | 0.893 | ✅ |
| three words back | 0.30 | 0.282 | 0.167 | 0.168 | 0.174 | ✗ (just) |
| mover | 0.20 | 0.175 | 0.058 | 0.293 | 0.231 | ✗ (just) |
| **the Bridge** | 0.50 | **0.063** | **0.569** | 0.089 | 0.529 | ✗ |
| counter (probe R²) | 0.50 | 0.394 | 0.332 | 0.496 | 0.515 | ✗ |
| number-spotter | 3.00 | 98.26 | 98.26 | 1.90 | 1.31 | ⚠ |
| order-word | 3.00 | 108.58 | 108.58 | 1.85 | 1.20 | ⚠ |
| premise-marker | 3.00 | 105.71 | 105.75 | 2.06 | 2.30 | ⚠ |

The table also carries three words back, a probe outside the 16. Fourteen of the 16 cards have a reading: induction only through the Nevermore's copy gain, and the Scales uncharted (no reading).

- **Nevermore's ability**: natural copy gain **2.08 nats** (the mark 1.0; the 9m 0.97); with the copy tack the scored copy gain is 6.33. The Nevermore is the one Face the run carries by heart.
- **The Bridge is the failure.** It held on the 9m (0.569) and on Pythia-160M (0.529), and this run reads 0.063 — below even Qwen's 0.089. The scaffold's own riddle reading agrees (5.7e-05 at the end). Either the 12-layer shape does not hold it where the 8-layer did, or the staged pull did not take; it wants one re-read at the last checkpoint before it is believed.
- **The comparator** is above its mark but far under the 9m and Qwen; the same question, smaller.
- **The three pips are not comparable across tokenisers.** Both Thorp ships read ~100 on number-spotter, order-word and premise-marker; every outside model we have read reads ~2. That is the 2,048-piece tokeniser's rare class pieces against the outside models' 50k–150k BPEs, not three cards won. Do not count them in a head-to-head.
- **Against Qwen3 4B, honestly**: the 50m is ahead on previous word, two words back, the delimiter and the rare word; behind on duplicate word, the sink, the comparator, the Bridge, the mover, the Nevermore and the counter; the three pips are uncomparable. That is 4 ahead, 7 behind, with three cards not counted. The old "15 of 16" target was not this voyage's job and is not claimed.

## The discovery chains

The 20 phrase-level and passage-level tests, the 50m at step 20,840. Performed is the deck's rule: lift ≥ 0.10 and score ≥ two thirds.

| chain | rung (class) | lift | score | performed |
| --- | --- | ---: | ---: | --- |
| Origin | kin (keel) | 1.195 | 0.958 | ✅ |
| | pedigree (pilot) | 0.721 | 0.958 | ✅ |
| | breeders (speller) | −0.002 | 0.417 | ✗ |
| | malthus (stylist) | −0.008 | 0.500 | ✗ |
| | **nature (paragraph)** | **0.042** | **0.542** | ✗ |
| Energy | fire (keel) | 1.498 | 0.958 | ✅ |
| | workshop (pilot) | 1.335 | 1.000 | ✅ |
| | smiths (speller) | 0.028 | 0.625 | ✗ |
| | rumford (stylist) | −0.073 | 0.458 | ✗ |
| | **mill (paragraph)** | **−0.015** | **0.500** | ✗ |
| Mendeleev | counting (keel) | 2.012 | 1.000 | ✅ |
| | period (pilot) | 0.537 | 0.833 | ✅ |
| | gap (speller) | 0.103 | 0.667 | ✅ |
| | triads (stylist) | 0.041 | 0.667 | ✗ |
| | **between (paragraph)** | **−0.023** | **0.417** | ✗ |
| Recurrence | again (keel) | 1.326 | 0.917 | ✅ |
| | refrain (pilot) | 2.535 | 1.000 | ✅ |
| | seasons (speller) | 0.125 | 0.708 | ✅ |
| | lucretius (stylist) | −0.015 | 0.583 | ✗ |
| | **pigeonhole (paragraph)** | **0.064** | **0.625** | ✗ |

**10 of 20 performed.** Every performed card is a phrase-level rung of the keel, pilot or speller; every rung from the stylist up is missed, and so are all four of the 50m's own paragraph rungs. The pattern is clean: the ship plays what a 9m plays, and a little more of it, but nothing that needs two facts chained.

- **Chaining** (the 40-item logic deck): gain **+0.072** against the +0.10 mark, score 0.417; the 9m read −0.030. The 8-item deck +0.036 (Qwen3 4B +0.192). It is climbing with size and still short.
- **Crowns** (the invented kingdom): gain +0.041 (mark 0.10), **moves −0.132** (the answer does not move with the standpoint), ask +0.050. Expected near zero without the dialogue stage; it is.

## The table: Table Talk's first five questions

Five questions through `thorp.table.reply` (temperature 0.8, seed 7, no history, up to 200 pieces), kept in `s1.table_talk`:

| question | answer (first line) | stopped | pieces |
| --- | --- | --- | ---: |
| What is a ship? | *Q: You can see? / A: Yes.* | blank | 14 |
| Why does ice melt in the sun? | *Why does ice? / A: Why does ice melt in the sun?* ×14 | length | 200 |
| What is two and two? | *Q: You can see one or more of them. / A: Q: Q. / A: Q. …* | length | 200 |
| Is it better to be good or to seem good? | *Q: You mean to say that you do not understand? / A: Q: What are you doing? …* | length | 200 |
| What happens to a plant that gets no water? | *Q: You can see it now, miss. / A. I do not know if you are not in a plant that gets no water?* | blank | 67 |

- **No turns.** 0 of 5 ended by opening the next `Q:`; 2 were stopped by the table's blank-line cut, 3 ran to the limit. That is the pre-dialogue failure mode exactly: the table cuts, the ship does not hand back.
- **The form is partly there.** She opens with `Q:` or a reply-shaped line, and one answer is a Q/A pair of her own ("You can see? / Yes."). The reading has taught her the *shape* of a turn, not what to put in it.
- **The content is echo and loop.** "Why does ice melt in the sun?" comes back as the question repeated behind `A:`; "two and two" collapses into `Q:` pieces; the plant answer echoes the question and adds "I do not know". Only the last shows an admission of not knowing, and it loops too.
- **The same five as completions** (temperature 0.7, seeds 1001–1005, stopping at a blank line) — the one form she was trained on:

| prompt | answer |
| --- | --- |
| A ship is | *in a state of perfect contentment. Come, sir," he said, "and do not make any difference to me.* |
| Ice melts in the sun because | *it were a snake, and, being but a stone's, it was a snake, and under my arm I had the look of a snake…* |
| Two and two are | *his. Speculiarity of the party. What made you forget this?* |
| It is better to be good than to seem good, because | *the truth is just. I have seen good portents and their wives and children travel about…* |
| A plant that gets no water will | *come next year, and then, when it is done, will be a good flavor.* |

The prose is fluent — spelling, punctuation, quotes, sentence rhythm — and ungrounded: a definition's shape without a definition, arithmetic answered with "his", a plant that "will be a good flavor". That is what 682.9M tokens of reading buys at 38.8M parameters: language, not answers.

## How this stands against the voyage's job

This voyage was never meant to converse; it is Table Talk's reading stage, and the dialogue stage's control. On that job:

- **The control is fixed**: 1.3105 bpb on the Tomes, so the dialogue stage's bar is **≤ 1.3605** (no worse by more than 0.05). The transcript, the five questions and this report are the "before".
- **The dialogue stage is not built**: the dialogue library, the turn converter and Table Talk's two checks (80% opening the next `Q:`; answers on topic beyond a shuffled pairing) are still to come (DECISIONS, 1187). Until they exist, every conversation with a Thorp ship is this: shape, echo, loop.
- **The turn check alone is cheap**, as suspected. A model can learn to open a `Q:` and to stop at an answer's length without learning to answer; the 0.25 content-word overlap the 21m already shows (against 0.00 shuffled) says the shape is partly in the reading, and the stage will mostly add the stop. Before the dialogue stage sails, add a **length-matched null**: ask the same question and a different question of the same length, and require the answer to move. And read the crowns' `moves` (+ the flip) as the content check, since "on topic" can be satisfied by echoing the question's nouns — which is exactly what this run does.
- **The 50m's own rung is unearned.** The ladder story says each size plays its class's rung. This 50m plays the 9m's and misses all four of its own. Its job moved to talk, and that is a fair choice, but the deck's record should say so plainly: the paragraph rung was not shown at the paragraph size.

## For Justin

1. **The Bridge.** Re-read it at the last checkpoint (one `thorp eval`), or accept 0.063 and mark the 12-layer shape as not holding it. The comparator wants the same look. Both are cheap; neither blocks Table Talk, but both matter to the 100m.
2. **The dialogue stage.** It needs the dialogue shelf (78 books, already scored), the turn converter, and the two checks. I would add the length-matched null above before it sails, and pre-register that the 50m's dialogue stage is judged on the Tomes (≤1.3605), turn-opening, and the crowns' `moves` — not on looking conversational.
3. **A second seed.** This is one seed; the class rule says a class counts on two. Another reading stage is about $0.86 and 2h20m. Whether it is worth it before the dialogue stage is your call.
4. **The 17.6 tokens a parameter.** The curve is still falling at 20,840; a second pass of the same shelf could move the Tomes under 1.30 for another ~$0.90, and it would make the dialogue stage's control stricter. Also your call.

## The record

- Spec: `ships/specs/fitouts/fu-ogden-v0-2~table-talk-reading@50m-pre-s1.yaml`; run `c353647d` in `ledger.sqlite`.
- Checkpoints: `data/checkpoints/c353647dc22ce3355a5a23adde56f3dab760b003/step-20840` (21 steps kept, 7.4 GB).
- Evals: 336 rows, 16 books, steps 1,024–20,840 (`hole-cards-unseen`).
- Table transcript: `s1.table_talk`, six rows for this run (the five above and one earlier probe).
- The five-question probe and the five completions were run by the assistant on 8 November; temperatures, seeds and piece counts are as stated above.
