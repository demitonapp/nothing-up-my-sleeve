// The RunGrid: every run at one size as a square, like a GitHub contribution graph (UI.md "RunGrid"). Bands
// of 7 rows x 53 columns stack downwards, so a new run only ever adds a square at the end. Colour is the run's
// quartile on one reading — Forgotten Tomes bits per byte (lower is better) or the logic deck's cause gain
// (higher is better) — the deepest green best. Extracted (and typed) from the view monolith; `renderRunGrid`
// draws it, `initRunGrid` wires the hover, click and the metric selector once.

import { emptyCls, pillCls, tooltipCls } from './ui';
import { fmt, esc } from './format';
import { cn } from './utils';

const GRID_ROWS = 7;
const GRID_COLS = 53;

type Metric = 'bpb' | 'cause';

const METRICS: Record<Metric, {
  label: string;
  value: (x: any) => number | null;
  better: 'lower' | 'higher';
  format: (v: number) => string;
}> = {
  bpb: {
    label: 'Forgotten Tomes bpb',
    value: (x) => (x.ft_en == null ? null : x.ft_en),
    better: 'lower',
    format: (v) => fmt(v),
  },
  cause: {
    label: 'cause gain',
    value: (x) => (x.cause == null ? null : x.cause),
    better: 'higher',
    format: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(3)}`,
  },
};

const STORE = 'thorp.gridmetric';

let gridKey = '';
let runsById = new Map<string, any>();
let rankById = new Map<string, number>();
let nScored = 0;
let metric: Metric = 'bpb';
let last: { r: { preset: string }; runs: any[]; selected: string | null } | null = null;

function storedMetric(): Metric {
  try {
    return localStorage.getItem(STORE) === 'cause' ? 'cause' : 'bpb';
  } catch {
    return 'bpb';
  }
}

function persistMetric(m: Metric): void {
  try {
    localStorage.setItem(STORE, m);
  } catch {
    /* private mode: the choice lasts the page */
  }
}

export function renderRunGrid(r: { preset: string }, runs: any[], selected: string | null, m?: Metric): void {
  const el = document.getElementById('rungrid');
  const sum = document.getElementById('rungridsum');
  if (!el || !sum) return;  // only a size's page carries the grid
  if (m) metric = m;
  const spec = METRICS[metric];
  last = { r, runs, selected };
  const key = r.preset + '|' + selected + '|' + metric + '|'
    + runs.map((x) => x.run_id + (x.status || '')[0] + (spec.value(x) ?? '')).join(',');
  if (key === gridKey) return;
  gridKey = key;
  if (!runs.length) { sum.innerHTML = ''; el.innerHTML = `<div class="${emptyCls()}">no voyages at ${esc(r.preset)} yet</div>`; return; }
  const scored = runs
    .filter((x) => spec.value(x) != null)
    .sort((a, b) => (spec.better === 'lower' ? spec.value(a)! - spec.value(b)! : spec.value(b)! - spec.value(a)!));
  rankById = new Map(scored.map((x, i) => [x.run_id, i]));
  const level = (x: any): number => (!rankById.has(x.run_id) ? 0 : 4 - Math.min(3, Math.floor((4 * rankById.get(x.run_id)!) / scored.length)));
  const live = runs.filter((x) => x.status === 'running').length;
  const med = scored.length ? spec.value(scored[Math.floor((scored.length - 1) / 2)]) : null;
  const latest = [...runs].reverse().find((x) => spec.value(x) != null);
  sum.innerHTML = `<span><b>${runs.length}</b> voyage${runs.length === 1 ? '' : 's'}</span><span><b>${scored.length}</b> scored on ${esc(spec.label)}</span>${live ? `<span class="${pillCls('blue')}">${live} running</span>` : ''}`
    + (scored.length ? `<span>best <b>${spec.format(spec.value(scored[0])!)}</b> ${esc(scored[0].ship || scored[0].name)}</span><span>median <b>${med == null ? '–' : spec.format(med)}</b></span><span>latest <b>${spec.format(spec.value(latest)!)}</b> ${esc(latest.ship || latest.name)}</span>` : '')
    + `<span class="legend">worse <i class="g1"></i><i class="g2"></i><i class="g3"></i><i class="g4"></i> better · <i class="g0"></i> not scored</span>`;
  const per = GRID_ROWS * GRID_COLS;
  const bands: string[] = [];
  for (let b = 0; b * per < runs.length; b++) {
    const chunk = runs.slice(b * per, (b + 1) * per);
    bands.push(`<div class="gridband"><div class="gridlabel">voyages ${b * per + 1}–${b * per + chunk.length}</div><div class="rungrid">${chunk.map((x) => {
      const st = (x.status || '').split(':')[0];
      return `<i class="g${level(x)}${st === 'running' ? ' run' : ''}${st === 'failed' ? ' fail' : ''}${x.run_id === selected ? ' sel' : ''}" data-run="${esc(x.run_id)}"></i>`;
    }).join('')}</div></div>`);
  }
  el.innerHTML = bands.join('');
  runsById = new Map(runs.map((x) => [x.run_id, x]));
  nScored = scored.length;
}

export function initRunGrid(goShip: (id: string) => void): void {
  const el = document.getElementById('rungrid');
  if (!el) return;  // wired once per page that has the grid; the other routes do not
  const sel = document.getElementById('gridmetric') as HTMLSelectElement | null;
  if (sel) {
    // a grid metric is a link too: /ships/300k?grid=cause opens the cause view
    const q = new URLSearchParams(location.search).get('grid');
    metric = q === 'cause' || q === 'bpb' ? q : storedMetric();
    sel.value = metric;
    sel.addEventListener('change', () => {
      metric = sel.value === 'cause' ? 'cause' : 'bpb';
      persistMetric(metric);
      gridKey = '';
      try {
        const u = new URL(location.href);
        if (metric === 'bpb') u.searchParams.delete('grid');
        else u.searchParams.set('grid', metric);
        history.replaceState(null, '', u);
      } catch {
        /* a file:// page cannot replace the URL */
      }
      if (last) renderRunGrid(last.r, last.runs, last.selected, metric);
    });
  }
  const tip = document.createElement('div');
  tip.className = cn('gridtip', tooltipCls);
  tip.hidden = true;
  document.body.appendChild(tip);
  el.addEventListener('mouseover', (e) => {
    const c = (e.target as HTMLElement).closest('i[data-run]') as HTMLElement | null;
    if (!c) return;
    const x = runsById.get(c.dataset.run!);
    if (!x) return;
    const spec = METRICS[metric];
    const k = rankById.get(x.run_id);
    const st = (x.status || '').split(':')[0];
    const bpb = x.ft_en != null ? `bpb <b>${fmt(x.ft_en)}</b>` : 'bpb not read';
    const cause = x.cause != null ? `cause <b>${`${x.cause >= 0 ? '+' : ''}${x.cause.toFixed(3)}`}</b>` : 'cause not read';
    const rank = k == null ? `not scored on ${esc(spec.label)}` : `#${k + 1} of ${nScored} on ${esc(spec.label)}`;
    tip.innerHTML = `<b>${esc(x.ship || x.name)}</b> <span class="s">${esc(x.name)}</span><br>`
      + `${bpb} · ${cause}<br>${rank}`
      + `<br>${esc(st)}${x.passes ? ` · ${x.passes} pass${x.passes === 1 ? '' : 'es'}` : ''}${x.started ? ` · started ${esc(String(x.started).slice(0, 16).replace('T', ' '))}` : ''}`;
    const b = c.getBoundingClientRect();
    tip.hidden = false;
    tip.style.left = Math.max(8, Math.min(b.left - 8, innerWidth - tip.offsetWidth - 8)) + 'px';
    tip.style.top = (b.bottom + 6) + 'px';
  });
  el.addEventListener('mouseout', (e) => { if ((e.target as HTMLElement).closest('i[data-run]')) tip.hidden = true; });
  // a square opens its run, as a row in the Runs table does
  el.addEventListener('click', (e) => {
    const c = (e.target as HTMLElement).closest('i[data-run]') as HTMLElement | null;
    if (!c) return;
    goShip(c.dataset.run!);
  });
}
