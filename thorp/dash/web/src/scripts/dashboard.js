// The dashboard: tabs, the run picker, every panel, refreshed every 5 s from the JSON API in
// server.py. Shared pieces live in ../lib (formatters, charts, DataTable, the reader).
import { Plotly, tok, C, PALETTE, layout, cfg, empty, plot } from '../lib/charts.js';
import { fmt, big, fmtBytes, esc, get, log10, mean } from '../lib/format.js';
import { DataTable } from '../lib/datatable.js';
import { openBook, openEssay } from '../lib/reader.js';

// metric keys: `<prefix>/layer_3`, `<prefix>/layer_3/attn`, `<prefix>/tok`, `<prefix>/pos`
const groupOf = (k, prefix) => k.slice(prefix.length);
const groupOrder = g => g === 'tok' ? -2 : g === 'pos' ? -1 : +g.split('/')[0].split('_').pop();
const groupLabel = g => g.startsWith('layer_') ? 'layer ' + g.split('/')[0].split('_').pop() : g === 'tok' ? 'token emb' : g === 'pos' ? 'position emb' : g;
const topKeys = (m, prefix) => Object.keys(m).filter(k => k.startsWith(prefix) && !groupOf(k, prefix).includes('/')).sort((a, b) => groupOrder(groupOf(a, prefix)) - groupOrder(groupOf(b, prefix)));
const layerOnly = (m, prefix) => topKeys(m, prefix).filter(k => groupOf(k, prefix).startsWith('layer_'));

let selected = new URLSearchParams(location.search).get('run');

const TABS = ['sizes', 'rung', 'betting', 'books', 'languages', 'sieves', 'attention', 'traits-section', 'runs-section'];
let currentRung = null;
// a model page lives at its class name: #proxy, #speller, #stylist… (old #rung-1m links still open it)
const slugOf = r => r.name.toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-');
const rungFor = key => ladderData && ladderData.rungs.find(r => slugOf(r) === key || r.preset === key);
// Routes: #sizes, #betting… are the global tabs; a model page is #/models/<class>[/training|/scoring|/waypoints].
// Old model links (#proxy, #rung-1m) land on the new address.
const MTABS = ['overview', 'training', 'scoring', 'waypoints'];
let modelTab = 'overview';
function route(h) {
  if (h.startsWith('/models/')) { const [slug, mt] = h.slice(8).split('/'); return { tab: 'rung', rung: slug, mtab: MTABS.includes(mt) ? mt : 'overview' }; }
  if (h.startsWith('rung-')) return { tab: 'rung', rung: h.slice(5), mtab: 'overview' };
  if (TABS.includes(h) && h !== 'rung') return { tab: h };
  if (h && h !== 'rung' && !h.startsWith('/')) return { tab: 'rung', rung: h, mtab: 'overview' };
  return { tab: TABS[0] };
}
const modelHash = (r, mt = 'overview') => `/models/${slugOf(r)}${mt === 'overview' ? '' : '/' + mt}`;
function showTab(h, push = true) {
  const rt = route(h);
  let id = rt.tab, hash = h || TABS[0];
  if (id === 'rung') {
    const r = rungFor(rt.rung);
    if (ladderData && !r) { id = hash = TABS[0]; push = true; }  // not a model this ladder has
    else {
      currentRung = rt.rung; modelTab = rt.mtab;
      if (r) {
        hash = modelHash(r, modelTab); push = true;
        document.querySelectorAll('#modelnav a').forEach(a => { a.href = '#' + modelHash(r, a.dataset.mtab); });
      }
      if (ladderData) renderRung();
    }
  }
  document.body.classList.toggle('on-model', id === 'rung');
  document.querySelectorAll('.section').forEach(s => s.classList.toggle('active', s.id === id));
  document.querySelectorAll('#mainnav a').forEach(a => a.classList.toggle('active', a.dataset.tab === id));
  document.querySelectorAll('#rung .mtab').forEach(t => t.classList.toggle('active', t.dataset.mtab === modelTab));
  document.querySelectorAll('#modelnav a').forEach(a => a.classList.toggle('active', a.dataset.mtab === modelTab));
  if (push && location.hash !== '#' + hash) history.replaceState(null, '', location.pathname + location.search + '#' + hash);
  // charts drawn while hidden have no width; size the ones now showing
  document.querySelectorAll(`#${id} .chart`).forEach(el => { if (el.data && el.offsetParent) Plotly.Plots.resize(el); });
}
document.querySelectorAll('#mainnav a').forEach(a => a.onclick = e => { e.preventDefault(); showTab(a.dataset.tab); });
document.getElementById('home').onclick = e => { e.preventDefault(); showTab(TABS[0]); window.scrollTo(0, 0); };
window.addEventListener('hashchange', () => showTab(location.hash.slice(1), false));
showTab(location.hash.slice(1) || TABS[0], false);

function ema(xs, span) {
  const a = 2 / (span + 1); let m = null;
  return xs.map(x => (m = m == null ? x : a * x + (1 - a) * m));
}

// ---- the kink: a two-line fit to (step, log10 norm); the break is where the layer changes regime
function linfit(x, y) {
  const n = x.length; let sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (let i = 0; i < n; i++) { sx += x[i]; sy += y[i]; sxx += x[i] * x[i]; sxy += x[i] * y[i]; }
  const d = n * sxx - sx * sx;
  const b = d ? (n * sxy - sx * sy) / d : 0, a = (sy - b * sx) / n;
  let sse = 0; for (let i = 0; i < n; i++) { const r = y[i] - (a + b * x[i]); sse += r * r; }
  return { a, b, sse };
}
function kink(xs, ys) {
  const n = xs.length; if (n < 6) return null;
  const one = linfit(xs, ys); let best = null;
  for (let k = 3; k <= n - 3; k++) {
    const L = linfit(xs.slice(0, k), ys.slice(0, k)), R = linfit(xs.slice(k), ys.slice(k));
    const sse = L.sse + R.sse;
    if (!best || sse < best.sse) best = { k, sse, L, R };
  }
  const strength = one.sse > 0 ? 1 - best.sse / one.sse : 0;
  const before = best.L.b * 100, after = best.R.b * 100;
  // which way the push went at the break: by the signs of the two slopes
  const kind = Math.abs(after - before) < 0.02 ? 'bent'
    : before < 0 && after >= 0 ? 'turned up' : before > 0 && after <= 0 ? 'turned down'
    : before < 0 ? (after > before ? 'flattened' : 'steepened') : (after > before ? 'steepened' : 'eased');
  return { step: xs[best.k], before, after, kind, strength, tentative: n < 10 || strength < 0.25, L: best.L, R: best.R, k: best.k, xs };
}
// the fit starts where warmup ends (the learning-rate peak): the ramp before it is the schedule's
// shape, not the layer's, and a hump defeats a two-line fit
function warmEnd(m) { if (!m.lr) return 0; const [x, v] = m.lr; let b = 0; v.forEach((lr, i) => { if (lr > v[b]) b = i; }); return x[b]; }
function kinksOf(m, prefix) {
  const out = {}, from = warmEnd(m);
  for (const k of topKeys(m, prefix)) {
    const [x, v] = m[k];
    const pts = x.map((s, i) => [s, v[i]]).filter(p => p[1] > 0 && p[0] >= from);
    const kk = kink(pts.map(p => p[0]), pts.map(p => Math.log10(p[1])));
    if (kk) out[k] = kk;
  }
  return out;
}

function stat(k, v, s = '') { return `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`; }

function kinkSummary(m, kinks) {
  const prefix = 'grad_norm/';
  const keys = layerOnly(m, prefix);
  if (!keys.length) return ['no records yet', ''];
  const firm = keys.filter(k => kinks[k] && !kinks[k].tentative), tent = keys.filter(k => kinks[k] && kinks[k].tentative);
  if (!firm.length) return [tent.length ? `${tent.length} tentative, none firm` : 'none yet', `${keys.length} layers, ${m[keys[0]][0].length} records`];
  const say = k => `${groupLabel(groupOf(k, prefix)).replace('layer ', 'L')} ${kinks[k].kind} @ ${kinks[k].step}`;
  const earliest = firm.slice().sort((a, b) => kinks[a].step - kinks[b].step)[0];
  return [firm.map(say).join(' · '), `${firm.length} firm, ${tent.length} tentative; earliest ${say(earliest)}`];
}

function headline(r, m, kinks) {
  const run = r.run;
  const wall = run.wall_minutes != null ? fmt(run.wall_minutes, 1) + ' min' : '–';
  const [kinkLine, kinkNote] = kinkSummary(m, kinks);
  // the shelf this run was fed: books, tokens under its own tokeniser, and bytes (tokens × bytes a token)
  const rec = (r.recipe && r.recipe.data) || [];
  const shelf = { books: rec.length, tokens: rec.reduce((a, b) => a + (b.tokens || 0), 0), bytes: rec.reduce((a, b) => a + (b.tokens || 0) * (b.bytes_per_token || 0), 0) };
  document.getElementById('strip').innerHTML = [
    stat('ship', esc(run.ship || run.name || ''), `${esc(run.name || '')} · <span class="mono">${run.run_id.slice(0, 12)}</span> <span class="badge ${run.status.split(':')[0]}">${esc(run.status)}</span>`),
    stat('kinks', `<span style="font-size:15px">${esc(kinkLine)}</span>`, esc(kinkNote)),
    stat('weights', big(r.n_params_total), `${esc(r.spec.model.preset)} · ${big(r.n_params_non_embedding)} non-embedding + ${big(r.n_params_embedding)} embedding`),
    stat('shelf', `${shelf.books} books`, `${big(shelf.tokens)} tokens · ${fmtBytes(shelf.bytes)} · read ${r.spec.data.passes}×`),
    stat('tokens / s', big(r.tokens_per_s), 'mean of last 50 steps'),
    stat(run.status === 'running' ? 'eta' : 'wall time', run.status === 'running' && r.eta_minutes != null ? `${fmt(r.eta_minutes, 1)} min` : wall, run.status === 'running' ? `${big(r.tokens_seen)} of ${big(r.tokens_planned)} tokens` : (run.finished || '')),
  ].join('');
  const ch = r.chinchilla || {}, latest = r.hole_bpb_latest, prev = r.hole_bpb_previous;
  document.getElementById('numbers').innerHTML = [
    stat('preset', esc(r.spec.model.preset), `N = ${big(r.n_params_non_embedding)} non-embedding`),
    stat('tokens seen', big(r.tokens_seen), `of ${big(r.tokens_planned)} planned`),
    stat('hole-card bpb mean', latest ? fmt(latest.value) : '–', latest ? `step ${latest.step}` + (prev ? ` · prev ${fmt(prev.value)} @ ${prev.step}` : '') : ''),
    stat('Chinchilla L(N,D)', fmt(ch.L_planned), `nats/token, indicative · D=${big(ch.D_planned)}; unique: ${fmt(ch.L_unique)}`),
    stat('gap (en hole-card CE − L)', fmt(ch.gap_planned), `en CE ${fmt(r.hole_ce_mean_en)} nats`),
  ].join('');
  document.getElementById('title').textContent = `${run.ship ? run.ship + ' · ' : ''}${run.name} · ${run.run_id.slice(0, 12)} · ${run.hardware || ''}`;
}

