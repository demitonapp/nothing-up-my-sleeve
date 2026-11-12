// The discovery chains' evidence cells, extracted (and typed) from the view monolith. `rungEvidence` renders one rung's
// best lift per size (✓ performed under the share rule, ▲ passed below its size, ⚠ while a bigger class fails it);
// `gradeNote` renders a chain's grade from many models. Both are pure: they take their rank/name helpers as arguments.

import { C, PALETTE, empty, layout, plot } from '../../lib/charts';
import { esc, fmt } from '../../lib/format';
import { pillCls } from '../../lib/ui';

export const rungEvidence = (
  t: { target_class?: string | null },
  ft: { threshold: number; evaluator?: unknown; ships: any[]; min_score?: number | null; viable?: boolean } | null | undefined,
  rank: (p: string) => number,
  opts: { floor?: boolean } = {},
): string => {
  const thr = ft ? ft.threshold : 0.1;
  if (!ft || (!ft.evaluator && !ft.ships.length)) {
    return `<div class="s">${ft && ft.viable === false ? 'not viable' : ft ? 'evaluator not built yet' : 'not measured'}</div>`;
  }
  if (!ft.ships.length) return '<div class="s">no readings yet</div>';
  const by: Record<string, { best: number; share: number | null; done: boolean; floor?: number }> = {};
  for (const x of ft.ships) {
    const b = by[x.preset] || (by[x.preset] = { best: -Infinity, share: null, done: false });
    b.best = Math.max(b.best, x.best);
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

export const gradeNote = (g: any, nameOf: (k: string) => string, full?: boolean): string => {
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

// A waypoint's coverage bar (UI.md "Filling the seven steps"): performed here, inherited, open.
export const coverageBar = (c: { here: number; inherited: number; open: number; total: number }): string =>
  `<span class="cbar" title="${c.here} performed here, ${c.inherited} inherited, ${c.open} open, of ${c.total}">${(
    [['here', c.here], ['inherited', c.inherited], ['open', c.open]] as [string, number][]
  ).map(([k, n]) => (n ? `<i class="${k}" style="flex:${n}"></i>` : '')).join('')}</span>`;

// A smaller test leads to a bigger one (the speller's three to the explorer's): the note under a trick's name.
export const leadNote = (t: { key: string; name: string; leads_to?: string }, kts: { key: string; name: string; leads_to?: string }[]): string => {
  const name = (k: string): string => (kts.find((x) => x.key === k) || {}).name || k;
  const led = kts.filter((x) => x.leads_to === t.key);
  return (t.leads_to ? `<div class="lead">→ leads to <a href="/orbitals/demiton/discoveries/${esc(t.leads_to)}">${esc(name(t.leads_to))}</a></div>` : '')
    + (led.length ? `<div class="lead">← led by ${led.map((x) => `<a href="/orbitals/demiton/discoveries/${esc(x.key)}">${esc(x.name)}</a>`).join(', ')}</div>` : '');
};

// A select of the seven steps to quantum physics, kept as chosen.
export const fillStepFilter = (sel: HTMLSelectElement, wps: { key: string; name: string }[]): void => {
  if (sel.options.length === wps.length + 1) return;
  const was = sel.value;
  sel.innerHTML = '<option value="">all seven</option>' + wps.map((w, i) => `<option value="${esc(w.key)}">${i + 1}. ${esc(w.name)}</option>`).join('');
  sel.value = was;
};

// A size's order-of-magnitude band (as the trick table uses): 9m -> 0, 350M -> 3, capped at 6.
export const sizeBand = (n: number): number => Math.min(6, Math.max(0, Math.floor(Math.log10(n)) - 5));

// One measured trick's readings by step: the threshold (amber), the floor (grey: the highest untrained reading
// among the sailings) and the outside models' readings (labelled), dotted. `presets` is the ladder order for colours.
export const trickChart = (
  id: string,
  d: { runs: any[]; threshold: number },
  t: { name: string; reference?: Record<string, number> },
  presets: string[],
): void => {
  if (!d.runs.length) {
    empty(id, 'readings start with the next ship to sail');
    return;
  }
  const floors = d.runs.map((r) => r.floor).filter((v) => v != null);
  const refs = Object.entries(t.reference || {});
  const line = (y: number, color: string, dash = 'dot') => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color, dash } });
  const label = (y: number, text: string, color: string) => ({ xref: 'paper', x: 1, xanchor: 'right', y, yanchor: 'bottom', showarrow: false, text, font: { size: 10, color } });
  const floor = floors.length ? Math.max(...floors) : null;
  plot(
    id,
    d.runs.map((r) => ({
      type: 'scatter', mode: 'lines+markers', name: `${r.ship || r.name} (${r.preset})`, legendgroup: r.preset, x: r.step, y: r.value,
      line: { color: PALETTE[presets.indexOf(r.preset) % PALETTE.length], width: 1.4 }, marker: { size: 7 },
      hovertemplate: `${esc(r.ship || r.name)}: %{y:.3f} at step %{x}<extra></extra>`,
    })),
    layout({
      showlegend: d.runs.length <= 12, xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: esc(t.name), gridcolor: C.line, zeroline: true, zerolinecolor: C.line },
      shapes: [line(d.threshold, C.accent), ...(floor != null ? [line(floor, C.muted)] : []), ...refs.map(([, v], i) => line(v, PALETTE[(i + 4) % PALETTE.length], 'dash'))],
      annotations: [label(d.threshold, `performed at ${d.threshold}`, C.accent), ...(floor != null ? [label(floor, `floor ${fmt(floor)}`, C.muted)] : []),
        ...refs.map(([n, v], i) => label(v, `${esc(n)} ${fmt(v, 2)}`, PALETTE[(i + 4) % PALETTE.length]))],
    }),
  );
};

