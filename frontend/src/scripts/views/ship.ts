// The pure data helpers behind the ship-page panels, extracted (and typed) from the view monolith. No DOM
// and no module state: each takes the payload it reads and returns the values the renderer writes. The DOM
// renderers that write these values stay in scripts/dashboard.ts until the view split reaches them.

import { fmt, mean, esc, log10, big, fmtBytes } from '../../lib/format';
import { kinksOf, meanOf, rangeOf, ema, kinkSummary, stat, interp, type Kink } from '../../lib/analysis';
import type { Metrics } from '../types';
import { PALETTE, C, plot, empty, layout } from '../../lib/charts';
import { groupLabel, groupOf, topKeys, layerOnly } from '../../lib/metrics';
import { pillCls, alertCls, emptyCls } from '../../lib/ui';

export const SHELF_OF = (n: string): string | undefined => (n.match(/^content-([a-z]+)-v1/) || [])[1];
export const SHELF_LABEL: Record<string, string> = { random: 'Flotsam · random (the null)', greek: 'Paralus · Greek polis', islamic: 'Dhow · Islamic golden age', renaissance: 'Santa Maria · Renaissance', about: 'Cutty Sark · about the ages' };
export const CURATED = ['greek', 'islamic', 'renaissance', 'about'];

export const holeMeta = (r: any): Record<string, any> => {
  const meta: Record<string, any> = {};
  for (const sets of Object.values((r.eval_sets && r.eval_sets.data.sets) || {}) as any[])
    for (const b of sets) meta[b.book_id] = b;
  return meta;
};

export interface BookSeries {
  id: string;
  title: string;
  family: string;
  x: number[];
  y: number[];
}

export const bookSeries = (m: Metrics, r: any): BookSeries[] => {
  const rec = (r.recipe && r.recipe.data) || [];
  const meta: Record<string, any> = {};
  for (const b of rec) meta[b.book_id] = b;
  return Object.keys(m).filter((k) => k.startsWith('loss/book/')).map((k) => {
    const id = k.slice('loss/book/'.length);
    const b = meta[id] || { title: id, family: '' };
    return { id, title: b.title, family: b.family, x: m[k][0], y: m[k][1] };
  });
};

export const meanCurve = (books: BookSeries[], steps: number[]): (number | null)[] =>
  steps.map((st) => mean(books.map((b) => { const j = b.x.indexOf(st); return j < 0 ? null : b.y[j]; }).filter((v): v is number => v != null)));

export const earliestKink = (r: any): string => {
  const ks = kinksOf(r.push || {}, 'grad_norm/');
  const firm = Object.entries(ks).filter(([k, v]) => k.split('/')[1].startsWith('layer_') && !v.tentative).sort((a, b) => a[1].step - b[1].step);
  return firm.length ? `L${firm[0][0].split('_').pop()} ${firm[0][1].kind} @ ${firm[0][1].step}` : '–';
};

export interface RuleRow {
  k: string;
  text?: string;
  cls: string;
  m?: number;
  d?: number;
  n?: number;
  spread?: number | null;
  out?: boolean;
}

export interface RuleVerdict {
  line: string;
  cls: string;
  rows: RuleRow[];
  c?: number;
  S?: number;
}

// groups: {shelf: [values]}; the null is Flotsam's spread (S = its range); a shelf clears it when
// its mean lies more than 2S from Flotsam's centre
export function ruleVerdict(groups: Record<string, (number | null | undefined)[]>, unit: string, digits: number): RuleVerdict {
  const F = (groups.random || []).filter((v): v is number => v != null);
  if (F.length < 2) return { line: `waiting for the random libraries (${F.length} of 3 finished)`, cls: 'open', rows: [] };
  const c = meanOf(F)!;
  const S = rangeOf(F)!;
  const rows: RuleRow[] = CURATED.map((k) => {
    const v = (groups[k] || []).filter((x): x is number => x != null);
    if (!v.length) return { k, text: 'not yet', cls: 'open' };
    const m = meanOf(v)!;
    const d = m - c;
    const out = Math.abs(d) > 2 * S;
    return { k, m, d, n: v.length, spread: rangeOf(v), out, text: `${fmt(m, digits)} (${v.length} ship${v.length > 1 ? 's' : ''}), ${d >= 0 ? '+' : ''}${fmt(d, digits)} from random`, cls: out ? 'yes' : 'no' };
  });
  const moved = rows.filter((r) => r.out);
  const line = moved.length ? `Content has a detectable bearing: ${moved.map((r) => SHELF_LABEL[r.k].split(' · ')[0]).join(', ')} ${moved.length > 1 ? 'lie' : 'lies'} more than 2S from the random libraries (centre ${fmt(c, digits)}, S ${fmt(S, digits)}${unit}).`
    : `No detectable bearing so far: every curated library lies within 2S of the random libraries (centre ${fmt(c, digits)}, S ${fmt(S, digits)}${unit}).`;
  return { line, cls: moved.length ? 'yes' : 'no', rows, c, S };
}

export function pairVerdict(groups: Record<string, (number | null | undefined)[]>, a: string, b: string, _digits: number): { d: number; bar: number; out: boolean } | null {
  const A = (groups[a] || []).filter((v): v is number => v != null);
  const B = (groups[b] || []).filter((v): v is number => v != null);
  if (A.length < 2 || B.length < 2) return null;
  const d = meanOf(A)! - meanOf(B)!;
  const bar = 2 * Math.max(rangeOf(A)!, rangeOf(B)!);
  return { d, bar, out: Math.abs(d) > bar };
}

// ---- the chart panels of the ship page (moved from the view monolith; they write the DOM, so they stay
// here until the view split reaches them, but they are typed and share no module state)

export function comparePanel(cmp: any[]): void {
  const data: any[] = [];
  cmp.forEach((r, i) => {
    if (!r.bpb.length) return;
    const col = PALETTE[i % PALETTE.length];
    const name = `${r.ship || r.name} · ${r.preset} · ${r.n_books ?? '?'} books · seed ${r.seed}`;
    data.push({ x: r.tokens, y: r.bpb, name, mode: 'lines+markers', line: { color: col, width: 2 }, marker: { size: 6 },
      hovertemplate: `${esc(name)}<br>%{x:,.0f} tokens<br>%{y:.4f} bpb<extra></extra>` });
    if (r.bpb_en.length) data.push({ x: r.tokens.slice(0, r.bpb_en.length), y: r.bpb_en, name: name + ' (en)', mode: 'lines', line: { color: col, width: 1, dash: 'dot' }, showlegend: false,
      hovertemplate: `${esc(name)} (en)<br>%{x:,.0f} tokens<br>%{y:.4f} bpb<extra></extra>` });
  });
  if (!data.length) return empty('compare', 'no scored voyage yet');
  plot('compare', data, layout({ xaxis: { title: 'tokens seen', gridcolor: C.line }, yaxis: { title: 'hole-card bits per byte', gridcolor: C.line } }));
}

