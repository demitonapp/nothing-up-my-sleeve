// The Discoveries page's dense renderers, typed out of the view monolith (scripts/dashboard.ts): the
// trick registry and its route, the chains table, one trick's page, one chain's climb, the star grid,
// the head chart, the deck, the traits and the chaining method. Pure functions returning HTML strings,
// as in views/governance.ts: the island owns the shell, the route and the state; this module owns the
// markup and the numbers. Chart drawers are async and import lib/charts (ECharts) lazily, so the server
// render of the island never pulls ECharts in.
//
// rungEvidence/gradeNote/leadNote mirror views/chains.ts, which cannot be imported here: it imports
// lib/charts at module load, and the islands are server-rendered.

import { CARD_FACE } from '../../lib/deck';
import { big, esc, fmt, fmtParams, signed } from '../../lib/format';
import { cardCls, emptyCls, pillCls } from '../../lib/ui';
import { modelHash, shipHash } from '../router';
import { ART_CARDS, cardArt, cardBadge } from './helpers';

// ---- the payloads (/api/discoveries and friends), typed to the fields the page reads

export interface Rung {
  preset: string;
  name: string;
  total: number;
}

export interface DiscShip {
  run_id: string;
  name: string;
  ship?: string | null;
  ship_key?: string | null;
  ship_name?: string | null;
  preset?: string | null;
  steps_to_lit?: number | null;
  shared_steps_to_lit?: number | null;
  best?: number | null;
  performed_at?: number | null;
  best_share?: number | null;
  floor?: number | null;
}

export interface Star {
  key: string;
  name: string;
  level?: number | null;
  rests_on?: string[] | null;
  threshold: number;
  about?: string;
  ships: DiscShip[];
}

export interface FleetTrick {
  key: string;
  name: string;
  metric?: string;
  threshold?: number;
  min_score?: number | null;
  evaluator?: string | null;
  leads_to?: string | null;
  cutoff?: number | null;
  viable?: boolean;
  ships: DiscShip[];
}

export interface KnownTrick {
  key: string;
  name: string;
  waypoint?: string;
  does: string;
  gate?: boolean;
  taught?: boolean;
  fleet?: string | null;
  stars: string[];
  field_params?: number | null;
  field_at?: string;
  field_band: string;
  field_band_rank: number;
  sure: string;
  target_class?: string | null;
  leads_to?: string | null;
  rests_on: string[];
  field_models?: string;
  source?: string;
  measure: string;
  reference?: Record<string, number>;
}

export interface Head {
  key: string;
  name: string;
  family: string;
  does: string;
  rests_on: string[];
  expected_from?: string | null;
  expected_why?: string | null;
  star?: string | null;
  measure: string;
  source: string;
  seen_in: string;
  trick?: string | null;
}

export interface TraitShip extends DiscShip {
  found_at?: number | null;
  learned_at?: number | null;
}

export interface ChainRung {
  preset: string;
  title: string;
  summary?: string;
}

export interface ChainRungs {
  rungs?: ChainRung[];
  chains?: string[][];
  grades?: Record<string, unknown>;
  graded_on?: string[];
  reference?: unknown[];
}

export interface Method {
  name: string;
  status?: string;
  trick?: string;
  parts?: { part: string; meaning: string; covered: string }[];
  gaps?: string[];
  controls?: { control: string; does: string }[];
  metric?: string;
  cards?: { card: string; status: string; operation: string }[];
}

export interface Waypoint {
  key: string;
  name: string;
  about: string;
}

export interface DiscData {
  tricks: FleetTrick[];
  stars: Star[];
  traits: { key: string; ships: TraitShip[] }[];
  known_heads: Head[];
  known_tricks: KnownTrick[];
  chain_rungs: ChainRungs;
  methods: Record<string, Method>;
  card_verdicts: Record<string, unknown>;
  waypoints: Waypoint[];
}

// ---- helpers shared by the drawers

const classLink = (rungs: Rung[], preset: string | null | undefined): string => {
  const r = rungs.find((x) => x.preset === preset);
  return r ? `<a href="${modelHash(r)}">${esc(r.preset)} · ${esc(r.name)}</a>` : esc(preset || '–');
};

// classes in ladder order, smallest first; a kind beyond the ladder ranks after them all
export const classRank = (rungs: Rung[]) => (p?: string | null): number => {
  const i = rungs.findIndex((r) => r.preset === p);
  return i < 0 ? 99 : i;
};

const shipLink = (x: DiscShip): string =>
  `<a href="${x.ship_key ? shipHash(x.ship_key, x.name) : shipHash(x.name)}">${esc(x.ship_name || x.ship || x.name)}</a>`;

const TRAIT_NAME = (t: string): string =>
  t.startsWith('family/') ? `${t.slice(7)} (language family)` : ({ fiction: 'Fiction', verse: 'Verse', first_person: 'First person' } as Record<string, string>)[t] || t;

export const FAMILY: Record<string, string> = {
  position: 'position',
  copying: 'copying',
  circuit: 'the indirect-object circuit',
  suppression: 'suppression',
  structure: 'grammar and reference',
  latent: 'latent state',
  task: 'the task',
};

// ---- the star cards (the Stars subtab): every star Nothing up my sleeve measures, as a playing card

export const starsCardsHtml = (d: DiscData): string => {
  const byName = Object.fromEntries(d.stars.map((s) => [s.key, s.name]));
  return d.stars
    .map((s) => {
      const lit = s.ships.filter((x) => x.steps_to_lit != null).sort((a, b) => (a.steps_to_lit as number) - (b.steps_to_lit as number));
      const shared = s.ships
        .filter((x) => x.shared_steps_to_lit != null)
        .sort((a, b) => (a.shared_steps_to_lit as number) - (b.shared_steps_to_lit as number));
      const best = [...s.ships].sort((a, b) => (b.best ?? -1) - (a.best ?? -1))[0];
      const first = lit[0];
      const firstShared = shared[0];
      const state: [string, string] = lit.length ? ['good', 'lit'] : shared.length ? ['accent', 'lit shared'] : ['', 'not lit yet'];
      const vb = cardBadge(d.card_verdicts, s.key);
      return `<div class="${cardCls(false, `card${lit.length ? ' lit' : ''}${ART_CARDS.has(s.key) ? ' playing' : ''}`)}">${cardArt(s.key)}${vb ? `<div class="vrow">${vb}</div>` : ''}
      <div class="top"><span class="preset">${esc(s.name)}</span><span class="${pillCls(state[0])}" title="lit: one head at the threshold; lit shared: the best layer's two strongest heads together">${state[1]}</span></div>
      <div class="job">level ${s.level}${s.rests_on && s.rests_on.length ? ` · rests on ${esc(s.rests_on.map((k) => byName[k] || k).join(', '))}` : ''} · lit at ${s.threshold}</div>
      <div class="ov">${esc(s.about || '')}</div>
      <div class="foot"><span>${first ? `first lit by ${shipLink(first)} at step ${first.steps_to_lit}` : best && best.best != null ? `nearest: ${shipLink(best)} at ${fmt(best.best)}` : 'no readings yet'}</span></div>
      ${firstShared ? `<div class="foot"><span>first lit shared by ${shipLink(firstShared)} at step ${firstShared.shared_steps_to_lit} (two heads together)</span></div>` : ''}
      <div class="foot"><span>lit on ${lit.length}${shared.length ? `, lit shared on ${shared.length},` : ''} of ${s.ships.length} voyages measured</span></div></div>`;
    })
    .join('');
};

// ---- the traits (the Traits view): what a ship's hidden state tells apart

const firstOf = (ships: TraitShip[], k: 'found_at' | 'learned_at'): TraitShip | undefined =>
  ships.filter((x) => x[k] != null).sort((a, b) => (a[k] as number) - (b[k] as number))[0];

export const traitsHtml = (d: DiscData): { head: string; body: string } => {
  const head = '<tr><th>trait</th><th>ships measured</th><th>found by</th><th>first found</th><th>learned by</th><th>first learned</th><th>best held-out AUC</th></tr>';
  const body =
    d.traits
      .map((t) => {
        const f = firstOf(t.ships, 'found_at');
        const l = firstOf(t.ships, 'learned_at');
        const best = [...t.ships].sort((a, b) => (b.best ?? -1) - (a.best ?? -1))[0];
        const who = (x: TraitShip | undefined, k: 'found_at' | 'learned_at'): string =>
          x ? `${shipLink(x)} (${esc(x.preset || '')}) at step ${x[k]}` : 'not yet';
        return `<tr${l || f ? ` data-run="${esc((l || f)!.run_id)}" tabindex="0"` : ''}><td><b>${esc(TRAIT_NAME(t.key))}</b></td><td>${t.ships.length}</td>
      <td>${t.ships.filter((x) => x.found_at != null).length}</td><td>${who(f, 'found_at')}</td>
      <td>${t.ships.filter((x) => x.learned_at != null).length}</td><td>${who(l, 'learned_at')}</td><td>${best && best.best != null ? `${fmt(best.best)} (${esc(best.ship_name || best.ship || best.name)})` : '–'}</td></tr>`;
      })
      .join('') || `<tr><td colspan="7" class="${emptyCls(true)}">no ship has trait probes yet</td></tr>`;
  return { head, body };
};

// ---- the star chart (the table of every known kind of head, and its state in Nothing up my sleeve)

const trickNote = (d: DiscData, h: Head): string => {
  const t = h.trick && d.tricks.find((x) => x.key === h.trick);
  if (!t) return '';
  const n = t.ships.filter((x) => x.performed_at != null).length;
  return `<br><span class="s">its trick, ${esc(t.name)}: ${t.ships.length ? `performed on ${n} of ${t.ships.length} sailings` : 'readings start with the next ship to sail'}</span>`;
};

