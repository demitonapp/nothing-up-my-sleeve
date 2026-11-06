// The dashboard: tabs, the run picker, every panel, refreshed every 5 s from the JSON API in
// server.py. Shared pieces live in ../lib (formatters, charts, DataTable, the reader).
import { Plotly, tok, C, PALETTE, layout, cfg, empty, plot } from '../lib/charts.js';
import { fmt, big, fmtBytes, esc, get, log10, mean } from '../lib/format.js';
import { DataTable } from '../lib/datatable.js';
import { openBook, openEssay } from '../lib/reader.js';
import { renderHand, miniHand } from '../lib/cards.js';
import { drawJourney, soundingSteps } from '../lib/journey.js';

// metric keys: `<prefix>/layer_3`, `<prefix>/layer_3/attn`, `<prefix>/tok`, `<prefix>/pos`
const groupOf = (k, prefix) => k.slice(prefix.length);
const groupOrder = g => g === 'tok' ? -2 : g === 'pos' ? -1 : +g.split('/')[0].split('_').pop();
const groupLabel = g => g.startsWith('layer_') ? 'layer ' + g.split('/')[0].split('_').pop() : g === 'tok' ? 'token emb' : g === 'pos' ? 'position emb' : g;
const topKeys = (m, prefix) => Object.keys(m).filter(k => k.startsWith(prefix) && !groupOf(k, prefix).includes('/')).sort((a, b) => groupOrder(groupOf(a, prefix)) - groupOrder(groupOf(b, prefix)));
const layerOnly = (m, prefix) => topKeys(m, prefix).filter(k => groupOf(k, prefix).startsWith('layer_'));

let selected = new URLSearchParams(location.search).get('run');

