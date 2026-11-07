# Thorp dashboard: UI and UX standards

The dashboard is one hash-routed page, an Astro app in `web/` (built to `static/`, served by
`server.py`): `src/pages/index.astro` is the shell, `src/components/` holds one component per tab,
`src/styles/global.css` the tokens and components below (`src/components/ui` the shadcn primitives, see "shadcn"), `src/lib/` the shared script pieces
(DataTable, charts, formatters, the reader) and `src/scripts/dashboard.js` the panels. These rules keep it reading as one
system. When a change needs something not covered here, add the rule here in the same change.

## Tokens

Every colour, radius and font size comes from a token on `:root`. No hex value or pixel font size
is written anywhere else in the CSS, and the charts read the same tokens (`C` and `PALETTE` in the
script are filled from the CSS, not typed in again).

| token | use |
|---|---|
| `--bg` | the page |
| `--panel` | panels, cards, the header's active tab |
| `--raise` | hover and popover surfaces, one step above a panel |
| `--line` | every border and rule |
| `--text`, `--muted` | body text; labels, notes, secondary numbers |
| `--accent` | the one highlight: active tab, selected row, sort arrow, card hover, section titles |
| `--good`, `--bad`, `--blue` | status only (finished / failed / running), never decoration |
| `--fs-xs` 11 · `--fs-sm` 12 · `--fs-md` 13 · `--fs-base` 14 · `--fs-lg` 16 · `--fs-xl` 18 · `--fs-2xl` 22 | the only font sizes (2xl is for headline numbers) |
| `--r-sm` 6 · `--r-md` 8 · `--r-pill` 10 | controls; panels, cards and popovers; pills |
| `--track`, `--c5`…`--c12` | a chart's background trace; the chart palette after blue, accent, good, bad |

Numbers sit in `tabular-nums` everywhere (set on `body`).

## Layout

- A tab is a `.section`: an `h1` with the question it answers in `.q`, then panels.
- A panel is `section.panel` with an `h2` title and an optional `.note` saying how to read it.
- Two or three panels side by side use `.row` / `.row3`; both fall back to one column on narrow screens.
- Spacing comes from the grid gaps (16px). One-off margins use `.mt` (8px), not `style=""`.
  Inline styles are only for values computed at run time (a chart height, the reader's page width).

## The words (2026-11-07 16:20, `fleet.TERMS`)

An **expedition** is a line of experiments with one goal, its levers and its stop rule (was a voyage:
`#/expeditions`, `#/voyages` still answered). A **voyage** is one ship's run, one spec trained once
(was a run, or a sailing). A **library** is a book list Thorp reads from, scores on or refuses (was a
shelf: `#/library`, `#/shelves` still answered); the ship's two stores are the canonical libraries.
Storage keeps `run_id` and the runs table, and the code its old names; the page says the new ones.
Every expedition's page follows **one template**: its header and figures, then the same five tabs
(`#/expeditions/<key>[/at-sea|/findings|/fleet|/inside]`). **Overview**: what it found and its next
steps ("nothing written up yet" until it comes home), and the question (what it measures, its levers).
**At sea**: the observation deck. **Findings**: its own instrument if it has one (the census grid, the
knockout, the induction chart, the climb, the book-value fit), then **its readings**, every voyage on
each measure it declares, the best marked. **Fleet**: its ships, the Forgotten Tomes score only where
it has one, first light only for the stars it is bound for. **Inside**: the journey through the layers.
Nothing on the page belongs to another expedition: an instrument shows only on its own expedition
(`data-voyage`), and a tab that doesn't apply is hidden, not left empty (At sea while nothing of it is
at sea, queued, paused or awaiting orders; Fleet before it has a ship; Inside until one of its voyages
records soundings); an address naming a hidden tab opens Overview. The **observation deck**
(`/api/observation?expedition=`) reads each of its voyages at sea live from its log
(`data/runs/<run_id>.log`) and the ledger: how far it has come and how long it has left, its loss as
a sparkline, tokens a second and memory, the four necessary cards as they stand, the logic deck's gain
and cause, and its **star chart** (`finds`, `latest` and `sky` from `_finds` and `_sky`): every star
by level with a line to each it rests on, the tricks beside them dashed to the stars expected to do
them, and the four chains rung by rung; each star lights gold at its first light and each trick blue
at its first performance (`fleet.performed`), numbered in the order found, the newest pulsing. Not
found yet: dim, brighter the nearer its latest reading is to the mark; found and since fallen below
it: dimmed; not built: a dashed ring. **Play** lights the finds one at a time in order; the slider and
the chips beneath go to any point, **live** to where the voyage is now. The section opens on **the
Nevermore card** (for now; a toggle gives **every star**): a flow, at one reading of the voyage, from
every head (by layer; `heads` from `_heads`, the layer x head matrices the stars, nevermore and cards
evaluators keep each eval) through the sieves, what each head does (a Nevermore head at its mark, a
previous-word head at its mark, nearly one at half the mark, another star's head, no job yet), to the
link: a previous-word head with a Nevermore head in a later layer forms the card; otherwise no
Nevermore above it, no previous-word head below, or still forming. A line says whether the card has
formed and names the nearest heads; a table beneath gives every head's two scores as bars against
the marks. Play runs the readings in order; the slider and live as on the chart. With none of its voyages at sea, the deck says
where its next one stands in the queue, and which voyage is at sea instead.
The Expeditions page opens on **the queue at a glance** (`/api/expeditions/overview`): the voyage at
sea, a bar of the voyages still to sail coloured by expedition with about how many hours, the queue's
lints, and per expedition its voyages at sea, queued, its next at #n, finished and failed. An
expedition's **state** is S2's view (since 16:35), worked out from the helm and the queue, never the
hand-set word (`declared`, on hover): at sea (at most one), under way, in port, home, paused, and
**awaiting orders** in the warning colour (declared running with nothing at sea or queued: stalled,
or done and not closed). The voyage at the **helm** (name, kind, pid, since) shows beside the voyage
at sea, and in Governance's S2. A ship's
page shows its voyage's **library aboard** (`/api/voyage/<run_id>/library`: each library's stage,
where it came from, books and hash; its opt-in and refusals), and each voyage chip carries where its
reading came from (`/api/voyages/where`).