// a kind of head's state in Nothing up my sleeve: not measured, measured without readings, lit, lit shared or best so far
const headState = (d: DiscData, h: Head): string => {
  if (!h.star) return `<td data-sort="9" class="s" title="${esc(h.measure)}">not measured yet · <i>${esc(h.measure)}</i>${trickNote(d, h)}</td>`;
  const st = d.stars.find((x) => x.key === h.star);
  if (!st) return '<td data-sort="5">measured</td>';
  if (!st.ships.length) return `<td data-sort="3"><span class="${pillCls('')}">measured</span> a star: ${esc(st.name)} · readings start with the next ship to sail · threshold ${st.threshold}</td>`;
  const lit = st.ships.filter((x) => x.steps_to_lit != null);
  const sh = st.ships.filter((x) => x.shared_steps_to_lit != null);
  const best = Math.max(-1, ...st.ships.map((x) => x.best ?? -1));
  const pill = lit.length ? `<span class="${pillCls('good')}">lit</span>` : sh.length ? `<span class="${pillCls('accent')}">lit shared</span>` : `<span class="${pillCls('')}">not lit yet</span>`;
  return `<td data-sort="${lit.length ? 0 : sh.length ? 1 : 2}">${pill} a star: ${esc(st.name)} · ${lit.length ? `lit on ${lit.length}` : sh.length ? `lit shared on ${sh.length}` : `best ${fmt(best)}`} of ${st.ships.length} sailings · threshold ${st.threshold}${trickNote(d, h)}</td>`;
};

// the smallest class where any sailing has lit a measured kind (one head first, else shared)
const firstLitIn = (d: DiscData, h: Head, rungs: Rung[]): string => {
  const rank = classRank(rungs);
  const st = h.star && d.stars.find((x) => x.key === h.star);
  if (!st) return '<td data-sort="99">–</td>';
  const lit = st.ships
    .filter((x) => x.steps_to_lit != null || x.shared_steps_to_lit != null)
    .sort((a, b) => rank(a.preset) - rank(b.preset));
  if (!lit.length) return '<td data-sort="98" class="s">not lit yet</td>';
  const x = lit[0];
  const below = rank(x.preset) < rank(h.expected_from);
  return `<td data-sort="${rank(x.preset)}">${classLink(rungs, x.preset)} · ${x.steps_to_lit != null ? 'lit' : 'lit shared'} by ${shipLink(x)}${below ? ` <span class="${pillCls('good')}" title="lit below the size expected to reach it">below expectation</span>` : ''}</td>`;
};

export const headsHtml = (d: DiscData, rungs: Rung[], family: string): { count: string; body: string } => {
  const heads = d.known_heads || [];
  const rows = heads.filter((h) => !family || h.family === family);
  const byKey = Object.fromEntries(heads.map((h) => [h.key, h.name]));
  const count = `${rows.length} kinds · ${rows.filter((h) => h.star).length} measured by Nothing up my sleeve`;
  const body = rows
    .map(
      (h) => `<tr${h.star ? ' class="measured"' : ''}><td><b>${esc(h.name)}</b></td><td>${esc(FAMILY[h.family] || h.family)}</td>
    <td>${esc(h.does)}</td><td>${(h.rests_on || []).length ? esc(h.rests_on.map((k) => byKey[k] || k).join(', ')) : '–'}</td>
    <td data-sort="${classRank(rungs)(h.expected_from)}" title="${esc(h.expected_why || '')}">${h.expected_from ? classLink(rungs, h.expected_from) : 'beyond the ladder'}</td>${firstLitIn(d, h, rungs)}${headState(d, h)}
    <td class="s">${esc(h.source)}</td><td class="s">${esc(h.seen_in)}</td></tr>`,
    )
    .join('');
  return { count, body };
};

// the families the star chart can be filtered by, in the payload's order
export const headFamilies = (d: DiscData): { key: string; label: string }[] => {
  const fams = [...new Set((d.known_heads || []).map((h) => h.family))];
  return fams.map((f) => ({ key: f, label: FAMILY[f] || f }));
};

// ---- Nothing up my sleeve's progress on a trick, from the fleet's readings (/api/discoveries tricks)
export interface TrickProgress {
  cell: string;
  state: string;
  cls: string;
}

export const trickProgress = (d: DiscData, kt: KnownTrick, rungs: Rung[]): TrickProgress => {
  const rank = classRank(rungs);
  const t = kt.fleet ? d.tricks.find((x) => x.key === kt.fleet) : undefined;
  if (!kt.fleet) return { cell: '<td data-sort="9" class="s">not measured yet</td>', state: 'not measured yet', cls: '' };
  if (t && t.viable === false) return { cell: '<td data-sort="10" class="s">not viable on Gutenberg in English</td>', state: 'not viable', cls: '' };
  if (t && !t.evaluator)
    return { cell: `<td data-sort="8" class="s">pre-registered${t.cutoff ? ` (cutoff ${t.cutoff})` : ''} · evaluator not built yet</td>`, state: 'pre-registered', cls: '' };
  if (!t || !t.ships.length) return { cell: '<td data-sort="8" class="s">measured · readings start with the next ship to sail</td>', state: 'measured, no readings yet', cls: '' };
  const done = t.ships.filter((x) => x.performed_at != null).sort((a, b) => rank(a.preset) - rank(b.preset) || (a.performed_at as number) - (b.performed_at as number));
  if (done.length) {
    const x = done[0];
    return { cell: `<td data-sort="${rank(x.preset)}"><span class="${pillCls('good')}">performed</span> at ${classLink(rungs, x.preset)} by ${shipLink(x)}, step ${x.performed_at}</td>`, state: 'performed', cls: 'good' };
  }
  const best = [...t.ships].sort((a, b) => (b.best ?? 0) - (a.best ?? 0))[0];
  return { cell: `<td data-sort="7"><span class="${pillCls('')}">not yet</span> best ${fmt(best.best)} of ${t.threshold} (${classLink(rungs, best.preset)})</td>`, state: 'not performed yet', cls: '' };
};

// A smaller test leads to a bigger one: the note under a trick's name (mirrors views/chains.ts).
const leadNote = (t: { key: string; name: string; leads_to?: string | null }, kts: { key: string; name: string; leads_to?: string | null }[]): string => {
  const name = (k: string): string => (kts.find((x) => x.key === k) || {}).name || k;
  const led = kts.filter((x) => x.leads_to === t.key);
  return (t.leads_to ? `<div class="lead">→ leads to <a href="/orbitals/demiton/discoveries/${esc(t.leads_to)}">${esc(name(t.leads_to))}</a></div>` : '')
    + (led.length ? `<div class="lead">← led by ${led.map((x) => `<a href="/orbitals/demiton/discoveries/${esc(x.key)}">${esc(x.name)}</a>`).join(', ')}</div>` : '');
};

// A chain's grade from many models (mirrors views/chains.ts).
const gradeNote = (g: any, nameOf: (k: string) => string, full?: boolean): string => {
  if (!g) return `<span class="${pillCls('')}" title="no grading written yet (the chain grades, s4.outside_readings)">not graded yet</span>`;
  if (g.graded) return `<span class="${pillCls('good')}" title="harder at every rung: no model passes a rung it fails below, fewer pass each rung, and every rung is reached">graded</span>`;
  const bits: string[] = [];
  if (g.inversions.length) bits.push(`${g.inversions.length} inversion${g.inversions.length > 1 ? 's' : ''}`);
  if (g.rising.length) bits.push(`more pass ${g.rising.map(nameOf).join(', ')} than the rung below`);
  if (g.unreached.length) bits.push(`${g.unreached.map(nameOf).join(', ')} unreached`);
  const tip = g.inversions.map((x: any) => `${x.model} performs ${nameOf(x.rung)} but fails ${x.fails_below.map(nameOf).join(', ')}`).join('\n');
  return `<span class="${pillCls('bad')}" title="${esc(tip)}">not graded</span> <span class="gnote">${esc(bits.join(' · '))}</span>`
    + (full && g.inversions.length ? `<details class="ginv"><summary>the inversions</summary><ul>${g.inversions.map((x: any) => `<li><b>${esc(x.model)}</b> performs ${esc(nameOf(x.rung))} but fails ${esc(x.fails_below.map(nameOf).join(', '))}</li>`).join('')}</ul></details>` : '');
};

