// The Expeditions page (UI.md "Expeditions"), as typed HTML renderers: the queue landing (waters plan,
// the queue at a glance, every voyage), the expedition cards, one expedition (its header, outcomes,
// levers, ships, readings and the instruments only some expeditions carry: the fit, the census, the
// knockout, the induction head and the climb), and the observation deck's star chart and Nevermore
// flow. The island owns the route, the tabs, the data and the events; these are pure functions of the
// payloads, kept out of dashboard.ts so the browser and the server render the same markup.
//
// Nothing here may import lib/charts, lib/stages, lib/panel or lib/reader at module load: the island
// is server-rendered, and those touch `document`/Plotly when they load. The chart drawers live in
// views/expedition-charts.ts and are imported inside the island's effects.

import { CARD_FACE } from '../../lib/deck';
import { big, esc, fmt, signed } from '../../lib/format';
import { alertCls, btnCls as shadcnBtnCls, cardCls, emptyCls, hoverCardCls, pillCls, toggleCls as shadcnToggleCls } from '../../lib/ui';
import { modelHash, shipHash } from '../router';
import { STAR_LABEL, starHeadline, statusPill } from './helpers';

// the ⓘ beside a metric heading. lib/info wires its popover listeners at module load, so it cannot be
// imported by this server-rendered module: the chip is drawn here and the island loads lib/info in an
// effect to place it.
const FT_HELP: [string, string, string] = ['The Forgotten Tomes score', 'Lower', 'Bits per byte on 16 period books released on Gutenberg after Qwen 3.8 appeared, so no Qwen model can have trained on them. The same number for Thorp and for Qwen, whatever their tokenisers: the yardstick for the order-of-magnitude gate.'];
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
  runs: Run[]; ships: Ship[]; stars?: string[]; learned?: string; next_steps?: string[];
  outcomes?: Outcome[]; levers?: Lever[]; stop: { max_runs: number; about?: string };
  fit?: Fit | null;
  plan?: { n: number; kind: string; name: string; detail?: string; queue?: string }[];
}
export interface Rung { preset: string; name: string; [key: string]: unknown }

export interface ExpRoute {
  kind: 'overview' | 'queue' | 'list' | 'voyage' | 'table' | 'other';
  key: string | null;
  tab: string;
  qview: 'glance' | 'every';
}

export const ETABS = ['overview', 'plan', 'at-sea', 'findings', 'fleet', 'runs', 'training', 'fitting', 'inside'];
const PREFIXES = new Set(['expeditions', 'voyages']);

/** Parse the expedition routes. `/expeditions` is the queue landing (the working surface); the cards
 *  are `/expeditions/expeditions`; one expedition is `/expeditions/<key>[/<tab>]`; the table is
 *  `/expeditions/<key>/table`. The old `/voyages` prefix is answered too. */