let currentRung = null;
const slugOf = r => r.name.toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-');
// classes renamed (old address name -> new; server.py CLASS_RENAMES): either name opens the class,
// and the address is rewritten to the class's current name
const CLASS_RENAMES = { seedling: 'keel', proxy: 'pilot' };
const CLASS_ALIASES = Object.fromEntries(Object.entries(CLASS_RENAMES).flatMap(([a, b]) => [[a, b], [b, a]]));
const rungFor = key => ladderData && ladderData.rungs.find(r => slugOf(r) === key || r.preset === key || slugOf(r) === CLASS_ALIASES[key]);
// ---- Navigation (UI.md, "Navigation"). Three ways in, each a section of the header:
//   #/classes                    the classes of ship, one card per model size (home)
//   #/classes/<class>[/<tab>]    one class: fleet (default), goals, overview, training, scoring, waypoints
//   #/ships                      every ship ever launched
//   #/ships/<key>[/<sailing>[/<tab>]]  one ship (a class fitted out one way) and one of its sailings (runs):
//                                betting (default), books, languages, sieves, attention, traits
//   #/voyages, #/voyages/<key>   the voyages, and one voyage
//   #/discoveries[/<trick>]      the tricks of the trade, and one trick; /stars and /traits beside them
//   #/sieves[/<sailing>]         the sieves explained, and one sailing's push, move and heading
// Older addresses (#sizes, #proxy, #rung-1m, #/models/…, #betting…, ?run=) land on the new ones.
const MTABS = ['fleet', 'goals', 'overview', 'training', 'scoring', 'waypoints'];
const STABS = ['betting', 'books', 'languages', 'sieves', 'attention', 'traits'];
const STAB_EL = { betting: 'betting', books: 'books', languages: 'languages', sieves: 'sieves', attention: 'attention', traits: 'traits-section' };
const OLD_SHIP = { betting: 'betting', books: 'books', languages: 'languages', sieves: 'sieves', attention: 'attention', 'traits-section': 'traits' };
const SECTION_NAV = { sizes: 'classes', rung: 'classes', ship: 'classes', 'runs-section': 'classes', voyages: 'voyages', voyage: 'voyages', discoveries: 'discoveries', sievesguide: 'sieves' };
let discView = 'index', discTrick = null;
let page = 'sizes', modelTab = 'fleet', shipKey = null, sailingKey = null, shipTab = 'betting', voyageKey = null, runsList = null, shipsData = null;
function route(h) {
  if (h.startsWith('/')) {
    const [a, b, c] = h.slice(1).split('/');
    if (a === 'classes' && b) return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'fleet' };
    if (a === 'models' && b) return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'overview' };
    if (a === 'ships' && b) {
      const d = h.slice(1).split('/')[3];
      if (STABS.includes(c)) return { page: 'ship', ship: decodeURIComponent(b), sailing: null, stab: c };
      return { page: 'ship', ship: decodeURIComponent(b), sailing: c ? decodeURIComponent(c) : null, stab: STABS.includes(d) ? d : 'betting' };
    }
    if (a === 'ships') return { page: 'runs-section' };
    if (a === 'voyages' && b) return { page: 'voyage', voyage: b };
    if (a === 'voyages') return { page: 'voyages' };
    if (a === 'discoveries') return { page: 'discoveries', dview: !b ? 'index' : (b === 'stars' || b === 'traits') ? b : 'trick', trick: b && b !== 'stars' && b !== 'traits' ? b : null };
    if (a === 'sieves') return { page: 'sievesguide', run: b ? decodeURIComponent(b) : null };
    return { page: 'sizes' };
  }
  if (h.startsWith('rung-')) return { page: 'rung', rung: h.slice(5), mtab: 'fleet' };
  if (h in OLD_SHIP) return { page: 'ship', ship: null, stab: OLD_SHIP[h] };
  if (h === 'runs-section') return { page: 'runs-section' };
  if (!h || h === 'sizes' || h === 'rung') return { page: 'sizes' };
  return { page: 'rung', rung: h, mtab: 'fleet' };  // an old class link: #proxy
}
const modelHash = (r, mt = 'fleet') => `/classes/${slugOf(r)}${mt === 'fleet' ? '' : '/' + mt}`;
const shipHash = (key, sailing = null, st = 'betting') => `/ships/${key}${sailing ? '/' + encodeURIComponent(sailing) : ''}${st === 'betting' ? '' : '/' + st}`;
const ladderRun = id => ladderData && ladderData.runs.find(x => x.run_id === id || x.name === id);
// The ship and sailing an address names. The first part is a ship key, or (an older address) a run
// name or id, which names its ship and that sailing. A ship without a sailing named opens its latest.
function shipRun(runs) {
  const ship = shipsData && shipsData.find(x => x.key === shipKey);
  let run = null;
  if (ship) {
    const sail = ship.sailings.find(x => x.name === sailingKey || x.run_id === sailingKey) || ship.sailings[ship.sailings.length - 1];
    run = runs.find(r => r.run_id === sail.run_id);
    return { ship, run };
  }
  if (shipKey) run = runs.find(r => r.name === shipKey || r.run_id === shipKey) || runs.find(r => r.run_id.startsWith(shipKey));
  else run = runs.find(r => r.run_id === selected) || runs.find(r => r.status === 'running' && r.name && !r.name.startsWith('smoke')) || runs[0];
  const lr = run && ladderRun(run.run_id);
  return { ship: lr && lr.ship_key && shipsData ? shipsData.find(x => x.key === lr.ship_key) : null, run };
}
// go to a run's ship and that sailing (a grid square, a training row, a discovery), or to a ship
function goShip(id) {
  const lr = ladderRun(id);
  location.hash = '#' + (lr && lr.ship_key ? shipHash(lr.ship_key, lr.name) : shipHash(lr ? lr.name : id));
}
const goShipKey = key => { location.hash = '#' + shipHash(key); };
function showTab(h, push = true) {
  const rt = route(h);
  let hash = null, wasShip = selected;
  page = rt.page;
  if (page === 'rung') {
    const r = rungFor(rt.rung);
    if (ladderData && !r) { page = 'sizes'; push = true; }  // not a class this ladder has
    else {
      currentRung = rt.rung; modelTab = rt.mtab;
      if (r) {
        hash = modelHash(r, modelTab);
        document.querySelectorAll('#modelnav a').forEach(a => { a.href = '#' + modelHash(r, a.dataset.mtab); });
      }
      if (ladderData) renderRung();
    }
  }
  if (page === 'ship') {
    shipKey = rt.ship; sailingKey = rt.sailing; shipTab = rt.stab;
    if (runsList && ladderData) {
      const { ship, run } = shipRun(runsList);
      if (run) {
        selected = run.run_id;
        if (ship) { shipKey = ship.key; sailingKey = run.name || run.run_id; } else { shipKey = run.name || run.run_id; sailingKey = null; }
        hash = shipHash(shipKey, sailingKey, shipTab);
      }
      document.querySelectorAll('#shipnav a').forEach(a => { a.href = '#' + shipHash(shipKey, sailingKey, a.dataset.stab); });
      shipHeader(ship, run);
    }
  }
  if (page === 'voyage') { voyageKey = rt.voyage; hash = '/voyages/' + voyageKey; }
  if (page === 'sizes') hash = '/classes';
  if (page === 'runs-section') hash = '/ships';
  if (page === 'voyages') hash = '/voyages';
  if (page === 'discoveries') {
    discView = rt.dview || 'index'; discTrick = rt.trick || null;
    hash = '/discoveries' + (discView === 'index' ? '' : '/' + (discView === 'trick' ? discTrick : discView));
    document.querySelectorAll('#discoveries .dview').forEach(v => v.classList.toggle('active', v.dataset.dview === discView));
    if (discData) drawDiscoveryView();
  }
  if (page === 'sievesguide') { sieveRun = rt.run; hash = '/sieves' + (sieveRun ? '/' + encodeURIComponent(sieveRun) : ''); }
  document.querySelectorAll('main > .section').forEach(s => s.classList.toggle('active', s.id === page));
  document.querySelectorAll('#mainnav a').forEach(a => a.classList.toggle('active', a.dataset.nav === SECTION_NAV[page]));
  document.querySelectorAll('#rung .mtab').forEach(t => t.classList.toggle('active', t.dataset.mtab === modelTab));
  document.querySelectorAll('#modelnav a').forEach(a => a.classList.toggle('active', a.dataset.mtab === modelTab));
  document.querySelectorAll('#ship .shiptab').forEach(t => t.classList.toggle('active', t.id === STAB_EL[shipTab]));
  document.querySelectorAll('#shipnav a').forEach(a => a.classList.toggle('active', a.dataset.stab === shipTab));
  // the address always reads the canonical way (old addresses and ?run= are rewritten, not stacked)
  if (hash && (location.hash !== '#' + hash || location.search)) history.replaceState(null, '', location.pathname + '#' + hash);
  if (page === 'voyages' || page === 'voyage') loadVoyages();
  if (page === 'discoveries') loadDiscoveries();
  if (page === 'sievesguide') loadSieves();
  if (page === 'ship' && (selected !== wasShip || !runsList)) refresh();
  // charts drawn while hidden have no width; size the ones now showing
  document.querySelectorAll(`#${page} .chart`).forEach(el => { if (el.data && el.offsetParent) Plotly.Plots.resize(el); });
}
function shipHeader(ship, run) {
  const preset = ship ? ship.cls : run && run.preset;
  const cls = preset && ladderData && ladderData.rungs.find(x => x.preset === preset);
  const link = document.getElementById('shipclass');
  link.textContent = cls ? `${cls.preset} · ${cls.name}` : preset || '';
  if (cls) link.href = '#' + modelHash(cls); else link.removeAttribute('href');
  document.getElementById('shipname').textContent = ship ? ship.name : run ? (run.ship || run.name || run.run_id.slice(0, 12)) : `no ship called ${shipKey}`;
  document.getElementById('shipfitout').textContent = ship ? ship.subtitle : '';
  document.getElementById('shiptags').innerHTML = ship ? (ship.archived ? '<span class="pill" title="fitted out before 7 November, 06:40">First Fleet · archived</span>' : '<span class="pill blue">in service</span>')
    + (ship.voyage ? ` <a class="pill accent" href="#/voyages/${esc(ship.voyage)}">${esc(VOYAGE_NAME[ship.voyage] || ship.voyage)}</a>` : '') : '';
  // its sailings: one per seed; the one shown is lit
  const sails = ship ? ship.sailings : run ? [{ run_id: run.run_id, name: run.name, seed: run.seed, status: run.status }] : [];
  document.getElementById('sailings').innerHTML = sails.map(x => `<a class="sailing${run && x.run_id === run.run_id ? ' on' : ''}" href="#${ship ? shipHash(ship.key, x.name, shipTab) : shipHash(x.name, null, shipTab)}"
    title="${esc(x.label || x.name)}">seed <b>${x.seed ?? '–'}</b> ${esc(x.name)} · ${esc((x.status || '').split(':')[0])}${x.ft_en != null ? ` · ${fmt(x.ft_en)}` : ''}</a>`).join('');
}
window.addEventListener('hashchange', () => showTab(location.hash.slice(1), false));
// once the whole script has run (showTab reaches state declared further down); an old ?run= address opens that ship
queueMicrotask(() => {
  const h = location.hash.slice(1);
  showTab(selected && !h.startsWith('/') && !(h in OLD_SHIP) ? '/ships/' + selected : (h || '/classes'), false);
});

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
// the kink rule is fleet.py's (KINK_MIN_RECORDS, KINK_FIRM), read from /api/sieves when it loads
let KINK_MIN = 10, KINK_FIRM = 0.25;
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
  return { step: xs[best.k], before, after, kind, strength, tentative: n < KINK_MIN || strength < KINK_FIRM, L: best.L, R: best.R, k: best.k, xs };
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
function runsTable(runs) {
  const tb = document.querySelector('#runs tbody');
  tb.innerHTML = runs.map(r => `<tr data-run="${r.run_id}" class="${r.run_id === selected ? 'sel' : ''}">
    <td>${esc(r.ship || '')}</td><td>${esc(r.name || '')}</td><td class="mono">${r.run_id.slice(0, 12)}</td><td>${esc(r.preset || '')}</td><td>${r.seed ?? ''}</td>
    <td><span class="badge ${(r.status || '').split(':')[0]}">${esc(r.status || '')}</span></td><td>${big(r.tokens_seen)}</td>
    <td>${fmt(r.wall_minutes, 1)}</td><td>${fmt(r.hole_bpb_mean, 4)}</td><td>${esc(r.started || '')}</td></tr>`).join('');
  tb.querySelectorAll('tr').forEach(tr => tr.onclick = () => goShip(tr.dataset.run));
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
  try { [ladderData, shipsData] = await Promise.all([get('/api/ladder'), get('/api/ships').catch(() => [])]); } catch (e) { return; }
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
  if (page === 'rung' || page === 'ship') showTab(location.hash.slice(1), false);
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
    goShip(c.dataset.run);
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

  // ---- Fleet: every ship of this class, the live ones first and the First Fleet folded below
  const fleet = (shipsData || []).filter(x => x.cls === r.preset).sort((a, b) => String(b.latest).localeCompare(String(a.latest)));
  const shipRow = x => {
    const last = x.sailings[x.sailings.length - 1], st = (last.status || '').split(':')[0];
    return `<tr data-ship="${esc(x.key)}"><td><b>${esc(x.name)}</b></td><td class="s">${esc(x.subtitle)}</td>
      <td data-sort="${x.sailings.length}">${x.sailings.length} <span class="s">(seed${x.sailings.length === 1 ? '' : 's'} ${x.sailings.map(y => y.seed ?? '–').join(', ')})</span></td>
      <td>${x.voyage ? `<a href="#/voyages/${esc(x.voyage)}">${esc(VOYAGE_NAME[x.voyage] || x.voyage)}</a>` : '–'}</td>
      <td><span class="pill ${st}">${esc(st)}</span></td><td>${fmt(x.ft_en_mean)}</td><td>${fmt(x.ft_en_best)}</td>
      <td>${esc(String(x.latest || '–').slice(0, 16).replace('T', ' '))}</td></tr>`;
  };
  const live = fleet.filter(x => !x.archived), old = fleet.filter(x => x.archived);
  document.querySelector('#fleettable tbody').innerHTML = live.length ? live.map(shipRow).join('')
    : `<tr><td colspan="8" class="empty">no ship of this class in service yet${old.length ? '; the First Fleet is below' : ''}</td></tr>`;
  document.getElementById('fleetarchivewrap').hidden = !old.length;
  document.getElementById('fleetarchivesum').textContent = `archived: ${old.length} ship${old.length === 1 ? '' : 's'}, ${old.reduce((n, x) => n + x.sailings.length, 0)} sailings, fitted out before 7 November`;
  document.querySelector('#fleetarchive tbody').innerHTML = old.map(shipRow).join('');

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
  if (modelTab === 'waypoints') { renderWaypoints(r); starsInReach(r); }
  if (modelTab === 'goals') classGoals(r);
  document.querySelectorAll('#rung .chart').forEach(el => { if (el.data && el.offsetParent) Plotly.Plots.resize(el); });
}
// ---- Waypoints: when each run passed each waypoint (server.py api_waypoints). Fetched only while
// the tab is open; the thresholds come from the evaluators, never typed in here.
const TRAIT_LABEL = { fiction: 'fiction', verse: 'verse', first_person: 'first person' };
const firstAt = (sr, ok) => { if (!sr) return undefined; const i = sr.value.findIndex(ok); return i < 0 ? null : sr.step[i]; };
const lastOf = sr => sr && sr.value.length ? sr.value[sr.value.length - 1] : null;
let wpKey = '', wpData = null;
// the hand panel: one run's heads as cards at one eval step; the slider walks the steps and ▶ deals
// them in order, so a card can be watched turning over. Following the latest step unless moved.
const hand = { run: null, idx: null, timer: null };
function handRuns() { return wpData ? wpData.runs.filter(x => x.hands && x.hands.length) : []; }
function drawHand(prevIdx = null) {
  const el = document.getElementById('hand'), pick = document.getElementById('handrun'), slider = document.getElementById('handstep');
  const tools = document.querySelector('#handpanel .handtools'), runs = handRuns();
  if (!runs.length) {
    tools.hidden = true;
    el.innerHTML = `<div class="empty">no run at this size has per-head Nevermore scores yet; they arrive with the queue (every 250 steps) and <span class="mono">scripts/score_nevermore.sh</span></div>`;
    return;
  }
  tools.hidden = false;
  const ids = runs.map(x => x.run_id).join(',');
  if (pick.dataset.ids !== ids) {
    pick.innerHTML = [...runs].reverse().map(x => `<option value="${esc(x.run_id)}">${esc(x.ship || x.name)} · ${esc(x.name)}</option>`).join('');
    pick.dataset.ids = ids;
  }
  if (!runs.some(x => x.run_id === hand.run)) hand.run = (runs.find(x => x.run_id === selected) || runs[runs.length - 1]).run_id;
  pick.value = hand.run;
  const run = runs.find(x => x.run_id === hand.run), hs = run.hands, last = hs.length - 1;
  const i = hand.idx == null ? last : Math.min(hand.idx, last);
  slider.max = last; slider.value = i; slider.disabled = last === 0;
  document.getElementById('handlabel').textContent = `step ${hs[i].step} · reading ${i + 1} of ${hs.length}${hand.idx == null ? ' (latest, live)' : ''}`;
  renderHand(el, hs[i], wpData.nevermore_threshold, prevIdx != null ? hs[prevIdx] : null);
}
function stopDeal() { clearInterval(hand.timer); hand.timer = null; document.getElementById('handplay').textContent = '▶ play'; }
document.getElementById('handrun').onchange = e => { stopDeal(); hand.run = e.target.value; hand.idx = null; drawHand(); };
document.getElementById('handstep').oninput = e => {
  stopDeal();
  const run = handRuns().find(x => x.run_id === hand.run), was = hand.idx ?? run.hands.length - 1, v = +e.target.value;
  hand.idx = v >= run.hands.length - 1 ? null : v;  // back at the end: follow live again
  drawHand(v > was ? was : null);
};
document.getElementById('handplay').onclick = () => {
  if (hand.timer) return stopDeal();
  const run = handRuns().find(x => x.run_id === hand.run); if (!run) return;
  hand.idx = 0; drawHand();
  document.getElementById('handplay').textContent = '❚❚ pause';
  hand.timer = setInterval(() => {
    const last = run.hands.length - 1, was = hand.idx;
    if (was >= last) { hand.idx = null; stopDeal(); return drawHand(); }
    hand.idx = was + 1; drawHand(was);
  }, 900);
};
async function renderWaypoints(r) {
  let d;
  try { d = await get('/api/waypoints?preset=' + encodeURIComponent(r.preset) + '&limit=' + RECENT); } catch (e) { return; }
  const key = JSON.stringify(d);
  if (key === wpKey) return;
  wpKey = key;
  wpData = d;
  drawHand();
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
    <th>real prose best${info('nevermore')}</th><th>random best${info('nevermore')}</th><th>Nevermores (real / random)</th><th>where</th><th>hand</th><th>copy gain${info('copygain')}</th>
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
      <td>${L == null ? '–' : `layer ${Math.round(L)}, head ${Math.round(H)}`}</td><td>${miniHand(x.hands && x.hands[x.hands.length - 1], thr)}</td>
      <td>${fmt(lastOf(nv.natural_copy_gain) ?? lastOf(nv.copy_gain), 2)}</td>
      ${core.map(t => { const q = traitAt(x.traits[t]); return stepCell(q.found) + stepCell(q.learned); }).join('')}
      <td>${fams.length ? `${famFound} of ${fams.length}` : '–'}</td></tr>`;
  }).join('') : `<tr><td colspan="${11 + 2 * core.length}" class="empty">no runs at ${esc(r.preset)} yet</td></tr>`;

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

// a row in a class's fleet or training table, or a voyage's ships, opens that ship
['fleettable', 'fleetarchive', 'trainruns', 'voyageruns'].forEach(id => document.getElementById(id).addEventListener('click', e => {
  const tr = e.target.closest('tr[data-run], tr[data-ship]'); if (!tr || e.target.closest('.info') || e.target.closest('a')) return;
  if (tr.dataset.ship) goShipKey(tr.dataset.ship); else goShip(tr.dataset.run);
}));

// ---- Voyages (server.py api_voyages, from thorp/voyages.py): the list, and one voyage from one
// template. A panel that belongs to one voyage carries data-voyage (book_value's fit).
const VOYAGE_NAME = {};
let voyagesData = null, voyagesKey = '', voyageSeries = null, voyageSeriesKey = '';
const statusPill = st => `<span class="pill ${{ running: 'blue', done: 'good', paused: 'accent' }[st] || ''}">${esc(st || '')}</span>`;
const classOf = preset => ladderData && ladderData.rungs.find(x => x.preset === preset);
const classLink = preset => { const c = classOf(preset); return c ? `<a href="#${modelHash(c)}">${esc(c.preset)} · ${esc(c.name)}</a>` : esc(preset || '–'); };
// the stars a voyage's runs have lit so far: the soonest step for each, or the best score yet
function starHeadline(v) {
  return Object.values(v.runs.reduce((acc, r) => {
    r.stars.forEach(x => {
      const a = acc[x.star] || (acc[x.star] = { star: x.star, lit: null, ship: null, shared: null, sship: null, best: null });
      if (x.steps_to_lit != null && (a.lit == null || x.steps_to_lit < a.lit)) { a.lit = x.steps_to_lit; a.ship = r.ship_name || r.ship || r.name; }
      if (x.shared_steps_to_lit != null && (a.shared == null || x.shared_steps_to_lit < a.shared)) { a.shared = x.shared_steps_to_lit; a.sship = r.ship_name || r.ship || r.name; }
      if (x.best != null && (a.best == null || x.best > a.best)) a.best = x.best;
    });
    return acc;
  }, {})).filter(a => a.best != null).map(a => { const n = STAR_LABEL[a.star] || a.star;
    return a.lit != null ? `${n} lit at step ${a.lit} (${a.ship})` : a.shared != null ? `${n} lit shared at step ${a.shared} (${a.sship}), no single head yet (best ${fmt(a.best)})` : `${n} not lit yet, best ${fmt(a.best)}`; }).join('; ');
}
const STAR_LABEL = { previous_word: 'the Previous Word', duplicate_word: 'the Duplicate Word', nevermore: 'Nevermore' };
async function loadVoyages() {
  let d;
  try { d = await get('/api/voyages'); } catch (e) { return; }
  d.forEach(v => { VOYAGE_NAME[v.key] = v.name; });
  const key = JSON.stringify(d) + '|' + voyageKey + '|' + !!ladderData;
  if (key === voyagesKey) return;
  voyagesKey = key; voyagesData = d;
  document.getElementById('voyagecards').innerHTML = d.map(v => {
    const valid = v.runs.filter(r => !r.set_aside).length;
    const headline = v.learned || starHeadline(v) || 'nothing found yet';
    return `<a class="card" href="#/voyages/${esc(v.key)}">
      <div class="top"><span class="preset">${esc(v.name)}</span>${statusPill(v.status)}</div>
      <div class="goal">${esc(v.goal)}</div>
      <div class="ov">${esc(headline)}</div>
      <div class="foot"><span>${esc(v.fleet || '')} · ${esc(v.preset || '')}</span><span>${valid} of ${v.stop.max_runs} runs</span></div>
      <div class="foot"><span>${(v.ships || []).length} ship${(v.ships || []).length === 1 ? '' : 's'}${v.stars && v.stars.length ? ` · bound for ${esc(v.stars.map(k => STAR_LABEL[k] || k).join(', '))}` : ''}</span></div></a>`;
  }).join('') || '<div class="empty">no voyages yet</div>';
  if (page === 'voyage') renderVoyage();
}
function renderVoyage() {
  const v = voyagesData && voyagesData.find(x => x.key === voyageKey);
  if (!v) { document.getElementById('voyagetitle').textContent = voyagesData ? `no voyage called ${voyageKey}` : 'loading…'; return; }
  document.querySelectorAll('#voyage [data-voyage]').forEach(el => { el.hidden = el.dataset.voyage !== v.key; });
  document.getElementById('voyagetitle').textContent = v.name;
  document.getElementById('voyagestatus').innerHTML = statusPill(v.status);
  document.getElementById('voyagegoal').textContent = v.goal;
  const valid = v.runs.filter(r => !r.set_aside);
  document.getElementById('voyageover').innerHTML = [
    ['fleet', esc(v.fleet || '–')], ['class', classLink(v.preset)],
    ['bound for', esc((v.stars || []).map(k => STAR_LABEL[k] || k).join(', ') || '–')], ['ships', String((v.ships || []).length)],
    ['runs', `${valid.length} of ${v.stop.max_runs}${v.runs.length > valid.length ? ` (${v.runs.length - valid.length} set aside)` : ''}`],
    ['stop rule', esc(v.stop.about || '')], ['status', esc(v.status)],
  ].map(([k, val]) => `<div><div class="k">${k}</div><div>${val}</div></div>`).join('');
  const learned = v.learned || starHeadline(v);
  document.getElementById('voyagelearned').hidden = !learned;
  document.getElementById('voyagelearnedtext').textContent = learned;
  // the fit (book_value): what a pure shelf of each kind is worth, with its interval
  if (v.fit && v.fit.coef) {
    const rows = Object.entries(v.fit.coef);
    document.getElementById('fitr2').textContent = `cross-validated R² ${fmt(v.fit.cv_r2, 2)} over ${v.fit.runs} runs`;
    document.querySelector('#fittable tbody').innerHTML = rows.map(([k, [e, lo, hi]]) => `<tr><td>${esc(k)}</td><td>${fmt(e)}</td><td>${fmt(lo)}</td><td>${fmt(hi)}</td></tr>`).join('');
    const pure = rows.filter(([k]) => k.startsWith('pure ')).sort((a, b) => b[1][0] - a[1][0]);
    plot('fitchart', [{ type: 'scatter', mode: 'markers', x: pure.map(p => p[1][0]), y: pure.map(p => p[0].replace('pure ', '')),
      error_x: { type: 'data', symmetric: false, array: pure.map(p => p[1][2] - p[1][0]), arrayminus: pure.map(p => p[1][0] - p[1][1]), color: C.muted },
      marker: { size: 9, color: C.accent }, hovertemplate: '%{y}: %{x:.3f}<extra></extra>' }],
      layout({ xaxis: { title: 'Forgotten Tomes bits per byte (lower is better)', gridcolor: C.line }, yaxis: { automargin: true }, margin: { l: 140 } }));
  }
  // the ships it fitted out, each with its sailings and, per star, how many lit it and how soon
  const starKeys = v.stars && v.stars.length ? v.stars : [...new Set(v.runs.flatMap(r => r.stars.map(x => x.star)))];
  const vships = v.ships && v.ships.length && typeof v.ships[0] === 'object' ? v.ships : [];
  document.querySelector('#voyageruns thead').innerHTML = `<tr><th>ship</th><th>fitout</th><th>sailings</th><th>Forgotten Tomes (mean)${info('ft')}</th>
    ${starKeys.map(k => `<th>${esc(STAR_LABEL[k] || k)}</th>`).join('')}</tr>`;
  document.querySelector('#voyageruns tbody').innerHTML = vships.length ? vships.map(x => `<tr data-ship="${esc(x.key)}">
    <td><b>${esc(x.name)}</b></td><td class="s">${esc(x.subtitle)}</td><td data-sort="${x.sailings.length}">${x.sailings.length}</td><td>${fmt(x.ft_en_mean)}</td>
    ${starKeys.map(k => { const st = (x.stars || {})[k] || {};
      return st.lit ? `<td data-sort="${st.soonest}">lit by ${st.lit} of ${x.sailings.length} · soonest step ${st.soonest}</td>`
        : st.lit_shared ? `<td data-sort="${st.soonest_shared}" title="the best layer's two strongest heads together">lit shared by ${st.lit_shared} of ${x.sailings.length} · soonest step ${st.soonest_shared}</td>`
        : st.best != null ? `<td data-sort="" class="s" title="not lit yet; the best so far">best ${fmt(st.best)}</td>` : '<td>–</td>'; }).join('')}</tr>`).join('')
    : `<tr><td colspan="${4 + starKeys.length}" class="empty">no ships have sailed on this voyage yet</td></tr>`;
  // the Forgotten Tomes score run by run, one colour per value of the setting that varies most
  const scored = v.runs.map((r, i) => ({ r, i: i + 1 })).filter(p => p.r.ft_en != null && !p.r.set_aside);
  if (!scored.length) empty('voyageft', 'no run on this voyage has a Forgotten Tomes score yet');
  else {
    const fields = ['passes', 'vocab', 'lr', 'recipe'];
    const by = fields.map(f => [f, new Set(scored.map(p => (p.r.settings || {})[f])).size]).sort((a, b) => b[1] - a[1])[0][0];
    const groups = [...new Set(scored.map(p => (p.r.settings || {})[by]))];
    plot('voyageft', groups.map((g, gi) => { const pts = scored.filter(p => (p.r.settings || {})[by] === g);
      return { type: 'scatter', mode: 'markers', name: `${by} ${String(g).replace('lists/', '').replace('.csv', '')}`, x: pts.map(p => p.i), y: pts.map(p => p.r.ft_en),
        text: pts.map(p => p.r.ship || p.r.name), hovertemplate: '%{text}: %{y:.3f}<extra></extra>', marker: { size: 9, color: PALETTE[gi % PALETTE.length] } }; }),
      layout({ xaxis: { title: 'run, in the order they sailed', gridcolor: C.line }, yaxis: { title: 'bits per byte', gridcolor: C.line }, legend: { orientation: 'h', y: 1.1 } }));
  }
  document.querySelector('#voyageoutcomes tbody').innerHTML = v.outcomes.map(o => `<tr><td>${esc(o.about)}</td><td class="mono">${esc(o.metric)}</td><td>${esc(o.better)}</td></tr>`).join('');
  document.querySelector('#voyagelevers tbody').innerHTML = v.levers.map(l => `<tr><td class="mono">${esc(l.key)}</td>
    <td>${l.fixed ? 'fixed' : l.choices && l.choices.length ? esc(l.choices.join(', ')) : `${l.low ?? '–'} to ${l.high ?? '–'}`}</td><td>${esc(l.about || '')}</td></tr>`).join('');
  voyageStars(v);
  journeyPanel(v);
}
// ---- the journey through the layers (lib/journey.js): one or two sailings of the voyage, read up
// their stack at one step; the slider follows the latest reading unless moved
const journey = { a: null, b: null, idx: null, cache: {} };
async function runMetrics(id) {
  const c = journey.cache[id];
  if (c && Date.now() - c.t < 15000) return c.m;
  const m = await get('/api/metrics?run=' + encodeURIComponent(id));
  journey.cache[id] = { m, t: Date.now() };
  return m;
}
const pushKinks = m => Object.fromEntries(Object.entries(kinksOf(m, 'grad_norm/')).map(([k, v]) => [groupOf(k, 'grad_norm/'), v]));
// the steps a sailing can be read at: its soundings if it has them, else its sieves
const journeySteps = m => { const s = soundingSteps(m); return s.length ? s : (m['grad_norm/layer_0'] ? m['grad_norm/layer_0'][0] : []); };
async function journeyPanel(v) {
  if (!sieveDef) { try { sieveDef = await get('/api/sieves'); } catch (e) { return; } }
  const runs = v.runs.filter(r => !r.set_aside), selA = document.getElementById('journeyA'), selB = document.getElementById('journeyB');
  if (!runs.length) { document.getElementById('journeyviewA').innerHTML = '<div class="empty">no sailings on this voyage yet</div>'; return; }
  const opts = runs.map(r => r.run_id).join(',');
  const label = r => `${r.ship_name || r.ship || r.name} · ${r.name}`;
  if (selA.dataset.opts !== opts + v.key) {
    const list = [...runs].reverse().map(r => `<option value="${esc(r.run_id)}">${esc(label(r))}</option>`).join('');
    selA.innerHTML = list; selB.innerHTML = '<option value="">none</option>' + list; selA.dataset.opts = opts + v.key;
    // a voyage with transplants opens on a receiver beside its control (same seed); else the running sailing
    const tp = id => voyageSeries && (voyageSeries.runs.find(x => x.run_id === id) || {}).transplant;
    const recv = [...runs].reverse().find(r => tp(r.run_id));
    if (!runs.some(r => r.run_id === journey.a)) journey.a = (recv || [...runs].reverse().find(r => r.status === 'running') || runs[runs.length - 1]).run_id;
    if (!runs.some(r => r.run_id === journey.b)) {
      const seed = recv && (recv.name.match(/-s(\d+)$/) || [])[1];
      const ctl = recv && runs.find(r => !tp(r.run_id) && /control/.test(r.name) && (!seed || r.name.endsWith('-s' + seed)));
      journey.b = ctl ? ctl.run_id : null;
    }
  }
  selA.value = journey.a; selB.value = journey.b || '';
  let mA, mB = null;
  try { mA = await runMetrics(journey.a); if (journey.b) mB = await runMetrics(journey.b); } catch (e) { return; }
  const steps = journeySteps(mA), slider = document.getElementById('journeystep');
  const last = Math.max(0, steps.length - 1), i = journey.idx == null ? last : Math.min(journey.idx, last), step = steps[i] ?? 0;
  slider.max = last; slider.value = i; slider.disabled = steps.length < 2;
  document.getElementById('journeylabel').textContent = steps.length ? `step ${step} · reading ${i + 1} of ${steps.length}${journey.idx == null ? ' (latest, live)' : ''}` : 'no readings yet';
  const modules = new Set([...document.querySelectorAll('#journeymods input:checked')].map(x => x.value));
  const runOf = id => runs.find(r => r.run_id === id);
  const tpOf = id => voyageSeries && (voyageSeries.runs.find(x => x.run_id === id) || {}).transplant;
  drawJourney(document.getElementById('journeyviewA'), mA, step, sieveDef, { modules, kinks: pushKinks(mA), title: label(runOf(journey.a)), transplant: tpOf(journey.a) });
  const vb = document.getElementById('journeyviewB');
  document.querySelector('#journeypanel .journeys').classList.toggle('two', !!mB);
  if (mB) drawJourney(vb, mB, step, sieveDef, { modules, kinks: pushKinks(mB), title: label(runOf(journey.b)) + ' (at the same step)', transplant: tpOf(journey.b) });
  else vb.innerHTML = '';
}
const currentVoyage = () => voyagesData && voyagesData.find(x => x.key === voyageKey);
document.getElementById('journeyA').onchange = e => { journey.a = e.target.value; journey.idx = null; const v = currentVoyage(); if (v) journeyPanel(v); };
document.getElementById('journeyB').onchange = e => { journey.b = e.target.value || null; const v = currentVoyage(); if (v) journeyPanel(v); };
document.getElementById('journeystep').oninput = e => { const v = currentVoyage(); if (!v) return; const n = +e.target.value; journey.idx = n >= +e.target.max ? null : n; journeyPanel(v); };
document.querySelectorAll('#journeymods input').forEach(x => x.onchange = () => { const v = currentVoyage(); if (v) journeyPanel(v); });

// first light: each star's score against step for every run of the voyage, the threshold dotted
async function voyageStars(v) {
  let d;
  try { d = await get('/api/voyage?key=' + encodeURIComponent(v.key)); } catch (e) { return; }
  const sel = document.getElementById('voyagestar');
  voyageSeries = d;
  const keys = Object.keys(d.stars), lit = k => d.runs.some(r => r.series[k] && r.series[k].step.length);
  if (sel.dataset.voyage !== v.key) {
    const own = (d.voyage_stars || []).filter(k => d.stars[k]);
    sel.innerHTML = [...own, ...keys.filter(k => !own.includes(k))].map(k => `<option value="${k}">${esc(d.stars[k].name)}</option>`).join('');
    sel.value = own.find(lit) || own[0] || keys.find(lit) || keys[0]; sel.dataset.voyage = v.key;
  }
  const k = sel.value, star = d.stars[k], key = JSON.stringify(d.runs.map(r => r.series[k])) + k;
  if (key === voyageSeriesKey) return;
  voyageSeriesKey = key;
  const rs = d.runs.filter(r => r.series[k] && r.series[k].step.length);
  if (!rs.length) return empty('voyagestars', `no run on this voyage has a reading for ${esc(star.name)} yet`);
  // per run: the best single head (solid) and, where the star can be shared, the best layer's two
  // strongest heads together (dashed); either line crossing the dotted threshold is first light
  const traces = rs.flatMap((r, i) => {
    // a donor (the run heads were taken from) is dotted; a receiver says so in its name
    const col = PALETTE[i % PALETTE.length], sr = r.series[k];
    const name = `${r.ship || r.name}${r.role === 'donor' ? ' (donor)' : r.role === 'receiver' ? ' (received heads)' : ''}`;
    const t = [{ type: 'scatter', mode: 'lines', name: `${name} · one head`, legendgroup: name, x: sr.step, y: sr.value, line: { color: col, width: 1.8, dash: r.role === 'donor' ? 'dot' : 'solid' } }];
    if (sr.shared_step && sr.shared_step.length) t.push({ type: 'scatter', mode: 'lines', name: `${name} · shared`, legendgroup: name,
      x: sr.shared_step, y: sr.shared_value, line: { color: col, width: 1.5, dash: 'dash' } });
    return t;
  });
  plot('voyagestars', traces,
    layout({ xaxis: { title: 'step', gridcolor: C.line }, legend: { orientation: 'h', y: 1.12 },
      yaxis: { title: `${star.name} score`, gridcolor: C.line, range: [0, Math.max(1, ...traces.flatMap(t => t.y))] },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: star.threshold, y1: star.threshold, line: { color: C.accent, dash: 'dot' } }] }));
}
document.getElementById('voyagestar').onchange = () => { voyageSeriesKey = ''; const v = voyagesData && voyagesData.find(x => x.key === voyageKey); if (v) voyageStars(v); };

// ---- Sieves (#/sieves): the three sieves from fleet.SIEVES, one sailing's heatmaps, and when each
// layer's heading settled beside the stars lit in it
let sieveDef = null, sieveRun = null, sieveKey = '';
const SETTLE_AT = 0.8, SETTLE_RECORDS = 3;
function sieveHeat(id, m, prefix, kinksByGroup, { log = true, diverging = false, msg = 'no readings for this sieve on this sailing' } = {}) {
  const keys = topKeys(m, prefix);
  if (!keys.length) return empty(id, msg);
  const x = m[keys[0]][0], y = keys.map(k => groupLabel(groupOf(k, prefix)));
  const z = keys.map(k => m[k][1].map(v => log ? log10(v) : v));
  const data = [{ type: 'heatmap', x, y, z, hovertemplate: `step %{x}<br>%{y}<br>${log ? 'log10 ' : ''}%{z:.2f}<extra></extra>`,
    ...(diverging ? { colorscale: [[0, C.bad], [0.5, tok('panel')], [1, C.good]], zmin: -1, zmax: 1, zmid: 0 } : { colorscale: 'Viridis' }),
    colorbar: { title: log ? 'log10' : 'cosine', thickness: 10 } }];
  const kx = [], ky = [], kt = [];
  keys.forEach((k, i) => { const kk = kinksByGroup[groupOf(k, prefix)]; if (kk) { kx.push(kk.step); ky.push(y[i]); kt.push(`push kink at ${kk.step}${kk.tentative ? ' (tentative)' : ''}`); } });
  if (kx.length) data.push({ type: 'scatter', x: kx, y: ky, text: kt, mode: 'markers', marker: { symbol: 'diamond', size: 9, color: '#fff', line: { color: '#000', width: 1 } },
    hovertemplate: '%{y}<br>%{text}<extra></extra>', showlegend: false });
  plot(id, data, layout({ margin: { l: 80, r: 10, t: 10, b: 36 }, xaxis: { title: 'step', gridcolor: C.line } }));
}
// the first step a value is reached, and the value of a companion series (the layer) at that step
const firstReach = (m, metric, thr) => { const sr = metric && m[metric]; if (!sr) return null; const i = sr[1].findIndex(v => v >= thr); return i < 0 ? null : sr[0][i]; };
const valueAt = (m, metric, step) => { const sr = metric && m[metric]; if (!sr) return null; const i = sr[0].indexOf(step); return i < 0 ? null : sr[1][i]; };
async function loadSieves() {
  if (!sieveDef) {
    try { sieveDef = await get('/api/sieves'); } catch (e) { return; }
    KINK_MIN = sieveDef.kink_min_records; KINK_FIRM = sieveDef.kink_firm;
    document.getElementById('kinkrule').textContent = `${KINK_MIN} records when the two lines remove at least ${Math.round(KINK_FIRM * 100)}% of one line's error`;
    document.getElementById('sievecards').innerHTML = sieveDef.sieves.map(v => `<div class="card"><div class="top"><span class="preset">${esc(v.name)}</span>
      <span class="mono">${esc(v.prefix)}</span></div><div class="ov">${esc(v.about)}</div></div>`).join('');
  }
  const runs = (runsList || (runsList = await get('/api/runs').catch(() => []))).filter(r => r.name && !r.name.startsWith('smoke'));
  if (!runs.length) return;
  const pick = document.getElementById('sievepick');
  const label = r => { const lr = ladderRun(r.run_id); return `${(lr && lr.ship_name) || r.ship || r.name} · ${r.name} (${r.preset || '–'})`; };
  const opts = runs.map(r => r.run_id).join(',');
  if (pick.dataset.opts !== opts) {
    pick.innerHTML = [...runs].reverse().map(r => `<option value="${esc(r.name)}">${esc(label(r))}</option>`).join('');
    pick.dataset.opts = opts;
  }
  const run = runs.find(r => r.name === sieveRun || r.run_id === sieveRun)
    || [...runs].reverse().find(r => r.status === 'running') || runs[runs.length - 1];
  pick.value = run.name;
  const lr = ladderRun(run.run_id), sh = lr && lr.ship_key && shipsData && shipsData.find(x => x.key === lr.ship_key);
  document.getElementById('sievenote').innerHTML = `${sh ? `<a href="#${shipHash(sh.key, run.name, 'sieves')}">${esc(sh.name)}</a> · ${esc(sh.subtitle)}` : esc(run.ship || run.name)} · ${esc((run.status || '').split(':')[0])}`;
  let m;
  try { m = await get('/api/metrics?run=' + encodeURIComponent(run.run_id)); } catch (e) { return; }
  const key = run.run_id + '|' + Object.keys(m).filter(k => /^(grad_norm|update_ratio|heading|stars|nevermore)\//.test(k)).map(k => k + m[k][0].length).join(',');
  if (key === sieveKey) return;
  sieveKey = key;
  const pk = kinksOf(m, 'grad_norm/'), byGroup = {};
  for (const [k, v] of Object.entries(pk)) byGroup[groupOf(k, 'grad_norm/')] = v;
  sieveHeat('sieve-push', m, 'grad_norm/', byGroup);
  sieveHeat('sieve-move', m, 'update_ratio/', byGroup);
  sieveHeat('sieve-heading', m, 'heading/', byGroup, { log: false, diverging: true,
    msg: run.status === 'running' && !topKeys(m, 'heading/').length ? 'the heading sieve starts with the next ship to sail; this sailing set out before it was fitted' : 'this sailing has no heading readings: the heading sieve started with ships sailing from 08:00 on 7 November' });
  // settled: per layer, the first step the heading holds SETTLE_AT for SETTLE_RECORDS records running
  const layers = layerOnly(m, 'grad_norm/').map(k => groupOf(k, 'grad_norm/'));
  const lit = sieveDef.stars.flatMap(st => {
    const out = [], a = firstReach(m, st.metric, st.threshold), b = firstReach(m, st.shared_metric, st.threshold);
    if (a != null) out.push({ name: st.name, step: a, layer: valueAt(m, st.layer, a), how: 'one head' });
    if (b != null) out.push({ name: st.name, step: b, layer: valueAt(m, st.shared_layer, b), how: 'shared' });
    return out;
  });
  document.querySelector('#settledtable tbody').innerHTML = layers.length ? [...layers].reverse().map(g => {
    const sr = m['heading/' + g], i = groupOrder(g);
    let settled = null;
    if (sr) for (let j = 0; j + SETTLE_RECORDS <= sr[1].length; j++) if (sr[1].slice(j, j + SETTLE_RECORDS).every(v => v >= SETTLE_AT)) { settled = sr[0][j]; break; }
    const here = lit.filter(x => x.layer != null && Math.round(x.layer) === i);
    const kk = byGroup[g];
    return `<tr><td>${esc(groupLabel(g))}</td><td data-sort="${settled ?? ''}">${sr ? (settled != null ? `step ${settled}` : 'not yet') : '–'}</td>
      <td>${sr ? fmt(sr[1][sr[1].length - 1], 2) : '–'}</td><td data-sort="${kk ? kk.step : ''}">${kk ? `step ${kk.step}${kk.tentative ? ' (tentative)' : ''}` : '–'}</td>
      <td>${here.length ? here.map(x => `${esc(x.name)} at step ${x.step} (${x.how})`).join('; ') : '–'}</td></tr>`;
  }).join('') : '<tr><td colspan="5" class="empty">no sieve readings on this sailing yet</td></tr>';
}
document.getElementById('sievepick').onchange = e => { location.hash = '#/sieves/' + encodeURIComponent(e.target.value); };