// One rung's best lift per size (mirrors views/chains.ts). ✓ performed, ▲ passed below its size,
// ⚠ passed below its size while a bigger class fails it.
type EvidenceFt = { threshold?: number; evaluator?: unknown; ships: DiscShip[]; min_score?: number | null; viable?: boolean } | null | undefined;
const rungEvidence = (t: { target_class?: string | null }, ft: EvidenceFt, rank: (p: string) => number, opts: { floor?: boolean } = {}): string => {
  const thr = ft ? ft.threshold ?? 0.1 : 0.1;
  if (!ft || (!ft.evaluator && !ft.ships.length)) {
    return `<div class="s">${ft && ft.viable === false ? 'not viable' : ft ? 'evaluator not built yet' : 'not measured'}</div>`;
  }
  if (!ft.ships.length) return '<div class="s">no readings yet</div>';
  const by: Record<string, { best: number; share: number | null; done: boolean; floor?: number }> = {};
  for (const x of ft.ships) {
    const b = by[x.preset as string] || (by[x.preset as string] = { best: -Infinity, share: null, done: false });
    b.best = Math.max(b.best, x.best as number);
    b.done = b.done || x.performed_at != null;
    if (x.best_share != null) b.share = Math.max(b.share ?? 0, x.best_share);
    if (x.floor != null) b.floor = Math.max(b.floor ?? -Infinity, x.floor);
  }
  const goal = rank(t.target_class ?? '');
  const failedAbove = (p: string): boolean => Object.entries(by).some(([q, b]) => rank(q) > rank(p) && !b.done);
  return Object.entries(by)
    .sort((a, b) => rank(a[0]) - rank(b[0]))
    .map(([p, b]) => {
      const below = b.done && rank(p) < goal;
      const audit = below && failedAbove(p);
      const why = b.done
        ? audit ? 'passed below its size while a bigger class fails it: audit the pairs' : below ? 'passed below its size' : 'performed'
        : b.best >= thr ? `lift at the mark but ${b.share != null ? Math.round(100 * b.share) + '%' : 'too few'} of pairs right, under ${Math.round(100 * (ft.min_score || 0))}%` : 'not performed';
      return `<div class="cr${b.done ? ' lit' : ''}${audit ? ' audit' : ''}" title="${esc(why)}"><span>${esc(p)}</span><b>${b.best >= 0 ? '+' : ''}${fmt(b.best, 2)}${b.share != null ? ` <i>${Math.round(100 * b.share)}%</i>` : ''}${b.done ? ' ✓' : ''}${below ? (audit ? ' ⚠' : ' ▲') : ''}</b>${opts.floor ? `<em>${b.floor != null ? `floor ${b.floor >= 0 ? '+' : ''}${fmt(b.floor, 2)}` : ''}</em>` : ''}</div>`;
    })
    .join('');
};

// The reference ladder's readings on one rung, as evidence rows; without the toggle, the one reference
// tricks.py names.
const refRows = (key: string, refs: any[] | undefined, ref: [string, number] | undefined, sign: (v: number | null | undefined) => string, chainRef: boolean): string => {
  if (chainRef && refs && refs.length) {
    return refs
      .map((m) => {
        const v = m.tricks[key];
        if (!v) return `<div class="cr ref"><span>${esc(m.short)}</span><b>–</b></div>`;
        return `<div class="cr ref${v.performed ? ' lit' : ''}"><span>${esc(m.short)}</span><b>${sign(v.lift)}${v.score != null ? ` <i>${Math.round(100 * v.score)}%</i>` : ''}${v.performed ? ' ✓' : ''}</b></div>`;
      })
      .join('');
  }
  return ref ? `<div class="cr ref"><span>${esc(ref[0])}</span><b>${sign(ref[1])}</b></div>` : '';
};

// ---- the registry of tricks (the Registry subtab), and the seven waypoints' route (the Quantum subtab)

export const trickRouteHtml = (d: DiscData): string => {
  const kts = d.known_tricks || [];
  const wps = d.waypoints || [];
  return wps
    .map((w, i) => {
      const mine = kts.filter((t) => t.waypoint === w.key);
      const gates = mine.filter((t) => t.gate);
      return `<div class="step"><div class="n">${i + 1}</div><div class="nm">${esc(w.name)}</div><div class="ab">${esc(w.about)}</div>
      <div class="gt">${gates.map((t) => `<a href="/orbitals/demiton/discoveries/${esc(t.key)}">◆ ${esc(t.name)}</a>`).join('')}${mine.filter((t) => t.leads_to).map((t) => `<a class="ld" href="/orbitals/demiton/discoveries/${esc(t.key)}" title="leads to ${esc((kts.find((x) => x.key === t.leads_to) || {}).name || t.leads_to)}">↗ ${esc(t.name)}</a>`).join('')}</div><div class="ct">${mine.length} tricks</div></div>`;
    })
    .join('<div class="arrow">→</div>');
};

export const skillLadderHtml = (d: DiscData): string => {
  const kts = d.known_tricks || [];
  const wps = d.waypoints || [];
  return `<div class="skillgrid">${wps.map((w, i) => {
    const mine = kts.filter((t) => t.waypoint === w.key);
    const skills = mine.map((t) => `<a class="skill${t.fleet ? ' measured' : ''}" href="/orbitals/demiton/discoveries/${esc(t.key)}">
      <b>${t.gate ? '◆ ' : ''}${esc(t.name)}</b><span>${esc(t.does)}</span>
      <em>${t.fleet ? 'measured by Nothing up my sleeve' : 'not measured yet'}${t.target_class ? ` · goal ${esc(t.target_class)}` : ''}${t.taught ? ' · taught' : ''}</em></a>`).join('');
    return `<section class="skillstep"><h3><span class="n">${i + 1}</span> ${esc(w.name)} <span class="s">${mine.length} skill${mine.length === 1 ? '' : 's'}</span></h3>
      <p class="s">${esc(w.about)}</p><div class="skills">${skills || '<div class="s">no skill is charted on this step yet</div>'}</div></section>`;
  }).join('')}</div>`;
};

export const trickBands = (d: DiscData): { rank: number; label: string }[] =>
  [...new Map((d.known_tricks || []).map((t) => [t.field_band_rank, t.field_band])).entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([rank, label]) => ({ rank, label }));

export const trickRowsHtml = (d: DiscData, rungs: Rung[], waypoint: string, band: string): { count: string; body: string } => {
  const kts = d.known_tricks || [];
  const wps = d.waypoints || [];
  const wpRank = (k?: string): number => wps.findIndex((w) => w.key === k);
  const wpName = (k?: string): string => (wps.find((w) => w.key === k) || {}).name || k || '';
  const rows = kts
    .filter((t) => (!waypoint || t.waypoint === waypoint) && (band === '' || String(t.field_band_rank) === band))
    .sort((a, b) => wpRank(a.waypoint) - wpRank(b.waypoint) || a.field_band_rank - b.field_band_rank);
  const heads = Object.fromEntries((d.known_heads || []).map((h) => [h.key, h.name]));
  const count = `${rows.length} tricks · ${rows.filter((t) => t.fleet).length} measured by Nothing up my sleeve`;
  const body = rows
    .map(
      (t) => `<tr data-trick="${esc(t.key)}" tabindex="0"${t.fleet ? ' class="measured"' : ''}>
    <td data-sort="${wpRank(t.waypoint)}">${esc(wpName(t.waypoint))}</td><td><b>${t.gate ? '◆ ' : ''}${esc(t.name)}</b>${t.taught ? ' <span class="s">(taught)</span>' : ''}${leadNote(t, kts)}</td><td>${esc(t.does)}</td><td data-sort="${t.field_params}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td><td class="s">${esc(t.sure)}</td>
    <td>${t.stars.length ? esc(t.stars.map((k) => heads[k] || k).join(', ')) : '<span class="s">none charted yet</span>'}</td>
    ${trickProgress(d, t, rungs).cell}<td data-sort="${t.target_class ? classRank(rungs)(t.target_class) : 99}">${t.target_class ? classLink(rungs, t.target_class) : t.taught ? '<span class="s">a reference: taught, not read</span>' : trickProgress(d, t, rungs).state === 'not viable' ? '<span class="s">not viable</span>' : '<span class="s">beyond the ladder</span>'}</td></tr>`,
    )
    .join('');
  return { count, body };
};

// ---- one trick (/orbitals/demiton/discoveries/<trick>)

export interface TrickPage {
  found: boolean;
  title: string;
  state: string;
  does: string;
  over: string;
  stars: string;
  track: string;
  // what the chart effect needs: the fleet trick (its key) and the known trick's name and reference readings
  chart: { fleetKey: string; name: string; reference?: Record<string, number> } | null;
  pair: { title: string; chart: { fleetKey: string; name: string; reference?: Record<string, number> } | null; empty: string | null } | null;
}

