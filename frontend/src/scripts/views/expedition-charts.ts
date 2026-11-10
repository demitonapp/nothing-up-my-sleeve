// The Expeditions page's charts and the journey through the layers. Imported with `await import(...)`
// from the island's effects: this module pulls in ECharts (lib/charts) and the stage bands, which touch
// the browser when they load, and the island is server-rendered.
//
// Each drawer takes the payload and writes into the element the island has already rendered, exactly
// as dashboard.ts's voyage drawers did, so the markup and the charts stay the same.

import { empty, layout, PALETTE, plot, tok } from '../../lib/charts';
import { drawJourney, soundingSteps } from '../../lib/journey';
import { band, common as commonStages, stageAt, stagesFor } from '../../lib/stages';
import { esc, get } from '../../lib/format';
import { kinksOf } from '../../lib/analysis';
import { groupOf } from '../../lib/metrics';
import { knockoutBlock, knockoutChart } from './knockouts';
import type { Expedition, Rung, SeriesMap } from './expeditions';
import { IND_METRICS } from './expeditions';

const palette = (i: number): string => PALETTE[i % PALETTE.length];

// ---- the fit (book_value): a pure shelf of each kind against its interval
export function drawFit(v: Expedition): void {
  if (!document.getElementById('fitchart') || !v.fit || !v.fit.coef) return;
  const rows = Object.entries(v.fit.coef);
  const pure = rows.filter(([k]) => k.startsWith('pure ')).sort((a, b) => b[1][0] - a[1][0]);
  plot('fitchart', [{
    type: 'scatter', mode: 'markers', x: pure.map((p) => p[1][0]), y: pure.map((p) => p[0].replace('pure ', '')),
    error_x: { type: 'data', symmetric: false, array: pure.map((p) => p[1][2] - p[1][0]), arrayminus: pure.map((p) => p[1][0] - p[1][1]), color: tok('muted') },
    marker: { size: 9, color: tok('accent') }, hovertemplate: '%{y}: %{x:.3f}<extra></extra>',
  }], layout({ xaxis: { title: 'Forgotten Tomes bits per byte (lower is better)', gridcolor: tok('line') }, yaxis: { automargin: true }, margin: { l: 140 } }));
}

// ---- the Forgotten Tomes score, voyage by voyage, one colour per value of the setting that varies most
export function drawVoyageFt(v: Expedition): void {
  const scored = v.runs.map((r, i) => ({ r, i: i + 1 })).filter((p) => p.r.ft_en != null && !p.r.set_aside);
  if (!scored.length) { empty('voyageft', 'no voyage on this expedition has a Forgotten Tomes score yet'); return; }
  const fields = ['passes', 'vocab', 'lr', 'recipe'];
  const by = fields.map((f) => [f, new Set(scored.map((p) => (p.r.settings || {})[f])).size] as [string, number]).sort((a, b) => b[1] - a[1])[0][0];
  const groups = [...new Set(scored.map((p) => (p.r.settings || {})[by]))];
  plot('voyageft', groups.map((g, gi) => {
    const pts = scored.filter((p) => (p.r.settings || {})[by] === g);
    return {
      type: 'scatter', mode: 'markers', name: `${by} ${String(g).replace('lists/', '').replace('.csv', '')}`, x: pts.map((p) => p.i), y: pts.map((p) => p.r.ft_en),
      text: pts.map((p) => p.r.ship || p.r.name), hovertemplate: '%{text}: %{y:.3f}<extra></extra>', marker: { size: 9, color: palette(gi) },
    };
  }), layout({ xaxis: { title: 'voyage, in the order they sailed', gridcolor: tok('line') }, yaxis: { title: 'bits per byte', gridcolor: tok('line') }, legend: { orientation: 'h', y: 1.1 } }));
}