// ---- the claim: the hypothesis in the order a sceptic wants it, and the ledger's reading of it
function claimPanel(cmp) {
  const shelves = {};
  for (const r of cmp) {
    if (!r.bpb.length) continue;
    (shelves[`${r.preset} · ${r.n_books ?? '?'} books`] ||= []).push(r);
  }
  const finals = Object.entries(shelves).map(([key, runs]) => {
    const done = runs.filter(r => r.status === 'finished');
    const vals = done.map(r => r.bpb[r.bpb.length - 1]);
    return { key, runs, seeds: new Set(done.map(r => r.seed)).size, best: vals.length ? Math.min(...vals) : null, spread: vals.length > 1 ? Math.max(...vals) - Math.min(...vals) : null };
  });
  const scored = finals.filter(f => f.best != null), seeded = finals.filter(f => f.spread != null);
  let verdict, cls = 'open';
  if (scored.length < 2) verdict = `Not testable yet: ${scored.length} finished shelf${scored.length === 1 ? '' : 'ves'} on the ledger. Two shelves at the same size and tokens are the first comparison; a second seed of one of them is the error bar.`;
  else {
    const sorted = scored.slice().sort((a, b) => a.best - b.best);
    const diff = sorted[sorted.length - 1].best - sorted[0].best;
    const spread = seeded.length ? Math.max(...seeded.map(f => f.spread)) : null;
    verdict = `Best shelf so far: ${sorted[0].key} at ${fmt(sorted[0].best, 4)} bpb; shelf-to-shelf difference ${fmt(diff, 4)}`;
    if (spread == null) verdict += '; no shelf has two finished seeds yet, so the difference has no error bar.';
    else { cls = diff > 2 * spread ? 'yes' : 'no'; verdict += `; seed-to-seed spread ${fmt(spread, 4)}.` + (cls === 'yes' ? ' The shelves differ by more than the seeds: the claim stands at this size.' : ' The seeds are as wide as the shelves: the difference is noise at this size.'); }
    verdict += ' Compared at each run’s final tokens; read the chart at matched tokens before quoting it.';
  }
  const rows = finals.map(f => `<tr><td>${esc(f.key)}</td><td>${f.runs.length}</td><td>${f.seeds}</td><td>${fmt(f.best, 4)}</td><td>${f.spread == null ? '–' : fmt(f.spread, 4)}</td></tr>`).join('');
  document.getElementById('claim').innerHTML = `
    <div><div class="k">Claim</div><div class="v">Some books make the guessing better, faster. Hold the model still, change the shelf, and the hole-card score falls faster per token on some shelves than on others. The kind of book that buys the most fall is the finding, and the next shelf is built from it.</div></div>
    <div><div class="k">Measure</div><div class="v">Guessing accuracy: bits per byte on the hole cards, books the model is never trained on. Learning speed: how far that number falls per million tokens seen. Neither is ever read from a book on the shelf.</div></div>
    <div><div class="k">Prediction</div><div class="v">At the same size and the same tokens, two shelves differ by more than two seeds of the same shelf do, and the order of shelves holds one size up. The per-book contribution (the heart of the dice, section 13) then names the books that carried it.</div></div>
    <div><div class="k">What would show it wrong</div><div class="v">A seed-to-seed spread as wide as the shelf-to-shelf difference; or an order of shelves at 9M that flips at 21M. Either is published as a finding, not buried.</div></div>
    <div class="reading"><div class="k">The ledger’s reading</div><div class="verdict ${cls}">${verdict}</div>
      <table class="mt"><thead><tr><th>shelf</th><th>runs</th><th>finished seeds</th><th>best final bpb</th><th>seed spread</th></tr></thead><tbody>${rows || '<tr><td colspan=5 class="empty">no scored run yet</td></tr>'}</tbody></table></div>`;
}

function comparePanel(cmp) {
  const data = [];
  cmp.forEach((r, i) => {
    if (!r.bpb.length) return;
    const col = PALETTE[i % PALETTE.length];
    const name = `${r.ship || r.name} · ${r.preset} · ${r.n_books ?? '?'} books · seed ${r.seed}`;
    data.push({ x: r.tokens, y: r.bpb, name, mode: 'lines+markers', line: { color: col, width: 2 }, marker: { size: 6 },
      hovertemplate: `${esc(name)}<br>%{x:,.0f} tokens<br>%{y:.4f} bpb<extra></extra>` });
    if (r.bpb_en.length) data.push({ x: r.tokens.slice(0, r.bpb_en.length), y: r.bpb_en, name: name + ' (en)', mode: 'lines', line: { color: col, width: 1, dash: 'dot' }, showlegend: false,
      hovertemplate: `${esc(name)} (en)<br>%{x:,.0f} tokens<br>%{y:.4f} bpb<extra></extra>` });
  });
  if (!data.length) return empty('compare', 'no scored run yet');
  plot('compare', data, layout({ xaxis: { title: 'tokens seen', gridcolor: C.line }, yaxis: { title: 'hole-card bits per byte', gridcolor: C.line } }));
}

function lossPanel(m, sets) {
  if (!m.loss) return empty('loss');
  const [s, v] = m.loss;
  const data = [
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

function holeMeta(r) {
  const meta = {};
  for (const sets of Object.values((r.eval_sets && r.eval_sets.data.sets) || {}))
    for (const b of sets) meta[b.book_id] = b;
  return meta;
}

function bpbPanel(evals, r) {
  if (!evals.length) return empty('bpb');
  const meta = holeMeta(r);
  const by = {};
  for (const e of evals) (by[e.book_id] ||= []).push(e);
  const data = Object.entries(by).map(([b, rows]) => { const t = meta[b] ? `${meta[b].title} (${meta[b].language})` : b; return {
    x: rows.map(r => r.step), y: rows.map(r => r.bpb), name: t, mode: 'lines+markers', marker: { size: 5 },
    hovertemplate: `${esc(t)}<br>step %{x}<br>%{y:.4f} bpb<extra></extra>` }; });
  plot('bpb', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'bits per byte', gridcolor: C.line },
    legend: { orientation: 'v', x: 1.02, y: 1, font: { size: 10 } }, margin: { l: 50, r: 10, t: 10, b: 36 } }));
}

function speedPanel(m) {
  if (!m.tokens_per_s) return empty('speed');
  const data = [{ x: m.tokens_per_s[0], y: ema(m.tokens_per_s[1], 20), name: 'tokens/s (EMA 20)', mode: 'lines', line: { color: C.good } }];
  if (m.mem_gb) data.push({ x: m.mem_gb[0], y: m.mem_gb[1], name: 'peak memory GB', yaxis: 'y2', mode: 'lines+markers', line: { color: C.accent }, marker: { size: 4 } });
  plot('speed', data, layout({ yaxis: { title: 'tokens / s', gridcolor: C.line }, yaxis2: { overlaying: 'y', side: 'right', title: 'GB', showgrid: false, rangemode: 'tozero' } }));
}

function heat(id, m, prefix, kinks, colorbar) {
  const keys = topKeys(m, prefix);
  if (!keys.length) return empty(id);
  const x = m[keys[0]][0];
  const data = [{ type: 'heatmap', x, y: keys.map(k => groupLabel(groupOf(k, prefix))), z: keys.map(k => m[k][1].map(log10)),
    colorscale: 'Viridis', colorbar: { title: colorbar, thickness: 10 }, hovertemplate: 'step %{x}<br>%{y}<br>log10 %{z:.2f}<extra></extra>' }];
  const kx = [], ky = [], kt = [];
  for (const k of keys) { const kk = kinks[k]; if (kk) { kx.push(kk.step); ky.push(groupLabel(groupOf(k, prefix))); kt.push(`kink at ${kk.step}${kk.tentative ? ' (tentative)' : ''}`); } }
  if (kx.length) data.push({ type: 'scatter', x: kx, y: ky, text: kt, mode: 'markers', marker: { symbol: 'diamond', size: 9, color: '#fff', line: { color: '#000', width: 1 } }, hovertemplate: '%{y}<br>%{text}<extra></extra>', showlegend: false });
  plot(id, data, layout({ margin: { l: 80, r: 10, t: 10, b: 36 }, xaxis: { title: 'step', gridcolor: C.line } }));
}

function kinkPanel(m, kinks) {
  const prefix = 'grad_norm/';
  const keys = layerOnly(m, prefix);
  if (!keys.length) { empty('kinks'); document.querySelector('#kinktable tbody').innerHTML = ''; return; }
  const data = [];
  keys.forEach((k, i) => {
    const g = groupOf(k, prefix), [x, v] = m[k], col = PALETTE[i % PALETTE.length];
    data.push({ x, y: v.map(log10), name: groupLabel(g), mode: 'lines', line: { color: col, width: 1.5 }, hovertemplate: `${groupLabel(g)}<br>step %{x}<br>log10 %{y:.2f}<extra></extra>` });
    const kk = kinks[k];
    if (kk) {
      const left = kk.xs.slice(0, kk.k), right = kk.xs.slice(kk.k);
      data.push({ x: left, y: left.map(s => kk.L.a + kk.L.b * s), mode: 'lines', line: { color: col, width: 1, dash: 'dot' }, showlegend: false, hoverinfo: 'skip' });
      data.push({ x: right, y: right.map(s => kk.R.a + kk.R.b * s), mode: 'lines', line: { color: col, width: 1, dash: 'dot' }, showlegend: false, hoverinfo: 'skip' });
      data.push({ x: [kk.step], y: [kk.L.a + kk.L.b * kk.step], mode: 'markers', marker: { symbol: 'diamond', size: 10, color: col, line: { color: '#fff', width: 1 } }, showlegend: false,
        hovertemplate: `${groupLabel(g)} kink at step ${kk.step}<br>before ${fmt(kk.before, 3)} / after ${fmt(kk.after, 3)} log10 per 100 steps<extra></extra>` });
    }
  });
  plot('kinks', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'log10 gradient norm', gridcolor: C.line }, legend: { orientation: 'h', y: -0.2, font: { size: 10 } } }));
  document.querySelector('#kinktable tbody').innerHTML = keys.map(k => {
    const kk = kinks[k], g = groupLabel(groupOf(k, prefix));
    if (!kk) return `<tr><td>${g}</td><td colspan=6 class="t">fewer than six records</td></tr>`;
    return `<tr><td>${g}</td><td>${kk.step}</td><td>${kk.kind}</td><td>${fmt(kk.before, 3)}</td><td>${fmt(kk.after, 3)}</td><td>${fmt(kk.strength, 2)}</td><td class="t">${kk.tentative ? 'tentative' : ''}</td></tr>`;
  }).join('');
  const firm = keys.map(k => kinks[k]).filter(kk => kk && !kk.tentative);
  document.getElementById('kinknote').textContent = 'Slopes are log10 of the norm per 100 steps. ' + (!firm.length
    ? 'The fit starts where warmup ends. A kink is tentative until ten records (500 steps) are in and the two-line fit removes at least a quarter of the one-line fit\'s residual. Turned up: the push bottomed and is rising again (the loss plateauing while the step stays large); turned down: it peaked; flattened or steepened: still falling, slower or faster; eased: still rising, slower.'
    : `${firm.length} of ${keys.length} layers have a firm kink; the earliest is at step ${Math.min(...firm.map(kk => kk.step))}, the latest at ${Math.max(...firm.map(kk => kk.step))}. A layer whose push flattens early has settled early; one that keeps falling is still being taught.`);
}

function attnPanels(m) {
  for (const [id, prefix, title] of [['attnpush', 'grad_norm/', 'log10 push ratio'], ['attnmove', 'update_ratio/', 'log10 move ratio']]) {
    const layers = layerOnly(m, prefix).map(k => groupOf(k, prefix));
    const rows = layers.filter(g => m[`${prefix}${g}/attn`] && m[`${prefix}${g}/mlp`]);
    if (!rows.length) { empty(id, 'no attn/mlp rows yet (written by runs started after 2026-11-06)'); continue; }
    const x = m[`${prefix}${rows[0]}/attn`][0];
    const z = rows.map(g => { const a = m[`${prefix}${g}/attn`][1], b = m[`${prefix}${g}/mlp`][1]; return a.map((v, i) => v > 0 && b[i] > 0 ? Math.log10(v / b[i]) : null); });
    plot(id, [{ type: 'heatmap', x, y: rows.map(groupLabel), z, colorscale: 'RdBu', zmid: 0, colorbar: { title, thickness: 10 }, hovertemplate: 'step %{x}<br>%{y}<br>%{z:.2f}<extra></extra>' }],
      layout({ margin: { l: 80, r: 10, t: 10, b: 36 }, xaxis: { title: 'step', gridcolor: C.line } }));
  }
}