export const trickPageHtml = (d: DiscData, rungs: Rung[], key: string | null): TrickPage => {
  const t = (d.known_tricks || []).find((x) => x.key === key);
  const empty: TrickPage = { found: false, title: `no trick called ${key ?? ''}`, state: '', does: '', over: '', stars: '', track: '', chart: null, pair: null };
  if (!t) return empty;
  const p = trickProgress(d, t, rungs);
  const ft = t.fleet ? d.tricks.find((x) => x.key === t.fleet) : undefined;
  const tgt = t.target_class && rungs.find((r) => r.preset === t.target_class);
  const wp = (d.waypoints || []).find((w) => w.key === t.waypoint);
  const tname = Object.fromEntries((d.known_tricks || []).map((x) => [x.key, x.name]));
  // a trick Nothing up my sleeve wrote itself has no field band: say that once rather than printing two 'not shown'
  const ownTest = t.field_params == null && /Nothing up my sleeve's own test/i.test(t.field_at || '');
  const over = [
    ['waypoint', `${esc(wp ? wp.name : t.waypoint)}${t.gate ? ' · <b>◆ a gate</b>: performed before a ship moves on' : ' · a milestone'}`],
    ['rests on', (t.rests_on || []).length ? t.rests_on.map((k) => `<a href="/orbitals/demiton/discoveries/${esc(k)}">${esc(tname[k] || k)}</a>`).join(', ') : '–'],
    ...(leadNote(t, d.known_tricks || []) ? [['leads', leadNote(t, d.known_tricks || [])]] : []),
    ...(() => {
      const ch = ((d.chain_rungs || {}).chains || []).find((c) => c.includes(t.key) || (t.fleet && c.includes(t.fleet)));
      if (!ch) return [];
      const end = ch[ch.length - 1];
      const en = (d.known_tricks || []).find((x) => x.key === end || x.fleet === end);
      return [['the climb', `${ch.indexOf(t.fleet || t.key) === ch.length - 1 ? '' : `step ${ch.indexOf(t.fleet || t.key) + 1} of ${ch.length} on `}<a href="/orbitals/demiton/discoveries/chains/${esc(end)}"><b>${esc(en ? en.name : end)}</b>: the climb, step by step</a>`]];
    })(),
    [ownTest ? 'where it comes from' : 'the field shows it at', ownTest ? `<b>Nothing up my sleeve's own test</b> <span class="s">(not from the field${t.field_models ? `; ${esc(t.field_models)} for scale` : ''})</span>` : `<span class="sizeband">${esc(t.field_band)}</span> parameters · ${esc(t.field_at)} <span class="s">(${esc(t.sure)})</span>`],
    ['in', ownTest ? '<span class="s">Nothing up my sleeve\'s own test</span>' : esc(t.field_models)],
    ['first shown by', `<span class="s">${esc(t.source)}</span>`],
    ["Nothing up my sleeve's goal class", t.target_class ? `${classLink(rungs, t.target_class)}${tgt ? ` · ${big(tgt.total)} parameters` : ''}` : t.taught ? 'none: the field shows it only when taught the task' : 'beyond the ladder: a horizon'],
    ['how Nothing up my sleeve measures it', ft ? `<span class="mono">${esc(ft.metric)}</span>, performed at ${ft.threshold}` : `not yet: ${esc(t.measure)}`],
  ]
    .map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`)
    .join('');
  // the stars needed
  const hs = (t.stars || []).map((k) => (d.known_heads || []).find((h) => h.key === k)).filter((h): h is Head => Boolean(h));
  const byKey = Object.fromEntries((d.known_heads || []).map((h) => [h.key, h.name]));
  const stars = hs.length
    ? hs
        .map(
          (h) => `<tr><td><b>${esc(h.name)}</b></td><td>${esc(h.does)}</td>
    <td>${(h.rests_on || []).length ? esc(h.rests_on.map((k) => byKey[k] || k).join(', ')) : '–'}</td>
    <td data-sort="${classRank(rungs)(h.expected_from)}">${h.expected_from ? classLink(rungs, h.expected_from) : 'beyond the ladder'}</td>${firstLitIn(d, h, rungs)}${headState(d, h)}</tr>`,
        )
        .join('')
    : '<tr><td colspan="6" class="' + emptyCls(true) + '">no kind of head is charted for this trick yet; it may be done in the feed-forward layers, or by heads not yet described</td></tr>';
  // Nothing up my sleeve's tracking, size by size
  const thr = ft ? ft.threshold : null;
  const track = rungs
    .map((r) => {
      const mine = ft ? ft.ships.filter((x) => x.preset === r.preset) : [];
      const done = mine.filter((x) => x.performed_at != null).sort((a, b) => (a.performed_at as number) - (b.performed_at as number));
      const orders = t.field_params ? Math.log10(t.field_params / r.total) : null;
      const best = mine.length ? Math.max(...mine.map((x) => x.best as number)) : null;
      const isT = r.preset === t.target_class;
      return `<tr${isT ? ' class="target"' : ''}><td>${classLink(rungs, r.preset)}${isT ? ` <span class="${pillCls('accent')}">target</span>` : ''}</td><td data-sort="${r.total}">${big(r.total)}</td>
      <td data-sort="${orders ?? ''}">${orders == null ? `<span class="s" title="${ownTest ? "this is Nothing up my sleeve's own test, not a field result" : 'no field band for this trick'}">${ownTest ? '–' : 'the field has not shown it'}</span>` : orders >= 0 ? `${orders.toFixed(1)} orders of magnitude smaller` : `${(-orders).toFixed(1)} orders larger`}</td>
      <td>${ft ? mine.length : '–'}</td><td>${ft ? (mine.length ? `${done.length} of ${mine.length}` : '–') : '–'}</td>
      <td>${best != null ? `${fmt(best)} <span class="s">of ${thr}</span>` : '–'}</td><td>${done.length ? `${shipLink(done[0])} at step ${done[0].performed_at}` : '–'}</td></tr>`;
    })
    .join('') + (ownTest ? `<tr><td colspan="7" class="s">Nothing up my sleeve's own test: there is no field band to compare. ${Object.entries(t.reference || {}).map(([n, v]) => `${esc(n)} lifts ${fmt(Number(v), 2)}`).join(', ') || 'No outside model is charted'} for scale.</td></tr>` : '');
  // the partner beside it: the bigger test a smaller one leads to, or the smaller one that leads here
  const partner = t.leads_to || ((d.known_tricks || []).find((x) => x.leads_to === t.key) || {}).key;
  const pt = partner ? (d.known_tricks || []).find((x) => x.key === partner) : undefined;
  let pair: TrickPage['pair'] = null;
  if (pt) {
    const pf = pt.fleet ? d.tricks.find((x) => x.key === pt.fleet) : undefined;
    const title = `${t.leads_to ? 'It leads to' : 'Led by'} <a href="/orbitals/demiton/discoveries/${esc(pt.key)}">${esc(pt.name)}</a> <span class="note">${t.leads_to ? 'the bigger test this one tracks, on the same evaluator and scale' : 'the smaller test that tracks this one, on the same evaluator and scale'}</span>`;
    const msg = !pf ? 'not measured yet' : pf.viable === false ? 'not viable on Gutenberg in English' : !pf.evaluator ? `pre-registered${pf.cutoff ? ` (cutoff ${pf.cutoff})` : ''}; its evaluator is not built yet` : null;
    pair = { title, chart: msg || !pf ? null : { fleetKey: pf.key, name: pt.name, reference: pt.reference }, empty: msg };
  }
  return {
    found: true,
    title: t.name,
    state: `<span class="${pillCls(p.cls)}">${esc(p.state)}</span>`,
    does: t.does,
    over,
    stars,
    track,
    chart: ft ? { fleetKey: ft.key, name: t.name, reference: t.reference } : null,
    pair,
  };
};

// ---- the scaffold, across every model ------------------------------------------------------------
// How well pinning heads worked: the best reading while they were held, the reading after they were
// faded, how much the fade cost (the drop), and what remains above the floor. A run is only here when
// its spec pinned heads; the table lists every model, including those with no scaffolded voyage.

export interface ScaffoldRow {
  run_id: string; name: string; ship: string; preset: string;
  heads: string[]; hold: number | null; fade: number | null; release: number | null;
  floor: number | null; held: number | null; after: number | null; drop: number | null; kept: number | null;
  verdict: string; total: number;
}

export interface ScaffoldSummary {
  preset: string; n: number; heads: number | null;
  held: number | null; after: number | null; drop: number | null; kept: number | null; floor: number | null;
  heldN: number; fadedN: number; neverN: number;
}

const scMed = (xs: (number | null)[]): number | null => {
  const v = xs.filter((x): x is number => x != null).sort((a, b) => a - b);
  return v.length ? v[Math.floor((v.length - 1) / 2)] : null;
};
const scFrac = (v: any, total: number): number | null => (v == null ? null : Number(v) <= 1 ? Number(v) * total : Number(v));

export const scaffoldRows = (d: any, threshold: number): ScaffoldRow[] => {
  const rows: ScaffoldRow[] = [];
  for (const r of d?.runs || []) {
    const sc = r.scaffold || {};
    const heads = (sc.heads || []) as any[];
    const step = (r.step || []) as number[], value = (r.value || []) as number[];
    if (!heads.length || !step.length) continue;
    const total = Math.max(...step);
    const holdEnd = scFrac(sc.hold, total);
    const fadeEnd = scFrac(sc.fade, total);
    const releaseEnd = scFrac(sc.release, total);
    const pts = step.map((s, i) => ({ s, v: value[i] })).filter((p) => p.v != null);
    const heldPts = holdEnd != null ? pts.filter((p) => p.s <= holdEnd) : pts.filter((p) => fadeEnd == null || p.s <= fadeEnd);
    const hasFade = sc.fade != null || sc.release != null;
    const afterStart = releaseEnd ?? fadeEnd;
    const afterPts = hasFade && afterStart != null ? pts.filter((p) => p.s >= afterStart) : [];
    // the best reading while the heads were held: how well the scaffold worked, before the fade
    const held = heldPts.length ? Math.max(...heldPts.map((p) => p.v)) : null;
    const after = hasFade && afterPts.length ? afterPts[0].v : null;
    const floor = r.floor != null ? Number(r.floor) : (pts.length ? pts[0].v : null);
    const drop = held != null && after != null ? held - after : null;
    const kept = after != null && floor != null ? after - floor : null;
    const verdict = held == null ? 'no reading while held'
      : held < threshold ? 'never reached the mark'
      : !hasFade ? 'still held (no fade)'
      : after == null ? 'the fade was not reached'
      : after >= threshold ? 'held after the fade'
      : drop != null && drop > 0.1 ? 'dropped at the fade'
      : 'faded below the mark';
    rows.push({ run_id: r.run_id, name: r.name, ship: r.ship || r.name, preset: r.preset || '–',
      heads: heads.map((h) => String(h.card || 'head')), hold: sc.hold ?? null, fade: sc.fade ?? null, release: sc.release ?? null,
      floor, held, after, drop, kept, verdict, total });
  }
  return rows;
};

export const scaffoldSummary = (rows: ScaffoldRow[], presets: string[], threshold: number): ScaffoldSummary[] => {
  const all = [...new Set([...presets, ...rows.map((r) => r.preset)])];
  return all.map((preset) => {
    const mine = rows.filter((r) => r.preset === preset);
    return {
      preset, n: mine.length, heads: scMed(mine.map((r) => r.heads.length)),
      held: scMed(mine.map((r) => r.held)), after: scMed(mine.map((r) => r.after)),
      drop: scMed(mine.map((r) => r.drop)), kept: scMed(mine.map((r) => r.kept)), floor: scMed(mine.map((r) => r.floor)),
      heldN: mine.filter((r) => r.held != null && r.held >= threshold).length,
      fadedN: mine.filter((r) => r.after != null && r.held != null && r.held >= threshold && r.after < threshold).length,
      neverN: mine.filter((r) => r.held != null && r.held < threshold).length,
    };
  });
};