// ---- first light: each star's score against step, every voyage, the threshold dotted
export async function drawVoyageStars(v: Expedition, d: any, starKey: string): Promise<void> {
  const el = document.getElementById('voyagestars');
  if (!el || !d || !d.stars || !d.stars[starKey]) return;
  const star = d.stars[starKey];
  const rs = (d.runs || []).filter((r: any) => r.series[starKey] && r.series[starKey].step.length);
  if (!rs.length) { empty('voyagestars', `no voyage on this expedition has a reading for ${esc(star.name)} yet`); return; }
  const traces = rs.flatMap((r: any, i: number) => {
    const col = palette(i), sr = r.series[starKey];
    const name = `${r.ship || r.name}${{ donor: ' (donor)', receiver: ' (received heads)', teacher: ' (teacher)', student: ' (taught)' }[r.role as string] || ''}`;
    const t: any[] = [{ type: 'scatter', mode: 'lines', name: `${name} · one head`, legendgroup: name, x: sr.step, y: sr.value, line: { color: col, width: 1.8, dash: r.role === 'donor' || r.role === 'teacher' ? 'dot' : 'solid' } }];
    if (sr.shared_step && sr.shared_step.length) t.push({ type: 'scatter', mode: 'lines', name: `${name} · shared`, legendgroup: name,
      x: sr.shared_step, y: sr.shared_value, line: { color: col, width: 1.5, dash: 'dash' } });
    return t;
  });
  plot('voyagestars', traces,
    layout({ xaxis: { title: 'step', gridcolor: tok('line') }, legend: { orientation: 'h', y: 1.12 },
      yaxis: { title: `${star.name} score`, gridcolor: tok('line'), range: [0, Math.max(1, ...traces.flatMap((t: any) => t.y as number[]))] },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: star.threshold, y1: star.threshold, line: { color: tok('accent'), dash: 'dot' } }] }));
  const stages = await stagesFor(rs.map((r: any) => r.run_id));
  band('#voyage', commonStages(stages));
}

// ---- the climb to chaining two facts (two_facts), from its discovery readings
export function drawVoyageClimb(v: Expedition, d: SeriesMap | null, lb: any, what: string, rungs: Rung[]): void {
  const el = document.getElementById('voyageclimb');
  if (!el || !d || !lb) return;
  const runs = v.runs.filter((r) => r.run_id);
  if (!runs.length) { empty('voyageclimb', 'no voyages yet: the baseline (keel, pilot, speller and stylist, two seeds each) is at the top of the queue'); return; }
  const rank = (p: string): number => { const i = rungs.findIndex((r) => r.preset === p); return i < 0 ? 99 : i; };
  const presetOf = (r: any): string => String(r.preset || r.class || '');
  const presets = [...new Set(runs.map(presetOf))].sort((a, b) => rank(a) - rank(b));
  const traces = runs.filter((r) => (d as any)[r.run_id] && (d as any)[r.run_id].step.length && ((d as any)[r.run_id][what] || []).some((x: any) => x != null)).map((r) => ({
    x: (d as any)[r.run_id].step, y: (d as any)[r.run_id][what], name: r.name, mode: 'lines+markers', marker: { size: 4 },
    line: { color: palette(presets.indexOf(presetOf(r))), width: 1.6 }, legendgroup: presetOf(r),
    hovertemplate: `${esc(r.name)}<br>step %{x}<br>${what === 'climb' ? 'climb' : what === 'logic_gain' ? 'chaining gain' : 'chaining lift'} %{y:.2f}<extra></extra>`, connectgaps: true,
  }));
  if (!traces.length) { empty('voyageclimb', what === 'logic_gain' ? 'no logic deck readings yet: the baseline voyages not yet sailed read it' : 'no discovery readings yet: the first comes at step 100'); return; }
  const shapes: any[] = [], notes: any[] = [];
  for (const r of (lb.reference || [])) {
    const y = what === 'climb' ? r.climb : what === 'chaining_lift' ? r.chaining_lift : null; if (y == null) continue;
    shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color: tok('muted'), width: 1, dash: 'dot' } });
    notes.push({ xref: 'paper', x: 1, y, xanchor: 'right', yanchor: 'bottom', showarrow: false, text: esc(String(r.model).split('/').pop()), font: { size: 9, color: tok('muted') } });
  }
  if (what === 'logic_gain') shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0.1, y1: 0.1, line: { color: tok('accent'), width: 1.2, dash: 'dot' } });
  if (what === 'chaining_lift') shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: lb.chaining_threshold ?? 0.1, y1: lb.chaining_threshold ?? 0.1, line: { color: tok('accent'), width: 1.2, dash: 'dot' } });
  plot('voyageclimb', traces, layout({ xaxis: { title: { text: 'step' } }, yaxis: { title: { text: what === 'climb' ? 'climb (0 to 5)' : what === 'logic_gain' ? 'chaining gain (logic deck)' : 'chaining lift' }, ...(what === 'climb' ? { range: [0, 5.2], dtick: 1 } : {}) }, shapes, annotations: notes, height: 380 }));
}