function bookSeries(m, r) {
  const rec = (r.recipe && r.recipe.data) || [];
  const meta = {}; for (const b of rec) meta[b.book_id] = b;
  return Object.keys(m).filter(k => k.startsWith('loss/book/')).map(k => {
    const id = k.slice('loss/book/'.length), b = meta[id] || { title: id, family: '' };
    return { id, title: b.title, family: b.family, x: m[k][0], y: m[k][1] };
  });
}
const meanCurve = (books, steps) => steps.map(st => mean(books.map(b => { const j = b.x.indexOf(st); return j < 0 ? null : b.y[j]; }).filter(v => v != null)));

function bookPanels(m, r, series, fams, famColour) {
  const traits = r.traits || {};
  if (!series.length) { empty('bookloss'); empty('kindloss'); empty('halflife'); return; }
  const seen = new Set();
  plot('bookloss', series.map(s => ({ x: s.x, y: s.y, name: s.family, legendgroup: s.family, showlegend: !seen.has(s.family) && !!seen.add(s.family), mode: 'lines', line: { color: famColour(s.family), width: 1 }, opacity: 0.8,
    hovertemplate: `${esc(s.title)} (${esc(s.family)})<br>step %{x}<br>%{y:.3f} nats<extra></extra>` })),
    layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token', gridcolor: C.line } }));

  const steps = [...new Set(series.flatMap(s => s.x))].sort((a, b) => a - b);
  const kdata = [];
  ['fiction', 'verse', 'first_person'].forEach((t, i) => {
    for (const val of [1, 0]) {
      const books = series.filter(s => traits[s.id] && traits[s.id][t] === val);
      if (!books.length) continue;
      kdata.push({ x: steps, y: meanCurve(books, steps), name: `${t.replace('_', ' ')}${val ? '' : ': not'} (${books.length})`, mode: 'lines', line: { color: PALETTE[i], width: val ? 2.5 : 1.5, dash: val ? 'solid' : 'dot' } });
    }
  });
  if (!kdata.length) empty('kindloss', 'no traits for these books (lists/traits.csv)');
  else plot('kindloss', kdata, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token, mean over books', gridcolor: C.line } }));

  const hl = series.map(s => {
    const y0 = s.y[0], ymin = Math.min(...s.y), target = y0 - (y0 - ymin) / 2;
    const j = s.y.findIndex(v => v <= target), n = s.y.length;
    const last = s.y[n - 1], prev = s.y[Math.max(0, n - 3)], dstep = s.x[n - 1] - s.x[Math.max(0, n - 3)];
    return { ...s, half: j < 0 ? null : s.x[j], drop: y0 - ymin, last, slope: dstep ? (last - prev) / dstep * 100 : 0 };
  }).filter(h => h.half != null && h.drop > 0).sort((a, b) => a.half - b.half || b.drop - a.drop);
  if (!hl.length) return empty('halflife');
  const kind = h => { const t = traits[h.id]; return t ? [t.fiction ? 'fiction' : 'non-fiction', t.verse ? 'verse' : null, t.first_person ? 'first person' : null].filter(Boolean).join(', ') : ''; };
  // labels must be unique: Plotly puts bars with the same category in one slot, and two volumes of
  // one book cut to 40 characters collide (The Gaming Table vols 1 and 2, Edith Wharton parts 1 and 2)
  const short = hl.map(h => h.title.slice(0, 40)), count = {};
  short.forEach(t => count[t] = (count[t] || 0) + 1);
  const labels = hl.map((h, i) => count[short[i]] > 1 ? `${short[i].slice(0, 32)}… (${h.id})` : short[i]);
  plot('halflife', [{ type: 'bar', x: labels, y: hl.map(h => h.half), marker: { color: hl.map(h => famColour(h.family)) },
    text: hl.map(h => `${h.family}${kind(h) ? ' · ' + kind(h) : ''}<br>half-life step ${h.half} · drop so far ${fmt(h.drop, 2)} nats<br>latest ${fmt(h.last, 3)} · slope ${fmt(h.slope, 3)} per 100 steps`), hovertemplate: '%{x}<br>%{text}<extra></extra>' }],
    layout({ margin: { l: 50, r: 10, t: 10, b: 140 }, xaxis: { tickangle: -60, tickfont: { size: 9 }, gridcolor: C.line }, yaxis: { title: 'half-life (step)', gridcolor: C.line } }));
}

function languagePanels(r, evals, series, fams, famColour) {
  const rec = r.recipe && r.recipe.data;
  if (!rec) { empty('families'); empty('familyloss'); empty('familybpb'); return; }
  const fam = {};
  for (const b of rec) fam[b.family] = (fam[b.family] || 0) + b.tokens;
  const fk = Object.keys(fam).sort((a, b) => fam[b] - fam[a]);
  plot('families', [{ type: 'bar', x: fk, y: fk.map(k => fam[k]), marker: { color: fk.map(famColour) }, hovertemplate: '%{x}<br>%{y:,} tokens<extra></extra>' }],
    layout({ yaxis: { title: 'tokens per pass', gridcolor: C.line } }));
  if (!series.length) empty('familyloss');
  else {
    const steps = [...new Set(series.flatMap(s => s.x))].sort((a, b) => a - b);
    plot('familyloss', fams.map(f => { const books = series.filter(s => s.family === f); return { x: steps, y: meanCurve(books, steps), name: `${f} (${books.length})`, mode: 'lines', line: { color: famColour(f), width: 2 } }; }).filter(t => t.y.some(v => v != null)),
      layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'nats / token, mean over books', gridcolor: C.line } }));
  }
  if (!evals.length) return empty('familybpb');
  const meta = holeMeta(r), last = Math.max(...evals.map(e => e.step));
  const byFam = {};
  for (const e of evals.filter(e => e.step === last)) { const f = (meta[e.book_id] || {}).family || '?'; (byFam[f] ||= []).push(e.bpb); }
  const ff = Object.keys(byFam).sort((a, b) => mean(byFam[a]) - mean(byFam[b]));
  plot('familybpb', [{ type: 'bar', x: ff, y: ff.map(f => mean(byFam[f])), marker: { color: ff.map(famColour) }, text: ff.map(f => `${byFam[f].length} book${byFam[f].length > 1 ? 's' : ''}`), hovertemplate: '%{x}<br>%{y:.4f} bpb · %{text}<extra></extra>' }],
    layout({ yaxis: { title: `bits per byte at step ${last}`, gridcolor: C.line } }));
}

function fallbackPanel(r) {
  const rec = r.recipe && r.recipe.data;
  if (!rec) return empty('fallback');
  const stats = (r.tokeniser && r.tokeniser.stats) || {};
  const rows = rec.map(b => ({ ...b, rate: (stats[b.book_id] || {}).byte_fallback_rate ?? b.byte_fallback_rate ?? 0 }))
    .sort((a, b) => b.rate - a.rate).slice(0, 25);
  plot('fallback', [{ type: 'bar', orientation: 'h', y: rows.map(b => `${b.title.slice(0, 34)} (${b.language})`).reverse(),
    x: rows.map(b => b.rate * 100).reverse(), marker: { color: C.accent }, hovertemplate: '%{y}<br>%{x:.3f}% byte tokens<extra></extra>' }],
    layout({ margin: { l: 230, r: 10, t: 10, b: 36 }, xaxis: { title: '% of tokens that are byte pieces (top 25)', gridcolor: C.line }, yaxis: { tickfont: { size: 10 } } }));
}

// the Traits tab reads any eval step's probes and sorts the traits by the layer they live in (with
// that layer's kink beside it), by the step they first reached YES, by AUC, or by name
const traitView = { sort: 'layer', step: null };
try { traitView.sort = localStorage.getItem('thorp.traitsort') || 'layer'; } catch (e) {}
function probePanel(r, kinks = {}) {
  const all = r.probes_all || [];
  const el = document.getElementById('traits');
  const sortSel = document.getElementById('traitsort'), stepSel = document.getElementById('traitstep');
  if (!all.length) { el.innerHTML = '<div class="empty">no probe rows yet: add <span class="mono">probes</span> to eval.evaluators in the spec</div>'; empty('probeheat', ''); stepSel.innerHTML = ''; return; }
  const steps = all.map(a => a.step);
  if (traitView.step == null || !steps.includes(traitView.step) || traitView.followLatest) { traitView.step = steps[steps.length - 1]; traitView.followLatest = true; }
  if (stepSel.dataset.steps !== steps.join(',')) { // rebuild only when a step arrives, so an open list stays open
    stepSel.innerHTML = steps.map(s => `<option value="${s}">${s}${s === steps[steps.length - 1] ? ' (latest)' : ''}</option>`).join('');
    stepSel.dataset.steps = steps.join(',');
  }
  stepSel.value = String(traitView.step);
  sortSel.value = traitView.sort;
  sortSel.onchange = () => { traitView.sort = sortSel.value; try { localStorage.setItem('thorp.traitsort', sortSel.value); } catch (e) {} probePanel(r, kinks); };
  stepSel.onchange = () => { traitView.step = +stepSel.value; traitView.followLatest = traitView.step === steps[steps.length - 1]; probePanel(r, kinks); };
  const p = all.find(a => a.step === traitView.step).data;
  document.getElementById('probesh').firstChild.textContent = `Traits at step ${traitView.step}: is there a direction? `;
  // the first step at which each trait was found, over every step on the ledger
  const first = {};
  for (const a of all) for (const [n, t] of Object.entries(a.data.traits)) if (t.status === 'found' && first[n] == null) first[n] = a.step;
  const best = t => t.auc ? Math.max(...t.auc) : -1;
  const kinkAt = L => { const k = kinks['grad_norm/layer_' + L]; return k ? k : null; };
  const byName = (a, b) => (a.includes('/') - b.includes('/')) || a.localeCompare(b);
  const names = Object.keys(p.traits).sort((a, b) => {
    const A = p.traits[a], B = p.traits[b];
    if (traitView.sort === 'name') return byName(a, b);
    if (traitView.sort === 'auc') return best(B) - best(A) || byName(a, b);
    if (traitView.sort === 'first') return (first[a] ?? Infinity) - (first[b] ?? Infinity) || best(B) - best(A) || byName(a, b);
    return (A.best_layer ?? Infinity) - (B.best_layer ?? Infinity) || best(B) - best(A) || byName(a, b);
  });
  document.getElementById('traitnote').textContent = traitView.sort === 'layer' ? 'traits grouped by the layer where the held-out AUC peaks; the kink is that layer’s, from the Sieves tab' : traitView.sort === 'first' ? 'first step found is over every eval step on the ledger, not only the one shown' : '';
  el.innerHTML = names.map(n => {
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
    return `<div class="trait"><div class="n">${esc(n.replace('_', ' '))}</div><div class="a ${a[1]}">${a[0]}</div><div class="r">${esc(where)}${kink}${firstLine}${floors}<br>shelf ${t.n_train[0]}/${t.n_train[1]} · held out ${t.n_test[0]}/${t.n_test[1]}</div></div>`;
  }).join('');
  const tested = names.filter(n => p.traits[n].auc);
  if (!tested.length) return empty('probeheat', 'no trait has two held-out books on each side');
  const L = p.traits[tested[0]].auc.length;
  const rows = tested.slice().reverse(); // heatmap rows read top-down in the strip's order
  plot('probeheat', [{ type: 'heatmap', x: [...Array(L).keys()].map(i => { const k = kinkAt(i); return `layer ${i}` + (k ? `<br>kink ${k.step}` : ''); }), y: rows.map(n => n.replace('_', ' ')), z: rows.map(n => p.traits[n].auc),
    zmin: 0.5, zmax: 1, colorscale: 'Viridis', colorbar: { title: 'AUC', thickness: 10 }, hovertemplate: '%{y}<br>%{x}<br>held-out AUC %{z:.3f}<extra></extra>' }],
    layout({ margin: { l: 130, r: 10, t: 10, b: 48 }, yaxis: { type: 'category', categoryorder: 'array', categoryarray: rows.map(n => n.replace('_', ' ')) } }));
}