export const scaffoldHtml = (rows: ScaffoldRow[], summary: ScaffoldSummary[], rungs: Rung[], threshold: number): string => {
  const head = '<tr><th>model</th><th>voyages with a scaffold</th><th>heads pinned</th><th>held</th><th>after the fade</th><th>drop</th><th>kept above the floor</th><th>verdict</th></tr>';
  const body = summary.map((s) => `<tr${s.n ? '' : ' class="none"'}><td>${classLink(rungs, s.preset)}</td>
    <td>${s.n || '<span class="s">none</span>'}</td><td>${s.heads ?? '–'}</td>
    <td>${s.held != null ? `${fmt(s.held)} <span class="s">of ${threshold}</span>` : '–'}</td>
    <td>${s.after != null ? fmt(s.after) : '–'}</td>
    <td>${s.drop != null ? signed(s.drop) : '–'}</td><td>${s.kept != null ? signed(s.kept) : '–'}</td>
    <td>${s.n ? `${s.heldN} held${s.fadedN ? ` · ${s.fadedN} faded` : ''}${s.neverN ? ` · ${s.neverN} never` : ''}` : '<span class="s">no scaffolded voyage</span>'}</td></tr>`).join('');
  const runs = rows.slice().sort((a, b) => a.preset.localeCompare(b.preset) || a.name.localeCompare(b.name)).map((r) => `<tr><td>${esc(r.preset)}</td><td><a href="${shipHash(r.name)}">${esc(r.name)}</a><div class="s">${esc(r.ship)}</div></td>
    <td title="${esc(r.heads.join(', '))}">${r.heads.length} <span class="s">${esc(r.heads.join(', '))}</span></td>
    <td>${r.hold != null ? `${Math.round(100 * r.hold)}%` : '–'} → ${r.fade != null ? `${Math.round(100 * r.fade)}%` : '–'}</td>
    <td>${r.held != null ? fmt(r.held) : '–'}</td><td>${r.after != null ? fmt(r.after) : '–'}</td>
    <td>${r.drop != null ? signed(r.drop) : '–'}</td><td>${r.kept != null ? signed(r.kept) : '–'}</td><td>${esc(r.verdict)}</td></tr>`).join('');
  return `<div class="scroll"><table id="scaffoldtable"><thead>${head}</thead><tbody>${body}</tbody></table></div>
    <details class="scaffoldruns"><summary>the voyages, one by one</summary><div class="scroll"><table id="scaffoldruns">
      <thead><tr><th>model</th><th>voyage</th><th>heads</th><th>hold → fade</th><th>held</th><th>after</th><th>drop</th><th>kept</th><th>verdict</th></tr></thead><tbody>${runs}</tbody></table></div></details>`;
};

export const drawScaffoldChart = async (id: string, summary: ScaffoldSummary[], threshold: number, label = 'reading'): Promise<void> => {
  const { plot, layout, C } = await import('../../lib/charts');
  const rows = summary.filter((s) => s.n && (s.held != null || s.after != null));
  if (!rows.length) { const { empty } = await import('../../lib/charts'); empty(id, 'no voyage has pinned a head yet'); return; }
  const x = rows.map((s) => s.preset);
  const traces: any[] = [
    { type: 'bar', name: 'held', x, y: rows.map((s) => s.held), marker: { color: C.blue } },
    { type: 'bar', name: 'after the fade', x, y: rows.map((s) => s.after), marker: { color: C.good } },
  ];
  if (rows.some((s) => s.floor != null)) traces.push({ type: 'bar', name: 'floor', x, y: rows.map((s) => s.floor), marker: { color: C.muted } });
  plot(id, traces, layout({ barmode: 'group', height: 320, xaxis: { title: 'model' }, yaxis: { title: label },
    shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: threshold, y1: threshold, line: { color: C.accent, dash: 'dot' } }],
    annotations: [{ xref: 'paper', x: 1, xanchor: 'right', y: threshold, yanchor: 'bottom', showarrow: false, text: `performed at ${threshold}`, font: { size: 10, color: C.accent } }] }));
};

// ---- the chains table (the Quantum subtab): the explorer's four tests, rung by rung

export const chainsTableHtml = (d: DiscData, rungs: Rung[], chainRef: boolean): { head: string; body: string } => {
  const kts = d.known_tricks || [];
  const byKey = Object.fromEntries(kts.map((t) => [t.key, t]));
  const led = new Set(kts.map((t) => t.leads_to).filter(Boolean));
  const chains = kts
    .filter((t) => t.leads_to && !led.has(t.key))
    .map((start) => {
      const c = [start];
      let t: KnownTrick = start;
      while (t.leads_to && byKey[t.leads_to]) {
        t = byKey[t.leads_to];
        c.push(t);
      }
      return c;
    });
  if (!chains.length) return { head: '', body: `<tr><td class="${emptyCls(true)}">no chains yet</td></tr>` };
  // the columns are the sizes the chains' rungs belong to, smallest first; the longest chains featured first
  const rank = classRank(rungs);
  const cols = [...new Set(chains.flat().map((t) => t.target_class).filter((p): p is string => Boolean(p)))].sort((a, b) => rank(a) - rank(b));
  const cr = d.chain_rungs || {};
  const order = (cr.chains || []).map((c) => c[c.length - 1]);
  const pos = (c: KnownTrick[]): number => {
    const i = order.indexOf(c[c.length - 1].fleet || c[c.length - 1].key);
    return i < 0 ? 99 : i;
  };
  chains.sort((a, b) => pos(a) - pos(b) || b.length - a.length);
  const head = `<tr><th>leads to</th>${cols.map((p, i) => `<th>rung ${i + 1} · ${classLink(rungs, p)}</th>`).join('')}</tr>`;
  const body =
    chains
      .map((c) => {
        const end = c[c.length - 1];
        const at = Object.fromEntries(c.map((t) => [t.target_class, t]));
        const chainKey = end.fleet || end.key;
        const hasPage = (cr.chains || []).some((x) => x[x.length - 1] === chainKey);
        const nameOf = (k: string): string => (byKey[k] || {}).name || k;
        return `<tr><td>${hasPage ? `<a href="/orbitals/demiton/discoveries/chains/${esc(chainKey)}"><b>${esc(end.name)}</b></a>` : `<b>${esc(end.name)}</b>`}<div class="grade">${gradeNote((cr.grades || {})[chainKey], nameOf)}</div>${hasPage ? '<div class="s">the climb, step by step →</div>' : ''}</td>${cols
          .map((p) => at[p])
          .map((t) => {
            if (!t) return '<td class="none"><div class="s">no rung</div></td>';
            const ft = t.fleet ? d.tricks.find((x) => x.key === t.fleet) : undefined;
            const ref = Object.entries(t.reference || {})[0] as [string, number] | undefined;
            const ev = rungEvidence(t, ft, rank);
            return `<td><a href="/orbitals/demiton/discoveries/${esc(t.key)}"><b>${esc(t.name)}</b></a>${ev}${refRows(t.fleet || t.key, cr.reference as any[] | undefined, ref, signed, chainRef)}</td>`;
          })
          .join('')}</tr>`;
      })
      .join('')
    + ((cr.rungs || []).length
      ? `<tr class="rungsum"><td><b>What a model at this rung is</b></td>${cols
          .map((p) => {
            const r = (cr.rungs || []).find((x) => x.preset === p);
            return r ? `<td><b>${esc(r.title)}</b><div class="s">${esc(r.summary || '')}</div></td>` : '<td></td>';
          })
          .join('')}</tr>`
      : '');
  return { head, body };
};

// ---- one chain (/orbitals/demiton/discoveries/chains/<key>): the explorer's test told as a climb, keel to explorer

export interface ChainPage {
  found: boolean;
  title: string;
  strand: string;
  over: string;
  steps: string;
}