## Navigation

The site is organised the way the project is: classes of ship (model sizes), the ships of each
class (runs), the voyages they sail on, and the discoveries followed across all of them. The header
holds the ways in, always:

- **Classes** (`#/classes`, home): one card per class of ship, each a model size with one job.
  A class opens its page (`#/classes/<class>`, below), whose first tab is its **fleet**: every
  ship of that class. A ship opens its own page.
- **Voyages** (`#/voyages`): the campaigns several ships sail on to find something
  (`thorp/fleet.py` `VOYAGES`): one card each with its goal, status, fleet and headline. A voyage
  (`#/voyages/<key>`) has one template: what it is and what it found (a finished voyage's
  `learned`, then its **suggested next steps** from `fleet.Voyage.next_steps`), its ships with their
  settings, Forgotten Tomes score and the step each star first lit, the score run by run, first
  light (each star's score against step, threshold dotted), outcomes and levers. A panel only one
  voyage has carries `data-voyage` (the book-value loop's fit).
- **Discoveries** (`#/discoveries`): **Tricks of the trade**, in three subtabs: **Chaining two
  facts** (`#/discoveries`, the trick in focus: where the claim stands, live; then **Methodology:
  chaining two facts**, rendered as written in `fleet.METHODS["chaining"]` (the trick; its parts,
  each covered, partly or not; the gaps; the planned controls of the logic deck; the metric,
  chaining gain; the cards it needs, a card in the deck linking to the star chart and pulsing when
  lit, a planned one dimmed; the status); then how it is measured and judged today: the matched
  pairs with an example from each chaining test, lift, the rule, grading, the chaining lift, the
  forecast and backtest, the pre-registered rule), **Quantum mechanics** (`#/discoveries/quantum`, the route of seven waypoints, then the
  discovery chains table)
  and **Registry of tricks** (`#/discoveries/registry`, every trick, with traits a link away) and
  **Stars** (`#/discoveries/stars`: a grid of every star Thorp measures by class of ship, each cell
  the class's best reading against the mark, green with the first lit step where a sailing lit it,
  and the card judge's verdict; then the star cards, the bridge layer by layer and the star chart). A trick, a chain, the stars and the traits keep their own addresses beneath. A trick is what a model can do, judged
  from outside by its bets; the catalogue is `thorp/dash/tricks.py` (`KNOWN_TRICKS`, 40 tricks).
  The tricks are grouped into the seven **waypoints** on the route to quantum physics (`WAYPOINTS`:
  reading, knowing, counting, reasoning, mathematics, physics, discovery), shown first as the route
  with each waypoint's **gate** tricks (◆, performed before a ship moves on; the rest are
  milestones). Each trick has what it does, the tricks it rests on, the field's **size band** (one
  order of magnitude, `FIELD_BANDS` in `server.py`, the detail on hover; "not shown in the field"
  for Thorp's own tests), how sure that is ("documented", "rough", or "today", where better data
  moved it down), the models and paper, the kinds of head thought to do it, Thorp's measurement or
  how it could be measured, and its **goal class**: the class of ship expected to reach it, about
  an order of magnitude smaller than the field where the depth it needs allows (None: beyond the
  ladder; `taught` marks a reference the field shows only when trained on the task). The table
  sorts and filters by waypoint and band. Quantum physics itself is the far horizon, beyond the
  budget; the destination the ladder proves is the bettor's three discovery tests, one per strand
  (the Origin test for reasoning, the energy test for physics, Mendeleev's gaps for mathematics;
  the geometry test was first choice but is not viable on Gutenberg in English), each a bet
  between an idea and its rivals on books from before its cutoff, pre-registered in DECISIONS.md.
  Each is reached by a **chain of six rungs**, one per class, keel to bettor, linked by `leads_to`
  (`fleet.chains()`): the words of the idea (keel), the copying trick put to it (pilot), its pieces
  as everyday knowledge (speller), what the precursors wrote (stylist), the pieces chained into a
  conclusion no sentence states (the 50m) and the discovery (bettor); the stylist's and the 50m's
  rungs were swapped so each chain gets harder as it climbs (DECISIONS.md, "The rungs above the
  keel rewritten"). The Origin: like father, like son, the pedigree test, the breeders' test,
  Malthus and Lyell, Nature's breeder. Energy: fire and ice, the workshop test, the smith's test,
  Rumford and Davy, the mill test. Mendeleev's gaps: one, two, three, the period test, the gap test,
  Döbereiner's triads, the between test. The eternal return (the philosophy test, cutoff 1872): again
  and again, the refrain test, the seasons test, Hume and Lucretius, the pigeonhole test. All read on one evaluator and scale (lift: idea over rival,
  less what the words alone carry), and every class is scored on every rung.
  **The discovery chains** table at the top of Discoveries has the four chains as rows in that fixed
  order (from `fleet.chains()`) and the classes as columns, smallest first, so rungs line up class by
  class (a chain with no rung for a class shows "no rung"). Each cell is every class's best lift and
  best share of pairs right, with Qwen3 0.6B for scale. The last row, from `fleet.RUNGS`, says what
  a model at each rung is according to the four tests (title in bold, summary beneath); it is read
  from fleet so it stays in one place. A matched-pairs test is **performed** under the share rule
  (`fleet.performed`; DECISIONS.md, "The share rule"): its lift at the threshold *and* its share of
  pairs right at `min_score` (two in three), at the same reading. The server applies it to
  `performed_at`, so every performed count on the dashboard follows it; tricks without `min_score`
  keep lift ≥ threshold. ✓ is performed; ▲ marks a class that performed a rung set for a bigger
  class, ⚠ (amber) one that did so while a bigger class measured on it fails, a sign the pairs want
  auditing. The geometry test is revived as the bettor's fifth test, outside the chains.
  **One chain** (`#/discoveries/chains/<key>`, keyed by the bettor's test, linked from each row of
  the chains table and from every rung's trick page) tells that test as a climb: the idea, who found
  it and the shelf (with the cutoff), all `fleet.CHAINS` copy, then the six steps keel first, each
  with its class and `fleet.RUNGS` title, the test (linked to its page), what the step adds to the
  one below, the evidence class by class as in the table plus the floor, Qwen3 0.6B, and the rule
  (lift and share), and its pairs: six shown, all on demand, each with ✓ or ✗ for each class's best
  sailing (that pair's lift in the latest `discovery` artifact, in the CSV's order). Above the keel a pair
  has a frame (the prompt's tail, its own column in the CSV), and the passage reads premise / **frame**,
  the frame in the stronger weight, since the lift is what the premise adds over the frame alone. The bettor's
  step reads "pairs not written yet" until `lists/discovery-<test>.csv` exists, with the rivals
  and the ablation from its `about`.
  **Grading** (`fleet.grading`, written to `data/compare/chain-grades.json`): a chain is graded when
  it gets harder at every rung across all the models read, Thorp's and the reference ladder's
  (`fleet.REFERENCE_LADDER`: Pythia 14m to 410m, Qwen3 0.6B, and Qwen3 1.7B and 4B at 4 bits). No model performs a rung while
  failing one below it (an inversion), no rung is performed by more models than the one below,
  and every rung is performed by some model. Each chain's grade sits under its name in the table
  ("graded", or "not graded" with the inversions, the rungs more pass than below, and the rungs
  unreached; the inversions on hover) and in the chain page's header, with every inversion listed
  and how many models perform each rung. "Show the reference ladder" (a per-viewer toggle,
  remembered) puts the ladder's lift, share and ✓ beside Thorp's classes in every cell and step;
  off, the one reference `tricks.py` names stands in.
  "→ leads to" and "← led by" notes link each pair in the trick table, the route, the Waypoints
  and Goals tables and each trick's page, where the partner's chart sits beside the trick's own.
  A trick's chart draws its threshold (amber), its floor (grey: the highest untrained reading among
  its sailings, `tricks/<key>/floor_lift`) and outside models' readings (`reference` in
  `tricks.py`, such as Qwen3 0.6B's lift), all dotted and labelled.
  A trick in `fleet.TRICKS` with no evaluator yet shows "pre-registered (cutoff …) · evaluator not
  built yet"; one with `viable` false shows "not viable on Gutenberg in English". A row opens the trick (`#/discoveries/<trick>`): its
  waypoint and gate, what it rests on, the field, the goal class, how it is measured, the stars
  needed to learn it, how Thorp is tracking class by class, and for measured tricks every
  sailing's score by step. One link away: **the stars** (`#/discoveries/stars`) and **traits**
  (`#/discoveries/traits`).
- **The table** (`#/voyages/<key>/table`, linked from Table Talk's voyage page): talk with a ship.
  Pick a sailing (Table Talk's own first, then any finished ship), a temperature, the longest answer
  and an optional seed; type a line and the ship answers it as "A:" after your "Q:"
  (`thorp.table.reply`, through server.py's POST `/api/table/reply`, the one endpoint that
  writes). The last eight exchanges go with each question as the conversation so far; every
  exchange is kept in the sailing's transcript (`thorp.table.transcript`, `/api/table/transcript`).
  Beside the talk are the ship's star and trick readings at the checkpoint answering, measured
  ones first. Each answer says why it stopped (the next turn, the length, the end of text), its
  tokens and seconds. Ships not trained on the Q:/A: form don't converse yet, and the page says so.
- **Leaderboard** (`#/leaderboard`): two boards on chaining two facts, from one table
  (`leaderboard.payload()["table"]`, outside models and Thorp versions together), split by the
  noise. **Chaining**: the rows whose chaining lift clears +0.03, ranked by it, with the chaining
  gain (logic deck), passed of 4, each test's lift and share, and what Thorp must match each
  competitor at; Thorp's forecasts join only when they clear the noise too. **Approaching
  chaining** ("the closest to chaining: the cards every chainer holds, then following one premise"):
  the rest, ranked by how many of the four necessary cards they hold (four small cards, lit or dark,
  "unreadable" where so) and then by the logic deck's one-hop lift, with the chaining lift greyed,
  since below +0.03 it is noise. Both boards carry **cause and effect** (`cause_gain`: the logic deck's chaining
  gain on its eight cause items), a value and a small bar with the 0.1 mark dotted: a strong reading
  counts, a small one is noise. The competitor and Thorp pages outline the cause bar in the "by kind
  of relation" chart. One-hop lifts within 0.05 of each other are noise too: those rows tie (`tied`), share
  a rank shown as "=5" with "tied within the noise" beneath, and are listed biggest first. Thorp rows keep their version names and page links. The old
  detail for a competitor's last cell on the Chaining board:
  reading there (with P once forecastable, the band in the tooltip), and the size each fit first
  reaches it at. The test columns drop first on narrow screens. Folded beneath: **Smoking the 2–4B
  range** (the least P over the competitors on each fit, or "not yet forecastable: N of 3 classes
  above the noise"; claimed, probable or not by the pre-registered rule; the chart of chaining
  lift against parameters with both fits and their bands, the competitors as red diamonds and
  the reference ladder in grey; the backtest) and **every ship** with chaining readings, filterable
  by class. A Thorp row is named by version ("Thorp 300k v1": `leaderboard.payload` best's `name`;
  the register `data/thorp-versions.json`, a version crowned only when a ship beats the last by more
  than the noise), its ship and sailings beneath, and opens **its page** (`#/leaderboard/thorp/
  <ship_key>`, `/api/thorp`, from `leaderboard.thorp_entry`: the mean of its sailings' latest
  readings) on the competitor page's template: the class, the ship, its runs, the version and its
  history, then the same chaining result, cards and rungs. Each outside model's name opens **its page** (`#/leaderboard/competitor/<model>`,
  `/api/competitor`, from `data/compare/chain-grades.json`): who made it (a link to its lab), its size, the checkpoint,
  and what Thorp must match it at (a tenth its size, with each fit's forecast there); its chaining
  result (the chaining lift, the tests performed, each test's lift and share, the logic deck's gain
  and share, the deck asked each way, one to three hops, one premise, swapped, padded, and the gain
  by kind of relation); its **cards** as playing cards (mover and comparator by one head and shared,
  the bridge with its curve over layers; lit or not; "unreadable" where its attention can't be read
  through MLX-LM; previous-word and Nevermore read for every model by the same reader,
  `cards.copying_cards`, Nevermore with its copy gain; "being read" until the cards land); and every rung of the four chains, keel to the 50m, Thorp's internal measures,
  shown because the page describes the competitor. The climb (internal: `leaderboard.internal`, `/api/leaderboard/internal`) lives on the
  two-fact voyage's page: each run's climb over training (`/api/climb`), coloured by class, the
  reference ladder as dotted levels, with a switch to the chaining lift or the chaining gain
  (logic deck) over training.
  The star chart (`#/discoveries/stars`) has **the bridge, layer by layer** (`/api/bridge`): the
  bridge card is a curve over layers, `stars/bridge/layer_<i>` (nats: how strongly the answer's
  position carries the middle term), one line per run, the provisional threshold dotted. The
  logic deck (`logic_test`) is in the registry; the comparator and bridge are kinds in the star
  chart, and the name mover is the mover card.
  **The card judge** (`thorp.card_check` verdicts, served as `card_verdicts`): each card carries a
  badge on the star chart, the methodology and the competitor pages: **necessary card** (green:
  every model that chains plays it), **marker** (blue: only the chainers play it), **not trusted**
  (amber: the reading isn't valid yet), with the counts behind it on hover.
  The server never sends NaN: a failed reading (NaN or infinity) goes out as null, since one NaN
  makes a whole JSON response unreadable to the browser.
  **The art** (`thorp/dash/art/generate_art.py`, the Atlas generators' Eduardo Risso style, made with
  fal; saved to `web/public/art/<key>.png`): a ship across the top of each class card (keel to summit,
  each a vessel a size up from the last) and a face on each playing card (previous-word, Nevermore,
  mover, comparator, bridge) wherever the card appears: the star chart, the methodology and the
  competitor pages. An image not made yet removes itself, so a card without art draws no frame.
  **The deck** (`lib/deck.js`): on a competitor's or a Thorp version's page the five cards are a
  player's hand on a table: the cards it has lit are in its hand, face up and fanned (each with a
  corner rank and suit, P♣ previous-word, N♠ Nevermore, M♦ mover, C♥ comparator, B♠ bridge, and its
  art), lifting on hover; the ones it hasn't are still in the deck, set aside face down with how
  close each came (a bar on the back), or greyed where unreadable or not read. Suits are printed in ink, never
  red: colour on a card means something (green lit, amber not trusted). A card the judge doesn't
  trust (`valid` false) keeps its place, in the hand or the deck, but carries an amber dashed edge,
  sepia art and a "not trusted" stamp across it, so it can't pass for a sound card. Any card turns
  over on a click (or Enter / Space) to what it does: the star's `about`, cut to fit (whole
  sentences up to about 170 characters, else the first up to its colon), how it stands, and a link to
  the stars; a set-aside card grows to a hand card's size while turned. A card stays turned through
  the page's redraw until clicked again. The readings, the mark
  and the judge's verdict sit in a table beneath, and the bridge's curve over layers below that.
  **The card census** (the `card_census` voyage's page, `/api/census`): which of the four necessary
  cards each class can draw, and its cause-and-effect score, run as ablations of the class's own
  fitout (`data/runs/cards/fitout-census-<key>.json`: {variation: [run per stage]}, run names read
  from the file since a variation may reuse the fitout's own run for a shared stage). Per fitout,
  "n of 4 possible at <class>" with the four small cards, then a grid of the variations (the fitout
  first) by the four cards and cause and effect, each cell the latest stage's reading (one head or
  shared, shaded toward the mark, green ✓ where lit; cause with its change from the fitout's own at
  that stage), the stage named where it isn't the last. A row opens to its three stages, each run
  linked. The first design's cd-* runs were never run and aren't shown.
  **The knockout** (the `knockout` voyage's page, and a section on each competitor page that has
  one; `/api/knockout`, `data/compare/knockout-<model>.json`; DECISIONS.md "The knockout,
  pre-registered"): in a model that chains, each card's 8 strongest heads silenced, beside three
  random draws of 8 heads. A badge per card (NECESSARY or not shown), a bar per card for the gain lost
  when silenced (cause; the comparator, order) beside the random draws' drops on that same measure in
  grey, and each card's own rule dotted over its group (0.1, and twice its largest random drop), and a table with each card's drops, verdict and its heads
  (layer:head); the competitor's deck table notes each card's knocked-out heads.
  **Discovering the induction head** (the `induction` voyage's page, `/api/series`): the Nevermore's
  natural score over steps for the trigram engine (green) against its random twin (grey), two seeds
  each (seed 1 solid, seed 2 dashed), the 0.3 mark dotted and a star where each run first lights it;
  then previous-word (0.5) and the copy gain (0.5). Above, the verdict by the pre-registered rule: lit
  on two seeds or not, and "repetition did it" when the engine lights it and its twin does not.
- **A lab** (`#/leaderboard/lab/<key>`, `/api/lab`, `thorp/labs.py`): the maker of a family of
  outside models (EleutherAI makes Pythia; `labs.LABS`, matched by family name, since checkpoints are
  re-hosted under `mlx-community/`), opened from the maker under each outside model's name on the
  leaderboard and from its page's "made by". Its models, then **its best** and **its worst**: the five
  (model, test) readings on the rungs of the four chains that stand highest and lowest against the
  other labs' models on the same test (standing: lift less their median, over their spread, in σ),
  each with its lift, the field median, how many it beats, share right and ✓. The other labs link
  beside the title.
- **Governance** (`#/governance`, after Leaderboard; `thorp/vsm.py`, `/api/governance`): Thorp's rules
  as Beer's Viable System Model, five Card bands from S5 at the top to S1, each with its name, purpose,
  its code as Badge chips and its live numbers from `vsm.audit()`. S5 policy: each policy's
  statement, when Justin adopted it, and an enforced or advisory Badge. S4 intelligence: the
  competitors and the reference ladder, linked to the leaderboard. S3 control: per policy, the
  queued runs breaking it and those excepted with the exception's reason (the stores policy large;
  an Alert while it is advisory and runs break it), each list one ghost Button open. S2 coordination: the queue's lints in an Alert, or a
  green "no collisions". S1 operations: the runs queued and every voyage with its status, linked.
  Read-only: a policy is switched in `data/policies.json`, by Justin.
- **Shelves** (`#/shelves`) opens on **Fitouts** (`thorp.shelves.fitouts`, kept warm like the
  shelves): a fitout is the training material matched to its stages. A card per fitout: its aim,
  positions, vocabulary, tack and tokens; two lanes, **pretraining** (its stages in order, one run)
  and **post-training** (in order, each seeded from the one before, with its learning rate and tack),
  each stage a block sized by its tokens showing its shelf (a click opens that shelf below), books,
  tokens per pass × passes, and purpose; then its runs and their status. Beneath them, the **fitout
  builder** (`thorp/fitouts.py`): a palette of shelves (training, other and drafts; each tile its
  books, tokens, in-window trigram repetition and variety, and a mini scatter of its books, variety
  against repetition, the frontier ringed; `/api/shelf_trigrams`), dragged into two lanes,
  pretraining and post-training. A dropped shelf is a stage block: its name, tokens (a slider up to
  the shelf, the whole shelf at the top), which books (all, random, highest repetition, the Pareto
  frontier), passes and purpose, and for post-training its learning rate and tack; blocks reorder by
  drag (within or across lanes) and are sized by tokens × passes. Above the lanes, the fitout's name,
  aim, positions and tack; below, the total tokens and how much of it is the repetition engine.
  **Save** posts to `fitouts.save` (a readable error if it doesn't validate); **Queue** builds the
  saved fitout for a class (the first four rungs) with its seeds, at the top or the end of the queue.
  The queue passes the S3 gate first: a refusal (`vsm.GateRefused`) shows its own words. The ship's
  stores (`lists/stores/`) head the palette, since a fitout that reads only them passes the stores
  rule; any other shelf opens an **opt-in** field for the reason in words (`opt_in` on the fitout)
  (`fitouts.queue`), only after a confirmation, since it changes what the Mac trains next. The saved
  fitouts and the hand-curated ones (opened as a copy) sit beneath, each one click from the builder.
  tokens per pass × passes, and purpose; then its runs and their status. Each class page has the
  same cards on a **Fitouts** tab (`#/classes/<class>/fitouts`, `/api/fitouts?preset=`), the class's
  fitouts only ("no fitout curated for this class yet" where there is none), followed by the cards
  each stage drew: every run (pretraining, post-training 1, 2, …) with the four necessary cards'
  latest readings, a small card lit or dark and the value beside it. Below the fitouts, every
  list of books (`thorp.shelves.payload`, `/api/shelves`). It takes
  seconds to compute, so the server keeps it warm (computed at start, served from memory and
  recomputed in the background every five minutes); until the first is ready the page says it is
  reading. Grouped by kind: training shelves, decks (scored on, never read), probes, other, and
  drafts folded away. A row per shelf: name, path and about; books fetched (of the rows when some
  aren't); about how many tokens; its language families as a small bar; read by how many runs and
  how many queued. A row opens to its uses (each run and its role: reads, reads first, a stage,
  tokeniser, scored on, refuses; queued ones in amber) and its books (`/api/shelf_books`), each
  opening in the reader; a book not fetched yet is shown faded.
- **Sieves** (`#/sieves[/<sailing>]`): how the ship answers the wind, layer by layer. An intro in
  the voyage vocabulary, a card per sieve with its write-up from `fleet.SIEVES` (push, move,
  heading: rendered as written there, never rewritten on the page), then for a picked sailing
  (the one running by default) a heatmap per sieve, layers as rows with the bottom of the stack at
  the bottom and each layer's push kink marked (◆); heading uses a diverging scale centred on 0.
  **Settled** gives, per layer, the first step its heading holds 0.8 for three records running,
  its push kink, and any star lit in that layer (one head or shared): do headings settle from the
  bottom up, and does a layer settle when its star lights? The kink rule (`KINK_MIN_RECORDS`,
  `KINK_FIRM`) is read from `fleet.py`, so page and code use one rule.

A ship is a class fitted out one way (`thorp/fleet.py` `Ship`: its training material and settings,
the fitout), and each of its runs is a sailing, one per seed. A ship's page
(`#/ships/<ship key>[/<sailing>[/<tab>]]`) shows its name, fitout line, whether it is in service or
archived with the First Fleet, and its sailings as chips; the tabs (Betting, Books, Languages,
Sieves, Attention, Traits) show the sailing picked, the latest by default. `#/ships` lists every
run. Ships are reached from a class's fleet, a voyage or a discovery; there is no run picker.
Stars are destinations, never ships.

Every address is canonical: older ones (`#sizes`, `#proxy`, `#rung-1m`, `#/models/…`, `#betting`,
`?run=`) are rewritten to the new form, never kept beside it.

## Class pages

The Classes home also has **Filling the seven steps to quantum physics**: a matrix of classes
against the seven steps, each cell the tricks that class performed, with "+n" inherited from a
smaller class and a bar; the last column is the whole route. Taught-only tricks don't count.

Every class on the ladder (`LADDER` in `thorp/models/registry.py`) gets one page, built from one
template (`web/src/components/ModelPage.astro`, filled by `renderRung` in `dashboard.js`) at
`#/classes/<class>`, named by class, not size: `#/classes/pilot`, `#/classes/speller`…
Renamed classes keep their old addresses (`CLASS_RENAMES` in `server.py` and `dashboard.js`:
the seedling is now the keel, the proxy the pilot), which redirect to the current name.

Its tabs sit under its title, each with its own address:

0. **Fleet** (`#/classes/proxy`): every ship of the class in service, newest first, one row per
   ship (its fitout, its sailings and their seeds, its voyage, mean and best Forgotten Tomes
   score); the archived First Fleet folds away below. A row opens the ship.
0. **Goals** (`/goals`): the class on the route to quantum physics. **The goal is as many
   tricks as the class can learn**, building on every trick below it and carrying all of them up
   to the next class, so the seven steps fill as fast as they can (Justin, 7 November). The goal
   classes in `tricks.py` are what the field would expect of each size: a minimum to prove, never
   a cap. The tab gives the goal, what the field is expected of this size (the highest step among its
   goal tricks, and the expected edge: those tricks at that step), how much is filled,
   what it carries up from smaller classes, and what the next class takes over; then **Filling
   the seven steps**, a bar per step split into tricks performed by this class (green), inherited
   from a smaller class (outlined: carried up, still to show here) and open (grey). Then the seven
   waypoints bottom to top with every trick as a chip: this class's goals lit, carried ones
   marked, bigger classes' faded with their class, ✓ where this class's sailings performed it.
   The goals table sorts by any column and filters by step to quantum physics.
1. **Overview** (`/overview`): the class's performance in as few charts as possible. The
   RunGrid (every run at this size), then the Forgotten Tomes score run by run with the best so
   far and the Qwen lines.
2. **Training** (`/training`): what it was trained on and how. The model (shape, parameters,
   where it trains, status), every run's setup (shelf, passes, seed, vocabulary, context, tokens,
   minutes), training loss, and the training shelves book by book.
3. **Scoring** (`/scoring`): every score on its runs, in two bands.
   - **Science**: how well it predicts text it has never seen. Bits per byte: the Forgotten Tomes,
     the held-out books, the split by kind of byte, the Forgotten Tomes book by book, and ranking
     shelves as a bigger model does (the proxy's calibration).
   - **Art**: how its writing compares with real books. The laws of text, non-words, word length
     and punctuation, balance and capitals, grammar (minimal pairs), voice (register), traits.
   Each band opens with its own "What we measure" list. The split is the `ART` set in
   `dashboard.js`; a metric not named there counts as science, so a new art metric must be added.
4. **Waypoints** (`/waypoints[/envelope|/stars]`): three sub-tabs, the steps a class proves in
   order, each a table of tricks (step to quantum physics, trick, the field's band, goal class,
   the stars needed with their state on this class, the trick's state on this class), sortable
   by any column and filtered by step:
   1. **Expected**: tricks the field already shows at this size or smaller (the field's band at
      or below the class's band): matched first.
   2. **Pushing the envelope**: this class's goals, and those it carries up from smaller classes,
      that the field shows only in bigger models.
   3. **Exploring the stars**: goals of the bigger classes, nearest first: the ambitious ones.
   A card per step counts its tricks, how many are measured and how many performed, and says
   "proven" when all are performed. Below the steps, **the instruments**:  the kinds of head this class is
   expected to reach (the star chart's "expected from" at or below it) with its own sailings'
   state on each, and what comes into reach one class up. Then the moments it passes in training. When each run first formed a
   Nevermore (induction head, `evaluators/nevermore.py`) and first found and learned each trait
   (`evaluators/probes.py`), then the strongest head and copy gain by step, and each trait's
   held-out AUC by step. The thresholds come from the evaluators through `/api/waypoints`. Each
   band has a "Read" button that opens its write-up in the book reader (`/api/essay`: the
   evaluator's own docstring), and the Nevermore test passage opens as a book. The Nevermores
   band opens with the model's hand of cards (below), dealt step by step.

A panel that belongs to one kind of model only carries `data-kind` (the proxy's calibration
against 9m) and sits in the tab it belongs to; never a special case in the script.

Panels that draw one mark per run (the scoreboards, the bar charts, the run tables) show the latest
30 runs and say so; training loss and the Waypoints charts show the latest 12. Only the Overview
shows every run, so a size with thousands of runs (the proxy loop) stays quick to load and to
redraw every 5 s.

The Scoring tab's "What we measure" table has a **now** column: for the classes scored on the cards
(registry `scored`: the four necessary cards held, then cause and effect, then chaining two facts),
the current version's readings (`/api/class_score`: from `leaderboard.thorp_entry` of the class's
best ship): the four small cards and "n of 4", the cause-and-effect gain with its 0.1 mark, the
chaining lift (marked "in the noise" at or below 0.03), and the census's best cards held so far.

## Forms (`src/lib/forms.js`)

A field is labelled, and the label is tied to it (wrapping it, or `for=`). A form is a `<form>`:
Enter submits, and the browser's own checks run first (`required`, `min`/`max`, `pattern`). The
checks the page can make itself run next and put their message **under the field** they concern
(`fieldError`: `aria-invalid`, the message tied by `aria-describedby`); a field loses its mark as it
is put right. A server refusal goes to its field too where it names one (the fitout builder: "stage
N: …" on that stage's block, the pretraining rule on its lane, the stores rule on the opt-in), and
otherwise to the message line. A button that sends says what it is doing ("Saving…", "Queueing…")
and takes no second click (`busy`). A form worth keeping keeps an unsaved draft in this browser and
offers it back ("An unsaved fitout from 16:46 … Restore it / Discard"), and the page warns before
leaving it unsaved. Every **filter bar** (`data-filters`) has a "reset" link, and its filters
(`data-remember`) are kept per viewer, restored once their options arrive. Nothing here replaces the
confirmation a consequential action needs (the queue's AlertDialog).

## Components

Each of these exists once. Use it instead of styling a new one.

- **DataTable** (`src/lib/datatable.js`): every `<table>` takes shadcn's Table look from here, sorts by clicking a header, keeps its sort through
  the 5 s redraw, and keeps footer rows (one `colspan` cell) at the bottom. `data-sort="…"` on a
  cell sorts by a hidden value; `data-nosort` on a table opts out.
  A table whose rows open something gets the class `clickable`: its rows then show a hover, take
  keyboard focus, and open on Enter or Space.
- **Pill**: a shadcn Badge. In string-built markup, `class="${pillCls('good')}"` (`src/lib/ui.ts`);
  in an island, `<Badge variant="good">`. Tones: `good`, `bad`, `blue`, `accent`, `solid`, and the
  run statuses `running / finished / failed`, each mapped to a Badge variant (`good`, `bad`, `info`,
  `highlight`, `solid`; `outline` when none). Never write `class="pill …"` by hand.
- **Button**: a shadcn Button, `btnCls()` (see "shadcn"); one look for every button on the dark page.
  A choice among several (the sailings) is a ToggleGroup, `toggleCls()` with `data-state="on"`.
- **Field**: shadcn's Input and NativeSelect, `fieldCls()` and `selectCls()`; one look for every field.
- **RunGrid** (`runGrid(rung, runs)`): every run at one size as a square, like a GitHub
  contribution graph, in the order the runs started. Bands of 7 × 53 squares (371 runs) stack
  downwards, so a new run only adds a square at the end. Colour is the run's Forgotten Tomes
  quartile among the runs scored so far, `--heat1` (worst) to `--heat4` (best, the strongest green);
  `--heat0` is not scored yet, red is failed, a pulsing blue outline is running, accent is the
  selected run. Hover gives the score and its rank; a click selects the run. It redraws only when
  a run or a score changes.
- **Cards** (`src/lib/cards.js`): a model's attention heads as a hand of playing cards, the way
  Nevermores are shown. Thorp beat blackjack by counting cards, remembering what was dealt to bet
  on what comes next, and a Nevermore does the same in text, so each head is a card.
  - A card is face down (the patterned back, `--card-back`) until its head becomes a Nevermore,
    scoring at least the evaluator's threshold on either test; then it turns face up (`--card-face`,
    ♠, an accent edge). In between, the face rises from the bottom in proportion to score ÷
    threshold, so a head that is forming shows.
  - The big number is the real-prose score, the corner one the random test; layer and head sit
    top left. The score is always printed: the card never hides the number.
  - Up to 64 heads the whole hand is laid out in rows by layer, the top layer first. Above that,
    the strongest five are fanned out. Card games give the look only: no poker hand ranks, which
    would mean nothing about a model.
  - `renderHand` draws one eval step; the Waypoints hand panel walks the steps with a slider and
    ▶ play, and a card that turns between two steps flips over. `miniHand` gives a run's
    strongest five as tiny cards for a table row.
- **Journey** (`src/lib/journey.js`, on every voyage page): one sailing read as the data's journey
  up its stack, drawn bottom to top: embeddings, each layer as an attention half and a
  feed-forward half, the output. The base is the **soundings** (`fleet.SOUNDINGS`, taken when
  *reading*, where the sieves measure *training*): beside each depth the guess the model would make
  if it stopped there (bits per byte) and how much that layer lowered it (green) or raised it
  (red); out of each half an arrow sized by how hard it writes into the stream and tilted by its
  turn, straight up along the stream (green), level across it (blue, something new), down against
  it (red). **Modules** the viewer switches on read each layer at the step chosen: push, move and
  heading for each half, the stars lit in that layer (one head or shared), and the push kink. One
  step slider moves everything and follows the latest reading unless moved; a second sailing can
  sit beside the first, read at the same step. A sailing without soundings says so and still
  shows its modules.
  A sailing that received heads from another (a `transplant` artifact, as in the Magician's
  Apprentice) has the receiving attention half outlined in the accent colour with "⇄ heads …
  transplanted from …" beside it, and "⇄ position embeddings transplanted" when positions came
  too. A voyage with transplants opens on a receiver beside its control of the same seed. On the
  first-light chart the donor run (the one the heads came from) is added and drawn dotted, the
  receivers say "(received heads)", and the star picker opens on the voyage's own first star.
- **Stages** (`src/lib/stages.js`): a run's training read in named stages, in order, under one
  learning-rate schedule (spec `data.stages`, the ledger's `stages` artifact; `/api/stages`). Every
  chart whose x-axis is the training step gets them as bands, labelled by name with a dotted line
  at each change: the ship page's charts, a class's training loss and waypoint charts, a voyage's
  first-light chart, the Sieves heatmaps. A chart of several runs gets bands only when those runs
  share the same stages. The ship page lists its sailing's stages (shelf, passes, steps, tokens),
  and the journey's step slider names the stage of the step shown, with the stages as a strip
  beneath it. A run without stages is one stage, reading, and draws none.
- **Teachers and transplants**: a run with `optim.teacher` learns from another run's predictions;
  on a voyage's first-light chart the teacher is drawn dotted, as a donor is, and its students say
  "(taught)". A transplant may carry token embeddings too (`tok`), whole layers beneath (`below`,
  outlined in the journey) and layer norms (`ln`); a lineage run's control is "lineage-ctl" of the
  same seed, every other receiver's is "control".
- **Info popover** (`info(key)` in the script → `ⓘ`, a shadcn HoverCard): the help for a metric (what it is, which way
  is better, how it is measured). Every metric's first appearance in a heading carries one.
- **Empty state** (shadcn Empty: `emptyCls()`, or `empty(id, msg)` for charts): says why nothing is there and what
  command fills it, e.g. `thorp eval RUN --evaluators curiosity`. Never a bare blank.
- **Book reader** (`#reader`): a book is read the way a Kindle Paperwhite shows one, after the
  Atlas essay reader in the monorepo (`packages/ui/apps/atlas/src/components/EssayReader.tsx`):
  paper, ink, a justified serif, pages or scroll, A−/A+, a quiet footer. It is the one place the
  page leaves the dark theme, on purpose.

## shadcn

shadcn/ui is the component kit, set up as in the monorepo's `shared-components` (`components.json`:
new-york, neutral, CSS variables, `@/components/ui`). React and Tailwind v4 are in the build for it.

- `src/components/ui/` holds the primitives, added with `pnpm dlx shadcn@latest add <name>`. They
  stay stock apart from Thorp's Badge variants; `*-variants.ts` hold the cva definitions apart from
  the `.tsx` so plain scripts can import them without React.
- `src/styles/ui.css` maps shadcn's colour, radius and font-size names onto the tokens above in
  `@theme`; it never redefines them on `:root`. Two names collide: Thorp `--muted` is grey **text**
  (shadcn `text-muted-foreground`), Thorp `--accent` is the gold **highlight** (shadcn `primary`,
  `ring`; shadcn `accent` is the hover surface, `--raise`). Tailwind's preflight is left out, so
  the hand-written CSS in `global.css` keeps working while it is replaced.
- Markup Astro writes uses the React components directly; they render at build time with no
  client JS (`Panel` in `src/components/Panel.tsx`). Markup `dashboard.js` builds as strings takes
  the same class lists from `src/lib/ui.ts` (`pillCls`, `btnCls`).
- A component that has a shadcn match below is built from it. A new look starts from a primitive,
  not from new CSS in `global.css`.

### Component map

Every Thorp component with a shadcn match is now built from it. In Astro markup, a `class={…}` from
`src/lib/ui.ts`; in `dashboard.js` strings, `class="${…}"` from the same helpers; tables are styled
by DataTable, so their markup names no classes.

| Thorp component | shadcn | how |
|---|---|---|
| Pill / badge / run status | Badge (+ `good`, `bad`, `info`, `highlight`, `solid`) | `pillCls(tone)` |
| Panel (`section.panel`, `h2`, `.note`) | Card | `cardCls(false, 'panel')`, or `<Panel>` in Astro; `.panel h2` keeps the title style |
| Class, voyage, star and sieve cards (`.card`) | Card; a link when it opens something | `cardCls(true, 'card')`; the card art layout stays in `global.css` |
| Button | Button (`outline`, `ghost`), size `xs` | `btnCls()` |
| Sailing picker (`a.sailing`) | ToggleGroup item, `data-state="on"` | `toggleCls()` |
| Header nav | Tabs (default), hash links as triggers | `tabsCls()`, `tabCls()`; `setTab()` sets `data-state` and `aria-current` |
| A page's own tabs (`.subnav`: class, ship, discoveries, waypoints) | Tabs (`line`) | `tabsCls('line', 'subnav')` |
| Field: `select` | NativeSelect, keeping the browser's arrow | `selectCls()` |
| Field: `input` (text, number, search) | Input | `fieldCls()` |
| `input[type=range]` | Slider colours on the native range | `rangeCls()` |
| `input[type=checkbox]` | Checkbox colours on the native box | `checkCls()` |
| DataTable (`<table>`) | Table (header, body, row, head, cell) | stamped by `datatable.js`, with `data-slot`; sorting unchanged |
| Back link, `a.crumb` | BreadcrumbLink | `crumbCls('back')` |
| Empty state (`.empty`, `empty()`) | Empty; EmptyDescription in a table cell | `emptyCls()`, `emptyCls(true)` |
| Info popover (`ⓘ`) | HoverCard look; opens on hover and focus as before | `hoverCardCls` |
| RunGrid hover (`.gridtip`) | Tooltip | `tooltipCls` |
| The ledger's reading (`div.verdict`) | Alert, edged in the verdict's colour | `alertCls('yes' / 'no' / 'open')`; a verdict inside a table cell stays text |
| Fitout builder's "lose your changes?" | AlertDialog, on a native `<dialog>` (focus trap, Esc) | `await confirmDialog(text, { title, ok })`; never `confirm()` |
| Book reader (`#reader`) | Dialog: `role="dialog"`, focus in on open and back on close | the paper theme stays its own |
| `details` (archive, folds, the ship at a glance) | Collapsible: the native element, which is what it renders | n/a |
| `.band` heading rule | none: a heading with a rule, not a separator element | n/a |
| Stat strip (`.stat`) | none: Thorp's own, inside a Card | n/a |
| Playing cards, journey SVG, RunGrid squares, climb and family bars, fitout lanes | none: domain drawings | n/a |
| Charts (Plotly) | none (shadcn Chart is Recharts) | n/a |

## Interaction

- Anything clickable shows `cursor: pointer`, a hover state and a visible focus ring
  (`:focus-visible`, the accent colour). Anything clickable can be reached and used by keyboard.
- Escape closes whatever is on top (popover, reader). Arrow keys turn pages in the reader.
- State a reader would want back is kept in `localStorage` under `thorp.*`, wrapped in try/catch:
  table sorts live for the page's life; the reader's text size, mode and place in each book persist.
- The URL holds where you are: `?run=` for the run, `#tab` or `#rung-<size>` for the view. Clicking
  THORP goes home.

## Words

- Plain English in sentence case. Headings say what a panel shows; the `.note` says how to read it.
- Say which way is better for every metric (`lower is better`), in the popover or the heading.
- Units on every number that has one (`bpb`, `KB`, `min`). Missing values are `–`.

### The voyage vocabulary

The page speaks the project's metaphor, consistently. Each word means one thing:

| word | means |
|---|---|
| class | a model size with one job (300k the keel, 1m the pilot, 9m the speller…) |
| ship | a class fitted out one way: its training material and settings (the fitout) |
| sailing | one run of a ship, one per seed |
| fleet | the ships of a class; the First Fleet is everything fitted out before 7 November, archived |
| voyage | a campaign several ships sail on to find something, with a goal, levers and a stop rule |
| trick | something a model can do, judged from outside by what it bets (copying what followed last time; Wednesday after Tuesday); `fleet.TRICKS`, performed at its threshold |
| star | a destination: the mechanism inside that does a trick, an attention head that does one recognisable job, lit at its threshold |
| lit / lit shared | a star is lit when one head reaches its threshold, and lit shared when the best layer's two strongest heads reach it together (a small model often splits one job across two heads); charts draw the single head solid and the shared pair dashed |
| trait | a direction in the hidden state that tells a kind of book apart on books never read |
| the wind | the error on each guess: how far the bet was from the word that came, felt by every weight that took part |
| a tack | the ship's response to the wind: one training update (the "bump" of a perceptron), its direction from the wind and its size from the learning rate |
| trim | how the tack is set: which guesses count and by how much, how big the step is, where it lands |
| the sieves | how hard the wind pushes each layer (push, `grad_norm/`) and how far the sail actually moves (move, `update_ratio/`) |