const LADDER = [
  [1, "knowing what it doesn't know", 'r1_calibration', 'correlation of its uncertainty with its loss'],
  [2, 'noticing the strange', 'r2_novelty_auc', 'AUC, unseen books against shelf books'],
  [3, 'learning from the page', 'r3_copy_gain', 'nats saved on a repeated span (and late minus early loss)'],
  [4, 'knowing a question', 'r4_question_auc', 'AUC, questions against statements, punctuation removed'],
  [5, 'expecting an answer', 'r5_expectancy', 'nats more uncertain after "?" than after "."'],
  [6, 'asking', 'r6_asking', 'log ratio of "?" where unsure, beyond the text'],
];
function ladderPanel(r, m) {
  const c = r.curiosity && r.curiosity.data, el = document.getElementById('ladder'), vd = document.getElementById('ladderverdict');
  if (!c) { el.innerHTML = '<div class="empty">no ladder rows yet: add <span class="mono">curiosity</span> to eval.evaluators, or re-score with <span class="mono">thorp eval RUN --evaluators curiosity</span></div>'; vd.innerHTML = ''; empty('laddertime', ''); return; }
  document.getElementById('ladderh').firstChild.textContent = `The curiosity ladder at step ${r.curiosity.step} `;
  const order = c.highest === 0 ? 'No rung is present yet.' : c.in_order ? `In order: every rung up to ${c.highest} that could be tested is present, none above an absent one.` : `Out of order: rung ${c.highest} is present above an absent rung. That is a finding against the ladder at this size.`;
  vd.innerHTML = `<div class="reading"><div class="k">The ledger’s reading</div><div class="verdict ${c.highest === 0 ? 'open' : c.in_order ? 'yes' : 'no'}">${order}</div></div>`;
  const floorOf = k => k === 2 ? c.floor_bow.r2 : k === 4 ? c.floor_bow.r4 : null;
  el.innerHTML = `<table><thead><tr><th>rung</th><th>measure</th><th>trained</th><th>untrained</th><th>token floor</th><th>status</th><th>reading</th></tr></thead><tbody>${
    LADDER.slice().reverse().map(([k, name, key, what]) => {
      const s = c.rungs[k] || { status: 'untestable', reason: '' };
      const cls = s.status === 'present' ? 'finished' : s.status === 'absent' ? 'failed' : 'running';
      return `<tr><td><b>${k}</b> ${esc(name)}</td><td class="note">${esc(what)}</td><td>${fmt(c.values[key], 3)}</td><td>${fmt(c.untrained[key], 3)}</td><td>${fmt(floorOf(k), 3)}</td>
        <td><span class="badge ${cls}">${s.status}</span></td><td class="note">${esc(s.reason)}</td></tr>`;
    }).join('')}</tbody></table>`;
  // when each rung appears: one row per rung, a mark at every eval step, filled where present
  const data = [];
  for (const [k, name] of LADDER) {
    const s = m[`curiosity/rung_${k}`];
    if (!s) continue;
    data.push({ x: s[0], y: s[0].map(() => k), mode: 'markers', name: `${k} ${name}`, showlegend: false,
      marker: { size: 10, symbol: 'square', color: s[1].map(v => v ? C.good : C.muted + '59') },
      hovertemplate: `${esc(name)}<br>step %{x}<extra></extra>` });
  }
  if (!data.length) return empty('laddertime', '');
  plot('laddertime', data, layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'rung', dtick: 1, range: [0.5, 6.5], gridcolor: C.line } }));
}

function samplesPanel(r) {
  const el = document.getElementById('samples');
  if (!r.samples) { el.innerHTML = '<div class="empty">no samples yet</div>'; empty('top10'); return; }
  document.getElementById('samplesh').textContent = `Samples at step ${r.samples.step}`;
  el.innerHTML = r.samples.data.map(s => `<div><span class="p">${esc(s.prompt)}</span> <span class="t">${s.temperature ? 'T=' + s.temperature : 'greedy'}</span><pre>${esc(s.prompt)}${esc(s.text)}</pre></div>`).join('');
  if (r.top10) {
    document.getElementById('top10h').textContent = `Next token after “${r.top10.data.prompt}”`;
    const t = r.top10.data.top.slice().reverse();
    plot('top10', [{ type: 'bar', orientation: 'h', y: t.map(x => JSON.stringify(x.token.replace(/▁/g, ' '))), x: t.map(x => x.p), marker: { color: C.good },
      hovertemplate: '%{y}<br>p = %{x:.4f}<extra></extra>' }], layout({ margin: { l: 110, r: 10, t: 10, b: 36 }, xaxis: { title: 'probability', gridcolor: C.line } }));
  }
}