export const chainPageHtml = (d: DiscData, rungs: Rung[], key: string | null, data: any, chainRef: boolean): ChainPage => {
  if (!data || !data.steps) {
    return {
      found: false,
      title: `no chain called ${key ?? ''}`,
      strand: '',
      over: '',
      steps: `<div class="${emptyCls()}">the chains are the explorer's four tests; <a href="/orbitals/demiton/discoveries">back to the chains table</a></div>`,
    };
  }
  const rank = classRank(rungs);
  const nameOfStep = (k: string): string => (data.steps.find((x: any) => x.key === k) || {}).name || k;
  const nameOf = (k: string): string => nameOfStep(k);
  const over = [
    ['the idea', esc(data.idea)],
    ['found by', esc(data.found)],
    ['the library', `${esc(data.shelf)}${data.cutoff ? ` <span class="s">(cutoff ${data.cutoff})</span>` : ''}`],
    ['the climb', `${data.steps.length} steps, one per size, each resting on the one before; step ${data.steps.length} is the bet itself`],
    ['the grade', `${gradeNote(data.grade, nameOf, true)}${data.grade ? `<div class="s">of the ${(data.graded_on || []).length} models read, how many perform each rung: ${data.steps.filter((x: any) => data.grade.counts[x.key] != null).map((x: any) => `${esc(x.name)} <b>${data.grade.counts[x.key]}</b>`).join(' → ')}</div>` : ''}`],
  ]
    .map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`)
    .join('');
  const kts = d.known_tricks || [];
  const sign = (v: number | null | undefined): string => (v == null ? '–' : `${v >= 0 ? '+' : ''}${fmt(v, 2)}`);
  const steps = data.steps
    .map((st: any, i: number) => {
      const found = kts.find((x) => x.key === st.key);
      const t: { key: string; name: string; target_class?: string | null; reference?: Record<string, number> } =
        found || { key: st.key, name: st.name, target_class: st.rung && st.rung.preset };
      const ft = d.tricks.find((x) => x.key === st.key);
      const r = st.rung || {};
      const ref = Object.entries(t.reference || st.reference || {})[0] as [string, number] | undefined;
      const last = i === data.steps.length - 1;
      // the pairs, with each size's best sailing on this test marked right (lift above zero) or wrong
      const best: Record<string, any> = {};
      for (const x of st.runs || []) if (x.preset && (!best[x.preset] || (x.lift ?? -9) > (best[x.preset].lift ?? -9))) best[x.preset] = x;
      const cls = Object.keys(best).sort((a, b) => rank(a) - rank(b));
      const passage = (p: any): string =>
        p.frame && p.prompt.endsWith(p.frame) && p.prompt.length > p.frame.length
          ? `${esc(p.prompt.slice(0, p.prompt.length - p.frame.length).trimEnd())} <span class="pfsep">/</span> <span class="pframe">${esc(p.frame)}</span> …`
          : `${esc(p.prompt)} …`;
      const row = (p: any, j: number): string =>
        `<tr><td class="pq">${passage(p)}</td><td class="pi">${esc(p.idea)}</td><td class="pr">${esc(p.rival)}</td>${cls
          .map((c) => {
            const v = best[c].pairs[j];
            return v == null ? '<td>–</td>' : `<td class="${v > 0 ? 'pok' : 'pno'}" title="${esc(best[c].name)}: lift ${sign(v)}">${v > 0 ? '✓' : '✗'}</td>`;
          })
          .join('')}</tr>`;
      const head = `<thead><tr><th>the passage</th><th>the idea</th><th>its rival</th>${cls.map((c) => `<th title="${esc(best[c].name)}">${esc(c)}</th>`).join('')}</tr></thead>`;
      const pairs = st.pairs && st.pairs.length
        ? `<div class="scroll"><table class="pairs" data-nosort>${head}<tbody>${st.pairs.slice(0, 6).map(row).join('')}</tbody></table></div>`
          + (st.pairs.length > 6 ? `<details><summary>all ${st.pairs.length} pairs</summary><div class="scroll"><table class="pairs" data-nosort>${head}<tbody>${st.pairs.map(row).join('')}</tbody></table></div></details>` : '')
        : `<div class="${emptyCls()}">pairs not written yet${st.pairs_file ? ` (<span class="mono">${esc(st.pairs_file)}</span>)` : ''}</div>`;
      return `<section class="${cardCls(false, `panel cstep${last ? ' bet' : ''}`)}">
      <div class="cnum">${i + 1}</div>
      <div class="cbody">
        <div class="crung">${r.preset ? classLink(rungs, r.preset) : ''}${r.title ? ` · <b>${esc(r.title)}</b>` : ''}</div>
        <h2><a href="/orbitals/demiton/discoveries/${esc(st.key)}">${esc(st.name)}</a></h2>
        <p class="cadds">${esc(st.adds)}</p>
        ${last && st.about ? `<p class="s">${esc(st.about)}</p>` : ''}
        <div class="row cev">
          <div class="cevid"><div class="k">class by size <span class="s">best lift · share right · floor</span></div>${rungEvidence(t, ft, rank, { floor: true })}
            ${refRows(st.key, data.reference, ref, sign, chainRef)}
            <div class="s">performed at lift ${st.threshold ?? '–'}${st.min_score != null ? ` and ${Math.round(100 * st.min_score)}% of pairs right` : ''}, at the same reading</div></div>
          <div class="cpairs"><div class="k">the pairs <span class="s">each size's best voyage, ✓ where it bets on the idea${st.pairs && st.pairs.some((p: any) => p.frame) ? '; premise / <b>frame</b>: the lift is what the premise adds over the frame alone' : ''}</span></div>${pairs}</div>
        </div>
      </div></section>`;
    })
    .join('');
  return { found: true, title: data.name, strand: `<span class="${pillCls('accent')}">${esc(data.strand)}</span>`, over, steps };
};

// ---- the star grid (the Stars subtab): every star Nothing up my sleeve measures, by size of ship

export const starGridHtml = (d: DiscData, rungs: Rung[]): { head: string; body: string } => {
  const stars = d.stars || [];
  const rank = classRank(rungs);
  const presets = [...new Set(stars.flatMap((s) => s.ships.map((x) => x.preset)).filter((p): p is string => Boolean(p)))].sort((a, b) => rank(a) - rank(b));
  const head = `<tr><th>star</th><th>the mark</th>${presets.map((p) => `<th>${classLink(rungs, p)}</th>`).join('')}<th>the judge</th></tr>`;
  const levelled = [...stars].sort((a, b) => (a.level ?? 9) - (b.level ?? 9) || a.name.localeCompare(b.name));
  const body =
    levelled
      .map((s) => {
        const f = CARD_FACE[s.key];
        const cells = presets
          .map((p) => {
            const mine = s.ships.filter((x) => x.preset === p);
            if (!mine.length) return '<td class="cen q">–</td>';
            const lit = mine
              .map((x) => ({ x, at: x.steps_to_lit ?? x.shared_steps_to_lit, shared: x.steps_to_lit == null && x.shared_steps_to_lit != null }))
              .filter((o) => o.at != null)
              .sort((a, b) => (a.at as number) - (b.at as number))[0];
            const best = Math.max(...mine.map((x) => x.best ?? -Infinity));
            const near = isFinite(best) && s.threshold ? Math.max(0, Math.min(1, best / s.threshold)) : 0;
            return lit
              ? `<td class="cen lit" title="first lit by ${esc(lit.x.ship_name || lit.x.name)} at step ${lit.at}${lit.shared ? ' (two heads together)' : ''}; ${mine.length} sailing${mine.length === 1 ? '' : 's'} read">✓ <span class="s">${lit.at}</span></td>`
              : `<td class="cen" style="--near:${(100 * near).toFixed(0)}%" title="best ${isFinite(best) ? best.toFixed(3) : '–'} of ${s.threshold} over ${mine.length} sailing${mine.length === 1 ? '' : 's'}">${isFinite(best) ? best.toFixed(2) : '–'}</td>`;
          })
          .join('');
        return `<tr><td>${f ? `<span class="suitmark">${f.rank}${f.suit}</span> ` : ''}<b>${esc(s.name)}</b><div class="s">level ${s.level ?? '–'}${(s.rests_on || []).length ? ` · rests on ${esc((s.rests_on || []).map((k) => (stars.find((x) => x.key === k) || {}).name || k).join(', '))}` : ''}</div></td>
      <td>${s.threshold}</td>${cells}<td>${cardBadge(d.card_verdicts, s.key) || '<span class="s">–</span>'}</td></tr>`;
      })
      .join('') || `<tr><td colspan="${presets.length + 3}" class="${emptyCls(true)}">no star measured yet</td></tr>`;
  return { head, body };
};

// ---- the deck (the Cards subtab): the sixteen cards, card by card
export const cardDeckHtml = (data: { cards: any[] }): string => {
  const tier: Record<string, string> = { keeper: '=', decayer: '~', untested: '?' };
  return (data.cards || [])
    .map(
      (c) => `<tr><td class="mono">${esc(c.card)}</td><td>${esc(c.suit)}</td>
    <td>${c.mark == null ? '–' : c.mark}</td><td title="keeper: holds after the fade; decayer: reads under the pull and falls; untested: never pinned">${tier[c.tier] || '?'}</td>
    <td>${c.ours == null ? '<span class="s">–</span>' : `<b>${c.ours.toFixed(2)}</b>`}</td>
    <td>${c.qwen == null ? '<span class="s">–</span>' : c.qwen.toFixed(2)}</td></tr>`,
    )
    .join('');
};

// ---- a trick's methodology (fleet.METHODS, /api/discoveries methods): rendered as written in fleet

const COVERED: Record<string, [string, string]> = { yes: ['good', 'covered'], partly: ['accent', 'partly'], no: ['bad', 'not covered'] };

const starOfCard = (d: DiscData, name: string): Star | null => {
  const n = name.toLowerCase().replace(/\(.*?\)/g, '').replace(/[^a-z]+/g, ' ').trim();
  return (
    d.stars.find((st) => {
      const sn = (st.name || st.key).toLowerCase().replace(/^the\s+/, '').replace(/[^a-z]+/g, ' ').trim();
      return sn === n || st.key.replace(/_/g, ' ') === n;
    }) || null
  );
};

export interface MethodHtml {
  name: string;
  status: string;
  trick: string;
  parts: string;
  gaps: string;
  controls: string;
  metric: string;
  cards: string;
}

export const methodHtml = (d: DiscData, key: string, rungs: Rung[]): MethodHtml | null => {
  const m = (d.methods || {})[key];
  if (!m) return null;
  const parts = (m.parts || [])
    .map((p) => {
      const c = COVERED[p.covered] || ['', p.covered];
      return `<tr><td><b>${esc(p.part)}</b></td><td>${esc(p.meaning)}</td><td><span class="${pillCls(c[0])}">${esc(c[1])}</span></td></tr>`;
    })
    .join('');
  const gaps = (m.gaps || []).map((g) => `<li>${esc(g)}</li>`).join('');
  const controls = (m.controls || []).map((c) => `<tr><td><b>${esc(c.control)}</b></td><td>${esc(c.does)}</td></tr>`).join('');
  const cards = (m.cards || [])
    .map((c) => {
      const planned = c.status !== 'in the deck';
      const st = planned ? null : starOfCard(d, c.card);
      const lit = st && (st.ships || []).some((x) => x.steps_to_lit != null || x.shared_steps_to_lit != null);
      // which sizes have lit it (one head or shared), smallest first, each with its first sailing and step; or the nearest
      let foot = '';
      if (st) {
        const by: Record<string, { at: number; x: DiscShip; shared: boolean }> = {};
        for (const x of st.ships || []) {
          const at = x.steps_to_lit ?? x.shared_steps_to_lit;
          if (at == null) continue;
          const b = by[x.preset as string];
          if (!b || at < b.at) by[x.preset as string] = { at, x, shared: x.steps_to_lit == null };
        }
        const cls = Object.keys(by).sort((a, b) => classRank(rungs)(a) - classRank(rungs)(b));
        if (cls.length) foot = `<div class="foot mlit">lit by ${cls.map((p) => `<span title="first by ${esc(by[p].x.name)} at step ${by[p].at}${by[p].shared ? ' (two heads together)' : ''}">${classLink(rungs, p)}</span>`).join(' · ')}</div>`;
        else {
          const near = [...(st.ships || [])].filter((x) => x.best != null).sort((a, b) => (b.best as number) - (a.best as number))[0];
          foot = `<div class="foot s">not lit by any size yet${near ? `; nearest ${esc(near.preset || '')} at ${fmt(near.best)} of ${st.threshold}` : ''}</div>`;
        }
      }
      const vb = st ? cardBadge(d.card_verdicts, st.key) : '';
      const inner = `${st ? cardArt(st.key) : ''}${vb ? `<div class="vrow">${vb}</div>` : ''}<div class="top"><span class="preset">${esc(c.card)}</span><span class="${pillCls(planned ? '' : lit ? 'good' : 'blue')}">${planned ? 'planned' : lit ? 'lit' : 'in the deck'}</span></div><div class="ov">${esc(c.operation)}</div>${foot}`;
      return planned ? `<div class="${cardCls(false, 'card planned')}">${inner}</div>` : `<div class="${cardCls(false, `card${lit ? ' lit pulse' : ''}`)}">${inner}<div class="foot"><a href="/orbitals/demiton/discoveries/stars">${st ? esc(st.name) : 'the star chart'} on the star chart →</a></div></div>`;
    })
    .join('');
  return { name: m.name.toLowerCase(), status: m.status || '', trick: m.trick || '', parts, gaps, controls, metric: m.metric || '', cards };
};

// ---- chaining two facts (the first subtab): the method's live numbers, the claim, the pairs, the grades

export interface TwoFactTest {
  chain: string;
  key: string;
}

export const twoFactTests = (d: DiscData): TwoFactTest[] => {
  const cr = d.chain_rungs || {};
  const chains = cr.chains || [];
  const rungIdx = (cr.rungs || []).findIndex((r) => /chains two facts/i.test(r.title || ''));
  return chains.map((c) => ({ chain: c[c.length - 1], key: c[rungIdx >= 0 ? rungIdx : 4] }));
};

export interface TwoFactsHtml {
  status: string;
  examples: string;
  grades: string;
  backtest: string;
  thr: number;
  noise: number;
  share: string | null;
}

export const twoFactsHtml = (d: DiscData, sq: any, lb: any, pulls: (any | null)[]): TwoFactsHtml => {
  const cr = d.chain_rungs || {};
  const chains = cr.chains || [];
  const tests = twoFactTests(d);
  const thr = sq.threshold ?? 0.1;
  const noise = sq.noise ?? 0.03;
  const ft = d.tricks.find((x) => x.key === (tests[0] || {}).key);
  const share = ft && ft.min_score ? `${Math.round(100 * ft.min_score)}% (two in three)` : null;
  // where the claim stands
  const rng = sq.range || [];
  const scored = rng.filter((c: any) => c.scored);
  const above = (sq.classes_above_noise || []).length;
  const pLin = sq.p_range_linear;
  const pBend = sq.p_range_bending;
  const state: [string, string] = sq.forecastable && pLin >= 0.9 ? ['good', 'claimed'] : sq.forecastable && pBend >= 0.9 ? ['accent', 'probable'] : ['', 'not claimed'];
  const best = ((lb && lb.board) || []).filter((b: any) => b.best && b.best.chaining_lift != null).sort((a: any, b: any) => b.best.chaining_lift - a.best.chaining_lift)[0];
  const status = `<div class="tfs"><span class="${pillCls(state[0])}">${state[1]}</span></div>
    <div class="tfs"><b>${scored.length} of ${rng.length}</b><span>2–4B competitors scored${sq.hardest ? `; the hardest, ${esc(sq.hardest)}` : ''}</span></div>
    <div class="tfs"><b>${above} of 3</b><span>Nothing up my sleeve classes above the noise, needed before any forecast</span></div>
    <div class="tfs"><b>${best ? signed(best.best.chaining_lift) : '–'}</b><span>Nothing up my sleeve's best chaining lift so far${best ? ` (${esc(best.best.preset)}, ${esc(best.best.ship || best.best.run)})` : ''}</span></div>
    <div class="tfs"><b>${sq.forecastable ? `${pLin == null ? '–' : Math.round(100 * pLin) + '%'} · ${pBend == null ? '–' : Math.round(100 * pBend) + '%'}` : 'not yet'}</b><span>P over the range, straight · bending</span></div>
    <div class="tfcomp">${rng.map((c: any) => `<span title="${esc(c.model)}">${esc(c.label)} <b>${c.scored && c.chaining_lift != null ? signed(c.chaining_lift) : '…'}</b> <i>at ${fmtParams(c.params)} → Nothing up my sleeve at ${fmtParams(c.smoke_at || c.params / 10)}</i></span>`).join('')}</div>`;
  // an example pair from each chaining test
  const passage = (p: any): string =>
    p.frame && p.prompt.endsWith(p.frame) && p.prompt.length > p.frame.length
      ? `${esc(p.prompt.slice(0, p.prompt.length - p.frame.length).trimEnd())} <span class="pfsep">/</span> <span class="pframe">${esc(p.frame)}</span> …`
      : `${esc(p.prompt)} …`;
  const examples = tests
    .map((t, i) => {
      const pd = pulls[i];
      const st = pd && pd.steps && pd.steps.find((x: any) => x.key === t.key);
      const p = st && st.pairs && st.pairs[0];
      return `<tr><td><a href="/orbitals/demiton/discoveries/chains/${esc(t.chain)}">${esc(pd ? pd.name : t.chain)}</a><div class="s"><a href="/orbitals/demiton/discoveries/${esc(t.key)}">${esc(st ? st.name : t.key)}</a></div></td>
      <td>${p ? passage(p) : '<span class="s">pairs not written yet</span>'}</td><td class="good">${p ? esc(p.idea) : ''}</td><td class="bad">${p ? esc(p.rival) : ''}</td></tr>`;
    })
    .join('');
  // each chain's grade
  const nameOf = (k: string): string => (d.known_tricks || []).find((x) => x.key === k)?.name || k;
  const grades = chains
    .map((c) => {
      const end = c[c.length - 1];
      const g: any = (cr.grades || {})[end];
      return `<div class="tfg"><a href="/orbitals/demiton/discoveries/chains/${esc(end)}"><b>${esc(nameOf(end))}</b></a> ${gradeNote(g, nameOf)}${g && g.counts ? `<div class="s">${Object.entries(g.counts as Record<string, number>).map(([, n]) => n).join(' → ')} of ${(cr.graded_on || []).length || '–'} models pass each rung, keel up</div>` : ''}</div>`;
    })
    .join('');
  // the backtest
  const fmtBand = (f: any): string => `${signed(f.predicted)} <span class="s">(${signed(f.band[0])} to ${signed(f.band[1])})</span>`;
  const backtest = (sq.backtest || [])
    .map(
      (b: any) => `<div class="sqbt"><b>${esc(b.test)}</b> · actual ${signed(b.actual)}
    ${['linear', 'bending']
      .filter((k) => b[k])
      .map((k) => `<div class="sqbk ${b[k].inside_band ? 'good' : 'bad'}">${k === 'linear' ? 'straight' : 'bending'}: ${fmtBand(b[k])} · ${b[k].inside_band ? 'inside the band' : b[k].predicted < b.actual ? 'missed, too low' : 'missed, too high'}</div>`)
      .join('')}</div>`,
    )
    .join('') + '<p class="s">The straight line has missed low both times, which is why it is the conservative curve and the claim is held to it.</p>';
  return { status, examples, grades, backtest, thr, noise, share };
};

// ---- the charts, drawn from the island's effects. ECharts is imported here, lazily: the island is
// server-rendered, so no module that touches document may be imported at module load.

export interface StarPoint {
  n: number;
  role: string;
  ours: number | null;
  qwen: number | null;
}

export const drawStarJourney = async (points: StarPoint[]): Promise<void> => {
  const el = document.getElementById('starjourney');
  if (!el) return;
  const { starChart } = await import('../../lib/panel');
  starChart(el, points, { label: 'the 300k', height: 380 });
};

export const drawStarDeviation = async (cards: any[]): Promise<void> => {
  const el = document.getElementById('stardev');
  if (!el) return;
  const { C, layout, plotEl } = await import('../../lib/charts');
  const cs = (cards || []).filter((c) => Math.abs(c.dev) > 0.02);
  if (!cs.length) {
    el.innerHTML = `<div class="${emptyCls()}">no point reads in both a 300k and Qwen3 4B yet</div>`;
    return;
  }
  const cs2 = [...cs].sort((a, b) => a.dev - b.dev);
  const mark: Record<string, string> = { keeper: '=', decayer: '~', untested: '?' };
  const tone = (v: number): string => (v >= 0 ? C.good || '#5aa07a' : C.bad || '#c0563f');
  el.innerHTML = '';
  plotEl(
    el,
    [
      {
        type: 'bar',
        orientation: 'h',
        y: cs2.map((c) => `${mark[c.tier] || '?'} ${c.name}`),
        x: cs2.map((c) => c.dev),
        marker: { color: cs2.map((c) => tone(c.dev)) },
        text: cs2.map((c) => `${c.ours.toFixed(2)} vs ${c.qwen.toFixed(2)}`),
        textposition: 'auto',
        hovertemplate: '%{y}<br>ours %{text}<br>deviation %{x:+.2f} of the mark<extra></extra>',
      },
    ],
    layout({
      margin: { l: 190, r: 24, t: 10, b: 40 },
      xaxis: { title: `deviation from Qwen3 4B (× the card's mark)`, gridcolor: C.line, zeroline: true, zerolinecolor: C.line },
      yaxis: { automargin: true, tickfont: { size: 11 } },
      showlegend: false,
      height: Math.max(320, 26 * cs2.length),
    }),
  );
};