export function lossPanel(m: Metrics, sets: string[]): void {
  if (!m.loss) return empty('loss');
  const [s, v] = m.loss;
  const data: any[] = [
    { x: s, y: v, name: 'loss', type: 'scattergl', mode: 'lines', line: { color: C.track, width: 1 } },
    { x: s, y: ema(v, 100), name: 'EMA 100', type: 'scattergl', mode: 'lines', line: { color: C.blue, width: 2 } },
  ];
  const palette = [C.accent, C.good, C.bad, C.c5];
  sets.forEach((set, i) => {
    const k = `eval/${set}/ce_mean`;
    if (m[k]) data.push({ x: m[k][0], y: m[k][1], name: `${set} CE mean`, mode: 'markers+lines', line: { dash: 'dot', color: palette[i % 4] }, marker: { size: 8, color: palette[i % 4] } });
    const ken = `eval/${set}/ce_mean_en`;
    if (m[ken]) data.push({ x: m[ken][0], y: m[ken][1], name: `${set} CE mean (en)`, mode: 'markers', marker: { size: 7, symbol: 'diamond', color: palette[(i + 1) % 4] } });
  });
  if (m.lr) data.push({ x: m.lr[0], y: m.lr[1], name: 'lr', yaxis: 'y2', mode: 'lines', line: { color: C.muted, width: 1, dash: 'dash' } });
  plot('loss', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token', gridcolor: C.line },
    yaxis2: { overlaying: 'y', side: 'right', title: 'lr', showgrid: false, exponentformat: 'e' } }));
}

export function bpbPanel(evals: any[], r: any): void {
  if (!evals.length) return empty('bpb');
  const meta = holeMeta(r);
  const by: Record<string, any[]> = {};
  for (const e of evals) (by[e.book_id] ||= []).push(e);
  const data = Object.entries(by).map(([b, rows]) => { const t = meta[b] ? `${meta[b].title} (${meta[b].language})` : b; return {
    x: rows.map((r) => r.step), y: rows.map((r) => r.bpb), name: t, mode: 'lines+markers', marker: { size: 5 },
    hovertemplate: `${esc(t)}<br>step %{x}<br>%{y:.4f} bpb<extra></extra>` }; });
  plot('bpb', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'bits per byte', gridcolor: C.line },
    legend: { orientation: 'v', x: 1.02, y: 1, font: { size: 10 } }, margin: { l: 50, r: 10, t: 10, b: 36 } }));
}

export function speedPanel(m: Metrics): void {
  if (!m.tokens_per_s) return empty('speed');
  const data: any[] = [{ x: m.tokens_per_s[0], y: ema(m.tokens_per_s[1], 20), name: 'tokens/s (EMA 20)', mode: 'lines', line: { color: C.good } }];
  if (m.mem_gb) data.push({ x: m.mem_gb[0], y: m.mem_gb[1], name: 'peak memory GB', yaxis: 'y2', mode: 'lines+markers', line: { color: C.accent }, marker: { size: 4 } });
  plot('speed', data, layout({ yaxis: { title: 'tokens / s', gridcolor: C.line }, yaxis2: { overlaying: 'y', side: 'right', title: 'GB', showgrid: false, rangemode: 'tozero' } }));
}

export function heat(id: string, m: Metrics, prefix: string, kinks: Record<string, Kink>, colorbar: string): void {
  const keys = topKeys(m, prefix);
  if (!keys.length) return empty(id);
  const x = m[keys[0]][0];
  const data: any[] = [{ type: 'heatmap', x, y: keys.map((k) => groupLabel(groupOf(k, prefix))), z: keys.map((k) => m[k][1].map(log10)),
    colorscale: 'Viridis', colorbar: { title: colorbar, thickness: 10 }, hovertemplate: 'step %{x}<br>%{y}<br>log10 %{z:.2f}<extra></extra>' }];
  const kx: number[] = [], ky: string[] = [], kt: string[] = [];
  for (const k of keys) { const kk = kinks[k]; if (kk) { kx.push(kk.step); ky.push(groupLabel(groupOf(k, prefix))); kt.push(`kink at ${kk.step}${kk.tentative ? ' (tentative)' : ''}`); } }
  if (kx.length) data.push({ type: 'scatter', x: kx, y: ky, text: kt, mode: 'markers', marker: { symbol: 'diamond', size: 9, color: '#fff', line: { color: '#000', width: 1 } }, hovertemplate: '%{y}<br>%{text}<extra></extra>', showlegend: false });
  plot(id, data, layout({ margin: { l: 80, r: 10, t: 10, b: 36 }, xaxis: { title: 'step', gridcolor: C.line } }));
}

export function kinkPanel(m: Metrics, kinks: Record<string, Kink>): void {
  const prefix = 'grad_norm/';
  const keys = layerOnly(m, prefix);
  if (!keys.length) { empty('kinks'); document.querySelector('#kinktable tbody')!.innerHTML = ''; return; }
  const data: any[] = [];
  keys.forEach((k, i) => {
    const g = groupOf(k, prefix);
    const [x, v] = m[k];
    const col = PALETTE[i % PALETTE.length];
    data.push({ x, y: v.map(log10), name: groupLabel(g), mode: 'lines', line: { color: col, width: 1.5 }, hovertemplate: `${groupLabel(g)}<br>step %{x}<br>log10 %{y:.2f}<extra></extra>` });
    const kk = kinks[k];
    if (kk) {
      const left = kk.xs.slice(0, kk.k), right = kk.xs.slice(kk.k);
      data.push({ x: left, y: left.map((s) => kk.L.a + kk.L.b * s), mode: 'lines', line: { color: col, width: 1, dash: 'dot' }, showlegend: false, hoverinfo: 'skip' });
      data.push({ x: right, y: right.map((s) => kk.R.a + kk.R.b * s), mode: 'lines', line: { color: col, width: 1, dash: 'dot' }, showlegend: false, hoverinfo: 'skip' });
      data.push({ x: [kk.step], y: [kk.L.a + kk.L.b * kk.step], mode: 'markers', marker: { symbol: 'diamond', size: 10, color: col, line: { color: '#fff', width: 1 } }, showlegend: false,
        hovertemplate: `${groupLabel(g)} kink at step ${kk.step}<br>before ${fmt(kk.before, 3)} / after ${fmt(kk.after, 3)} log10 per 100 steps<extra></extra>` });
    }
  });
  plot('kinks', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'log10 gradient norm', gridcolor: C.line }, legend: { orientation: 'h', y: -0.2, font: { size: 10 } } }));
  document.querySelector('#kinktable tbody')!.innerHTML = keys.map((k) => {
    const kk = kinks[k], g = groupLabel(groupOf(k, prefix));
    if (!kk) return `<tr><td>${g}</td><td colspan=6 class="t">fewer than six records</td></tr>`;
    return `<tr><td>${g}</td><td>${kk.step}</td><td>${kk.kind}</td><td>${fmt(kk.before, 3)}</td><td>${fmt(kk.after, 3)}</td><td>${fmt(kk.strength, 2)}</td><td class="t">${kk.tentative ? 'tentative' : ''}</td></tr>`;
  }).join('');
  const firm = keys.map((k) => kinks[k]).filter((kk): kk is Kink => !!kk && !kk.tentative);
  document.getElementById('kinknote')!.textContent = 'Slopes are log10 of the norm per 100 steps. ' + (!firm.length
    ? 'The fit starts where warmup ends. A kink is tentative until ten records (500 steps) are in and the two-line fit removes at least a quarter of the one-line fit\'s residual. Turned up: the push bottomed and is rising again (the loss plateauing while the step stays large); turned down: it peaked; flattened or steepened: still falling, slower or faster; eased: still rising, slower.'
    : `${firm.length} of ${keys.length} layers have a firm kink; the earliest is at step ${Math.min(...firm.map((kk) => kk.step))}, the latest at ${Math.max(...firm.map((kk) => kk.step))}. A layer whose push flattens early has settled early; one that keeps falling is still being taught.`);
}