// A trick's state on one size (UI.md "Filling the seven steps"): measured or not, performed or best.
export const trickOnClass = (
  t: { fleet?: string },
  preset: string,
  data: { tricks?: any[] },
): { text: string; measured: boolean; done: boolean; sort: number } => {
  const ft: any = t.fleet && (data.tricks || []).find((x) => x.key === t.fleet);
  if (!t.fleet) return { text: 'not measured yet', measured: false, done: false, sort: 9 };
  if (ft && ft.viable === false) return { text: 'not viable on Gutenberg in English', measured: false, done: false, sort: 10 };
  if (ft && !ft.evaluator) return { text: `pre-registered${ft.cutoff ? ` (cutoff ${ft.cutoff})` : ''} · evaluator not built yet`, measured: false, done: false, sort: 8 };
  const mine: any[] = ft ? ft.ships.filter((x: any) => x.preset === preset) : [];
  if (!mine.length) return { text: 'measured · no voyage of this size has a reading yet', measured: true, done: false, sort: 8 };
  const done = mine.filter((x: any) => x.performed_at != null);
  const best = Math.max(...mine.map((x: any) => x.best));
  return done.length
    ? { text: `on ${done.length} of ${mine.length} sailings`, measured: true, done: true, sort: 0 }
    : { text: `best ${fmt(best)} of ${ft.threshold} on ${mine.length} sailings`, measured: true, done: false, sort: 1 };
};

// A star's state on one size: lit (one head), shared (two heads together), or its best score.
export const starOnClass = (h: { name: string; star?: string } | null, preset: string, data: { stars?: any[] }): string => {
  if (!h) return '';
  if (!h.star) return `${esc(h.name)} <span class="s">(not measured)</span>`;
  const st: any = (data.stars || []).find((x) => x.key === h.star);
  const mine: any[] = st ? st.ships.filter((x: any) => x.preset === preset) : [];
  if (!mine.length) return `${esc(h.name)} <span class="s">(no reading on this size)</span>`;
  const lit = mine.filter((x: any) => x.steps_to_lit != null).length;
  const sh = mine.filter((x: any) => x.shared_steps_to_lit != null).length;
  return `${esc(h.name)} ${lit ? `<span class="${pillCls('good')}">lit ${lit}/${mine.length}</span>` : sh ? `<span class="${pillCls('accent')}">shared ${sh}/${mine.length}</span>` : `<span class="${pillCls('')}">best ${fmt(Math.max(...mine.map((x: any) => x.best ?? 0)))}</span>`}`;
};
