// The Expeditions page (UI.md "Expeditions"), as typed HTML renderers: the queue landing (waters plan,
// the queue at a glance, every voyage), the expedition cards, one expedition (its header, outcomes,
// levers, ships, readings and the instruments only some expeditions carry: the fit, the census, the
// knockout, the induction head and the climb), and the observation deck's star chart and Nevermore
// flow. The island owns the route, the tabs, the data and the events; these are pure functions of the
// payloads, kept out of dashboard.ts so the browser and the server render the same markup.
//
// Nothing here may import lib/charts, lib/stages, lib/panel or lib/reader at module load: the island
// is server-rendered, and those touch `document`/ECharts when they load. The chart drawers live in
// views/expedition-charts.ts and are imported inside the island's effects.

import { CARD_FACE } from '../../lib/deck';
import { big, esc, fmt, signed } from '../../lib/format';
import { alertCls, btnCls as shadcnBtnCls, cardCls, emptyCls, hoverCardCls, pillCls, toggleCls as shadcnToggleCls } from '../../lib/ui';
import { modelHash, shipHash } from '../router';
import { STAR_LABEL, artImg, starHeadline, statusPill } from './helpers';

// the ⓘ beside a metric heading. lib/info wires its popover listeners at module load, so it cannot be
// imported by this server-rendered module: the chip is drawn here and the island loads lib/info in an
// effect to place it.
const FT_HELP: [string, string, string] = ['The Forgotten Tomes score', 'Lower', 'Bits per byte on 16 period books released on Gutenberg after Qwen 3.8 appeared, so no Qwen model can have trained on them. The same number for Nothing up my sleeve and for Qwen, whatever their tokenisers: the yardstick for the order-of-magnitude gate.'];
const infoChip = (h: [string, string, string]): string =>
  `<span class="info" tabindex="0">ⓘ<span class="pop ${hoverCardCls}"><b>${esc(h[0])}</b><br>Better: <b>${esc(h[1])}</b><br>${esc(h[2])}</span></span>`;

// ---- the payloads (server.py api_voyages / api_expeditions_overview / api_queue / api_waters / ...)
export interface StarRead {
  threshold?: number | null;
  latest?: number | null;
  star: string;
  steps_to_lit?: number | null;
  shared_steps_to_lit?: number | null;
  best?: number | null;
}
export interface Run {
  name: string;
  run_id: string;
  ship?: string;
  ship_name?: string;
  ship_key?: string;
  size?: string;
  preset?: string;
  status?: string;
  set_aside?: boolean;
  ft_en?: number | null;
  settings?: Record<string, unknown>;
  stars?: StarRead[];
  tokens_seen?: number;
  [key: string]: unknown;
}
export interface Outcome { about: string; metric: string; better?: string }
export interface Lever { key: string; low?: number | null; high?: number | null; choices?: (string | number)[]; fixed?: boolean; about?: string }
export interface ShipStar { lit?: number; soonest?: number | null; lit_shared?: number; soonest_shared?: number | null; best?: number | null }
export interface Ship {
  key: string; name: string; subtitle?: string; preset?: string; size?: string; archived?: boolean;
  sailings: { run_id?: string; name?: string; seed?: number | null; status?: string | null; label?: string; ft_en?: number | null }[];
  ft_en_mean?: number | null; stars?: Record<string, ShipStar>;
}
export interface Fit { coef?: Record<string, [number, number, number]>; cv_r2?: number; runs?: number }
export interface Expedition {
  key: string; name: string; goal: string; status: string; fleet?: string; preset?: string; sop?: string | null;
  /** the goals one by one, each with what it is and why it is wanted (fleet.py `goals`); absent on most */
  goals?: { text: string; detail?: string; why?: string }[];
  runs: Run[]; ships: Ship[]; stars?: string[]; learned?: string; next_steps?: string[];
  outcomes?: Outcome[]; levers?: Lever[]; stop: { max_runs: number; about?: string };
  fit?: Fit | null;
  plan?: { n: number; kind: string; name: string; detail?: string; queue?: string }[];
}
export interface Rung { preset: string; name: string; [key: string]: unknown }

export interface ExpRoute {
  kind: 'home' | 'charter' | 'queue' | 'list' | 'voyage' | 'table' | 'other';
  key: string | null;
  tab: string;
  qview: 'glance' | 'every' | 'planning';
}

export const ETABS = ['overview', 'plan', 'at-sea', 'findings', 'fleet', 'runs', 'training', 'fitting', 'inside'];
const PREFIXES = new Set(['expeditions', 'voyages']);

/** Parse the expedition routes. `/expeditions` is the landing: three doors (the current charter, the
 *  expeditions, the queue), its tabs replaced by the breadcrumbs' menu (12 November, Justin). The charter
 *  is `/expeditions/charter`, the cards are `/expeditions/expeditions`, the queue is `/expeditions/queue`;
 *  one expedition is `/expeditions/<key>[/<tab>]`; the table is `/expeditions/<key>/table`. The old
 *  `/voyages` prefix and `/expeditions/plans` are answered too. */
export function parseExpeditionRoute(path: string): ExpRoute {
  const clean = String(path || '/').split('?')[0].split('#')[0];
  const parts = clean.split('/').filter(Boolean);
  const bare: ExpRoute = { kind: 'other', key: null, tab: 'overview', qview: 'glance' };
  if (!parts.length || !PREFIXES.has(parts[0])) return bare;
  const dec = (x: string): string => { try { return decodeURIComponent(x); } catch { return x; } };
  const rest = parts.slice(1).map(dec);
  if (!rest.length) return { kind: 'home', key: null, tab: 'overview', qview: 'glance' };
  // /expeditions/charter/<section>: each of the charter's cards has its own page (13 November, Justin); `key` is the section
  if (rest[0] === 'charter') return { kind: 'charter', key: rest[1] || null, tab: 'overview', qview: 'glance' };
  if (rest[0] === 'queue') return { kind: 'queue', key: null, tab: 'overview', qview: rest[1] === 'every' ? 'every' : rest[1] === 'planning' ? 'planning' : 'glance' };
  if (rest[0] === 'expeditions' || rest[0] === 'plans') return { kind: 'list', key: null, tab: 'overview', qview: 'glance' };
  if (rest[1] === 'table') return { kind: 'table', key: rest[0], tab: 'overview', qview: 'glance' };
  return { kind: 'voyage', key: rest[0], tab: ETABS.includes(rest[1]) ? rest[1] : 'overview', qview: 'glance' };
}

// ---- the state S2 works an expedition out from the helm and the queue (expeditions.overview)
const STATE_TONE: Record<string, string> = { 'at sea': 'running', 'under way': 'blue', 'in port': '', home: 'good', paused: 'accent', 'awaiting orders': 'bad' };
const STATE_NOTE: Record<string, string> = {
  'at sea': 'a voyage of it is at sea now', 'under way': 'voyages of it are queued', 'in port': 'planned, nothing queued yet', home: 'done',
  paused: 'paused', 'awaiting orders': 'declared running with nothing at sea or queued: stalled, or done and not closed',
};
export const statePill = (st: string | null | undefined, declared?: string | null): string => st
  ? `<span class="${pillCls(STATE_TONE[st] ?? '')}${st === 'awaiting orders' ? ' awaiting' : ''}" title="${esc(STATE_NOTE[st] || st)}${declared && declared !== st ? `; declared ${esc(declared)}` : ''}">${esc(st)}</span>`
  : '';
export const expPill = (state: string | undefined | null, v: { status?: string }): string =>
  state ? statePill(state, v.status) : statusPill(v.status);

export const classLink = (rungs: Rung[], preset: string | null | undefined): string => {
  const c = (rungs || []).find((x) => x.preset === preset);
  return c ? `<a href="${modelHash(c)}">${esc(c.preset)} · ${esc(c.name)}</a>` : esc(preset || '–');
};
const btnClsLocal = (v: 'outline' | 'ghost' | 'default' = 'outline', extra = ''): string => shadcnBtnCls(v, extra);
const toggleClsLocal = (extra = ''): string => shadcnToggleCls(extra);

// ---- the expedition cards (#voyagecards): one card an expedition, its fal image (generate_art.py,
// EXPEDITIONS), its aim, what it found and the same counts the table carried, so the page reads as one
// grid of like cards rather than a table of names with no picture.
const cut = (t: string, n: number): string => (t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t);

/** The landing's three doors (12 November, Justin: "make it open with three cards the Current Charter,
 *  Expeditions, Queue and add them with fal images ... instead of using the tabs use the breadcrumbs
 *  nav"): one plate each, the same brass yard card Demiton's sections use, with the live count under
 *  the line and the way on from the crumb's menu one click up. The reading arrives after the first
 *  paint, so an unread card says which reading it is waiting for. */
export function expeditionDoorsHtml(launch: any, overview: any): string {
  const r = launch && launch.readiness;
  const exps: any[] = (overview && overview.expeditions) || [];
  const q = overview && overview.queue;
  const open = exps.filter((e) => e.status !== 'done').length;
  const plural = (n: number, one: string, many = one + 's'): string => `${n} ${n === 1 ? one : many}`;
  const doors: [string, string, string, string, string][] = [
    ['Current Charter',
      'the one expedition: the fleet it launches, the master charter it sails under, and every goal\'s part in it',
      '/expeditions/charter', 'expeditions-charter',
      r ? `${r.signed} of ${r.params} signed · ${plural(r.blocking, 'deciding goal')} open · ${r.home} of ${r.ships} ships home` : 'reading the charter…'],
    ['Expeditions',
      'every expedition: the ones still settling their charter, and the settled record of what each went out to find',
      '/expeditions/expeditions', 'expeditions-list',
      exps.length ? `${open} open · ${exps.length - open} settled` : overview ? 'no expeditions yet' : 'reading the expeditions…'],
    ['Queue',
      'what sails next, in order, as the S2 coordinator takes it from the Mac lane',
      '/expeditions/queue', 'expeditions-queue',
      q ? `${plural(Number(q.voyages) || 0, 'voyage')} queued · ${Number(q.hours_left || 0).toFixed(1)} h of sailing left` : 'reading the queue…'],
  ];
  return `<div class="harbours shipyardgrid expeditionsyard">${doors.map(([name, about, href, art, tally], i) =>
    `<a class="${cardCls(true, 'card harbourcard shipyardcard')}" href="${esc(href)}">${artImg(art, 'cardart ship')}
      <div class="yardplate">
        <span class="yardnum">${String(i + 1).padStart(2, '0')}</span>
        <span class="yardrule" aria-hidden="true"></span>
        <span class="nm">${esc(name)}</span>
        <span class="job">${esc(about)}</span>
        <span class="yardnote">${esc(tally)}</span>
        <span class="yardopen">open the ${esc(name.toLowerCase())} →</span>
      </div></a>`).join('')}</div>`;
}

/** The charter's seven sections as fal cards (12 November, Justin: "for this page
 *  http://localhost:4321/expeditions/charter can you give me fal cards for the fleet, the ship, the
 *  tokeniser, what it reads, the scaffold, the training, the return leg"): the same brass yard plates as
 *  Demiton's sections, each opening the section it names by its anchor. The fleet is the launch's own
 *  panel; the other six are the master charter's groups. */
/** The charter's seven cards, and a page each (13 November, Justin: "each of the cards ... needs it's own
 *  page"): /expeditions/charter/<slug>. `group` is the master charter's group key the page shows ('fleet' is
 *  the launch's own fleet panel, not a group). */
export const CHARTER_SECTIONS: { slug: string; group: string; name: string; about: string; art: string }[] = [
  { slug: 'fleet', group: 'fleet', name: 'The fleet', about: 'the eight ships of v0.1: a base at every class, and an instruct ship from the 9m up', art: 'charter-fleet' },
  { slug: 'ship', group: 'ship', name: 'The ship', about: 'the hull: layers, width, query and KV heads, context, positions and how it is built', art: 'charter-ship' },
  { slug: 'tokeniser', group: 'tokeniser', name: 'The tokeniser', about: 'the pieces: the vocabulary, byte fallback, what it is trained on and the control symbols', art: 'charter-tokeniser' },
  { slug: 'reads', group: 'reads', name: 'What it reads', about: 'the recipe, passes, cleaning, order and refusals: the corpus every class reads', art: 'charter-reads' },
  { slug: 'scaffold', group: 'scaffold', name: 'The scaffold', about: 'the cards and riddles, their weight, and how long a pin is held, faded and released', art: 'charter-scaffold' },
  { slug: 'training', group: 'training', name: 'The training', about: 'the optimiser, learning rate, warm-up, batch, schedule, grad clip and precision', art: 'charter-training' },
  { slug: 'return-leg', group: 'leg', name: 'The return leg', about: "the instruct ship's leg: what it inherits, its turns and stages, its learning rate and the pull", art: 'charter-return-leg' },
  { slug: 'bar', group: 'bar', name: 'The bar', about: 'what the fleet is judged on and leans toward: its curiosity, read on every ship, and its targets on the leaderboard', art: 'charter-bar' },
];
export const charterSection = (slug: string | null | undefined) => CHARTER_SECTIONS.find((s) => s.slug === slug) || null;
/** Where a master-charter row lives: its group's page, at the row's own anchor (param keys read `ship.layers`). */
export const charterParamHref = (key: string): string => {
  const group = String(key).split('.')[0];
  const sec = CHARTER_SECTIONS.find((s) => s.group === group);
  return `/expeditions/charter/${sec ? sec.slug : ''}#param-${encodeURIComponent(String(key).replace(/[^a-z0-9-]/gi, '-'))}`;
};

export function charterCardsHtml(launch?: any): string {
  // under each card, where the section stands: ships home for the fleet, rows signed for a group
  const stand = (s: (typeof CHARTER_SECTIONS)[number]): string => {
    if (!launch) return '';
    if (s.slug === 'fleet') return launch.readiness ? `${launch.readiness.home} of ${launch.readiness.ships} ships home` : '';
    const g = ((launch.charter && launch.charter.groups) || []).find((x: any) => x.key === s.group);
    return g ? `${g.params.filter((p: any) => p.state === 'signed').length} of ${g.params.length} signed` : '';
  };
  const sections: [string, string, string, string, string][] = CHARTER_SECTIONS.map((s) => [s.name, s.about, `/expeditions/charter/${s.slug}`, s.art, stand(s)]);
  return `<div class="harbours shipyardgrid chartercards">${sections.map(([name, about, href, art, standing], i) =>
    `<a class="${cardCls(true, 'card harbourcard shipyardcard')}" href="${esc(href)}">${artImg(art, 'cardart ship')}
      <div class="yardplate">
        <span class="yardnum">${String(i + 1).padStart(2, '0')}</span>
        <span class="yardrule" aria-hidden="true"></span>
        <span class="nm">${esc(name)}</span>
        <span class="job">${esc(about)}</span>
        ${standing ? `<span class="s">${esc(standing)}</span>` : ''}
        <span class="yardopen">open ${esc(name.toLowerCase())} →</span>
      </div></a>`).join('')}</div>`;
}