export const drawBridge = async (d: any, rungs: Rung[]): Promise<void> => {
  if (!document.getElementById('bridgechart')) return;
  const { empty, layout, plot, tok, PALETTE } = await import('../../lib/charts');
  const runs = (d.runs || []).filter((r: any) => r.curve && r.curve.length);
  if (!runs.length) {
    empty('bridgechart', 'no voyage has read the bridge yet: it comes with the cards evaluator');
    return;
  }
  const rank = classRank(rungs);
  const presets = [...new Set(runs.map((r: any) => r.preset))].sort((a, b) => rank(a as string) - rank(b as string));
  const traces = runs.map((r: any) => ({
    x: r.curve.map((_: unknown, i: number) => i),
    y: r.curve,
    name: `${r.name} (${r.preset})`,
    mode: 'lines+markers',
    marker: { size: 5 },
    line: { color: PALETTE[presets.indexOf(r.preset) % PALETTE.length], width: 1.6 },
    hovertemplate: `${esc(r.name)}<br>layer %{x}<br>%{y:.3f} nats<extra></extra>`,
  }));
  const shapes = d.threshold != null ? [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: d.threshold, y1: d.threshold, line: { color: tok('accent'), width: 1, dash: 'dot' } }] : [];
  plot('bridgechart', traces, layout({ xaxis: { title: { text: 'layer (bottom of the stack first)' }, dtick: 1 }, yaxis: { title: { text: 'the bridge at the answer (nats)' } }, shapes, height: 320 }));
};