// ---- matched tokens: a run's score where its curve crosses a token count, by linear interpolation
const MATCH_AT = [16e6, 32e6, 64e6];
function interp(xs, ys, x) {
  if (!xs.length || x < xs[0] || x > xs[xs.length - 1]) return null;
  for (let i = 1; i < xs.length; i++) if (xs[i] >= x) { const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1] || 1); return ys[i - 1] + t * (ys[i] - ys[i - 1]); }
  return ys[ys.length - 1];
}
function earliestKink(r) {
  const ks = kinksOf(r.push || {}, 'grad_norm/');
  const firm = Object.entries(ks).filter(([k, v]) => k.split('/')[1].startsWith('layer_') && !v.tentative).sort((a, b) => a[1].step - b[1].step);
  return firm.length ? `L${firm[0][0].split('_').pop()} ${firm[0][1].kind} @ ${firm[0][1].step}` : '–';
}
function matchedPanel(cmp) {
  const runs = cmp.filter(r => r.bpb.length);
  if (!runs.length) { document.getElementById('matched').innerHTML = '<div class="empty">no scored run yet</div>'; return; }
  const rows = runs.map(r => {
    const last = r.bpb.length - 1;
    return `<tr><td>${esc(r.ship || r.name)}</td><td>${r.seed ?? ''}</td><td class="mono">${esc(r.set)}</td><td>${r.n_books ?? '?'}</td><td>${big(r.tokens[last])}</td>
      ${MATCH_AT.map(x => `<td>${fmt(interp(r.tokens, r.bpb, x), 4)}</td>`).join('')}
      <td><b>${fmt(r.bpb[last], 4)}</b></td><td>${fmt(r.bpb_en[r.bpb_en.length - 1], 4)}</td><td>${esc(earliestKink(r))}</td>
      <td><span class="badge ${(r.status || '').split(':')[0]}">${esc((r.status || '').split(':')[0])}</span></td></tr>`;
  }).join('');
  document.getElementById('matched').innerHTML = `<table><thead><tr><th>ship</th><th>seed</th><th>set</th><th>books</th><th>tokens seen</th>
    ${MATCH_AT.map(x => `<th>bpb @ ${big(x)}</th>`).join('')}<th>final bpb</th><th>final en</th><th>earliest firm kink</th><th>status</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="note" style="margin-top:6px">Compare only rows on the same set: hole-cards (13 books) and hole-cards-v2 (20 books, without Darwin and Einstein) are different decks.</div>`;
}
function truthGapPanel(cmp) {
  const lit = r => r.by_set['hole-cards-v2'] ? 'hole-cards-v2' : 'hole-cards';
  const runs = cmp.filter(r => r.by_set && r.by_set.truths && r.by_set[lit(r)]);
  const el = document.getElementById('truthgap');
  if (!runs.length) { el.innerHTML = '<div class="empty">no run has been scored on the truths deck yet (lists/truths.csv): re-score a finished run with <span class="mono">thorp eval RUN --sets lists/hole-cards-v2.csv lists/truths.csv</span></div>'; return; }
  const rows = runs.map(r => {
    const T = r.by_set.truths, L = r.by_set[lit(r)];
    const pts = T.steps.map((s, i) => [s, T.tokens[i], T.bpb[i], L.bpb[L.steps.indexOf(s)]]).filter(p => p[3] != null);
    const first = pts[0], last = pts[pts.length - 1];
    if (!last) return '';
    const trend = pts.length > 1 ? fmt((last[2] - last[3]) - (first[2] - first[3]), 4) : '– (one step)';
    return `<tr><td>${esc(r.ship || r.name)}</td><td>${r.seed ?? ''}</td><td class="mono">${lit(r)}</td><td>${big(last[1])}</td><td>${fmt(last[2], 4)}</td><td>${fmt(last[3], 4)}</td><td><b>${fmt(last[2] - last[3], 4)}</b></td><td>${trend}</td></tr>`;
  }).join('');
  el.innerHTML = `<table><thead><tr><th>ship</th><th>seed</th><th>against</th><th>at tokens</th><th>truths bpb</th><th>literature bpb</th><th>truth gap</th><th>change since first scored</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ---- the content experiment: the pre-registered rule applied to every outcome, from the rows
const SHELF_OF = n => (n.match(/^content-([a-z]+)-v1/) || [])[1];
const SHELF_LABEL = { random: 'Flotsam · random (the null)', greek: 'Paralus · Greek polis', islamic: 'Dhow · Islamic golden age', renaissance: 'Santa Maria · Renaissance', about: 'Cutty Sark · about the ages' };
const CURATED = ['greek', 'islamic', 'renaissance', 'about'];
const meanOf = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
const rangeOf = a => a.length > 1 ? Math.max(...a) - Math.min(...a) : null;
function ruleVerdict(groups, unit, digits) {
  // groups: {shelf: [values]}; the null is Flotsam's spread (S = its range); a shelf clears it when
  // its mean lies more than 2S from Flotsam's centre
  const F = (groups.random || []).filter(v => v != null);
  if (F.length < 2) return { line: `waiting for the random shelves (${F.length} of 3 finished)`, cls: 'open', rows: [] };
  const c = meanOf(F), S = rangeOf(F);
  const rows = CURATED.map(k => {
    const v = (groups[k] || []).filter(x => x != null);
    if (!v.length) return { k, text: 'not yet', cls: 'open' };
    const m = meanOf(v), d = m - c, out = Math.abs(d) > 2 * S;
    return { k, m, d, n: v.length, spread: rangeOf(v), out, text: `${fmt(m, digits)} (${v.length} ship${v.length > 1 ? 's' : ''}), ${d >= 0 ? '+' : ''}${fmt(d, digits)} from random`, cls: out ? 'yes' : 'no' };
  });
  const moved = rows.filter(r => r.out);
  const line = moved.length ? `Content has a detectable bearing: ${moved.map(r => SHELF_LABEL[r.k].split(' · ')[0]).join(', ')} ${moved.length > 1 ? 'lie' : 'lies'} more than 2S from the random shelves (centre ${fmt(c, digits)}, S ${fmt(S, digits)}${unit}).`
    : `No detectable bearing so far: every curated shelf lies within 2S of the random shelves (centre ${fmt(c, digits)}, S ${fmt(S, digits)}${unit}).`;
  return { line, cls: moved.length ? 'yes' : 'no', rows, c, S };
}
function pairVerdict(groups, a, b, digits) {
  const A = (groups[a] || []).filter(v => v != null), B = (groups[b] || []).filter(v => v != null);
  if (A.length < 2 || B.length < 2) return null;
  const d = meanOf(A) - meanOf(B), bar = 2 * Math.max(rangeOf(A), rangeOf(B));
  return { d, bar, out: Math.abs(d) > bar };
}
function contentPanel(ships) {
  const el = document.getElementById('contentverdict'), tb = document.getElementById('contentships');
  if (!ships.length) { el.innerHTML = '<div class="empty">no content ship on the ledger yet: they run after the night queue and the re-score (scripts/queue_content.sh)</div>'; tb.innerHTML = ''; empty('contentchart', ''); return; }
  // matched tokens: the smallest final tokens-seen among the ships that have finished
  const score = r => r.by_set && r.by_set.neutral;
  const done = ships.filter(r => r.status === 'finished' && score(r));
  const T = done.length ? Math.min(...done.map(r => score(r).tokens[score(r).tokens.length - 1])) : null;
  const at = r => T == null || !score(r) ? null : interp(score(r).tokens, score(r).bpb, T);
  const shelfOf = r => SHELF_OF(r.name);
  const group = f => { const g = {}; for (const r of done) (g[shelfOf(r)] ||= []).push(f(r)); return g; };
  const primary = ruleVerdict(group(at), ' bpb', 4);
  // secondary outcomes, each by the same rule
  const lastTraits = r => (r.traits.length ? r.traits[r.traits.length - 1].traits : {});
  const traitNames = [...new Set(done.flatMap(r => Object.keys(lastTraits(r))))].filter(n => !n.startsWith('family/')).sort();
  const kinkOf = r => { const ks = kinksOf(r.push || {}, 'grad_norm/'); const f = Object.entries(ks).filter(([k, v]) => k.split('/')[1].startsWith('layer_') && !v.tentative).map(([, v]) => v.step); return f.length ? Math.min(...f) : null; };
  const lastQuarter = (series, steps) => { if (!series) return null; const [x, v] = series; const cut = Math.max(...x) * 0.75; const vals = v.filter((_, i) => x[i] >= cut && v[i] > 0).map(Math.log10); return meanOf(vals); };
  const sieveOf = (r, key, src) => { const ks = Object.keys(src || {}).filter(k => k.startsWith(key)); return meanOf(ks.map(k => lastQuarter(src[k])).filter(v => v != null)); };
  const secondary = [
    ...traitNames.map(t => [`trait: ${t.replace('_', ' ')} (best held-out AUC)`, ruleVerdict(group(r => (lastTraits(r)[t] || {}).best ?? null), '', 3)]),
    ['kinks: earliest firm kink (step)', ruleVerdict(group(kinkOf), ' steps', 0)],
    ['sieves: push, last quarter (mean log10 over layers)', ruleVerdict(group(r => sieveOf(r, 'grad_norm/layer_', r.push)), '', 3)],
    ['sieves: move, last quarter (mean log10 update ratio)', ruleVerdict(group(r => sieveOf(r, 'update_ratio/layer_', r.move)), '', 3)],
    ['curiosity ladder: highest rung present', ruleVerdict(group(r => r.ladder.length ? r.ladder[r.ladder.length - 1][1] : null), '', 1)],
  ];
  const g = group(at);
  const pairs = [['quality: Greek against Cutty Sark', 'greek', 'about'], ['quality: Islamic against Cutty Sark', 'islamic', 'about'], ['quality: Renaissance against Cutty Sark', 'renaissance', 'about'],
    ['type: Greek against Islamic', 'greek', 'islamic'], ['type: Greek against Renaissance', 'greek', 'renaissance'], ['type: Islamic against Renaissance', 'islamic', 'renaissance']]
    .map(([label, a, b]) => { const p = pairVerdict(g, a, b, 4); return `<tr><td>${label}</td><td>${p ? `${p.d >= 0 ? '+' : ''}${fmt(p.d, 4)} bpb` : '–'}</td><td>${p ? fmt(p.bar, 4) : '–'}</td><td>${p ? `<span class="badge ${p.out ? 'finished' : 'failed'}">${p.out ? 'differ' : 'within noise'}</span>` : 'needs two ships a side'}</td></tr>`; }).join('');
  el.innerHTML = `<div class="reading"><div class="k">The ledger’s reading: guessing (neutral deck, English bits per byte at ${T ? big(T) : '–'} tokens, ${done.length} of ${ships.length} ships finished)</div><div class="verdict ${primary.cls}">${primary.line}</div>
    <table class="mt"><thead><tr><th>shelf</th><th>against the random shelves</th></tr></thead><tbody>${primary.rows.map(r => `<tr><td>${SHELF_LABEL[r.k]}</td><td><span class="verdict ${r.cls}" style="display:inline">${esc(r.text)}</span></td></tr>`).join('')}</tbody></table>
    <table class="mt"><thead><tr><th>quality and type</th><th>difference</th><th>twice the larger spread</th><th>reading</th></tr></thead><tbody>${pairs}</tbody></table>
    <table class="mt"><thead><tr><th>secondary outcome</th><th>reading (same rule: more than 2S from the random shelves)</th></tr></thead><tbody>${secondary.map(([label, v]) => `<tr><td>${esc(label)}</td><td><span class="verdict ${v.cls}" style="display:inline">${esc(v.line)}</span></td></tr>`).join('')}</tbody></table></div>`;
  tb.innerHTML = `<table style="margin-top:12px"><thead><tr><th>ship</th><th>shelf</th><th>its question</th><th>status</th><th>tokens</th><th>neutral bpb at T</th><th>earliest firm kink</th><th>highest rung</th></tr></thead><tbody>${
    ships.map(r => `<tr><td><b>${esc(r.ship || r.name)}</b></td><td>${esc(SHELF_LABEL[shelfOf(r)] || '')}</td><td class="note">${esc(r.question || '')}</td><td><span class="badge ${(r.status || '').split(':')[0]}">${esc((r.status || '').split(':')[0])}</span></td>
      <td>${score(r) ? big(score(r).tokens[score(r).tokens.length - 1]) : '–'}</td><td>${fmt(at(r), 4)}</td><td>${kinkOf(r) ?? '–'}</td><td>${r.ladder.length ? r.ladder[r.ladder.length - 1][1] : '–'}</td></tr>`).join('')}</tbody></table>`;
  const col = { random: C.muted, greek: C.blue, islamic: C.good, renaissance: C.accent, about: C.c5 };
  const data = ships.filter(score).map(r => ({ x: score(r).tokens, y: score(r).bpb, name: r.ship, mode: 'lines+markers', line: { color: col[shelfOf(r)], width: 2 }, marker: { size: 5 },
    hovertemplate: `${esc(r.ship)}<br>%{x:,.0f} tokens<br>%{y:.4f} neutral bpb<extra></extra>` }));
  if (!data.length) return empty('contentchart', '');
  plot('contentchart', data, layout({ xaxis: { title: 'tokens seen', gridcolor: C.line }, yaxis: { title: 'neutral-deck bits per byte', gridcolor: C.line } }));
}

// the header's run picker: every per-run panel follows it; panels marked ALL RUNS do not
function runPicker(runs) {
  const sel = document.getElementById('runpick');
  const key = runs.map(r => r.run_id + r.status).join(',');
  if (sel.dataset.key !== key) { // rebuild only when the run list changes, so an open list stays open
    sel.innerHTML = runs.map(r => `<option value="${r.run_id}">${esc(r.ship || r.name || r.run_id.slice(0, 12))} · ${esc(r.name || '')} · ${esc((r.status || '').split(':')[0])}</option>`).join('');
    sel.dataset.key = key;
  }
  sel.value = selected;
  sel.onchange = () => { selected = sel.value; history.replaceState(null, '', '?run=' + selected + location.hash); refresh(); };
}

function runsTable(runs) {
  const tb = document.querySelector('#runs tbody');
  tb.innerHTML = runs.map(r => `<tr data-run="${r.run_id}" class="${r.run_id === selected ? 'sel' : ''}">
    <td>${esc(r.ship || '')}</td><td>${esc(r.name || '')}</td><td class="mono">${r.run_id.slice(0, 12)}</td><td>${esc(r.preset || '')}</td><td>${r.seed ?? ''}</td>
    <td><span class="badge ${(r.status || '').split(':')[0]}">${esc(r.status || '')}</span></td><td>${big(r.tokens_seen)}</td>
    <td>${fmt(r.wall_minutes, 1)}</td><td>${fmt(r.hole_bpb_mean, 4)}</td><td>${esc(r.started || '')}</td></tr>`).join('');
  tb.querySelectorAll('tr').forEach(tr => tr.onclick = () => {
    selected = tr.dataset.run; history.replaceState(null, '', '?run=' + selected + location.hash); refresh();
  });
}


// what each speller metric means, which way is better, and why (popovers on the 9m page)
const HELP = {
  nevermore: ['Nevermore score', 'Higher (0.3 or more is a Nevermore)', "The strongest head's attention from a repeated word to the word that followed it last time; measured on random pieces repeated twice (the standard test) and on a real passage repeated twice. A head attending evenly would score about 0.003."],
  copygain: ['Copy gain', 'Higher', 'How much easier the second copy is to predict than the first, in nats per token. Only a model that copies can gain.'],
  bpb: ['Bits per byte on English held-out books', 'Lower', 'How many bits the model needs, on average, to guess each byte of books it never saw. Fewer bits means better bets on unseen text. It is the headline score every rung shares.'],
  word_inside: ['Bits per byte inside a word', 'Lower', 'Letters after the first one in a word. Once a word has begun, how surely does the model know how it goes on? This is spelling.'],
  word_start: ['Bits per byte at a word start', 'Lower', 'The first letter of each word: which word comes next. That depends on grammar and meaning more than spelling, so expect it to stay high at 9m.'],
  punct: ['Bits per byte on punctuation', 'Lower', 'Commas, full stops, quotation marks, dashes. How well the model knows where punctuation goes.'],
  space: ['Bits per byte on spaces', 'Lower', 'Knowing where a word ends. A spelling skill as much as a layout one.'],
  newline: ['Bits per byte on line breaks', 'Lower', 'Paragraph and verse layout: where lines end.'],
  nonword_rate: ['Non-words', 'Lower, down to the books\' own rate', 'Share of the words the model writes that never appear anywhere on its shelf: invented spellings. The books\' own rate (ref) is the floor, because real text also holds words the shelf lacks. Reaching ref means it spells like a book.'],
  zipf: ['Zipf slope', 'Closer to the books', 'How fast word frequency falls with rank (the 10th commonest word is about a tenth as common as the 1st). Below the books: words used too evenly, as in noise. Above: too much repetition of a few common words. Real English sits near 1.'],
  heaps: ['Heaps slope', 'Closer to the books', 'How fast new words keep appearing as text goes on. Above the books usually means inventing words; below means a small, repetitive vocabulary.'],
  word_len: ['Mean word length', 'Closer to the books', 'Average letters per word. Real text prefers short common words (brevity law); a model that writes long strings of letters scores high here.'],
  punct_per_100w: ['Punctuation per 100 words', 'Closer to the books', 'How much punctuation it uses at all. Too much is a common early failure: commas and quote marks sprayed everywhere.'],
  unbalanced_per_kw: ['Unbalanced brackets and quotes per 1,000 words', 'Lower, down to the books\' own rate', 'Brackets and curly quotes closed without being opened, or left open. The books have a few because the excerpts are cut mid-passage; that is the floor.'],
  cap_after_stop: ['Capital after a full stop', 'Higher, up to the books', 'Share of sentence ends followed by a capital letter. Books score about 0.9 (abbreviations such as "Mr." account for the rest).'],
  word_len_js: ['Word-length divergence', 'Lower (0 is identical)', 'Jensen–Shannon divergence, in bits, between the model\'s mix of word lengths and the books\'. 0 means the same shape.'],
  punct_js: ['Punctuation-mix divergence', 'Lower (0 is identical)', 'Divergence between which punctuation marks the model uses and which the books use: the right marks in the right proportions.'],
  traits: ['Traits as they emerge', 'Earlier and stronger', 'Can a probe read fiction, verse or first person off the model\'s hidden state, at which layer, from which step? Shown on the Traits tab for each run.'],
  ft: ['The Forgotten Tomes score', 'Lower', 'Bits per byte on 16 period books released on Gutenberg after Qwen 3.8 appeared, so no Qwen model can have trained on them. The same number for Thorp and for Qwen, whatever their tokenisers: the yardstick for the order-of-magnitude gate.'],
  rank: ['Rank agreement with 9m', 'Higher (1 is perfect)', 'Spearman correlation between the order 9m puts the shelves in and the order 1m puts them in. At 0.8 or above the proxy is trusted to explore those kinds of questions.'],
  modelref: ['model / ref', 'Model close to ref', 'Each law is measured on text the model writes (left) and on excerpts of the held-out books (ref, right), at the same length. The target is the books\' own value.'],
};
const info = k => { const h = HELP[k]; return h ? `<span class="info" tabindex="0">ⓘ<span class="pop"><b>${esc(h[0])}</b><br>Better: <b>${esc(h[1])}</b><br>${esc(h[2])}</span></span>` : ''; };
// popovers sit in scrolling tables, so they are placed against the window, kept on screen
function placePop(el) {
  const pop = el.querySelector('.pop'), r = el.getBoundingClientRect(), w = 280;
  pop.style.left = Math.max(8, Math.min(r.left - 8, window.innerWidth - w - 8)) + 'px';
  pop.style.top = (r.bottom + 6) + 'px';
}
window.addEventListener('scroll', () => document.querySelectorAll('.info.open').forEach(x => x.classList.remove('open')), true);
['mouseover', 'focusin'].forEach(ev => document.addEventListener(ev, e => { const el = e.target.closest && e.target.closest('.info'); if (el) placePop(el); }));
document.addEventListener('click', e => {
  const el = e.target.closest('.info');
  if (el) placePop(el);
  document.querySelectorAll('.info.open').forEach(x => { if (x !== el) x.classList.remove('open'); });
  if (el) el.classList.toggle('open');
});
const METRIC_KEY = { 'inside a word': 'word_inside', 'word start': 'word_start', 'punctuation': 'punct', 'layout': 'space', 'non-words': 'nonword_rate',
  'Zipf and Heaps': 'zipf', 'word length, punctuation mix': 'word_len_js', 'balance and capitals': 'cap_after_stop', 'traits as they emerge': 'traits',
  'Forgotten Tomes score': 'ft', 'rank agreement with 9m': 'rank' };


// ---- the books on a rung page: the Forgotten Tomes with every score, each run's training shelf, a reader
let tomesData = null;
let tomesKey = null, shelfKey = null;
// the Forgotten Tomes book by book: the best run at this size, the latest few, and the outside models
async function renderTomes(r, allRuns) {
  const scored = allRuns.filter(x => x.ft_en != null);
  const best = [...scored].sort((a, b) => a.ft_en - b.ft_en)[0];
  const pick = [...new Set([best, ...scored.slice(-4)].filter(Boolean).map(x => x.ship || x.name))];
  const key = [r.preset, pick.join(','), Math.floor(Date.now() / 60000)].join('|');
  if (key === tomesKey) return;
  tomesKey = key;
  const head = document.querySelector('#tomestable thead'), body = document.querySelector('#tomestable tbody');
  try { tomesData = await get('/api/tomes'); } catch (e) { body.innerHTML = '<tr><td class="empty">could not load the deck</td></tr>'; return; }
  const outside = Object.keys(tomesData.scores).filter(k => !ladderData.runs.some(x => (x.ship || x.name) === k));
  const cols = [...pick.filter(k => tomesData.scores[k]), ...outside];
  const label = c => c === (best && (best.ship || best.name)) ? `${esc(c)} <span class="pill good">best</span>` : esc(c);
  head.innerHTML = `<tr><th>title</th><th>author</th><th>released</th><th>size</th>${cols.map(c => `<th>${label(c)}${info('ft')}</th>`).join('')}</tr>`;
  body.innerHTML = tomesData.books.map(b => `<tr data-book="${b.book_id}"><td>${esc(b.title)}</td><td>${esc(b.author)}</td><td>${esc(b.released)}</td>
    <td>${fmtBytes(b.bytes)}</td>${cols.map(c => `<td>${fmt(tomesData.scores[c][b.book_id])}</td>`).join('')}</tr>`).join('');
}
// one run's training shelf, every book on it
async function renderShelf(r, runs) {
  const pick = document.getElementById('shelfpick'), filt = document.getElementById('bookfilter');
  const head = document.querySelector('#shelftable thead'), body = document.querySelector('#shelftable tbody');
  const names = runs.map(x => x.name);
  if (!names.length) { head.innerHTML = ''; body.innerHTML = '<tr><td class="empty">no runs at this size yet</td></tr>'; shelfKey = null; return; }
  const opts = runs.map(x => x.name).join(',');
  if (pick.dataset.opts !== opts) {
    const was = pick.value;
    pick.innerHTML = [...runs].reverse().map(x => `<option value="${esc(x.name)}">${esc(x.ship || x.name)} · ${esc(x.name)}</option>`).join('');
    pick.dataset.opts = opts;
    if (names.includes(was)) pick.value = was;
  }
  const key = [r.preset, pick.value, filt.value].join('|');
  if (key === shelfKey) return;
  shelfKey = key;
  const shelf = await get('/api/shelf?run=' + encodeURIComponent(pick.value || names[names.length - 1]));
  const q = filt.value.trim().toLowerCase();
  const rows = shelf.filter(b => !q || (b.title + ' ' + b.family).toLowerCase().includes(q));
  head.innerHTML = `<tr><th>title</th><th>family</th><th>language</th><th>tokens</th><th>bytes per token</th></tr>`;
  body.innerHTML = rows.map(b => `<tr data-book="${b.book_id}"><td>${esc(b.title)}</td><td>${esc(b.family)}</td><td>${esc(b.language)}</td>
    <td>${big(b.tokens)}</td><td>${fmt(b.bytes_per_token, 2)}</td></tr>`).join('') + `<tr><td colspan="5" class="note">${rows.length} of ${shelf.length} books</td></tr>`;
}
document.getElementById('shelfpick').onchange = () => renderRung();
document.getElementById('bookfilter').oninput = () => renderRung();

// ---- the ladder: home cards, then one page per rung with the metrics that judge its job
const SPLIT_LABEL = { word_inside: 'inside a word', word_start: 'word start', punct: 'punctuation', space: 'space', newline: 'newline' };
const LAW_COLS = [
  ['nonword_rate', 'non-words', 3], ['zipf', 'Zipf', 2], ['heaps', 'Heaps', 2], ['word_len', 'word length', 2],
  ['punct_per_100w', 'punct /100 w', 1], ['unbalanced_per_kw', 'unbalanced /1k w', 1], ['cap_after_stop', 'capital after stop', 2],
  ['word_len_js', 'word-length JS', 3], ['punct_js', 'punct mix JS', 3],
];
var ladderData = null;  // var: showTab reads it before this line runs
const rungRuns = p => ladderData.runs.filter(r => r.preset === p && !(r.name || '').startsWith('smoke'));
async function loadLadder() {
  try { ladderData = await get('/api/ladder'); } catch (e) { return; }
  const d = ladderData;
  document.getElementById('rungcards').innerHTML = d.rungs.map(r => {
    const runs = rungRuns(r.preset), live = runs.filter(x => x.status === 'running').length, done = runs.filter(x => x.status === 'finished').length;
    const nlive = r.metrics.filter(m => m[2] === 'live').length;
    return `<a class="card" href="#${esc(modelHash(r))}">
      <div class="top"><span class="preset">${esc(r.preset)}</span><span class="nm">${esc(r.name)}</span></div>
      <div class="job">${esc(r.job)}</div><div class="ov">${esc(r.overview)}</div>
      <div class="foot"><span>${big(r.total)} params · ${esc(r.where.split(' (')[0])}</span>
      <span class="pill${live ? ' live' : ''}">${live ? live + ' running' : esc(r.status)}</span></div>
      <div class="foot"><span>${done} finished run${done === 1 ? '' : 's'}</span><span>${nlive} of ${r.metrics.length} metrics live</span></div></a>`;
  }).join('');
  document.querySelector('#queue tbody').innerHTML = d.queue.map((q, i) => `<tr${q.status === 'running' ? ' class="sel"' : ''}><td>${i + 1}</td>
    <td>${esc(q.name)}</td><td>${esc(q.status.split(':')[0])}</td></tr>`).join('');
  if (document.getElementById('rung').classList.contains('active')) showTab(location.hash.slice(1), false);
}
const RECENT = 30;
// ---- RunGrid: every run at one size as a square, like a GitHub contribution graph. Bands of 7 rows
// x 53 columns (a "year" of 371 runs) stack downwards, so a new run only ever adds a square at the
// end. Colour is the run's Forgotten Tomes quartile among the scored runs: deepest green is best.
const GRID_ROWS = 7, GRID_COLS = 53;
let gridKey = '';
function runGrid(r, runs) {
  const el = document.getElementById('rungrid'), sum = document.getElementById('rungridsum');
  const key = r.preset + '|' + selected + '|' + runs.map(x => x.run_id + (x.status || '')[0] + (x.ft_en ?? '')).join(',');
  if (key === gridKey) return;
  gridKey = key;
  if (!runs.length) { sum.innerHTML = ''; el.innerHTML = `<div class="empty">no runs at ${esc(r.preset)} yet</div>`; return; }
  const scored = runs.filter(x => x.ft_en != null).sort((a, b) => a.ft_en - b.ft_en);
  const rank = new Map(scored.map((x, i) => [x.run_id, i]));
  const level = x => !rank.has(x.run_id) ? 0 : 4 - Math.min(3, Math.floor(4 * rank.get(x.run_id) / scored.length));
  const live = runs.filter(x => x.status === 'running').length;
  const med = scored.length ? scored[Math.floor((scored.length - 1) / 2)].ft_en : null;
  const latest = [...runs].reverse().find(x => x.ft_en != null);
  sum.innerHTML = `<span><b>${runs.length}</b> run${runs.length === 1 ? '' : 's'}</span><span><b>${scored.length}</b> scored</span>${live ? `<span class="pill blue">${live} running</span>` : ''}`
    + (scored.length ? `<span>best <b>${fmt(scored[0].ft_en)}</b> ${esc(scored[0].ship || scored[0].name)}</span><span>median <b>${fmt(med)}</b></span><span>latest <b>${fmt(latest.ft_en)}</b> ${esc(latest.ship || latest.name)}</span>` : '')
    + `<span class="legend">worse <i class="g1"></i><i class="g2"></i><i class="g3"></i><i class="g4"></i> better · <i class="g0"></i> not scored</span>`;
  const per = GRID_ROWS * GRID_COLS, bands = [];
  for (let b = 0; b * per < runs.length; b++) {
    const chunk = runs.slice(b * per, (b + 1) * per);
    bands.push(`<div class="gridband"><div class="gridlabel">runs ${b * per + 1}–${b * per + chunk.length}</div><div class="rungrid">${chunk.map(x => {
      const st = (x.status || '').split(':')[0];
      return `<i class="g${level(x)}${st === 'running' ? ' run' : ''}${st === 'failed' ? ' fail' : ''}${x.run_id === selected ? ' sel' : ''}" data-run="${esc(x.run_id)}"></i>`;
    }).join('')}</div></div>`);
  }
  el.innerHTML = bands.join('');
  el._runs = new Map(runs.map(x => [x.run_id, x])); el._rank = rank; el._n = scored.length;
}
(() => {
  const el = document.getElementById('rungrid'), tip = document.createElement('div');
  tip.className = 'gridtip'; tip.hidden = true; document.body.appendChild(tip);
  el.addEventListener('mouseover', e => {
    const c = e.target.closest('i[data-run]'); if (!c) return;
    const x = el._runs.get(c.dataset.run); if (!x) return;
    const k = el._rank.get(x.run_id), st = (x.status || '').split(':')[0];
    tip.innerHTML = `<b>${esc(x.ship || x.name)}</b> <span class="s">${esc(x.name)}</span><br>`
      + (x.ft_en != null ? `Forgotten Tomes <b>${fmt(x.ft_en)}</b> bpb · #${k + 1} of ${el._n}` : `no Forgotten Tomes score yet`)
      + `<br>${esc(st)}${x.passes ? ` · ${x.passes} pass${x.passes === 1 ? '' : 'es'}` : ''}${x.started ? ` · started ${esc(String(x.started).slice(0, 16).replace('T', ' '))}` : ''}`;
    const b = c.getBoundingClientRect(); tip.hidden = false;
    tip.style.left = Math.max(8, Math.min(b.left - 8, innerWidth - tip.offsetWidth - 8)) + 'px';
    tip.style.top = (b.bottom + 6) + 'px';
  });
  el.addEventListener('mouseout', e => { if (e.target.closest('i[data-run]')) tip.hidden = true; });
  // a square opens its run, as a row in the Runs table does
  el.addEventListener('click', e => {
    const c = e.target.closest('i[data-run]'); if (!c) return;
    selected = c.dataset.run; history.replaceState(null, '', '?run=' + selected + location.hash); refresh();
  });
})();  // panels that draw one mark per run show the latest RECENT; the run grid shows every run
// Scoring is in two parts. Science: how well the model predicts text it has never seen (bits per
// byte, the split by kind of byte, ranking shelves as a bigger model does, the bets). Art: how its
// writing compares with real books (the laws of text, non-words, grammar, voice, traits). A metric
// not named here counts as science.
const ART = new Set(['non-words', 'Zipf and Heaps', 'word length, punctuation mix', 'balance and capitals',
  'traits as they emerge', 'minimal pairs', 'register probe', 'the 9m laws']);