/** The charter's goals on the expeditions' own page (12 November, Justin: "this page
 *  /expeditions/expeditions should show also a summary of the goals and where we are to achieving them
 *  for the charter to be signed off. That's what the expeditions are for, is to get enough information
 *  to sign off the charter. Each charter is a full fleet version of Nothin up my sleeve"): the rows of
 *  the master charter counted by where they stand, then the goals that decide them — open ones first —
 *  each with the charter rows it settles and the reading so far. The bar, the fleet's own readings and
 *  what is carried are folded below: they do not hold a row of this charter. */
const GOAL_TONE: Record<string, string> = { done: 'good', partly: 'accent', open: '', dropped: '' };
const GOAL_PART: [string, string, string][] = [
  ['decides', 'Deciding the charter', 'a row of the master charter waits on it'],
  ['acceptance', 'The bar', 'a reading the fleet is judged on'],
  ['delivered', 'Delivered by the fleet', 'the reading only the fleet itself can give'],
  ['carried', 'Carried to the next expedition', 'not needed to sign this charter'],
  ['unassigned', 'No part yet', 'a goal the launch has not read into a part yet'],
];
const GROUP_SHORT: Record<string, string> = {
  'The ship': 'ship', 'The tokeniser': 'tokeniser', 'What it reads': 'reads',
  'The scaffold': 'scaffold', 'The training': 'training', 'The return leg (instruct ships)': 'return leg', 'The bar': 'bar',
};
const goalRank = (st: string): number => ({ partly: 0, open: 1, done: 2, dropped: 3 }[st] ?? 4);
const byGoal = (a: any, b: any): number =>
  goalRank(a.status) - goalRank(b.status)
  || String(a.expedition_name || a.expedition || '').localeCompare(String(b.expedition_name || b.expedition || ''))
  || String(a.goal_id).localeCompare(String(b.goal_id), undefined, { numeric: true });

export function goalSummaryHtml(launch: any): string {
  if (!launch) return '';
  const rows: { key: string; group: string; name: string; state: string }[] = [];
  for (const g of launch.charter?.groups || []) {
    for (const p of g.params || []) rows.push({ key: p.key, group: GROUP_SHORT[g.name] || String(g.name).toLowerCase(), name: p.name, state: p.state });
  }
  const paramOf = new Map(rows.map((x) => [x.key, x]));
  const count: Record<string, number> = { signed: 0, ready: 0, waiting: 0, drifted: 0 };
  for (const x of rows) count[x.state] = (count[x.state] || 0) + 1;
  const total = rows.length;
  const pct = (n: number): string => (total ? `${(100 * n) / total}%` : '0%');
  const parts: any[] = launch.parts || [];
  const blocking = parts.filter((p) => p.part === 'decides' && p.status !== 'done').length;

  const bar = `<div class="chartertally">
      <span><b>${count.signed}</b> of ${total} rows signed</span>
      <span><b>${count.ready}</b> ready to sign</span>
      <span><b>${count.waiting}</b> waiting on a goal</span>
      <span><b>${blocking}</b> deciding ${blocking === 1 ? 'goal' : 'goals'} still to settle</span>
    </div>
    <div class="phasebar charterbar" role="img" aria-label="${count.signed} of ${total} charter rows signed, ${count.ready} ready, ${count.waiting} waiting on a goal${count.drifted ? `, ${count.drifted} drifted` : ''}">
      <i class="signed" style="width:${pct(count.signed)}"></i><i class="ready" style="width:${pct(count.ready)}"></i><i class="waiting" style="width:${pct(count.waiting)}"></i>${count.drifted ? `<i class="drifted" style="width:${pct(count.drifted)}"></i>` : ''}
    </div>
    <div class="phaselegend charterlegend">
      <span><i class="signed"></i> signed <b>${count.signed}</b></span>
      <span><i class="ready"></i> ready to sign <b>${count.ready}</b></span>
      <span><i class="waiting"></i> waiting on a goal <b>${count.waiting}</b></span>
      ${count.drifted ? `<span><i class="drifted"></i> drifted <b>${count.drifted}</b></span>` : ''}
    </div>`;

  const goalRow = (p: any, withParts: boolean): string => {
    const groups = new Map<string, string[]>();
    for (const key of p.params || []) {
      const info = paramOf.get(key);
      if (!info) continue;
      const href = charterParamHref(key);
      const name = `<a href="${href}" title="${esc(key)} · ${esc(info.state)}">${esc(info.name)}</a>`;
      groups.set(info.group, [...(groups.get(info.group) || []), name]);
    }
    const decides = [...groups].map(([g, names]) => `<div><span class="s">${esc(g)} · </span>${names.join(', ')}</div>`).join('') || '<span class="s">carried from the draft</span>';
    const note = p.evidence || p.words || '';
    const why = p.why ? `<div class="s why">${esc(p.why)}</div>` : '';
    const exp = p.expedition ? `<a href="/expeditions/${encodeURIComponent(p.expedition)}">${esc(p.expedition_name || p.expedition)}</a>` : '';
    const third = withParts
      ? decides
      : `<span class="partname">${esc((GOAL_PART.find(([k]) => k === p.part) || [p.part, p.part])[1])}</span>`;
    return `<tr>
      <td><b>${esc(p.text)}</b><div class="s mono">${esc(p.goal_id)}${exp ? ` · ${exp}` : ''}</div>${why}</td>
      <td><span class="${pillCls(GOAL_TONE[p.status] || '')}">${esc(p.status || '–')}</span></td>
      <td class="decides">${third}</td>
      <td class="where">${note ? esc(cut(note, 240)) : '<span class="s">nothing written up yet</span>'}</td>
    </tr>`;
  };
  const groupRow = (title: string, note: string): string =>
    `<tr class="chartergroup"><th colspan="4" scope="colgroup">${esc(title)} <span class="s">${esc(note)}</span></th></tr>`;

  const deciding = parts.filter((p) => p.part === 'decides').sort(byGoal);
  const unsettled = deciding.filter((p) => p.status !== 'done');
  const settled = deciding.filter((p) => p.status === 'done');
  const head = `<thead><tr><th>goal</th><th>where it stands</th><th>charter rows</th><th>the reading so far</th></tr></thead>`;
  const decidingTable = deciding.length ? `<div class="scroll"><table class="goaltable chartersummary" data-nosort>${head}<tbody>
      ${unsettled.length ? groupRow(`Still to settle (${unsettled.length})`, 'a row of the master charter waits on these') + unsettled.map((p) => goalRow(p, true)).join('') : ''}
      ${settled.length ? groupRow(`Settled (${settled.length})`, 'their rows are ready, or already signed') + settled.map((p) => goalRow(p, true)).join('') : ''}
    </tbody></table></div>` : `<div class="${emptyCls()}">no goal decides a row of this charter yet</div>`;

  const rest = parts.filter((p) => p.part !== 'decides');
  const restTable = rest.length ? `<details class="archive goalrest">
      <summary>The bar, the fleet's own readings, and what is carried (${rest.length}) <span class="s">they do not hold a row of this charter: they judge the fleet or wait for the next expedition</span></summary>
      <div class="scroll"><table class="goaltable chartersummary rest" data-nosort>${head}<tbody>
        ${GOAL_PART.filter(([k]) => k !== 'decides').map(([k, title, note]) => {
          const list = rest.filter((p) => p.part === k).sort(byGoal);
          return list.length ? groupRow(`${title} (${list.length})`, note) + list.map((p) => goalRow(p, false)).join('') : '';
        }).join('')}
      </tbody></table></div>
    </details>` : '';

  const cta = `<p class="goalcta"><a href="/expeditions/charter">Open the master charter →</a> <span class="s">sign a row off there as its goals settle</span></p>`;

  return `${bar}${decidingTable}${restTable}${cta}`;
}

export function expeditionCardsHtml(exps: Expedition[], states: Record<string, string>, overview?: any, prep?: Record<string, any>): string {
  const ov: Record<string, any> = {};
  for (const e of (overview && overview.expeditions) || []) ov[e.key] = e;
  const cards = exps.map((v) => {
    const o = ov[v.key] || {};
    const valid = v.runs.filter((r) => !r.set_aside).length;
    const found = v.learned || starHeadline(v) || '';
    const ships = (v.ships || []).length;
    const queued = Number(o.queued || 0);
    const counts = `${Number(o.at_sea || 0)} at sea · ${Number(o.finished || 0)} home · ${Number(o.failed || 0)} failed · ${queued} queued`;
    // its part in the launch (12 November): research or test voyages, the charter rows it decides, and how
    // many of its goals still stand between the charter and a signature
    const pr = prep && prep[v.key];
    const decides: string[] = (pr && pr.decides) || [];
    const prepLine = pr ? `<div class="foot prepline"><span>${esc(pr.kind)}${decides.length ? ` · <span title="${esc(decides.join('; '))}">decides ${decides.length} charter row${decides.length === 1 ? '' : 's'}</span>` : ' · decides no charter row'}</span><span class="${pr.blocking ? 'blocking' : ''}">${pr.blocking ? `${pr.blocking} goal${pr.blocking === 1 ? '' : 's'} before the launch` : 'nothing before the launch'}</span></div>` : '';
    return `<a class="${cardCls(true, 'card expcard')}" href="/expeditions/${esc(v.key)}" data-expedition="${esc(v.key)}">
      ${artImg(`exp-${v.key}`, 'cardart ship')}
      <div class="top"><span class="preset">${esc(v.name)}</span>${expPill(states[v.key], v)}</div>
      <div class="goal">${esc(v.goal)}</div>
      <div class="ov" title="${esc(found)}">${esc(cut(found, 240) || 'nothing written up yet: what it found is written when it comes home')}</div>
      <div class="foot"><span>${esc(v.fleet || '')}${v.preset ? ` · ${esc(v.preset)}` : ''}</span><span>${valid} of ${v.stop.max_runs} voyages</span></div>
      <div class="foot"><span class="expcounts">${counts} · ${ships} ship${ships === 1 ? '' : 's'}</span></div>
      ${prepLine}
    </a>`;
  }).join('');
  return cards ? `<div class="cards expcards">${cards}</div>` : `<div class="${emptyCls()}">no expeditions yet</div>`;
}