export function attnPanels(m: Metrics): void {
  for (const [id, prefix, title] of [['attnpush', 'grad_norm/', 'log10 push ratio'], ['attnmove', 'update_ratio/', 'log10 move ratio']]) {
    const layers = layerOnly(m, prefix).map((k) => groupOf(k, prefix));
    const rows = layers.filter((g) => m[`${prefix}${g}/attn`] && m[`${prefix}${g}/mlp`]);
    if (!rows.length) { empty(id, 'no attn/mlp rows yet (written by voyages started after 2026-11-06)'); continue; }
    const x = m[`${prefix}${rows[0]}/attn`][0];
    const z = rows.map((g) => { const a = m[`${prefix}${g}/attn`][1], b = m[`${prefix}${g}/mlp`][1]; return a.map((v, i) => v > 0 && b[i] > 0 ? Math.log10(v / b[i]) : null); });
    plot(id, [{ type: 'heatmap', x, y: rows.map(groupLabel), z, colorscale: 'RdBu', zmid: 0, colorbar: { title, thickness: 10 }, hovertemplate: 'step %{x}<br>%{y}<br>%{z:.2f}<extra></extra>' }],
      layout({ margin: { l: 80, r: 10, t: 10, b: 36 }, xaxis: { title: 'step', gridcolor: C.line } }));
  }
}

