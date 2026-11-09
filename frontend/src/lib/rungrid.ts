// The RunGrid: every run at one size as a square, like a GitHub contribution graph (UI.md "RunGrid"). Bands
// of 7 rows x 53 columns stack downwards, so a new run only ever adds a square at the end. Colour is the run's
// Forgotten Tomes quartile among the scored runs: deepest green is best. Extracted (and typed) from the view
// monolith; `renderRunGrid` draws it, `initRunGrid` wires the hover and click once.

import { emptyCls, pillCls, tooltipCls } from './ui';
import { fmt, esc } from './format';
import { cn } from './utils';

const GRID_ROWS = 7;
const GRID_COLS = 53;

let gridKey = '';
let runsById = new Map<string, any>();
let rankById = new Map<string, number>();
let nScored = 0;

export function renderRunGrid(r: { preset: string }, runs: any[], selected: string | null): void {
  const el = document.getElementById('rungrid');
  const sum = document.getElementById('rungridsum');
  if (!el || !sum) return;  // only a size's page carries the grid
  const key = r.preset + '|' + selected + '|' + runs.map((x) => x.run_id + (x.status || '')[0] + (x.ft_en ?? '')).join(',');
  if (key === gridKey) return;
  gridKey = key;
  if (!runs.length) { sum.innerHTML = ''; el.innerHTML = `<div class="${emptyCls()}">no voyages at ${esc(r.preset)} yet</div>`; return; }
  const scored = runs.filter((x) => x.ft_en != null).sort((a, b) => a.ft_en - b.ft_en);
  rankById = new Map(scored.map((x, i) => [x.run_id, i]));
  const level = (x: any): number => (!rankById.has(x.run_id) ? 0 : 4 - Math.min(3, Math.floor((4 * rankById.get(x.run_id)!) / scored.length)));
  const live = runs.filter((x) => x.status === 'running').length;
  const med = scored.length ? scored[Math.floor((scored.length - 1) / 2)].ft_en : null;
  const latest = [...runs].reverse().find((x) => x.ft_en != null);
  sum.innerHTML = `<span><b>${runs.length}</b> voyage${runs.length === 1 ? '' : 's'}</span><span><b>${scored.length}</b> scored</span>${live ? `<span class="${pillCls('blue')}">${live} running</span>` : ''}`
    + (scored.length ? `<span>best <b>${fmt(scored[0].ft_en)}</b> ${esc(scored[0].ship || scored[0].name)}</span><span>median <b>${fmt(med)}</b></span><span>latest <b>${fmt(latest.ft_en)}</b> ${esc(latest.ship || latest.name)}</span>` : '')
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
  const tip = document.createElement('div');
  tip.className = cn('gridtip', tooltipCls);
  tip.hidden = true;
  document.body.appendChild(tip);
  el.addEventListener('mouseover', (e) => {
    const c = (e.target as HTMLElement).closest('i[data-run]') as HTMLElement | null;
    if (!c) return;
    const x = runsById.get(c.dataset.run!);
    if (!x) return;
    const k = rankById.get(x.run_id);
    const st = (x.status || '').split(':')[0];
    tip.innerHTML = `<b>${esc(x.ship || x.name)}</b> <span class="s">${esc(x.name)}</span><br>`
      + (x.ft_en != null ? `Forgotten Tomes <b>${fmt(x.ft_en)}</b> bpb · #${k! + 1} of ${nScored}` : `no Forgotten Tomes score yet`)
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