// ---- the plan and the waters each ship sails in (#waters; thorp/dash/waters.py, /api/waters)
const LANE_TONE: Record<string, string> = { mac: 'blue', vast: 'accent' };
const mins = (m: number | null | undefined): string => (m == null ? '' : m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1)} h`);
const big2 = (n: number | null | undefined): string => (n == null ? '' : n >= 1e9 ? `${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `${Math.round(n / 1e6)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n));
const laneChip = (lane: string, d: any): string => `<span class="${pillCls(LANE_TONE[lane] || '')} lanechip" title="${esc(d.lanes[lane].where)}: ${esc(d.lanes[lane].how)}">${esc(String(d.lanes[lane].name).toLowerCase())}</span>`;

function planTraining(p: any): string {
  const t = p.training; if (!t) return '';
  const len = t.steps ? `<b>${Number(t.steps).toLocaleString()}</b> steps × ${big2(t.batch_tokens)} tokens` : `${big2(t.batch_tokens)} tokens a step <span class="s">(steps known once it sails)</span>`;
  const opt = `lr ${t.lr}${t.schedule ? `, ${esc(t.schedule)}` : ''}${t.warmup ? `, ${t.warmup} warm-up` : ''} · ${esc(t.positions || '')} · ${esc(t.backend)}`;
  const ph = (t.phases || []).length ? `<ul class="planlist">${t.phases.map((x: string) => `<li>${esc(x)}</li>`).join('')}</ul>` : '<div class="s">the language-model loss alone</div>';
  return `<div>${len}</div><div class="s">${opt}</div>${ph}`;
}
function planMaterial(p: any): string {
  const m = p.material; if (!m) return '';
  const books = (m.stages || []).reduce((a: number, s: any) => a + (s.books || 0), 0);
  const head = `<b title="${esc(m.aim || '')}">${esc(m.fitout || 'no fitout')}</b>${m.variation ? ` <span class="${pillCls('')}">~ ${esc(m.variation)}</span>` : ''}`;
  const size = `<div class="s">${books ? `${books.toLocaleString()} books` : ''}${m.tokens_per_pass ? ` · about ${big2(m.tokens_per_pass)} tokens a pass` : ''}${m.clean ? ` · ${esc(m.clean)}` : ''}${m.opt_in ? ' · beyond the stores (approved)' : ''}</div>`;
  const st = (m.stages || []).length > 1 || (m.stages || []).some((s: any) => s.name !== 'the reading')
    ? `<ul class="planlist">${m.stages.map((s: any) => `<li>${esc(s.name)}: <span class="mono">${esc(String(s.recipe || '').split('/').pop())}</span>, ${s.books ?? '?'} books × ${s.passes}</li>`).join('')}</ul>`
    : (m.stages || []).map((s: any) => `<div class="s"><span class="mono">${esc(String(s.recipe || '').split('/').pop())}</span> read ${s.passes} time${s.passes === 1 ? '' : 's'}</div>`).join('');
  return head + size + st;
}
function planWhat(p: any): string {
  if (p.kind === 'spec') {
    const title = String(p.ship || p.name).replace(/^Fitout: /, '');
    const ex = p.expedition === 'ogden' && p.material && p.material.fitout ? esc(p.material.fitout)
      : p.expedition ? `<a href="/expeditions/${esc(p.expedition)}">${esc(p.expedition_name || p.expedition)}</a>` : '';
    const prog = p.at_sea && p.step != null && p.training && p.training.steps ? ` · step ${Number(p.step).toLocaleString()} of ${Number(p.training.steps).toLocaleString()} (${Math.round((100 * p.step) / p.training.steps)}%)` : '';
    return `<div class="plantitle"><a href="${shipHash(p.name)}">${esc(title)}</a>${p.missing ? ` <span class="${pillCls('bad')}">no spec</span>` : ''}</div>
      <div class="s">${ex}${ex ? ' · ' : ''}${esc(p.preset || '')}${p.seed != null ? ` · seed ${p.seed}` : ''} · <span class="mono">${esc(p.name)}</span>${prog}</div>
      ${p.goal ? `<div class="plangoal" title="${esc(p.goal)}">${esc(p.goal)}</div>` : ''}
      <details class="plandet"><summary>training plan and material</summary><div class="plandetgrid"><div><div class="s"><b>training plan</b></div>${planTraining(p)}</div><div><div class="s"><b>training material</b></div>${planMaterial(p)}</div></div></details>`;
  }
  if (p.kind === 'hold') return `<b>${esc(p.name)}</b> <span class="${pillCls(p.hold && p.hold.held ? 'accent' : 'good')}">${p.hold && p.hold.held ? 'held' : 'lifted'}</span>${p.hold && p.hold.note ? `<div class="plangoal">${esc(p.hold.note)}</div>` : ''}`;
  if (p.kind === 'wait') return `<b>${esc(p.name)}</b>`;
  return `<span class="s">a step:</span> <span class="mono" title="${esc(p.text)}">${esc(p.name)}</span>`;
}
function laneCard(lane: string, d: any): string {
  const L = d.lanes[lane], sea = L.at_sea;
  const now = sea ? `<div class="ovsea"><span class="${pillCls('running')}">at sea</span> ${sea.kind === 'spec' ? `<a href="${shipHash(sea.name)}" class="mono">${esc(sea.name)}</a>` : `<span class="mono" title="${esc(sea.text)}">${esc(sea.name)}</span>`}
      <div class="s">since ${esc(String(sea.since || '').slice(11, 16))}${sea.left_min != null ? ` · about ${mins(sea.left_min)} left` : sea.elapsed_min != null ? ` · ${mins(sea.elapsed_min)} so far, no time of its own yet` : ''}</div></div>` : '';
  const ships = (L.ships || []).map((s: any) => `<div class="ovsea"><span class="${pillCls('running')}">at sea</span> <a href="${shipHash(s.name)}" class="mono">${esc(s.name)}</a>
      <div class="s">${esc(s.gpu)} at $${Number(s.dph).toFixed(3)}/h · since ${esc(String(s.since).slice(11, 16))} · $${Number(s.cost).toFixed(2)} so far of a $${Number(s.quote || 0).toFixed(2)} quote · about ${mins(s.left_min)} left${s.by_queue ? '' : ' · <i>sailed by hand, outside the queue</i>'}</div></div>`).join('');
  const idle = !sea && !ships ? `<div class="s">in port${L.queued ? '' : ': nothing queued for these waters'}</div>` : '';
  const w = L.week;
  const spend = w ? `<div class="spend" title="S5's terms: $${w.voyage_budget} a voyage, $${w.budget} a week (Monday to Sunday, UTC), ${w.max_out} ship out at a time"><div class="spendbar"><span style="width:${Math.min(100, (100 * (w.spent || 0)) / (w.budget || 1))}%"></span></div>
      <div class="s">this week <b>$${(w.spent ?? 0).toFixed(2)}</b> of $${w.budget} · $${w.voyage_budget} a voyage · ${w.max_out} ship out at a time${L.key ? '' : ' · <span class="bad">no Vast.ai key</span>'}</div></div>` : '';
  const steps = L.queued - L.voyages;
  return `<div class="watercard ${lane}"><div class="wtop">${laneChip(lane, d)} <b>${esc(L.where)}</b> <span class="s">${esc(L.how)}</span></div>
    ${now}${ships}${idle}
    <div class="ovq"><b>${L.voyages}</b> voyage${L.voyages === 1 ? '' : 's'} and ${steps} step${steps === 1 ? '' : 's'} to sail · clear ${L.at_least ? 'no sooner than' : 'about'} <b>${esc(L.clear_at)}</b></div>${spend}</div>`;
}
export function watersHtml(d: any): string {
  const finishAt = (p: any): string => {
    if (p.kind !== 'spec') return '';
    const start = p.at_sea ? new Date() : new Date(Date.now() + (p.starts_in_min ?? 0) * 60000);
    if (p.est_min == null) return p.at_sea ? '' : 'no time yet';
    const done = new Date(start.getTime() + p.est_min * 60000);
    return `${String(done.getHours()).padStart(2, '0')}:${String(done.getMinutes()).padStart(2, '0')}`;
  };
  const when = (p: any): string => p.at_sea ? `<span class="${pillCls('running')}">at sea</span><div class="s">since ${esc(String(p.since || '').slice(11, 16))}${p.left_min != null ? `, about ${mins(p.left_min)} left` : ''}</div>`
    : `${p.at_least ? '≥ ' : '≈ '}${esc(p.starts_at)}<div class="s">${p.est_min != null ? (p.est_is_max ? `up to ${mins(p.est_min)}` : mins(p.est_min)) : 'no time yet'}</div>`;
  const ships = d.plan.filter((p: any) => p.kind === 'spec').length;
  const rows = d.plan.map((p: any) => `<tr class="plan-${p.kind}${p.at_sea ? ' atsea' : ''}${p.waits_for ? ' waiting' : ''}"><td class="s">${p.n ?? ''}</td>
      <td class="plantime">${when(p)}</td><td>${laneChip(p.lane, d)}</td>
      <td class="planwhat">${p.kind === 'spec' ? `<span class="mono">${esc(p.preset || p.name || '')}</span>` : ''}</td>
      <td class="s">${finishAt(p)}</td>
      <td>${p.kind === 'spec' && p.sop ? `<span class="${pillCls('accent')}">v${esc(p.sop)}</span>` : '<span class="s">–</span>'}</td>
      <td class="s">${p.waits_for ? `<span class="${pillCls('accent')}">waits</span> ${esc(p.waits_for)}` : ''}</td></tr>`).join('')
    || `<tr><td colspan="6" class="${emptyCls(true)}">the queue is empty</td></tr>`;
  return `<div class="waters">${laneCard('mac', d)}${laneCard('vast', d)}</div>
    <div class="ovq"><b>${ships}</b> ship${ships === 1 ? '' : 's'} in the plan, at sea first, then the queue in its order; open a ship's <i>training plan and material</i> for how it trains and what it reads</div>
    <div class="scroll"><table data-nosort class="plantable"><thead><tr><th>#</th><th title="about when it sails (≥ where a line ahead of it in its waters has no time yet), and for how long">sails</th><th>waters</th><th>ship</th><th title="the SOP the voyage is built to">SOP</th><th title="when it is expected to dock: the line's start plus how long a voyage like it takes on this Mac">finishes</th><th>waits for</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="s">as of ${esc(d.now)}</div>`;
}