export function bookPanels(m: Metrics, r: any, series: BookSeries[], fams: string[], famColour: (f: string) => string): void {
  const traits = r.traits || {};
  if (!series.length) { empty('bookloss'); empty('kindloss'); empty('halflife'); return; }
  const seen = new Set<string>();
  plot('bookloss', series.map((s) => ({ x: s.x, y: s.y, name: s.family, legendgroup: s.family, showlegend: !seen.has(s.family) && !!seen.add(s.family), mode: 'lines', line: { color: famColour(s.family), width: 1 }, opacity: 0.8,
    hovertemplate: `${esc(s.title)} (${esc(s.family)})<br>step %{x}<br>%{y:.3f} nats<extra></extra>` })),
    layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token', gridcolor: C.line } }));

  const steps = [...new Set(series.flatMap((s) => s.x))].sort((a, b) => a - b);
  const kdata: any[] = [];
  (['fiction', 'verse', 'first_person'] as const).forEach((t, i) => {
    for (const val of [1, 0]) {
      const books = series.filter((s) => traits[s.id] && traits[s.id][t] === val);
      if (!books.length) continue;
      kdata.push({ x: steps, y: meanCurve(books, steps), name: `${t.replace('_', ' ')}${val ? '' : ': not'} (${books.length})`, mode: 'lines', line: { color: PALETTE[i], width: val ? 2.5 : 1.5, dash: val ? 'solid' : 'dot' } });
    }
  });
  if (!kdata.length) empty('kindloss', 'no traits for these books (lists/traits.csv)');
  else plot('kindloss', kdata, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token, mean over books', gridcolor: C.line } }));

  const hl = series.map((s) => {
    const y0 = s.y[0], ymin = Math.min(...s.y), target = y0 - (y0 - ymin) / 2;
    const j = s.y.findIndex((v) => v <= target), n = s.y.length;
    const last = s.y[n - 1], prev = s.y[Math.max(0, n - 3)], dstep = s.x[n - 1] - s.x[Math.max(0, n - 3)];
    return { ...s, half: j < 0 ? null : s.x[j], drop: y0 - ymin, last, slope: dstep ? (last - prev) / dstep * 100 : 0 };
  }).filter((h) => h.half != null && h.drop > 0).sort((a, b) => a.half! - b.half! || b.drop - a.drop);
  if (!hl.length) return empty('halflife');
  const kind = (h: any): string => { const t = traits[h.id]; return t ? [t.fiction ? 'fiction' : 'non-fiction', t.verse ? 'verse' : null, t.first_person ? 'first person' : null].filter(Boolean).join(', ') : ''; };
  // labels must be unique: Plotly puts bars with the same category in one slot, and two volumes of
  // one book cut to 40 characters collide (The Gaming Table vols 1 and 2, Edith Wharton parts 1 and 2)
  const short = hl.map((h) => h.title.slice(0, 40));
  const count: Record<string, number> = {};
  short.forEach((t) => count[t] = (count[t] || 0) + 1);
  const labels = hl.map((h, i) => count[short[i]] > 1 ? `${short[i].slice(0, 32)}… (${h.id})` : short[i]);
  plot('halflife', [{ type: 'bar', x: labels, y: hl.map((h) => h.half), marker: { color: hl.map((h) => famColour(h.family)) },
    text: hl.map((h) => `${h.family}${kind(h) ? ' · ' + kind(h) : ''}<br>half-life step ${h.half} · drop so far ${fmt(h.drop, 2)} nats<br>latest ${fmt(h.last, 3)} · slope ${fmt(h.slope, 3)} per 100 steps`), hovertemplate: '%{x}<br>%{text}<extra></extra>' }],
    layout({ margin: { l: 50, r: 10, t: 10, b: 140 }, xaxis: { tickangle: -60, tickfont: { size: 9 }, gridcolor: C.line }, yaxis: { title: 'half-life (step)', gridcolor: C.line } }));
}

export function languagePanels(r: any, evals: any[], series: BookSeries[], fams: string[], famColour: (f: string) => string): void {
  const rec = r.recipe && r.recipe.data;
  if (!rec) { empty('families'); empty('familyloss'); empty('familybpb'); return; }
  const fam: Record<string, number> = {};
  for (const b of rec) fam[b.family] = (fam[b.family] || 0) + b.tokens;
  const fk = Object.keys(fam).sort((a, b) => fam[b] - fam[a]);
  plot('families', [{ type: 'bar', x: fk, y: fk.map((k) => fam[k]), marker: { color: fk.map(famColour) }, hovertemplate: '%{x}<br>%{y:,} tokens<extra></extra>' }],
    layout({ yaxis: { title: 'tokens per pass', gridcolor: C.line } }));
  if (!series.length) empty('familyloss');
  else {
    const steps = [...new Set(series.flatMap((s) => s.x))].sort((a, b) => a - b);
    plot('familyloss', fams.map((f) => { const books = series.filter((s) => s.family === f); return { x: steps, y: meanCurve(books, steps), name: `${f} (${books.length})`, mode: 'lines', line: { color: famColour(f), width: 2 } }; }).filter((t) => t.y.some((v) => v != null)),
      layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token, mean over books', gridcolor: C.line } }));
  }
  if (!evals.length) return empty('familybpb');
  const meta = holeMeta(r), last = Math.max(...evals.map((e) => e.step));
  const byFam: Record<string, number[]> = {};
  for (const e of evals.filter((e) => e.step === last)) { const f = (meta[e.book_id] || {}).family || '?'; (byFam[f] ||= []).push(e.bpb); }
  const ff = Object.keys(byFam).sort((a, b) => mean(byFam[a])! - mean(byFam[b])!);
  plot('familybpb', [{ type: 'bar', x: ff, y: ff.map((f) => mean(byFam[f])), marker: { color: ff.map(famColour) }, text: ff.map((f) => `${byFam[f].length} book${byFam[f].length > 1 ? 's' : ''}`), hovertemplate: '%{x}<br>%{y:.4f} bpb · %{text}<extra></extra>' }],
    layout({ yaxis: { title: `bits per byte at step ${last}`, gridcolor: C.line } }));
}

export function fallbackPanel(r: any): void {
  const rec = r.recipe && r.recipe.data;
  if (!rec) return empty('fallback');
  const stats = (r.tokeniser && r.tokeniser.stats) || {};
  const rows = rec.map((b: any) => ({ ...b, rate: (stats[b.book_id] || {}).byte_fallback_rate ?? b.byte_fallback_rate ?? 0 }))
    .sort((a: any, b: any) => b.rate - a.rate).slice(0, 25);
  plot('fallback', [{ type: 'bar', orientation: 'h', y: rows.map((b: any) => `${b.title.slice(0, 34)} (${b.language})`).reverse(),
    x: rows.map((b: any) => b.rate * 100).reverse(), marker: { color: C.accent }, hovertemplate: '%{y}<br>%{x:.3f}% byte tokens<extra></extra>' }],
    layout({ margin: { l: 230, r: 10, t: 10, b: 36 }, xaxis: { title: '% of tokens that are byte pieces (top 25)', gridcolor: C.line }, yaxis: { tickfont: { size: 10 } } }));
}

export function headline(r: any, m: Metrics, kinks: Record<string, Kink>): void {
  const run = r.run;
  const wall = run.wall_minutes != null ? fmt(run.wall_minutes, 1) + ' min' : '–';
  const [kinkLine, kinkNote] = kinkSummary(m, kinks);
  // the shelf this run was fed: books, tokens under its own tokeniser, and bytes (tokens × bytes a token)
  const rec = (r.recipe && r.recipe.data) || [];
  const shelf = { books: rec.length, tokens: rec.reduce((a: number, b: any) => a + (b.tokens || 0), 0), bytes: rec.reduce((a: number, b: any) => a + (b.tokens || 0) * (b.bytes_per_token || 0), 0) };
  document.getElementById('strip')!.innerHTML = [
    stat('ship', esc(run.ship || run.name || ''), `${esc(run.name || '')} · <span class="mono">${run.run_id.slice(0, 12)}</span> <span class="${pillCls(run.status.split(':')[0])}">${esc(run.status)}</span>`),
    stat('kinks', `<span style="font-size:15px">${esc(kinkLine)}</span>`, esc(kinkNote)),
    stat('weights', big(r.n_params_total), `${esc(r.spec.model.preset)} · ${big(r.n_params_non_embedding)} non-embedding + ${big(r.n_params_embedding)} embedding`),
    stat('shelf', `${shelf.books} books`, `${big(shelf.tokens)} tokens · ${fmtBytes(shelf.bytes)} · read ${r.spec.data.passes}×`),
    stat('tokens / s', big(r.tokens_per_s), 'mean of last 50 steps'),
    stat(run.status === 'running' ? 'eta' : 'wall time', run.status === 'running' && r.eta_minutes != null ? `${fmt(r.eta_minutes, 1)} min` : wall, run.status === 'running' ? `${big(r.tokens_seen)} of ${big(r.tokens_planned)} tokens` : (run.finished || '')),
  ].join('');
  const ch = r.chinchilla || {}, latest = r.hole_bpb_latest, prev = r.hole_bpb_previous;
  document.getElementById('numbers')!.innerHTML = [
    stat('preset', esc(r.spec.model.preset), `N = ${big(r.n_params_non_embedding)} non-embedding`),
    stat('tokens seen', big(r.tokens_seen), `of ${big(r.tokens_planned)} planned`),
    stat('hole-card bpb mean', latest ? fmt(latest.value) : '–', latest ? `step ${latest.step}` + (prev ? ` · prev ${fmt(prev.value)} @ ${prev.step}` : '') : ''),
    stat('Chinchilla L(N,D)', fmt(ch.L_planned), `nats/token, indicative · D=${big(ch.D_planned)}; unique: ${fmt(ch.L_unique)}`),
    stat('gap (en hole-card CE − L)', fmt(ch.gap_planned), `en CE ${fmt(r.hole_ce_mean_en)} nats`),
  ].join('');
  document.getElementById('title')!.textContent = `${run.ship ? run.ship + ' · ' : ''}${run.name} · ${run.run_id.slice(0, 12)} · ${run.hardware || ''}`;
}

// ---- the claim: the hypothesis in the order a sceptic wants it, and the ledger's reading of it
export function claimPanel(cmp: any[]): void {
  const shelves: Record<string, any[]> = {};
  for (const r of cmp) {
    if (!r.bpb.length) continue;
    (shelves[`${r.preset} · ${r.n_books ?? '?'} books`] ||= []).push(r);
  }
  const finals = Object.entries(shelves).map(([key, runs]) => {
    const done = runs.filter((r) => r.status === 'finished');
    const vals = done.map((r) => r.bpb[r.bpb.length - 1]);
    return { key, runs, seeds: new Set(done.map((r) => r.seed)).size, best: vals.length ? Math.min(...vals) : null, spread: vals.length > 1 ? Math.max(...vals) - Math.min(...vals) : null };
  });
  const scored = finals.filter((f) => f.best != null), seeded = finals.filter((f) => f.spread != null);
  let verdict: string, cls = 'open';
  if (scored.length < 2) verdict = `Not testable yet: ${scored.length} finished librar${scored.length === 1 ? 'y' : 'ies'} on the ledger. Two libraries at the same size and tokens are the first comparison; a second seed of one of them is the error bar.`;
  else {
    const sorted = scored.slice().sort((a, b) => a.best! - b.best!);
    const diff = sorted[sorted.length - 1].best! - sorted[0].best!;
    const spread = seeded.length ? Math.max(...seeded.map((f) => f.spread!)) : null;
    verdict = `Best library so far: ${sorted[0].key} at ${fmt(sorted[0].best!, 4)} bpb; shelf-to-shelf difference ${fmt(diff, 4)}`;
    if (spread == null) verdict += '; no library has two finished seeds yet, so the difference has no error bar.';
    else { cls = diff > 2 * spread ? 'yes' : 'no'; verdict += `; seed-to-seed spread ${fmt(spread, 4)}.` + (cls === 'yes' ? ' The libraries differ by more than the seeds: the claim stands at this size.' : ' The seeds are as wide as the libraries: the difference is noise at this size.'); }
    verdict += ' Compared at each voyage’s final tokens; read the chart at matched tokens before quoting it.';
  }
  const rows = finals.map((f) => `<tr><td>${esc(f.key)}</td><td>${f.runs.length}</td><td>${f.seeds}</td><td>${fmt(f.best, 4)}</td><td>${f.spread == null ? '–' : fmt(f.spread, 4)}</td></tr>`).join('');
  document.getElementById('claim')!.innerHTML = `
    <div><div class="k">Claim</div><div class="v">Some books make the guessing better, faster. Hold the model still, change the library, and the hole-card score falls faster per token on some libraries than on others. The kind of book that buys the most fall is the finding, and the next library is built from it.</div></div>
    <div><div class="k">Measure</div><div class="v">Guessing accuracy: bits per byte on the hole cards, books the model is never trained on. Learning speed: how far that number falls per million tokens seen. Neither is ever read from a book on the library.</div></div>
    <div><div class="k">Prediction</div><div class="v">At the same size and the same tokens, two libraries differ by more than two seeds of the same library do, and the order of libraries holds one size up. The per-book contribution (the heart of the dice, section 13) then names the books that carried it.</div></div>
    <div><div class="k">What would show it wrong</div><div class="v">A seed-to-seed spread as wide as the shelf-to-shelf difference; or an order of libraries at 9M that flips at 21M. Either is published as a finding, not buried.</div></div>
    <div class="reading"><div class="k">The ledger’s reading</div><div class="${alertCls(cls)}">${verdict}</div>
      <table class="mt"><thead><tr><th>library</th><th>voyages</th><th>finished seeds</th><th>best final bpb</th><th>seed spread</th></tr></thead><tbody>${rows || '<tr><td colspan=5 class="${emptyCls(true)}">no scored voyage yet</td></tr>'}</tbody></table></div>`;
}

export const LADDER: [number, string, string, string][] = [
  [1, "knowing what it doesn't know", 'r1_calibration', 'correlation of its uncertainty with its loss'],
  [2, 'noticing the strange', 'r2_novelty_auc', 'AUC, unseen books against library books'],
  [3, 'learning from the page', 'r3_copy_gain', 'nats saved on a repeated span (and late minus early loss)'],
  [4, 'knowing a question', 'r4_question_auc', 'AUC, questions against statements, punctuation removed'],
  [5, 'expecting an answer', 'r5_expectancy', 'nats more uncertain after "?" than after "."'],
  [6, 'asking', 'r6_asking', 'log ratio of "?" where unsure, beyond the text'],
];

export function ladderPanel(r: any, m: Metrics): void {
  const c = r.curiosity && r.curiosity.data, el = document.getElementById('ladder')!, vd = document.getElementById('ladderverdict')!;
  if (!c) { el.innerHTML = '<div class="${emptyCls()}">no ladder rows yet: add <span class="mono">curiosity</span> to eval.evaluators, or re-score with <span class="mono">thorp eval RUN --evaluators curiosity</span></div>'; vd.innerHTML = ''; empty('laddertime', ''); return; }
  document.getElementById('ladderh')!.firstChild!.textContent = `The curiosity ladder at step ${r.curiosity.step} `;
  const order = c.highest === 0 ? 'No rung is present yet.' : c.in_order ? `In order: every rung up to ${c.highest} that could be tested is present, none above an absent one.` : `Out of order: rung ${c.highest} is present above an absent rung. That is a finding against the ladder at this size.`;
  vd.innerHTML = `<div class="reading"><div class="k">The ledger’s reading</div><div class="${alertCls(c.highest === 0 ? 'open' : c.in_order ? 'yes' : 'no')}">${order}</div></div>`;
  const floorOf = (k: number) => k === 2 ? c.floor_bow.r2 : k === 4 ? c.floor_bow.r4 : null;
  el.innerHTML = `<table><thead><tr><th>rung</th><th>measure</th><th>trained</th><th>untrained</th><th>token floor</th><th>status</th><th>reading</th></tr></thead><tbody>${
    LADDER.slice().reverse().map(([k, name, key, what]) => {
      const s = c.rungs[k] || { status: 'untestable', reason: '' };
      const cls = s.status === 'present' ? 'finished' : s.status === 'absent' ? 'failed' : 'running';
      return `<tr><td><b>${k}</b> ${esc(name)}</td><td class="note">${esc(what)}</td><td>${fmt(c.values[key], 3)}</td><td>${fmt(c.untrained[key], 3)}</td><td>${fmt(floorOf(k), 3)}</td>
        <td><span class="${pillCls(cls)}">${s.status}</span></td><td class="note">${esc(s.reason)}</td></tr>`;
    }).join('')}</tbody></table>`;
  // when each rung appears: one row per rung, a mark at every eval step, filled where present
  const data: any[] = [];
  for (const [k, name] of LADDER) {
    const s = m[`curiosity/rung_${k}`];
    if (!s) continue;
    data.push({ x: s[0], y: s[0].map(() => k), mode: 'markers', name: `${k} ${name}`, showlegend: false,
      marker: { size: 10, symbol: 'square', color: s[1].map((v) => v ? C.good : C.muted + '59') },
      hovertemplate: `${esc(name)}<br>step %{x}<extra></extra>` });
  }
  if (!data.length) return empty('laddertime', '');
  plot('laddertime', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'rung', dtick: 1, range: [0.5, 6.5], gridcolor: C.line } }));
}