// ---- Discoveries (server.py api_discoveries): the stars and the traits, across every ship
let discKey = '';
// a discovery names the ship, and links to the sailing that made it
const shipLink = x => `<a href="#${x.ship_key ? shipHash(x.ship_key, x.name) : shipHash(x.name)}">${esc(x.ship_name || x.ship || x.name)}</a>`;
const TRAIT_NAME = t => t.startsWith('family/') ? `${t.slice(7)} (language family)` : ({ fiction: 'Fiction', verse: 'Verse', first_person: 'First person' }[t] || t);
async function loadDiscoveries() {
  let d;
  try { d = await get('/api/discoveries'); } catch (e) { return; }
  const key = JSON.stringify(d) + !!ladderData;
  if (key === discKey) return;
  discKey = key;
  const byName = Object.fromEntries(d.stars.map(s => [s.key, s.name]));
  document.getElementById('starcards').innerHTML = d.stars.map(s => {
    const lit = s.ships.filter(x => x.steps_to_lit != null).sort((a, b) => a.steps_to_lit - b.steps_to_lit);
    const shared = s.ships.filter(x => x.shared_steps_to_lit != null).sort((a, b) => a.shared_steps_to_lit - b.shared_steps_to_lit);
    const best = [...s.ships].sort((a, b) => (b.best ?? -1) - (a.best ?? -1))[0];
    const first = lit[0], firstShared = shared[0];
    const state = lit.length ? ['good', 'lit'] : shared.length ? ['accent', 'lit shared'] : ['', 'not lit yet'];
    return `<div class="card${lit.length ? ' lit' : ''}">
      <div class="top"><span class="preset">${esc(s.name)}</span><span class="pill ${state[0]}" title="lit: one head at the threshold; lit shared: the best layer's two strongest heads together">${state[1]}</span></div>
      <div class="job">level ${s.level}${s.rests_on.length ? ` · rests on ${esc(s.rests_on.map(k => byName[k] || k).join(', '))}` : ''} · lit at ${s.threshold}</div>
      <div class="ov">${esc(s.about)}</div>
      <div class="foot"><span>${first ? `first lit by ${shipLink(first)} at step ${first.steps_to_lit}` : best && best.best != null ? `nearest: ${shipLink(best)} at ${fmt(best.best)}` : 'no readings yet'}</span></div>
      ${firstShared ? `<div class="foot"><span>first lit shared by ${shipLink(firstShared)} at step ${firstShared.shared_steps_to_lit} (two heads together)</span></div>` : ''}
      <div class="foot"><span>lit on ${lit.length}${shared.length ? `, lit shared on ${shared.length},` : ''} of ${s.ships.length} sailings measured</span></div></div>`;
  }).join('');
  // the star chart: every known kind of head; the measured ones carry their state
  discHeads = d.known_heads || []; discStars = d.stars; discTricks = d.tricks || []; discData = d; drawHeads(); drawDiscoveryView();
  document.querySelector('#traittable thead').innerHTML = `<tr><th>trait</th><th>ships measured</th><th>found by</th><th>first found</th><th>learned by</th><th>first learned</th><th>best held-out AUC</th></tr>`;
  const firstOf = (ships, k) => ships.filter(x => x[k] != null).sort((a, b) => a[k] - b[k])[0];
  document.querySelector('#traittable tbody').innerHTML = d.traits.map(t => {
    const f = firstOf(t.ships, 'found_at'), l = firstOf(t.ships, 'learned_at'), best = [...t.ships].sort((a, b) => (b.best ?? -1) - (a.best ?? -1))[0];
    const who = (x, k) => x ? `${shipLink(x)} (${esc(x.preset || '')}) at step ${x[k]}` : 'not yet';
    return `<tr${(l || f) ? ` data-run="${esc((l || f).run_id)}" tabindex="0"` : ''}><td><b>${esc(TRAIT_NAME(t.key))}</b></td><td>${t.ships.length}</td>
      <td>${t.ships.filter(x => x.found_at != null).length}</td><td>${who(f, 'found_at')}</td>
      <td>${t.ships.filter(x => x.learned_at != null).length}</td><td>${who(l, 'learned_at')}</td><td>${best && best.best != null ? `${fmt(best.best)} (${esc(best.ship_name || best.ship || best.name)})` : '–'}</td></tr>`;
  }).join('') || '<tr><td colspan="7" class="empty">no ship has trait probes yet</td></tr>';
}
let discHeads = [], discStars = [], discTricks = [], discData = null;
// a kind of head's state in Thorp: not measured, measured without readings, lit, lit shared or best so far
function headState(h) {
  if (!h.star) return `<td data-sort="9" class="s" title="${esc(h.measure)}">not measured yet · <i>${esc(h.measure)}</i>${trickNote(h)}</td>`;
  const st = discStars.find(x => x.key === h.star);
  if (!st) return '<td data-sort="5">measured</td>';
  if (!st.ships.length) return `<td data-sort="3"><span class="pill">measured</span> a star: ${esc(st.name)} · readings start with the next ship to sail · threshold ${st.threshold}</td>`;
  const lit = st.ships.filter(x => x.steps_to_lit != null), sh = st.ships.filter(x => x.shared_steps_to_lit != null);
  const best = Math.max(-1, ...st.ships.map(x => x.best ?? -1));
  const pill = lit.length ? '<span class="pill good">lit</span>' : sh.length ? '<span class="pill accent">lit shared</span>' : '<span class="pill">not lit yet</span>';
  return `<td data-sort="${lit.length ? 0 : sh.length ? 1 : 2}">${pill} a star: ${esc(st.name)} · ${lit.length ? `lit on ${lit.length}` : sh.length ? `lit shared on ${sh.length}` : `best ${fmt(best)}`} of ${st.ships.length} sailings · threshold ${st.threshold}${trickNote(h)}</td>`;
}
// Thorp's progress on a trick: the smallest class that performed it, else the best reading so far
function trickProgress(kt) {
  const t = kt.fleet && discTricks.find(x => x.key === kt.fleet);
  if (!kt.fleet) return { cell: '<td data-sort="9" class="s">not measured yet</td>', state: 'not measured yet', cls: '' };
  if (!t || !t.ships.length) return { cell: '<td data-sort="8" class="s">measured · readings start with the next ship to sail</td>', state: 'measured, no readings yet', cls: '' };
  const done = t.ships.filter(x => x.performed_at != null).sort((a, b) => classRank(a.preset) - classRank(b.preset) || a.performed_at - b.performed_at);
  if (done.length) { const x = done[0]; return { cell: `<td data-sort="${classRank(x.preset)}"><span class="pill good">performed</span> at ${classLink(x.preset)} by ${shipLink(x)}, step ${x.performed_at}</td>`, state: 'performed', cls: 'good' }; }
  const best = [...t.ships].sort((a, b) => b.best - a.best)[0];
  return { cell: `<td data-sort="7"><span class="pill">not yet</span> best ${fmt(best.best)} of ${t.threshold} (${classLink(best.preset)})</td>`, state: 'not performed yet', cls: '' };
}
const ladderParams = p => { const r = ladderData && ladderData.rungs.find(x => x.preset === p); return r ? r.total : null; };
function drawTricks() {
  const sel = document.getElementById('trickfamily'), bandSel = document.getElementById('trickband'), kts = discData.known_tricks || [];
  const wps = discData.waypoints || [], wpRank = k => wps.findIndex(w => w.key === k), wpName = k => (wps.find(w => w.key === k) || {}).name || k;
  if (sel.options.length !== wps.length + 1) sel.innerHTML = '<option value="">all</option>' + wps.map(w => `<option value="${esc(w.key)}">${esc(w.name)}</option>`).join('');
  // the route: the seven waypoints in order, each with its gate tricks
  document.getElementById('trickroute').innerHTML = wps.map((w, i) => {
    const mine = kts.filter(t => t.waypoint === w.key), gates = mine.filter(t => t.gate);
    return `<div class="step"><div class="n">${i + 1}</div><div class="nm">${esc(w.name)}</div><div class="ab">${esc(w.about)}</div>
      <div class="gt">${gates.map(t => `<a href="#/discoveries/${esc(t.key)}">◆ ${esc(t.name)}</a>`).join('')}</div><div class="ct">${mine.length} tricks</div></div>`;
  }).join('<div class="arrow">→</div>');
  // the size bands present, smallest first
  const bands = [...new Map(kts.map(t => [t.field_band_rank, t.field_band])).entries()].sort((a, b) => a[0] - b[0]);
  if (bandSel.options.length !== bands.length + 1) { const was = bandSel.value; bandSel.innerHTML = '<option value="">any size</option>' + bands.map(([r, b]) => `<option value="${r}">${esc(b)}</option>`).join(''); bandSel.value = was; }
  const rows = kts.filter(t => (!sel.value || t.waypoint === sel.value) && (bandSel.value === '' || String(t.field_band_rank) === bandSel.value))
    .sort((a, b) => wpRank(a.waypoint) - wpRank(b.waypoint) || a.field_band_rank - b.field_band_rank);
  const heads = Object.fromEntries((discData.known_heads || []).map(h => [h.key, h.name]));
  document.getElementById('trickcount').textContent = `${rows.length} tricks · ${rows.filter(t => t.fleet).length} measured by Thorp`;
  document.querySelector('#tricktable tbody').innerHTML = rows.map(t => `<tr data-trick="${esc(t.key)}" tabindex="0"${t.fleet ? ' class="measured"' : ''}>
    <td data-sort="${wpRank(t.waypoint)}">${esc(wpName(t.waypoint))}</td><td><b>${t.gate ? '◆ ' : ''}${esc(t.name)}</b>${t.taught ? ' <span class="s">(taught)</span>' : ''}</td><td>${esc(t.does)}</td><td data-sort="${t.field_params}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td><td class="s">${esc(t.sure)}</td>
    <td>${t.stars.length ? esc(t.stars.map(k => heads[k] || k).join(', ')) : '<span class="s">none charted yet</span>'}</td>
    ${trickProgress(t).cell}<td data-sort="${t.target_class ? classRank(t.target_class) : 99}">${t.target_class ? classLink(t.target_class) : t.taught ? '<span class="s">a reference: taught, not read</span>' : '<span class="s">beyond the ladder</span>'}</td></tr>`).join('');
}
document.getElementById('trickfamily').onchange = () => discData && drawTricks();
document.getElementById('trickband').onchange = () => discData && drawTricks();
document.getElementById('tricktable').addEventListener('click', e => { const tr = e.target.closest('tr[data-trick]'); if (tr && !e.target.closest('a')) location.hash = '#/discoveries/' + tr.dataset.trick; });
let trickChartKey = '';
async function drawTrickPage() {
  const t = (discData.known_tricks || []).find(x => x.key === discTrick);
  if (!t) { document.getElementById('tricktitle').textContent = `no trick called ${discTrick}`; return; }
  const p = trickProgress(t), ft = t.fleet && discTricks.find(x => x.key === t.fleet);
  document.getElementById('tricktitle').textContent = t.name;
  document.getElementById('trickstate').innerHTML = `<span class="pill ${p.cls}">${esc(p.state)}</span>`;
  document.getElementById('trickdoes').textContent = t.does;
  const tgt = t.target_class && classOf(t.target_class);
  const wp = (discData.waypoints || []).find(w => w.key === t.waypoint), tname = Object.fromEntries((discData.known_tricks || []).map(x => [x.key, x.name]));
  document.getElementById('trickover').innerHTML = [
    ['waypoint', `${esc(wp ? wp.name : t.waypoint)}${t.gate ? ' · <b>◆ a gate</b>: performed before a ship moves on' : ' · a milestone'}`],
    ['rests on', t.rests_on.length ? t.rests_on.map(k => `<a href="#/discoveries/${esc(k)}">${esc(tname[k] || k)}</a>`).join(', ') : '–'],
    ['the field shows it at', `<span class="sizeband">${esc(t.field_band)}</span> parameters · ${esc(t.field_at)} <span class="s">(${esc(t.sure)})</span>`], ['in', esc(t.field_models)], ['first shown by', `<span class="s">${esc(t.source)}</span>`],
    ["Thorp's goal class", t.target_class ? `${classLink(t.target_class)}${tgt ? ` · ${big(tgt.total)} parameters` : ''}` : t.taught ? 'none: the field shows it only when taught the task' : 'beyond the ladder: a horizon'],
    ['how Thorp measures it', ft ? `<span class="mono">${esc(ft.metric)}</span>, performed at ${ft.threshold}` : `not yet: ${esc(t.measure)}`],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  // the stars needed
  const hs = t.stars.map(k => (discData.known_heads || []).find(h => h.key === k)).filter(Boolean), byKey = Object.fromEntries((discData.known_heads || []).map(h => [h.key, h.name]));
  document.querySelector('#trickstars tbody').innerHTML = hs.length ? hs.map(h => `<tr><td><b>${esc(h.name)}</b></td><td>${esc(h.does)}</td>
    <td>${h.rests_on.length ? esc(h.rests_on.map(k => byKey[k] || k).join(', ')) : '–'}</td>
    <td data-sort="${classRank(h.expected_from)}">${h.expected_from ? classLink(h.expected_from) : 'beyond the ladder'}</td>${firstLitIn(h)}${headState(h)}</tr>`).join('')
    : '<tr><td colspan="6" class="empty">no kind of head is charted for this trick yet; it may be done in the feed-forward layers, or by heads not yet described</td></tr>';
  // class by class
  const thr = ft ? ft.threshold : null;
  document.querySelector('#tricktrack tbody').innerHTML = (ladderData ? ladderData.rungs : []).map(r => {
    const mine = ft ? ft.ships.filter(x => x.preset === r.preset) : [], done = mine.filter(x => x.performed_at != null).sort((a, b) => a.performed_at - b.performed_at);
    const orders = t.field_params ? Math.log10(t.field_params / r.total) : null, best = mine.length ? Math.max(...mine.map(x => x.best)) : null, isT = r.preset === t.target_class;
    return `<tr${isT ? ' class="target"' : ''}><td>${classLink(r.preset)}${isT ? ' <span class="pill accent">target</span>' : ''}</td><td data-sort="${r.total}">${big(r.total)}</td>
      <td data-sort="${orders ?? ''}">${orders == null ? '<span class="s">the field has not shown it</span>' : orders >= 0 ? `${orders.toFixed(1)} orders of magnitude smaller` : `${(-orders).toFixed(1)} orders larger`}</td>
      <td>${ft ? mine.length : '–'}</td><td>${ft ? (mine.length ? `${done.length} of ${mine.length}` : '–') : '–'}</td>
      <td>${best != null ? `${fmt(best)} <span class="s">of ${thr}</span>` : '–'}</td><td>${done.length ? `${shipLink(done[0])} at step ${done[0].performed_at}` : '–'}</td></tr>`;
  }).join('');
  // the chart, for a measured trick
  document.getElementById('trickchartpanel').hidden = !ft;
  if (!ft) return;
  let d;
  try { d = await get('/api/trick?key=' + encodeURIComponent(ft.key)); } catch (e) { return; }
  const key = JSON.stringify(d.runs.map(r => [r.run_id, r.value.length, r.value[r.value.length - 1]]));
  if (key === trickChartKey) return;
  trickChartKey = key;
  if (!d.runs.length) return empty('trickchart', 'readings start with the next ship to sail');
  const presets = ladderData.rungs.map(r => r.preset);
  plot('trickchart', d.runs.map(r => ({ type: 'scatter', mode: 'lines', name: `${r.ship || r.name} (${r.preset})`, legendgroup: r.preset, x: r.step, y: r.value,
    line: { color: PALETTE[presets.indexOf(r.preset) % PALETTE.length], width: 1.4 }, hovertemplate: `${esc(r.ship || r.name)}: %{y:.3f} at step %{x}<extra></extra>` })),
    layout({ showlegend: d.runs.length <= 12, xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: esc(t.name), gridcolor: C.line },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: d.threshold, y1: d.threshold, line: { color: C.accent, dash: 'dot' } }] }));
}
function drawDiscoveryView() { if (discView === 'index') drawTricks(); if (discView === 'trick') drawTrickPage(); }
// the trick a kind of head performs, if measured: performed or not, on how many sailings
const trickNote = h => {
  const t = h.trick && discTricks.find(x => x.key === h.trick);
  if (!t) return '';
  const n = t.ships.filter(x => x.performed_at != null).length;
  return `<br><span class="s">its trick, ${esc(t.name)}: ${t.ships.length ? `performed on ${n} of ${t.ships.length} sailings` : 'readings start with the next ship to sail'}</span>`;
};
// classes in ladder order, smallest first; a kind beyond the ladder ranks after them all
const classRank = p => { const i = ladderData ? ladderData.rungs.findIndex(r => r.preset === p) : -1; return i < 0 ? 99 : i; };
// the smallest class where any sailing has lit a measured kind (one head first, else shared)
function firstLitIn(h) {
  const st = h.star && discStars.find(x => x.key === h.star);
  if (!st) return '<td data-sort="99">–</td>';
  const lit = st.ships.filter(x => x.steps_to_lit != null || x.shared_steps_to_lit != null).sort((a, b) => classRank(a.preset) - classRank(b.preset));
  if (!lit.length) return '<td data-sort="98" class="s">not lit yet</td>';
  const x = lit[0], below = classRank(x.preset) < classRank(h.expected_from);
  return `<td data-sort="${classRank(x.preset)}">${classLink(x.preset)} · ${x.steps_to_lit != null ? 'lit' : 'lit shared'} by ${shipLink(x)}${below ? ' <span class="pill good" title="lit below the class expected to reach it">below expectation</span>' : ''}</td>`;
}
// ---- a class's goals on the route to quantum physics (the Goals tab): its own goals, those of smaller
// classes it carries up, those left for bigger ones; its target level and ceiling
async function classGoals(r) {
  if (!reachData || Date.now() - reachAt > 30000) { try { reachData = await get('/api/discoveries'); reachAt = Date.now(); } catch (e) { return; } }
  const kts = reachData.known_tricks || [], wps = reachData.waypoints || [], me = classRank(r.preset);
  const wpRank = k => wps.findIndex(w => w.key === k), tname = Object.fromEntries(kts.map(t => [t.key, t.name]));
  const where = t => t.target_class == null ? (t.taught ? 'taught' : 'beyond') : classRank(t.target_class) < me ? 'below' : classRank(t.target_class) === me ? 'mine' : 'above';
  // a trick's state on this class's sailings
  const onClass = t => {
    const ft = t.fleet && (reachData.tricks || []).find(x => x.key === t.fleet);
    if (!t.fleet) return { text: 'not measured yet', done: false };
    const mine = ft ? ft.ships.filter(x => x.preset === r.preset) : [];
    if (!mine.length) return { text: 'measured · no sailing of this class has a reading yet', done: false };
    const done = mine.filter(x => x.performed_at != null), best = Math.max(...mine.map(x => x.best));
    return { text: done.length ? `performed on ${done.length} of ${mine.length} sailings` : `best ${fmt(best)} of ${ft.threshold} on ${mine.length} sailings`, done: done.length > 0, best };
  };
  const goals = kts.filter(t => where(t) === 'mine'), carried = kts.filter(t => where(t) === 'below');
  const level = goals.length ? wps[Math.max(...goals.map(t => wpRank(t.waypoint)))] : null;
  const ceiling = level ? goals.filter(t => t.waypoint === level.key) : [];
  const nextCls = ladderData.rungs[me + 1], nextGoals = nextCls ? kts.filter(t => t.target_class === nextCls.preset) : [];
  const done = goals.filter(t => onClass(t).done).length;
  document.getElementById('goalsover').innerHTML = [
    ['target level', level ? `<b>${esc(level.name)}</b> (waypoint ${wpRank(level.key) + 1} of ${wps.length})` : 'none set'],
    ['ceiling', ceiling.length ? ceiling.map(t => `<a href="#/discoveries/${esc(t.key)}">${t.gate ? '◆ ' : ''}${esc(t.name)}</a>`).join(', ') + '<br><span class="s">the upper limit expected of this size</span>' : '–'],
    ['its goals', `${goals.length} trick${goals.length === 1 ? '' : 's'} · ${done} performed so far`],
    ['carried up', carried.length ? `${carried.length} from smaller classes, kept, not relearned` : 'none: the first class on the ladder'],
    ['next class', nextCls ? `${classLink(nextCls.preset)} takes over with ${nextGoals.length}: ${nextGoals.slice(0, 4).map(t => esc(t.name)).join(', ')}${nextGoals.length > 4 ? '…' : ''}` : 'the top of the ladder; beyond it, the horizon'],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  // the route, bottom (reading) to top (discovery)
  document.getElementById('goalroute').innerHTML = [...wps].reverse().map(w => {
    const ts = kts.filter(t => t.waypoint === w.key).sort((a, b) => (a.target_class ? classRank(a.target_class) : 99) - (b.target_class ? classRank(b.target_class) : 99));
    const isLevel = level && level.key === w.key;
    return `<div class="wp${isLevel ? ' level' : ''}"><div class="wpname">${wpRank(w.key) + 1}. ${esc(w.name)}${isLevel ? ' <span class="pill accent">target level</span>' : ''}</div>
      <div class="chips">${ts.map(t => { const s = where(t), st = s === 'mine' || s === 'below' ? onClass(t) : null;
        const tip = `${t.name}: ${s === 'mine' ? 'a goal of this class' : s === 'below' ? `carried up from ${t.target_class}` : s === 'above' ? `a goal of ${t.target_class}` : s === 'taught' ? 'a reference, taught not read' : 'beyond the ladder'}${st ? ' · ' + st.text : ''}`;
        return `<a class="chip ${s}${st && st.done ? ' done' : ''}" href="#/discoveries/${esc(t.key)}" title="${esc(tip)}">${t.gate ? '◆ ' : ''}${esc(t.name)}${st && st.done ? ' ✓' : ''}${s === 'above' ? ` <span class="cls">${esc(t.target_class)}</span>` : ''}</a>`; }).join('')}</div></div>`;
  }).join('');
  document.querySelector('#goaltable tbody').innerHTML = goals.length ? goals.sort((a, b) => wpRank(a.waypoint) - wpRank(b.waypoint)).map(t => {
    const st = onClass(t);
    return `<tr data-trick="${esc(t.key)}" tabindex="0"><td><b>${esc(t.name)}</b></td><td data-sort="${wpRank(t.waypoint)}">${esc((wps.find(w => w.key === t.waypoint) || {}).name)}</td>
      <td>${t.gate ? '◆ gate' : 'milestone'}</td><td>${t.rests_on.length ? esc(t.rests_on.map(k => tname[k] || k).join(', ')) : '–'}</td>
      <td data-sort="${t.field_params ?? ''}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td>
      <td>${st.done ? '<span class="pill good">performed</span> ' : ''}${esc(st.text)}</td></tr>`;
  }).join('') : '<tr><td colspan="6" class="empty">no goals set for this class yet</td></tr>';
}
document.getElementById('goaltable').addEventListener('click', e => { const tr = e.target.closest('tr[data-trick]'); if (tr && !e.target.closest('a')) location.hash = '#/discoveries/' + tr.dataset.trick; });

// a class's stars in reach: the kinds expected at or below it, with its own sailings' state
let reachData = null, reachAt = 0;
async function starsInReach(r) {
  if (!reachData || Date.now() - reachAt > 30000) { try { reachData = await get('/api/discoveries'); reachAt = Date.now(); } catch (e) { return; } }
  const me = classRank(r.preset), heads = reachData.known_heads || [];
  const inReach = heads.filter(h => h.expected_from && classRank(h.expected_from) <= me).sort((a, b) => classRank(a.expected_from) - classRank(b.expected_from));
  const next = heads.filter(h => h.expected_from && classRank(h.expected_from) === me + 1);
  document.getElementById('reachnext').textContent = next.length ? `next in reach, one class up: ${next.map(h => h.name).join(', ')}` : '';
  document.querySelector('#reachtable tbody').innerHTML = inReach.length ? inReach.map(h => {
    const st = h.star && reachData.stars.find(x => x.key === h.star);
    let cell = '<td data-sort="9" class="s">not measured yet</td>';
    if (st) {
      const mine = st.ships.filter(x => x.preset === r.preset), lit = mine.filter(x => x.steps_to_lit != null), sh = mine.filter(x => x.shared_steps_to_lit != null);
      const best = Math.max(-1, ...mine.map(x => x.best ?? -1));
      cell = !mine.length ? '<td data-sort="8" class="s">measured, but no sailing of this class has a reading yet</td>'
        : `<td data-sort="${lit.length ? 0 : sh.length ? 1 : 2}">${lit.length ? '<span class="pill good">lit</span>' : sh.length ? '<span class="pill accent">lit shared</span>' : '<span class="pill">not lit yet</span>'}
          ${lit.length ? `on ${lit.length}` : sh.length ? `on ${sh.length}` : `best ${fmt(best)}`} of ${mine.length} sailings · threshold ${st.threshold}</td>`;
    }
    return `<tr><td><b>${esc(h.name)}</b></td><td>${esc(FAMILY[h.family] || h.family)}</td><td data-sort="${classRank(h.expected_from)}">${classLink(h.expected_from)}</td>
      <td class="s">${esc(h.expected_why || '')}</td>${cell}</tr>`;
  }).join('') : '<tr><td colspan="5" class="empty">no kind of head is expected this small</td></tr>';
}
const FAMILY = { position: 'position', copying: 'copying', circuit: 'the indirect-object circuit', suppression: 'suppression', structure: 'grammar and reference', task: 'the task' };
function drawHeads() {
  const sel = document.getElementById('headfamily');
  const fams = [...new Set(discHeads.map(h => h.family))];
  if (sel.options.length !== fams.length + 1) sel.innerHTML = '<option value="">all</option>' + fams.map(f => `<option value="${f}">${esc(FAMILY[f] || f)}</option>`).join('');
  const rows = discHeads.filter(h => !sel.value || h.family === sel.value), byKey = Object.fromEntries(discHeads.map(h => [h.key, h.name]));
  const state = headState;
  document.getElementById('headcount').textContent = `${rows.length} kinds · ${rows.filter(h => h.star).length} measured by Thorp`;
  document.querySelector('#headtable tbody').innerHTML = rows.map(h => `<tr${h.star ? ' class="measured"' : ''}><td><b>${esc(h.name)}</b></td><td>${esc(FAMILY[h.family] || h.family)}</td>
    <td>${esc(h.does)}</td><td>${h.rests_on.length ? esc(h.rests_on.map(k => byKey[k] || k).join(', ')) : '–'}</td>
    <td data-sort="${classRank(h.expected_from)}" title="${esc(h.expected_why || '')}">${h.expected_from ? classLink(h.expected_from) : 'beyond the ladder'}</td>${firstLitIn(h)}${state(h)}
    <td class="s">${esc(h.source)}</td><td class="s">${esc(h.seen_in)}</td></tr>`).join('');
}
document.getElementById('headfamily').onchange = drawHeads;
document.getElementById('traittable').addEventListener('click', e => { const tr = e.target.closest('tr[data-run]'); if (tr && !e.target.closest('a')) goShip(tr.dataset.run); });

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
  await loadLadder();  // a ship's address resolves through the ladder and the ships
  if (page === 'voyages' || page === 'voyage') loadVoyages();
  if (page === 'voyage' && currentVoyage()) journeyPanel(currentVoyage());
  if (page === 'discoveries') loadDiscoveries();
  if (page === 'sievesguide') loadSieves();
  try {
    const runs = await get('/api/runs');
    const first = !runsList;
    runsList = runs;
    if (!runs.length) { document.getElementById('title').textContent = 'no runs in the ledger yet'; return; }
    runsTable(runs);
    if (page !== 'ship') { document.getElementById('updated').textContent = 'updated ' + new Date().toLocaleTimeString(); return; }
    if (first) return showTab(location.hash.slice(1), false);  // now the ship can be named
    const { ship, run } = shipRun(runs);
    if (!run) { shipHeader(null, null); return; }
    if (run.run_id !== selected) return showTab(location.hash.slice(1), false);
    shipHeader(ship, run);
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