export function parseExpeditionRoute(path: string): ExpRoute {
  const clean = String(path || '/').split('?')[0].split('#')[0];
  const parts = clean.split('/').filter(Boolean);
  const bare: ExpRoute = { kind: 'other', key: null, tab: 'overview', qview: 'glance' };
  if (!parts.length || !PREFIXES.has(parts[0])) return bare;
  const dec = (x: string): string => { try { return decodeURIComponent(x); } catch { return x; } };
  const rest = parts.slice(1).map(dec);
  if (!rest.length) return { kind: 'overview', key: null, tab: 'overview', qview: 'glance' };
  if (rest[0] === 'queue') return { kind: 'queue', key: null, tab: 'overview', qview: rest[1] === 'every' ? 'every' : 'glance' };
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

// ---- the expedition cards (#voyagecards)
export function expeditionCardsHtml(exps: Expedition[], states: Record<string, string>): string {
  return exps.map((v) => {
    const valid = v.runs.filter((r) => !r.set_aside).length;
    const headline = v.learned || starHeadline(v) || 'nothing found yet';
    return `<a class="${cardCls(true, 'card')}" href="/expeditions/${esc(v.key)}">
      <div class="top"><span class="preset">${esc(v.name)}</span>${expPill(states[v.key], v)}</div>
      <div class="goal">${esc(v.goal)}</div>
      <div class="ov">${esc(headline)}</div>
      <div class="foot"><span>${esc(v.fleet || '')} · ${esc(v.preset || '')}</span><span>${valid} of ${v.stop.max_runs} voyages</span></div>
      <div class="foot"><span>${(v.ships || []).length} ship${(v.ships || []).length === 1 ? '' : 's'}${v.stars && v.stars.length ? ` · bound for ${esc(v.stars.map((k) => STAR_LABEL[k] || k).join(', '))}` : ''}</span></div></a>`;
  }).join('') || `<div class="${emptyCls()}">no expeditions yet</div>`;
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
export function queueRowsHtml(d: any, rungs: Rung[]): string {
  const rows = (d.rows || []).map((r: any) => r.kind === 'step'
    ? `<tr class="qstep"><td class="s">${r.n}</td><td colspan="3" class="s" title="${esc(r.cmd)}">↳ then a step: <span class="mono">${esc(r.name)}</span></td></tr>`
    : `<tr${r.status === 'at sea' ? ' class="sel"' : ''}><td class="s">${r.n ?? ''}</td>
      <td>${r.status === 'at sea' ? `<span class="${pillCls('running')}">at sea</span> ` : ''}${(() => {
        const rung = rungs.find((x) => x.preset === r.preset);
        const label = `<span class="mono">${esc(r.preset || r.name)}</span>`;
        return rung ? `<a href="${modelHash(rung, 'training')}" title="open ${esc(String(rung.name).toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-'))}'s training page">${label}</a>` : label;
      })()}${r.missing ? ` <span class="${pillCls('bad')}">no spec</span>` : ''}</td>
      <td>${r.sop ? `<span class="${pillCls('accent')}">v${esc(r.sop)}</span>` : '<span class="s">–</span>'}</td>
      <td class="s">${r.status === 'at sea' ? 'sailing' : sailsIn(r.starts_in_min, !!r.at_least)}</td></tr>`).join('')
    || `<tr><td colspan="4" class="${emptyCls(true)}">the queue is empty</td></tr>`;
  return rows;
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
  return `<div class="obsship">
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
export function deckHtml(d: Observation, sky: Record<string, SkyViewState>, expeditionName: string): string {
  if (d.at_sea && d.at_sea.length) return d.at_sea.map((r) => deckShipHtml(r, skyStateOf(sky[r.run_id]))).join('');
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

// ---- the SOP cards (#expeditions; /api/expeditions/overview .sops): one card per version that states an aim
export function sopCardsHtml(d: any): string {
// the SOP cards: the page's subject is the standard (9 November): one card per version that states an aim, its art
  // and its goals. The running one comes first; the fleet's older groupings stay for the other tabs.
  const sops = d.sops || [];
  const cards = sops.length ? `<div class="sopcards">${sops.map((e: any) => `<a class="sopcard${e.at_sea ? ' atsea' : ''}" href="${e.expedition ? `/expeditions/${esc(e.expedition)}` : '/shipyard/training'}" title="${e.expedition ? `open the ${esc(e.expedition)} expedition` : 'open the SOP in the shipyard'}">
      ${e.art ? `<img class="sopart" src="/art/${esc(e.art)}.png" alt="" loading="lazy">` : '<div class="sopart"></div>'}
      <div class="sopbody">
        <div class="sophead"><b>${esc(e.expedition_name || `SOP v${e.version}`)}</b><span class="s">SOP v${esc(e.version)}</span>${e.at_sea ? `<span class="${pillCls('running')}">at sea</span>` : `<span class="${pillCls('')}">${e.finished ? 'in port' : 'planned'}</span>`}<span class="s">${e.at_sea ? `${e.at_sea} voyage${e.at_sea === 1 ? '' : 's'} out` : e.finished ? `${e.finished} voyage${e.finished === 1 ? '' : 's'} home` : 'not sailed'}</span></div>
        <div class="k">its goals</div>
        <ul class="sopgoals">${(e.goals || []).map((g: any) => `<li><b>${esc(typeof g === 'string' ? g : g.text)}</b>${typeof g === 'string' || !g.detail ? '' : ` <span class="s">— ${esc(g.detail)}</span>`}</li>`).join('')}</ul>
      </div></a>`).join('')}</div>` : '';
  return cards;
}