// ---- the induction head (the induction expedition): the trigram engine against its random twin
export function drawInductionCharts(v: Expedition, d: SeriesMap | null): void {
  const runs = (v.runs || []).filter((r) => r.name);
  if (!runs.length) {
    ['indnevermore', 'indprev', 'indcopy'].forEach((id) => empty(id, 'no voyage yet: the trigram engine and its random twin are at the top of the queue'));
    return;
  }
  if (!d) return;
  const twin = (r: any): boolean => /random/.test(r.name);
  const seedOf = (r: any): string => (r.name.match(/-s(\d+)$/) || [])[1] || '1';
  const draw = (id: string, metric: string, mark: number, label: string): void => {
    const traces: any[] = [], shapes: any[] = [];
    for (const r of runs) {
      const sr = (d[r.name] || {})[metric]; if (!sr) continue;
      const col = twin(r) ? tok('muted') : tok('good');
      traces.push({ x: sr[0], y: sr[1], mode: 'lines', name: `${twin(r) ? 'random twin' : 'trigram engine'}, seed ${seedOf(r)}`, line: { color: col, width: 1.8, dash: seedOf(r) === '1' ? 'solid' : 'dash' },
        hovertemplate: `${esc(r.name)}<br>step %{x}<br>${label} %{y:.3f}<extra></extra>` });
      const i = sr[1].findIndex((x) => x != null && x >= mark);
      if (i >= 0) traces.push({ x: [sr[0][i]], y: [sr[1][i]], mode: 'markers', marker: { color: col, size: 10, symbol: 'star' }, showlegend: false, hovertemplate: `${esc(r.name)} first lights it at step ${sr[0][i]}<extra></extra>` });
    }
    if (!traces.length) { empty(id, 'no readings yet'); return; }
    shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: mark, y1: mark, line: { color: tok('accent'), dash: 'dot', width: 1.4 } });
    plot(id, traces, layout({ xaxis: { title: { text: 'step' } }, yaxis: { title: { text: label } }, shapes, legend: { orientation: 'h', y: -0.2 } }));
  };
  draw('indnevermore', IND_METRICS.nev, 0.3, 'Nevermore (natural score)');
  draw('indprev', IND_METRICS.prev, 0.5, 'previous-word');
  draw('indcopy', IND_METRICS.copy, 0.5, 'copy gain (nats/token)');
}

// ---- the knockout (knockout): each reference model's four cards silenced, with its random controls
export function knockoutHtml(d: any): string {
  const rs = (d && d.results) || [];
  if (!rs.length) return '<div class="empty">no knockout has finished yet: the first, Qwen3 4B, takes about an hour</div>';
  return rs.map((k: any, i: number) => `<div class="komodel"><h3><a href="/leaderboard/competitor/${encodeURIComponent(k.model)}">${esc(k.label || k.model)}</a></h3>${knockoutBlock(k, 'kochart' + i)}</div>`).join('');
}
export function drawKnockoutCharts(d: any): void {
  const rs = (d && d.results) || [];
  rs.forEach((k: any, i: number) => { if (document.getElementById('kochart' + i)) knockoutChart(k, 'kochart' + i); });
}