// ---- the queue at a glance (#expoverview; /api/expeditions/overview)
const PALETTE_VARS = ['var(--blue)', 'var(--accent)', 'var(--good)', 'var(--bad)', 'var(--c5)', 'var(--c6)', 'var(--c7)', 'var(--c8)', 'var(--c9)', 'var(--c10)', 'var(--c11)', 'var(--c12)'];
export function overviewHtml(d: any): string {
  const q = d.queue || {}, sea = d.at_sea || [], ex = d.expeditions || [];
  const helm = d.helm ? `<div class="ovsea"><span class="${pillCls('good')}">at the helm</span> <b>${esc(d.helm.name || '')}</b> <span class="s">${esc(d.helm.kind || '')}${d.helm.pid ? ` · pid ${d.helm.pid}` : ''}${d.helm.since ? ` · since ${esc(String(d.helm.since).slice(11, 16))}` : ''}</span></div>`
    : '<div class="ovsea s">no helm yet: the voyage at sea was launched before the helm (S2) existed, so it shows from the ledger</div>';
  const name = (k: string): string => (ex.find((e: any) => e.key === k) || {}).name || k;
  const atSea = sea.length ? sea.map((r: any) => `<div class="ovsea"><span class="${pillCls('running')}">at sea</span> <a href="${shipHash(r.name)}"><b>${esc(r.name)}</b></a>
      <div class="s">${esc(r.ship || '')}${r.expedition ? ` · <a href="/expeditions/${esc(r.expedition)}">${esc(name(r.expedition))}</a>` : ''}${r.started ? ` · since ${esc(String(r.started).slice(11, 16))}` : ''}</div></div>`).join('') : '<div class="s">no voyage at sea</div>';
  const bar = `<div class="ovbar" title="the queue: ${q.voyages} voyages, about ${q.hours_left} hours">${ex.filter((e: any) => e.queued).map((e: any, i: number) => `<span style="flex-grow:${e.queued};background:${PALETTE_VARS[i % PALETTE_VARS.length]}" title="${esc(e.name)}: ${e.queued} queued, next at #${e.next_in_queue}"></span>`).join('')}</div>
    <div class="ovq"><b>${q.voyages ?? '–'}</b> voyages to sail · about <b>${q.hours_left ?? '–'}</b> hours${q.voyages_without_a_time ? ` <span class="s">(${q.voyages_without_a_time} with no time yet, so more)</span>` : ''}${q.steps ? ` · ${q.steps} queue command${q.steps === 1 ? '' : 's'}` : ''}</div>
    ${(q.lints || []).length ? `<div class="${alertCls('no')}">${q.lints.map((l: string) => esc(l)).join('<br>')}</div>` : ''}`;
  const rows = ex.map((e: any) => `<tr><td><span class="ovsw" style="background:${e.queued ? PALETTE_VARS[ex.filter((x: any) => x.queued).indexOf(e) % PALETTE_VARS.length] : 'transparent'}"></span> ${e.key === '(no expedition)' ? `<i>${esc(e.name)}</i>` : `<a href="/expeditions/${esc(e.key)}"><b>${esc(e.name)}</b></a>`}</td>
      <td>${statePill(e.status, e.declared)}</td><td>${e.at_sea ? `<span class="${pillCls('running')}">${e.at_sea} at sea</span>` : ''}</td>
      <td>${e.queued || '–'}</td><td>${e.next_in_queue ? `#${e.next_in_queue}` : '–'}</td><td>${e.finished || '–'}</td><td>${e.failed ? `<span class="bad">${e.failed}</span>` : '–'}</td></tr>`).join('');
  // the page is the SOPs and nothing else (9 November, Justin: "remove at a glance section and every
  // voyage section ... we'll navigate to those pages to explore more"): what is at sea is on the card.
  return sopCardsHtml(d);
}

// ---- the queue as a table (#queuetable; /api/queue)
const sailsIn = (m: number | null | undefined, atLeast: boolean): string => (m == null ? '' : (atLeast ? '≥ ' : '') + (m < 1 ? 'next' : m < 90 ? `${m} min` : m < 48 * 60 ? `${(m / 60).toFixed(1)} h` : `${(m / 1440).toFixed(1)} days`));
// The queue's clock time, in the reader's own timezone: the estimate is the sum of the mean wall
// times of the voyages ahead. A day suffix appears when it is not today; ≥ marks a line whose own
// start is a lower bound (a voyage ahead has no time yet).
const clock = (d: Date): string => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
const startsAt = (r: any): string => {
  if (r.status === 'at sea') return r.started ? `<span class="s">since ${clock(new Date(r.started))}</span>` : '<span class="s">at sea</span>';
  if (r.starts_in_min == null) return '<span class="s">no time yet</span>';
  const d = new Date(Date.now() + Number(r.starts_in_min) * 60000);
  const day = d.toDateString() === new Date().toDateString() ? '' : ` ${d.toLocaleDateString(undefined, { weekday: 'short' })}`;
  return `${r.at_least ? '≥ ' : ''}<b>${clock(d)}</b>${day ? `<span class="s">${day}</span>` : ''}`;
};
/** A step's length on its row (12 November): about how long it takes and where that came from, an upper bound
 *  said as one, and for a step at sea what it has left. */
const stepLength = (r: any): string => {
  if (r.est_min == null) return 'no time of its own yet: the lines behind it start no sooner than shown';
  const len = `${r.est_is_max ? 'up to ' : 'about '}${mins(Number(r.est_min))}`;
  const left = r.status === 'at sea' && r.left_min != null ? ` · about ${mins(Number(r.left_min))} left` : '';
  return `${len} · ${esc(r.est_source || '')}${left}`;
};
/** The queue names the voyage, not only its class (10 November: three 300k lines read as "300k" and
 *  nothing else). The goal is the spec's question, cut to one line; the full text is in the title. */
const queueGoal = (r: any): string => {
  const t = String(r.goal || r.experiment || '').replace(/\s+/g, ' ').trim();
  return t.length > 90 ? t.slice(0, 87) + '…' : t;
};
/** How far a voyage has come, as the card reads it: its training step of the steps its schedule sets,
 *  from the row's own `detail`. A line that has not sailed is 0%: there is nothing to read yet. */
const queueDone = (r: any): { step: number; total: number | null; tokens: number | null; tokensTotal: number | null } | null => {
  const det = r.detail || {}, rd = det.readings || {}, sch = det.schedule || {}, opt = det.optim || {};
  const step = rd.step != null ? Number(rd.step) : sch.step != null ? Number(sch.step) : null;
  const total = opt.steps != null ? Number(opt.steps) : sch.total != null ? Number(sch.total) : null;
  if (step == null || !(step > 0)) return null;
  const bt = opt.batch_tokens != null ? Number(opt.batch_tokens) : null;
  return { step, total: total != null && total > 0 ? total : null, tokens: rd.tokens_seen != null ? Number(rd.tokens_seen) : null,
    tokensTotal: total != null && total > 0 && bt ? total * bt : null };
};
const compact = (n: number): string => (n >= 1e9 ? `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(Math.round(n)));
const queueComplete = (r: any): string => {
  const q = queueDone(r);
  if (!q) return '<span class="s" title="not started: it sails when the lines ahead of it are home">0%</span>';
  const { step, total } = q;
  if (total == null) return `<span class="s" title="its step total is known once it sails">step ${Math.round(step).toLocaleString()}</span>`;
  const done = Math.max(0, Math.min(100, (100 * step) / total));
  const pct = done < 1 ? done.toFixed(1) : done.toFixed(0);
  // a ship at sea says where it is in steps and in the text it has read (13 November, Justin)
  const where = r.status === 'at sea'
    ? `<div class="qprogsub">step ${Math.round(step).toLocaleString()} / ${Math.round(total).toLocaleString()}${q.tokens != null && q.tokensTotal ? ` · ${compact(q.tokens)} / ${compact(q.tokensTotal)} tokens` : ''}</div>` : '';
  return `<div class="qprog" title="step ${Math.round(step).toLocaleString()} of ${Math.round(total).toLocaleString()} · ${pct}% complete"><progress class="qvbar qminibar" max="${total}" value="${step}" aria-label="voyage progress"></progress><b>${pct}%</b></div>${where}`;
};
/** The day a clock time falls on, when it is not today. */
const dayOf = (d: Date): string => (d.toDateString() === new Date().toDateString() ? '' : ` ${d.toLocaleDateString(undefined, { weekday: 'short' })}`);
/** When a voyage at sea is expected home, and by what: its own pace, or the hire's quote while it has none; and a
 *  flag where the quote and the pace disagree by a quarter (13 November: the 50m was quoted 5 h and ran 20). */
const homeAt = (r: any): string => {
  if (r.left_min == null) return '';
  const d = new Date(Date.now() + Number(r.left_min) * 60000);
  const ab = r.abroad || {};
  const how = ab.paced ? 'by its pace' : ab.quote_min != null ? "by the hire's quote" : esc(String(r.est_source || ''));
  let flag = '';
  if (ab.paced && ab.quote_min && r.est_min && (r.est_min / ab.quote_min > 1.25 || r.est_min / ab.quote_min < 0.8)) {
    flag = ` <span class="${pillCls('bad')}" title="the hire was quoted ${mins(ab.quote_min)}; at its pace so far the voyage takes ${mins(r.est_min)}">quoted ${mins(ab.quote_min)}</span>`;
  }
  return `<div class="s qhome" title="${esc(String(r.est_source || ''))}">home <b>${clock(d)}</b>${dayOf(d)} · ${mins(Number(r.left_min))} left · ${how}${flag}</div>`;
};
/** What a hired ship costs, on its row. */
const hireLine = (r: any): string => {
  const ab = r.abroad;
  if (!ab) return '';
  const bits = [ab.gpu ? esc(ab.gpu) : 'hiring', ab.dph != null ? `$${Number(ab.dph).toFixed(2)}/h` : '',
    ab.spent != null ? `$${Number(ab.spent).toFixed(2)} so far${ab.projected != null ? `, about $${Number(ab.projected).toFixed(2)} at its finish` : ''}` : '',
    ab.quote_cost != null && ab.paced ? `quoted $${Number(ab.quote_cost).toFixed(2)}` : ''].filter(Boolean);
  return `<div class="s qhire" title="the Vast.ai hire: its dollars an hour, what it has run up since the hire, and what it will have at its finish">${bits.join(' · ')}</div>`;
};
type QueueView = { kind?: string; text?: string; open?: Set<string> };
const queueCat = (r: any): string => (r.kind === 'voyage' ? 'voyage' : r.what === 'investigation' ? 'investigation' : r.what === 'reading' ? 'reading' : 'other');
const stepPrefix = (r: any): string => String(r.name || '').split(':')[0].trim();
/** The rows the page shows under a filter (13 November): by kind, and by text over the name, goal and expedition. */
export function queueMatches(d: any, v: QueueView = {}): number[] {
  const kind = v.kind || 'all', text = (v.text || '').trim().toLowerCase();
  return (d.rows || []).map((r: any, i: number) => ({ r, i })).filter(({ r }: any) => {
    if (kind !== 'all' && queueCat(r) !== kind) return false;
    if (!text) return true;
    return [r.name, r.goal, r.experiment, r.goal_id, r.expedition_name, r.serves?.text, r.what].join(' ').toLowerCase().includes(text);
  }).map(({ i }: any) => i);
}
export function queueRowsHtml(d: any, rungs: Rung[], view: QueueView = {}): string {
  // the at-sea voyages are the first of the queue: number them too (10 November, Justin: "I'd be
  // expecting the at sea ships to still have a number"), and let the number run on through the file.
  const all: any[] = d.rows || [];
  const keep = new Set(queueMatches(d, view));
  const filtered = (view.kind && view.kind !== 'all') || !!(view.text || '').trim();
  // the SOP every row shares is not worth a column: a row's SOP shows only where it differs (13 November)
  const sops = all.map((r) => r.sop).filter(Boolean);
  const commonSop = sops.sort((a, b) => sops.filter((x) => x === b).length - sops.filter((x) => x === a).length)[0];
  const stepRow = (r: any, i: number): string => {
    const intel = r.kind === 'intelligence';
    const what = ({ investigation: 'an investigation', reading: 'a reading', upkeep: 'upkeep', intelligence: 'the intelligence audit' } as Record<string, string>)[r.what] || 'a step';
    const label = intel
      ? `<span class="qintelbadge" title="S4 intelligence: a scheduled Liberty Machine task, not a voyage">S4</span> <b>${esc(r.name)}</b>`
      : `${what}: <b>${esc(r.name)}</b>`;
    const goal = r.goal_id
      ? ` <span class="${pillCls('accent')}" title="the goal this ${intel ? 'task' : 'step'} serves">${esc(r.goal_id)}</span>`
      : intel || r.what === 'upkeep' || r.status === 'at sea' ? '' : ` <span class="${pillCls('bad')}" title="every line serves an expedition's goal: thorp queue goal LINE --goal EXPEDITION:N">no goal</span>`;
    const cadence = intel ? ' · a turn of the Liberty Machine planning cycle' : '';
    return `<tr class="qstep${intel ? ' qintel' : ''}${r.status === 'at sea' ? ' sel' : ''}" data-qi="${i}" tabindex="0" aria-label="show the card for ${esc(r.name)}" title="show ${intel ? 'this Liberty Machine task' : 'this step'}'s card"><td class="s">${i + 1}</td><td colspan="3" class="s">${r.status === 'at sea' ? '' : intel ? '↳ scheduled: ' : '↳ then '}${label}${goal}<div class="s">${stepLength(r)}${cadence}</div></td>
      <td class="s" title="${r.est_min == null ? 'no time yet' : `about ${Math.round(r.est_min)} min · ${esc(r.est_source || '')}`}">${startsAt(r)}</td>
      <td class="s">${r.status === 'at sea' ? `<span class="${pillCls('running')}">at sea</span>` : sailsIn(r.starts_in_min, !!r.at_least)}</td></tr>`;
  };
  const voyageRow = (r: any, i: number): string => {
    const rung = rungs.find((x) => x.preset === r.preset);
    const label = `<span class="mono">${esc(r.preset || r.name)}</span>`;
    const train = rung ? ` <a class="s mono" href="${modelHash(rung, 'training')}" title="open the ${esc(r.preset)} class's training page">${label} ↗</a>` : '';
    const sop = r.sop && r.sop !== commonSop ? ` <span class="${pillCls('accent')}" title="this voyage's SOP differs from the rest of the queue's v${esc(commonSop || '')}">v${esc(r.sop)}</span>` : '';
    const goal = r.goal_id
      ? `<span class="${pillCls('accent')}" title="the goal this voyage serves">${esc(r.goal_id)}</span>${r.serves?.text ? `<div class="s qserves" title="${esc(r.serves.text)}">${esc(r.serves.text)}</div>` : ''}`
      : `<span class="${pillCls('bad')}" title="every line serves an expedition's goal: thorp queue goal LINE --goal EXPEDITION:N">no goal</span>`;
    return `<tr data-qi="${i}" tabindex="0" aria-label="show the card for ${esc(r.name)}" title="show this voyage's card"${r.status === 'at sea' ? ' class="sel"' : ''}><td class="s">${i + 1}</td>
      <td><b>${esc(r.name)}</b>${r.lane && r.lane !== 'mac' ? ` <span class="${pillCls('blue')}" title="sails on the ${esc(r.lane)} lane">${esc(r.lane)}</span>` : ''}${r.purser?.waters === 'foreign' && !r.purser.applied ? ` <span class="${pillCls('')}" title="${esc(r.purser.reason || '')}">purser: abroad</span>` : ''}${sop}${r.missing ? ` <span class="${pillCls('bad')}">no spec</span>` : ''}${train}<div class="s" title="${esc(r.goal || '')}">${esc(queueGoal(r))}</div>${hireLine(r)}</td>
      <td class="qgoalcell">${goal}</td>
      <td class="s qcomplete">${queueComplete(r)}</td>
      <td class="s" title="${r.est_min == null ? 'no time yet' : `about ${Math.round(r.est_min)} min · ${esc(r.est_source || '')}`}">${startsAt(r)}</td>
      <td class="s">${r.status === 'at sea' ? `<span class="${pillCls('running')}">at sea</span>${homeAt(r)}` : sailsIn(r.starts_in_min, !!r.at_least)}</td></tr>`;
  };
  const out: string[] = [];
  for (let i = 0; i < all.length; i++) {
    if (!keep.has(i)) continue;
    const r = all[i];
    if (r.kind === 'step' && r.status !== 'at sea' && !filtered) {
      // a chain of like steps (13 IFEval readings) is one line that opens: its members are the same step on other models
      let j = i;
      while (j + 1 < all.length && all[j + 1].kind === 'step' && all[j + 1].status !== 'at sea' && all[j + 1].what === r.what && stepPrefix(all[j + 1]) === stepPrefix(r)) j++;
      const n = j - i + 1;
      if (n >= 4) {
        const key = String(i), open = !!view.open?.has(key);
        const last = all[j];
        const total = all.slice(i, j + 1).reduce((s, x) => s + (Number(x.est_min) || 0), 0);
        const end = last.starts_in_min != null && last.est_min != null ? new Date(Date.now() + (Number(last.starts_in_min) + Number(last.est_min)) * 60000) : null;
        out.push(`<tr class="qgroup" data-qg="${key}" tabindex="0" role="button" aria-expanded="${open}" aria-label="${open ? 'hide' : 'show'} the ${n} ${esc(stepPrefix(r))} steps" title="${open ? 'hide' : 'show'} these ${n} steps"><td class="s">${i + 1}–${j + 1}</td><td colspan="3" class="s"><span class="qcaret">${open ? '▾' : '▸'}</span> ↳ then ${n} ${esc(r.what === 'reading' ? 'readings' : r.what === 'investigation' ? 'investigations' : 'steps')}: <b>${esc(stepPrefix(r))}</b> <span class="s">about ${mins(total)} of sailing in all</span></td>
          <td class="s">${startsAt(r)}${end ? ` <span class="s">to ${clock(end)}</span>` : ''}</td><td class="s">${sailsIn(r.starts_in_min, !!r.at_least)}</td></tr>`);
        if (open) for (let k = i; k <= j; k++) out.push(stepRow(all[k], k));
        i = j;
        continue;
      }
    }
    out.push(r.kind === 'voyage' ? voyageRow(r, i) : stepRow(r, i));
  }
  return out.join('') || `<tr><td colspan="6" class="${emptyCls(true)}">${filtered ? 'nothing in the queue matches' : 'the queue is empty'}</td></tr>`;
}

/** A voyage's pins as one strip: a cell a layer, each card a chip in the layer it is taught (the queue's
 *  card and the at-sea card draw the same strip). */
export function pinsStripHtml(pins: { card?: string; layer?: number }[], layers: number): string {
  const by: Record<number, string[]> = {};
  (pins || []).forEach((h) => {
    const L = Number(h.layer);
    if (!Number.isFinite(L)) return;
    (by[L] || (by[L] = [])).push(String(h.card || '?'));
  });
  return Array.from({ length: Math.max(0, layers) }, (_, L) => {
    const cs = by[L] || [];
    return `<span class="pincell${cs.length ? ' used' : ''}" title="layer ${L}: ${cs.length ? esc(cs.join(', ')) : 'free'}">${cs.map((c) => `<i>${esc(c)}</i>`).join('')}<b>L${L}</b></span>`;
  }).join('');
}

// ---- every run of the expedition (the Runs tab): the finished arms, not only the ones at sea
export function runsTableHtml(v: Expedition | null): string {
  if (!v) return '<div class="s">reading the expedition…</div>';
  const runs = (v.runs || []).filter((r) => !r.set_aside);
  if (!runs.length) return '<div class="s">no runs for this expedition yet</div>';
  const lit = (r: Run): number => (r.stars || []).filter((s: StarRead) => s.latest != null && s.threshold != null && s.latest >= s.threshold).length;
  const rows = runs.map((r) => {
    const key = String(r.ship_key || r.name);
    const name = `<a href="${shipHash(key)}"><b>${esc(r.name)}</b></a>`;
    const ship = `<span class="s">${esc(String(r.ship_name || r.ship || ''))}</span>`;
    const size = esc(String(r.size || r.preset || ''));
    const tone = r.status === 'finished' ? 'good' : r.status === 'running' ? 'running' : r.status === 'queued' ? '' : 'bad';
    const status = r.status ? `<span class="${pillCls(tone)}">${esc(r.status)}</span>` : '–';
    const ft = r.ft_en == null ? '<span class="s">–</span>' : Number(r.ft_en).toFixed(2);
    const tokens = r.tokens_seen ? big(r.tokens_seen) : '<span class="s">–</span>';
    const stars = `${lit(r)}/${(r.stars || []).length}`;
    return `<tr><td>${name}</td><td>${ship}</td><td>${size}</td><td>${status}</td><td>${ft}</td><td>${tokens}</td><td>${stars}</td></tr>`;
  }).join('');
  return `<div class="scroll"><table id="expruns" class="clickable"><thead><tr><th>arm</th><th>ship</th><th>size</th><th>status</th><th>Forgotten Tomes</th><th>tokens</th><th>stars lit</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// ---- one expedition's header, outcomes and levers
export function voyageOverHtml(v: Expedition, rungs: Rung[]): string {
  const valid = v.runs.filter((r) => !r.set_aside);
  return [
    ['fleet', esc(v.fleet || '–')], ['class', classLink(rungs, v.preset)],
    ['bound for', esc((v.stars || []).map((k) => STAR_LABEL[k] || k).join(', ') || '–')], ['ships', String((v.ships || []).length)],
    ['runs', `${valid.length} of ${v.stop.max_runs}${v.runs.length > valid.length ? ` (${v.runs.length - valid.length} set aside)` : ''}`],
    ['stop rule', esc(v.stop.about || '')], ['status', esc(v.status)],
  ].map(([k, val]) => `<div><div class="k">${k}</div><div>${val}</div></div>`).join('');
}
export function planHtml(v: Expedition): string {
  const steps = v.plan || [];
  return steps.map((p) => `<li class="planstep ${p.kind === 'ship' ? 'ship' : 'investigation'}">
      <div class="pphead"><b>${p.n}. ${esc(p.name)}</b><span class="${pillCls(p.kind === 'ship' ? 'accent' : 'blue')}">${esc(p.kind)}</span></div>
      ${p.detail ? `<div class="s">${esc(p.detail)}</div>` : ''}
      ${p.queue ? `<div class="ppmeta mono">${esc(p.queue)}</div>` : ''}
    </li>`).join('');
}

export function outcomesRowsHtml(v: Expedition): string {
  return (v.outcomes || []).map((o) => `<tr><td>${esc(o.about)}</td><td class="mono">${esc(o.metric)}</td><td>${esc(o.better || '')}</td></tr>`).join('');
}
export function leversRowsHtml(v: Expedition): string {
  return (v.levers || []).map((l) => `<tr><td class="mono">${esc(l.key)}</td>
    <td>${l.fixed ? 'fixed' : l.choices && l.choices.length ? esc(l.choices.join(', ')) : `${l.low ?? '–'} to ${l.high ?? '–'}`}</td><td>${esc(l.about || '')}</td></tr>`).join('');
}

// ---- the ships, and the Forgotten Tomes score and first light panels (Fleet tab)
export function fleetShipsHtml(v: Expedition): { head: string; body: string; starKeys: string[]; scored: boolean; light: boolean; by: string } {
  const starKeys = v.stars && v.stars.length ? v.stars : [...new Set(v.runs.flatMap((r) => (r.stars || []).map((x) => x.star)))];
  const vships = v.ships && v.ships.length && typeof v.ships[0] === 'object' ? v.ships : [];
  const head = `<tr><th>ship</th><th>fitout</th><th>voyages</th><th>Forgotten Tomes (mean)${infoChip(FT_HELP)}</th>
    ${starKeys.map((k) => `<th>${esc(STAR_LABEL[k] || k)}</th>`).join('')}</tr>`;
  const body = vships.length ? vships.map((x) => `<tr data-ship="${esc(x.key)}">
    <td><b>${esc(x.name)}</b></td><td class="s">${esc(x.subtitle)}</td><td data-sort="${x.sailings.length}">${x.sailings.length}</td><td>${fmt(x.ft_en_mean)}</td>
    ${starKeys.map((k) => { const st = (x.stars || {})[k] || {};
      return st.lit ? `<td data-sort="${st.soonest}">lit by ${st.lit} of ${x.sailings.length} · soonest step ${st.soonest}</td>`
        : st.lit_shared ? `<td data-sort="${st.soonest_shared}" title="the best layer's two strongest heads together">lit shared by ${st.lit_shared} of ${x.sailings.length} · soonest step ${st.soonest_shared}</td>`
        : st.best != null ? `<td data-sort="" class="s" title="not lit yet; the best so far">best ${fmt(st.best)}</td>` : '<td>–</td>'; }).join('')}</tr>`).join('')
    : `<tr><td colspan="${4 + starKeys.length}" class="${emptyCls(true)}">no ships have sailed on this expedition yet</td></tr>`;
  const scored = v.runs.map((r, i) => ({ r, i: i + 1 })).filter((p) => p.r.ft_en != null && !p.r.set_aside);
  let by = 'passes';
  if (scored.length) {
    const fields = ['passes', 'vocab', 'lr', 'recipe'];
    by = fields.map((f) => [f, new Set(scored.map((p) => (p.r.settings || {})[f])).size] as [string, number]).sort((a, b) => b[1] - a[1])[0][0];
  }
  return { head, body, starKeys, scored: scored.length > 0, light: !!(v.stars && v.stars.length), by };
}

// ---- its readings: every voyage on each measure the expedition is judged by (Findings tab)
export interface SeriesMap { [run: string]: { [metric: string]: [number[], (number | null)[]] } }
export function expeditionOutcomes(v: Expedition): Outcome[] {
  return (v.outcomes || []).filter((o) => o.metric && !/[*<]/.test(o.metric)).slice(0, 10);
}
export function readingsTable(v: Expedition, d: SeriesMap | null): { head: string; body: string } {
  const outs = expeditionOutcomes(v);
  const runs = v.runs.filter((r) => !r.set_aside && r.name);
  if (!outs.length || !runs.length) {
    return { head: '', body: `<tr><td class="${emptyCls(true)}">${outs.length ? 'no voyage has sailed on it yet' : 'it declares no measure the ledger records'}</td></tr>` };
  }
  if (!d) return { head: '', body: `<tr><td colspan="${outs.length + 2}" class="${emptyCls(true)}">reading its voyages…</td></tr>` };
  const last = (r: Run, m: string): number | null => { const sr = (d[r.name] || {})[m]; return sr && sr[1].length ? (sr[1][sr[1].length - 1] ?? null) : null; };
  const best = outs.map((o) => {
    const vals = runs.map((r) => last(r, o.metric)).filter((x): x is number => x != null);
    if (!vals.length) return null;
    return /lower|less|smaller/.test(o.better || '') ? Math.min(...vals) : Math.max(...vals);
  });
  const head = `<tr><th>voyage</th><th>ship</th>${outs.map((o) => `<th title="${esc(o.metric)}; better is ${esc(o.better || '')}">${esc(o.about)}</th>`).join('')}</tr>`;
  const read = runs.filter((r) => outs.some((o) => last(r, o.metric) != null));
  const body = read.slice().reverse().map((r) => `<tr><td><a href="${shipHash(r.name)}">${esc(r.name)}</a></td><td class="s">${esc(r.ship_name || r.ship || '')}</td>
    ${outs.map((o, i) => { const x = last(r, o.metric); return x == null ? '<td class="s">–</td>' : `<td class="${x === best[i] ? 'good' : ''}">${fmt(x)}${x === best[i] ? ' ★' : ''}</td>`; }).join('')}</tr>`).join('')
    || `<tr><td colspan="${outs.length + 2}" class="${emptyCls(true)}">none of its voyages has a reading on these measures yet</td></tr>`;
  return { head, body };
}

// ---- the fit (book_value): what a pure shelf of each kind is worth
export function fitHtml(v: Expedition): { r2: string; rows: string } {
  const fit = v.fit;
  if (!fit || !fit.coef) return { r2: '', rows: '' };
  const rows = Object.entries(fit.coef).map(([k, x]) => `<tr><td>${esc(k)}</td><td>${fmt(x[0])}</td><td>${fmt(x[1])}</td><td>${fmt(x[2])}</td></tr>`).join('');
  return { r2: `cross-validated R² ${fmt(fit.cv_r2, 2)} over ${fit.runs} runs`, rows };
}

// ---- the star chart, on the observation deck: one voyage's sky, played in the order finds were made
interface SkyPos { x: number; y: number; side: string }
function skyLayout(sky: any): { pos: Record<string, SkyPos>; w: number; h: number } {
  const pos: Record<string, SkyPos> = {}, W0 = 40, COL = 130, ROW = 50, TOP = 46;
  const stars = sky.stars.slice().sort((a: any, b: any) => a.level - b.level || b.rests_on.length - a.rests_on.length);
  const used: Record<number, number[]> = {};
  for (const st of stars) {
    const x = W0 + COL * st.level, col = (used[st.level] = used[st.level] || []);
    let y = st.rests_on.length && pos['star:' + st.rests_on[0]] ? pos['star:' + st.rests_on[0]].y : null;
    if (y == null || col.includes(y)) { y = TOP; while (col.includes(y)) y += ROW; }
    col.push(y); pos['star:' + st.key] = { x, y, side: 'r' };
  }
  const besideX = W0 + COL * 4 + 20; let lastY = -Infinity;
  const beside = sky.tricks.map((t: any) => { const ys = t.performed_by.map((k: string) => pos['star:' + k]).filter(Boolean).map((p: SkyPos) => p.y); return { t, y: ys.length ? ys.reduce((a: number, b: number) => a + b, 0) / ys.length : 9999 }; }).sort((a: any, b: any) => a.y - b.y);
  for (const b of beside) { let y = b.y === 9999 ? lastY + ROW : b.y; if (y < lastY + 44) y = lastY + 44; if (!isFinite(y)) y = TOP; lastY = y; pos['trick:' + b.t.key] = { x: besideX, y, side: 'r' }; }
  const chainX = besideX + 150, STEP = 84;
  sky.chains.forEach((c: any[], i: number) => c.forEach((t: any, j: number) => { pos['trick:' + t.key] = { x: chainX + STEP * j, y: TOP + 18 + 100 * i, side: j % 2 ? 'a' : 'b' }; }));
  const ys = Object.values(pos).map((p) => p.y);
  const ymax = ys.length ? Math.max(...ys) : TOP;
  return { pos, w: chainX + STEP * 5 + 70, h: ymax + 40 };
}
function starPath(cx: number, cy: number, R: number): string {
  const r = R * 0.45; let d = '';
  for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, q = i % 2 ? r : R; d += `${i ? 'L' : 'M'}${(cx + q * Math.cos(a)).toFixed(1)},${(cy + q * Math.sin(a)).toFixed(1)}`; }
  return d + 'Z';
}
export interface SkyViewState { view: 'nevermore' | 'all'; k: number | null; i: number | null }
export const skyStateOf = (s?: SkyViewState): SkyViewState => s || { view: 'nevermore', k: null, i: null };

function skyAll(r: any, st: SkyViewState): string {
  const sky = r.sky; if (!sky) return '';
  const finds = r.finds || [];
  const k = st.k == null ? finds.length : Math.min(st.k, finds.length), shown = finds.slice(0, k), live = st.k == null;
  const at = Object.fromEntries(shown.map((f: any) => [f.kind + ':' + f.key, f])), newest = shown[shown.length - 1];
  const { pos, w, h } = skyLayout(sky), latest = r.latest || {};
  const items = [...sky.stars.map((x: any) => ({ ...x, id: 'star:' + x.key, kind: 'star' })), ...sky.tricks.map((x: any) => ({ ...x, id: 'trick:' + x.key, kind: 'trick' })), ...sky.chains.flat().map((x: any) => ({ ...x, id: 'trick:' + x.key, kind: 'trick' }))];
  const line = (a: string, b: string, cls: string): string => { const p = pos[a], q = pos[b]; return p && q ? `<line class="skyline ${cls}${at[a] && at[b] ? ' on' : ''}" x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}"/>` : ''; };
  const lines = [
    ...sky.stars.flatMap((x: any) => x.rests_on.map((o: string) => line('star:' + x.key, 'star:' + o, ''))),
    ...sky.tricks.flatMap((x: any) => x.performed_by.map((o: string) => line('trick:' + x.key, 'star:' + o, 'dash'))),
    ...sky.chains.flatMap((c: any[]) => c.slice(1).map((t: any, j: number) => line('trick:' + c[j].key, 'trick:' + t.key, ''))),
  ].join('');
  const dot = (it: any): string => {
    const p = pos[it.id]; if (!p) return '';
    const f = at[it.id], near = live && !f && latest[it.id] != null && it.threshold ? Math.max(0, Math.min(1, latest[it.id] / it.threshold)) : 0;
    const faded = live && f && latest[it.id] != null && latest[it.id] < it.threshold;
    const cls = ['skyobj', it.kind, f ? 'found' : '', it.built === false ? 'unbuilt' : '', f && f === newest ? 'newest' : '', faded ? 'faded' : ''].filter(Boolean).join(' ');
    const r0 = it.kind === 'star' ? 6 : 5, lx = p.side === 'r' ? p.x + 11 : p.x, ly = p.side === 'r' ? p.y + 4 : p.side === 'a' ? p.y - 13 : p.y + 20;
    const tip = `${it.name}: ${f ? `${it.kind === 'star' ? 'lit' : 'performed'} at step ${f.step} (${signed(f.value)}, the mark ${it.threshold}${f.how ? ', ' + f.how : ''})${faded ? `; since faded to ${signed(latest[it.id])}` : ''}` : it.built === false ? 'not built yet: no test reads it' : `not found${latest[it.id] != null ? `; latest ${signed(latest[it.id])} of ${it.threshold}` : ''}`}`;
    const shape = it.kind === 'star'
      ? `<path d="${starPath(p.x, p.y, f ? r0 + 2 : r0)}"/>`
      : `<rect x="${p.x - r0}" y="${p.y - r0}" width="${2 * r0}" height="${2 * r0}" transform="rotate(45 ${p.x} ${p.y})"/>`;
    return `<g class="${cls}" style="--near:${(0.25 + 0.6 * near).toFixed(2)}" data-id="${esc(it.id)}"><title>${esc(tip)}</title>${f === newest ? `<circle class="pulse" cx="${p.x}" cy="${p.y}" r="10"/>` : ''}${shape}
      <text x="${lx}" y="${ly}" text-anchor="${p.side === 'r' ? 'start' : 'middle'}">${f ? `<tspan class="ord">${f.order}</tspan> ` : ''}${esc(it.name)}</text></g>`;
  };
  const firstStar = Object.keys(pos).find((x) => x.startsWith('star:'));
  const heads = firstStar ? `<text class="skyhead" x="${pos[firstStar].x - 6}" y="16">THE STARS <tspan>heads inside, by level</tspan></text>
    ${sky.tricks.length ? `<text class="skyhead" x="${pos['trick:' + sky.tricks[0].key].x - 6}" y="16">TRICKS</text>` : ''}
    ${sky.chains.length ? `<text class="skyhead" x="${pos['trick:' + sky.chains[0][0].key].x - 6}" y="16">THE FOUR CHAINS <tspan>rung by rung, to the discovery</tspan></text>` : ''}` : '';
  const svg = `<svg class="skysvg" viewBox="0 0 ${w} ${h}" width="${w}" role="img" aria-label="star chart: ${shown.length} of ${items.filter((i: any) => i.built !== false).length} found">${heads}${lines}${items.map(dot).join('')}</svg>`;
  const cap = newest ? `<b>${newest.order}.</b> step ${newest.step}: <b>${esc(newest.name)}</b> ${newest.kind === 'star' ? 'lit' : 'performed'} <span class="s">(${signed(newest.value)}, the mark ${newest.threshold}${newest.how ? ', ' + newest.how : ''})</span>` : '<span class="s">nothing found yet</span>';
  return `<div class="skytop"><span class="s">each star and trick lights where this voyage found it, numbered in order</span>
      <span class="skyctl"><button class="${btnClsLocal('outline')}" data-sky="play" ${finds.length ? '' : 'disabled'}>${st.k != null ? '❚❚ pause' : '▶ play'}</button>
      <input type="range" class="skyrange" min="0" max="${finds.length}" value="${k}" aria-label="finds shown" ${finds.length ? '' : 'disabled'}>
      <button class="${btnClsLocal(live ? 'default' : 'outline', live ? 'text-primary-foreground hover:text-primary-foreground' : '')}" data-sky="live" aria-pressed="${live}">live</button>
      <span class="s">${k} of ${finds.length} found${r.step != null ? ` · at step ${r.step}` : ''}</span></span></div>
    <div class="skycap">${cap}</div>
    <div class="scroll skywrap">${svg}</div>
    <div class="skyorder">${finds.map((f: any) => `<button class="skychip${f.order <= k ? ' on' : ''}" data-k="${f.order}" title="step ${f.step}">${f.order}. ${f.kind === 'star' ? '★' : '◆'} ${esc(f.name)} <span class="s">${f.step}</span></button>`).join('') || '<span class="s">no star lit and no trick performed yet</span>'}</div>`;
}

// the Nevermore card traced through the sieves (the default star-chart view)
const NV_JOBS: [string, string, string][] = [
  ['nm', 'Nevermore head', 'at its mark: attends from a repeat to what followed it last time'],
  ['pw', 'previous-word head', 'at its mark: attends to the word just before'],
  ['nm_near', 'nearly a Nevermore', 'half its mark or more'],
  ['pw_near', 'nearly previous-word', 'half its mark or more'],
  ['other', "another star's head", 'lit as another star (two back, a sink, the delimiter...)'],
  ['none', 'no job yet', 'below half of every mark'],
];
const NV_ENDS: [string, string, string][] = [
  ['linked', 'linked: the Nevermore card', 'a previous-word head with a Nevermore head in a later layer'],
  ['pw_alone', 'no Nevermore above it', 'a previous-word head with no Nevermore head in a later layer'],
  ['nm_alone', 'no previous-word head below', 'a Nevermore head with no previous-word head in an earlier layer: copying some other way'],
  ['forming', 'still forming', 'nearly there: half the mark or more, not yet at it'],
];
function nvClassify(snap: any, marks: Record<string, number>): any[] {
  const m = snap.m, pw = m.previous_word, nm = m.nevermore, heads: any[] = [];
  const others = Object.keys(m).filter((k) => k !== 'previous_word' && k !== 'nevermore' && marks[k] != null);
  pw.forEach((row: number[], l: number) => row.forEach((_: number, h: number) => {
    const p = pw[l][h], n = (nm[l] || [])[h] ?? 0;
    const lit = others.filter((k) => m[k][l] && m[k][l][h] >= marks[k]).sort((a, b) => m[b][l][h] / marks[b] - m[a][l][h] / marks[a]);
    const job = n >= marks.nevermore ? 'nm' : p >= marks.previous_word ? 'pw' : n >= marks.nevermore / 2 ? 'nm_near' : p >= marks.previous_word / 2 ? 'pw_near' : lit.length ? 'other' : 'none';
    heads.push({ l, h, pw: p, nm: n, job, other: lit[0] || null, otherVal: lit[0] ? m[lit[0]][l][h] : null });
  }));
  for (const x of heads) {
    x.end = x.job === 'pw' ? (heads.some((y) => y.job === 'nm' && y.l > x.l) ? 'linked' : 'pw_alone')
      : x.job === 'nm' ? (heads.some((y) => y.job === 'pw' && y.l < x.l) ? 'linked' : 'nm_alone')
      : x.job === 'nm_near' || x.job === 'pw_near' ? 'forming' : null;
  }
  return heads;
}
function nevermoreFlow(r: any, st: SkyViewState): string {
  const H = r.heads || { steps: [] }, steps = H.steps || [], marks = H.marks || {}, names = H.names || {};
  if (!steps.length) return '<div class="s">no head readings yet: the stars and the Nevermore are read at each eval</div>';
  const i = st.i == null ? steps.length - 1 : Math.min(st.i, steps.length - 1), snap = steps[i], live = st.i == null;
  const heads = nvClassify(snap, marks), layers = [...new Set(heads.map((x) => x.l))].sort((a, b) => a - b);
  const W = 860, NW = 12, GAP = 14, Hh = Math.max(200, 26 * heads.length + 40), U = (Hh - 30 - GAP * 5) / heads.length;
  const colX = [140, 420, 680];
  const cols: any[][] = [
    layers.map((l) => ({ id: 'L' + l, label: `layer ${l}`, sub: `${heads.filter((x) => x.l === l).length} heads`, n: heads.filter((x) => x.l === l).length, cls: 'layer' })),
    NV_JOBS.map(([k, label, about]) => ({ id: k, label, about, n: heads.filter((x) => x.job === k).length, cls: 'job-' + k })).filter((x) => x.n),
    NV_ENDS.map(([k, label, about]) => ({ id: k, label, about, n: heads.filter((x) => x.end === k).length, cls: 'end-' + k })).filter((x) => x.n),
  ];
  const at: Record<string, any> = {};
  cols.forEach((col, c) => { let y = 24; col.forEach((nd: any) => { nd.x = colX[c]; nd.y = y; nd.h = Math.max(4, nd.n * U); nd.out = 0; nd.in = 0; at[nd.id] = nd; y += nd.h + GAP; }); });
  const links: string[] = [];
  const pairs = (a: (x: any) => string | null, b: (x: any) => string | null) => {
    const g: Record<string, any[]> = {};
    heads.forEach((x) => { const s = a(x), t = b(x); if (s != null && t != null) { const k = s + '>' + t; (g[k] = g[k] || []).push(x); } });
    return Object.entries(g).map(([k, hs]) => { const [s, t] = k.split('>'); return { s, t, hs }; });
  };
  const order = (id: string): number => [...cols[1], ...cols[2]].findIndex((n) => n.id === id);
  for (const lk of [...pairs((x) => 'L' + x.l, (x) => x.job).sort((a, b) => order(a.t) - order(b.t)), ...pairs((x) => x.job, (x) => x.end).sort((a, b) => order(a.t) - order(b.t))]) {
    const a = at[lk.s], b = at[lk.t], w = lk.hs.length * U;
    const y0 = a.y + a.out + w / 2, y1 = b.y + b.in + w / 2; a.out += w; b.in += w;
    const x0 = a.x + NW, x1 = b.x, mx = (x0 + x1) / 2;
    const tip = `${lk.hs.length} head${lk.hs.length === 1 ? '' : 's'}: ${lk.hs.map((x) => `layer ${x.l} head ${x.h} (previous word ${x.pw.toFixed(2)}, Nevermore ${x.nm.toFixed(2)})`).join('; ')}`;
    links.push(`<path class="nvlink to-${esc(lk.t)}" d="M${x0},${y0}C${mx},${y0} ${mx},${y1} ${x1},${y1}" stroke-width="${Math.max(1, w - 1).toFixed(1)}"><title>${esc(tip)}</title></path>`);
  }
  const nodes = cols.flatMap((col, c) => col.map((nd: any) => `<g class="nvnode ${nd.cls}"><title>${esc(nd.label + (nd.about ? ': ' + nd.about : ''))}</title><rect x="${nd.x}" y="${nd.y}" width="${NW}" height="${nd.h}" rx="2"/>
    <text x="${c === 0 ? nd.x - 6 : nd.x + NW + 6}" y="${nd.y + nd.h / 2 + 4}" text-anchor="${c === 0 ? 'end' : 'start'}">${esc(nd.label)} <tspan class="n">${nd.n}</tspan></text></g>`)).join('');
  const heads3 = ['every head', 'the sieves: what each head does', 'the link'].map((t, c) => `<text class="skyhead" x="${c === 0 ? colX[0] + NW : colX[c]}" y="12" text-anchor="${c === 0 ? 'end' : 'start'}">${t.toUpperCase()}</text>`).join('');
  const formed = heads.some((x) => x.end === 'linked');
  const best = heads.slice().sort((a, b) => b.pw / marks.previous_word - a.pw / marks.previous_word)[0], bestN = heads.slice().sort((a, b) => b.nm - a.nm)[0];
  const verdict = formed ? `<span class="${pillCls('good')}">formed</span> the Nevermore card is in its hand at step ${snap.step}`
    : `<span class="${pillCls('')}">not formed</span> at step ${snap.step}: the best previous-word head is layer ${best.l} head ${best.h} at <b>${best.pw.toFixed(2)}</b> of ${marks.previous_word}; the best Nevermore head layer ${bestN.l} head ${bestN.h} at <b>${bestN.nm.toFixed(2)}</b> of ${marks.nevermore}`;
  const bar = (v: number, mk: number): string => `<span class="nvbar" title="${v.toFixed(3)} of ${mk}"><span style="width:${Math.max(0, Math.min(100, (100 * v) / mk)).toFixed(0)}%"></span><i style="left:50%"></i></span> ${v.toFixed(2)}`;
  const jobName: Record<string, string> = Object.fromEntries([...NV_JOBS, ...NV_ENDS].map(([k, l]) => [k, l]));
  const table = `<table class="nvheads" data-nosort><thead><tr><th>head</th><th>previous word <span class="s">mark ${marks.previous_word}</span></th><th>Nevermore <span class="s">mark ${marks.nevermore}</span></th><th>the sieve</th><th>the link</th></tr></thead><tbody>${heads.map((x) => `<tr><td>layer ${x.l} · head ${x.h}</td><td>${bar(x.pw, marks.previous_word)}</td><td>${bar(x.nm, marks.nevermore)}</td><td><span class="nvdot job-${x.job}"></span>${esc(jobName[x.job])}${x.other ? ` <span class="s">(${esc(names[x.other] || x.other)} ${x.otherVal.toFixed(2)})</span>` : ''}</td><td class="s">${x.end ? esc(jobName[x.end]) : '–'}</td></tr>`).join('')}</tbody></table>`;
  return `<div class="skyctl"><button class="${btnClsLocal('outline')}" data-nv="play">${st.i != null ? '❚❚ pause' : '▶ play'}</button>
      <input type="range" class="nvrange" min="0" max="${steps.length - 1}" value="${i}" aria-label="step">
      <button class="${btnClsLocal(live ? 'default' : 'outline', live ? 'text-primary-foreground hover:text-primary-foreground' : '')}" data-nv="live" aria-pressed="${live}">live</button>
      <span class="s">step <b>${snap.step}</b> · reading ${i + 1} of ${steps.length}</span></div>
    <div class="skycap">${verdict}</div>
    <div class="scroll skywrap"><svg class="nvsvg" viewBox="0 0 ${W} ${Hh}" role="img" aria-label="every head through the sieves to the Nevermore card at step ${snap.step}">${heads3}${links.join('')}${nodes}</svg></div>
    <div class="scroll">${table}</div>
    <p class="s">A head passes a sieve at its star's mark; half the mark is "nearly". The Nevermore is read on real passages (a repeat, then what followed it last time); the previous-word head on the same passages. The card forms when a previous-word head has a Nevermore head in a later layer to read what it wrote. Read every ${steps.length > 1 ? steps[1].step - steps[0].step : '–'} steps.</p>`;
}
export function skyChart(r: any, st: SkyViewState): string {
  const v = st.view || 'nevermore';
  return `<div class="skytop"><span class="k">the star chart</span>
      <span class="skytabs" role="tablist">${[['nevermore', 'the Nevermore card'], ['all', 'every star']].map(([k, l]) => `<button role="tab" aria-selected="${v === k}" class="${toggleClsLocal()}" data-state="${v === k ? 'on' : 'off'}" data-skyview="${k}">${l}</button>`).join('')}</span></div>
    ${v === 'nevermore' ? nevermoreFlow(r, st) : skyAll(r, st)}`;
}

// the observation deck (#obsdeck; /api/observation): its voyages at sea, read live from their logs
const hm = (s: number | null | undefined): string => (s == null ? '–' : s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min` : s >= 60 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`);
function spark(l: [number[], number[]] | null | undefined): string {
  if (!l || !l[1] || l[1].length < 2) return '';
  const ys = l[1], W = 220, H = 40, lo = Math.min(...ys), hi = Math.max(...ys), sx = (i: number): number => ((W - 2) * i) / (ys.length - 1) + 1, sy = (y: number): number => H - 2 - (H - 4) * (hi > lo ? (y - lo) / (hi - lo) : 0.5);
  return `<svg class="obsspark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="loss over the last steps"><polyline points="${ys.map((y, i) => `${sx(i).toFixed(1)},${sy(y).toFixed(1)}`).join(' ')}"/></svg>`;
}
function deckShipHtml(r: any, st: SkyViewState): string {
  const pct = r.step && r.steps_total ? Math.min(100, (100 * r.step) / r.steps_total) : 0;
  const cardChip = (k: string, c: any): string => {
    const f = CARD_FACE[k] || {}, best = Math.max(c.one ?? -Infinity, c.shared ?? -Infinity);
    return `<span class="obscard${c.lit ? ' lit' : ''}" title="${esc(STAR_LABEL[k] || f.short || k)}: one head ${c.one != null ? c.one.toFixed(3) : '–'}${c.shared != null ? `, two together ${c.shared.toFixed(3)}` : ''}; the mark ${c.threshold}"><span class="minicard${c.lit ? ' on' : ''}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span> ${isFinite(best) ? best.toFixed(2) : '–'}<i class="s"> / ${c.threshold}</i></span>`;
  };
  return `<div class="obsship" data-deck-run="${esc(r.run_id)}">
      <div class="obshead"><span class="${pillCls('running')}">at sea</span> <a href="${shipHash(r.name)}"><b>${esc(r.name)}</b></a>
        <div class="s">${esc(r.ship || '')}${r.started ? ` · cast off ${esc(String(r.started).slice(11, 16))}` : ''}</div></div>
      <div class="obsrow">
        <div class="obsprog"><div class="obsbar"><span style="width:${pct.toFixed(1)}%"></span></div>
          <div class="s">step <b>${r.step ?? '–'}</b> of ${r.steps_total ?? '–'} · ${pct.toFixed(0)}% · about <b>${hm(r.eta_s)}</b> to port</div></div>
        <div class="obsloss"><div class="s">loss <b>${r.loss && r.loss[1].length ? r.loss[1][r.loss[1].length - 1].toFixed(2) : '–'}</b></div>${spark(r.loss)}</div>
        <div class="obsfig"><div><b>${r.tokens_per_s != null ? big(r.tokens_per_s) : '–'}</b><span>tokens a second</span></div><div><b>${r.mem_gb ?? '–'}</b><span>GB</span></div>
          ${r.hole_cards_bpb != null ? `<div><b>${r.hole_cards_bpb.toFixed(3)}</b><span>hole cards, bits per byte</span></div>` : ''}</div>
      </div>
      <div class="obscards"><span class="k">the four cards</span> ${Object.entries(r.cards || {}).map(([k, c]) => cardChip(k, c)).join('')}
        ${r.logic_gain != null ? `<span class="obscard" title="the logic deck's chaining gain"><b>gain</b> ${signed(r.logic_gain)}</span>` : ''}${r.cause_gain != null ? `<span class="obscard" title="cause and effect"><b>cause</b> ${signed(r.cause_gain)}</span>` : ''}</div>
      <div class="sky" data-run="${esc(r.run_id)}">${skyChart(r, st)}</div>
    </div>`;
}
export interface Observation {
  expedition: string; at_sea: any[]; state?: string | null; queued?: number | null; next_in_queue?: number | null;
  helm?: any; elsewhere?: any[];
}
export function deckHtml(d: Observation, sky: Record<string, SkyViewState>, expeditionName: string, selectedRunId: string | null = null): string {
  const sea = d.at_sea || [];
  if (sea.length) {
    // one voyage at a time: the chips pick which, and the default is the first at sea rather than
    // drawing every journey's deck (10 November: the deck showed all of them)
    const chosen = (selectedRunId ? sea.find((r) => r.run_id === selectedRunId) : null) || sea[0];
    const chips = sea.length > 1
      ? `<div class="obsnav"><span class="k">voyage</span><div class="skytabs">${sea.map((r) => `<button type="button" class="skychip${r.run_id === chosen.run_id ? ' on' : ''}" data-deck-run="${esc(r.run_id)}">${esc(r.name)}</button>`).join('')}</div></div>`
      : '';
    return chips + deckShipHtml(chosen, skyStateOf(sky[chosen.run_id]));
  }
  const where = d.next_in_queue ? `its next voyage is <b>#${d.next_in_queue}</b> in the queue (${d.queued} of its voyages queued)` : d.state === 'home' ? 'it is home: every voyage has come back' : d.state === 'awaiting orders' ? 'it is awaiting orders: nothing of it at sea or queued' : 'nothing of it is queued';
  const other = (d.elsewhere || [])[0];
  return `<div class="${emptyCls()}">no voyage of this expedition is at sea: ${where}.${other ? ` At sea now: <a href="${shipHash(other.name)}">${esc(other.name)}</a>${other.expedition ? `, of <a href="/expeditions/${esc(other.expedition)}">${esc(expeditionName)}</a>` : ''}.` : ''}</div>`;
}

// ---- the census (card_census): each size's fitout and its variations, a row openable for its stages
export const STAGE_NAMES = ['pretraining', 'post-training 1', 'post-training 2'];
export function censusHtml(d: any, open: Set<string>, rungs: Rung[]): string {
  const cards = d.cards || [], cs = d.censuses || [];
  if (!cs.length) return `<div class="${emptyCls()}">no fitout census written yet</div>`;
  const read = (st: any): boolean => !!(st && ((st.cards && Object.keys(st.cards).length) || st.cause != null));
  const lastRead = (r: any): [any, number] => { for (let i = r.stages.length - 1; i >= 0; i--) if (read(r.stages[i])) return [r.stages[i], i]; return [null, -1]; };
  const cardCell = (st: any, k: any, i: number, last: boolean): string => {
    const x = st && st.cards && st.cards[k.key]; if (!x) return '<td class="cen q">–</td>';
    const best = Math.max(x.one ?? -Infinity, x.shared ?? -Infinity), near = Math.max(0, Math.min(1, best / k.threshold));
    return `<td class="cen${x.lit ? ' lit' : ''}" style="--near:${(100 * near).toFixed(0)}%" title="${esc(k.name)}: one head ${x.one != null ? x.one.toFixed(3) : '–'}${x.shared != null ? `, shared ${x.shared.toFixed(3)}` : ''}; the mark ${k.threshold}">${isFinite(best) ? best.toFixed(2) : '–'}${x.lit ? ' ✓' : ''}${last && i < 2 ? `<div class="s">${esc(STAGE_NAMES[i])}</div>` : ''}</td>`;
  };
  const causeCell2 = (st: any, base: any): string => {
    if (!st || st.cause == null) return '<td class="cen q">–</td>';
    const dlt = base && base.cause != null && st !== base ? st.cause - base.cause : null;
    return `<td class="cen${st.cause >= 0.1 ? ' lit' : ''}" title="cause and effect: the logic deck's chaining gain on its cause items${dlt != null ? `; ${signed(dlt)} against the fitout's own` : ''}">${signed(st.cause)}${dlt != null ? `<div class="s">${signed(dlt)} vs fitout</div>` : ''}</td>`;
  };
  return cs.map((c: any) => {
    const sailed = c.rows.filter((r: any) => r.stages.some(read)).length, base = c.rows.find((r: any) => r.variation === 'fitout');
    const head = `<div class="censushead"><span class="cenposs"><b>${c.possible.length} of ${cards.length}</b> possible at ${c.preset ? classLink(rungs, c.preset) : esc(c.key)}</span>
      <span class="miniset">${cards.map((k: any) => { const f = CARD_FACE[k.key] || {}; return `<span class="minicard${c.possible.includes(k.key) ? ' on' : ''}" title="${esc(k.name)}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span>`; }).join('')}</span>
      <span class="s">${esc(c.name || c.key)} · ${sailed} of ${c.rows.length} variations read${c.summary ? ' · census written' : ''}</span></div>`;
    const rows = c.rows.map((r: any) => {
      const [st, i] = lastRead(r), isOpen = open.has(c.key + '|' + r.variation);
      const status = r.stages.every((x: any) => x.status === 'queued') ? 'queued' : r.stages.some((x: any) => x.status === 'running') ? 'running' : r.stages.every((x: any) => x.status === 'finished') ? 'finished' : 'sailing';
      const baseSt = base && i >= 0 ? base.stages[i] : null;
      const main = `<tr class="cenrow${isOpen ? ' open' : ''}" data-cen="${esc(c.key + '|' + r.variation)}"><td><b>${esc(r.variation)}</b>${r.variation === 'fitout' ? ` <span class="${pillCls('accent')}">the fitout</span>` : ''}</td><td>${statusPill(status)}</td>
        ${st ? cards.map((k: any) => cardCell(st, k, i, true)).join('') + causeCell2(st, baseSt) : `<td class="cen q" colspan="${cards.length + 1}">${status === 'queued' ? 'queued' : 'no reading yet'}</td>`}</tr>`;
      const detail = isOpen ? r.stages.map((x: any, j: number) => `<tr class="censtage"><td class="s">↳ ${esc(STAGE_NAMES[j] || 'stage ' + (j + 1))}</td><td>${x.status === 'queued' ? esc(x.run) : `<a href="${shipHash(x.run)}">${esc(x.run)}</a>`} ${statusPill(x.status)}</td>
        ${read(x) ? cards.map((k: any) => cardCell(x, k, j, false)).join('') + causeCell2(x, base && base.stages[j]) : `<td class="cen q" colspan="${cards.length + 1}">${x.status === 'queued' ? 'queued' : 'no reading yet'}</td>`}</tr>`).join('') : '';
      return main + detail;
    }).join('');
    return `${head}<div class="scroll"><table class="censustable" data-nosort><thead><tr><th>variation <span class="s">open one for its stages</span></th><th></th>${cards.map((k: any) => { const f = CARD_FACE[k.key] || {}; return `<th title="${esc(k.name)}, lit at ${k.threshold}">${f.rank || ''}${f.suit || ''} ${esc(f.short || k.name)}</th>`; }).join('')}<th title="the logic deck's chaining gain on its cause items, 0.1 the mark">cause and effect</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }).join('');
}

// ---- the induction head's verdict (the induction expedition): the pre-registered rule, read
export const IND_METRICS = {
  nev: 'nevermore/natural_max_score', prev: 'stars/previous_word/max_score', copy: 'nevermore/natural_copy_gain',
};
export function inductionVerdict(v: Expedition, d: SeriesMap | null): string {
  const runs = (v.runs || []).filter((r) => r.name);
  if (!runs.length) return '<span class="s">waiting for the first readings (every 100 steps)</span>';
  if (!d) return '<span class="s">reading its voyages…</span>';
  const twin = (r: Run): boolean => /random/.test(r.name);
  const lit = (r: Run): number | false | null => { const sr = (d[r.name] || {})[IND_METRICS.nev]; if (!sr) return null; const i = sr[1].findIndex((x) => x != null && x >= 0.3); return i >= 0 ? sr[0][i] : false; };
  const eng = runs.filter((r) => !twin(r)), tw = runs.filter(twin);
  const engLit = eng.filter((r) => lit(r)).length, twLit = tw.filter((r) => lit(r)).length;
  const best = (rs: Run[]): number => Math.max(-Infinity, ...rs.map((r) => { const sr = (d[r.name] || {})[IND_METRICS.nev]; return sr ? Math.max(...sr[1].filter((x): x is number => x != null)) : -Infinity; }));
  const success = engLit + twLit >= 2 && (engLit >= 2 || twLit >= 2), byRepetition = engLit >= 2 && twLit === 0;
  return `<span class="${pillCls(success ? 'good' : '')}">${success ? 'lit on two seeds' : 'not lit on two seeds yet'}</span>
    ${byRepetition ? `<span class="${pillCls('good')}">repetition did it</span>` : ''}
    <span class="s">trigram engine: ${engLit} of ${eng.length} seeds lit${isFinite(best(eng)) ? `, best ${best(eng).toFixed(3)}` : ''} · random twin: ${twLit} of ${tw.length}${isFinite(best(tw)) ? `, best ${best(tw).toFixed(3)}` : ''} · earlier 300k Nevermores: 0.00 to 0.01</span>`;
}

// ---- the table (#table: talk with a ship; /api/table/transcript, POST /api/table/reply)
export interface TableExchange { q: string; a: string; meta?: any }
const tableMeta = (m: any): string => !m ? '' : [
  m.temperature != null ? `t ${Number(m.temperature).toFixed(2)}` : '', m.seed != null ? `seed ${m.seed}` : '', m.tokens != null ? `${m.tokens} tokens` : '',
  m.seconds != null ? `${Number(m.seconds).toFixed(1)} s` : '',
  m.stopped ? { turn: 'stopped at the next turn', blank: 'stopped at a blank line', length: 'stopped at the length', eos: 'stopped at the end of text' }[m.stopped as string] || `stopped: ${m.stopped}` : '',
].filter(Boolean).join(' · ');
export function tableLogHtml(log: TableExchange[], pending: string | null): string {
  return (log.length || pending ? '' : `<div class="${emptyCls()}">no exchanges with this ship yet: say something below</div>`)
    + log.map((x) => `<div class="ex"><div class="q"><b>Q:</b> ${esc(x.q)}</div><div class="a"><b>A:</b> ${esc(x.a)}</div><div class="m">${esc(tableMeta(x.meta))}</div></div>`).join('')
    + (pending ? `<div class="ex pending"><div class="q"><b>Q:</b> ${esc(pending)}</div><div class="a"><b>A:</b> <span class="s">the ship is thinking…</span></div></div>` : '');
}
export function tableReadingsHtml(r: any): string {
  if (!r) return 'no readings came back';
  const row = (k: string, v: any): string => `<div class="rd${v == null ? ' none' : ''}"><span>${esc(STAR_LABEL[k] || k.replace(/_/g, ' '))}</span><b>${v == null ? '–' : typeof v === 'number' ? fmt(v) : esc(String(v))}</b></div>`;
  const order = (o: any): [string, any][] => Object.entries(o || {}).sort((a, b) => ((a[1] == null ? 1 : 0) - (b[1] == null ? 1 : 0))) as [string, any][];
  const stars = order(r.stars), tricks = order(r.tricks);
  return (stars.length ? `<div class="k">stars</div>${stars.map(([k, v]) => row(k, v)).join('')}` : '')
    + (tricks.length ? `<div class="k mt">tricks</div>${tricks.map(([k, v]) => row(k, v)).join('')}` : '') || 'no readings on this ship';
}

// the name of a voyage by expedition key (the cards, the queue, the deck's "elsewhere")
export const expeditionName = (exps: Expedition[], key: string | null | undefined): string =>
  (exps.find((x) => x.key === key) || {}).name || String(key || '');

// ---- the cards in play (#expeditions; /api/expeditions/overview .sops and /api/expeditions): one grid,
// the standard at sea beside the expeditions open ahead of their own standard, so every card reads alike.
const sopCardHtml = (e: any): string => `<a class="sopcard${e.at_sea ? ' atsea' : ''}" href="${e.expedition ? `/expeditions/${esc(e.expedition)}` : '/shipyard/training'}" title="${e.expedition ? `open the ${esc(e.expedition)} expedition` : 'open the SOP in the shipyard'}">
      ${e.art ? `<img class="sopart" src="/art/${esc(e.art)}.png" alt="" loading="lazy">` : '<div class="sopart"></div>'}
      <div class="sopbody">
        <div class="sophead"><b>${esc(e.expedition_name || `SOP v${e.version}`)}</b><span class="s">SOP v${esc(e.version)}</span>${e.at_sea ? `<span class="${pillCls('running')}">at sea</span>` : `<span class="${pillCls('')}">${e.finished ? 'in port' : 'planned'}</span>`}<span class="s">${e.at_sea ? `${e.at_sea} voyage${e.at_sea === 1 ? '' : 's'} out` : e.finished ? `${e.finished} voyage${e.finished === 1 ? '' : 's'} home` : 'not sailed'}</span></div>
        <div class="k">its goals</div>
        <ul class="sopgoals">${(e.goals || []).map((g: any) => `<li><b>${esc(typeof g === 'string' ? g : g.text)}</b>${typeof g === 'string' || !g.detail ? '' : ` <span class="s">— ${esc(g.detail)}</span>`}</li>`).join('')}</ul>
      </div></a>`;

const openCardHtml = (v: Expedition, states: Record<string, string>, ov: Record<string, any>): string => {
  const o = ov[v.key] || {};
  const valid = v.runs.filter((r) => !r.set_aside).length;
  const atSea = Number(o.at_sea || 0);
  const sailed = `${valid} of ${v.stop.max_runs} voyage${v.stop.max_runs === 1 ? '' : 's'}`;
  return `<a class="sopcard${atSea ? ' atsea' : ''}" href="/expeditions/${esc(v.key)}" title="open the ${esc(v.name)} expedition">
      ${artImg(`exp-${v.key}`, 'sopart')}
      <div class="sopbody">
        <div class="sophead"><b>${esc(v.name)}</b><span class="s">expedition</span>${expPill(states[v.key], v)}<span class="s">${sailed}</span></div>
        <div class="k">its goal</div>
        <ul class="sopgoals"><li title="${esc(v.goal)}">${esc(cut(v.goal, 640))}</li></ul>
      </div></a>`;
};

/** One grid for the page: every live SOP card and every open expedition card. They are different data
 *  and the same shape, so Kipling and Arc de Triomphe sit side by side rather than stacked. */
export function overviewCardsHtml(d: any, exps: Expedition[], states: Record<string, string>, overview?: any): string {
  const ov: Record<string, any> = {};
  for (const e of (overview && overview.expeditions) || []) ov[e.key] = e;
  const cards = [...(d.sops || []).map(sopCardHtml), ...(exps || []).map((v) => openCardHtml(v, states, ov))];
  return cards.length ? `<div class="sopcards">${cards.join('')}</div>` : '';
}

// ---- the SOP cards on the Plans tab's earlier standards (one grid, unchanged)
export function sopCardsHtml(d: any): string {
  const sops = d.sops || [];
  return sops.length ? `<div class="sopcards">${sops.map(sopCardHtml).join('')}</div>` : '';
}

// ---- First Light: the first expedition's findings, from its fourteen round-1 voyages
export function firstLightFindings(v: Expedition): string {
  const runs = v.runs
    .filter((r) => !r.set_aside && r.ft_en != null)
    .slice()
    .sort((a, b) => (a.ft_en as number) - (b.ft_en as number));
  if (!runs.length) return `<p class="${emptyCls(false)}">no voyage has a Forgotten Tomes score yet</p>`;
  const arm = (r: Run): string => (r.ship || r.name || '').replace(/^First Light:\s*/, '');
  const setting = (r: Run, k: string): string => {
    const x = ((r.settings || {}) as Record<string, unknown>)[k];
    return x == null ? '–' : String(x);
  };
  const shelf = (r: Run): string => String((r.settings || {}).recipe || '').replace(/^lists\//, '').replace(/\.csv$/, '');
  const star = (r: Run, key: string): StarRead | undefined => (r.stars || []).find((x) => x.star === key);
  const lit = (r: Run, key: string): string => {
    const x = star(r, key);
    if (!x) return '–';
    if (x.steps_to_lit != null) return `lit ${fmt(x.steps_to_lit, 0)}`;
    if (x.shared_steps_to_lit != null) return `shared ${fmt(x.shared_steps_to_lit, 0)}`;
    return '–';
  };
  const best = runs[0];
  const base = runs.filter((r) => /baseline/.test(arm(r)));
  const spread = base.length === 2 ? Math.abs((base[0].ft_en as number) - (base[1].ft_en as number)) : null;
  const pw = star(best, 'previous_word');
  const shared = pw && pw.shared_steps_to_lit != null
    ? ` No single head reached the previous-word mark; the best voyage lit it <b>shared</b> (the best layer's two strongest heads together) at step ${fmt(pw.shared_steps_to_lit, 0)}.`
    : '';
  const rows = runs.map((r) => `<tr><td><a href="${shipHash(r.name)}">${esc(arm(r))}</a></td><td class="s">${esc(setting(r, 'vocab'))}</td><td class="s">${esc(setting(r, 'lr'))}</td><td class="s">${esc(shelf(r))}</td><td class="s">${esc(setting(r, 'seed'))}</td><td class="${r === best ? 'good' : ''}">${fmt(r.ft_en, 3)}${r === best ? ' ★' : ''}</td><td class="s">${lit(r, 'previous_word')}</td><td class="s">${lit(r, 'duplicate_word')}</td></tr>`).join('');
  return `<p><b>${esc(arm(best))}</b> won at <b>${fmt(best.ft_en, 3)}</b> bits per byte on the 16 unseen books.${spread == null ? '' : ` The baseline's two seeds sit <b>${fmt(spread, 3)}</b> apart — that is the error bar every later comparison used.`}${shared}</p>
    <p class="s">Reading more was the strongest lever (the pathfinder read twice); vocabulary 16,384 beat 4,096, 2,048 was the worst of the three, and the verse shelf was the worst shelf. The 2,048 vocabulary and 2e-3 learning rate the later 1m runs use are this sweep's descendants.</p>
    <div class="scroll"><table><thead><tr><th>arm</th><th>vocab</th><th>lr</th><th>shelf</th><th>seed</th><th>Forgotten Tomes</th><th>previous-word</th><th>duplicate-word</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// ---- the plans page as a table: every expedition, one row, with what it has sailed and what it found
export function expeditionTableHtml(exps: Expedition[], states: Record<string, string>, overview: any): string {
  const ov: Record<string, any> = {};
  for (const e of (overview && overview.expeditions) || []) ov[e.key] = e;
  const rows = exps.map((v) => {
    const o = ov[v.key] || {};
    const valid = v.runs.filter((r) => !r.set_aside).length;
    const found = v.learned || starHeadline(v) || '';
    const queued = Number(o.queued || 0);
    return `<tr>
      <td><a href="/expeditions/${esc(v.key)}"><b>${esc(v.name)}</b></a><div class="s">${esc(cut(v.goal || '', 120))}</div></td>
      <td class="s">${esc(v.fleet || '')}</td>
      <td class="s">${esc(v.preset || '')}</td>
      <td>${expPill(states[v.key], v)}</td>
      <td class="num">${Number(o.at_sea || 0)}</td>
      <td class="num">${Number(o.finished || 0)}</td>
      <td class="num">${Number(o.failed || 0)}</td>
      <td class="num">${queued}${o.next_in_queue != null ? ` <span class="s">next #${Number(o.next_in_queue)}</span>` : ''}</td>
      <td class="num">${valid}/${v.stop.max_runs}</td>
      <td class="s">${esc(cut(found, 160))}</td>
    </tr>`;
  }).join('');
  return `<div class="scroll"><table id="expeditiontable"><thead><tr>
    <th>expedition</th><th>fleet</th><th>class</th><th>status</th>
    <th title="voyages at sea now">at sea</th><th title="voyages that finished">finished</th>
    <th title="voyages that failed or were stopped">failed</th><th title="its lines still in the queue, and where its next one stands">queued</th>
    <th title="voyages sailed of the stop rule's maximum">voyages</th><th>what it found</th>
  </tr></thead><tbody>${rows || `<tr><td colspan="10" class="${emptyCls()}">no expeditions yet</td></tr>`}</tbody></table></div>`;
}

// ---- the queue as swimlanes (12 November, Justin: "in the queue I'd be expecting to see the lane. So
// something like a swimlane perhaps?"): one track a lane, this Mac and the hired GPU, each line a block from
// when it starts to when it is home, on one clock from now to the queue's last homecoming. The purser's advice
// (a voyage it would send abroad, while it only advises) is drawn on the Vast lane as an outline.
const LANE_NAME: Record<string, string> = { mac: 'This Mac', vast: 'Vast.ai' };
const PRESET_TONE: Record<string, string> = { '300k': 'p300k', '1m': 'p1m', '9m': 'p9m', '21m': 'p21m', '50m': 'p21m' };

function laneShort(r: any): string {
  return String(r.name || '').replace(/@v\d+(\.\d+)*/, '').replace(/^fitouts\//, '');
}

function clockAt(minFromNow: number): string {
  const d = new Date(Date.now() + minFromNow * 60000);
  return `${d.toLocaleDateString(undefined, { weekday: 'short' })} ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;
}

export function queueLanesHtml(d: any): string {
  const rows: any[] = d?.rows || [];
  if (!rows.length) return '';
  const lanes: any[] = d.lanes && d.lanes.length
    ? d.lanes
    : [{ lane: 'mac', kind: 'local', seats: 1, enabled: true }, { lane: 'vast', kind: 'charter', seats: 1, enabled: true }];
  const span = (r: any): [number, number] | null => {
    if (r.status === 'at sea') {
      const left = r.left_min != null ? Number(r.left_min) : null;
      return left == null ? null : [0, Math.max(left, 1)];
    }
    if (r.starts_in_min == null || r.est_min == null) return null;
    return [Number(r.starts_in_min), Number(r.starts_in_min) + Math.max(Number(r.est_min), 1)];
  };
  const advice = rows
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => r.purser && r.purser.waters === 'foreign' && !r.purser.applied && r.purser.foreign_home_min != null);
  const ends = rows.map(span).filter((x): x is [number, number] => !!x).map((x) => x[1])
    .concat(advice.map(({ r }) => Number(r.purser.foreign_home_min)));
  const total = Math.max(60, ...ends, Number(d.hours_left || 0) * 60);
  const pct = (m: number): string => `${Math.min(100, Math.max(0, (m / total) * 100)).toFixed(3)}%`;
  const step = total <= 12 * 60 ? 120 : total <= 36 * 60 ? 180 : 720;
  const tickAt: number[] = [];
  for (let m = step; m < total * 0.9; m += step) tickAt.push(m); // clear of the end's own label
  const block = (r: any, i: number, a: number, b: number, ghost = false, group?: { label: string; tip: string }): string => {
    const intel = r.kind === 'intelligence';
    const tone = intel ? 'pintel' : r.kind === 'step' ? 'pstep' : (PRESET_TONE[r.preset] || 'pother');
    const sea = r.status === 'at sea';
    const p = r.purser || {};
    const name = intel ? `S4 intelligence: ${r.name}` : r.name;
    const tip = ghost
      ? `${r.name}: the purser would sail it abroad (${p.gpu || 'a hired GPU'}, about ${Math.round(p.foreign_min || 0)} min, $${Number(p.cost || 0).toFixed(2)}), home ${clockAt(b)}. Advice only: it sails on this Mac unless the purser is routing.`
      : `${name}${r.goal_id ? ` · ${r.goal_id}` : ''}${sea ? ' · at sea now' : ` · starts ${clockAt(a)}`} · about ${Math.round(b - a)} min · home ${clockAt(b)}${p.reason ? ` · purser: ${p.reason}` : ''}`;
    const q = sea ? queueDone(r) : null;
    const pctDone = q && q.total ? ` ${Math.round((100 * q.step) / q.total)}%` : '';
    const label = group ? group.label : intel ? 'S4 audit' : r.kind === 'step' ? '' : `${laneShort(r)}${pctDone}`;
    if (group) return `<span class="qlblock ${tone} qlgroupblock" data-qi="${i}" tabindex="0" role="button" style="left:${pct(a)};width:max(3px, calc(${pct(b)} - ${pct(a)}))" title="${esc(group.tip)}" aria-label="${esc(group.tip)}">${esc(label)}</span>`;
    return `<span class="qlblock ${tone}${sea ? ' sea' : ''}${ghost ? ' ghost' : ''}" data-qi="${i}" tabindex="0" role="button" style="left:${pct(a)};width:max(3px, calc(${pct(b)} - ${pct(a)}))" title="${esc(tip)}" aria-label="${esc(tip)}">${esc(label)}</span>`;
  };
  const tracks = lanes.map((ln: any) => {
    const mine = rows.map((r, i) => ({ r, i })).filter(({ r }) => (r.lane || 'mac') === ln.lane);
    // a chain of like steps is one block, labelled with its count (13 November: thirty unlabelled slivers)
    const parts: string[] = [];
    for (let k = 0; k < mine.length; k++) {
      const { r, i } = mine[k];
      const sp = span(r);
      if (r.kind === 'step' && sp && r.status !== 'at sea') {
        let m = k;
        while (m + 1 < mine.length && mine[m + 1].r.kind === 'step' && mine[m + 1].r.what === r.what && stepPrefix(mine[m + 1].r) === stepPrefix(r) && span(mine[m + 1].r)) m++;
        if (m > k) {
          const run = mine.slice(k, m + 1), end = span(run[run.length - 1].r)![1];
          const names = run.map((x) => String(x.r.name).split(': ').slice(1).join(': ') || x.r.name);
          const tip = `${stepPrefix(r)}: ${run.length} ${r.what === 'reading' ? 'readings' : r.what === 'investigation' ? 'investigations' : 'steps'} in a row (${names.slice(0, 6).join(', ')}${names.length > 6 ? ', …' : ''}) · starts ${clockAt(sp[0])} · home ${clockAt(end)} · click for the first's card`;
          parts.push(block(r, i, sp[0], end, false, { label: `${stepPrefix(r)} ×${run.length}`, tip }));
          k = m;
          continue;
        }
      }
      parts.push(sp ? block(r, i, sp[0], sp[1]) : '');
    }
    const blocks = parts.join('');
    const ghosts = ln.kind === 'charter'
      ? advice.map(({ r, i }) => block(r, i, Number(r.purser.foreign_home_min) - Number(r.purser.foreign_min || 0), Number(r.purser.foreign_home_min), true)).join('')
      : '';
    const atSea = mine.filter(({ r }) => r.status === 'at sea').map(({ r }) => r.name);
    const queued = mine.filter(({ r }) => r.status !== 'at sea').length;
    const lastEnd = Math.max(0, ...mine.map(({ r }) => (span(r) || [0, 0])[1]));
    const n = Number(ln.seats || 1);
    const seats = ln.kind === 'charter' ? `${n} ship${n === 1 ? '' : 's'} out at once` : `${n} seat${n === 1 ? '' : 's'}`;
    let sub: string;
    if (!ln.enabled) sub = 'switched off';
    else if (mine.length) {
      const hired = mine.map(({ r }) => r.abroad).filter(Boolean);
      const spent = hired.reduce((s2: number, a: any) => s2 + (Number(a.spent) || 0), 0), proj = hired.reduce((s2: number, a: any) => s2 + (Number(a.projected) || 0), 0);
      const cost = ln.kind === 'charter' && hired.length ? ` · $${spent.toFixed(2)} out so far, about $${proj.toFixed(2)} at their finish` : '';
      sub = `${atSea.length ? `at sea: ${esc(atSea.join(', '))} · ` : ''}${queued} queued · clear ${esc(clockAt(lastEnd))}${cost}`;
    }
    else if (ln.kind === 'charter' && ln.can_hire === false) sub = 'idle: no Vast.ai key';
    else {
      const pm = d.purser && typeof d.purser === 'object' ? d.purser : {};
      const abroad = (pm.foreign_expeditions || []).map((x: string) => x.replace(/_/g, ' ')).join(', ');
      sub = `idle: no line is written <span class="mono">vast:</span>, and the purser (${esc(pm.mode || 'off')}) ${abroad ? `lets only ${esc(abroad)} sail abroad` : 'lets no expedition sail abroad'}`
        + (advice.length ? ` · it would send ${advice.length} here (outlined)` : '');
    }
    const empty = !blocks && !ghosts ? `<span class="qlempty">${ln.kind === 'charter' ? 'nothing sailing abroad' : 'nothing queued'}</span>` : '';
    const grid = tickAt.map((m) => `<span class="qlgrid" style="left:${pct(m)}"></span>`).join('');
    return `<div class="qlane"><div class="qlhead"><b>${esc(LANE_NAME[ln.lane] || ln.lane)}</b> <span class="s">${esc(ln.lane)} lane · ${seats}</span><div class="s">${sub}</div></div><div class="qltrack">${grid}${blocks}${ghosts}${empty}</div></div>`;
  }).join('');
  const axis = tickAt.map((m) => `<span class="qltick" style="left:${pct(m)}">${esc(clockAt(m))}</span>`).join('');
  const legend = [['p300k', '300k'], ['p1m', '1m'], ['p9m', '9m'], ['p21m', '21m and up'], ['pstep', 'a step'], ['pintel', 'S4 intelligence']]
    .map(([c, l]) => `<span><i class="qlswatch ${c}"></i>${l}</span>`).join('');
  return `<div class="qlanes" aria-label="the queue by lane"><div class="qlane qlaxisrow"><div class="qlhead"></div><div class="qlaxis"><span class="qltick qlnow">now</span>${axis}<span class="qltick qlend">${esc(clockAt(total))}</span></div></div>${tracks}<div class="qllegend s">${legend}<span><i class="qlswatch p9m sea"></i>at sea</span><span><i class="qlswatch p9m ghost"></i>the purser's advice</span></div></div>`;
}