export const drawTrickChart = async (id: string, d: any, t: { name: string; reference?: Record<string, number> }, presets: string[]): Promise<void> => {
  const { trickChart } = await import('./chains');
  trickChart(id, d, t, presets);
};

export const emptyChart = async (id: string, msg: string): Promise<void> => {
  const { empty } = await import('../../lib/charts');
  empty(id, msg);
};

// ---------------------------------------------------------------- the head census (every one of Qwen's 1,152)
// thorp/head_census.py records heads-<model>: every head's score on each kind it can measure, its layer,
// and the behavioural clusters that are cards outside the sixteen. The Stars tab's Heads subtab lists them
// by category, expandable; the Cards subtab lists the sixteen and then the clusters.
const CENSUS_KIND: Record<string, string> = {
  previous_word: 'Previous-word', offset_2: 'Two words back', offset_3: 'Three words back',
  attention_sink: 'Attention sink', delimiter: 'Delimiter', rare_word: 'Rare word',
  duplicate_word: 'Duplicate word', nevermore: 'Nevermore (induction)', mover: 'Mover',
  comparator: 'Comparator', bridge: 'Bridge',
};

export function headsCensusHtml(c: any): string {
  if (!c || !c.found) return `<div class="${emptyCls()}">the head census has not been run for this model yet (thorp.head_census)</div>`;
  const heads: any[] = c.inventory || [];
  const clusters: any[] = c.clusters || [];
  const byKey: Record<string, any> = {};
  for (const h of heads) byKey[`${h.layer}.${h.head}`] = h;
  const pad = (n: number) => String(n).padStart(2, '0');
  const pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(100 * v)}%`);
  const cell = (h: any) => `<tr><td class="mono">L${pad(h.layer)}.H${pad(h.head)}</td>
    <td>${h.lit && h.lit.length ? esc(h.lit.join(', ')) : '<span class="s">no card names it</span>'}</td>
    <td>${h.layer}</td><td>${pct(h.sink)}</td><td>${pct(h.previous)}</td>
    <td>${h.entropy != null ? h.entropy.toFixed(1) : '–'}</td>
    <td>${h.number != null ? `${h.number.toFixed(1)}×` : '–'}</td></tr>`;
  const merged: Record<string, { name: string; size: number; heads: number[][]; top: string[] }> = {};
  for (const cl of clusters) {
    const key = cl.name || 'Other';
    if (!merged[key]) merged[key] = { name: key, size: 0, heads: [], top: cl.top || [] };
    merged[key].size += cl.size;
    merged[key].heads.push(...(cl.heads || []));
  }
  const cats = Object.values(merged).sort((a, b) => b.size - a.size);
  const summary = cats.map((cl) => `<tr><td><b>${esc(cl.name)}</b></td><td>${cl.size}</td>
    <td>${(cl.top || []).slice(0, 3).map((t: string) => esc(String(t).split(' (')[0])).join(', ')}</td></tr>`).join('');
  const sections = cats.map((cl) => {
    const rows = (cl.heads || []).map(([l, h]: number[]) => byKey[`${l}.${h}`]).filter(Boolean)
      .sort((a: any, b: any) => a.layer - b.layer || a.head - b.head);
    return `<details class="scaffoldruns"><summary><b>${esc(cl.name)}</b> <span class="s">${rows.length} head${rows.length === 1 ? '' : 's'}</span></summary>
      <div class="scroll"><table data-nosort><thead><tr><th>head</th><th>named by</th><th>layer</th><th>sink</th><th>previous</th><th>entropy</th><th>numbers</th></tr></thead><tbody>${rows.map(cell).join('')}</tbody></table></div></details>`;
  }).join('');
  return `<div class="k">${c.n_heads} heads on ${esc(c.model)}, in ${cats.length} categories <span class="s">every head is in exactly one; the kind that names it is a separate reading, shown in "named by"</span></div>
    <div class="scroll"><table data-nosort><thead><tr><th>category</th><th>heads</th><th>what distinguishes it</th></tr></thead><tbody>${summary}</tbody></table></div>
    ${sections}`;
}

export function cardsBeyondHtml(c: any): string {
  if (!c || !c.found) return '';
  const clusters = (c.clusters || []).slice(0, 12);
  const rows = clusters.map((cl: any) => {
    const top = (cl.top || []).map((t: string) => t.split(' (')[0]);
    return `<tr><td><b>${esc(top[0] || 'unnamed role')}</b>${top.slice(1).length ? `<div class="s">${esc(top.slice(1).join(', '))}</div>` : ''}</td>
      <td>${cl.size}</td><td>${esc(cl.heads.slice(0, 6).map((h: number[]) => `L${h[0]}.H${h[1]}`).join(', '))}</td>
      <td><span class="s">${top.some((t: string) => /number|series|copy|previous|punct|line|follow-on/i.test(t)) ? 'candidate card' : 'broad role'}</span></td></tr>`;
  }).join('');
  return `<section class="${cardCls(false, 'panel')}" style="margin-top:16px">
    <h2>Cards outside the sixteen <span class="note">the behavioural clusters of all ${c.n_heads} heads on a battery of prompts (prose, maths, code, series, repetition, coreference, syntax, a needle). A cluster whose behaviour no card names is a candidate for one of the ten kinds with no star metric: successor, copy-suppression, retrieval, the name movers, syntactic, coreference, function vectors</span></h2>
    <div class="scroll"><table data-nosort><thead><tr><th>cluster</th><th>heads</th><th>examples</th><th></th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

export function personasHtml(p: any): string {
  if (!p || p.found === false || !p.norms) return `<div class="${emptyCls()}">the persona probe has not been run for this model (thorp.persona_vectors)</div>`;
  const traits = Object.keys(p.norms || {});
  const rows = traits.map((t) => `<tr><td><b>${esc(t)}</b></td><td>${p.norms[t].toFixed(2)}</td>
    <td>${p.projection_on_plain?.[t] != null ? p.projection_on_plain[t].toFixed(3) : '–'}</td>
    <td>${p.cosine_on_plain?.[t] != null ? p.cosine_on_plain[t].toFixed(3) : '–'}</td></tr>`).join('');
  const cs = Object.entries(p.cosines || {}).map(([k, v]) => [k, Number(v)] as [string, number]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 8)
    .map(([k, v]) => `<tr><td>${esc(String(k).replace('|', ' · '))}</td><td>${v.toFixed(3)}</td></tr>`).join('');
  return `<div class="k">${traits.length} persona directions at layer ${p.layer} (width ${p.width}) <span class="s">each direction is the mean residual-stream difference between the trait's system prompt and its opposite over ${4} questions; its norm is how much of the stream the trait moves</span></div>
    <div class="row"><div><div class="k">The directions</div><div class="scroll"><table data-nosort><thead><tr><th>trait</th><th>norm</th><th>projection on a plain prompt</th><th>cosine with plain</th></tr></thead><tbody>${rows}</tbody></table></div></div>
    <div><div class="k">How much the traits share a direction</div><div class="scroll"><table data-nosort><thead><tr><th>pair</th><th>cosine</th></tr></thead><tbody>${cs}</tbody></table></div></div></div>`;
}
