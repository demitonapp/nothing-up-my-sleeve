# Thorp dashboard: UI and UX standards

The dashboard is one hash-routed page, an Astro app in `web/` (built to `static/`, served by
`server.py`): `src/pages/index.astro` is the shell, `src/components/` holds one component per tab,
`src/styles/global.css` the tokens and components below, `src/lib/` the shared script pieces
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

## Navigation

The site is organised the way the project is: classes of ship (model sizes), the ships of each
class (runs), the voyages they sail on, and the discoveries followed across all of them. The header
holds the ways in, always:

- **Classes** (`#/classes`, home): one card per class of ship, each a model size with one job.
  A class opens its page (`#/classes/<class>`, below), whose first tab is its **fleet**: every
  ship of that class. A ship opens its own page.
- **Voyages** (`#/voyages`): the campaigns several ships sail on to find something
  (`thorp/fleet.py` `VOYAGES`): one card each with its goal, status, fleet and headline. A voyage
  (`#/voyages/<key>`) has one template: what it is and what it found, its ships with their
  settings, Forgotten Tomes score and the step each star first lit, the score run by run, first
  light (each star's score against step, threshold dotted), outcomes and levers. A panel only one
  voyage has carries `data-voyage` (the book-value loop's fit).
- **Discoveries** (`#/discoveries`): the two things followed across every ship to find our
  bearings. **Stars** (`fleet.STARS`: the Previous Word, the Duplicate Word, Nevermore), one card
  each with its threshold, what it rests on, and the first ship to light it or the nearest so far;
  and **traits** (fiction, verse, first person, the language families), with how many ships
  found and learned each, and the first to do so. Under the star cards, **the star chart**: every
  kind of attention head the literature describes (`thorp/dash/heads.py` `KNOWN_HEADS`: what it
  does, its family, what its source reports it rests on, where it was first described, what it has
  been seen in). A kind Thorp measures links to its `fleet.STARS` star and shows its state from the
  ledger; the rest say how Thorp could measure them. Adding a kind is an entry in `heads.py`;
  measuring one is a star in `fleet.py` and an evaluator.
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

Every class on the ladder (`LADDER` in `thorp/models/registry.py`) gets one page, built from one
template (`web/src/components/ModelPage.astro`, filled by `renderRung` in `dashboard.js`) at
`#/classes/<class>`, named by class, not size: `#/classes/proxy`, `#/classes/speller`…

Its tabs sit under its title, each with its own address:

0. **Fleet** (`#/classes/proxy`): every ship of the class in service, newest first, one row per
   ship (its fitout, its sailings and their seeds, its voyage, mean and best Forgotten Tomes
   score); the archived First Fleet folds away below. A row opens the ship.
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
4. **Waypoints** (`/waypoints`): the moments it passes in training. When each run first formed a
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

## Components

Each of these exists once. Use it instead of styling a new one.

- **DataTable** (`src/lib/datatable.js`): every `<table>` sorts by clicking a header, keeps its sort through
  the 5 s redraw, and keeps footer rows (one `colspan` cell) at the bottom. `data-sort="…"` on a
  cell sorts by a hidden value; `data-nosort` on a table opts out.
  A table whose rows open something gets the class `clickable`: its rows then show a hover, take
  keyboard focus, and open on Enter or Space.
- **Pill** (`.pill`): a small rounded label. Colour variants `.good`, `.bad`, `.blue`, `.accent`,
  and `.solid` for a filled one. Run status uses `.pill.running / .finished / .failed`.
  (`.badge` is an alias kept for existing markup.)
- **Button** (`button`, `.btn`): one look for every button on the dark page; `.on` marks the
  selected one in a group (`.booktabs`).
- **Field** (`select`, `input`): one look for every field.
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
- **Info popover** (`info(key)` in the script → `ⓘ`): the help for a metric (what it is, which way
  is better, how it is measured). Every metric's first appearance in a heading carries one.
- **Empty state** (`.empty`, or `empty(id, msg)` for charts): says why nothing is there and what
  command fills it, e.g. `thorp eval RUN --evaluators curiosity`. Never a bare blank.
- **Book reader** (`#reader`): a book is read the way a Kindle Paperwhite shows one, after the
  Atlas essay reader in the monorepo (`packages/ui/apps/atlas/src/components/EssayReader.tsx`):
  paper, ink, a justified serif, pages or scroll, A−/A+, a quiet footer. It is the one place the
  page leaves the dark theme, on purpose.

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
| class | a model size with one job (1m the proxy, 9m the speller…) |
| ship | a class fitted out one way: its training material and settings (the fitout) |
| sailing | one run of a ship, one per seed |
| fleet | the ships of a class; the First Fleet is everything fitted out before 7 November, archived |
| voyage | a campaign several ships sail on to find something, with a goal, levers and a stop rule |
| star | a destination: an attention head that does one recognisable job, lit at its threshold |
| lit / lit shared | a star is lit when one head reaches its threshold, and lit shared when the best layer's two strongest heads reach it together (a small model often splits one job across two heads); charts draw the single head solid and the shared pair dashed |
| trait | a direction in the hidden state that tells a kind of book apart on books never read |
| the wind | the error on each guess: how far the bet was from the word that came, felt by every weight that took part |
| a tack | the ship's response to the wind: one training update (the "bump" of a perceptron), its direction from the wind and its size from the learning rate |
| trim | how the tack is set: which guesses count and by how much, how big the step is, where it lands |
| the sieves | how hard the wind pushes each layer (push, `grad_norm/`) and how far the sail actually moves (move, `update_ratio/`) |