// ---- the journey through the layers (lib/journey.ts): one or two voyages read up their stack at one step
const journeyCache = new Map<string, { m: Record<string, any>; t: number }>();
let sieveDef: any = null;
async function runMetrics(id: string): Promise<Record<string, any>> {
  const c = journeyCache.get(id);
  if (c && Date.now() - c.t < 15000) return c.m;
  const m = await get<Record<string, any>>('/api/metrics?run=' + encodeURIComponent(id));
  journeyCache.set(id, { m, t: Date.now() });
  return m;
}
const kinksFor = (m: Record<string, any>): Record<string, any> => Object.fromEntries(
  Object.entries(kinksOf(m as Record<string, number[][]>, 'grad_norm/')).map(([k, v]) => [groupOf(k, 'grad_norm/'), v]),
);
const stepsOf = (m: Record<string, any>): number[] => {
  const s = soundingSteps(m as Record<string, number[][]>);
  return s.length ? s : (m['grad_norm/layer_0'] ? (m['grad_norm/layer_0'][0] as number[]) : []);
};

export interface JourneyArgs {
  v: Expedition;
  detail: any;
  a: string | null;
  b: string | null;
  idx: number | null;
  modules: Set<string>;
}

export async function drawJourneyPanel({ v, detail, a, b, idx, modules }: JourneyArgs): Promise<void> {
  const viewA = document.getElementById('journeyviewA');
  const viewB = document.getElementById('journeyviewB');
  if (!viewA || !viewB) return;
  const runs = v.runs.filter((r) => !r.set_aside);
  if (!runs.length) { viewA.innerHTML = '<div class="empty">no voyages on this expedition yet</div>'; viewB.innerHTML = ''; return; }
  if (!a) return;
  if (!sieveDef) { try { sieveDef = await get('/api/sieves'); } catch { return; } }
  let mA: Record<string, any>, mB: Record<string, any> | null = null;
  try { mA = await runMetrics(a); if (b) mB = await runMetrics(b); } catch { return; }
  const steps = stepsOf(mA), slider = document.getElementById('journeystep') as HTMLInputElement | null;
  const last = Math.max(0, steps.length - 1), i = idx == null ? last : Math.min(idx, last), step = steps[i] ?? 0;
  if (slider) { slider.max = String(last); slider.value = String(i); slider.disabled = steps.length < 2; }
  const jst: any = (await stagesFor([a]))[a], here: any = stageAt(jst, step);
  const label = document.getElementById('journeylabel');
  if (label) label.textContent = steps.length ? `step ${step}${here ? ` · stage ${here.index + 1}: ${here.name}` : ''} · reading ${i + 1} of ${steps.length}${idx == null ? ' (latest, live)' : ''}` : 'no readings yet';
  const lastStep = steps.length ? steps[steps.length - 1] : 0, segs = document.getElementById('journeystages');
  if (segs) {
    segs.style.display = jst && jst.length ? '' : 'none';
    if (jst && jst.length) segs.innerHTML = jst.map((s: any) => `<span class="${here && here.index === s.index ? 'on' : ''}" style="flex:${Math.max(1, Math.min(s.last_step, lastStep) - s.first_step + 1)}" title="${esc(s.name)}: steps ${s.first_step}–${s.last_step}">${esc(s.name)}</span>`).join('');
  }
  const runOf = (id: string | null): any => runs.find((r) => r.run_id === id);
  const tpOf = (id: string | null): any => detail && ((detail.runs || []).find((x: any) => x.run_id === id) || {}).transplant;
  const labelOf = (r: any): string => r ? `${r.ship_name || r.ship || r.name} · ${r.name}` : 'a voyage';
  drawJourney(viewA, mA, step, sieveDef, { modules, kinks: kinksFor(mA), title: labelOf(runOf(a)), transplant: tpOf(a) });
  document.querySelector('#journeypanel .journeys')?.classList.toggle('two', !!mB);
  if (mB) drawJourney(viewB, mB, step, sieveDef, { modules, kinks: kinksFor(mB), title: labelOf(runOf(b)) + ' (at the same step)', transplant: tpOf(b) });
  else viewB.innerHTML = '';
}