export function samplesPanel(r: any): void {
  const el = document.getElementById('samples')!;
  if (!r.samples) { el.innerHTML = '<div class="${emptyCls()}">no samples yet</div>'; empty('top10'); return; }
  document.getElementById('samplesh')!.textContent = `Samples at step ${r.samples.step}`;
  el.innerHTML = r.samples.data.map((s: any) => `<div><span class="p">${esc(s.prompt)}</span> <span class="t">${s.temperature ? 'T=' + s.temperature : 'greedy'}</span><pre>${esc(s.prompt)}${esc(s.text)}</pre></div>`).join('');
  if (r.top10) {
    document.getElementById('top10h')!.textContent = `Next token after “${r.top10.data.prompt}”`;
    const t = r.top10.data.top.slice().reverse();
    plot('top10', [{ type: 'bar', orientation: 'h', y: t.map((x: any) => JSON.stringify(x.token.replace(/▁/g, ' '))), x: t.map((x: any) => x.p), marker: { color: C.good },
      hovertemplate: '%{y}<br>p = %{x:.4f}<extra></extra>' }], layout({ margin: { l: 110, r: 10, t: 10, b: 36 }, xaxis: { title: 'probability', gridcolor: C.line } }));
  }
}

export function contentPanel(ships: any[]): void {
  const el = document.getElementById('contentverdict')!, tb = document.getElementById('contentships')!;
  if (!ships.length) { el.innerHTML = '<div class="${emptyCls()}">no content ship on the ledger yet: they voyage after the night queue and the re-score (scripts/queue_content.sh)</div>'; tb.innerHTML = ''; empty('contentchart', ''); return; }
  // matched tokens: the smallest final tokens-seen among the ships that have finished
  const score = (r: any) => r.by_set && r.by_set.neutral;
  const done = ships.filter((r) => r.status === 'finished' && score(r));
  const T = done.length ? Math.min(...done.map((r) => score(r).tokens[score(r).tokens.length - 1])) : null;
  const at = (r: any) => T == null || !score(r) ? null : interp(score(r).tokens, score(r).bpb, T);
  const shelfOf = (r: any): string => SHELF_OF(r.name) ?? '';
  const group = (f: (r: any) => any) => { const g: Record<string, any[]> = {}; for (const r of done) (g[shelfOf(r)] ||= []).push(f(r)); return g; };
  const primary = ruleVerdict(group(at), ' bpb', 4);
  // secondary outcomes, each by the same rule
  const lastTraits = (r: any) => (r.traits.length ? r.traits[r.traits.length - 1].traits : {});
  const traitNames = [...new Set(done.flatMap((r) => Object.keys(lastTraits(r))))].filter((n) => !n.startsWith('family/')).sort();
  const kinkOf = (r: any) => { const ks = kinksOf(r.push || {}, 'grad_norm/'); const f = Object.entries(ks).filter(([k, v]) => k.split('/')[1].startsWith('layer_') && !v.tentative).map(([, v]) => v.step); return f.length ? Math.min(...f) : null; };
  const lastQuarter = (series: any, steps: number[]) => { if (!series) return null; const [x, v] = series; const cut = Math.max(...x) * 0.75; const vals = v.filter((_: number, i: number) => x[i] >= cut && v[i] > 0).map(Math.log10); return meanOf(vals); };
  const sieveOf = (r: any, key: string, src: any) => { const ks = Object.keys(src || {}).filter((k) => k.startsWith(key)); return meanOf(ks.map((k) => lastQuarter(src[k], [] as number[])).filter((v) => v != null)); };
  const secondary: [string, RuleVerdict][] = [
    ...traitNames.map((t) => [`trait: ${t.replace('_', ' ')} (best held-out AUC)`, ruleVerdict(group((r: any) => (lastTraits(r)[t] || {}).best ?? null), '', 3)] as [string, RuleVerdict]),
    ['kinks: earliest firm kink (step)', ruleVerdict(group(kinkOf), ' steps', 0)],
    ['sieves: push, last quarter (mean log10 over layers)', ruleVerdict(group((r: any) => sieveOf(r, 'grad_norm/layer_', r.push)), '', 3)],
    ['sieves: move, last quarter (mean log10 update ratio)', ruleVerdict(group((r: any) => sieveOf(r, 'update_ratio/layer_', r.move)), '', 3)],
    ['curiosity ladder: highest rung present', ruleVerdict(group((r: any) => r.ladder.length ? r.ladder[r.ladder.length - 1][1] : null), '', 1)],
  ];
  const g = group(at);
  const pairs = [['quality: Greek against Cutty Sark', 'greek', 'about'], ['quality: Islamic against Cutty Sark', 'islamic', 'about'], ['quality: Renaissance against Cutty Sark', 'renaissance', 'about'],
    ['type: Greek against Islamic', 'greek', 'islamic'], ['type: Greek against Renaissance', 'greek', 'renaissance'], ['type: Islamic against Renaissance', 'islamic', 'renaissance']]
    .map(([label, a, b]) => { const p = pairVerdict(g, a, b, 4); return `<tr><td>${label}</td><td>${p ? `${p.d >= 0 ? '+' : ''}${fmt(p.d, 4)} bpb` : '–'}</td><td>${p ? fmt(p.bar, 4) : '–'}</td><td>${p ? `<span class="${pillCls(p.out ? 'finished' : 'failed')}">${p.out ? 'differ' : 'within noise'}</span>` : 'needs two ships a side'}</td></tr>`; }).join('');
  el.innerHTML = `<div class="reading"><div class="k">The ledger’s reading: guessing (neutral deck, English bits per byte at ${T ? big(T) : '–'} tokens, ${done.length} of ${ships.length} ships finished)</div><div class="${alertCls(primary.cls)}">${primary.line}</div>
    <table class="mt"><thead><tr><th>library</th><th>against the random libraries</th></tr></thead><tbody>${primary.rows.map((r) => `<tr><td>${SHELF_LABEL[r.k]}</td><td><span class="verdict ${r.cls}" style="display:inline">${esc(r.text)}</span></td></tr>`).join('')}</tbody></table>
    <table class="mt"><thead><tr><th>quality and type</th><th>difference</th><th>twice the larger spread</th><th>reading</th></tr></thead><tbody>${pairs}</tbody></table>
    <table class="mt"><thead><tr><th>secondary outcome</th><th>reading (same rule: more than 2S from the random libraries)</th></tr></thead><tbody>${secondary.map(([label, v]) => `<tr><td>${esc(label)}</td><td><span class="verdict ${v.cls}" style="display:inline">${esc(v.line)}</span></td></tr>`).join('')}</tbody></table></div>`;
  tb.innerHTML = `<table style="margin-top:12px"><thead><tr><th>ship</th><th>library</th><th>its question</th><th>status</th><th>tokens</th><th>neutral bpb at T</th><th>earliest firm kink</th><th>highest rung</th></tr></thead><tbody>${
    ships.map((r) => `<tr><td><b>${esc(r.ship || r.name)}</b></td><td>${esc(SHELF_LABEL[shelfOf(r)] || '')}</td><td class="note">${esc(r.question || '')}</td><td><span class="${pillCls((r.status || '').split(':')[0])}">${esc((r.status || '').split(':')[0])}</span></td>
      <td>${score(r) ? big(score(r).tokens[score(r).tokens.length - 1]) : '–'}</td><td>${fmt(at(r), 4)}</td><td>${kinkOf(r) ?? '–'}</td><td>${r.ladder.length ? r.ladder[r.ladder.length - 1][1] : '–'}</td></tr>`).join('')}</tbody></table>`;
  const col: Record<string, string> = { random: C.muted, greek: C.blue, islamic: C.good, renaissance: C.accent, about: C.c5 };
  const data = ships.filter(score).map((r) => ({ x: score(r).tokens, y: score(r).bpb, name: r.ship, mode: 'lines+markers', line: { color: col[shelfOf(r)], width: 2 }, marker: { size: 5 },
    hovertemplate: `${esc(r.ship)}<br>%{x:,.0f} tokens<br>%{y:.4f} neutral bpb<extra></extra>` }));
  if (!data.length) return empty('contentchart', '');
  plot('contentchart', data, layout({ xaxis: { title: 'tokens seen', gridcolor: C.line }, yaxis: { title: 'neutral-deck bits per byte', gridcolor: C.line } }));
}

