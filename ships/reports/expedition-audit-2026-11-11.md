# The expedition audit, the consolidation, and a queue that retires them (11 November)

Justin:

> "the goals have to have a relationship to expeditions in the db ... a lot of existing expeditions whose
> goals we haven't necessarily done and they may be cheap to solve on the 300k. So can you audit all
> expeditions and their goals and then propose a queue that will knock as many items off the expedition as
> possible so we start retiring expeditions and getting ready for our first model that we can chat to. This
> will be a 9m"

> "also the arc de triomphe is just complicating it, all the arc de triomphe goals can be migrated to the
> knockout and we can cancel the arc de triomphe"

> "a lot of the expeditions can actually be consolidated"

## 1. The relationship, in the store

A goal used to exist only as a Python tuple in `fleet.EXPEDITIONS`; nothing joined a goal to its expedition
and nothing joined a queue line to a goal. Now:

- **`s1.expeditions`** — one row an expedition (`key` PK, name, goal, fleet, preset, ship, declared_status).
  `fleet.py` stays the source of the words; this is the row to hang things from.
- **`s1.expedition_goals`** — one row a goal: `goal_id` PK, `expedition_key` FK, position, text, detail,
  why, and the **verdict the store owns**: `status` (open / partly / done / dropped), `evidence`, `words`,
  `settled_at`.
- **`s2.queue_lines.goal_id`** — FK to a goal, filled when the line is queued (from the spec's `goal:` and
  `ship:` label, or `--goal`).

The id is the same string `priorities.py` already ranks by (`arc_de_triomphe:4`), so a priority row, a goal
and a queue line are one key. A goal may declare its own `position`, which is what lets a goal be deleted
without renumbering the ones after it — the knockout kept `knockout:3` when its first two goals went.

    thorp goals sync                     # copy the words from fleet.py; verdicts are kept
    thorp goals                          # every goal, with its state
    thorp goals set <goal> done --evidence "run, metric, value"
    thorp queue add <line> --goal <goal>
    thorp queue show                     # each line prints its goal

Migration `v3q6r9s2t5u8_expedition_goals` (head); module `thorp/expedition_goals.py`; the coordinator's
state refresh syncs the words pass by pass. An expedition is retired when every goal is `done` or
`dropped` **and** its fleet `status` is `done` with a `learned` line — the two records the fleet already
keeps.

## 2. What the audit found

Every goal and every declared outcome was read against the ledger — the best reading, not the latest,
because a card lit early and faded late is still a card that formed.

**Seventeen expeditions became four.** Thirteen are settled and retired; four carry every open question.

### Retired (13)

| expedition | why it is settled | the reading |
| --- | --- | --- |
| book_value | already closed | the shelf explains 59% of the spread; 19 loop runs |
| apprentice | already closed | handover 2.143 vs control 2.110 bpb; the trick does not transfer |
| two_bets | the type bet beats the word bet | 0.3314 / 0.3145 against 0.2159 / 0.2141, both seeds, over the 0.10 prediction |
| induction | answered negative | engine 0.0087 / 0.0071 vs its random twin 0.0103 / 0.0077; no Nevermore at 300k |
| ogden | the corpus is fixed and read | six runs home; previous-word 0.344–0.396 → 0.528–0.633 and the comparator 0.106–0.181 → 0.477–0.675, 300k → 9m, two seeds |
| best_keel | answered by ranking runs we have | 15 of 55 300k runs hold all four rungs at their final reading; 300k@v0.0.6-pins leads at mean lift 0.573 |
| first_light | answered negative at 1m | duplicate-word 0.0136 against 0.3; a 50m later reads 0.876 |
| arc_de_triomphe | merged into the knockout | its four goals are now knockout:4–7, position for position |
| table_talk | merged into kipling | kipling:7 — the same deliverable, the period-English recipe |
| two_facts | merged into the knockout | knockout:8 — chaining rising with class, one rung up |
| logic_tutor | merged into the knockout | knockout:9 — whether chaining can be taught |
| smallest_bridge | merged into card_census | card_census:2 — how small the four cards still form |
| apprentice_2 | merged into seedling | seedling:2 — what a pilot inherits from the rung below |

### Open (4 expeditions, 17 open goals)

- **kipling** — 6 open, 1 done, 1 partly. Open: 2 control tokens, 3 the chat 9m, 4 the probe, 5 the 21m,
  7 Table Talk. Done: 6 GQA (at 300k, two seeds: no language gain, and it costs the mover and the bridge).
  Partly: 1 IFEval (the 9m read 89.6% on the 541 against a 65% mark, but the rigged pilot cost the language,
  bpb 2.09 → 4.75, and the honest held-out split has never run).
- **knockout** — 1 done (no card is necessary in any of the six models read), 2 dropped (Justin: the 21m
  smoke needs no reasoning), 3–9 open: the SmolLM2 smoke, the Qwen audit, the arch, our first reasoning
  model, the AI2 ARC audit, the chaining ladder, the teaching of chaining.
- **card_census** — 2 open. The 300k half is already in the ledger (previous-word lit in five arms, the
  comparator in one); the 1m half never sailed (0 of 21 arms).
- **seedling** — 2 open. The keel donor is read; no grown-from-keel pilot has ever sailed.

**What is cheap and was never done:** the AI2 ARC audit (a reading, ~10 minutes a ship), the 300k control-
token quartet and probe (the batch that failed on a corrupt cache), the 9m chat pair, and the 1m census.

## 3. The proposed queue

`ships/specs/queue-proposed-2026-11-11.txt`, in five phases. The order is by goal closure per hour:

| phase | lines | goal(s) | cost |
| --- | --- | --- | --- |
| A. free readings | the two queued investigations; five arc readings | knockout:4, knockout:7 | minutes to hours, no voyage |
| B. the 300k sweep | 10 lines | kipling:2, kipling:4 | ~12h |
| C. the chat 9m | 2 lines | **kipling:3 + kipling:7** | ~5h |
| D. the cheap closures | ~7 lines at 1m | seedling:1–2, card_census:1–2, knockout:8–9 | ~3h a line |
| E. the 21m | 1 line | kipling:5, knockout:3 | ~12.5h |

**Phase C is the answer to "our first model that we can chat to".** The 9m pretrains, then
`9m@v0.0.6-return` (written today, `goal: 3`, modelled on the pilot that read 89.6%) teaches it to answer
and obey; the Chat tab reads it directly. That one pair closes kipling:3 and kipling:7 together.

## 4. What was changed in the repo

- `s1.expeditions`, `s1.expedition_goals`, `s2.queue_lines.goal_id`; migration `v3q6r9s2t5u8`.
- `thorp/expedition_goals.py` (sync, verdicts, retireable), `thorp goals` CLI, `thorp queue add --goal`.
- `priorities.py` and the priority API read goals by position, so ids are stable across deletions.
- `fleet.py`: knockout reduced to the SmolLM2 goal and joined by the four arc goals (positions 4–7), the
  two-facts aim (8) and the logic-tutor aim (9); arc closed; thirteen expeditions closed or merged.
- `ships/specs/fitouts/9m@v0.0.6-return.yaml` — the chat leg, `goal: 3`, conforms to SOP v0.0.6.
- `backend/thorp/sources/gutenberg.py`: `resolution.csv` is now written under an exclusive lock and
  replaced atomically, and read past a torn row. The corrupt 43 MB cache that killed every 300k ship on
  11 November was repaired (valid UTF-8, one torn row dropped) and `prepare()` now succeeds on
  `300k@v0.0.6`, `-marks` and `-probe`.