const metricRows = list => list.length ? list.map(m => `<tr><td><b>${esc(m[0])}</b>${info(METRIC_KEY[m[0]])}</td><td>${esc(m[1])}</td>
    <td>${HELP[METRIC_KEY[m[0]]] ? esc(HELP[METRIC_KEY[m[0]]][1]) : '–'}</td>
    <td><span class="pill${m[2] === 'live' ? ' live' : ''}">${esc(m[2])}</span></td></tr>`).join('')
  : '<tr><td colspan="4" class="empty">none for this model yet</td></tr>';
const runCells = x => `<td>${esc(x.ship || '')}</td><td>${esc(x.name)}</td><td>${esc((x.status || '').split(':')[0])}</td>`;
function renderRung() {
  const r = rungFor(currentRung) || ladderData.rungs[0];
  // the template's own slot: panels marked data-kind show only on that kind of model
  document.querySelectorAll('#rung [data-kind]').forEach(el => { el.hidden = !el.dataset.kind.split(' ').includes(r.kind || slugOf(r)); });
  document.getElementById('rungtitle').textContent = `${r.preset} · ${r.name}`;
  document.getElementById('rungjob').textContent = r.job;
  const allRuns = rungRuns(r.preset), runs = allRuns.slice(-RECENT), capped = allRuns.length > runs.length;
  const more = (n) => capped ? `<tr><td colspan="${n}" class="note">the latest ${runs.length} of ${allRuns.length} runs at ${esc(r.preset)}; the Overview grid has every one</td></tr>` : '';
  const none = (n) => `<tr><td colspan="${n}" class="empty">no runs at ${esc(r.preset)} yet</td></tr>`;
  document.querySelectorAll('#rung .recentnote').forEach(el => { el.textContent = capped ? `(the latest ${runs.length} of ${allRuns.length} runs)` : ''; });

  // ---- Overview: every run, and the Forgotten Tomes score run by run
  runGrid(r, allRuns);
  ftProgress(allRuns);

  // ---- Training: the model, each run's setup, loss, the shelves
  document.getElementById('rungover').innerHTML = [
    ['overview', r.overview], ['shape', `${r.layers} layers × ${r.width} wide, ${r.heads} heads`],
    ['parameters', `${big(r.total)} (${big(r.non_embedding)} non-embedding)`], ['where it trains', r.where],
    ['judged by', r.scored], ['status', r.status],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${esc(v)}</div></div>`).join('');
  const shelfName = x => esc((x.recipe || '–').replace('lists/', '').replace('.csv', ''));
  document.querySelector('#trainruns tbody').innerHTML = runs.length ? runs.map(x => `<tr data-run="${esc(x.run_id)}">${runCells(x)}<td>${shelfName(x)}</td>
    <td>${x.passes ?? '–'}</td><td>${x.seed ?? '–'}</td><td>${x.vocab ?? '–'}</td><td>${x.context ?? '–'}</td><td>${big(x.tokens_seen)}</td>
    <td>${fmt(x.wall_minutes, 1)}</td><td>${esc(String(x.started || '–').slice(0, 16).replace('T', ' '))}</td></tr>`).join('') + more(11) : none(11);
  renderShelf(r, runs);

  // ---- Scoring: science, then art
  document.querySelector('#sciencemetrics tbody').innerHTML = metricRows(r.metrics.filter(m => !ART.has(m[0])));
  document.querySelector('#artmetrics tbody').innerHTML = metricRows(r.metrics.filter(m => ART.has(m[0])));
  document.querySelector('#scienceboard thead').innerHTML = `<tr><th>ship</th><th>name</th><th>status</th><th>Forgotten Tomes${info('ft')}</th>
    <th>held-out bpb (en)${info('bpb')}</th>${Object.entries(SPLIT_LABEL).map(([k, l]) => `<th>${l}${info(k)}</th>`).join('')}</tr>`;
  document.querySelector('#scienceboard tbody').innerHTML = runs.length ? runs.map(x => `<tr>${runCells(x)}<td>${fmt(x.ft_en)}</td><td>${fmt(x.bpb_en)}</td>
    ${Object.keys(SPLIT_LABEL).map(c => `<td>${fmt(x.split[c])}</td>`).join('')}</tr>`).join('') + more(10) : none(10);
  const cell = (m, ref, dg) => m == null ? '–' : `${fmt(m, dg)}${ref == null ? '' : ` <span class="s">/ ${fmt(ref, dg)}</span>`}`;
  document.querySelector('#artboard thead').innerHTML = `<tr><th>ship</th><th>name</th><th>status</th>${LAW_COLS.map(c => `<th>${c[1]}${info(c[0])}<br><span class="s">model / ref</span>${info('modelref')}</th>`).join('')}</tr>`;
  document.querySelector('#artboard tbody').innerHTML = runs.length ? runs.map(x => `<tr>${runCells(x)}
    ${LAW_COLS.map(([k, , dg]) => `<td>${cell(x.laws[k], x.ref[k], dg)}</td>`).join('')}</tr>`).join('') + more(3 + LAW_COLS.length) : none(3 + LAW_COLS.length);
  const split = runs.filter(x => Object.values(x.split).some(v => v != null));
  if (!split.length) empty('splitchart', runs.length ? 'the split arrives when scripts/queue_9m.sh re-scores the finished runs, after tonight\'s pool runs' : 'no runs at this size yet');
  else plot('splitchart', split.map((x, i) => ({ type: 'bar', name: x.ship || x.name, x: Object.values(SPLIT_LABEL),
    y: Object.keys(SPLIT_LABEL).map(c => x.split[c]), marker: { color: PALETTE[i % PALETTE.length] } })),
    layout({ barmode: 'group', yaxis: { title: 'bits per byte', gridcolor: C.line } }));
  const ratioKeys = LAW_COLS.filter(c => !c[0].endsWith('_js'));
  const laws = runs.filter(x => Object.values(x.laws).some(v => v != null));
  if (!laws.length) empty('lawchart', runs.length ? 'the laws arrive with the same re-score' : 'no runs at this size yet');
  else plot('lawchart', laws.map((x, i) => ({ type: 'bar', name: x.ship || x.name, x: ratioKeys.map(c => c[1]),
    y: ratioKeys.map(([k]) => x.laws[k] != null && x.ref[k] ? x.laws[k] / x.ref[k] : null), marker: { color: PALETTE[i % PALETTE.length] } })),
    layout({ barmode: 'group', yaxis: { title: 'model ÷ books', gridcolor: C.line },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: C.accent, dash: 'dot' } }] }));
  renderTomes(r, allRuns);
  rungExtras(r, runs, allRuns);
  if (modelTab === 'waypoints') renderWaypoints(r);
  document.querySelectorAll('#rung .chart').forEach(el => { if (el.data && el.offsetParent) Plotly.Plots.resize(el); });
}
// ---- Waypoints: when each run passed each waypoint (server.py api_waypoints). Fetched only while
// the tab is open; the thresholds come from the evaluators, never typed in here.
const TRAIT_LABEL = { fiction: 'fiction', verse: 'verse', first_person: 'first person' };
const firstAt = (sr, ok) => { if (!sr) return undefined; const i = sr.value.findIndex(ok); return i < 0 ? null : sr.step[i]; };
const lastOf = sr => sr && sr.value.length ? sr.value[sr.value.length - 1] : null;
let wpKey = '';
async function renderWaypoints(r) {
  let d;
  try { d = await get('/api/waypoints?preset=' + encodeURIComponent(r.preset) + '&limit=' + RECENT); } catch (e) { return; }
  const key = JSON.stringify(d);
  if (key === wpKey) return;
  wpKey = key;
  document.getElementById('readpassage').dataset.book = d.natural_book;
  const thr = d.nevermore_threshold, found = d.trait_found, margin = d.trait_margin, core = d.core_traits;
  const stepCell = v => v === undefined ? '<td>–</td>' : v === null ? '<td data-sort="">not yet</td>' : `<td data-sort="${v}">step ${v}</td>`;
  // a trait is learned at the first step where it is found and clears both floors (where they were measured)
  const traitAt = t => {
    if (!t || !t.best) return { found: undefined, learned: undefined };
    const fl = i => Math.max(...['floor_bow', 'floor_init'].map(k => (t[k] && t[k].value[t[k].step.indexOf(t.best.step[i])]) ?? -Infinity));
    const hasFloors = t.floor_bow || t.floor_init;
    const fi = t.best.value.findIndex(v => v >= found);
    const li = hasFloors ? t.best.value.findIndex((v, i) => v >= found && v - fl(i) >= margin) : -2;
    return { found: fi < 0 ? null : t.best.step[fi], learned: li === -2 ? undefined : li < 0 ? null : t.best.step[li] };
  };
  document.querySelector('#waypointtable thead').innerHTML = `<tr><th>ship</th><th>name</th><th>status</th><th>Nevermore formed</th>
    <th>real prose best${info('nevermore')}</th><th>random best${info('nevermore')}</th><th>Nevermores (real / random)</th><th>where</th><th>copy gain${info('copygain')}</th>
    ${core.map(t => `<th>${TRAIT_LABEL[t] || t} found</th><th>${TRAIT_LABEL[t] || t} learned</th>`).join('')}<th>language families found</th></tr>`;
  document.querySelector('#waypointtable tbody').innerHTML = d.runs.length ? d.runs.map(x => {
    const nv = x.nevermore, fams = Object.keys(x.traits).filter(t => t.startsWith('family/'));
    const famFound = fams.filter(t => traitAt(x.traits[t]).found != null).length;
    // formed: the first step where either test has a head at the threshold
    const a = firstAt(nv.natural_max_score, v => v >= thr), b = firstAt(nv.max_score, v => v >= thr);
    const formed = a === undefined && b === undefined ? undefined : [a, b].filter(v => v != null).sort((p, q) => p - q)[0] ?? null;
    const L = lastOf(nv.natural_best_layer), H = lastOf(nv.natural_best_head);
    const count = (k) => lastOf(nv[k]) == null ? '–' : String(Math.round(lastOf(nv[k])));
    return `<tr>${runCells(x)}${stepCell(formed)}<td>${fmt(lastOf(nv.natural_max_score), 3)}</td><td>${fmt(lastOf(nv.max_score), 3)}</td>
      <td>${nv.natural_count || nv.count ? `${count('natural_count')} / ${count('count')}` : '–'}</td>
      <td>${L == null ? '–' : `layer ${Math.round(L)}, head ${Math.round(H)}`}</td><td>${fmt(lastOf(nv.natural_copy_gain) ?? lastOf(nv.copy_gain), 2)}</td>
      ${core.map(t => { const q = traitAt(x.traits[t]); return stepCell(q.found) + stepCell(q.learned); }).join('')}
      <td>${fams.length ? `${famFound} of ${fams.length}` : '–'}</td></tr>`;
  }).join('') : `<tr><td colspan="${10 + 2 * core.length}" class="empty">no runs at ${esc(r.preset)} yet</td></tr>`;

  const recent = d.runs.slice(-12);
  const lines = (pick, id, title, msg, extra = {}) => {
    const rs = recent.filter(x => pick(x) && pick(x).step.length);
    if (!rs.length) return empty(id, msg);
    plot(id, rs.map((x, i) => ({ type: 'scatter', mode: 'lines+markers', name: x.ship || x.name, x: pick(x).step, y: pick(x).value,
      line: { color: PALETTE[i % PALETTE.length], width: 1.5 }, marker: { size: 4 } })),
      layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title, gridcolor: C.line }, ...extra }));
  };
  const hline = (y) => ({ shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color: C.accent, dash: 'dot' } }] });
  const nvMsg = `no run at ${esc(r.preset)} has Nevermore scores on the ledger yet: queued runs record them every 250 steps, loop runs at their last step, and <span class="mono">scripts/score_nevermore.sh</span> scores every finished 1m and 9m run once. First test readings: none formed anywhere yet; Smaller Pieces (9m, vocabulary 4,096) has one forming in its top layer, 0.12 on real prose`;
  lines(x => x.nevermore.natural_max_score || x.nevermore.max_score, 'nvchart', 'Nevermore score', nvMsg, { ...hline(thr), yaxis: { title: 'Nevermore score', gridcolor: C.line, range: [0, 1] } });
  lines(x => x.nevermore.natural_copy_gain || x.nevermore.copy_gain, 'copychart', 'nats per token', nvMsg);
  for (const t of core) lines(x => x.traits[t] && x.traits[t].best, 'trait-' + t, 'held-out AUC',
    `no run at ${esc(r.preset)} has trait probes yet; add <span class="mono">probes</span> to eval.evaluators`, { ...hline(found), showlegend: false });
}

// the Waypoints write-ups and the Nevermore test passage open in the reader
document.querySelectorAll('[data-essay]').forEach(b => b.onclick = () => openEssay(b.dataset.essay));
document.getElementById('readpassage').onclick = e => { if (e.currentTarget.dataset.book) openBook(e.currentTarget.dataset.book); };

// a Training row opens its run, as the Runs table does
document.getElementById('trainruns').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-run]'); if (!tr || e.target.closest('.info')) return;
  selected = tr.dataset.run; history.replaceState(null, '', '?run=' + selected + location.hash); refresh();
});

// Overview's second chart: every scored run's Forgotten Tomes score in start order, the best so far,
// and the outside models as dotted lines. One trace of dots, so thousands of runs stay quick.
let ftKey = '';
function ftProgress(allRuns) {
  const ext = (ladderData.external || []).filter(x => x.set === 'hole-cards-unseen' && x.bpb_mean_en != null);
  const pts = allRuns.map((x, i) => ({ x, i: i + 1 })).filter(p => p.x.ft_en != null);
  const key = pts.map(p => p.x.run_id + p.x.ft_en).join(',') + '|' + ext.length;
  if (key === ftKey) return;
  ftKey = key;
  if (!pts.length) return empty('ftchart', 'no run at this size has a Forgotten Tomes score yet');
  let best = Infinity;
  const bestSoFar = pts.map(p => (best = Math.min(best, p.x.ft_en)));
  plot('ftchart', [
    { type: 'scattergl', mode: 'markers', name: 'a run', x: pts.map(p => p.i), y: pts.map(p => p.x.ft_en),
      text: pts.map(p => `${p.x.ship || p.x.name} · ${p.x.name}`), hovertemplate: 'run %{x}: %{text}<br>%{y:.3f} bpb<extra></extra>',
      marker: { size: 6, color: C.blue, opacity: 0.55 } },
    { type: 'scatter', mode: 'lines', name: 'best so far', x: pts.map(p => p.i), y: bestSoFar, line: { color: C.good, width: 2, shape: 'hv' },
      hovertemplate: 'best so far %{y:.3f}<extra></extra>' },
  ], layout({ xaxis: { title: 'run, in the order they started', gridcolor: C.line },
    yaxis: { title: 'bits per byte', gridcolor: C.line, range: (() => {  // wide enough for the Qwen lines too
      const ys = [...pts.map(p => p.x.ft_en), ...ext.map(x => x.bpb_mean_en)], lo = Math.min(...ys), hi = Math.max(...ys), pad = (hi - lo) * 0.06 || 0.05;
      return [lo - pad, hi + pad]; })() },
    legend: { orientation: 'h', y: 1.08 },
    shapes: ext.map((x, i) => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: x.bpb_mean_en, y1: x.bpb_mean_en, line: { color: PALETTE[(i + 4) % PALETTE.length], dash: 'dot' } })),
    annotations: ext.map((x, i) => ({ xref: 'paper', x: 1, xanchor: 'right', y: x.bpb_mean_en, yanchor: 'bottom', showarrow: false,
      text: `${x.model.split('/').pop()} ${x.bpb_mean_en.toFixed(3)}`, font: { size: 10, color: PALETTE[(i + 4) % PALETTE.length] } })) }));
}

// training loss, and (for the proxy) calibration against 9m
async function rungExtras(r, runs, allRuns) {
  try {
    const curves = await get('/api/rung?preset=' + encodeURIComponent(r.preset) + '&limit=12');
    const withLoss = curves.filter(c => c.steps.length);
    if (!withLoss.length) empty('losschart', 'no training at this size yet');
    else plot('losschart', withLoss.map((c, i) => ({ type: 'scatter', mode: 'lines', name: c.ship || c.name, x: c.steps, y: ema(c.loss, 9),
      line: { color: PALETTE[i % PALETTE.length], width: 1.5 } })), layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'loss', gridcolor: C.line } }));
  } catch (e) { empty('losschart', 'could not load the curves'); }
  if (r.kind !== 'proxy') return;
  const big9 = ladderData.runs.filter(x => x.preset === ladderData.rungs.find(q => q.kind !== 'proxy').preset);
  // only proxy runs with a 9m twin calibrate anything; the loop's random shelves have none
  const pairs = allRuns.map(p => ({ p, n: big9.find(n => n.recipe === p.recipe && n.passes === p.passes && n.seed === p.seed && n.status === 'finished') })).filter(x => x.n);
  document.querySelector('#caltable tbody').innerHTML = pairs.map(({ p, n }) => `<tr><td>${esc((p.recipe || '').replace('lists/', '').replace('.csv', ''))}</td>
    <td>${p.passes ?? '–'}</td><td>${n ? esc(n.ship || n.name) : '–'}</td><td>${fmt(n && n.ft_en)}</td><td>${esc(p.ship || p.name)}</td><td>${fmt(p.ft_en)}</td></tr>`).join('');
  const both = pairs.filter(({ p, n }) => n && n.ft_en != null && p.ft_en != null);
  const rank = a => a.map(v => a.filter(w => w < v).length);
  let verdict = `${both.length} of ${pairs.length} shelves scored at both sizes.`;
  if (both.length >= 3) {
    const a = rank(both.map(x => x.n.ft_en)), b = rank(both.map(x => x.p.ft_en)), k = a.length;
    const rho = 1 - 6 * a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0) / (k * (k * k - 1));
    verdict += ` Rank agreement (Spearman) ${rho.toFixed(2)}: ${rho >= 0.8 ? 'the proxy orders the shelves as 9m does' : 'not yet trustworthy'}.`;
  } else verdict += ' Rank agreement needs at least three; the 9m runs are re-scored on the Forgotten Tomes by the queue.';
  document.getElementById('calverdict').textContent = verdict;
  if (!both.length) empty('calchart', 'points appear when a shelf has a Forgotten Tomes score at both sizes');
  else plot('calchart', [{ type: 'scatter', mode: 'markers+text', x: both.map(x => x.n.ft_en), y: both.map(x => x.p.ft_en),
    text: both.map(x => x.n.ship || x.n.name), textposition: 'top center', marker: { size: 10, color: C.accent } }],
    layout({ xaxis: { title: '9m score', gridcolor: C.line }, yaxis: { title: '1m score', gridcolor: C.line } }));
}


// the run overview folds away; the choice is remembered per viewer
(() => {
  const el = document.getElementById('stripwrap');
  try { if (localStorage.getItem('thorp.strip') === 'closed') el.open = false; } catch (e) {}
  el.addEventListener('toggle', () => { try { localStorage.setItem('thorp.strip', el.open ? 'open' : 'closed'); } catch (e) {} });
})();
async function refresh() {
  loadLadder();
  try {
    const runs = await get('/api/runs');
    if (!runs.length) { document.getElementById('title').textContent = 'no runs in the ledger yet'; return; }
    if (!selected || !runs.find(r => r.run_id === selected)) {
      selected = (runs.find(r => r.status === 'running' && r.name && !r.name.startsWith('smoke')) || runs.find(r => r.status === 'running') || runs[0]).run_id;
    }
    runsTable(runs);
    runPicker(runs);
    const cur = runs.find(x => x.run_id === selected);
    if (cur) document.getElementById('stripsum').textContent = `${cur.ship || cur.name} · ${(cur.status || '').split(':')[0]}`;
    const [r, m, evals, cmp, content] = await Promise.all([get('/api/run?run=' + selected), get('/api/metrics?run=' + selected), get('/api/evals?run=' + selected), get('/api/compare'), get('/api/experiment?prefix=content-')]);
    const rec = (r.recipe && r.recipe.data) || [];
    const fams = [...new Set(rec.map(b => b.family).concat(Object.values(holeMeta(r)).map(b => b.family)))].filter(Boolean).sort();
    const famColour = f => PALETTE[Math.max(0, fams.indexOf(f)) % PALETTE.length];
    const series = bookSeries(m, r);
    const gk = kinksOf(m, 'grad_norm/');
    headline(r, m, gk);
    contentPanel(content);
    claimPanel(cmp);
    comparePanel(cmp);
    matchedPanel(cmp);
    truthGapPanel(cmp);
    lossPanel(m, r.sets || []);
    bpbPanel(evals, r);
    bookPanels(m, r, series, fams, famColour);
    fallbackPanel(r);
    languagePanels(r, evals, series, fams, famColour);
    heat('gradheat', m, 'grad_norm/', gk, 'log10');
    heat('moveheat', m, 'update_ratio/', kinksOf(m, 'update_ratio/'), 'log10');
    kinkPanel(m, gk);
    attnPanels(m);
    speedPanel(m);
    probePanel(r, gk);
    ladderPanel(r, m);
    samplesPanel(r);
    document.getElementById('updated').textContent = 'updated ' + new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById('updated').textContent = 'error: ' + e;
  }
}
refresh();
setInterval(refresh, 5000);
