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

## Model pages

Every model on the ladder (`LADDER` in `thorp/models/registry.py`) gets one page, built from one
template (`web/src/components/ModelPage.astro`, filled by `renderRung` in `dashboard.js`). Its URL is the model's class name, not
its size: `#proxy`, `#speller`, `#stylist`, `#paragraph`, `#bettor`, `#summit`. Old `#rung-1m` links
redirect there. The template, in this order, the same for every model:

1. Title: `← ladder`, size and class (`1m · The proxy`), the model's job.
2. Overview: shape, parameters, where it trains, what judges it, status.
3. **Every run at this size**: the RunGrid (below). It is the first chart on every model page.
4. What we measure, and why: each metric tied to the model's job, live or to come.
5. The model's own panels, and only these vary: `section.panel[data-kind="proxy"]` shows only on
   a model of that kind (the proxy's calibration against 9m). A new model-specific panel goes
   here with its `data-kind`, never as a special case in the script.
6. Scoreboard, then the Forgotten Tomes beside Qwen and training loss, then the books, then
   bits per byte by kind of byte and the laws.

Panels that draw one mark per run (the scoreboard, the bar charts) show the latest 30 runs and say
so; training loss shows the latest 12. Only the RunGrid shows every run, so a size with thousands of
runs (the proxy loop) stays quick to load and to redraw every 5 s.

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