export const MATCH_AT = [16e6, 32e6, 64e6];

export function matchedPanel(cmp: any[]): void {
  const runs = cmp.filter((r) => r.bpb.length);
  if (!runs.length) { document.getElementById('matched')!.innerHTML = '<div class="${emptyCls()}">no scored voyage yet</div>'; return; }
  const rows = runs.map((r) => {
    const last = r.bpb.length - 1;
    return `<tr><td>${esc(r.ship || r.name)}</td><td>${r.seed ?? ''}</td><td class="mono">${esc(r.set)}</td><td>${r.n_books ?? '?'}</td><td>${big(r.tokens[last])}</td>
      ${MATCH_AT.map((x) => `<td>${fmt(interp(r.tokens, r.bpb, x), 4)}</td>`).join('')}
      <td><b>${fmt(r.bpb[last], 4)}</b></td><td>${fmt(r.bpb_en[r.bpb_en.length - 1], 4)}</td><td>${esc(earliestKink(r))}</td>
      <td><span class="${pillCls((r.status || '').split(':')[0])}">${esc((r.status || '').split(':')[0])}</span></td></tr>`;
  }).join('');
  document.getElementById('matched')!.innerHTML = `<table><thead><tr><th>ship</th><th>seed</th><th>set</th><th>books</th><th>tokens seen</th>
    ${MATCH_AT.map((x) => `<th>bpb @ ${big(x)}</th>`).join('')}<th>final bpb</th><th>final en</th><th>earliest firm kink</th><th>status</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="note" style="margin-top:6px">Compare only rows on the same set: hole-cards (13 books) and hole-cards-v2 (20 books, without Darwin and Einstein) are different decks.</div>`;
}

export function truthGapPanel(cmp: any[]): void {
  const lit = (r: any) => (r.by_set['hole-cards-v2'] ? 'hole-cards-v2' : 'hole-cards');
  const runs = cmp.filter((r) => r.by_set && r.by_set.truths && r.by_set[lit(r)]);
  const el = document.getElementById('truthgap')!;
  if (!runs.length) { el.innerHTML = '<div class="${emptyCls()}">no voyage has been scored on the truths deck yet (lists/truths.csv): re-score a finished voyage with <span class="mono">thorp eval RUN --sets lists/hole-cards-v2.csv lists/truths.csv</span></div>'; return; }
  const rows = runs.map((r) => {
    const T = r.by_set.truths, L = r.by_set[lit(r)];
    type Pt = [number, number, number, number | null];
    const pts = (T.steps.map((s: number, i: number) => [s, T.tokens[i], T.bpb[i], L.bpb[L.steps.indexOf(s)]]) as Pt[])
      .filter((p): p is [number, number, number, number] => p[3] != null);
    const first = pts[0], last = pts[pts.length - 1];
    if (!last) return '';
    const trend = pts.length > 1 ? fmt((last[2] - last[3]) - (first[2] - first[3]), 4) : '– (one step)';
    return `<tr><td>${esc(r.ship || r.name)}</td><td>${r.seed ?? ''}</td><td class="mono">${lit(r)}</td><td>${big(last[1])}</td><td>${fmt(last[2], 4)}</td><td>${fmt(last[3], 4)}</td><td><b>${fmt(last[2] - last[3], 4)}</b></td><td>${trend}</td></tr>`;
  }).join('');
  el.innerHTML = `<table><thead><tr><th>ship</th><th>seed</th><th>against</th><th>at tokens</th><th>truths bpb</th><th>literature bpb</th><th>truth gap</th><th>change since first scored</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// the Traits tab: the sort and step the viewer chose, kept here (not in the monolith's state) and in
// localStorage, so a redraw leaves the reader where they were
const traitView: { sort: string; step: number | null; followLatest?: boolean } = { sort: 'layer', step: null };
try { traitView.sort = localStorage.getItem('thorp.traitsort') || 'layer'; } catch { /* blocked */ }

export function probePanel(r: any, kinks: Record<string, Kink> = {}): void {
  const all = r.probes_all || [];
  const el = document.getElementById('traits')!;
  const sortSel = document.getElementById('traitsort') as HTMLSelectElement;
  const stepSel = document.getElementById('traitstep') as HTMLSelectElement;
  if (!all.length) { el.innerHTML = '<div class="${emptyCls()}">no probe rows yet: add <span class="mono">probes</span> to eval.evaluators in the spec</div>'; empty('probeheat', ''); stepSel.innerHTML = ''; return; }
  const steps = all.map((a: any) => a.step);
  if (traitView.step == null || !steps.includes(traitView.step) || traitView.followLatest) { traitView.step = steps[steps.length - 1]; traitView.followLatest = true; }
  if (stepSel.dataset.steps !== steps.join(',')) { // rebuild only when a step arrives, so an open list stays open
    stepSel.innerHTML = steps.map((s: number) => `<option value="${s}">${s}${s === steps[steps.length - 1] ? ' (latest)' : ''}</option>`).join('');
    stepSel.dataset.steps = steps.join(',');
  }
  stepSel.value = String(traitView.step);
  sortSel.value = traitView.sort;
  sortSel.onchange = () => { traitView.sort = sortSel.value; try { localStorage.setItem('thorp.traitsort', sortSel.value); } catch { /* blocked */ } probePanel(r, kinks); };
  stepSel.onchange = () => { traitView.step = +stepSel.value; traitView.followLatest = traitView.step === steps[steps.length - 1]; probePanel(r, kinks); };
  const p = all.find((a: any) => a.step === traitView.step).data;
  document.getElementById('probesh')!.firstChild!.textContent = `Traits at step ${traitView.step}: is there a direction? `;
  // the first step at which each trait was found, over every step on the ledger
  const first: Record<string, number> = {};
  for (const a of all) for (const [n, t] of Object.entries(a.data.traits as Record<string, any>)) if (t.status === 'found' && first[n] == null) first[n] = a.step;
  const best = (t: any) => (t.auc ? Math.max(...t.auc) : -1);
  const kinkAt = (L: number) => { const k = kinks['grad_norm/layer_' + L]; return k ? k : null; };
  const byName = (a: string, b: string) => (Number(a.includes('/')) - Number(b.includes('/'))) || a.localeCompare(b);
  const names = Object.keys(p.traits).sort((a, b) => {
    const A = p.traits[a], B = p.traits[b];
    if (traitView.sort === 'name') return byName(a, b);
    if (traitView.sort === 'auc') return best(B) - best(A) || byName(a, b);
    if (traitView.sort === 'first') return (first[a] ?? Infinity) - (first[b] ?? Infinity) || best(B) - best(A) || byName(a, b);
    return (A.best_layer ?? Infinity) - (B.best_layer ?? Infinity) || best(B) - best(A) || byName(a, b);
  });
  document.getElementById('traitnote')!.textContent = traitView.sort === 'layer' ? 'traits grouped by the layer where the held-out AUC peaks; the kink is that layer’s, from the Sieves tab' : traitView.sort === 'first' ? 'first step found is over every eval step on the ledger, not only the one shown' : '';
  el.innerHTML = names.map((n) => {
    const t = p.traits[n];
    // YES is split by the floors when they exist: emergent (beats the bag of tokens and the untrained
    // model) or in the tokens (a floor finds it too, so the model need not have built anything)
    const hasFloors = t.floor_bow !== undefined;
    const a = t.status === 'found' ? (hasFloors ? (t.emergent ? ['YES · emergent', 'yes'] : ['YES · in the tokens', 'na']) : ['YES', 'yes'])
      : t.status === 'not_found' ? ['NO', 'no'] : ['n/a', 'na'];
    const where = t.auc ? `layer ${t.best_layer}, AUC ${fmt(Math.max(...t.auc), 3)}` : t.reason;
    const k = t.auc ? kinkAt(t.best_layer) : null;
    const kink = k ? `<br>layer ${t.best_layer} kink @ ${k.step} (${k.kind}${k.tentative ? ', tentative' : ''})` : '';
    const firstLine = first[n] != null ? `<br>first found @ step ${first[n]}` : '';
    const floors = hasFloors ? `<br>floors: tokens ${fmt(t.floor_bow, 3)} · untrained ${fmt(t.floor_init, 3)}` : '';
    return `<div class="trait"><div class="n">${esc(n.replace('_', ' '))}</div><div class="a ${a[1]}">${a[0]}</div><div class="r">${esc(where)}${kink}${firstLine}${floors}<br>library ${t.n_train[0]}/${t.n_train[1]} · held out ${t.n_test[0]}/${t.n_test[1]}</div></div>`;
  }).join('');
  const tested = names.filter((n) => p.traits[n].auc);
  if (!tested.length) return empty('probeheat', 'no trait has two held-out books on each side');
  const L = p.traits[tested[0]].auc.length;
  const rows = tested.slice().reverse(); // heatmap rows read top-down in the strip's order
  plot('probeheat', [{ type: 'heatmap', x: [...Array(L).keys()].map((i) => { const k = kinkAt(i); return `layer ${i}` + (k ? `<br>kink ${k.step}` : ''); }), y: rows.map((n) => n.replace('_', ' ')), z: rows.map((n) => p.traits[n].auc),
    zmin: 0.5, zmax: 1, colorscale: 'Viridis', colorbar: { title: 'AUC', thickness: 10 }, hovertemplate: '%{y}<br>%{x}<br>held-out AUC %{z:.3f}<extra></extra>' }],
    layout({ margin: { l: 130, r: 10, t: 10, b: 48 }, yaxis: { type: 'category', categoryorder: 'array', categoryarray: rows.map((n) => n.replace('_', ' ')) } }));
}

export function runsTable(runs: any[], selected: string | null, goShip: (id: string) => void): void {
  const tb = document.querySelector('#runs tbody');
  if (!tb) return;  // the every-ship table lives on its own page now (the multi-page split)
  tb.innerHTML = runs.map((r) => `<tr data-run="${r.run_id}" class="${r.run_id === selected ? 'sel' : ''}">
    <td>${esc(r.ship || '')}</td><td>${esc(r.name || '')}</td><td class="mono">${r.run_id.slice(0, 12)}</td><td>${esc(r.preset || '')}</td><td>${r.seed ?? ''}</td>
    <td><span class="${pillCls((r.status || '').split(':')[0])}">${esc(r.status || '')}</span></td><td>${big(r.tokens_seen)}</td>
    <td>${fmt(r.wall_minutes, 1)}</td><td>${fmt(r.hole_bpb_mean, 4)}</td><td>${esc(r.started || '')}</td></tr>`).join('');
  tb.querySelectorAll('tr').forEach((tr) => { (tr as HTMLElement).onclick = () => goShip((tr as HTMLElement).dataset.run!); });
}

// the ship page's stage list: the stages its sailing read, in order (empty: one stage, reading)
export function drawStageList(st: any[] | null): void {
  const p = document.getElementById('stagepanel')!;
  p.hidden = !(st && st.length);
  if (!st || !st.length) return;
  document.querySelector('#stagetable tbody')!.innerHTML = st.map((s) => `<tr><td>${s.index + 1}</td><td><b>${esc(s.name)}</b></td>
    <td>${esc(String(s.recipe || '–').replace('lists/', '').replace('.csv', ''))}</td><td>${s.passes ?? '–'}</td><td>${s.first_step}–${s.last_step}</td><td>${big(s.tokens)}</td></tr>`).join('');
}
