// The dashboard: tabs, the run picker, every panel, refreshed every 5 s from the JSON API in
// server.py. Shared pieces live in ../lib (formatters, charts, DataTable, the reader).
import { Plotly, tok, C, PALETTE, layout, cfg, empty, plot } from '../lib/charts.js';
import { fmt, big, fmtBytes, esc, get, log10, mean } from '../lib/format.js';
import { DataTable } from '../lib/datatable.js';
import { pillCls, btnCls, fieldCls, selectCls, rangeCls, checkCls, cardCls, emptyCls, toggleCls, alertCls, hoverCardCls, tooltipCls, setTab, confirmDialog } from '../lib/ui';
import { cn } from '../lib/utils';
import { openBook, openEssay } from '../lib/reader.js';
import { renderHand, miniHand } from '../lib/cards.js';
import { drawJourney, soundingSteps } from '../lib/journey.js';
import { deckHand, CARD_FACE } from '../lib/deck.js';
import { fieldError, clearErrors, busy, filterBars, store } from '../lib/forms.js';
import { stagesFor, common as commonStages, band as bandStages, stageAt } from '../lib/stages.js';

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
//   #/voyages, #/expeditions/<key>   the voyages, and one voyage; #/expeditions/<key>/table talks with its ships
//   #/discoveries[/<trick>]      the tricks of the trade, and one trick; /stars and /traits beside them
//   #/sieves[/<sailing>]         the sieves explained, and one sailing's push, move and heading
// Older addresses (#sizes, #proxy, #rung-1m, #/models/…, #betting…, ?run=) land on the new ones.
const MTABS = ['fleet', 'goals', 'overview', 'training', 'scoring', 'waypoints', 'fitouts'];
const STABS = ['betting', 'books', 'languages', 'sieves', 'attention', 'traits'];
const STAB_EL = { betting: 'betting', books: 'books', languages: 'languages', sieves: 'sieves', attention: 'attention', traits: 'traits-section' };
const OLD_SHIP = { betting: 'betting', books: 'books', languages: 'languages', sieves: 'sieves', attention: 'attention', 'traits-section': 'traits' };
const SECTION_NAV = { sizes: 'classes', rung: 'classes', ship: 'classes', 'runs-section': 'classes', voyages: 'expeditions', voyage: 'expeditions', table: 'expeditions', discoveries: 'discoveries', sievesguide: 'sieves', leaderboard: 'leaderboard', competitor: 'leaderboard', governance: 'governance', shelves: 'library' };
let discView = 'index', discTrick = null, discChain = null, discSub = 'two-facts';
// an expedition page's tabs (UI.md, "Expeditions"): the same five for every expedition; one that doesn't apply is hidden
const ETABS = ['overview', 'at-sea', 'findings', 'fleet', 'inside'];
let expTab = 'overview';
// the Discoveries subtabs: the trick in focus (chaining two facts), the road to quantum mechanics, the registry of every trick
const DSUBS = ['two-facts', 'quantum', 'registry', 'stars'];
// the leaderboard and the shelves (their code is at the end; declared here, as the first route may reach them)
let cpModel = null, cpThorp = null, cpKey = null, cpStarsAsked = false, lbData = null, lbKey = null, shelvesData = null, shelfOpen = null, shelvesKey = null;
const shelfBooks = new Map();
let page = 'sizes', modelTab = 'fleet', shipKey = null, sailingKey = null, shipTab = 'betting', voyageKey = null, runsList = null, shipsData = null;
function route(h) {
  if (h.startsWith('/')) {
    const [a, b, c] = h.slice(1).split('/');
    if (a === 'classes' && b) { const d = h.slice(1).split('/')[3]; return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'fleet', wsub: WSUBS.includes(d) ? d : 'expected' }; }
    if (a === 'models' && b) return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'overview' };
    if (a === 'ships' && b) {
      const d = h.slice(1).split('/')[3];
      if (STABS.includes(c)) return { page: 'ship', ship: decodeURIComponent(b), sailing: null, stab: c };
      return { page: 'ship', ship: decodeURIComponent(b), sailing: c ? decodeURIComponent(c) : null, stab: STABS.includes(d) ? d : 'betting' };
    }
    if (a === 'ships') return { page: 'runs-section' };
    if ((a === 'voyages' || a === 'expeditions') && b && c === 'table') return { page: 'table', voyage: b };
    if ((a === 'voyages' || a === 'expeditions') && b) return { page: 'voyage', voyage: b, etab: ETABS.includes(c) ? c : 'overview' };
    if (a === 'voyages' || a === 'expeditions') return { page: 'voyages' };
    if (a === 'discoveries' && b === 'chains' && c) return { page: 'discoveries', dview: 'chain', chain: c };
    if (a === 'discoveries' && (!b || DSUBS.includes(b))) return { page: 'discoveries', dview: 'index', dsub: b || 'two-facts' };
    if (a === 'discoveries') return { page: 'discoveries', dview: b === 'traits' ? b : 'trick', trick: b !== 'traits' ? b : null };
    if (a === 'sieves') return { page: 'sievesguide', run: b ? decodeURIComponent(b) : null };
    if (a === 'leaderboard' && b === 'thorp' && c) return { page: 'competitor', thorp: decodeURIComponent(c) };
    if (a === 'leaderboard' && b === 'competitor' && c) return { page: 'competitor', model: decodeURIComponent(h.slice(1).split('/').slice(2).join('/')) };
    if (a === 'leaderboard') return { page: 'leaderboard' };
    if (a === 'governance') return { page: 'governance' };
    if (a === 'shelves' || a === 'library') return { page: 'shelves', shelf: b ? decodeURIComponent(b) : null };
    return { page: 'sizes' };
  }
  if (h.startsWith('rung-')) return { page: 'rung', rung: h.slice(5), mtab: 'fleet' };
  if (h in OLD_SHIP) return { page: 'ship', ship: null, stab: OLD_SHIP[h] };
  if (h === 'runs-section') return { page: 'runs-section' };
  if (!h || h === 'sizes' || h === 'rung') return { page: 'sizes' };
  return { page: 'rung', rung: h, mtab: 'fleet' };  // an old class link: #proxy
}
const WSUBS = ['expected', 'envelope', 'stars'];
let wpSub = 'expected';
const modelHash = (r, mt = 'fleet', sub = null) => `/classes/${slugOf(r)}${mt === 'fleet' ? '' : '/' + mt}${mt === 'waypoints' && sub && sub !== 'expected' ? '/' + sub : ''}`;
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
      currentRung = rt.rung; modelTab = rt.mtab; wpSub = rt.wsub || 'expected';
      if (r) {
        hash = modelHash(r, modelTab, wpSub);
        document.querySelectorAll('#modelnav a').forEach(a => { a.href = '#' + modelHash(r, a.dataset.mtab); });
        document.querySelectorAll('#wpnav a').forEach(a => { a.href = '#' + modelHash(r, 'waypoints', a.dataset.wsub); });
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
  if (page === 'voyage') {
    voyageKey = rt.voyage; expTab = rt.etab || 'overview';
    document.querySelectorAll('#expnav a').forEach(a => { a.href = '#/expeditions/' + voyageKey + (a.dataset.etab === 'overview' ? '' : '/' + a.dataset.etab); });
    showExpTab();  // may fall back to Overview, so the address is written after it
    hash = '/expeditions/' + voyageKey + (expTab === 'overview' ? '' : '/' + expTab);
  }
  if (page === 'table') { tableVoyage = rt.voyage; hash = '/expeditions/' + tableVoyage + '/table'; loadTable(); }
  if (page === 'sizes') hash = '/classes';
  if (page === 'runs-section') hash = '/ships';
  if (page === 'voyages') hash = '/expeditions';
  if (page === 'discoveries') {
    discView = rt.dview || 'index'; discTrick = rt.trick || null; discChain = rt.chain || null;
    if (discView === 'index') discSub = rt.dsub || 'two-facts';
    hash = '/discoveries' + (discView === 'index' ? (discSub === 'two-facts' ? '' : '/' + discSub) : '/' + (discView === 'trick' ? discTrick : discView === 'chain' ? 'chains/' + discChain : discView));
    document.querySelectorAll('#discoveries .dview').forEach(v => v.classList.toggle('active', v.dataset.dview === discView));
    document.querySelectorAll('#discoveries .dsub').forEach(v => v.classList.toggle('active', v.dataset.dsub === discSub));
    document.querySelectorAll('#discnav a').forEach(a => setTab(a, a.dataset.dsub === discSub));
    if (discData) drawDiscoveryView();
  }
  if (page === 'sievesguide') { sieveRun = rt.run; hash = '/sieves' + (sieveRun ? '/' + encodeURIComponent(sieveRun) : ''); }
  if (page === 'leaderboard') hash = '/leaderboard';
  if (page === 'governance') hash = '/governance';
  if (page === 'competitor') { cpThorp = rt.thorp || null; cpModel = rt.thorp || rt.model; hash = cpThorp ? '/leaderboard/thorp/' + encodeURIComponent(cpThorp) : '/leaderboard/competitor/' + encodeURIComponent(cpModel); }
  if (page === 'shelves') { shelfOpen = rt.shelf || shelfOpen; hash = '/library'; }
  document.querySelectorAll('main > .section').forEach(s => s.classList.toggle('active', s.id === page));
  document.querySelectorAll('#mainnav a').forEach(a => setTab(a, a.dataset.nav === SECTION_NAV[page]));
  document.querySelectorAll('#rung .mtab').forEach(t => t.classList.toggle('active', t.dataset.mtab === modelTab));
  document.querySelectorAll('#modelnav a').forEach(a => setTab(a, a.dataset.mtab === modelTab));
  document.querySelectorAll('#rung .wsub').forEach(t => t.classList.toggle('active', t.dataset.wsub === wpSub));
  document.querySelectorAll('#wpnav a').forEach(a => setTab(a, a.dataset.wsub === wpSub));
  document.querySelectorAll('#ship .shiptab').forEach(t => t.classList.toggle('active', t.id === STAB_EL[shipTab]));
  document.querySelectorAll('#shipnav a').forEach(a => setTab(a, a.dataset.stab === shipTab));
  // the address always reads the canonical way (old addresses and ?run= are rewritten, not stacked)
  if (hash && (location.hash !== '#' + hash || location.search)) history.replaceState(null, '', location.pathname + '#' + hash);
  if (page === 'voyages' || page === 'voyage') loadVoyages();
  if (page === 'voyages') loadOverview();
  if (page === 'discoveries') loadDiscoveries();
  if (page === 'sievesguide') loadSieves();
  if (page === 'leaderboard') loadLeaderboard();
  if (page === 'governance') loadGovernance();
  if (page === 'competitor') loadCompetitor();
  if (page === 'shelves') loadShelves();
  if (page === 'ship' && (selected !== wasShip || !runsList)) refresh();
  // charts drawn while hidden have no width; size the ones now showing
  document.querySelectorAll(`#${page} .chart`).forEach(el => { if (el.data && el.offsetParent) Plotly.Plots.resize(el); });
}
// the ship page's stage list: the stages its sailing read, in order (empty: one stage, reading)
function drawStageList(st) {
  const p = document.getElementById('stagepanel');
  p.hidden = !(st && st.length);
  if (!st || !st.length) return;
  document.querySelector('#stagetable tbody').innerHTML = st.map(s => `<tr><td>${s.index + 1}</td><td><b>${esc(s.name)}</b></td>
    <td>${esc(String(s.recipe || '–').replace('lists/', '').replace('.csv', ''))}</td><td>${s.passes ?? '–'}</td><td>${s.first_step}–${s.last_step}</td><td>${big(s.tokens)}</td></tr>`).join('');
}
function shipHeader(ship, run) {
  const preset = ship ? ship.cls : run && run.preset;
  const cls = preset && ladderData && ladderData.rungs.find(x => x.preset === preset);
  const link = document.getElementById('shipclass');
  link.textContent = cls ? `${cls.preset} · ${cls.name}` : preset || '';
  if (cls) link.href = '#' + modelHash(cls); else link.removeAttribute('href');
  document.getElementById('shipname').textContent = ship ? ship.name : run ? (run.ship || run.name || run.run_id.slice(0, 12)) : `no ship called ${shipKey}`;
  document.getElementById('shipfitout').textContent = ship ? ship.subtitle : '';
  document.getElementById('shiptags').innerHTML = ship ? (ship.archived ? `<span class="${pillCls('')}" title="fitted out before 7 November, 06:40">First Fleet · archived</span>` : `<span class="${pillCls('blue')}">in service</span>`)
    + (ship.voyage ? ` <a class="${pillCls('accent')}" href="#/expeditions/${esc(ship.voyage)}">${esc(VOYAGE_NAME[ship.voyage] || ship.voyage)}</a>` : '') : '';
  // its sailings: one per seed; the one shown is lit
  const sails = ship ? ship.sailings : run ? [{ run_id: run.run_id, name: run.name, seed: run.seed, status: run.status }] : [];
  document.getElementById('sailings').innerHTML = sails.map(x => `<a class="${toggleCls('sailing')}" data-state="${run && x.run_id === run.run_id ? 'on' : 'off'}" href="#${ship ? shipHash(ship.key, x.name, shipTab) : shipHash(x.name, null, shipTab)}"
    title="${esc(x.label || x.name)}" data-rid="${esc(x.run_id || '')}">seed <b>${x.seed ?? '–'}</b> ${esc(x.name)} · ${esc((x.status || '').split(':')[0])}${x.ft_en != null ? ` · ${fmt(x.ft_en)}` : ''}</a>`).join('');
  whereBadges(sails.map(x => x.run_id).filter(Boolean), id => document.querySelector(`#sailings [data-rid="${CSS.escape(id)}"]`));
  drawAboard(run);
}
window.addEventListener('hashchange', () => showTab(location.hash.slice(1), false));
filterBars();
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
    stat('ship', esc(run.ship || run.name || ''), `${esc(run.name || '')} · <span class="mono">${run.run_id.slice(0, 12)}</span> <span class="${pillCls(run.status.split(':')[0])}">${esc(run.status)}</span>`),
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
  if (scored.length < 2) verdict = `Not testable yet: ${scored.length} finished librar${scored.length === 1 ? 'y' : 'ies'} on the ledger. Two libraries at the same size and tokens are the first comparison; a second seed of one of them is the error bar.`;
  else {
    const sorted = scored.slice().sort((a, b) => a.best - b.best);
    const diff = sorted[sorted.length - 1].best - sorted[0].best;
    const spread = seeded.length ? Math.max(...seeded.map(f => f.spread)) : null;
    verdict = `Best library so far: ${sorted[0].key} at ${fmt(sorted[0].best, 4)} bpb; shelf-to-shelf difference ${fmt(diff, 4)}`;
    if (spread == null) verdict += '; no library has two finished seeds yet, so the difference has no error bar.';
    else { cls = diff > 2 * spread ? 'yes' : 'no'; verdict += `; seed-to-seed spread ${fmt(spread, 4)}.` + (cls === 'yes' ? ' The libraries differ by more than the seeds: the claim stands at this size.' : ' The seeds are as wide as the libraries: the difference is noise at this size.'); }
    verdict += ' Compared at each voyage’s final tokens; read the chart at matched tokens before quoting it.';
  }
  const rows = finals.map(f => `<tr><td>${esc(f.key)}</td><td>${f.runs.length}</td><td>${f.seeds}</td><td>${fmt(f.best, 4)}</td><td>${f.spread == null ? '–' : fmt(f.spread, 4)}</td></tr>`).join('');
  document.getElementById('claim').innerHTML = `
    <div><div class="k">Claim</div><div class="v">Some books make the guessing better, faster. Hold the model still, change the library, and the hole-card score falls faster per token on some libraries than on others. The kind of book that buys the most fall is the finding, and the next library is built from it.</div></div>
    <div><div class="k">Measure</div><div class="v">Guessing accuracy: bits per byte on the hole cards, books the model is never trained on. Learning speed: how far that number falls per million tokens seen. Neither is ever read from a book on the library.</div></div>
    <div><div class="k">Prediction</div><div class="v">At the same size and the same tokens, two libraries differ by more than two seeds of the same library do, and the order of libraries holds one size up. The per-book contribution (the heart of the dice, section 13) then names the books that carried it.</div></div>
    <div><div class="k">What would show it wrong</div><div class="v">A seed-to-seed spread as wide as the shelf-to-shelf difference; or an order of libraries at 9M that flips at 21M. Either is published as a finding, not buried.</div></div>
    <div class="reading"><div class="k">The ledger’s reading</div><div class="${alertCls(cls)}">${verdict}</div>
      <table class="mt"><thead><tr><th>library</th><th>voyages</th><th>finished seeds</th><th>best final bpb</th><th>seed spread</th></tr></thead><tbody>${rows || '<tr><td colspan=5 class="${emptyCls(true)}">no scored voyage yet</td></tr>'}</tbody></table></div>`;
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
  if (!data.length) return empty('compare', 'no scored voyage yet');
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
    if (!rows.length) { empty(id, 'no attn/mlp rows yet (written by voyages started after 2026-11-06)'); continue; }
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
  if (!all.length) { el.innerHTML = '<div class="${emptyCls()}">no probe rows yet: add <span class="mono">probes</span> to eval.evaluators in the spec</div>'; empty('probeheat', ''); stepSel.innerHTML = ''; return; }
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
    return `<div class="trait"><div class="n">${esc(n.replace('_', ' '))}</div><div class="a ${a[1]}">${a[0]}</div><div class="r">${esc(where)}${kink}${firstLine}${floors}<br>library ${t.n_train[0]}/${t.n_train[1]} · held out ${t.n_test[0]}/${t.n_test[1]}</div></div>`;
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
  [2, 'noticing the strange', 'r2_novelty_auc', 'AUC, unseen books against library books'],
  [3, 'learning from the page', 'r3_copy_gain', 'nats saved on a repeated span (and late minus early loss)'],
  [4, 'knowing a question', 'r4_question_auc', 'AUC, questions against statements, punctuation removed'],
  [5, 'expecting an answer', 'r5_expectancy', 'nats more uncertain after "?" than after "."'],
  [6, 'asking', 'r6_asking', 'log ratio of "?" where unsure, beyond the text'],
];
function ladderPanel(r, m) {
  const c = r.curiosity && r.curiosity.data, el = document.getElementById('ladder'), vd = document.getElementById('ladderverdict');
  if (!c) { el.innerHTML = '<div class="${emptyCls()}">no ladder rows yet: add <span class="mono">curiosity</span> to eval.evaluators, or re-score with <span class="mono">thorp eval RUN --evaluators curiosity</span></div>'; vd.innerHTML = ''; empty('laddertime', ''); return; }
  document.getElementById('ladderh').firstChild.textContent = `The curiosity ladder at step ${r.curiosity.step} `;
  const order = c.highest === 0 ? 'No rung is present yet.' : c.in_order ? `In order: every rung up to ${c.highest} that could be tested is present, none above an absent one.` : `Out of order: rung ${c.highest} is present above an absent rung. That is a finding against the ladder at this size.`;
  vd.innerHTML = `<div class="reading"><div class="k">The ledger’s reading</div><div class="${alertCls(c.highest === 0 ? 'open' : c.in_order ? 'yes' : 'no')}">${order}</div></div>`;
  const floorOf = k => k === 2 ? c.floor_bow.r2 : k === 4 ? c.floor_bow.r4 : null;
  el.innerHTML = `<table><thead><tr><th>rung</th><th>measure</th><th>trained</th><th>untrained</th><th>token floor</th><th>status</th><th>reading</th></tr></thead><tbody>${
    LADDER.slice().reverse().map(([k, name, key, what]) => {
      const s = c.rungs[k] || { status: 'untestable', reason: '' };
      const cls = s.status === 'present' ? 'finished' : s.status === 'absent' ? 'failed' : 'running';
      return `<tr><td><b>${k}</b> ${esc(name)}</td><td class="note">${esc(what)}</td><td>${fmt(c.values[key], 3)}</td><td>${fmt(c.untrained[key], 3)}</td><td>${fmt(floorOf(k), 3)}</td>
        <td><span class="${pillCls(cls)}">${s.status}</span></td><td class="note">${esc(s.reason)}</td></tr>`;
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
  if (!r.samples) { el.innerHTML = '<div class="${emptyCls()}">no samples yet</div>'; empty('top10'); return; }
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
  if (!runs.length) { document.getElementById('matched').innerHTML = '<div class="${emptyCls()}">no scored voyage yet</div>'; return; }
  const rows = runs.map(r => {
    const last = r.bpb.length - 1;
    return `<tr><td>${esc(r.ship || r.name)}</td><td>${r.seed ?? ''}</td><td class="mono">${esc(r.set)}</td><td>${r.n_books ?? '?'}</td><td>${big(r.tokens[last])}</td>
      ${MATCH_AT.map(x => `<td>${fmt(interp(r.tokens, r.bpb, x), 4)}</td>`).join('')}
      <td><b>${fmt(r.bpb[last], 4)}</b></td><td>${fmt(r.bpb_en[r.bpb_en.length - 1], 4)}</td><td>${esc(earliestKink(r))}</td>
      <td><span class="${pillCls((r.status || '').split(':')[0])}">${esc((r.status || '').split(':')[0])}</span></td></tr>`;
  }).join('');
  document.getElementById('matched').innerHTML = `<table><thead><tr><th>ship</th><th>seed</th><th>set</th><th>books</th><th>tokens seen</th>
    ${MATCH_AT.map(x => `<th>bpb @ ${big(x)}</th>`).join('')}<th>final bpb</th><th>final en</th><th>earliest firm kink</th><th>status</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="note" style="margin-top:6px">Compare only rows on the same set: hole-cards (13 books) and hole-cards-v2 (20 books, without Darwin and Einstein) are different decks.</div>`;
}
function truthGapPanel(cmp) {
  const lit = r => r.by_set['hole-cards-v2'] ? 'hole-cards-v2' : 'hole-cards';
  const runs = cmp.filter(r => r.by_set && r.by_set.truths && r.by_set[lit(r)]);
  const el = document.getElementById('truthgap');
  if (!runs.length) { el.innerHTML = '<div class="${emptyCls()}">no voyage has been scored on the truths deck yet (lists/truths.csv): re-score a finished voyage with <span class="mono">thorp eval RUN --sets lists/hole-cards-v2.csv lists/truths.csv</span></div>'; return; }
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
  if (F.length < 2) return { line: `waiting for the random libraries (${F.length} of 3 finished)`, cls: 'open', rows: [] };
  const c = meanOf(F), S = rangeOf(F);
  const rows = CURATED.map(k => {
    const v = (groups[k] || []).filter(x => x != null);
    if (!v.length) return { k, text: 'not yet', cls: 'open' };
    const m = meanOf(v), d = m - c, out = Math.abs(d) > 2 * S;
    return { k, m, d, n: v.length, spread: rangeOf(v), out, text: `${fmt(m, digits)} (${v.length} ship${v.length > 1 ? 's' : ''}), ${d >= 0 ? '+' : ''}${fmt(d, digits)} from random`, cls: out ? 'yes' : 'no' };
  });
  const moved = rows.filter(r => r.out);
  const line = moved.length ? `Content has a detectable bearing: ${moved.map(r => SHELF_LABEL[r.k].split(' · ')[0]).join(', ')} ${moved.length > 1 ? 'lie' : 'lies'} more than 2S from the random libraries (centre ${fmt(c, digits)}, S ${fmt(S, digits)}${unit}).`
    : `No detectable bearing so far: every curated library lies within 2S of the random libraries (centre ${fmt(c, digits)}, S ${fmt(S, digits)}${unit}).`;
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
  if (!ships.length) { el.innerHTML = '<div class="${emptyCls()}">no content ship on the ledger yet: they voyage after the night queue and the re-score (scripts/queue_content.sh)</div>'; tb.innerHTML = ''; empty('contentchart', ''); return; }
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
    .map(([label, a, b]) => { const p = pairVerdict(g, a, b, 4); return `<tr><td>${label}</td><td>${p ? `${p.d >= 0 ? '+' : ''}${fmt(p.d, 4)} bpb` : '–'}</td><td>${p ? fmt(p.bar, 4) : '–'}</td><td>${p ? `<span class="${pillCls(p.out ? 'finished' : 'failed')}">${p.out ? 'differ' : 'within noise'}</span>` : 'needs two ships a side'}</td></tr>`; }).join('');
  el.innerHTML = `<div class="reading"><div class="k">The ledger’s reading: guessing (neutral deck, English bits per byte at ${T ? big(T) : '–'} tokens, ${done.length} of ${ships.length} ships finished)</div><div class="${alertCls(primary.cls)}">${primary.line}</div>
    <table class="mt"><thead><tr><th>library</th><th>against the random libraries</th></tr></thead><tbody>${primary.rows.map(r => `<tr><td>${SHELF_LABEL[r.k]}</td><td><span class="verdict ${r.cls}" style="display:inline">${esc(r.text)}</span></td></tr>`).join('')}</tbody></table>
    <table class="mt"><thead><tr><th>quality and type</th><th>difference</th><th>twice the larger spread</th><th>reading</th></tr></thead><tbody>${pairs}</tbody></table>
    <table class="mt"><thead><tr><th>secondary outcome</th><th>reading (same rule: more than 2S from the random libraries)</th></tr></thead><tbody>${secondary.map(([label, v]) => `<tr><td>${esc(label)}</td><td><span class="verdict ${v.cls}" style="display:inline">${esc(v.line)}</span></td></tr>`).join('')}</tbody></table></div>`;
  tb.innerHTML = `<table style="margin-top:12px"><thead><tr><th>ship</th><th>library</th><th>its question</th><th>status</th><th>tokens</th><th>neutral bpb at T</th><th>earliest firm kink</th><th>highest rung</th></tr></thead><tbody>${
    ships.map(r => `<tr><td><b>${esc(r.ship || r.name)}</b></td><td>${esc(SHELF_LABEL[shelfOf(r)] || '')}</td><td class="note">${esc(r.question || '')}</td><td><span class="${pillCls((r.status || '').split(':')[0])}">${esc((r.status || '').split(':')[0])}</span></td>
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
    <td><span class="${pillCls((r.status || '').split(':')[0])}">${esc(r.status || '')}</span></td><td>${big(r.tokens_seen)}</td>
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
  nonword_rate: ['Non-words', 'Lower, down to the books\' own rate', 'Share of the words the model writes that never appear anywhere on its library: invented spellings. The books\' own rate (ref) is the floor, because real text also holds words the library lacks. Reaching ref means it spells like a book.'],
  zipf: ['Zipf slope', 'Closer to the books', 'How fast word frequency falls with rank (the 10th commonest word is about a tenth as common as the 1st). Below the books: words used too evenly, as in noise. Above: too much repetition of a few common words. Real English sits near 1.'],
  heaps: ['Heaps slope', 'Closer to the books', 'How fast new words keep appearing as text goes on. Above the books usually means inventing words; below means a small, repetitive vocabulary.'],
  word_len: ['Mean word length', 'Closer to the books', 'Average letters per word. Real text prefers short common words (brevity law); a model that writes long strings of letters scores high here.'],
  punct_per_100w: ['Punctuation per 100 words', 'Closer to the books', 'How much punctuation it uses at all. Too much is a common early failure: commas and quote marks sprayed everywhere.'],
  unbalanced_per_kw: ['Unbalanced brackets and quotes per 1,000 words', 'Lower, down to the books\' own rate', 'Brackets and curly quotes closed without being opened, or left open. The books have a few because the excerpts are cut mid-passage; that is the floor.'],
  cap_after_stop: ['Capital after a full stop', 'Higher, up to the books', 'Share of sentence ends followed by a capital letter. Books score about 0.9 (abbreviations such as "Mr." account for the rest).'],
  word_len_js: ['Word-length divergence', 'Lower (0 is identical)', 'Jensen–Shannon divergence, in bits, between the model\'s mix of word lengths and the books\'. 0 means the same shape.'],
  punct_js: ['Punctuation-mix divergence', 'Lower (0 is identical)', 'Divergence between which punctuation marks the model uses and which the books use: the right marks in the right proportions.'],
  traits: ['Traits as they emerge', 'Earlier and stronger', 'Can a probe read fiction, verse or first person off the model\'s hidden state, at which layer, from which step? Shown on the Traits tab for each voyage.'],
  ft: ['The Forgotten Tomes score', 'Lower', 'Bits per byte on 16 period books released on Gutenberg after Qwen 3.8 appeared, so no Qwen model can have trained on them. The same number for Thorp and for Qwen, whatever their tokenisers: the yardstick for the order-of-magnitude gate.'],
  rank: ['Rank agreement with 9m', 'Higher (1 is perfect)', 'Spearman correlation between the order 9m puts the libraries in and the order 1m puts them in. At 0.8 or above the proxy is trusted to explore those kinds of questions.'],
  modelref: ['model / ref', 'Model close to ref', 'Each law is measured on text the model writes (left) and on excerpts of the held-out books (ref, right), at the same length. The target is the books\' own value.'],
};
const info = k => { const h = HELP[k]; return h ? `<span class="info" tabindex="0">ⓘ<span class="pop ${hoverCardCls}"><b>${esc(h[0])}</b><br>Better: <b>${esc(h[1])}</b><br>${esc(h[2])}</span></span>` : ''; };
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
  try { tomesData = await get('/api/tomes'); } catch (e) { body.innerHTML = '<tr><td class="${emptyCls(true)}">could not load the deck</td></tr>'; return; }
  const outside = Object.keys(tomesData.scores).filter(k => !ladderData.runs.some(x => (x.ship || x.name) === k));
  const cols = [...pick.filter(k => tomesData.scores[k]), ...outside];
  const label = c => c === (best && (best.ship || best.name)) ? `${esc(c)} <span class="${pillCls('good')}">best</span>` : esc(c);
  head.innerHTML = `<tr><th>title</th><th>author</th><th>released</th><th>size</th>${cols.map(c => `<th>${label(c)}${info('ft')}</th>`).join('')}</tr>`;
  body.innerHTML = tomesData.books.map(b => `<tr data-book="${b.book_id}"><td>${esc(b.title)}</td><td>${esc(b.author)}</td><td>${esc(b.released)}</td>
    <td>${fmtBytes(b.bytes)}</td>${cols.map(c => `<td>${fmt(tomesData.scores[c][b.book_id])}</td>`).join('')}</tr>`).join('');
}
// one run's training shelf, every book on it
async function renderShelf(r, runs) {
  const pick = document.getElementById('shelfpick'), filt = document.getElementById('bookfilter');
  const head = document.querySelector('#shelftable thead'), body = document.querySelector('#shelftable tbody');
  const names = runs.map(x => x.name);
  if (!names.length) { head.innerHTML = ''; body.innerHTML = '<tr><td class="${emptyCls(true)}">no voyages at this size yet</td></tr>'; shelfKey = null; return; }
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
  let d;
  try { [d, shipsData] = await Promise.all([get('/api/ladder'), get('/api/ships').catch(() => [])]); } catch (e) { d = { error: e.message }; }
  if (!d || !Array.isArray(d.rungs)) {  // the server failed: say so where the classes go, keep the last good ladder
    document.getElementById('rungcards').innerHTML = `<div class="${emptyCls()}">the classes could not be read${d && d.error ? ': ' + esc(d.error) : ''}. Restart <span class="mono">thorp dash</span> if it was just changed.</div>`;
    return;
  }
  ladderData = d;
  document.getElementById('rungcards').innerHTML = d.rungs.map(r => {
    const runs = rungRuns(r.preset), live = runs.filter(x => x.status === 'running').length, done = runs.filter(x => x.status === 'finished').length;
    const nlive = r.metrics.filter(m => m[2] === 'live').length;
    return `<a class="${cardCls(true, 'card classcard')}" href="#${esc(modelHash(r))}">${artImg(classSlug(r.name), 'cardart ship')}
      <div class="top"><span class="preset">${esc(r.preset)}</span><span class="nm">${esc(r.name)}</span></div>
      <div class="job">${esc(r.job)}</div><div class="ov">${esc(r.overview)}</div>
      <div class="foot"><span>${big(r.total)} params · ${esc(r.where.split(' (')[0])}</span>
      <span class="${pillCls(live ? ' live' : '')}">${live ? live + ' running' : esc(r.status)}</span></div>
      <div class="foot"><span>${done} finished voyage${done === 1 ? '' : 's'}</span><span>${nlive} of ${r.metrics.length} metrics live</span></div></a>`;
  }).join('');
  document.querySelector('#queue tbody').innerHTML = d.queue.map((q, i) => `<tr${q.status === 'running' ? ' class="sel"' : ''}><td>${i + 1}</td>
    <td>${esc(q.name)}</td><td>${esc(q.status.split(':')[0])}</td></tr>`).join('');
  if (page === 'sizes') routeCoverage();
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
  if (!runs.length) { sum.innerHTML = ''; el.innerHTML = `<div class="${emptyCls()}">no voyages at ${esc(r.preset)} yet</div>`; return; }
  const scored = runs.filter(x => x.ft_en != null).sort((a, b) => a.ft_en - b.ft_en);
  const rank = new Map(scored.map((x, i) => [x.run_id, i]));
  const level = x => !rank.has(x.run_id) ? 0 : 4 - Math.min(3, Math.floor(4 * rank.get(x.run_id) / scored.length));
  const live = runs.filter(x => x.status === 'running').length;
  const med = scored.length ? scored[Math.floor((scored.length - 1) / 2)].ft_en : null;
  const latest = [...runs].reverse().find(x => x.ft_en != null);
  sum.innerHTML = `<span><b>${runs.length}</b> voyage${runs.length === 1 ? '' : 's'}</span><span><b>${scored.length}</b> scored</span>${live ? `<span class="${pillCls('blue')}">${live} running</span>` : ''}`
    + (scored.length ? `<span>best <b>${fmt(scored[0].ft_en)}</b> ${esc(scored[0].ship || scored[0].name)}</span><span>median <b>${fmt(med)}</b></span><span>latest <b>${fmt(latest.ft_en)}</b> ${esc(latest.ship || latest.name)}</span>` : '')
    + `<span class="legend">worse <i class="g1"></i><i class="g2"></i><i class="g3"></i><i class="g4"></i> better · <i class="g0"></i> not scored</span>`;
  const per = GRID_ROWS * GRID_COLS, bands = [];
  for (let b = 0; b * per < runs.length; b++) {
    const chunk = runs.slice(b * per, (b + 1) * per);
    bands.push(`<div class="gridband"><div class="gridlabel">voyages ${b * per + 1}–${b * per + chunk.length}</div><div class="rungrid">${chunk.map(x => {
      const st = (x.status || '').split(':')[0];
      return `<i class="g${level(x)}${st === 'running' ? ' run' : ''}${st === 'failed' ? ' fail' : ''}${x.run_id === selected ? ' sel' : ''}" data-run="${esc(x.run_id)}"></i>`;
    }).join('')}</div></div>`);
  }
  el.innerHTML = bands.join('');
  el._runs = new Map(runs.map(x => [x.run_id, x])); el._rank = rank; el._n = scored.length;
}
(() => {
  const el = document.getElementById('rungrid'), tip = document.createElement('div');
  tip.className = cn('gridtip', tooltipCls); tip.hidden = true; document.body.appendChild(tip);
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
    <td><span class="${pillCls(m[2] === 'live' ? ' live' : '')}">${esc(m[2])}</span></td></tr>`).join('')
  : '<tr><td colspan="4" class="${emptyCls(true)}">none for this model yet</td></tr>';
const runCells = x => `<td>${esc(x.ship || '')}</td><td>${esc(x.name)}</td><td>${esc((x.status || '').split(':')[0])}</td>`;
function renderRung() {
  const r = rungFor(currentRung) || ladderData.rungs[0];
  // the template's own slot: panels marked data-kind show only on that kind of model
  document.querySelectorAll('#rung [data-kind]').forEach(el => { el.hidden = !el.dataset.kind.split(' ').includes(r.kind || slugOf(r)); });
  document.getElementById('rungtitle').textContent = `${r.preset} · ${r.name}`;
  document.getElementById('rungjob').textContent = r.job;
  const allRuns = rungRuns(r.preset), runs = allRuns.slice(-RECENT), capped = allRuns.length > runs.length;
  const more = (n) => capped ? `<tr><td colspan="${n}" class="note">the latest ${runs.length} of ${allRuns.length} voyages at ${esc(r.preset)}; the Overview grid has every one</td></tr>` : '';
  const none = (n) => `<tr><td colspan="${n}" class="${emptyCls(true)}">no voyages at ${esc(r.preset)} yet</td></tr>`;
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
      <td>${x.voyage ? `<a href="#/expeditions/${esc(x.voyage)}">${esc(VOYAGE_NAME[x.voyage] || x.voyage)}</a>` : '–'}</td>
      <td><span class="${pillCls(st)}">${esc(st)}</span></td><td>${fmt(x.ft_en_mean)}</td><td>${fmt(x.ft_en_best)}</td>
      <td>${esc(String(x.latest || '–').slice(0, 16).replace('T', ' '))}</td></tr>`;
  };
  const live = fleet.filter(x => !x.archived), old = fleet.filter(x => x.archived);
  document.querySelector('#fleettable tbody').innerHTML = live.length ? live.map(shipRow).join('')
    : `<tr><td colspan="8" class="${emptyCls(true)}">no ship of this class in service yet${old.length ? '; the First Fleet is below' : ''}</td></tr>`;
  document.getElementById('fleetarchivewrap').hidden = !old.length;
  document.getElementById('fleetarchivesum').textContent = `archived: ${old.length} ship${old.length === 1 ? '' : 's'}, ${old.reduce((n, x) => n + x.sailings.length, 0)} voyages, fitted out before 7 November`;
  document.querySelector('#fleetarchive tbody').innerHTML = old.map(shipRow).join('');

  // ---- Scoring: science, then art
  document.querySelector('#sciencemetrics tbody').innerHTML = metricRows(r.metrics.filter(m => !ART.has(m[0])));
  classScoreLive(r);
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
  if (!split.length) empty('splitchart', runs.length ? 'the split arrives when scripts/queue_9m.sh re-scores the finished voyages, after tonight\'s pool voyages' : 'no voyages at this size yet');
  else plot('splitchart', split.map((x, i) => ({ type: 'bar', name: x.ship || x.name, x: Object.values(SPLIT_LABEL),
    y: Object.keys(SPLIT_LABEL).map(c => x.split[c]), marker: { color: PALETTE[i % PALETTE.length] } })),
    layout({ barmode: 'group', yaxis: { title: 'bits per byte', gridcolor: C.line } }));
  const ratioKeys = LAW_COLS.filter(c => !c[0].endsWith('_js'));
  const laws = runs.filter(x => Object.values(x.laws).some(v => v != null));
  if (!laws.length) empty('lawchart', runs.length ? 'the laws arrive with the same re-score' : 'no voyages at this size yet');
  else plot('lawchart', laws.map((x, i) => ({ type: 'bar', name: x.ship || x.name, x: ratioKeys.map(c => c[1]),
    y: ratioKeys.map(([k]) => x.laws[k] != null && x.ref[k] ? x.laws[k] / x.ref[k] : null), marker: { color: PALETTE[i % PALETTE.length] } })),
    layout({ barmode: 'group', yaxis: { title: 'model ÷ books', gridcolor: C.line },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: C.accent, dash: 'dot' } }] }));
  renderTomes(r, allRuns);
  rungExtras(r, runs, allRuns);
  if (modelTab === 'waypoints') { renderWaypoints(r); starsInReach(r); classSteps(r); }
  if (modelTab === 'goals') classGoals(r);
  if (modelTab === 'fitouts') classFitouts(r);
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
    el.innerHTML = `<div class="${emptyCls()}">no voyage at this size has per-head Nevermore scores yet; they arrive with the queue (every 250 steps) and <span class="mono">scripts/score_nevermore.sh</span></div>`;
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
  }).join('') : `<tr><td colspan="${11 + 2 * core.length}" class="${emptyCls(true)}">no voyages at ${esc(r.preset)} yet</td></tr>`;

  const recent = d.runs.slice(-12);
  const lines = (pick, id, title, msg, extra = {}) => {
    const rs = recent.filter(x => pick(x) && pick(x).step.length);
    if (!rs.length) return empty(id, msg);
    plot(id, rs.map((x, i) => ({ type: 'scatter', mode: 'lines+markers', name: x.ship || x.name, x: pick(x).step, y: pick(x).value,
      line: { color: PALETTE[i % PALETTE.length], width: 1.5 }, marker: { size: 4 } })),
      layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title, gridcolor: C.line }, ...extra }));
  };
  const hline = (y) => ({ shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color: C.accent, dash: 'dot' } }] });
  const nvMsg = `no voyage at ${esc(r.preset)} has Nevermore scores on the ledger yet: queued voyages record them every 250 steps, loop voyages at their last step, and <span class="mono">scripts/score_nevermore.sh</span> scores every finished 1m and 9m voyage once. First test readings: none formed anywhere yet; Smaller Pieces (9m, vocabulary 4,096) has one forming in its top layer, 0.12 on real prose`;
  lines(x => x.nevermore.natural_max_score || x.nevermore.max_score, 'nvchart', 'Nevermore score', nvMsg, { ...hline(thr), yaxis: { title: 'Nevermore score', gridcolor: C.line, range: [0, 1] } });
  lines(x => x.nevermore.natural_copy_gain || x.nevermore.copy_gain, 'copychart', 'nats per token', nvMsg);
  for (const t of core) lines(x => x.traits[t] && x.traits[t].best, 'trait-' + t, 'held-out AUC',
    `no voyage at ${esc(r.preset)} has trait probes yet; add <span class="mono">probes</span> to eval.evaluators`, { ...hline(found), showlegend: false });
  stagesFor(recent.map(x => x.run_id)).then(m => bandStages('#rung', commonStages(m)));
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
const statusPill = st => `<span class="${pillCls({ running: 'blue', done: 'good', paused: 'accent' }[st] || '')}">${esc(st || '')}</span>`;
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
  try { d = await get('/api/expeditions'); } catch (e) { return; }
  d.forEach(v => { VOYAGE_NAME[v.key] = v.name; });
  const key = JSON.stringify(d) + '|' + voyageKey + '|' + !!ladderData;
  if (key === voyagesKey) return;
  voyagesKey = key; voyagesData = d;
  document.getElementById('voyagecards').innerHTML = d.map(v => {
    const valid = v.runs.filter(r => !r.set_aside).length;
    const headline = v.learned || starHeadline(v) || 'nothing found yet';
    return `<a class="${cardCls(true, 'card')}" href="#/expeditions/${esc(v.key)}">
      <div class="top"><span class="preset">${esc(v.name)}</span>${expPill(v)}</div>
      <div class="goal">${esc(v.goal)}</div>
      <div class="ov">${esc(headline)}</div>
      <div class="foot"><span>${esc(v.fleet || '')} · ${esc(v.preset || '')}</span><span>${valid} of ${v.stop.max_runs} voyages</span></div>
      <div class="foot"><span>${(v.ships || []).length} ship${(v.ships || []).length === 1 ? '' : 's'}${v.stars && v.stars.length ? ` · bound for ${esc(v.stars.map(k => STAR_LABEL[k] || k).join(', '))}` : ''}</span></div></a>`;
  }).join('') || '<div class="${emptyCls()}">no expeditions yet</div>';
  if (page === 'voyage') renderVoyage();
}
function renderVoyage() {
  const v = voyagesData && voyagesData.find(x => x.key === voyageKey);
  if (!v) { document.getElementById('voyagetitle').textContent = voyagesData ? `no expedition called ${voyageKey}` : 'loading…'; return; }
  document.querySelectorAll('#voyage [data-voyage]').forEach(el => { el.hidden = el.dataset.voyage !== v.key; });
  gateExpTabs(v);
  document.getElementById('voyagetitle').textContent = v.name;
  document.getElementById('voyagestatus').innerHTML = expPill(v);
  document.getElementById('voyagegoal').textContent = v.goal;
  const valid = v.runs.filter(r => !r.set_aside);
  document.getElementById('voyageover').innerHTML = [
    ['fleet', esc(v.fleet || '–')], ['class', classLink(v.preset)],
    ['bound for', esc((v.stars || []).map(k => STAR_LABEL[k] || k).join(', ') || '–')], ['ships', String((v.ships || []).length)],
    ['runs', `${valid.length} of ${v.stop.max_runs}${v.runs.length > valid.length ? ` (${v.runs.length - valid.length} set aside)` : ''}`],
    ['stop rule', esc(v.stop.about || '')], ['status', esc(v.status)],
  ].map(([k, val]) => `<div><div class="k">${k}</div><div>${val}</div></div>`).join('');
  const learned = v.learned || starHeadline(v);
  // standard: every expedition shows the panel; one with nothing written up says so
  document.getElementById('voyagelearned').hidden = false;
  document.getElementById('voyagelearnedtext').innerHTML = learned ? esc(learned) : '<span class="s">nothing written up yet: what it found is written when it comes home</span>';
  const next = v.next_steps || [];
  document.getElementById('voyagenextwrap').hidden = !next.length;
  document.getElementById('voyagenext').innerHTML = next.map(x => `<li>${esc(x)}</li>`).join('');
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
  document.querySelector('#voyageruns thead').innerHTML = `<tr><th>ship</th><th>fitout</th><th>voyages</th><th>Forgotten Tomes (mean)${info('ft')}</th>
    ${starKeys.map(k => `<th>${esc(STAR_LABEL[k] || k)}</th>`).join('')}</tr>`;
  document.querySelector('#voyageruns tbody').innerHTML = vships.length ? vships.map(x => `<tr data-ship="${esc(x.key)}">
    <td><b>${esc(x.name)}</b></td><td class="s">${esc(x.subtitle)}</td><td data-sort="${x.sailings.length}">${x.sailings.length}</td><td>${fmt(x.ft_en_mean)}</td>
    ${starKeys.map(k => { const st = (x.stars || {})[k] || {};
      return st.lit ? `<td data-sort="${st.soonest}">lit by ${st.lit} of ${x.sailings.length} · soonest step ${st.soonest}</td>`
        : st.lit_shared ? `<td data-sort="${st.soonest_shared}" title="the best layer's two strongest heads together">lit shared by ${st.lit_shared} of ${x.sailings.length} · soonest step ${st.soonest_shared}</td>`
        : st.best != null ? `<td data-sort="" class="s" title="not lit yet; the best so far">best ${fmt(st.best)}</td>` : '<td>–</td>'; }).join('')}</tr>`).join('')
    : `<tr><td colspan="${4 + starKeys.length}" class="${emptyCls(true)}">no ships have sailed on this expedition yet</td></tr>`;
  // the Forgotten Tomes score run by run, one colour per value of the setting that varies most
  const scored = v.runs.map((r, i) => ({ r, i: i + 1 })).filter(p => p.r.ft_en != null && !p.r.set_aside);
  // the Forgotten Tomes score shows only where the expedition has one; first light only for the stars it is bound for
  document.getElementById('ftpanel').hidden = !scored.length;
  document.getElementById('lightpanel').hidden = !(v.stars && v.stars.length);
  if (!scored.length) empty('voyageft', 'no voyage on this expedition has a Forgotten Tomes score yet');
  else {
    const fields = ['passes', 'vocab', 'lr', 'recipe'];
    const by = fields.map(f => [f, new Set(scored.map(p => (p.r.settings || {})[f])).size]).sort((a, b) => b[1] - a[1])[0][0];
    const groups = [...new Set(scored.map(p => (p.r.settings || {})[by]))];
    plot('voyageft', groups.map((g, gi) => { const pts = scored.filter(p => (p.r.settings || {})[by] === g);
      return { type: 'scatter', mode: 'markers', name: `${by} ${String(g).replace('lists/', '').replace('.csv', '')}`, x: pts.map(p => p.i), y: pts.map(p => p.r.ft_en),
        text: pts.map(p => p.r.ship || p.r.name), hovertemplate: '%{text}: %{y:.3f}<extra></extra>', marker: { size: 9, color: PALETTE[gi % PALETTE.length] } }; }),
      layout({ xaxis: { title: 'voyage, in the order they sailed', gridcolor: C.line }, yaxis: { title: 'bits per byte', gridcolor: C.line }, legend: { orientation: 'h', y: 1.1 } }));
  }
  document.querySelector('#voyageoutcomes tbody').innerHTML = v.outcomes.map(o => `<tr><td>${esc(o.about)}</td><td class="mono">${esc(o.metric)}</td><td>${esc(o.better)}</td></tr>`).join('');
  document.querySelector('#voyagelevers tbody').innerHTML = v.levers.map(l => `<tr><td class="mono">${esc(l.key)}</td>
    <td>${l.fixed ? 'fixed' : l.choices && l.choices.length ? esc(l.choices.join(', ')) : `${l.low ?? '–'} to ${l.high ?? '–'}`}</td><td>${esc(l.about || '')}</td></tr>`).join('');
  // the journey picks its default sailings from the transplant records, so it waits for them
  voyageStars(v).then(() => journeyPanel(v));
  voyageClimb(v);
  drawDeck(v);
  drawExpReadings(v);
  if (v.key === 'card_census') drawCensus();
  if (v.key === 'knockout') drawKnockouts();
  if (v.key === 'induction') drawInduction(v);
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
  if (!runs.length) { document.getElementById('journeyviewA').innerHTML = '<div class="${emptyCls()}">no voyages on this expedition yet</div>'; return; }
  const opts = runs.map(r => r.run_id).join(',');
  const label = r => `${r.ship_name || r.ship || r.name} · ${r.name}`;
  if (selA.dataset.opts !== opts + v.key) {
    const list = [...runs].reverse().map(r => `<option value="${esc(r.run_id)}">${esc(label(r))}</option>`).join('');
    selA.innerHTML = list; selB.innerHTML = '<option value="">none</option>' + list; selA.dataset.opts = opts + v.key;
    // a voyage with transplants opens on a receiver beside its control (same seed); else the running sailing
    const tp = id => voyageSeries && (voyageSeries.runs.find(x => x.run_id === id) || {}).transplant;
    const roleOf = id => voyageSeries && (voyageSeries.runs.find(x => x.run_id === id) || {}).role;
    const recv = [...runs].reverse().find(r => tp(r.run_id) || roleOf(r.run_id) === 'student');
    if (!runs.some(r => r.run_id === journey.a)) journey.a = (recv || [...runs].reverse().find(r => r.status === 'running') || runs[runs.length - 1]).run_id;
    if (!runs.some(r => r.run_id === journey.b)) {
      // a receiver's control: the same seed, "lineage-ctl" for a lineage run, "control" for the rest
      const seed = recv && (recv.name.match(/-s(\d+)$/) || [])[1];
      const want = recv && /lineage/.test(recv.name) ? /lineage-ctl/ : /control/;
      const ctl = recv && runs.find(r => r.run_id !== recv.run_id && !tp(r.run_id) && want.test(r.name) && (!seed || r.name.endsWith('-s' + seed)));
      journey.b = ctl ? ctl.run_id : null;
    }
  }
  selA.value = journey.a; selB.value = journey.b || '';
  let mA, mB = null;
  try { mA = await runMetrics(journey.a); if (journey.b) mB = await runMetrics(journey.b); } catch (e) { return; }
  const steps = journeySteps(mA), slider = document.getElementById('journeystep');
  const last = Math.max(0, steps.length - 1), i = journey.idx == null ? last : Math.min(journey.idx, last), step = steps[i] ?? 0;
  slider.max = last; slider.value = i; slider.disabled = steps.length < 2;
  const jst = (await stagesFor([journey.a]))[journey.a], here = stageAt(jst, step);
  document.getElementById('journeylabel').textContent = steps.length ? `step ${step}${here ? ` · stage ${here.index + 1}: ${here.name}` : ''} · reading ${i + 1} of ${steps.length}${journey.idx == null ? ' (latest, live)' : ''}` : 'no readings yet';
  const lastStep = steps.length ? steps[steps.length - 1] : 0, segs = document.getElementById('journeystages');
  segs.hidden = !(jst && jst.length);
  if (jst && jst.length) segs.innerHTML = jst.map(s => `<span class="${here && here.index === s.index ? 'on' : ''}" style="flex:${Math.max(1, Math.min(s.last_step, lastStep) - s.first_step + 1)}" title="${esc(s.name)}: steps ${s.first_step}–${s.last_step}">${esc(s.name)}</span>`).join('');
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
  try { d = await get('/api/expedition?key=' + encodeURIComponent(v.key)); } catch (e) { return; }
  const sel = document.getElementById('voyagestar');
  voyageSeries = d;
  const keys = Object.keys(d.stars), lit = k => d.runs.some(r => r.series[k] && r.series[k].step.length);
  if (sel.dataset.voyage !== v.key) {
    const own = (d.voyage_stars || []).filter(k => d.stars[k]);
    sel.innerHTML = (own.length ? own : keys).map(k => `<option value="${k}">${esc(d.stars[k].name)}</option>`).join('');
    sel.value = own.find(lit) || own[0] || keys.find(lit) || keys[0]; sel.dataset.voyage = v.key;
  }
  const k = sel.value, star = d.stars[k], key = JSON.stringify(d.runs.map(r => r.series[k])) + k;
  if (key === voyageSeriesKey) return;
  voyageSeriesKey = key;
  const rs = d.runs.filter(r => r.series[k] && r.series[k].step.length);
  if (!rs.length) return empty('voyagestars', `no voyage on this expedition has a reading for ${esc(star.name)} yet`);
  // per run: the best single head (solid) and, where the star can be shared, the best layer's two
  // strongest heads together (dashed); either line crossing the dotted threshold is first light
  const traces = rs.flatMap((r, i) => {
    // a donor (the run heads were taken from) is dotted; a receiver says so in its name
    const col = PALETTE[i % PALETTE.length], sr = r.series[k];
    const name = `${r.ship || r.name}${{ donor: ' (donor)', receiver: ' (received heads)', teacher: ' (teacher)', student: ' (taught)' }[r.role] || ''}`;
    const t = [{ type: 'scatter', mode: 'lines', name: `${name} · one head`, legendgroup: name, x: sr.step, y: sr.value, line: { color: col, width: 1.8, dash: r.role === 'donor' || r.role === 'teacher' ? 'dot' : 'solid' } }];
    if (sr.shared_step && sr.shared_step.length) t.push({ type: 'scatter', mode: 'lines', name: `${name} · shared`, legendgroup: name,
      x: sr.shared_step, y: sr.shared_value, line: { color: col, width: 1.5, dash: 'dash' } });
    return t;
  });
  plot('voyagestars', traces,
    layout({ xaxis: { title: 'step', gridcolor: C.line }, legend: { orientation: 'h', y: 1.12 },
      yaxis: { title: `${star.name} score`, gridcolor: C.line, range: [0, Math.max(1, ...traces.flatMap(t => t.y))] },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: star.threshold, y1: star.threshold, line: { color: C.accent, dash: 'dot' } }] }));
  stagesFor(rs.map(r => r.run_id)).then(m => bandStages('#voyage', commonStages(m)));
}
document.getElementById('voyagestar').onchange = () => { voyageSeriesKey = ''; const v = voyagesData && voyagesData.find(x => x.key === voyageKey); if (v) voyageStars(v); };

// ---- Sieves (#/sieves): the three sieves from fleet.SIEVES, one sailing's heatmaps, and when each
// layer's heading settled beside the stars lit in it
let sieveDef = null, sieveRun = null, sieveKey = '';
const SETTLE_AT = 0.8, SETTLE_RECORDS = 3;
function sieveHeat(id, m, prefix, kinksByGroup, { log = true, diverging = false, msg = 'no readings for this sieve on this voyage' } = {}) {
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
    document.getElementById('sievecards').innerHTML = sieveDef.sieves.map(v => `<div class="${cardCls(false, 'card')}"><div class="top"><span class="preset">${esc(v.name)}</span>
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
    msg: run.status === 'running' && !topKeys(m, 'heading/').length ? 'the heading sieve starts with the next ship to sail; this voyage set out before it was fitted' : 'this voyage has no heading readings: the heading sieve started with ships voyage from 08:00 on 7 November' });
  stagesFor([run.run_id]).then(st => bandStages('#sievesguide', st[run.run_id]));
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
  }).join('') : '<tr><td colspan="5" class="${emptyCls(true)}">no sieve readings on this voyage yet</td></tr>';
}
document.getElementById('sievepick').onchange = e => { location.hash = '#/sieves/' + encodeURIComponent(e.target.value); };

// ---- the table (#/expeditions/<key>/table, components/TableTalk.astro): talk with a ship. Each question goes
// to POST /api/table/reply with the last exchanges of the transcript as the conversation so far; the
// answer, why it stopped and the ship's readings come back, and the exchange is kept on the far side.
let tableVoyage = 'table_talk', tableRun = null, tableLog = [], tableBusy = false;
const TABLE_HISTORY = 8;
async function loadTable() {
  document.getElementById('tableback').href = '#/expeditions/' + tableVoyage;
  const sel = document.getElementById('tablerun');
  let vs = voyagesData; if (!vs) { try { vs = await get('/api/expeditions'); } catch (e) { vs = []; } }
  let runs = runsList; if (!runs) { try { runs = runsList = await get('/api/runs'); } catch (e) { runs = []; } }
  const v = (vs || []).find(x => x.key === tableVoyage), own = v ? v.runs.filter(r => r.status === 'finished' || r.status === 'running') : [];
  const others = runs.filter(r => r.status === 'finished' && r.name && !r.name.startsWith('smoke') && !own.some(o => o.run_id === r.run_id)).reverse();
  const label = r => `${r.ship || r.name} · ${r.name}${r.preset ? ` (${r.preset})` : ''}`;
  const opts = own.map(r => r.run_id).join(',') + '|' + others.map(r => r.run_id).join(',');
  if (sel.dataset.opts !== opts) {
    sel.innerHTML = (own.length ? `<optgroup label="${esc(v ? v.name : tableVoyage)}">${own.map(r => `<option value="${esc(r.name)}">${esc(label(r))}</option>`).join('')}</optgroup>` : '')
      + `<optgroup label="any finished ship">${others.map(r => `<option value="${esc(r.name)}">${esc(label(r))}</option>`).join('')}</optgroup>`;
    sel.dataset.opts = opts;
  }
  if (!tableRun || ![...sel.options].some(o => o.value === tableRun)) tableRun = sel.options.length ? sel.options[0].value : null;
  sel.value = tableRun || '';
  await loadTranscript();
}
async function loadTranscript() {
  const status = document.getElementById('tablestatus'), input = document.getElementById('tableq');
  if (!tableRun) { status.textContent = 'no finished ship to talk with yet'; return; }
  try {
    const r = await fetch('/api/table/transcript?run=' + encodeURIComponent(tableRun));
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    tableLog = d.map(x => ({ q: x.question, a: x.answer, meta: x }));
    status.textContent = ''; input.disabled = false; document.getElementById('tableask').disabled = false;
  } catch (e) {
    tableLog = [];
    const notBuilt = /not built yet/.test(String(e.message));
    status.textContent = notBuilt ? "The table isn't open yet: the ship's side (thorp.table) is still being built. The page is ready for it." : 'could not load the transcript: ' + e.message;
    input.disabled = notBuilt; document.getElementById('tableask').disabled = notBuilt;
  }
  drawTable();
}
function drawTable(pending = null) {
  const log = document.getElementById('tablelog');
  const meta = m => !m ? '' : [m.temperature != null ? `t ${Number(m.temperature).toFixed(2)}` : '', m.seed != null ? `seed ${m.seed}` : '', m.tokens != null ? `${m.tokens} tokens` : '',
    m.seconds != null ? `${Number(m.seconds).toFixed(1)} s` : '', m.stopped ? { turn: 'stopped at the next turn', length: 'stopped at the length', eos: 'stopped at the end of text' }[m.stopped] || `stopped: ${m.stopped}` : ''].filter(Boolean).join(' · ');
  log.innerHTML = (tableLog.length || pending ? '' : '<div class="${emptyCls()}">no exchanges with this ship yet: say something below</div>')
    + tableLog.map(x => `<div class="ex"><div class="q"><b>Q:</b> ${esc(x.q)}</div><div class="a"><b>A:</b> ${esc(x.a)}</div><div class="m">${esc(meta(x.meta))}</div></div>`).join('')
    + (pending ? `<div class="ex pending"><div class="q"><b>Q:</b> ${esc(pending)}</div><div class="a"><b>A:</b> <span class="s">the ship is thinking…</span></div></div>` : '');
  log.scrollTop = log.scrollHeight;
}
function drawReadings(r) {
  const el = document.getElementById('tablereadings');
  if (!r) { el.textContent = 'no readings came back'; return; }
  // measured readings first; one the ship has no reading for shows as a dash
  const row = (k, v) => `<div class="rd${v == null ? ' none' : ''}"><span>${esc(STAR_LABEL[k] || k.replace(/_/g, ' '))}</span><b>${v == null ? '–' : typeof v === 'number' ? fmt(v) : esc(String(v))}</b></div>`;
  const order = o => Object.entries(o || {}).sort((a, b) => (a[1] == null) - (b[1] == null));
  const stars = order(r.stars), tricks = order(r.tricks);
  el.innerHTML = (stars.length ? `<div class="k">stars</div>${stars.map(([k, v]) => row(k, v)).join('')}` : '')
    + (tricks.length ? `<div class="k mt">tricks</div>${tricks.map(([k, v]) => row(k, v)).join('')}` : '') || 'no readings on this ship';
}
async function ask(question) {
  if (tableBusy || !question.trim() || !tableRun) return;
  tableBusy = true;
  const input = document.getElementById('tableq'), status = document.getElementById('tablestatus');
  input.value = ''; drawTable(question); status.textContent = '';
  const seed = document.getElementById('tableseed').value.trim();
  try {
    const r = await fetch('/api/table/reply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      run: tableRun, question, history: tableLog.slice(-TABLE_HISTORY).map(x => ({ q: x.q, a: x.a })),
      temperature: +document.getElementById('tabletemp').value, max_tokens: +document.getElementById('tablemax').value, seed: seed === '' ? null : seed }) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    tableLog.push({ q: question, a: d.answer, meta: { ...d, temperature: +document.getElementById('tabletemp').value, seed: seed === '' ? null : seed } });
    drawReadings(d.readings);
    if (d.prompt_tokens != null) status.textContent = `the ship read ${d.prompt_tokens} tokens of the conversation (step ${d.step ?? '–'})`;
  } catch (e) {
    status.textContent = /not built yet/.test(String(e.message)) ? "The table isn't open yet: the ship's side (thorp.table) is still being built." : 'no answer: ' + e.message;
    input.value = question;
  }
  tableBusy = false;
  drawTable();
}
document.getElementById('tableform').addEventListener('submit', e => { e.preventDefault(); ask(document.getElementById('tableq').value); });
document.getElementById('tablerun').onchange = e => { tableRun = e.target.value; document.getElementById('tablereadings').textContent = 'ask something to see them'; loadTranscript(); };
document.getElementById('tabletemp').oninput = e => { document.getElementById('tabletempv').textContent = (+e.target.value).toFixed(2); };

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
    const vb = cardBadge(d.card_verdicts, s.key);
    return `<div class="${cardCls(false, `card${lit.length ? ' lit' : ''}${ART_CARDS.has(s.key) ? ' playing' : ''}`)}">${cardArt(s.key)}${vb ? `<div class="vrow">${vb}</div>` : ''}
      <div class="top"><span class="preset">${esc(s.name)}</span><span class="${pillCls(state[0])}" title="lit: one head at the threshold; lit shared: the best layer's two strongest heads together">${state[1]}</span></div>
      <div class="job">level ${s.level}${s.rests_on.length ? ` · rests on ${esc(s.rests_on.map(k => byName[k] || k).join(', '))}` : ''} · lit at ${s.threshold}</div>
      <div class="ov">${esc(s.about)}</div>
      <div class="foot"><span>${first ? `first lit by ${shipLink(first)} at step ${first.steps_to_lit}` : best && best.best != null ? `nearest: ${shipLink(best)} at ${fmt(best.best)}` : 'no readings yet'}</span></div>
      ${firstShared ? `<div class="foot"><span>first lit shared by ${shipLink(firstShared)} at step ${firstShared.shared_steps_to_lit} (two heads together)</span></div>` : ''}
      <div class="foot"><span>lit on ${lit.length}${shared.length ? `, lit shared on ${shared.length},` : ''} of ${s.ships.length} voyages measured</span></div></div>`;
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
  }).join('') || '<tr><td colspan="7" class="${emptyCls(true)}">no ship has trait probes yet</td></tr>';
}
let discHeads = [], discStars = [], discTricks = [], discData = null;
// a kind of head's state in Thorp: not measured, measured without readings, lit, lit shared or best so far
function headState(h) {
  if (!h.star) return `<td data-sort="9" class="s" title="${esc(h.measure)}">not measured yet · <i>${esc(h.measure)}</i>${trickNote(h)}</td>`;
  const st = discStars.find(x => x.key === h.star);
  if (!st) return '<td data-sort="5">measured</td>';
  if (!st.ships.length) return `<td data-sort="3"><span class="${pillCls('')}">measured</span> a star: ${esc(st.name)} · readings start with the next ship to sail · threshold ${st.threshold}</td>`;
  const lit = st.ships.filter(x => x.steps_to_lit != null), sh = st.ships.filter(x => x.shared_steps_to_lit != null);
  const best = Math.max(-1, ...st.ships.map(x => x.best ?? -1));
  const pill = lit.length ? `<span class="${pillCls('good')}">lit</span>` : sh.length ? `<span class="${pillCls('accent')}">lit shared</span>` : `<span class="${pillCls('')}">not lit yet</span>`;
  return `<td data-sort="${lit.length ? 0 : sh.length ? 1 : 2}">${pill} a star: ${esc(st.name)} · ${lit.length ? `lit on ${lit.length}` : sh.length ? `lit shared on ${sh.length}` : `best ${fmt(best)}`} of ${st.ships.length} sailings · threshold ${st.threshold}${trickNote(h)}</td>`;
}
// Thorp's progress on a trick: the smallest class that performed it, else the best reading so far
function trickProgress(kt) {
  const t = kt.fleet && discTricks.find(x => x.key === kt.fleet);
  if (!kt.fleet) return { cell: '<td data-sort="9" class="s">not measured yet</td>', state: 'not measured yet', cls: '' };
  if (t && t.viable === false) return { cell: '<td data-sort="10" class="s">not viable on Gutenberg in English</td>', state: 'not viable', cls: '' };
  if (t && !t.evaluator) return { cell: `<td data-sort="8" class="s">pre-registered${t.cutoff ? ` (cutoff ${t.cutoff})` : ''} · evaluator not built yet</td>`, state: 'pre-registered', cls: '' };
  if (!t || !t.ships.length) return { cell: '<td data-sort="8" class="s">measured · readings start with the next ship to sail</td>', state: 'measured, no readings yet', cls: '' };
  const done = t.ships.filter(x => x.performed_at != null).sort((a, b) => classRank(a.preset) - classRank(b.preset) || a.performed_at - b.performed_at);
  if (done.length) { const x = done[0]; return { cell: `<td data-sort="${classRank(x.preset)}"><span class="${pillCls('good')}">performed</span> at ${classLink(x.preset)} by ${shipLink(x)}, step ${x.performed_at}</td>`, state: 'performed', cls: 'good' }; }
  const best = [...t.ships].sort((a, b) => b.best - a.best)[0];
  return { cell: `<td data-sort="7"><span class="${pillCls('')}">not yet</span> best ${fmt(best.best)} of ${t.threshold} (${classLink(best.preset)})</td>`, state: 'not performed yet', cls: '' };
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
      <div class="gt">${gates.map(t => `<a href="#/discoveries/${esc(t.key)}">◆ ${esc(t.name)}</a>`).join('')}${mine.filter(t => t.leads_to).map(t => `<a class="ld" href="#/discoveries/${esc(t.key)}" title="leads to ${esc((kts.find(x => x.key === t.leads_to) || {}).name || t.leads_to)}">↗ ${esc(t.name)}</a>`).join('')}</div><div class="ct">${mine.length} tricks</div></div>`;
  }).join('<div class="arrow">→</div>');
  // the size bands present, smallest first
  const bands = [...new Map(kts.map(t => [t.field_band_rank, t.field_band])).entries()].sort((a, b) => a[0] - b[0]);
  if (bandSel.options.length !== bands.length + 1) { const was = bandSel.value; bandSel.innerHTML = '<option value="">any size</option>' + bands.map(([r, b]) => `<option value="${r}">${esc(b)}</option>`).join(''); bandSel.value = was; }
  const rows = kts.filter(t => (!sel.value || t.waypoint === sel.value) && (bandSel.value === '' || String(t.field_band_rank) === bandSel.value))
    .sort((a, b) => wpRank(a.waypoint) - wpRank(b.waypoint) || a.field_band_rank - b.field_band_rank);
  const heads = Object.fromEntries((discData.known_heads || []).map(h => [h.key, h.name]));
  document.getElementById('trickcount').textContent = `${rows.length} tricks · ${rows.filter(t => t.fleet).length} measured by Thorp`;
  document.querySelector('#tricktable tbody').innerHTML = rows.map(t => `<tr data-trick="${esc(t.key)}" tabindex="0"${t.fleet ? ' class="measured"' : ''}>
    <td data-sort="${wpRank(t.waypoint)}">${esc(wpName(t.waypoint))}</td><td><b>${t.gate ? '◆ ' : ''}${esc(t.name)}</b>${t.taught ? ' <span class="s">(taught)</span>' : ''}${leadNote(t, kts)}</td><td>${esc(t.does)}</td><td data-sort="${t.field_params}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td><td class="s">${esc(t.sure)}</td>
    <td>${t.stars.length ? esc(t.stars.map(k => heads[k] || k).join(', ')) : '<span class="s">none charted yet</span>'}</td>
    ${trickProgress(t).cell}<td data-sort="${t.target_class ? classRank(t.target_class) : 99}">${t.target_class ? classLink(t.target_class) : t.taught ? '<span class="s">a reference: taught, not read</span>' : trickProgress(t).state === 'not viable' ? '<span class="s">not viable</span>' : '<span class="s">beyond the ladder</span>'}</td></tr>`).join('');
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
  document.getElementById('trickstate').innerHTML = `<span class="${pillCls(p.cls)}">${esc(p.state)}</span>`;
  document.getElementById('trickdoes').textContent = t.does;
  const tgt = t.target_class && classOf(t.target_class);
  const wp = (discData.waypoints || []).find(w => w.key === t.waypoint), tname = Object.fromEntries((discData.known_tricks || []).map(x => [x.key, x.name]));
  document.getElementById('trickover').innerHTML = [
    ['waypoint', `${esc(wp ? wp.name : t.waypoint)}${t.gate ? ' · <b>◆ a gate</b>: performed before a ship moves on' : ' · a milestone'}`],
    ['rests on', t.rests_on.length ? t.rests_on.map(k => `<a href="#/discoveries/${esc(k)}">${esc(tname[k] || k)}</a>`).join(', ') : '–'],
    ...(leadNote(t, discData.known_tricks || []) ? [['leads', leadNote(t, discData.known_tricks || [])]] : []),
    ...(() => { const ch = ((discData.chain_rungs || {}).chains || []).find(c => c.includes(t.key) || c.includes(t.fleet)); if (!ch) return [];
      const end = ch[ch.length - 1], en = (discData.known_tricks || []).find(x => x.key === end || x.fleet === end);
      return [['the climb', `${ch.indexOf(t.fleet || t.key) === ch.length - 1 ? '' : `step ${ch.indexOf(t.fleet || t.key) + 1} of ${ch.length} on `}<a href="#/discoveries/chains/${esc(end)}"><b>${esc(en ? en.name : end)}</b>: the climb, step by step</a>`]]; })(),
    ['the field shows it at', `<span class="sizeband">${esc(t.field_band)}</span> parameters · ${esc(t.field_at)} <span class="s">(${esc(t.sure)})</span>`], ['in', esc(t.field_models)], ['first shown by', `<span class="s">${esc(t.source)}</span>`],
    ["Thorp's goal class", t.target_class ? `${classLink(t.target_class)}${tgt ? ` · ${big(tgt.total)} parameters` : ''}` : t.taught ? 'none: the field shows it only when taught the task' : 'beyond the ladder: a horizon'],
    ['how Thorp measures it', ft ? `<span class="mono">${esc(ft.metric)}</span>, performed at ${ft.threshold}` : `not yet: ${esc(t.measure)}`],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  // the stars needed
  const hs = t.stars.map(k => (discData.known_heads || []).find(h => h.key === k)).filter(Boolean), byKey = Object.fromEntries((discData.known_heads || []).map(h => [h.key, h.name]));
  document.querySelector('#trickstars tbody').innerHTML = hs.length ? hs.map(h => `<tr><td><b>${esc(h.name)}</b></td><td>${esc(h.does)}</td>
    <td>${h.rests_on.length ? esc(h.rests_on.map(k => byKey[k] || k).join(', ')) : '–'}</td>
    <td data-sort="${classRank(h.expected_from)}">${h.expected_from ? classLink(h.expected_from) : 'beyond the ladder'}</td>${firstLitIn(h)}${headState(h)}</tr>`).join('')
    : '<tr><td colspan="6" class="${emptyCls(true)}">no kind of head is charted for this trick yet; it may be done in the feed-forward layers, or by heads not yet described</td></tr>';
  // class by class
  const thr = ft ? ft.threshold : null;
  document.querySelector('#tricktrack tbody').innerHTML = (ladderData ? ladderData.rungs : []).map(r => {
    const mine = ft ? ft.ships.filter(x => x.preset === r.preset) : [], done = mine.filter(x => x.performed_at != null).sort((a, b) => a.performed_at - b.performed_at);
    const orders = t.field_params ? Math.log10(t.field_params / r.total) : null, best = mine.length ? Math.max(...mine.map(x => x.best)) : null, isT = r.preset === t.target_class;
    return `<tr${isT ? ' class="target"' : ''}><td>${classLink(r.preset)}${isT ? ` <span class="${pillCls('accent')}">target</span>` : ''}</td><td data-sort="${r.total}">${big(r.total)}</td>
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
  trickChart('trickchart', d, t);
  // the partner beside it: the bigger test a smaller one leads to, or the smaller one that leads here
  const partner = t.leads_to || ((discData.known_tricks || []).find(x => x.leads_to === t.key) || {}).key;
  const pt = partner && (discData.known_tricks || []).find(x => x.key === partner);
  document.getElementById('trickpairpanel').hidden = !pt;
  if (!pt) return;
  document.getElementById('trickpairtitle').innerHTML = `${t.leads_to ? 'It leads to' : 'Led by'} <a href="#/discoveries/${esc(pt.key)}">${esc(pt.name)}</a> <span class="note">${t.leads_to ? 'the bigger test this one tracks, on the same evaluator and scale' : 'the smaller test that tracks this one, on the same evaluator and scale'}</span>`;
  const pf = pt.fleet && discTricks.find(x => x.key === pt.fleet);
  if (!pf) return empty('trickpairchart', 'not measured yet');
  if (pf.viable === false) return empty('trickpairchart', 'not viable on Gutenberg in English');
  if (!pf.evaluator) return empty('trickpairchart', `pre-registered${pf.cutoff ? ` (cutoff ${pf.cutoff})` : ''}; its evaluator is not built yet`);
  try { trickChart('trickpairchart', await get('/api/trick?key=' + encodeURIComponent(pf.key)), pt); } catch (e) { empty('trickpairchart', 'could not load it'); }
}
// one measured trick, every sailing's reading by step: the threshold (amber), the floor (grey: the
// highest untrained reading among the sailings) and outside models' readings (labelled), dotted
function trickChart(id, d, t) {
  if (!d.runs.length) return empty(id, 'readings start with the next ship to sail');
  const presets = ladderData.rungs.map(r => r.preset), floors = d.runs.map(r => r.floor).filter(v => v != null);
  const refs = Object.entries(t.reference || {}), line = (y, color, dash = 'dot') => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color, dash } });
  const label = (y, text, color) => ({ xref: 'paper', x: 1, xanchor: 'right', y, yanchor: 'bottom', showarrow: false, text, font: { size: 10, color } });
  const floor = floors.length ? Math.max(...floors) : null;
  plot(id, d.runs.map(r => ({ type: 'scatter', mode: 'lines+markers', name: `${r.ship || r.name} (${r.preset})`, legendgroup: r.preset, x: r.step, y: r.value,
    line: { color: PALETTE[presets.indexOf(r.preset) % PALETTE.length], width: 1.4 }, marker: { size: 7 }, hovertemplate: `${esc(r.ship || r.name)}: %{y:.3f} at step %{x}<extra></extra>` })),
    layout({ showlegend: d.runs.length <= 12, xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: esc(t.name), gridcolor: C.line, zeroline: true, zerolinecolor: C.line },
      shapes: [line(d.threshold, C.accent), ...(floor != null ? [line(floor, C.muted)] : []), ...refs.map(([, v], i) => line(v, PALETTE[(i + 4) % PALETTE.length], 'dash'))],
      annotations: [label(d.threshold, `performed at ${d.threshold}`, C.accent), ...(floor != null ? [label(floor, `floor ${fmt(floor)}`, C.muted)] : []),
        ...refs.map(([n, v], i) => label(v, `${esc(n)} ${fmt(v, 2)}`, PALETTE[(i + 4) % PALETTE.length]))] }));
}
// the discovery chains: each bettor test reached in rungs, one per class (leads_to from the speller's
// tests up); rows are the chains, columns the rungs, each cell every class's best lift on that rung
// one rung's evidence, class by class (the chains table and the chain pages): the best lift and best share of pairs
// right, ✓ performed under the share rule, ▲ passed below its class, ⚠ while a bigger class fails it; opts.floor adds
// the floor (the highest untrained reading)
function rungEvidence(t, ft, rank, opts = {}) {
  const thr = ft ? ft.threshold : 0.1;
  let body;
  if (!ft || (!ft.evaluator && !ft.ships.length)) body = `<div class="s">${ft && ft.viable === false ? 'not viable' : ft ? 'evaluator not built yet' : 'not measured'}</div>`;
  else if (!ft.ships.length) body = '<div class="s">no readings yet</div>';
  else {
    // per class: the best lift, its best share of pairs right, and whether any sailing performed it under the
    // share rule (lift at the threshold and share at min_score at the same reading; the server's performed_at)
    const by = {};
    for (const x of ft.ships) {
      const b = by[x.preset] || (by[x.preset] = { best: -Infinity, share: null, done: false });
      b.best = Math.max(b.best, x.best); b.done = b.done || x.performed_at != null;
      if (x.best_share != null) b.share = Math.max(b.share ?? 0, x.best_share);
      if (x.floor != null) b.floor = Math.max(b.floor ?? -Infinity, x.floor);
    }
    // a class that performs a rung set for a bigger class has passed below its class; when a bigger class was
    // measured on it and did not perform it, the pair set wants auditing (DECISIONS.md, "The share rule")
    const goal = rank(t.target_class);
    const failedAbove = p => Object.entries(by).some(([q, b]) => rank(q) > rank(p) && !b.done);
    body = Object.entries(by).sort((a, b) => rank(a[0]) - rank(b[0])).map(([p, b]) => {
      const below = b.done && rank(p) < goal, audit = below && failedAbove(p);
      const why = b.done ? (audit ? 'passed below its class while a bigger class fails it: audit the pairs' : below ? 'passed below its class' : 'performed')
        : b.best >= thr ? `lift at the mark but ${b.share != null ? Math.round(100 * b.share) + '%' : 'too few'} of pairs right, under ${Math.round(100 * (ft.min_score || 0))}%` : 'not performed';
      return `<div class="cr${b.done ? ' lit' : ''}${audit ? ' audit' : ''}" title="${esc(why)}"><span>${esc(p)}</span><b>${b.best >= 0 ? '+' : ''}${fmt(b.best, 2)}${b.share != null ? ` <i>${Math.round(100 * b.share)}%</i>` : ''}${b.done ? ' ✓' : ''}${below ? (audit ? ' ⚠' : ' ▲') : ''}</b>${opts.floor ? `<em>${b.floor != null ? `floor ${b.floor >= 0 ? '+' : ''}${fmt(b.floor, 2)}` : ''}</em>` : ''}</div>`;
    }).join('');
  }
  return body;
}
// ---- grading (fleet.grading, data/compare/chain-grades.json): does a chain get harder as it climbs, judged on many models
// at once. Graded: no model performs a rung while failing one below it, no rung is performed by more models than the
// one below, and every rung is performed by some model. The reference ladder (Pythia 14m to 410m, Qwen3 0.6B) is
// shown beside Thorp's classes when the toggle is on; it is a per-viewer choice, remembered.
let chainRef = false;
try { chainRef = localStorage.getItem('thorp.chainref') === 'on'; } catch (e) {}
function chainRefToggle(id, redraw) {
  const el = document.getElementById(id); if (!el) return;
  el.checked = chainRef;
  el.onchange = () => { chainRef = el.checked; try { localStorage.setItem('thorp.chainref', chainRef ? 'on' : 'off'); } catch (e) {} redraw(); };
}
function gradeNote(g, nameOf, full) {
  if (!g) return `<span class="${pillCls('')}" title="no grading written yet (data/compare/chain-grades.json)">not graded yet</span>`;
  if (g.graded) return `<span class="${pillCls('good')}" title="harder at every rung: no model passes a rung it fails below, fewer pass each rung, and every rung is reached">graded</span>`;
  const bits = [];
  if (g.inversions.length) bits.push(`${g.inversions.length} inversion${g.inversions.length > 1 ? 's' : ''}`);
  if (g.rising.length) bits.push(`more pass ${g.rising.map(nameOf).join(', ')} than the rung below`);
  if (g.unreached.length) bits.push(`${g.unreached.map(nameOf).join(', ')} unreached`);
  const tip = g.inversions.map(x => `${x.model} performs ${nameOf(x.rung)} but fails ${x.fails_below.map(nameOf).join(', ')}`).join('\n');
  return `<span class="${pillCls('bad')}" title="${esc(tip)}">not graded</span> <span class="gnote">${esc(bits.join(' · '))}</span>`
    + (full && g.inversions.length ? `<details class="ginv"><summary>the inversions</summary><ul>${g.inversions.map(x => `<li><b>${esc(x.model)}</b> performs ${esc(nameOf(x.rung))} but fails ${esc(x.fails_below.map(nameOf).join(', '))}</li>`).join('')}</ul></details>` : '');
}
// the reference ladder's readings on one rung, as evidence rows; without the toggle, the one reference tricks.py names
function refRows(key, refs, ref, sign) {
  if (chainRef && refs && refs.length) return refs.map(m => {
    const v = m.tricks[key];
    if (!v) return `<div class="cr ref"><span>${esc(m.short)}</span><b>–</b></div>`;
    return `<div class="cr ref${v.performed ? ' lit' : ''}"><span>${esc(m.short)}</span><b>${sign(v.lift)}${v.score != null ? ` <i>${Math.round(100 * v.score)}%</i>` : ''}${v.performed ? ' ✓' : ''}</b></div>`;
  }).join('');
  return ref ? `<div class="cr ref"><span>${esc(ref[0])}</span><b>${sign(ref[1])}</b></div>` : '';
}
const signed = v => v == null ? '–' : `${v >= 0 ? '+' : ''}${fmt(v, 2)}`;
function drawChains() {
  const kts = discData.known_tricks || [], byKey = Object.fromEntries(kts.map(t => [t.key, t]));
  const led = new Set(kts.map(t => t.leads_to).filter(Boolean));
  const chains = kts.filter(t => t.leads_to && !led.has(t.key)).map(start => { const c = [start]; let t = start; while (t.leads_to && byKey[t.leads_to]) { t = byKey[t.leads_to]; c.push(t); } return c; });
  const tb = document.getElementById('chaintable');
  chainRefToggle('chainrefidx', drawChains);
  if (!chains.length) { tb.tHead.innerHTML = ''; tb.tBodies[0].innerHTML = '<tr><td class="${emptyCls(true)}">no chains yet</td></tr>'; return; }
  // the columns are the classes the chains' rungs belong to, smallest first, so a chain that starts at the keel and one
  // that starts at the speller line up class by class; the longest chains are featured first
  const presets = ladderData ? ladderData.rungs.map(r => r.preset) : [];
  const rank = p => { const i = presets.indexOf(p); return i < 0 ? 99 : i; };
  const cols = [...new Set(chains.flat().map(t => t.target_class).filter(Boolean))].sort((a, b) => rank(a) - rank(b));
  // the chains in the order fleet.chains() gives (Origin, energy, Mendeleev's gaps, the eternal return); any it
  // does not name follow, longest first
  const cr = discData.chain_rungs || {}, order = (cr.chains || []).map(c => c[c.length - 1]);
  const pos = c => { const i = order.indexOf(c[c.length - 1].fleet || c[c.length - 1].key); return i < 0 ? 99 : i; };
  chains.sort((a, b) => pos(a) - pos(b) || b.length - a.length);
  tb.tHead.innerHTML = `<tr><th>leads to</th>${cols.map((p, i) => `<th>rung ${i + 1} · ${classLink(p)}</th>`).join('')}</tr>`;
  tb.tBodies[0].innerHTML = chains.map(c => {
    const end = c[c.length - 1], at = Object.fromEntries(c.map(t => [t.target_class, t]));
    const chainKey = end.fleet || end.key, hasPage = (cr.chains || []).some(x => x[x.length - 1] === chainKey);
    const nameOf = k => (byKey[k] || {}).name || k;
    return `<tr><td>${hasPage ? `<a href="#/discoveries/chains/${esc(chainKey)}"><b>${esc(end.name)}</b></a>` : `<b>${esc(end.name)}</b>`}<div class="grade">${gradeNote((cr.grades || {})[chainKey], nameOf)}</div>${hasPage ? '<div class="s">the climb, step by step →</div>' : ''}</td>${cols.map(p => at[p]).map(t => {
      if (!t) return '<td class="none"><div class="s">no rung</div></td>';
      const ft = t.fleet && discTricks.find(x => x.key === t.fleet), ref = Object.entries(t.reference || {})[0];
      const body = rungEvidence(t, ft, rank);
      return `<td><a href="#/discoveries/${esc(t.key)}"><b>${esc(t.name)}</b></a>${body}${refRows(t.fleet || t.key, cr.reference, ref, signed)}</td>`;
    }).join('')}</tr>`;
  }).join('')
  // what a model at each rung is, according to the chains (fleet.RUNGS)
  + ((cr.rungs || []).length ? `<tr class="rungsum"><td><b>What a model at this rung is</b></td>${cols.map(p => {
      const r = cr.rungs.find(x => x.preset === p);
      return r ? `<td><b>${esc(r.title)}</b><div class="s">${esc(r.summary)}</div></td>` : '<td></td>';
    }).join('')}</tr>` : '');
}
function drawDiscoveryView() { if (discView === 'index' && discSub === 'stars') { drawBridge(); drawStarGrid(); } if (discView === 'index') { drawChains(); drawTricks(); if (discSub === 'two-facts') drawTwoFacts(); } if (discView === 'trick') drawTrickPage(); if (discView === 'chain') drawChainPage(); }

// ---- One chain (#/discoveries/chains/<key>): a bettor's test told as a climb, keel to bettor (fleet.CHAINS). The copy is
// fleet's; the evidence per class is /api/discoveries' (as in the chains table), the pairs and per-pair lifts /api/chain's.
const chainCache = new Map();
async function drawChainPage() {
  const key = discChain, el = document.getElementById('chainsteps');
  let d = chainCache.get(key);
  if (!d) {
    try { d = await get('/api/chain?key=' + encodeURIComponent(key)); } catch (e) { d = null; }
    if (!d || !d.steps) {
      document.getElementById('chaintitle').textContent = `no chain called ${key}`;
      ['chainstrand', 'chainover'].forEach(id => { document.getElementById(id).innerHTML = ''; });
      el.innerHTML = '<div class="${emptyCls()}">the chains are the bettor\'s four tests; <a href="#/discoveries">back to the chains table</a></div>'; return;
    }
    chainCache.set(key, d);
  }
  if (discChain !== key) return;
  document.getElementById('chaintitle').textContent = d.name;
  document.getElementById('chainstrand').innerHTML = `<span class="${pillCls('accent')}">${esc(d.strand)}</span>`;
  document.getElementById('chainover').innerHTML = [
    ['the idea', esc(d.idea)], ['found by', esc(d.found)],
    ['the library', `${esc(d.shelf)}${d.cutoff ? ` <span class="s">(cutoff ${d.cutoff})</span>` : ''}`],
    ['the climb', `${d.steps.length} steps, one per class, each resting on the one before; step ${d.steps.length} is the bet itself`],
    ['the grade', `${gradeNote(d.grade, k => (d.steps.find(x => x.key === k) || {}).name || k, true)}${d.grade ? `<div class="s">of the ${d.graded_on.length} models read, how many perform each rung: ${d.steps.filter(x => d.grade.counts[x.key] != null).map(x => `${esc(x.name)} <b>${d.grade.counts[x.key]}</b>`).join(' → ')}</div>` : ''}`],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  chainRefToggle('chainrefpage', drawChainPage);
  const kts = discData.known_tricks || [], presets = ladderData ? ladderData.rungs.map(r => r.preset) : [];
  const rank = p => { const i = presets.indexOf(p); return i < 0 ? 99 : i; };
  const sign = v => v == null ? '–' : `${v >= 0 ? '+' : ''}${fmt(v, 2)}`;
  el.innerHTML = d.steps.map((st, i) => {
    const t = kts.find(x => x.key === st.key) || { key: st.key, name: st.name, target_class: st.rung && st.rung.preset };
    const ft = discTricks.find(x => x.key === st.key), r = st.rung || {}, ref = Object.entries(t.reference || st.reference || {})[0];
    const last = i === d.steps.length - 1;
    // the pairs, with each class's best sailing on this test marked right (lift above zero) or wrong, pair by pair
    const best = {};
    for (const x of st.runs) if (x.preset && (!best[x.preset] || (x.lift ?? -9) > (best[x.preset].lift ?? -9))) best[x.preset] = x;
    const cls = Object.keys(best).sort((a, b) => rank(a) - rank(b));
    // a pair with a frame reads premise / frame: the lift is what the premise adds over the frame alone
    const passage = p => p.frame && p.prompt.endsWith(p.frame) && p.prompt.length > p.frame.length
      ? `${esc(p.prompt.slice(0, p.prompt.length - p.frame.length).trimEnd())} <span class="pfsep">/</span> <span class="pframe">${esc(p.frame)}</span> …`
      : `${esc(p.prompt)} …`;
    const row = (p, j) => `<tr><td class="pq">${passage(p)}</td><td class="pi">${esc(p.idea)}</td><td class="pr">${esc(p.rival)}</td>${cls.map(c => {
      const v = best[c].pairs[j]; return v == null ? '<td>–</td>' : `<td class="${v > 0 ? 'pok' : 'pno'}" title="${esc(best[c].name)}: lift ${sign(v)}">${v > 0 ? '✓' : '✗'}</td>`;
    }).join('')}</tr>`;
    const head = `<thead><tr><th>the passage</th><th>the idea</th><th>its rival</th>${cls.map(c => `<th title="${esc(best[c].name)}">${esc(c)}</th>`).join('')}</tr></thead>`;
    const pairs = st.pairs && st.pairs.length
      ? `<div class="scroll"><table class="pairs" data-nosort>${head}<tbody>${st.pairs.slice(0, 6).map(row).join('')}</tbody></table></div>`
        + (st.pairs.length > 6 ? `<details><summary>all ${st.pairs.length} pairs</summary><div class="scroll"><table class="pairs" data-nosort>${head}<tbody>${st.pairs.map(row).join('')}</tbody></table></div></details>` : '')
      : `<div class="${emptyCls()}">pairs not written yet${st.pairs_file ? ` (<span class="mono">${esc(st.pairs_file)}</span>)` : ''}</div>`;
    return `<section class="${cardCls(false, "panel cstep${last ? ' bet' : ''}")}">
      <div class="cnum">${i + 1}</div>
      <div class="cbody">
        <div class="crung">${r.preset ? classLink(r.preset) : ''}${r.title ? ` · <b>${esc(r.title)}</b>` : ''}</div>
        <h2><a href="#/discoveries/${esc(st.key)}">${esc(st.name)}</a></h2>
        <p class="cadds">${esc(st.adds)}</p>
        ${last && st.about ? `<p class="s">${esc(st.about)}</p>` : ''}
        <div class="row cev">
          <div class="cevid"><div class="k">class by class <span class="s">best lift · share right · floor</span></div>${rungEvidence(t, ft, rank, { floor: true })}
            ${refRows(st.key, d.reference, ref, sign)}
            <div class="s">performed at lift ${st.threshold ?? '–'}${st.min_score != null ? ` and ${Math.round(100 * st.min_score)}% of pairs right` : ''}, at the same reading</div></div>
          <div class="cpairs"><div class="k">the pairs <span class="s">each class's best voyage, ✓ where it bets on the idea${st.pairs && st.pairs.some(p => p.frame) ? '; premise / <b>frame</b>: the lift is what the premise adds over the frame alone' : ''}</span></div>${pairs}</div>
        </div>
      </div></section>`;
  }).join('');
}
// the trick a kind of head performs, if measured: performed or not, on how many sailings
const trickNote = h => {
  const t = h.trick && discTricks.find(x => x.key === h.trick);
  if (!t) return '';
  const n = t.ships.filter(x => x.performed_at != null).length;
  return `<br><span class="s">its trick, ${esc(t.name)}: ${t.ships.length ? `performed on ${n} of ${t.ships.length} sailings` : 'readings start with the next ship to sail'}</span>`;
};
// classes in ladder order, smallest first; a kind beyond the ladder ranks after them all
const classRank = p => { const i = ladderData && ladderData.rungs ? ladderData.rungs.findIndex(r => r.preset === p) : -1; return i < 0 ? 99 : i; };
// the smallest class where any sailing has lit a measured kind (one head first, else shared)
function firstLitIn(h) {
  const st = h.star && discStars.find(x => x.key === h.star);
  if (!st) return '<td data-sort="99">–</td>';
  const lit = st.ships.filter(x => x.steps_to_lit != null || x.shared_steps_to_lit != null).sort((a, b) => classRank(a.preset) - classRank(b.preset));
  if (!lit.length) return '<td data-sort="98" class="s">not lit yet</td>';
  const x = lit[0], below = classRank(x.preset) < classRank(h.expected_from);
  return `<td data-sort="${classRank(x.preset)}">${classLink(x.preset)} · ${x.steps_to_lit != null ? 'lit' : 'lit shared'} by ${shipLink(x)}${below ? ` <span class="${pillCls('good')}" title="lit below the class expected to reach it">below expectation</span>` : ''}</td>`;
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
    if (ft && ft.viable === false) return { text: 'not viable on Gutenberg in English', done: false };
    if (ft && !ft.evaluator) return { text: `pre-registered${ft.cutoff ? ` (cutoff ${ft.cutoff})` : ''} · evaluator not built yet`, done: false };
    const mine = ft ? ft.ships.filter(x => x.preset === r.preset) : [];
    if (!mine.length) return { text: 'measured · no voyage of this class has a reading yet', done: false };
    const done = mine.filter(x => x.performed_at != null), best = Math.max(...mine.map(x => x.best));
    return { text: done.length ? `on ${done.length} of ${mine.length} sailings` : `best ${fmt(best)} of ${ft.threshold} on ${mine.length} sailings`, done: done.length > 0, best };
  };
  const goals = kts.filter(t => where(t) === 'mine'), carried = kts.filter(t => where(t) === 'below');
  const level = goals.length ? wps[Math.max(...goals.map(t => wpRank(t.waypoint)))] : null;
  const ceiling = level ? goals.filter(t => t.waypoint === level.key) : [];
  const nextCls = ladderData.rungs[me + 1], nextGoals = nextCls ? kts.filter(t => t.target_class === nextCls.preset) : [];
  const done = goals.filter(t => onClass(t).done).length;
  const cov = coverage(reachData, r.preset), filled = cov.reduce((n, c) => n + c.here, 0), inh = cov.reduce((n, c) => n + c.inherited, 0), all = cov.reduce((n, c) => n + c.total, 0);
  document.getElementById('goalcoverage').innerHTML = cov.map((c, i) => `<div class="crow"><span class="cname">${i + 1}. ${esc(c.name)}</span>${coverageBar(c)}
    <span class="cnum">${c.here} here${c.inherited ? ` · ${c.inherited} inherited` : ''} · ${c.open} open of ${c.total}</span></div>`).join('')
    + `<div class="crow total"><span class="cname">the route</span>${coverageBar({ here: filled, inherited: inh, open: all - filled - inh, total: all })}<span class="cnum">${filled} here · ${inh} inherited · ${all - filled - inh} open of ${all}</span></div>`;
  document.getElementById('goalsover').innerHTML = [
    ['the goal', 'as many tricks as it can learn, building on all the tricks below it, carried up to the next class'],
    ['expected at this size', level ? `<b>${esc(level.name)}</b> (step ${wpRank(level.key) + 1} of ${wps.length})` : 'nothing from books at this size'],
    ['the expected edge', ceiling.length ? ceiling.map(t => `<a href="#/discoveries/${esc(t.key)}">${t.gate ? '◆ ' : ''}${esc(t.name)}</a>`).join(', ') + '<br><span class="s">where a ship this size is expected to stop; beyond it is pushing the envelope</span>' : '–'],
    ['filled so far', `${filled} of ${all} tricks performed here${inh ? `, ${inh} more inherited to carry up` : ''} · ${done} of the ${goals.length} the field expects`],
    ['carried up', carried.length ? `${carried.length} expected of smaller classes, kept, not relearned` : 'none: the first class on the ladder; everything it learns is carried up'],
    ['next class', nextCls ? `${classLink(nextCls.preset)} takes over with ${nextGoals.length}: ${nextGoals.slice(0, 4).map(t => esc(t.name)).join(', ')}${nextGoals.length > 4 ? '…' : ''}` : 'the top of the ladder; beyond it, the horizon'],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  // the route, bottom (reading) to top (discovery)
  document.getElementById('goalroute').innerHTML = [...wps].reverse().map(w => {
    const ts = kts.filter(t => t.waypoint === w.key).sort((a, b) => (a.target_class ? classRank(a.target_class) : 99) - (b.target_class ? classRank(b.target_class) : 99));
    const isLevel = level && level.key === w.key;
    return `<div class="wp${isLevel ? ' level' : ''}"><div class="wpname">${wpRank(w.key) + 1}. ${esc(w.name)}${isLevel ? ` <span class="${pillCls('accent')}">target level</span>` : ''}</div>
      <div class="chips">${ts.map(t => { const s = where(t), st = s === 'mine' || s === 'below' ? onClass(t) : null;
        const tip = `${t.name}: ${s === 'mine' ? 'a goal of this class' : s === 'below' ? `carried up from ${t.target_class}` : s === 'above' ? `a goal of ${t.target_class}` : s === 'taught' ? 'a reference, taught not read' : 'beyond the ladder'}${st ? ' · ' + st.text : ''}`;
        return `<a class="chip ${s}${st && st.done ? ' done' : ''}" href="#/discoveries/${esc(t.key)}" title="${esc(tip)}">${t.gate ? '◆ ' : ''}${esc(t.name)}${st && st.done ? ' ✓' : ''}${s === 'above' ? ` <span class="cls">${esc(t.target_class)}</span>` : ''}</a>`; }).join('')}</div></div>`;
  }).join('');
  fillStepFilter(document.getElementById('goalfilter'), wps);
  const gf = document.getElementById('goalfilter').value, shown = goals.filter(t => !gf || t.waypoint === gf);
  document.querySelector('#goaltable tbody').innerHTML = shown.length ? shown.sort((a, b) => wpRank(a.waypoint) - wpRank(b.waypoint)).map(t => {
    const st = onClass(t);
    return `<tr data-trick="${esc(t.key)}" tabindex="0"><td><b>${esc(t.name)}</b>${leadNote(t, kts)}</td><td data-sort="${wpRank(t.waypoint)}">${esc((wps.find(w => w.key === t.waypoint) || {}).name)}</td>
      <td>${t.gate ? '◆ gate' : 'milestone'}</td><td>${t.rests_on.length ? esc(t.rests_on.map(k => tname[k] || k).join(', ')) : '–'}</td>
      <td data-sort="${t.field_params ?? ''}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td>
      <td>${st.done ? `<span class="${pillCls('good')}">performed</span> ` : ''}${esc(st.text)}</td></tr>`;
  }).join('') : `<tr><td colspan="6" class="${emptyCls(true)}">${goals.length ? 'none of this class\'s goals at this step' : 'no goals set for this class yet'}</td></tr>`;
}
// ---- coverage of the route (UI.md, "Filling the seven steps"): for a class and a step, the tricks its
// sailings performed (here), those performed only by a smaller class (inherited: carried up, still to
// show here) and the rest (open). Only measured tricks can be performed; the rest count as open.
function coverage(data, preset) {
  const kts = data.known_tricks || [], wps = data.waypoints || [], me = classRank(preset);
  const performedBy = t => { const ft = t.fleet && (data.tricks || []).find(x => x.key === t.fleet); return ft ? ft.ships.filter(x => x.performed_at != null).map(x => x.preset) : []; };
  return wps.map(w => {
    const ts = kts.filter(t => t.waypoint === w.key && !t.taught);
    let here = 0, inherited = 0;
    for (const t of ts) {
      const by = performedBy(t);
      if (by.includes(preset)) here++;
      else if (by.some(p => classRank(p) < me)) inherited++;
    }
    return { key: w.key, name: w.name, total: ts.length, here, inherited, open: ts.length - here - inherited };
  });
}
const coverageBar = c => `<span class="cbar" title="${c.here} performed here, ${c.inherited} inherited, ${c.open} open, of ${c.total}">${
  [['here', c.here], ['inherited', c.inherited], ['open', c.open]].map(([k, n]) => n ? `<i class="${k}" style="flex:${n}"></i>` : '').join('')}</span>`;
async function routeCoverage() {
  if (!reachData || Date.now() - reachAt > 30000) { try { reachData = await get('/api/discoveries'); reachAt = Date.now(); } catch (e) { return; } }
  const wps = reachData.waypoints || [];
  const tb = document.getElementById('coveragetable');
  tb.tHead.innerHTML = `<tr><th>class</th>${wps.map((w, i) => `<th>${i + 1}. ${esc(w.name)}</th>`).join('')}<th>the route</th></tr>`;
  tb.tBodies[0].innerHTML = ladderData.rungs.map(r => {
    const cov = coverage(reachData, r.preset), tot = cov.reduce((a, c) => ({ total: a.total + c.total, here: a.here + c.here, inherited: a.inherited + c.inherited, open: a.open + c.open }), { total: 0, here: 0, inherited: 0, open: 0 });
    return `<tr><td>${classLink(r.preset)}</td>${cov.map(c => `<td><a class="ccell" href="#${modelHash(r, 'goals')}">${c.here}${c.inherited ? `<span class="inh">+${c.inherited}</span>` : ''} <span class="s">of ${c.total}</span>${coverageBar(c)}</a></td>`).join('')}
      <td><b>${tot.here}</b>${tot.inherited ? `<span class="inh">+${tot.inherited}</span>` : ''} <span class="s">of ${tot.total}</span>${coverageBar(tot)}</td></tr>`;
  }).join('');
}

// a smaller test leads to a bigger one (the speller's three to the bettor's): the note under a trick's name
function leadNote(t, kts) {
  const name = k => (kts.find(x => x.key === k) || {}).name || k;
  const led = kts.filter(x => x.leads_to === t.key);
  return (t.leads_to ? `<div class="lead">→ leads to <a href="#/discoveries/${esc(t.leads_to)}">${esc(name(t.leads_to))}</a></div>` : '')
    + (led.length ? `<div class="lead">← led by ${led.map(x => `<a href="#/discoveries/${esc(x.key)}">${esc(x.name)}</a>`).join(', ')}</div>` : '');
}

// a select of the seven steps to quantum physics, kept as chosen
function fillStepFilter(sel, wps) {
  if (sel.options.length === wps.length + 1) return;
  const was = sel.value;
  sel.innerHTML = '<option value="">all seven</option>' + wps.map((w, i) => `<option value="${esc(w.key)}">${i + 1}. ${esc(w.name)}</option>`).join('');
  sel.value = was;
}
document.getElementById('goalfilter').onchange = () => { const r = rungFor(currentRung); if (r) classGoals(r); };

// ---- Waypoints, in three steps a class proves in order (UI.md): expected (the field already shows it
// at this size or smaller: match the field), pushing the envelope (this class's goals, and those it
// carries up, that nobody has shown at this size), exploring the stars (bigger classes' goals: the
// ambitious ones). "This size" is the class's order-of-magnitude band, as the trick table uses.
const sizeBand = n => Math.min(6, Math.max(0, Math.floor(Math.log10(n)) - 5));
function trickOnClass(t, preset, data) {
  const ft = t.fleet && (data.tricks || []).find(x => x.key === t.fleet);
  if (!t.fleet) return { text: 'not measured yet', measured: false, done: false, sort: 9 };
  if (ft && ft.viable === false) return { text: 'not viable on Gutenberg in English', measured: false, done: false, sort: 10 };
  if (ft && !ft.evaluator) return { text: `pre-registered${ft.cutoff ? ` (cutoff ${ft.cutoff})` : ''} · evaluator not built yet`, measured: false, done: false, sort: 8 };
  const mine = ft ? ft.ships.filter(x => x.preset === preset) : [];
  if (!mine.length) return { text: 'measured · no voyage of this class has a reading yet', measured: true, done: false, sort: 8 };
  const done = mine.filter(x => x.performed_at != null), best = Math.max(...mine.map(x => x.best));
  return done.length ? { text: `on ${done.length} of ${mine.length} sailings`, measured: true, done: true, sort: 0 }
    : { text: `best ${fmt(best)} of ${ft.threshold} on ${mine.length} sailings`, measured: true, done: false, sort: 1 };
}
function starOnClass(h, preset, data) {
  if (!h) return '';
  if (!h.star) return `${esc(h.name)} <span class="s">(not measured)</span>`;
  const st = (data.stars || []).find(x => x.key === h.star), mine = st ? st.ships.filter(x => x.preset === preset) : [];
  if (!mine.length) return `${esc(h.name)} <span class="s">(no reading on this class)</span>`;
  const lit = mine.filter(x => x.steps_to_lit != null).length, sh = mine.filter(x => x.shared_steps_to_lit != null).length;
  return `${esc(h.name)} ${lit ? `<span class="${pillCls('good')}">lit ${lit}/${mine.length}</span>` : sh ? `<span class="${pillCls('accent')}">shared ${sh}/${mine.length}</span>` : `<span class="${pillCls('')}">best ${fmt(Math.max(...mine.map(x => x.best ?? 0)))}</span>`}`;
}
async function classSteps(r) {
  if (!reachData || Date.now() - reachAt > 30000) { try { reachData = await get('/api/discoveries'); reachAt = Date.now(); } catch (e) { return; } }
  const d = reachData, kts = d.known_tricks || [], wps = d.waypoints || [], me = classRank(r.preset), band = sizeBand(r.total);
  const wpRank = k => wps.findIndex(w => w.key === k), heads = Object.fromEntries((d.known_heads || []).map(h => [h.key, h]));
  const expected = kts.filter(t => t.field_params != null && t.field_band_rank <= band);
  const ex = new Set(expected.map(t => t.key));
  const envelope = kts.filter(t => !ex.has(t.key) && t.target_class && classRank(t.target_class) <= me);
  const stars = kts.filter(t => !ex.has(t.key) && t.target_class && classRank(t.target_class) > me);
  const sets = { expected, envelope, stars };
  const names = { expected: 'Expected', envelope: 'Pushing the envelope', stars: 'Exploring the stars' };
  const about = { expected: 'match the field at this size', envelope: 'what nobody has shown at this size', stars: 'the ambitious ones, for bigger classes' };
  document.getElementById('wpsteps').innerHTML = WSUBS.map((k, i) => {
    const ts = sets[k], st = ts.map(t => trickOnClass(t, r.preset, d)), done = st.filter(x => x.done).length, meas = st.filter(x => x.measured).length;
    const proven = ts.length && done === ts.length;
    return `<a class="st${k === wpSub ? ' on' : ''}${proven ? ' proven' : ''}" href="#${modelHash(r, 'waypoints', k)}"><div class="t">${i + 1} · ${names[k]}</div>
      <div class="c">${about[k]} · ${ts.length} trick${ts.length === 1 ? '' : 's'} · ${meas} measured · ${done} performed</div></a>`;
  }).join('');
  fillStepFilter(document.getElementById('wpfilter'), wps);
  const wf = document.getElementById('wpfilter').value;
  const head = `<tr><th>step</th><th>trick</th><th>the field shows it at</th><th>goal class</th><th>stars needed (on this class)</th><th>on this class</th></tr>`;
  for (const k of WSUBS) {
    const rows = sets[k].filter(t => !wf || t.waypoint === wf).sort((a, b) => wpRank(a.waypoint) - wpRank(b.waypoint) || a.field_band_rank - b.field_band_rank);
    const tb = document.getElementById('wp-' + k);
    tb.tHead.innerHTML = head;
    tb.tBodies[0].innerHTML = rows.length ? rows.map(t => {
      const st = trickOnClass(t, r.preset, d);
      return `<tr data-trick="${esc(t.key)}" tabindex="0"><td data-sort="${wpRank(t.waypoint)}">${wpRank(t.waypoint) + 1}. ${esc((wps.find(w => w.key === t.waypoint) || {}).name || t.waypoint)}</td>
        <td><b>${t.gate ? '◆ ' : ''}${esc(t.name)}</b>${t.taught ? ' <span class="s">(taught, not read)</span>' : ''}${leadNote(t, kts)}</td>
        <td data-sort="${t.field_params ?? ''}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td>
        <td data-sort="${t.target_class ? classRank(t.target_class) : 99}">${t.target_class ? classLink(t.target_class) : '<span class="s">none</span>'}</td>
        <td>${t.stars.length ? t.stars.map(s => starOnClass(heads[s], r.preset, d)).join('<br>') : '<span class="s">none charted</span>'}</td>
        <td data-sort="${st.sort}">${st.done ? `<span class="${pillCls('good')}">performed</span> ` : ''}${esc(st.text)}</td></tr>`;
    }).join('') : `<tr><td colspan="6" class="${emptyCls(true)}">${sets[k].length ? 'none at this step' : k === 'expected' ? 'nothing: the field shows no trick at this size; everything here is pushing the envelope' : k === 'envelope' ? 'no goals at this size beyond what the field already shows' : 'nothing above this class on the ladder'}</td></tr>`;
  }
}
document.getElementById('wpfilter').onchange = () => { const r = rungFor(currentRung); if (r) classSteps(r); };
['wp-expected', 'wp-envelope', 'wp-stars'].forEach(id => document.getElementById(id).addEventListener('click', e => {
  const tr = e.target.closest('tr[data-trick]'); if (tr && !e.target.closest('a')) location.hash = '#/discoveries/' + tr.dataset.trick;
}));
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
      cell = !mine.length ? '<td data-sort="8" class="s">measured, but no voyage of this class has a reading yet</td>'
        : `<td data-sort="${lit.length ? 0 : sh.length ? 1 : 2}">${lit.length ? `<span class="${pillCls('good')}">lit</span>` : sh.length ? `<span class="${pillCls('accent')}">lit shared</span>` : `<span class="${pillCls('')}">not lit yet</span>`}
          ${lit.length ? `on ${lit.length}` : sh.length ? `on ${sh.length}` : `best ${fmt(best)}`} of ${mine.length} sailings · threshold ${st.threshold}</td>`;
    }
    return `<tr><td><b>${esc(h.name)}</b></td><td>${esc(FAMILY[h.family] || h.family)}</td><td data-sort="${classRank(h.expected_from)}">${classLink(h.expected_from)}</td>
      <td class="s">${esc(h.expected_why || '')}</td>${cell}</tr>`;
  }).join('') : '<tr><td colspan="5" class="${emptyCls(true)}">no kind of head is expected this small</td></tr>';
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
  if (!pts.length) return empty('ftchart', 'no voyage at this size has a Forgotten Tomes score yet');
  let best = Infinity;
  const bestSoFar = pts.map(p => (best = Math.min(best, p.x.ft_en)));
  plot('ftchart', [
    { type: 'scattergl', mode: 'markers', name: 'a voyage', x: pts.map(p => p.i), y: pts.map(p => p.x.ft_en),
      text: pts.map(p => `${p.x.ship || p.x.name} · ${p.x.name}`), hovertemplate: 'run %{x}: %{text}<br>%{y:.3f} bpb<extra></extra>',
      marker: { size: 6, color: C.blue, opacity: 0.55 } },
    { type: 'scatter', mode: 'lines', name: 'best so far', x: pts.map(p => p.i), y: bestSoFar, line: { color: C.good, width: 2, shape: 'hv' },
      hovertemplate: 'best so far %{y:.3f}<extra></extra>' },
  ], layout({ xaxis: { title: 'voyage, in the order they started', gridcolor: C.line },
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
  stagesFor(allRuns.slice(-12).map(x => x.run_id)).then(m => bandStages('#rung', commonStages(m)));
  if (r.kind !== 'proxy') return;
  const big9 = ladderData.runs.filter(x => x.preset === ladderData.rungs.find(q => q.kind !== 'proxy').preset);
  // only proxy runs with a 9m twin calibrate anything; the loop's random shelves have none
  const pairs = allRuns.map(p => ({ p, n: big9.find(n => n.recipe === p.recipe && n.passes === p.passes && n.seed === p.seed && n.status === 'finished') })).filter(x => x.n);
  document.querySelector('#caltable tbody').innerHTML = pairs.map(({ p, n }) => `<tr><td>${esc((p.recipe || '').replace('lists/', '').replace('.csv', ''))}</td>
    <td>${p.passes ?? '–'}</td><td>${n ? esc(n.ship || n.name) : '–'}</td><td>${fmt(n && n.ft_en)}</td><td>${esc(p.ship || p.name)}</td><td>${fmt(p.ft_en)}</td></tr>`).join('');
  const both = pairs.filter(({ p, n }) => n && n.ft_en != null && p.ft_en != null);
  const rank = a => a.map(v => a.filter(w => w < v).length);
  let verdict = `${both.length} of ${pairs.length} libraries scored at both sizes.`;
  if (both.length >= 3) {
    const a = rank(both.map(x => x.n.ft_en)), b = rank(both.map(x => x.p.ft_en)), k = a.length;
    const rho = 1 - 6 * a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0) / (k * (k * k - 1));
    verdict += ` Rank agreement (Spearman) ${rho.toFixed(2)}: ${rho >= 0.8 ? 'the proxy orders the libraries as 9m does' : 'not yet trustworthy'}.`;
  } else verdict += ' Rank agreement needs at least three; the 9m voyages are re-scored on the Forgotten Tomes by the queue.';
  document.getElementById('calverdict').textContent = verdict;
  if (!both.length) empty('calchart', 'points appear when a library has a Forgotten Tomes score at both sizes');
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
  if (page === 'voyages') loadOverview();
  if (page === 'voyage' && currentVoyage()) journeyPanel(currentVoyage());
  if (page === 'discoveries') loadDiscoveries();
  if (page === 'sievesguide') loadSieves();
  if (page === 'leaderboard') loadLeaderboard();
  if (page === 'governance') loadGovernance();
  if (page === 'competitor') loadCompetitor();
  if (page === 'shelves') loadShelves();
  try {
    const runs = await get('/api/runs');
    const first = !runsList;
    runsList = runs;
    if (!runs.length) { document.getElementById('title').textContent = 'no voyages in the ledger yet'; return; }
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
    stagesFor([selected]).then(st => { bandStages('#ship', st[selected]); drawStageList(st[selected]); });
    document.getElementById('updated').textContent = 'updated ' + new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById('updated').textContent = 'error: ' + e;
  }
}
refresh();
setInterval(refresh, 5000);


// ==================================================================================== the leaderboard
// (#/leaderboard; thorp.leaderboard.payload, UI.md "Leaderboard"): the best of each class on the climb to chaining two
// facts, the reference ladder on the same bars, and every run. A climb bar runs 0 to 5, ticked at each rung; the four-chain
// strip has a row per chain, five cells (keel to 50m), lit cells filled and the next cell filled by its share of the mark.
const CHAIN_LABEL = { origin_test: 'the Origin', energy_test: 'energy', mendeleev_gaps: "Mendeleev's gaps", recurrence_test: 'the eternal return' };
const CHAIN_SHORT = { origin_test: 'Origin', energy_test: 'energy', mendeleev_gaps: 'Mendeleev', recurrence_test: 'return' };
const RUNG_CLASS = ['keel', 'pilot', 'speller', 'stylist', '50m'];
function climbBar(c, max = 5) {
  if (c == null) return '<span class="s">–</span>';
  const pct = Math.max(0, Math.min(100, 100 * c / max));
  return `<div class="climb" title="climb ${fmt(c, 2)} of ${max}"><div class="cfill" style="width:${pct}%"></div>${Array.from({ length: max - 1 }, (_, i) => `<i style="left:${100 * (i + 1) / max}%"></i>`).join('')}<b>${fmt(c, 2)}</b></div>`;
}
function chainingCell(v, thr) {
  if (v == null) return '<span class="s">not read</span>';
  return `<span class="${v >= thr ? 'good' : Math.abs(v) <= 0.03 ? 's' : ''}" title="${v >= thr ? 'at the mark' : Math.abs(v) <= 0.03 ? 'within the noise (about 0.03 of zero)' : 'below the mark'}">${signed(v)}</span>`;
}
function chainStrip(chains) {
  if (!chains) return '';
  return `<div class="cstrip">${Object.entries(chains).map(([k, c]) => `<div class="csr" title="${esc(CHAIN_LABEL[k] || k)}: ${c.rungs} rung${c.rungs === 1 ? '' : 's'} performed${c.next ? `, next ${esc(c.next.replace(/_test$/, ''))} at ${Math.round(100 * c.partial)}% of its mark` : ', all five'}"><span>${esc(CHAIN_SHORT[k] || k)}</span>${RUNG_CLASS.map((r, i) => `<em class="${i < c.rungs ? 'on' : ''}">${i === c.rungs && c.partial ? `<u style="width:${Math.round(100 * c.partial)}%"></u>` : ''}</em>`).join('')}</div>`).join('')}</div>`;
}
const runLink = x => x.run ? `<a href="#${shipHash(x.run)}">${esc(x.run)}</a>` : '–';
// The leaderboard is chaining-only (leaderboard.payload: the four chaining tests, public; the climb is internal and lives on
// the two-fact voyage's page). Best in class is a SHIP, its sailings averaged.
async function loadLeaderboard() {
  let d; try { d = await get('/api/leaderboard'); } catch (e) { return; }
  const key = JSON.stringify(d) + !!ladderData; if (key === lbKey) return; lbKey = key; lbData = d;
  const sel = document.getElementById('lbclass'), presets = [...new Set((d.ships || []).map(r => r.preset).filter(Boolean))].sort((a, b) => classRank(a) - classRank(b));
  const keep = sel.value;
  sel.innerHTML = '<option value="">every class</option>' + presets.map(p => `<option value="${esc(p)}">${esc(p)}${classOf(p) ? ' · ' + esc(classOf(p).name) : ''}</option>`).join('');
  sel.value = presets.includes(keep) ? keep : '';
  sel.onchange = drawLbRuns;
  drawLbRuns();
  drawLbTable();
  drawSmokingQwen();
}
// the logic deck's chaining gain in a cell: the proof that a pass is chaining (✓ when performed: gain at the mark and two in
// three items right); "not read" until the deck is scored on that model
function logicCell(l, kind) {
  if (kind === 'forecast') return '';
  if (!l || l.gain == null) return '<span class="s">not read yet</span>';
  return `<span class="tc${l.performed ? ' lit' : ''}" title="chaining gain ${signed(l.gain)}${l.score != null ? `, ${Math.round(100 * l.score)}% of items right` : ''}${l.performed ? ', performed' : ''}">${signed(l.gain)} <i>${l.score != null ? Math.round(100 * l.score) + '%' : ''}</i>${l.performed ? ' ✓' : ''}</span>`;
}
// one chaining test's reading in a cell: lift, share right, ✓ when performed under the rule
function testCell(t) {
  if (!t || t.lift == null) return '<span class="s">–</span>';
  return `<span class="tc${t.performed ? ' lit' : ''}" title="${esc(t.name || '')}: lift ${signed(t.lift)}, ${t.score != null ? Math.round(100 * t.score) + '% of pairs right' : ''}${t.performed ? ', performed' : ''}">${signed(t.lift)} <i>${t.score != null ? Math.round(100 * t.score) + '%' : ''}</i>${t.performed ? ' ✓' : ''}</span>`;
}
function drawLbRuns() {
  if (!lbData) return;
  const want = document.getElementById('lbclass').value, thr = lbData.threshold ?? 0.1, tests = lbData.tests || [];
  const rows = (lbData.ships || []).filter(r => !want || r.preset === want).sort((a, b) => (b.chaining_lift ?? -9) - (a.chaining_lift ?? -9));
  document.getElementById('lbcount').textContent = `${rows.length} ship${rows.length === 1 ? '' : 's'}`;
  document.querySelector('#lbruns thead').innerHTML = `<tr><th>ship</th><th>class</th><th>voyages</th><th>chaining lift</th><th>chaining gain <span class="s">logic deck</span></th><th>passed</th>${tests.map(t => `<th>${esc(t.name)}</th>`).join('')}</tr>`;
  document.querySelector('#lbruns tbody').innerHTML = rows.map(r => `<tr><td>${r.ship_key ? `<a href="#${shipHash(r.ship_key)}">${esc(r.ship || r.run)}</a>` : esc(r.ship || r.run)}</td><td data-sort="${classRank(r.preset)}">${classLink(r.preset)}</td>
    <td data-sort="${r.sailings ?? 1}">${r.sailings ?? 1}</td><td data-sort="${r.chaining_lift ?? -9}">${chainingCell(r.chaining_lift, thr)}</td><td data-sort="${r.logic && r.logic.gain != null ? r.logic.gain : -9}">${logicCell(r.logic)}</td><td data-sort="${r.passed ?? 0}">${r.passed ?? 0} of ${tests.length}</td>
    ${tests.map(t => `<td>${testCell((r.tests || {})[t.key])}</td>`).join('')}</tr>`).join('')
    || `<tr><td colspan="${6 + tests.length}" class="${emptyCls(true)}">no ships with chaining readings in this class</td></tr>`;
}

// ==================================================================================== the shelves
// (#/shelves; thorp.shelves.payload served warm, UI.md "Shelves"): grouped by kind, training first, then the decks, the
// probes and the rest, drafts folded away. A row opens to its uses (each run and its role) and its books, which open in
// the reader.
const SHELF_KINDS = [['training', 'Training libraries', 'what the ships read'], ['deck', 'Decks', 'the books the ships are scored on, never read'],
  ['probe', 'Probes', 'small lists the instruments read'], ['other', 'Other', 'lists kept for a purpose of their own'], ['draft', 'Drafts', 'lists being drawn up, not yet used']];
async function loadShelves() {
  let d; try { d = await get('/api/library'); } catch (e) { return; }
  if (!d.shelves) {
    drawFitouts(d);
    document.getElementById('shelfgroups').innerHTML = `<div class="${emptyCls()}">${d.error ? 'the libraries could not be read: ' + esc(d.error) : 'reading the libraries (a few seconds)…'}</div>`;
    if (!d.error) setTimeout(() => { if (page === 'shelves') loadShelves(); }, 2500);
    return;
  }
  drawFitouts(d);
  if (d.shelves) initBuilder(d.shelves);
  const key = JSON.stringify(d.shelves); if (key === shelvesKey) return; shelvesKey = key; shelvesData = d.shelves;
  const sel = document.getElementById('shelfkind'), keep = sel.value;
  sel.innerHTML = '<option value="">every kind</option>' + SHELF_KINDS.filter(k => shelvesData.some(x => x.kind === k[0])).map(k => `<option value="${k[0]}">${k[1].toLowerCase()}</option>`).join('');
  sel.value = keep; sel.onchange = drawShelves;
  document.getElementById('shelfsearch').oninput = drawShelves;
  drawShelves();
}
const FAMILY_TOK = ['blue', 'accent', 'good', 'bad', 'c5', 'c6', 'c7', 'c8', 'c9', 'c10'];
const familyColour = (() => { const seen = {}; return f => seen[f] || (seen[f] = `var(--${FAMILY_TOK[Object.keys(seen).length % FAMILY_TOK.length]})`); })();
function familyBar(fam) {
  const n = Object.values(fam || {}).reduce((a, b) => a + b, 0); if (!n) return '<span class="s">–</span>';
  return `<div class="fbar" title="${esc(Object.entries(fam).map(([f, k]) => `${f} ${k}`).join(' · '))}">${Object.entries(fam).map(([f, k]) => `<span style="width:${100 * k / n}%;background:${familyColour(f)}"></span>`).join('')}</div>`;
}
function drawShelves() {
  if (!shelvesData) return;
  const want = document.getElementById('shelfkind').value, q = document.getElementById('shelfsearch').value.trim().toLowerCase();
  const rows = shelvesData.filter(x => (!want || x.kind === want) && (!q || (x.name + ' ' + x.path + ' ' + x.about).toLowerCase().includes(q)));
  document.getElementById('shelfcount').textContent = `${rows.length} librar${rows.length === 1 ? 'y' : 'ies'}`;
  const known = SHELF_KINDS.map(k => k[0]);
  const groups = [...SHELF_KINDS, ...[...new Set(rows.map(x => x.kind))].filter(k => !known.includes(k)).map(k => [k, k, ''])];
  document.getElementById('shelfgroups').innerHTML = groups.map(([k, title, note]) => {
    const g = rows.filter(x => x.kind === k); if (!g.length) return '';
    const body = `<div class="scroll"><table class="shelftable clickable" data-kind="${k}"><thead><tr><th>library</th><th>books</th><th>~tokens</th><th>families</th><th>read by</th></tr></thead><tbody>${g.map(x => `
      <tr data-shelf="${esc(x.path)}"${x.path === shelfOpen ? ' class="open"' : ''}><td><b>${esc(x.name)}</b> <span class="mono s">${esc(x.path)}</span>${x.about ? `<div class="s">${esc(x.about)}</div>` : ''}</td>
        <td data-sort="${x.books}">${x.books}${x.books < x.rows ? ` <span class="s">of ${x.rows}</span>` : ''}</td>
        <td data-sort="${x.tokens_est}">${big(x.tokens_est)}</td><td>${familyBar(x.families)}</td>
        <td data-sort="${x.runs + x.queued}">${[x.runs ? `read by ${x.runs} run${x.runs === 1 ? '' : 's'}` : '', x.queued ? `<span class="accent">${x.queued} queued</span>` : ''].filter(Boolean).join(' · ') || '<span class="s">no voyage yet</span>'}</td></tr>
      ${x.path === shelfOpen ? `<tr class="shelfdetail"><td colspan="5" id="shelfdetail"></td></tr>` : ''}`).join('')}</tbody></table></div>`;
    const head = `${esc(title)} <span class="note">${g.length} · ${esc(note)}</span>`;
    return k === 'draft' && !q && want !== 'draft'
      ? `<section class="${cardCls(false, 'panel')}"><details${g.some(x => x.path === shelfOpen) ? ' open' : ''}><summary><h2>${head}</h2></summary>${body}</details></section>`
      : `<section class="${cardCls(false, 'panel')}"><h2>${head}</h2>${body}</section>`;
  }).join('') || '<div class="${emptyCls()}">no library matches</div>';
  document.querySelectorAll('#shelfgroups tr[data-shelf]').forEach(tr => tr.onclick = e => {
    if (e.target.closest('a')) return;
    shelfOpen = shelfOpen === tr.dataset.shelf ? null : tr.dataset.shelf; drawShelves();
  });
  if (shelfOpen) drawShelfDetail();
}
async function drawShelfDetail() {
  const el = document.getElementById('shelfdetail'), x = shelvesData.find(s => s.path === shelfOpen); if (!el || !x) return;
  const roleOrder = r => ['reads', 'reads first', 'tokeniser', 'scored on', 'refuses'].indexOf(r);
  const uses = [...x.uses].sort((a, b) => (a.status === 'queued') - (b.status === 'queued') || roleOrder(a.role) - roleOrder(b.role) || a.run.localeCompare(b.run));
  const usesHtml = uses.length ? `<div class="shelfuses">${uses.map(u => `<span class="use${u.status === 'queued' ? ' queued' : ''}">${u.status === 'queued' ? esc(u.run) : `<a href="#${shipHash(u.run)}">${esc(u.run)}</a>`} <i>${esc(u.role)}</i>${u.status === 'queued' ? ' <i>queued</i>' : ''}</span>`).join('')}</div>` : '<div class="s">no voyage reads it yet</div>';
  el.innerHTML = `<div class="k">used by</div>${usesHtml}<div class="k mt">the books</div><div id="shelfbooks" class="s">reading the list…</div>`;
  let books = shelfBooks.get(x.path);
  if (!books) { try { books = await get('/api/library_books?path=' + encodeURIComponent(x.path)); shelfBooks.set(x.path, books); } catch (e) { books = null; } }
  const bel = document.getElementById('shelfbooks'); if (!bel || shelfOpen !== x.path) return;
  if (!books) { bel.textContent = 'the list could not be read'; return; }
  bel.className = 'shelfbooks';
  bel.innerHTML = books.map(b => b.book_id
    ? `<button class="${btnCls('outline', 'bookbtn')}" data-book="${esc(b.book_id)}" title="open in the reader">${esc(b.title)}<span>${esc(b.author)}${b.family ? ' · ' + esc(b.family) : ''}</span></button>`
    : `<span class="bookbtn off" title="not fetched yet">${esc(b.title)}<span>${esc(b.author)} · not fetched</span></span>`).join('');
  bel.querySelectorAll('[data-book]').forEach(b => b.onclick = () => openBook(b.dataset.book));
}

// ==================================================================================== the two-fact problem's climb
// (the two_facts voyage page): each run's climb over training, coloured by class, from its discovery readings
// (/api/climb), with the reference ladder as dotted levels for scale; a select switches to the chaining lift.
async function voyageClimb(v) {
  const el = document.getElementById('voyageclimb'); if (!el || v.key !== 'two_facts') return;
  const runs = v.runs.filter(r => r.run_id);
  if (!runs.length) { empty('voyageclimb', 'no voyages yet: the baseline (keel, pilot, speller and stylist, two seeds each) is at the top of the queue'); return; }
  let d, lb; try { [d, lb] = await Promise.all([get('/api/climb?runs=' + runs.map(r => r.run_id).join(',')), get('/api/leaderboard/internal')]); } catch (e) { return; }
  const what = document.getElementById('voyageclimbwhat').value || 'climb';
  runs.forEach(r => { r.preset = r.preset || r.class; });
  const presets = [...new Set(runs.map(r => r.preset))].sort((a, b) => classRank(a) - classRank(b));
  const traces = runs.filter(r => d[r.run_id] && d[r.run_id].step.length && (d[r.run_id][what] || []).some(v => v != null)).map(r => ({
    x: d[r.run_id].step, y: d[r.run_id][what], name: r.name, mode: 'lines+markers', marker: { size: 4 },
    line: { color: PALETTE[presets.indexOf(r.preset) % PALETTE.length], width: 1.6 }, legendgroup: r.preset, hovertemplate: `${esc(r.name)}<br>step %{x}<br>${what === 'climb' ? 'climb' : what === 'logic_gain' ? 'chaining gain' : 'chaining lift'} %{y:.2f}<extra></extra>`, connectgaps: true,
  }));
  if (!traces.length) { empty('voyageclimb', what === 'logic_gain' ? 'no logic deck readings yet: the baseline voyages not yet sailed read it' : 'no discovery readings yet: the first comes at step 100'); return; }
  const shapes = [], notes = [];
  for (const r of (lb.reference || [])) {
    const y = what === 'climb' ? r.climb : what === 'chaining_lift' ? r.chaining_lift : null; if (y == null) continue;
    shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color: tok('muted'), width: 1, dash: 'dot' } });
    notes.push({ xref: 'paper', x: 1, y, xanchor: 'right', yanchor: 'bottom', showarrow: false, text: esc(r.model.split('/').pop()), font: { size: 9, color: tok('muted') } });
  }
  if (what === 'logic_gain') shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0.1, y1: 0.1, line: { color: tok('accent'), width: 1.2, dash: 'dot' } });
  if (what === 'chaining_lift') shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: lb.chaining_threshold ?? 0.1, y1: lb.chaining_threshold ?? 0.1, line: { color: tok('accent'), width: 1.2, dash: 'dot' } });
  plot('voyageclimb', traces, layout({ xaxis: { title: { text: 'step' } }, yaxis: { title: { text: what === 'climb' ? 'climb (0 to 5)' : what === 'logic_gain' ? 'chaining gain (logic deck)' : 'chaining lift' }, ...(what === 'climb' ? { range: [0, 5.2], dtick: 1 } : {}) }, shapes, annotations: notes, height: 380 }));
}
document.getElementById('voyageclimbwhat')?.addEventListener('change', () => { const v = currentVoyage && currentVoyage(); if (v) voyageClimb(v); });


// ---- Smoking Qwen (top of the Leaderboard; thorp.smoking_qwen.payload, UI.md "Leaderboard"): chaining lift against size on
// Thorp's classes, fitted (linear and bending, in log10 parameters, as smoking_qwen fits them) and carried to 400M, with the
// bootstrap's 5-95% band there, Qwen3 4B's mark, the threshold, and the reference ladder in grey.
let sqKey = null, sqData = null;
function polyfit(xs, ys, deg) {  // least squares through (xs, ys), coefficients highest power first (numpy.polyfit's order)
  const n = deg + 1, A = Array.from({ length: n }, () => Array(n + 1).fill(0));
  xs.forEach((x, i) => { for (let r = 0; r < n; r++) { for (let c = 0; c < n; c++) A[r][c] += x ** (2 * deg - r - c); A[r][n] += ys[i] * x ** (deg - r); } });
  for (let i = 0; i < n; i++) { let m = i; for (let r = i + 1; r < n; r++) if (Math.abs(A[r][i]) > Math.abs(A[m][i])) m = r; [A[i], A[m]] = [A[m], A[i]];
    for (let r = 0; r < n; r++) if (r !== i) { const f = A[r][i] / A[i][i]; for (let c = i; c <= n; c++) A[r][c] -= f * A[i][c]; } }
  return A.map((row, i) => row[n] / row[i]);
}
const polyval = (co, x) => co.reduce((a, c) => a * x + c, 0);
async function drawSmokingQwen() {
  if (!document.getElementById('sqchart')) return;
  let d; try { d = await get('/api/smoking_qwen'); } catch (e) { return; }
  sqData = d; drawLbTable();
  const key = JSON.stringify(d); if (key === sqKey) return; sqKey = key;
  const T = d.target || {}, th = d.thorp || {}, pts = th.points || [], need = 3;
  const pct = v => v == null ? '–' : `${Math.round(100 * v)}%`;
  const above = (d.classes_above_noise || []).length;
  const rng = d.range || [], scored = rng.filter(c => c.scored);
  const pLin = d.p_range_linear ?? (th.linear || {}).p_at_or_above_target, pBend = d.p_range_bending ?? (th.bending || {}).p_at_or_above_target;
  document.getElementById('sqhead').innerHTML = d.forecastable
    ? `<div class="sqp"><b class="${pLin >= 0.9 ? 'good' : ''}">${pct(pLin)}</b><span>on the straight line (conservative), the least over the range</span></div>
       <div class="sqp"><b class="${pBend >= 0.9 ? 'accent' : ''}">${pct(pBend)}</b><span>on the bending curve (probable), the least over the range</span></div>`
    : `<div class="sqp"><b class="s">not yet forecastable</b><span>${above} of ${need} classes above the noise (a chaining lift over ${d.noise ?? 0.03}); a curve through noise extrapolates nothing, so the curves below are drawn but no probability is claimed</span></div>`;
  const claimed = d.forecastable && pLin >= 0.9, probable = d.forecastable && !claimed && pBend >= 0.9;
  document.getElementById('sqhead').innerHTML += `<div class="sqp"><b>${claimed ? `<span class="${pillCls('good')}">claimed</span>` : probable ? `<span class="${pillCls('accent')}">probable</span>` : `<span class="${pillCls('')}">not claimed</span>`}</b><span>${rng.length ? `${scored.length} of ${rng.length} competitors scored${d.hardest ? `; the hardest, ${esc(d.hardest)}` : ''}, each to be matched at a tenth its size` : `target: ${esc(_shortModel(T.model))} at ${signed(T.chaining_lift)}, a Thorp of ${fmtParams(d.smoke_at)}`}</span></div>`;
  document.getElementById('sqrule').textContent = 'Claimed when forecastable (three classes above the noise) and P ≥ 0.9 on the straight line for every competitor in the range; "probable" when only the bending curve reaches 0.9.';
  const fmtBand = f => f ? `${signed(f.predicted)} <span class="s">(${signed(f.band[0])} to ${signed(f.band[1])})</span>` : '–';
  document.getElementById('sqbacktest').innerHTML = (d.backtest || []).map(b => `<div class="sqbt"><div><b>${esc(b.test)}</b> · actual ${signed(b.actual)}</div>
    ${['linear', 'bending'].filter(k => b[k]).map(k => `<div class="sqbk ${b[k].inside_band ? 'good' : 'bad'}">${k === 'linear' ? 'straight' : 'bending'}: ${fmtBand(b[k])} · ${b[k].inside_band ? 'inside the band' : b[k].predicted < b.actual ? 'missed (too low)' : 'missed (too high)'}</div>`).join('')}</div>`).join('') || '<div class="s">no backtest yet</div>';
  // the chart
  const lx = Math.log10, traces = [];
  const xs = pts.map(p => lx(p.params)), ys = pts.map(p => p.chaining_lift);
  const grid = Array.from({ length: 61 }, (_, i) => 5 + i * (lx(d.smoke_at) - 5) / 60);
  for (const [kind, deg, col, dash] of [['linear', 1, tok('blue'), 'solid'], ['bending', 2, tok('accent'), 'dash']]) {
    const f = th[kind]; if (!f || pts.length < deg + 1) continue;
    const co = polyfit(xs, ys, deg);
    traces.push({ x: grid.map(g => 10 ** g), y: grid.map(g => polyval(co, g)), mode: 'lines', name: kind === 'linear' ? 'straight line' : 'bending curve', line: { color: col, width: 1.6, dash }, hoverinfo: 'skip' });
    traces.push({ x: [d.smoke_at], y: [f.predicted], mode: 'markers', name: `${kind === 'linear' ? 'straight' : 'bending'} at 400M`, showlegend: false, marker: { color: col, size: 9, symbol: 'diamond' },
      error_y: { type: 'data', symmetric: false, array: [f.band[1] - f.predicted], arrayminus: [f.predicted - f.band[0]], color: col, thickness: 1.4, width: 6 },
      hovertemplate: `${kind === 'linear' ? 'straight' : 'bending'} at 400M: %{y:.3f}<br>5-95%: ${signed(f.band[0])} to ${signed(f.band[1])}<extra></extra>` });
  }
  traces.push({ x: pts.map(p => p.params), y: ys, mode: 'markers+text', name: 'Thorp (best of each class)', text: pts.map(p => p.name), textposition: 'top center', textfont: { size: 10, color: tok('text') },
    marker: { color: tok('good'), size: 10 }, customdata: pts.map(p => p.run || ''), hovertemplate: '%{text} · %{customdata}<br>%{x:.3s} parameters<br>chaining lift %{y:.3f}<extra></extra>' });
  const comp = (d.reference || []).filter(r => r.competitor && r.chaining_lift != null);
  if (comp.length) traces.push({ x: comp.map(r => r.params), y: comp.map(r => r.chaining_lift), mode: 'markers+text', name: 'the 2–4B competitors', text: comp.map(r => r.short), textposition: 'middle left', textfont: { size: 9, color: tok('bad') },
    marker: { color: tok('bad'), size: 9, symbol: 'diamond-open' }, hovertemplate: '%{text}<br>%{x:.3s} parameters<br>chaining lift %{y:.3f}<extra></extra>' });
  const ref = (d.reference || []).filter(r => !r.competitor);
  if (ref.length) traces.push({ x: ref.map(r => r.params), y: ref.map(r => r.chaining_lift), mode: 'markers', name: 'reference ladder (hover for each)', text: ref.map(r => r.short),
    marker: { color: tok('muted'), size: 7, symbol: 'circle-open' }, hovertemplate: '%{text}<br>%{x:.3s} parameters<br>chaining lift %{y:.3f}<extra></extra>' });
  const shapes = [
    { type: 'line', xref: 'x', yref: 'paper', x0: d.smoke_at, x1: d.smoke_at, y0: 0, y1: 1, line: { color: tok('muted'), width: 1, dash: 'dash' } },
    { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: -(d.noise ?? 0.03), y1: d.noise ?? 0.03, fillcolor: 'rgba(139,148,158,0.10)', line: { width: 0 }, layer: 'below' },
    { type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: d.threshold ?? 0.1, y1: d.threshold ?? 0.1, line: { color: tok('accent'), width: 1, dash: 'dot' } },
  ];
  if (T.chaining_lift != null) shapes.push({ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: T.chaining_lift, y1: T.chaining_lift, line: { color: tok('bad'), width: 1.2 } });
  const notes = [
    { xref: 'x', yref: 'paper', x: Math.log10(d.smoke_at), y: 1, yanchor: 'bottom', showarrow: false, text: '400M', font: { size: 10, color: tok('muted') } },
    { xref: 'paper', yref: 'y', x: 0, y: d.threshold ?? 0.1, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: 'performed (0.1)', font: { size: 9, color: tok('accent') } },
    { xref: 'paper', yref: 'y', x: 0, y: d.noise ?? 0.03, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: 'noise', font: { size: 9, color: tok('muted') } },
  ];
  if (T.chaining_lift != null) notes.push({ xref: 'paper', yref: 'y', x: 0, y: T.chaining_lift, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: `${esc(_shortModel(T.model))} ${signed(T.chaining_lift)}`, font: { size: 10, color: tok('bad') } });
  plot('sqchart', traces, layout({ xaxis: { type: 'log', title: { text: 'parameters' }, range: [5, 10] }, yaxis: { title: { text: 'chaining lift' }, zeroline: false }, shapes, annotations: notes, height: 400, legend: { orientation: 'h', y: -0.2 } }));
}
const _shortModel = m => (m || '').split('/').pop().replace(/-(\d+)bit$/, ' $1-bit').replace('Qwen3-', 'Qwen3 ');


// ---- the leaderboard table: one ranking on the chaining lift. Outside models (leaderboard.reference, sized from
// smoking_qwen's REFERENCE_PARAMS), Thorp's classes (each class's best run), and Thorp's forecasts: the two fits through
// Thorp's class points (polynomials in log10 parameters, as smoking_qwen fits them) read at each class not yet measured
// and at 400M. For each outside model, the size where each fit reaches its lift.
const MAKER = [[/qwen/i, 'Qwen', 'Alibaba'], [/llama/i, 'Llama', 'Meta'], [/phi/i, 'Phi', 'Microsoft'], [/pythia/i, 'Pythia', 'EleutherAI'], [/gemma/i, 'Gemma', 'Google'], [/smollm/i, 'SmolLM', 'Hugging Face']];
const makerOf = m => (MAKER.find(([re]) => re.test(m)) || [null, '', ''])[2];
const fmtParams = n => n == null ? '–' : n >= 1e12 ? `${(n / 1e12).toFixed(n >= 1e13 ? 0 : 1)}T` : n >= 1e9 ? `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B` : n >= 1e6 ? `${Math.round(n / 1e6)}M` : `${Math.round(n / 1e3)}k`;
// where a fit (coefficients in log10 parameters) first reaches y above the largest measured size; null if never by 10^14
function fitReachAt(co, y, from) {
  if (!co) return null;
  for (let x = from; x <= 14; x += 0.005) if (polyval(co, x) >= y) return 10 ** x;
  return null;
}
document.getElementById('lbshowfc').onchange = () => drawLbTable();
document.getElementById('lbshowpythia').onchange = () => drawLbTable();
document.querySelectorAll('#leaderboard details.lbfold').forEach(d => d.addEventListener('toggle', () => {
  if (d.open) d.querySelectorAll('.js-plotly-plot').forEach(el => Plotly.Plots.resize(el));
}));
function drawLbTable() {
  const tb = document.querySelector('#lbtable tbody'); if (!tb || !lbData) return;
  const thr = lbData.threshold ?? 0.1, sq = sqData || {}, tests = lbData.tests || [];
  document.getElementById('lbthr').textContent = thr;
  document.querySelector('#lbtable thead').innerHTML = `<tr><th>#</th><th>model</th><th>parameters</th><th>chaining lift</th><th title="the logic deck's chaining gain: the lift with both premises less the better single premise, on invented words and counterfactual premises; the proof that a pass is chaining, not knowing or one premise">chaining gain<div class="s">logic deck</div></th><th title="${CAUSE_NOTE}">cause and effect<div class="s">chaining gain</div></th><th>passed</th>${tests.map(t => `<th class="tcol">${esc(t.name.replace(/^The /, ''))}</th>`).join('')}<th>Thorp must match it at</th></tr>`;
  const showFc = document.getElementById('lbshowfc').checked, showPy = document.getElementById('lbshowpythia').checked;
  const rungs = (ladderData && ladderData.rungs) || [];
  // the two fits through Thorp's class points (smoking_qwen's)
  const pts = ((sq.thorp || {}).points || []).filter(p => p.params && p.chaining_lift != null);
  const xs = pts.map(p => Math.log10(p.params)), ys = pts.map(p => p.chaining_lift), top = xs.length ? Math.max(...xs) : 6;
  const fits = { straight: pts.length >= 2 ? polyfit(xs, ys, 1) : null, bending: pts.length >= 3 ? polyfit(xs, ys, 2) : null };
  const trusted = !!sq.forecastable;
  document.getElementById('lbfcnote').innerHTML = !pts.length ? '' : trusted ? 'forecasts trusted: three classes above the noise'
    : `<span class="accent">forecasts not yet trusted</span>: ${(sq.classes_above_noise || []).length} of 3 classes above the noise`;
  const range = Object.fromEntries((sq.range || []).map(c => [c.model, c]));
  // one table (leaderboard.payload table), outside models and Thorp versions together, split by the noise: the CHAINING
  // board holds the rows whose chaining lift clears it, ranked by chaining lift; the rest approach chaining (drawn below)
  const tests_of = r => r.kind === 'thorp' ? ((lbData.ships || []).find(x => x.ship_key === r.ship_key) || (lbData.board || []).map(b => b.best).find(b => b && b.ship_key === r.ship_key) || {}).tests
    : ((lbData.reference || []).find(x => x.model === r.model) || {}).tests;
  const asRow = r => {
    if (r.kind === 'thorp') {
      const best = (lbData.board || []).map(b => b.best).find(b => b && b.ship_key === r.ship_key) || {};
      const preset = best.preset || (r.ship_key || '').split(':')[0], rr = rungs.find(x => x.preset === preset);
      return { kind: 'thorp', cls: preset, ship: { ...best, name: r.name, ship: r.ship || best.ship, ship_key: r.ship_key, sailings: r.sailings ?? best.sailings }, params: r.params ?? (rr ? rr.total : null),
        lift: r.chaining_lift, passed: r.passed, tests: tests_of(r), logic: r.logic, src: r };
    }
    return { kind: 'outside', model: r.model, name: r.name, maker: makerOf(r.model), competitor: r.kind === 'competitor', params: r.params ?? (range[r.model] || {}).params ?? null,
      lift: r.chaining_lift, passed: r.passed, tests: tests_of(r), logic: r.logic, tenth: range[r.model], src: r };
  };
  const table = lbData.table || [];
  const rows = table.filter(r => r.group === 'chaining' && (showPy || r.kind !== 'ladder')).sort((a, b) => a.rank - b.rank).map(asRow);
  const seen = new Set(table.map(r => r.model).filter(Boolean));
  for (const c of sq.range || []) if (!seen.has(c.model)) rows.push({ kind: 'outside', name: c.label, maker: makerOf(c.model), competitor: true, params: c.params, lift: null, pending: true });
  drawLbApproach(table.filter(r => r.group === 'approaching').sort((a, b) => a.rank - b.rank).map(r => ({ ...asRow(r), src: r })), thr);
  // Thorp's forecasts: each class not yet measured, and 400M
  let fcNoise = 0;
  if (showFc && (fits.straight || fits.bending)) {
    const measured = new Set(table.filter(r => r.kind === 'thorp').map(r => (r.ship_key || '').split(':')[0]));
    const at = rungs.filter(r => !measured.has(r.preset) && r.total).map(r => ({ cls: r.preset, params: r.total }));
    if (sq.smoke_at && !at.some(a => Math.abs(a.params - sq.smoke_at) / sq.smoke_at < 0.1)) at.push({ label: `Thorp ${fmtParams(sq.smoke_at)}`, params: sq.smoke_at, smoke: true });
    for (const a of at) {
      const x = Math.log10(a.params), st = fits.straight ? polyval(fits.straight, x) : null, be = fits.bending ? polyval(fits.bending, x) : null;
      // the Chaining board holds only what clears the noise: a forecast still in it is counted, not drawn
      if ((be ?? st) > (lbData.noise ?? 0.03)) rows.push({ kind: 'forecast', name: a.label, cls: a.cls, params: a.params, lift: be ?? st, straight: st, bending: be, smoke: a.smoke });
      else fcNoise++;
    }
  }
  if (fcNoise) document.getElementById('lbfcnote').innerHTML += ` · ${fcNoise} forecast${fcNoise === 1 ? '' : 's'} still in the noise, so not on this board`;
  // the ranked rows keep their rank; a forecast sits where its lift would, unranked
  rows.sort((a, b) => (b.lift ?? -9) - (a.lift ?? -9) || (b.params ?? 0) - (a.params ?? 0));
  const liftCell = r => r.pending ? '<span class="s">being scored</span>'
    : r.kind === 'forecast' ? `<span title="bending (probable) ${signed(r.bending)}; straight (conservative) ${signed(r.straight)}"><b>${signed(r.bending)}</b> <span class="s">bending</span><div class="s">${signed(r.straight)} straight</div></span>`
    : chainingCell(r.lift, thr);
  // a competitor: Thorp must match it at a tenth its size; each fit's reading there (and P, once forecastable), and the size
  // where each fit first reaches it
  const matchCell = r => {
    if (r.kind !== 'outside' || !r.competitor) return '';
    const tenth = r.tenth && r.tenth.smoke_at || (r.params ? r.params / 10 : null);
    let out = `<div><b>${fmtParams(tenth)}</b> <span class="s">a tenth its size</span></div>`;
    const c = r.tenth;
    if (c && c.scored) out += ['bending', 'linear'].filter(k => c[k]).map(k => `<div title="5–95% ${signed(c[k].band[0])} to ${signed(c[k].band[1])}"><span class="s">${k === 'linear' ? 'straight' : k}</span> ${signed(c[k].predicted)}${c[k].p_at_or_above_target != null ? ` · <b>P ${Math.round(100 * c[k].p_at_or_above_target)}%</b>` : ''}</div>`).join('');
    if (r.lift != null && (fits.bending || fits.straight)) {
      const reach = k => fits[k] ? fitReachAt(fits[k], r.lift, top) : undefined;
      out += `<div class="s">fits reach it at: ${['bending', 'straight'].filter(k => fits[k]).map(k => `${k} ${reach(k) == null ? 'never' : fmtParams(reach(k))}`).join(' · ')}</div>`;
    }
    return out;
  };
  let rank = 0;
  tb.innerHTML = rows.map(r => {
    const ranked = r.kind !== 'forecast' && !r.pending; if (ranked) rank++;
    const name = r.kind === 'thorp' ? `<a href="#/leaderboard/thorp/${encodeURIComponent(r.ship.ship_key)}"><b>${esc(r.ship.name || `Thorp ${r.cls}`)}</b></a><div class="s">${r.ship.ship_key ? `<a href="#${shipHash(r.ship.ship_key)}">${esc(r.ship.ship)}</a>` : esc(r.ship.ship || '')} · ${r.ship.sailings ?? 1} sailing${(r.ship.sailings ?? 1) === 1 ? '' : 's'}</div>`
      : r.kind === 'forecast' ? `${r.cls ? classLink(r.cls) : `<b>${esc(r.name)}</b>`} <span class="${pillCls('accent')}">forecast</span>${r.smoke ? '<div class="s">a tenth of Qwen3 4B</div>' : ''}`
      : `${r.model && !r.pending ? `<a href="#/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a>` : `<b>${esc(r.name)}</b>`}${r.competitor ? ` <span class="${pillCls('blue')}" title="a 2–4B competitor: Thorp must match it at a tenth its size">2–4B</span>` : ''}<div class="s">${esc(r.maker)}</div>`;
    return `<tr class="lb-${r.kind}${r.kind === 'forecast' && !trusted ? ' untrusted' : ''}${r.pending ? ' pending' : ''}"><td>${ranked ? rank : ''}</td><td>${name}</td><td>${fmtParams(r.params)}</td>
      <td>${liftCell(r)}</td><td>${logicCell(r.logic, r.kind)}</td><td>${r.kind === 'forecast' ? '' : causeCell(r.src && r.src.cause_gain)}</td><td>${r.passed != null ? `${r.passed} of ${tests.length}` : ''}</td>${tests.map(t => `<td class="tcol">${r.tests ? testCell(r.tests[t.key]) : ''}</td>`).join('')}<td>${matchCell(r)}</td></tr>`;
  }).join('') || `<tr><td colspan="${8 + tests.length}" class="${emptyCls(true)}">no readings yet</td></tr>`;
}


// ---- Chaining two facts (#/discoveries, the first subtab): the method, with the live numbers beside it. Where the claim
// stands (Smoking the 2-4B range), an example pair from each chaining test (/api/chain), each chain's grade, the backtest.
// The copy is in Discoveries.astro; thresholds are read from fleet through the payloads, so page and code agree.
let tfKey = null;
async function drawTwoFacts() {
  const el = document.getElementById('tfstatus'); if (!el || !discData) return;
  const cr = discData.chain_rungs || {}, chains = cr.chains || [];
  drawMethod('chaining');
  let sq, lb; try { [sq, lb] = await Promise.all([get('/api/smoking_qwen'), lbData ? lbData : get('/api/leaderboard')]); } catch (e) { return; }
  // the chaining test of each chain: the rung whose class is the 50m (fleet.RUNGS' "Chains two facts into a third")
  const rungIdx = (cr.rungs || []).findIndex(r => /chains two facts/i.test(r.title || ''));
  const tests = chains.map(c => ({ chain: c[c.length - 1], key: c[rungIdx >= 0 ? rungIdx : 4] }));
  const pulls = await Promise.all(tests.map(t => chainCache.get(t.chain) ? chainCache.get(t.chain) : get('/api/chain?key=' + encodeURIComponent(t.chain)).then(d => { if (d && d.steps) chainCache.set(t.chain, d); return d; }).catch(() => null)));
  const key = JSON.stringify([sq, lb && lb.reference, cr.grades, pulls.map(p => p && p.key)]); if (key === tfKey) return; tfKey = key;
  const thr = sq.threshold ?? 0.1, noise = sq.noise ?? 0.03;
  const ft = discTricks.find(x => x.key === (tests[0] || {}).key);
  document.getElementById('tfthr').textContent = thr;
  document.getElementById('tfnoise').textContent = noise;
  if (ft && ft.min_score) document.getElementById('tfshare').textContent = `${Math.round(100 * ft.min_score)}% (two in three)`;
  // where the claim stands
  const rng = sq.range || [], scored = rng.filter(c => c.scored), above = (sq.classes_above_noise || []).length;
  const pLin = sq.p_range_linear, pBend = sq.p_range_bending;
  const state = sq.forecastable && pLin >= 0.9 ? ['good', 'claimed'] : sq.forecastable && pBend >= 0.9 ? ['accent', 'probable'] : ['', 'not claimed'];
  const best = (lb.board || []).filter(b => b.best && b.best.chaining_lift != null).sort((a, b) => b.best.chaining_lift - a.best.chaining_lift)[0];
  el.innerHTML = `<div class="tfs"><span class="${pillCls(state[0])}">${state[1]}</span></div>
    <div class="tfs"><b>${scored.length} of ${rng.length}</b><span>2–4B competitors scored${sq.hardest ? `; the hardest, ${esc(sq.hardest)}` : ''}</span></div>
    <div class="tfs"><b>${above} of 3</b><span>Thorp classes above the noise, needed before any forecast</span></div>
    <div class="tfs"><b>${best ? signed(best.best.chaining_lift) : '–'}</b><span>Thorp's best chaining lift so far${best ? ` (${esc(best.best.preset)}, ${esc(best.best.ship || best.best.run)})` : ''}</span></div>
    <div class="tfs"><b>${sq.forecastable ? `${pLin == null ? '–' : Math.round(100 * pLin) + '%'} · ${pBend == null ? '–' : Math.round(100 * pBend) + '%'}` : 'not yet'}</b><span>P over the range, straight · bending</span></div>
    <div class="tfcomp">${rng.map(c => `<span title="${esc(c.model)}">${esc(c.label)} <b>${c.scored && c.chaining_lift != null ? signed(c.chaining_lift) : '…'}</b> <i>at ${fmtParams(c.params)} → Thorp at ${fmtParams(c.smoke_at || c.params / 10)}</i></span>`).join('')}</div>`;
  // an example pair from each chaining test
  const passage = p => p.frame && p.prompt.endsWith(p.frame) && p.prompt.length > p.frame.length
    ? `${esc(p.prompt.slice(0, p.prompt.length - p.frame.length).trimEnd())} <span class="pfsep">/</span> <span class="pframe">${esc(p.frame)}</span> …` : `${esc(p.prompt)} …`;
  document.querySelector('#tfexamples tbody').innerHTML = tests.map((t, i) => {
    const d = pulls[i], st = d && d.steps && d.steps.find(x => x.key === t.key), p = st && st.pairs && st.pairs[0];
    return `<tr><td><a href="#/discoveries/chains/${esc(t.chain)}">${esc(d ? d.name : t.chain)}</a><div class="s"><a href="#/discoveries/${esc(t.key)}">${esc(st ? st.name : t.key)}</a></div></td>
      <td>${p ? passage(p) : '<span class="s">pairs not written yet</span>'}</td><td class="good">${p ? esc(p.idea) : ''}</td><td class="bad">${p ? esc(p.rival) : ''}</td></tr>`;
  }).join('');
  // each chain's grade
  const nameOf = k => ((discData.known_tricks || []).find(x => x.key === k) || {}).name || k;
  document.getElementById('tfgrades').innerHTML = chains.map(c => {
    const end = c[c.length - 1], g = (cr.grades || {})[end];
    return `<div class="tfg"><a href="#/discoveries/chains/${esc(end)}"><b>${esc(nameOf(end))}</b></a> ${gradeNote(g, nameOf)}${g && g.counts ? `<div class="s">${Object.entries(g.counts).map(([k, n]) => n).join(' → ')} of ${(cr.graded_on || []).length || '–'} models pass each rung, keel up</div>` : ''}</div>`;
  }).join('');
  // the backtest
  const fmtBand = f => `${signed(f.predicted)} <span class="s">(${signed(f.band[0])} to ${signed(f.band[1])})</span>`;
  document.getElementById('tfbacktest').innerHTML = (sq.backtest || []).map(b => `<div class="sqbt"><b>${esc(b.test)}</b> · actual ${signed(b.actual)}
    ${['linear', 'bending'].filter(k => b[k]).map(k => `<div class="sqbk ${b[k].inside_band ? 'good' : 'bad'}">${k === 'linear' ? 'straight' : 'bending'}: ${fmtBand(b[k])} · ${b[k].inside_band ? 'inside the band' : b[k].predicted < b.actual ? 'missed, too low' : 'missed, too high'}</div>`).join('')}</div>`).join('')
    + '<p class="s">The straight line has missed low both times, which is why it is the conservative curve and the claim is held to it.</p>';
}


// ---- a trick's methodology (fleet.METHODS, /api/discoveries methods): rendered as written in fleet. The cards are the stars
// the trick needs; one in the deck links to the star chart and pulses when any sailing has lit it, a planned one is dimmed.
const COVERED = { yes: ['good', 'covered'], partly: ['accent', 'partly'], no: ['bad', 'not covered'] };
function starOfCard(name) {
  const n = name.toLowerCase().replace(/\(.*?\)/g, '').replace(/[^a-z]+/g, ' ').trim();
  return (discStars || []).find(st => { const sn = (st.name || st.key).toLowerCase().replace(/^the\s+/, '').replace(/[^a-z]+/g, ' ').trim(); return sn === n || st.key.replace(/_/g, ' ') === n; }) || null;
}
function drawMethod(key) {
  const m = ((discData || {}).methods || {})[key], el = document.getElementById('method'); if (!el) return;
  el.hidden = !m; if (!m) return;
  document.getElementById('mname').textContent = m.name.toLowerCase();
  document.getElementById('mstatus').textContent = m.status || '';
  document.getElementById('mtrick').textContent = m.trick || '';
  document.querySelector('#mparts tbody').innerHTML = (m.parts || []).map(p => { const c = COVERED[p.covered] || ['', p.covered];
    return `<tr><td><b>${esc(p.part)}</b></td><td>${esc(p.meaning)}</td><td><span class="${pillCls(c[0])}">${esc(c[1])}</span></td></tr>`; }).join('');
  document.getElementById('mgaps').innerHTML = (m.gaps || []).map(g => `<li>${esc(g)}</li>`).join('');
  document.querySelector('#mcontrols tbody').innerHTML = (m.controls || []).map(c => `<tr><td><b>${esc(c.control)}</b></td><td>${esc(c.does)}</td></tr>`).join('');
  document.getElementById('mmetric').textContent = m.metric || '';
  document.getElementById('mcards').innerHTML = (m.cards || []).map(c => {
    const planned = c.status !== 'in the deck', st = planned ? null : starOfCard(c.card);
    const lit = st && (st.ships || []).some(x => x.steps_to_lit != null || x.shared_steps_to_lit != null);
    // which classes have lit it (one head or shared), smallest first, each with its first sailing and step; or the nearest
    let foot = '';
    if (st) {
      const by = {};
      for (const x of st.ships || []) {
        const at = x.steps_to_lit ?? x.shared_steps_to_lit; if (at == null) continue;
        const b = by[x.preset]; if (!b || at < b.at) by[x.preset] = { at, x, shared: x.steps_to_lit == null };
      }
      const cls = Object.keys(by).sort((a, b) => classRank(a) - classRank(b));
      if (cls.length) foot = `<div class="foot mlit">lit by ${cls.map(p => `<span title="first by ${esc(by[p].x.name)} at step ${by[p].at}${by[p].shared ? ' (two heads together)' : ''}">${classLink(p)}</span>`).join(' · ')}</div>`;
      else {
        const near = [...(st.ships || [])].filter(x => x.best != null).sort((a, b) => b.best - a.best)[0];
        foot = `<div class="foot s">not lit by any class yet${near ? `; nearest ${esc(near.preset)} at ${fmt(near.best)} of ${st.threshold}` : ''}</div>`;
      }
    }
    const vb = st ? cardBadge((discData || {}).card_verdicts, st.key) : '';
    const inner = `${st ? cardArt(st.key) : ''}${vb ? `<div class="vrow">${vb}</div>` : ''}<div class="top"><span class="preset">${esc(c.card)}</span><span class="${pillCls(planned ? '' : lit ? 'good' : 'blue')}">${planned ? 'planned' : lit ? 'lit' : 'in the deck'}</span></div><div class="ov">${esc(c.operation)}</div>${foot}`;
    return planned ? `<div class="${cardCls(false, 'card planned')}">${inner}</div>` : `<div class="${cardCls(false, `card${lit ? ' lit pulse' : ''}`)}">${inner}<div class="foot"><a href="#/discoveries/stars">${st ? esc(st.name) : 'the star chart'} on the star chart →</a></div></div>`;
  }).join('');
}


// ---- the bridge card over layers (#/discoveries/stars; /api/bridge): how strongly the answer's position carries the middle
// term at each layer, one line per run that read it, coloured by class, the threshold dotted. A two-hop chain needs the
// bridge resolved in the middle layers, before the second hop.
let bridgeKey = null;
async function drawBridge() {
  if (!document.getElementById('bridgechart')) return;
  let d; try { d = await get('/api/bridge'); } catch (e) { return; }
  const key = JSON.stringify(d); if (key === bridgeKey) return; bridgeKey = key;
  const runs = (d.runs || []).filter(r => r.curve && r.curve.length);
  if (!runs.length) { empty('bridgechart', 'no voyage has read the bridge yet: it comes with the cards evaluator'); return; }
  const presets = [...new Set(runs.map(r => r.preset))].sort((a, b) => classRank(a) - classRank(b));
  const traces = runs.map(r => ({ x: r.curve.map((_, i) => i), y: r.curve, name: `${r.name} (${r.preset})`, mode: 'lines+markers', marker: { size: 5 },
    line: { color: PALETTE[presets.indexOf(r.preset) % PALETTE.length], width: 1.6 }, hovertemplate: `${esc(r.name)}<br>layer %{x}<br>%{y:.3f} nats<extra></extra>` }));
  const shapes = d.threshold != null ? [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: d.threshold, y1: d.threshold, line: { color: tok('accent'), width: 1, dash: 'dot' } }] : [];
  plot('bridgechart', traces, layout({ xaxis: { title: { text: 'layer (bottom of the stack first)' }, dtick: 1 }, yaxis: { title: { text: 'the bridge at the answer (nats)' } }, shapes, height: 320 }));
}


// ==================================================================================== one competitor
// (#/leaderboard/competitor/<model>; /api/competitor, UI.md "Leaderboard"): an outside model's chaining result, the logic
// deck, its cards and every rung.
const LOGIC_VARIANTS = [['lift_one_hop', 'one hop'], ['lift_both', 'two hops (both premises)'], ['lift_three_hop', 'three hops'], ['lift_first', 'first premise only'], ['lift_second', 'second premise only'], ['lift_swapped', 'premises swapped'], ['lift_padded', 'a third fact added']];
// a star's about, cut to what fits on the back of a card: whole sentences up to about 170 characters, or the first
// sentence up to its colon when that one alone is longer (the example after the colon is on the star chart)
function shortAbout(t) {
  if (!t) return '';
  const sents = t.trim().split(/(?<=\.)\s+/);  // a full stop then a space ends a sentence; 0.3 does not
  let out = '';
  for (const x of sents) { if ((out + ' ' + x).length > 170) break; out = out ? out + ' ' + x : x; }
  return out || sents[0].split(': ')[0].replace(/[.,;]?$/, '.');
}
async function loadCompetitor() {
  if (!cpModel) return;
  let d; try { d = await get(cpThorp ? '/api/thorp?ship=' + encodeURIComponent(cpThorp) : '/api/competitor?model=' + encodeURIComponent(cpModel)); } catch (e) { d = null; }
  if (!d || d.error || !d.model) { document.getElementById('cptitle').textContent = `no model called ${cpModel}`; return; }
  const key = JSON.stringify(d) + discStars.length; if (key === cpKey) return; cpKey = key;
  // the cards' marks come from the stars; fetched once, without holding up the page (it redraws when they arrive)
  if (!discStars.length && !cpStarsAsked) { cpStarsAsked = true; get('/api/discoveries').then(x => { discStars = x.stars || []; if (page === 'competitor') loadCompetitor(); }).catch(() => {}); }
  document.getElementById('cptitle').textContent = d.label;
  document.getElementById('cppills').innerHTML = d.thorp ? `<span class="${pillCls('good')}">Thorp</span>${d.current ? '' : ` <span class="${pillCls('')}">not the current version</span>`}`
    : (d.competitor ? `<span class="${pillCls('blue')}">2–4B competitor</span> ` : '') + (d.ladder ? `<span class="${pillCls('')}">reference ladder</span>` : '');
  const chainingTests = d.chains.map(c => c.rungs.find(r => /chains two facts/i.test(r.rung || ''))).filter(Boolean);
  const read = chainingTests.filter(t => t.lift != null), mean = read.length ? read.reduce((a, t) => a + t.lift, 0) / read.length : null;
  const passed = chainingTests.filter(t => t.performed).length, t = d.tenth;
  if (d.thorp) {
    const sh = d.ship || {}, crowned = c => c ? c.replace('T', ' ') : '';
    document.getElementById('cpover').innerHTML = [
      ['class', classLink(sh.preset)], ['parameters', fmtParams(d.params)],
      ['the ship', `${sh.ship_key ? `<a href="#${shipHash(sh.ship_key)}">${esc(sh.ship || sh.ship_key)}</a>` : esc(sh.ship || '')}<div class="s">${sh.sailings ?? 0} sailing${sh.sailings === 1 ? '' : 's'}, every reading the mean of their latest</div>`],
      ['the voyages', (sh.runs || []).map(r => `<a href="#${shipHash(r)}">${esc(r)}</a>`).join(', ') || '–'],
      ['version', `${d.version ? `<b>v${d.version}</b>, crowned ${esc(crowned(d.crowned))}` : 'not crowned'}${(d.history || []).length ? `<div class="s">${d.history.map(h => `v${h.v} ${esc(h.ship)} (${signed(h.chaining_lift)}, ${esc(crowned(h.crowned))})`).join(' → ')}</div>` : ''}<div class="s">a new version is crowned only when a ship beats the last by more than the noise (0.03)</div>`],
    ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  } else document.getElementById('cpover').innerHTML = [
    ['made by', esc(makerOf(d.model) || '–')], ['parameters', fmtParams(d.params)], ['checkpoint', `<span class="mono">${esc(d.model)}</span>`],
    ['Thorp must match it at', d.competitor && d.params ? `<b>${fmtParams(t && t.smoke_at || d.params / 10)}</b> <span class="s">a tenth its size</span>${t && t.scored ? ['bending', 'linear'].filter(k => t[k]).map(k => `<div class="s">${k === 'linear' ? 'straight' : k} forecast there ${signed(t[k].predicted)}${t[k].p_at_or_above_target != null ? ` · P ${Math.round(100 * t[k].p_at_or_above_target)}%` : ''}</div>`).join('') : ''}` : '<span class="s">not a competitor: a reference model that grades the chains</span>'],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  // the chaining result
  const L = d.logic;
  document.getElementById('cpsum').innerHTML = !d.scored ? '<div class="${emptyCls()}">not scored yet: the competitors are being scored now, a few minutes each</div>'
    : `<div class="tfs"><b>${mean == null ? '–' : signed(mean)}</b><span>chaining lift (mean of the four)</span></div>
       <div class="tfs"><b>${passed} of ${chainingTests.length}</b><span>chaining tests performed</span></div>
       <div class="tfs"><b class="${L && L.performed ? 'good' : ''}">${L && L.gain != null ? signed(L.gain) : 'not read'}</b><span>chaining gain on the logic deck${L && L.score != null ? `, ${Math.round(100 * L.score)}% of items right` : ''}${L && L.items_n ? `, ${L.items_n} items` : ''}${L && L.performed ? ' ✓' : ''}</span></div>`;
  document.querySelector('#cptests tbody').innerHTML = chainingTests.map((x, i) => `<tr><td><a href="#/discoveries/${esc(x.key)}"><b>${esc(x.name)}</b></a></td><td><a href="#/discoveries/chains/${esc(d.chains[i].key)}">${esc(d.chains[i].name)}</a></td>
    <td class="${x.performed ? 'good' : ''}">${x.lift != null ? signed(x.lift) : '–'}</td><td>${x.score != null ? Math.round(100 * x.score) + '%' : '–'}</td><td>${x.performed ? '✓' : ''}</td></tr>`).join('');
  if (L) {
    const vs = LOGIC_VARIANTS.filter(([k]) => L[k] != null);
    plot('cpvariants', [{ type: 'bar', orientation: 'h', y: vs.map(v => v[1]), x: vs.map(([k]) => L[k]), marker: { color: vs.map(([k]) => k === 'lift_both' ? tok('accent') : /one_hop|three_hop/.test(k) ? tok('blue') : tok('muted')) },
      hovertemplate: '%{y}: %{x:.3f}<extra></extra>' }], layout({ height: 260, margin: { l: 170, r: 10, t: 10, b: 30 }, yaxis: { autorange: 'reversed' }, xaxis: { title: { text: 'mean lift' }, zeroline: true } }));
    const rel = Object.keys(L).filter(k => k.startsWith('gain_')).map(k => [k.slice(5), L[k]]);
    // cause and effect is the leaderboard's own measure, so its bar is outlined and named
    if (rel.length) plot('cprelations', [{ type: 'bar', x: rel.map(r => r[0] === 'cause' ? 'cause and effect' : r[0]), y: rel.map(r => r[1]),
      marker: { color: rel.map(r => r[1] >= 0.1 ? tok('good') : r[1] >= 0 ? tok('blue') : tok('bad')), line: { color: rel.map(r => r[0] === 'cause' ? tok('accent') : 'rgba(0,0,0,0)'), width: rel.map(r => r[0] === 'cause' ? 3 : 0) } },
      hovertemplate: '%{x}: %{y:.3f}<extra></extra>' }],
      layout({ height: 260, margin: { l: 50, r: 10, t: 10, b: 40 }, yaxis: { title: { text: 'chaining gain' } }, shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0.1, y1: 0.1, line: { color: tok('accent'), dash: 'dot', width: 1 } }] }));
    else empty('cprelations', 'no per-relation gains read');
  } else { empty('cpvariants', 'the logic deck is not read on this model yet'); empty('cprelations', '–'); }
  // the cards: the hand it holds (lit, fanned) and what is still in the deck (set aside face down), then the readings
  const C = d.cards, readable = !C || C.attention_readable !== false;
  const thrOf = key => ((discStars || []).find(s => s.key === key) || {}).threshold;
  const DECK = [['previous_word', 'Previous-word'], ['nevermore', 'Nevermore (induction)'], ['mover', 'Mover'], ['comparator', 'Comparator'], ['bridge', 'Bridge']];
  const hand = DECK.map(([key, name]) => {
    const x = C && C[key], thr = thrOf(key);
    const state = !C ? 'unread' : key !== 'bridge' && !readable ? 'unreadable' : !x ? 'unread' : (x.lit || x.lit_shared) ? 'lit' : (x.max == null && key === 'bridge') ? 'unreadable' : 'unlit';
    const best = x ? Math.max(x.max ?? -Infinity, x.shared ?? -Infinity) : null;
    const verdict = (d.card_verdicts || {})[key];
    const star = (discStars || []).find(st => st.key === key);
    return { key, name, held: state === 'lit', state, near: thr && best != null && isFinite(best) ? best / thr : null, x, thr, untrusted: !!verdict && verdict.valid === false,
      about: star && shortAbout(star.about), href: '#/discoveries/stars' };
  });
  const rowOf = c => {
    const x = c.x || {}, v = cardBadge(d.card_verdicts, c.key);
    const read = c.state === 'unread' ? '<span class="s">not read yet</span>' : c.state === 'unreadable' ? '<span class="s">unreadable</span>'
      : c.key === 'bridge' ? `best ${x.max != null ? fmt(x.max) + ' nats' : '<i>unreadable</i>'}${x.best_layer != null ? ` at layer ${x.best_layer}${x.layers ? ` of ${x.layers}` : ''}` : ''}`
      : `one head ${x.max != null ? fmt(x.max) : '–'}${x.shared != null ? ` · shared ${fmt(x.shared)}${x.shared_layer != null ? ` (layer ${x.shared_layer})` : ''}` : ''}${'copy_gain' in x ? ` · copy gain ${x.copy_gain != null ? fmt(x.copy_gain) + ' nats/token' : '<i>unreadable</i>'}` : ''}`;
    const f = CARD_FACE[c.key] || {};
    return `<tr class="${c.held ? 'held' : ''}"><td><span class="suitmark">${f.rank || ''}${f.suit || ''}</span> <b>${esc(c.name)}</b></td><td>${c.held ? `<span class="${pillCls('good')}">in hand</span>` : `<span class="${pillCls('')}">${{ unlit: 'in the deck', unread: 'not read', unreadable: 'unreadable' }[c.state]}</span>`}</td>
      <td>${read}</td><td>${c.thr != null ? c.thr : '–'}</td><td>${v}</td></tr>`;
  };
  document.getElementById('cpcards').innerHTML = deckHand(hand, { empty: !C ? 'its cards are being read' : 'no card lit yet' })
    + `<div class="scroll"><table class="decktable" data-nosort><thead><tr><th>card</th><th></th><th>its reading</th><th>the mark</th><th>the judge</th></tr></thead><tbody>${hand.map(rowOf).join('')}</tbody></table></div>`
    + (C && C.bridge && C.bridge.curve && C.bridge.curve.length ? '<div class="k mt">the bridge over layers <span class="s">nats at the answer\'s position; the mark dotted</span></div><div class="chart cpbridge" id="cpbridge"></div>' : '');
  if (!cpThorp) competitorKnockout(d.model).then(k => {
    if (!k) return;
    // the silenced heads on each card's row: "its 8 heads, layer:head", and the knockout's verdict
    document.querySelectorAll('#cpcards .decktable tbody tr').forEach((tr, i) => {
      const key = DECK[i] && DECK[i][0], heads = (k.card_heads || {})[key], v = (k.verdict || {})[key];
      if (heads && heads.length) tr.cells[2].insertAdjacentHTML('beforeend', `<div class="s kohd">knocked out: ${heads.map(h => `${h[0]}:${h[1]}`).join(' ')}${v ? ` · ${v.necessary ? '<b class="good">necessary</b>' : 'not shown necessary'}` : ''}</div>`);
    });
  });
  const B = C && C.bridge;
  if (B && B.curve && B.curve.length) {
    const thr = thrOf('bridge');
    plot('cpbridge', [{ x: B.curve.map((_, i) => i), y: B.curve, mode: 'lines+markers', line: { color: B.lit ? tok('good') : tok('blue'), width: 1.6 }, hovertemplate: 'layer %{x}: %{y:.2f}<extra></extra>' }],
      layout({ height: 160, margin: { l: 40, r: 10, t: 6, b: 30 }, showlegend: false, xaxis: { title: { text: 'layer' }, dtick: Math.max(1, Math.round(B.curve.length / 8)) }, shapes: thr != null ? [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: thr, y1: thr, line: { color: tok('accent'), dash: 'dot', width: 1 } }] : [] }));
  }
  // every rung
  const width = Math.max(...d.chains.map(c => c.rungs.length - 1));
  document.querySelector('#cprungs thead').innerHTML = `<tr><th>chain</th>${d.chains[0].rungs.slice(0, width).map(r => `<th>${esc(r.rung || '')}</th>`).join('')}</tr>`;
  document.querySelector('#cprungs tbody').innerHTML = d.chains.map(c => `<tr><td><a href="#/discoveries/chains/${esc(c.key)}"><b>${esc(c.name)}</b></a></td>${c.rungs.slice(0, width).map(r => `<td><a href="#/discoveries/${esc(r.key)}">${esc(r.name)}</a><div class="${r.performed ? 'good' : 's'}">${r.lift != null ? `${signed(r.lift)} · ${r.score != null ? Math.round(100 * r.score) + '%' : ''}${r.performed ? ' ✓' : ''}` : 'not read'}</div></td>`).join('')}</tr>`).join('');
}


// ---- the card judge (thorp.card_check verdicts): a NECESSARY card is played by every model that chains two facts; a MARKER
// is played only by them; a card whose reading isn't trusted is "not trusted"; else it is neither
function cardBadge(verdicts, key) {
  const v = (verdicts || {})[key]; if (!v) return '';
  const tip = `played by ${v.chainers_lit} of the models that chain two facts; dark in ${v.non_chainers_dark} that don't`;
  if (v.valid === false) return `<span class="vbadge warn" title="${esc(tip)}: the reading is not trusted yet">not trusted</span>`;
  if (v.marker) return `<span class="vbadge marker" title="${esc(tip)}: only the chainers play it">marker</span>`;
  if (v.necessary) return `<span class="vbadge need" title="${esc(tip)}: every chainer plays it, so a ship must draw it">necessary card</span>`;
  return `<span class="vbadge" title="${esc(tip)}">neither necessary nor a marker</span>`;
}


// ---- the art (thorp/dash/art/generate_art.py: Eduardo Risso style, made with fal; public/art/<key>.png): one image per class
// of ship and one per playing card. An image that isn't there removes itself, so a card without art draws no frame.
const ART_CARDS = new Set(['previous_word', 'nevermore', 'mover', 'comparator', 'bridge']);
const classSlug = name => (name || '').toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-');
function artImg(key, cls = 'cardart') {
  return key ? `<img class="${cls}" src="art/${encodeURIComponent(key)}.png" alt="" loading="lazy" onerror="this.remove()">` : '';
}
const cardArt = key => ART_CARDS.has(key) ? artImg(key, 'cardart face') : '';


// ---- the APPROACHING CHAINING board (leaderboard.payload table, group "approaching"): models whose chaining lift is still in
// the noise, ranked by the cards every chainer holds (previous-word, Nevermore, mover, comparator) and then by following one
// premise (the logic deck's one-hop lift). Their chaining lift is shown greyed: below +0.03 it is noise.
const NEEDED = [['previous_word', 'Previous-word'], ['nevermore', 'Nevermore'], ['mover', 'Mover'], ['comparator', 'Comparator']];
function drawLbApproach(rows, thr) {
  const tb = document.querySelector('#lbapproach tbody'); if (!tb) return;
  const icons = r => {
    const c = r.src.cards;
    if (!c) return `<span class="miniset"><span class="s">unreadable</span></span>`;
    return `<span class="miniset">${NEEDED.map(([k, n]) => { const f = CARD_FACE[k] || {}; return `<span class="minicard${c[k] ? ' on' : ''}" title="${esc(n)}: ${c[k] ? 'lit' : 'not lit'}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span>`; }).join('')}</span>`;
  };
  tb.innerHTML = rows.map(r => {
    const name = r.kind === 'thorp' ? `<a href="#/leaderboard/thorp/${encodeURIComponent(r.ship.ship_key)}"><b>${esc(r.ship.name)}</b></a><div class="s">${r.ship.ship_key ? `<a href="#${shipHash(r.ship.ship_key)}">${esc(r.ship.ship || '')}</a>` : esc(r.ship.ship || '')}${r.ship.sailings ? ` · ${r.ship.sailings} sailing${r.ship.sailings === 1 ? '' : 's'}` : ''}</div>`
      : `<a href="#/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a>${r.competitor ? ` <span class="${pillCls('blue')}">2–4B</span>` : ''}<div class="s">${esc(r.maker)}</div>`;
    const held = r.src.cards_held;
    const rank = r.src.tied ? `<span title="tied within the noise: one-hop lifts within 0.05 of each other">=${r.src.rank}</span><div class="s tiehint">tied within the noise</div>` : r.src.rank;
    return `<tr class="lb-${r.kind}"><td>${rank}</td><td>${name}</td><td>${fmtParams(r.params)}</td>
      <td>${icons(r)} <span class="s">${held == null ? '' : `${held} of 4`}</span></td>
      <td>${r.src.one_hop != null ? signed(r.src.one_hop) : '–'}</td>
      <td>${causeCell(r.src.cause_gain)}</td>
      <td class="noise" title="below +0.03 the chaining lift is noise">${r.lift != null ? signed(r.lift) : '–'}</td></tr>`;
  }).join('') || '<tr><td colspan="7" class="${emptyCls(true)}">nothing below the line</td></tr>';
}


// ---- the card census (the card_census voyage page; /api/census): ablations of each class's fitout. Per fitout, a grid of
// variations (the fitout first) × the four necessary cards and cause and effect, each cell the latest stage's reading (lit ✓;
// cause with its change from the fitout's own at that stage); a row opens to its three stages.
let censusKey = null;
const censusOpen = new Set();
const STAGE_NAMES = ['pretraining', 'post-training 1', 'post-training 2'];
async function drawCensus() {
  const el = document.getElementById('censusgrid'); if (!el) return;
  let d; try { d = await get('/api/census'); } catch (e) { return; }
  const key = JSON.stringify(d) + [...censusOpen].join(','); if (key === censusKey) return; censusKey = key;
  const cards = d.cards || [], cs = d.censuses || [];
  if (!cs.length) { el.innerHTML = '<div class="${emptyCls()}">no fitout census written yet</div>'; return; }
  const read = st => st && (st.cards && Object.keys(st.cards).length || st.cause != null);
  const lastRead = r => { for (let i = r.stages.length - 1; i >= 0; i--) if (read(r.stages[i])) return [r.stages[i], i]; return [null, -1]; };
  const cardCell = (st, k, i, last) => {
    const x = st && st.cards && st.cards[k.key]; if (!x) return '<td class="cen q">–</td>';
    const best = Math.max(x.one ?? -Infinity, x.shared ?? -Infinity), near = Math.max(0, Math.min(1, best / k.threshold));
    return `<td class="cen${x.lit ? ' lit' : ''}" style="--near:${(100 * near).toFixed(0)}%" title="${esc(k.name)}: one head ${x.one != null ? x.one.toFixed(3) : '–'}${x.shared != null ? `, shared ${x.shared.toFixed(3)}` : ''}; the mark ${k.threshold}">${isFinite(best) ? best.toFixed(2) : '–'}${x.lit ? ' ✓' : ''}${last && i < 2 ? `<div class="s">${esc(STAGE_NAMES[i])}</div>` : ''}</td>`;
  };
  const causeCell2 = (st, base) => {
    if (!st || st.cause == null) return '<td class="cen q">–</td>';
    const dlt = base && base.cause != null && st !== base ? st.cause - base.cause : null;
    return `<td class="cen${st.cause >= 0.1 ? ' lit' : ''}" title="cause and effect: the logic deck's chaining gain on its cause items${dlt != null ? `; ${signed(dlt)} against the fitout's own` : ''}">${signed(st.cause)}${dlt != null ? `<div class="s">${signed(dlt)} vs fitout</div>` : ''}</td>`;
  };
  el.innerHTML = cs.map(c => {
    const sailed = c.rows.filter(r => r.stages.some(read)).length, base = c.rows.find(r => r.variation === 'fitout');
    const head = `<div class="censushead"><span class="cenposs"><b>${c.possible.length} of ${cards.length}</b> possible at ${c.preset ? classLink(c.preset) : esc(c.key)}</span>
      <span class="miniset">${cards.map(k => { const f = CARD_FACE[k.key] || {}; return `<span class="minicard${c.possible.includes(k.key) ? ' on' : ''}" title="${esc(k.name)}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span>`; }).join('')}</span>
      <span class="s">${esc(c.name || c.key)} · ${sailed} of ${c.rows.length} variations read${c.summary ? ' · census written' : ''}</span></div>`;
    const rows = c.rows.map(r => {
      const [st, i] = lastRead(r), open = censusOpen.has(c.key + '|' + r.variation);
      const status = r.stages.every(x => x.status === 'queued') ? 'queued' : r.stages.some(x => x.status === 'running') ? 'running' : r.stages.every(x => x.status === 'finished') ? 'finished' : 'sailing';
      const baseSt = base && i >= 0 ? base.stages[i] : null;
      const main = `<tr class="cenrow${open ? ' open' : ''}" data-cen="${esc(c.key + '|' + r.variation)}"><td><b>${esc(r.variation)}</b>${r.variation === 'fitout' ? ` <span class="${pillCls('accent')}">the fitout</span>` : ''}</td><td>${statusPill(status)}</td>
        ${st ? cards.map(k => cardCell(st, k, i, true)).join('') + causeCell2(st, baseSt) : `<td class="cen q" colspan="${cards.length + 1}">${status === 'queued' ? 'queued' : 'no reading yet'}</td>`}</tr>`;
      const detail = open ? r.stages.map((x, j) => `<tr class="censtage"><td class="s">↳ ${esc(STAGE_NAMES[j] || 'stage ' + (j + 1))}</td><td>${x.status === 'queued' ? esc(x.run) : `<a href="#${shipHash(x.run)}">${esc(x.run)}</a>`} ${statusPill(x.status)}</td>
        ${read(x) ? cards.map(k => cardCell(x, k, j, false)).join('') + causeCell2(x, base && base.stages[j]) : `<td class="cen q" colspan="${cards.length + 1}">${x.status === 'queued' ? 'queued' : 'no reading yet'}</td>`}</tr>`).join('') : '';
      return main + detail;
    }).join('');
    return `${head}<div class="scroll"><table class="censustable" data-nosort><thead><tr><th>variation <span class="s">open one for its stages</span></th><th></th>${cards.map(k => { const f = CARD_FACE[k.key] || {}; return `<th title="${esc(k.name)}, lit at ${k.threshold}">${f.rank || ''}${f.suit || ''} ${esc(f.short || k.name)}</th>`; }).join('')}<th title="the logic deck's chaining gain on its cause items, 0.1 the mark">cause and effect</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }).join('');
  el.querySelectorAll('tr.cenrow').forEach(tr => tr.onclick = e => {
    if (e.target.closest('a')) return;
    const k = tr.dataset.cen; censusOpen.has(k) ? censusOpen.delete(k) : censusOpen.add(k); censusKey = null; drawCensus();
  });
}


// ---- fitouts (#/shelves, top; thorp.shelves.fitouts, served warm): the training material matched to the pretraining and
// post-training stages. A card per fitout: its aim and settings, then two lanes of stage blocks sized by tokens (a block's
// shelf opens the shelf below), then its runs.
// one fitout as a card: its aim and settings, its two lanes of stage blocks, its runs (Shelves and the class pages)
function fitoutCard(f) {
  const tackOf = t => t ? `${esc(t.kind || 'tack')}${t.alpha != null ? ` ×${t.alpha}` : ''}` : '';
  const lane = (f, phase, label, note) => {
    const st = (f.stages || []).filter(x => x.phase === phase).sort((a, b) => a.order - b.order);
    if (!st.length) return '';
    const total = st.reduce((a, x) => a + (x.tokens || 0), 0);
    return `<div class="folane"><div class="folabel">${label} <span class="s">${big(total)} tokens · ${note}</span></div><div class="foblocks">${st.map((x, i) => `
      <div class="foblock ${phase === 'post-training' ? 'post' : 'pre'}" style="flex-grow:${Math.max(1, x.tokens || 0)}" title="${esc(x.purpose || '')}">
        <div class="fobn"><b>${x.order}. ${esc(x.name)}</b>${i ? '<span class="s"> ← seeded from the stage before</span>'.repeat(phase === 'post-training' ? 1 : 0) : ''}</div>
        <a class="foshelf" data-shelf="${esc(x.shelf)}" href="#/library">${esc(x.shelf_name || x.shelf)}</a>
        <div class="s">${x.books} books · ${big(x.tokens_per_pass)} × ${x.passes} = ${big(x.tokens)}</div>
        ${phase === 'post-training' ? `<div class="s">${x.lr != null ? `lr ${x.lr}` : ''}${x.tack ? ` · tack ${tackOf(x.tack)}` : ''}</div>` : ''}
        <div class="fop">${esc(x.purpose || '')}</div></div>`).join('')}</div></div>`;
  };
  return `<div class="fitout">
    <div class="fohead"><span class="${pillCls('')}">${esc(f.preset || '')}</span> <b>${esc(f.name)}</b></div>
    <p class="foaim">${esc(f.aim || '')}</p>
    <div class="s">${[f.positions ? `positions ${esc(f.positions)}` : 'learned positions', f.vocab ? `vocabulary ${big(f.vocab)}` : '', f.tack ? `tack ${tackOf(f.tack)}` : '', f.tokens ? `${big(f.tokens)} tokens in all` : ''].filter(Boolean).join(' · ')}</div>
    ${lane(f, 'pretraining', 'Pretraining', 'its stages in order, one voyage')}
    ${lane(f, 'post-training', 'Post-training', 'each stage seeded from the one before')}
    <div class="foruns"><span class="s">voyages</span> ${(f.runs || []).map(r => `<span class="forun">${r.status && r.status !== 'queued' ? `<a href="#${shipHash(r.run)}">${esc(r.run)}</a>` : esc(r.run)} ${statusPill(r.status || 'queued')}</span>`).join('') || '<span class="s">none yet</span>'}</div>
  </div>`;
}
let fitoutKey = null;
function drawFitouts(d) {
  const el = document.getElementById('fitouts'); if (!el) return;
  if (!d.fitouts) { el.innerHTML = `<div class="${emptyCls()}">${d.fitouts_error ? 'the fitouts could not be read: ' + esc(d.fitouts_error) : 'reading the fitouts (a few seconds)…'}</div>`; if (!d.fitouts_error) setTimeout(() => { if (page === 'shelves') loadShelves(); }, 2500); return; }
  const key = JSON.stringify(d.fitouts); if (key === fitoutKey) return; fitoutKey = key;
  if (!d.fitouts.length) { el.innerHTML = '<div class="${emptyCls()}">no fitouts yet</div>'; return; }
  el.innerHTML = d.fitouts.map(fitoutCard).join('');
  el.querySelectorAll('a.foshelf').forEach(a => a.onclick = e => {
    e.preventDefault(); shelfOpen = a.dataset.shelf; drawShelves();
    const tr = document.querySelector(`#shelfgroups tr[data-shelf="${CSS.escape(a.dataset.shelf)}"]`); if (tr) tr.scrollIntoView({ block: 'center', behavior: 'smooth' });
  });
}


// ---- cause and effect (leaderboard table cause_gain: the logic deck's chaining gain on its cause items): a value and a small
// bar with the 0.1 mark dotted. Eight items: a strong reading counts, a small one is noise.
const CAUSE_NOTE = "the logic deck's chaining gain on its cause-and-effect items (when X, then Y; Y makes Z): eight items, so a strong reading counts and a small one is noise; the mark, 0.1, dotted";
function causeCell(v) {
  if (v == null || !isFinite(v)) return '<span class="s">not read</span>';
  const pos = Math.max(-0.2, Math.min(1, v)), w = 100 * (pos + 0.2) / 1.2, mark = 100 * (0.1 + 0.2) / 1.2, zero = 100 * 0.2 / 1.2;
  return `<span class="cause${v >= 0.1 ? ' lit' : ''}" title="${esc(CAUSE_NOTE)}"><b>${signed(v)}</b><span class="cbar"><i style="left:${Math.min(w, zero)}%;width:${Math.abs(w - zero)}%"></i><u style="left:${mark}%"></u></span></span>`;
}


// ---- a class's Fitouts tab (#/classes/<class>/fitouts; /api/fitouts?preset=): the fitout cards for this class, then each
// stage's runs with the four necessary cards' latest readings (a mini card lit or dark, the value beside it)
let classFitKey = null;
async function classFitouts(r) {
  const el = document.getElementById('classfitouts'); if (!el) return;
  let d; try { d = await get('/api/fitouts?preset=' + encodeURIComponent(r.preset)); } catch (e) { return; }
  if (!d.fitouts) { el.innerHTML = `<div class="${emptyCls()}">${d.error ? 'the fitouts could not be read: ' + esc(d.error) : 'reading the fitouts (a few seconds)…'}</div>`; if (!d.error) setTimeout(() => { if (page === 'rung' && modelTab === 'fitouts') classFitouts(r); }, 3000); return; }
  const key = r.preset + JSON.stringify(d); if (key === classFitKey) return; classFitKey = key;
  if (!d.fitouts.length) { el.innerHTML = '<div class="${emptyCls()}">no fitout curated for this class yet</div>'; return; }
  const stageOf = run => /-pre-/.test(run) ? ['pretraining', 0] : /-post(\d+)-/.test(run) ? [`post-training ${run.match(/-post(\d+)-/)[1]}`, +run.match(/-post(\d+)-/)[1]] : ['', 9];
  el.innerHTML = d.fitouts.map(f => {
    const runs = [...(f.runs || [])].sort((a, b) => stageOf(a.run)[1] - stageOf(b.run)[1] || a.run.localeCompare(b.run));
    const rc = f.run_cards || {};
    const prog = `<div class="k mt">The cards each stage drew <span class="s">the four necessary cards' latest readings, voyage by voyage</span></div>
      <div class="scroll"><table class="decktable" data-nosort><thead><tr><th>stage</th><th>voyage</th><th></th>${NEEDED.map(([k, n]) => { const fc = CARD_FACE[k] || {}; return `<th>${fc.rank || ''}${fc.suit || ''} ${esc(n)}</th>`; }).join('')}</tr></thead><tbody>${runs.map(x => {
        const c = rc[x.run];
        return `<tr><td>${esc(stageOf(x.run)[0])}</td><td>${c ? `<a href="#${shipHash(x.run)}">${esc(x.run)}</a>` : esc(x.run)}</td><td>${statusPill(x.status || 'queued')}</td>${NEEDED.map(([k]) => {
          const v = c && c[k]; if (!v) return `<td class="s">${c ? 'no reading' : 'not sailed'}</td>`;
          const best = Math.max(v.one ?? -Infinity, v.shared ?? -Infinity), fc = CARD_FACE[k] || {};
          return `<td title="one head ${v.one != null ? v.one.toFixed(3) : '–'}${v.shared != null ? `, shared ${v.shared.toFixed(3)}` : ''}; the mark ${v.threshold}"><span class="minicard${v.lit ? ' on' : ''}"><b>${fc.rank || ''}</b><i>${fc.suit || ''}</i></span> ${isFinite(best) ? fmt(best) : '–'}</td>`;
        }).join('')}</tr>`;
      }).join('')}</tbody></table></div>`;
    return fitoutCard(f) + prog;
  }).join('');
  el.querySelectorAll('a.foshelf').forEach(a => a.onclick = e => { e.preventDefault(); shelfOpen = a.dataset.shelf; location.hash = '#/library'; });
}


// ---- a class's live scoring (Scoring tab, "What we measure"; /api/class_score): beside the cards held, cause and effect and
// chaining two facts, the class's current version's readings, and the census's best cards held so far
let scoreKey = null;
async function classScoreLive(r) {
  const tb = document.querySelector('#sciencemetrics tbody'); if (!tb) return;
  // every row gets the "now" cell, empty until a reading fills it
  tb.querySelectorAll('tr').forEach(tr => { if (tr.cells.length < 5) tr.insertCell(-1).className = 'scorenow'; });
  let d; try { d = await get('/api/class_score?preset=' + encodeURIComponent(r.preset)); } catch (e) { return; }
  if (currentRung !== r.preset && (rungFor(currentRung) || {}).preset !== r.preset) return;
  document.getElementById('scorenowhead').innerHTML = d.version ? `now <span class="s">${esc(d.version)}</span>` : 'now';
  const cell = name => { const tr = [...tb.rows].find(x => (x.cells[0].innerText || '').trim().toLowerCase() === name); return tr && tr.cells[4]; };
  const minis = c => `<span class="miniset">${NEEDED.map(([k, n]) => { const f = CARD_FACE[k] || {}; return `<span class="minicard${c && c[k] ? ' on' : ''}" title="${esc(n)}: ${c && c[k] ? 'lit' : 'not lit'}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span>`; }).join('')}</span>`;
  const census = d.census ? (d.census.written ? (d.census.held != null ? `<div class="s">best cards held in the census: ${d.census.held} of 4, by ${esc(d.census.variation)}</div>` : '<div class="s">the census has no readings yet</div>') : '<div class="s">the census around its fitout has not landed yet</div>') : '';
  const c1 = cell('cards held');
  if (c1) c1.innerHTML = d.version ? `${minis(d.cards)} <b>${d.held} of 4</b>${census}` : `<span class="s">no version yet</span>${census}`;
  const c2 = cell('cause and effect');
  if (c2) c2.innerHTML = d.version ? causeCell(d.cause) : '<span class="s">no version yet</span>';
  const c3 = cell('chaining two facts');
  if (c3) c3.innerHTML = d.version ? `<span class="${d.chaining != null && d.chaining > 0.03 ? 'good' : 's'}" title="the mean lift on the four chaining tests; above 0.03 it leaves the noise">${d.chaining != null ? signed(d.chaining) : '–'}</span>${d.chaining != null && d.chaining <= 0.03 ? ' <span class="s">in the noise</span>' : ''}` : '<span class="s">no version yet</span>';
  if (d.ship_key && c1) c1.insertAdjacentHTML('beforeend', `<div class="s"><a href="#/leaderboard/thorp/${encodeURIComponent(d.ship_key)}">${esc(d.version)}'s hand →</a></div>`);
}


// ---- the knockout (fleet.VOYAGES["knockout"]; /api/knockout; DECISIONS.md "The knockout, pre-registered"): in a model that
// chains, each card's 8 strongest heads silenced and the logic deck read again, beside three random draws of 8 heads. A bar
// per card (the gain lost when silenced: cause, or order for the comparator), the random draws' bars, the rule line (a drop
// of 0.1 and more than twice the largest random drop) and a verdict per card: NECESSARY or not shown.
const KO_CARDS = [['previous_word', 'Previous-word'], ['nevermore', 'Nevermore'], ['mover', 'Mover'], ['comparator', 'Comparator']];
function knockoutBlock(k, id) {
  const base = k.baseline || {}, v = k.verdict || {}, controls = k.controls || [];
  const drop = (cond, measure) => cond && base[measure] != null && cond[measure] != null ? base[measure] - cond[measure] : null;
  const ctrlCause = controls.map(c => drop(c, 'cause_gain'));
  const largest = Math.max(0, ...ctrlCause.filter(x => x != null));
  const line = Math.max(0.1, 2 * largest);
  const badges = KO_CARDS.map(([key, name]) => {
    const x = v[key], f = CARD_FACE[key] || {};
    if (!x) return `<span class="kobadge"><b>${f.rank || ''}${f.suit || ''}</b> ${esc(name)} <i>not knocked out</i></span>`;
    return `<span class="kobadge ${x.necessary ? 'need' : ''}" title="${esc(x.measure || 'cause_gain')} dropped ${x.drop != null ? x.drop.toFixed(3) : '–'}; the largest random drop ${x.largest_random_drop != null ? x.largest_random_drop.toFixed(3) : '–'}; chaining lift dropped ${x.chaining_lift_drop != null ? x.chaining_lift_drop.toFixed(3) : '–'}"><b>${f.rank || ''}${f.suit || ''}</b> ${esc(name)} <i>${x.necessary ? 'NECESSARY' : 'not shown'}</i></span>`;
  }).join('');
  const rows = KO_CARDS.filter(([key]) => v[key] || k[key]).map(([key, name]) => {
    const x = v[key] || {}, heads = (k.card_heads || {})[key] || [];
    return `<tr><td><b>${esc(name)}</b></td><td class="s">${esc((x.measure || (key === 'comparator' ? 'order_gain' : 'cause_gain')).replace('_', ' '))}</td>
      <td>${x.drop != null ? signed(x.drop) : '–'}</td><td>${x.largest_random_drop != null ? signed(x.largest_random_drop) : '–'}</td><td>${x.chaining_lift_drop != null ? signed(x.chaining_lift_drop) : '–'}</td>
      <td>${x.necessary ? `<span class="${pillCls('good')}">necessary</span>` : `<span class="${pillCls('')}">not shown</span>`}</td>
      <td class="mono kohd">${heads.map(h => `${h[0]}:${h[1]}`).join(' ')}</td></tr>`;
  }).join('');
  return `<div class="kobadges">${badges}</div>
    <div class="row koro"><div class="chart" id="${id}"></div>
    <div class="scroll"><table class="kotable" data-nosort><thead><tr><th>card</th><th>measure</th><th>lost</th><th>largest random</th><th>chaining lift lost</th><th>verdict</th><th>its ${k.k || 8} heads <span class="s">layer:head</span></th></tr></thead><tbody>${rows}</tbody></table>
    <p class="s">baseline: cause gain ${base.cause_gain != null ? signed(base.cause_gain) : '–'} · order gain ${base.order_gain != null ? signed(base.order_gain) : '–'} · logic gain ${base.logic_gain != null ? signed(base.logic_gain) : '–'} · chaining lift ${base.chaining_lift != null ? signed(base.chaining_lift) : '–'}${k.layers ? ` · ${k.layers} layers × ${k.heads} heads` : ''}</p></div></div>`;
}
function knockoutChart(k, id) {
  // grouped per card: the card's own drop and the three random draws' drops, all on that card's own measure (the comparator,
  // order gain; the rest, cause gain), with the card's rule line at max(0.1, 2 × its largest random drop)
  const base = k.baseline || {}, v = k.verdict || {}, controls = k.controls || [];
  const cards = KO_CARDS.filter(([key]) => v[key]);
  const measureOf = key => v[key].measure || (key === 'comparator' ? 'order_gain' : 'cause_gain');
  const lost = (cond, m) => cond && base[m] != null && cond[m] != null ? base[m] - cond[m] : null;
  const names = cards.map(([, n]) => n);
  const traces = [{ type: 'bar', name: 'its 8 heads silenced', x: names, y: cards.map(([key]) => v[key].drop),
    marker: { color: cards.map(([key]) => v[key].necessary ? tok('good') : tok('blue')) },
    text: cards.map(([key, n]) => `${n}: ${measureOf(key).replace('_', ' ')} lost ${v[key].drop != null ? v[key].drop.toFixed(3) : '–'}`), textposition: 'none', hovertemplate: '%{text}<extra></extra>' }];
  controls.forEach((c, i) => traces.push({ type: 'bar', name: `random ${i + 1}`, x: names, y: cards.map(([key]) => lost(c, measureOf(key))), marker: { color: tok('muted'), opacity: 0.5 + 0.15 * i },
    text: cards.map(([key]) => `random draw ${i + 1}: ${measureOf(key).replace('_', ' ')} lost ${lost(c, measureOf(key)) != null ? lost(c, measureOf(key)).toFixed(3) : '–'}`), textposition: 'none', hovertemplate: '%{text}<extra></extra>', showlegend: i === 0, legendgroup: 'random' }));
  const shapes = [], notes = [];
  cards.forEach(([key], i) => {
    const largest = v[key].largest_random_drop ?? Math.max(0, ...controls.map(c => lost(c, measureOf(key)) ?? 0));
    const line = Math.max(0.1, 2 * largest);
    shapes.push({ type: 'line', xref: 'x', yref: 'y', x0: i - 0.45, x1: i + 0.45, y0: line, y1: line, line: { color: tok('accent'), dash: 'dot', width: 1.6 } });
    notes.push({ xref: 'x', yref: 'y', x: i, y: line, yanchor: 'bottom', showarrow: false, text: `${line.toFixed(2)}${measureOf(key) === 'order_gain' ? ' (order)' : ''}`, font: { size: 9, color: tok('accent') } });
  });
  plot(id, traces, layout({ barmode: 'group', height: 300, margin: { l: 50, r: 10, t: 10, b: 40 }, yaxis: { title: { text: 'gain lost when silenced' } },
    legend: { orientation: 'h', y: -0.18 }, shapes, annotations: notes }));
}
let koKey = null;
async function drawKnockouts() {
  const el = document.getElementById('knockouts'); if (!el) return;
  let d; try { d = await get('/api/knockout'); } catch (e) { return; }
  const key = JSON.stringify(d); if (key === koKey) return; koKey = key;
  const rs = d.results || [];
  if (!rs.length) { el.innerHTML = '<div class="${emptyCls()}">no knockout has finished yet: the first, Qwen3 4B, takes about an hour</div>'; return; }
  el.innerHTML = rs.map((k, i) => `<div class="komodel"><h3><a href="#/leaderboard/competitor/${encodeURIComponent(k.model)}">${esc(k.label || k.model)}</a></h3>${knockoutBlock(k, 'kochart' + i)}</div>`).join('');
  rs.forEach((k, i) => knockoutChart(k, 'kochart' + i));
}
async function competitorKnockout(model) {
  const sec = document.getElementById('cpknockout'), el = document.getElementById('cpknock'); if (!sec || !el) return null;
  let d; try { d = await get('/api/knockout?model=' + encodeURIComponent(model)); } catch (e) { d = null; }
  const k = d && (d.results || [])[0];
  sec.hidden = !k; if (!k) return null;
  el.innerHTML = knockoutBlock(k, 'cpkochart'); knockoutChart(k, 'cpkochart');
  return k;
}


// ==================================================================================== the fitout builder
// (#/shelves; thorp/fitouts.py, /api/fitout_builder, /api/shelf_trigrams, POST /api/fitouts/save and /queue; UI.md
// "Fitout builder"). A palette of training shelves (each with its books, tokens, trigram repetition and variety, and a mini
// scatter with the frontier ringed), dragged into two lanes, pretraining and post-training; each dropped shelf a stage
// block (its name, how many tokens, which books, passes, purpose, and for post-training its learning rate and tack), blocks
// reordered by drag and sized by tokens × passes; the fitout's settings and its total; Save, then Build for a class and
// Queue (after a confirmation, since it changes what the Mac trains next); and the fitouts to open.
const FB_SELECT = { all: 'all of it', random: 'random books', repeat: 'highest repetition', frontier: 'Pareto frontier' };
const fb = { name: '', aim: '', positions: 'rope', tack: { alpha: 3, kind: 'induction' }, stages: [], opt_in: '', key: null, saved: null, dirty: false };
let fbShelves = [], fbMeta = null, fbInit = false, fbDrag = null;
const fbTri = new Map();
const fbShelf = path => fbShelves.find(x => x.path === path);
const fbStageTokens = st => (st.tokens ?? (fbShelf(st.shelf) || {}).tokens_est ?? 0);
async function initBuilder(shelves) {
  fbShelves = shelves.filter(x => x.kind === 'training' || x.kind === 'other' || x.kind === 'draft').filter(x => x.books > 0);
  if (!fbMeta) { try { fbMeta = await get('/api/fitout_builder'); } catch (e) { return; } }
  drawPalette(); drawLibrary();
  if (!fbInit) {
    fbInit = true; drawBuilder(); wireLanes(); fbDraftOffer();
    document.getElementById('fbform').addEventListener('submit', e => { e.preventDefault(); fbSave(); });
    // a field put right loses its mark as it is typed in
    document.getElementById('fbform').addEventListener('input', e => { const t = e.target.closest('[aria-invalid="true"]'); if (t) clearErrors(t.parentElement || t); });
  }
}
function triScatter(path) {
  const t = fbTri.get(path);
  if (!t || !t.books || !t.books.length) return `<span class="s">${t && t.computing ? 'measuring…' : t ? 'unmeasured' : ''}</span>`;
  const W = 120, H = 64, xs = t.books.map(b => b.variety), ys = t.books.map(b => b.repeat_rate);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = 0, y1 = Math.max(...ys, 0.01);
  const front = new Set(t.frontier || []);
  const px = v => 4 + (W - 8) * (x1 > x0 ? (v - x0) / (x1 - x0) : 0.5), py = v => H - 4 - (H - 8) * (v - y0) / (y1 - y0);
  return `<svg class="triscatter" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="variety against repetition">
    <line x1="4" y1="${H - 4}" x2="${W - 4}" y2="${H - 4}" class="tsaxis"/><line x1="4" y1="4" x2="4" y2="${H - 4}" class="tsaxis"/>
    ${t.books.map(b => `<circle cx="${px(b.variety).toFixed(1)}" cy="${py(b.repeat_rate).toFixed(1)}" r="${front.has(b.id) ? 2.8 : 1.6}" class="${front.has(b.id) ? 'tsf' : 'tsb'}"><title>${esc(b.id)}: repetition ${(100 * b.repeat_rate).toFixed(1)}%, variety ${(100 * b.variety).toFixed(0)}%${front.has(b.id) ? ' (frontier)' : ''}</title></circle>`).join('')}
  </svg>`;
}
function drawPalette() {
  const el = document.getElementById('fbpalette'); if (!el) return;
  // the ship's stores first: a fitout that reads only them passes the stores rule (S3) with no opt-in
  const isStore = x => x.path.startsWith('lists/stores/');
  const sorted = [...fbShelves].sort((a, b) => isStore(b) - isStore(a) || (b.trigrams && b.trigrams.measured ? 1 : 0) - (a.trigrams && a.trigrams.measured ? 1 : 0) || a.name.localeCompare(b.name));
  el.innerHTML = sorted.map(x => {
    const t = x.trigrams;
    return `<div class="fbtile" draggable="true" data-shelf="${esc(x.path)}" title="${esc(x.about || x.path)}">
      <div class="fbtn"><b>${esc(x.name)}</b>${isStore(x) ? ` <span class="${pillCls('good')}">the ship's stores</span>` : x.kind !== 'training' ? ` <span class="${pillCls('')}">${esc(x.kind)}</span>` : ''}</div>
      <div class="s">${x.books} books · ${big(x.tokens_est)} tokens</div>
      <div class="s">${t && t.measured ? `repetition <b>${(100 * t.repeat_rate).toFixed(1)}%</b> · variety ${(100 * t.variety).toFixed(0)}%` : 'trigrams not measured'}</div>
      <div class="fbsc" data-sc="${esc(x.path)}">${t && t.measured ? triScatter(x.path) : ''}</div></div>`;
  }).join('') || '<div class="${emptyCls()}">no training libraries</div>';
  el.querySelectorAll('.fbtile').forEach(tile => {
    tile.addEventListener('dragstart', e => { fbDrag = { shelf: tile.dataset.shelf }; e.dataTransfer.setData('text/plain', tile.dataset.shelf); e.dataTransfer.effectAllowed = 'copy'; });
  });
  // each measured shelf's books, fetched once
  for (const x of sorted) if (x.trigrams && x.trigrams.measured && !fbTri.has(x.path)) {
    fbTri.set(x.path, { computing: true });
    get('/api/library_trigrams?path=' + encodeURIComponent(x.path)).then(t => {
      fbTri.set(x.path, t.computing ? null : t);
      const c = document.querySelector(`#fbpalette [data-sc="${CSS.escape(x.path)}"]`); if (c) c.innerHTML = triScatter(x.path);
    }).catch(() => fbTri.delete(x.path));
  }
}
function fbMark() { fb.dirty = true; drawTotals(); drawActions(); fbDraftSave(); }
// an unsaved fitout is kept in this browser (per viewer), offered back when the builder opens again
const FB_DRAFT = 'thorp.fitout.draft';
let fbDraftTimer = null;
function fbDraftSave() {
  clearTimeout(fbDraftTimer);
  fbDraftTimer = setTimeout(() => {
    if (!fb.dirty || (!fb.stages.length && !fb.name)) return;
    store.set(FB_DRAFT, JSON.stringify({ at: new Date().toISOString(), key: fb.key, f: { name: fb.name, aim: fb.aim, opt_in: fb.opt_in, positions: fb.positions, tack: fb.tack, stages: fb.stages } }));
  }, 400);
}
function fbDraftClear() { clearTimeout(fbDraftTimer); store.set(FB_DRAFT, null); }
function fbDraftOffer() {
  let d = null; try { d = JSON.parse(store.get(FB_DRAFT) || 'null'); } catch (e) { d = null; }
  if (!d || !d.f) return;
  const when = new Date(d.at), n = (d.f.stages || []).length;
  fbMsg(`<span>An unsaved fitout from ${when.toTimeString().slice(0, 5)}: <b>${esc(d.f.name || 'unnamed')}</b>, ${n} stage${n === 1 ? '' : 's'}.</span>
    <button type="button" class="${btnCls()}" id="fbdraftyes">Restore it</button> <button type="button" class="${btnCls('ghost')}" id="fbdraftno">Discard</button>`, 'draft');
  document.getElementById('fbdraftyes').onclick = () => { fbLoad(d.f, null); fb.key = d.key || null; fb.dirty = true; drawActions(); fbMsg('restored the unsaved fitout: save it to keep it'); };
  document.getElementById('fbdraftno').onclick = () => { fbDraftClear(); fbMsg(''); };
}
window.addEventListener('beforeunload', e => { if (fb.dirty && fb.stages.length) { e.preventDefault(); e.returnValue = ''; } });
function drawSettings() {
  const el = document.getElementById('fbsettings');
  el.innerHTML = `<div class="fbrow"><label>name <input class="${fieldCls('')}" id="fbname" value="${esc(fb.name)}" placeholder="a name for this fitout" required maxlength="80"></label>
    <label>positions <select class="${selectCls('')}" id="fbpos"><option value="rope"${fb.positions === 'rope' ? ' selected' : ''}>rope</option><option value="learned"${fb.positions === 'learned' ? ' selected' : ''}>learned</option></select></label>
    <label>tack <select class="${selectCls('')}" id="fbtack"><option value="">none</option><option value="induction"${fb.tack && fb.tack.kind === 'induction' ? ' selected' : ''}>induction</option><option value="conclusion"${fb.tack && fb.tack.kind === 'conclusion' ? ' selected' : ''}>conclusion</option></select></label>
    <label>× <input class="${fieldCls('')}" id="fbalpha" type="number" min="0" step="0.5" value="${fb.tack ? fb.tack.alpha ?? 3 : 3}" style="width:56px"${fb.tack ? '' : ' disabled'}></label></div>
    <label class="fbaim">aim <textarea id="fbaim" rows="2" placeholder="what this fitout is for">${esc(fb.aim)}</textarea></label>
    <label class="fbaim fboptin" id="fboptinwrap" hidden>opt-in <textarea id="fboptin" rows="2" placeholder="why this fitout reads outside the ship's stores (the stores rule, S3: required for any library not in lists/stores/)">${esc(fb.opt_in || '')}</textarea></label>`;
  el.querySelector('#fbname').oninput = e => { fb.name = e.target.value; fbMark(); };
  el.querySelector('#fbaim').oninput = e => { fb.aim = e.target.value; fbMark(); };
  el.querySelector('#fboptin').oninput = e => { fb.opt_in = e.target.value; fbMark(); };
  el.querySelector('#fbpos').onchange = e => { fb.positions = e.target.value; fbMark(); };
  el.querySelector('#fbtack').onchange = e => { fb.tack = e.target.value ? { alpha: +el.querySelector('#fbalpha').value || 3, kind: e.target.value } : null; el.querySelector('#fbalpha').disabled = !fb.tack; fbMark(); };
  el.querySelector('#fbalpha').oninput = e => { if (fb.tack) fb.tack.alpha = +e.target.value; fbMark(); };
}
function stageBlock(st, i) {
  const sh = fbShelf(st.shelf) || { name: st.shelf, tokens_est: st.tokens || 0, books: '?' };
  const max = Math.max(1, sh.tokens_est || st.tokens || 1), tok = st.tokens ?? max, post = st.phase === 'post-training';
  const weight = Math.max(1, tok * (st.passes || 1));
  return `<div class="fbblock ${post ? 'post' : 'pre'}" draggable="true" data-i="${i}" style="flex-grow:${weight}">
    <div class="fbbh"><input class="${fieldCls('fbin')}" data-f="name" value="${esc(st.name)}"><button type="button" class="${btnCls('ghost', 'fbx')}" data-x="${i}" title="remove this stage" aria-label="remove this stage">×</button></div>
    <div class="s">${esc(sh.name)} · ${sh.books} books</div>
    <label class="s">tokens <b data-tokv="${i}">${big(tok)}</b>${st.tokens == null ? ' (the whole library)' : ` of ${big(max)}`}<input class="${rangeCls('fbin')}" type="range" data-f="tokens" min="${Math.min(max, 100000)}" max="${max}" step="${Math.max(1, Math.round(max / 200))}" value="${tok}"></label>
    <div class="fbrow2"><label class="s">books <select class="${selectCls('fbin')}" data-f="select">${(fbMeta.select || Object.keys(FB_SELECT)).map(k => `<option value="${k}"${st.select === k ? ' selected' : ''}>${esc(FB_SELECT[k] || k)}</option>`).join('')}</select></label>
      <label class="s">passes <input class="${fieldCls('fbin')}" data-f="passes" type="number" min="1" max="20" required value="${st.passes || 1}" style="width:48px"></label></div>
    ${post ? `<div class="fbrow2"><label class="s">lr <input class="${fieldCls('fbin')}" data-f="lr" type="number" step="0.0001" min="0" value="${st.lr ?? ''}" placeholder="the voyage's" style="width:80px"></label>
      <label class="s">tack <select class="${selectCls('fbin')}" data-f="tack"><option value="">the fitout's</option><option value="induction"${st.tack && st.tack.kind === 'induction' ? ' selected' : ''}>induction</option><option value="conclusion"${st.tack && st.tack.kind === 'conclusion' ? ' selected' : ''}>conclusion</option></select></label></div>` : ''}
    <input class="${fieldCls('fbin fbpurpose')}" data-f="purpose" value="${esc(st.purpose || '')}" placeholder="what this stage is for">
  </div>`;
}
function drawLanes() {
  for (const phase of ['pretraining', 'post-training']) {
    const drop = document.querySelector(`.fbdrop[data-phase="${phase}"]`);
    const idx = fb.stages.map((st, i) => [st, i]).filter(([st]) => st.phase === phase);
    drop.innerHTML = idx.map(([st, i]) => stageBlock(st, i)).join('') || `<div class="fbempty">drop a library here</div>`;
  }
  document.querySelectorAll('.fbblock').forEach(b => {
    const i = +b.dataset.i, st = fb.stages[i];
    b.querySelectorAll('.fbin').forEach(inp => {
      const f = inp.dataset.f;
      inp.addEventListener(inp.type === 'range' || inp.tagName === 'INPUT' ? 'input' : 'change', () => {
        if (f === 'tokens') { st.tokens = +inp.value >= ((fbShelf(st.shelf) || {}).tokens_est || Infinity) ? null : +inp.value; b.querySelector(`[data-tokv="${i}"]`).textContent = big(+inp.value); b.style.flexGrow = Math.max(1, +inp.value * (st.passes || 1)); }
        else if (f === 'passes') { st.passes = Math.max(1, +inp.value || 1); b.style.flexGrow = Math.max(1, fbStageTokens(st) * st.passes); }
        else if (f === 'lr') st.lr = inp.value === '' ? null : +inp.value;
        else if (f === 'tack') st.tack = inp.value ? { alpha: (fb.tack && fb.tack.alpha) || 3, kind: inp.value } : null;
        else st[f] = inp.value;
        fbMark();
      });
      inp.addEventListener('mousedown', e => e.stopPropagation());
    });
    b.querySelector('.fbx').onclick = () => { fb.stages.splice(i, 1); fbMark(); drawLanes(); };
    b.addEventListener('dragstart', e => { if (e.target.closest('input,select,textarea')) { e.preventDefault(); return; } fbDrag = { move: i }; e.dataTransfer.setData('text/plain', 'move'); e.dataTransfer.effectAllowed = 'move'; });
  });
  drawTotals();
}
function wireLanes() {
  document.querySelectorAll('.fbdrop').forEach(drop => {
    drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('over'));
    drop.addEventListener('drop', e => {
      e.preventDefault(); drop.classList.remove('over');
      const phase = drop.dataset.phase, target = e.target.closest('.fbblock'), before = target ? +target.dataset.i : null;
      if (fbDrag && fbDrag.shelf) {
        const sh = fbShelf(fbDrag.shelf); if (!sh) return;
        const st = { phase, name: sh.name.replace(/^The /, '').toLowerCase(), shelf: sh.path, tokens: null, select: 'all', passes: 1, lr: phase === 'post-training' ? 0.001 : null, tack: null, purpose: '' };
        if (before == null) fb.stages.push(st); else fb.stages.splice(before, 0, st);
      } else if (fbDrag && fbDrag.move != null) {
        const [st] = fb.stages.splice(fbDrag.move, 1); st.phase = phase;
        let at = before == null ? fb.stages.length : before > fbDrag.move ? before - 1 : before;
        fb.stages.splice(at, 0, st);
      }
      fbDrag = null; fbMark(); drawLanes();
    });
  });
}
function drawTotals() {
  const el = document.getElementById('fbtotal'); if (!el) return;
  const outside = fb.stages.filter(st => !String(st.shelf).startsWith('lists/stores/'));
  const ow = document.getElementById('fboptinwrap');
  if (ow) { ow.hidden = !outside.length; ow.title = outside.length ? `${outside.length} stage${outside.length === 1 ? '' : 's'} read outside the ship's stores: ${outside.map(st => st.name).join(', ')}` : ''; }
  const tot = st => fbStageTokens(st) * (st.passes || 1);
  const all = fb.stages.reduce((a, st) => a + tot(st), 0);
  const rep = fb.stages.filter(st => st.select === 'repeat' || st.select === 'frontier').reduce((a, st) => a + tot(st), 0);
  const pre = fb.stages.filter(st => st.phase === 'pretraining').reduce((a, st) => a + tot(st), 0);
  el.innerHTML = fb.stages.length ? `<b>${big(all)}</b> tokens read in all (${big(pre)} pretraining, ${big(all - pre)} post-training) · <b>${all ? Math.round(100 * rep / all) : 0}%</b> of it the repetition engine <span class="s">(stages that take the most repetitive books or the frontier)</span>` : '<span class="s">drag a library from the palette into a lane to begin</span>';
}
function drawActions() {
  const el = document.getElementById('fbactions'); if (!el || !fbMeta) return;
  const canQueue = fb.key && !fb.dirty;
  el.innerHTML = `<button type="submit" class="${btnCls()}" id="fbsave">${fb.key && !fb.dirty ? 'Saved' : 'Save'}</button>
    <span class="fbsep">then</span>
    <label>build for <select class="${selectCls('')}" id="fbclass">${(fbMeta.classes || []).map(c => `<option value="${esc(c.preset)}">${esc(c.preset)} · ${esc(c.name)}</option>`).join('')}</select></label>
    <label>seeds <input class="${fieldCls('')}" id="fbseeds" value="1, 2" style="width:60px" pattern="\\s*\\d+(\\s*,\\s*\\d+)*\\s*" title="seeds, as whole numbers separated by commas"></label>
    <label>put it <select class="${selectCls('')}" id="fbwhere"><option value="end">at the end of the queue</option><option value="top">at the top (next to sail)</option></select></label>
    <button type="button" class="${btnCls()}" id="fbqueue"${canQueue ? '' : ' disabled'} title="${canQueue ? 'compile it for that class and put its voyages in the queue' : 'save it first'}">Queue</button>
    <button type="button" id="fbnew" class="${btnCls('ghost')}">New</button>`;
  // Save is the form's submit (Enter in any field saves), so the form's own checks run first
  el.querySelector('#fbqueue').onclick = fbQueue;
  el.querySelector('#fbnew').onclick = async () => { if (fb.dirty && fb.stages.length && !await confirmDialog('The unsaved changes here are lost.', { title: 'Start a new fitout?', ok: 'Start new' })) return; fbDraftClear(); fbLoad({ name: '', aim: '', positions: 'rope', tack: { alpha: 3, kind: 'induction' }, stages: [] }, null); fb.dirty = false; drawActions(); };
}
function fbMsg(html, kind = '') { const el = document.getElementById('fbmsg'); if (el) { el.className = 'fbmsg ' + kind; el.innerHTML = html; } }
async function fbPost(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || r.statusText); return j;
}
// a server refusal, put where it belongs: "stage N: …" on that stage's block (N counts the stages as sent), the pretraining
// rule on its lane, the stores rule on the opt-in; anything else in the message line
function fbServerError(message) {
  const m = message.match(/stage (\d+):\s*(.*)/i);
  if (m) { const blk = document.querySelector(`.fbblock[data-i="${+m[1] - 1}"]`); if (blk) { fieldError(blk, m[2]); return true; } }
  if (/pretraining stage/i.test(message)) { fieldError(document.querySelector('.fbdrop[data-phase="pretraining"]'), message); return true; }
  if (/stores/i.test(message) && !document.getElementById('fboptinwrap').hidden) { fieldError(document.getElementById('fboptin'), message); return true; }
  return false;
}
// the checks the page can make before anything is sent; true when it may go
function fbCheck(form, { queueing = false } = {}) {
  clearErrors(form);
  let ok = form.checkValidity();
  if (!ok) form.reportValidity();
  if (!fb.stages.some(st => st.phase === 'pretraining')) { fieldError(document.querySelector('.fbdrop[data-phase="pretraining"]'), 'drop at least one library here: a fitout needs a pretraining stage'); ok = false; }
  const outside = fb.stages.filter(st => !String(st.shelf).startsWith('lists/stores/'));
  if (queueing && outside.length && !(fb.opt_in || '').trim()) { fieldError(document.getElementById('fboptin'), `the stores rule (S3) needs a reason in words: ${outside.length} stage${outside.length === 1 ? ' reads' : 's read'} outside the ship's stores`); ok = false; }
  return ok;
}
async function fbSave() {
  const form = document.getElementById('fbform');
  if (!fbCheck(form)) { fbMsg('not saved: fix the marked fields', 'bad'); return; }
  const body = { key: fb.key || undefined, name: fb.name, aim: fb.aim, positions: fb.positions, tack: fb.tack, stages: fb.stages, opt_in: fb.opt_in || undefined };
  const done = busy(document.getElementById('fbsave'), 'Saving…');
  try {
    const r = await fbPost('/api/fitouts/save', { fitout: body });
    fb.key = r.key; fb.dirty = false; fbDraftClear(); fbMeta = null; fbMeta = await get('/api/fitout_builder');
    done('Saved'); fbMsg(`saved as <b>${esc(r.key)}</b> (data/fitouts/${esc(r.key)}.json)`, 'good'); drawActions(); drawLibrary();
  } catch (e) { done(); fbMsg(fbServerError(e.message) ? 'not saved: see the marked field' : `not saved: ${esc(e.message)}`, 'bad'); }
}
async function fbQueue() {
  if (!fb.key || fb.dirty) return;
  const preset = document.getElementById('fbclass').value, where = document.getElementById('fbwhere').value;
  const seeds = document.getElementById('fbseeds').value.split(/[^0-9]+/).filter(Boolean).map(Number);
  const runs = seeds.length * (1 + fb.stages.filter(st => st.phase === 'post-training').length);
  if (!seeds.length) { fieldError(document.getElementById('fbseeds'), 'give at least one seed'); return; }
  if (!fbCheck(document.getElementById('fbform'), { queueing: true })) { fbMsg('not queued: fix the marked fields', 'bad'); return; }
  if (!await confirmDialog(`Queue "${fb.name || fb.key}" for the ${preset}: ${runs} voyage${runs === 1 ? '' : 's'} (${seeds.length} seed${seeds.length === 1 ? '' : 's'}) ${where === 'top' ? 'at the TOP of the queue, next to sail' : 'at the end of the queue'}?\n\nThis changes what the Mac trains next.`)) return;
  const done = busy(document.getElementById('fbqueue'), 'Queueing…');
  try {
    const r = await fbPost('/api/fitouts/queue', { key: fb.key, preset, seeds, where });
    done();
    fbMsg(`queued ${r.lines.length} voyage${r.lines.length === 1 ? '' : 's'} ${where === 'top' ? 'at the top' : 'at the end'}: ${r.lines.map(l => `<span class="mono">${esc(l)}</span>`).join(', ')}`, 'good');
  } catch (e) { done(); fbMsg(fbServerError(e.message) ? 'not queued: the gate (S3) refused it, see the marked field' : `not queued, the gate (S3) refused it: ${esc(e.message)}`, 'bad'); }
}
function fbLoad(f, key) {
  fb.name = f.name || ''; fb.aim = f.aim || ''; fb.opt_in = f.opt_in || ''; fb.positions = f.positions || 'rope'; fb.tack = f.tack ? { ...f.tack } : null;
  fb.stages = (f.stages || []).map(st => ({ ...st, tack: st.tack ? { ...st.tack } : null })); fb.key = key; fb.dirty = !key;
  drawBuilder(); fbMsg(key ? `opened <b>${esc(key)}</b>` : f.name ? `a copy of <b>${esc(f.name)}</b>: save it under its own name` : '');
}
function drawBuilder() { drawSettings(); drawLanes(); drawActions(); }
function drawLibrary() {
  const el = document.getElementById('fblibrary'); if (!el || !fbMeta) return;
  const card = (f, kind) => `<div class="fblib"><span class="${pillCls(kind === 'saved' ? 'blue' : '')}">${kind}</span> <b>${esc(f.name)}</b>
    <div class="s">${(f.stages || []).length} stages · ${esc(f.positions || '')}${f.tack ? ` · tack ${esc(f.tack.kind)}` : ''}</div>
    <button class="${btnCls()}" data-open="${esc(f.key)}" data-kind="${kind}">${kind === 'saved' ? 'Open' : 'Open a copy'}</button></div>`;
  el.innerHTML = (fbMeta.saved || []).map(f => card(f, 'saved')).join('') + (fbMeta.curated || []).map(f => card(f, 'curated')).join('') || '<span class="s">none yet</span>';
  el.querySelectorAll('[data-open]').forEach(b => b.onclick = async () => {
    const kind = b.dataset.kind, f = (kind === 'saved' ? fbMeta.saved : fbMeta.curated).find(x => x.key === b.dataset.open); if (!f) return;
    if (fb.dirty && fb.stages.length && !await confirmDialog('The unsaved changes here are lost.', { title: 'Open another fitout?', ok: 'Open it' })) return;
    if (kind === 'saved') fbLoad(f, f.key); else fbLoad({ ...f, name: `${f.name} (copy)` }, null);
    document.getElementById('builderpanel').scrollIntoView({ behavior: 'smooth' });
  });
}


// ---- Discovering the induction head (the induction voyage's page; /api/series): the Nevermore's natural score over steps for
// the trigram engine against its random twin, two seeds each, with the 0.3 mark and the step each first lights it; then
// previous-word and the copy gain. The verdict reads the pre-registered rule.
let indKey = null;
async function drawInduction(v) {
  const runs = (v.runs || []).filter(r => r.name);
  if (!runs.length) {
    ['indnevermore', 'indprev', 'indcopy'].forEach(id => empty(id, 'no voyage yet: the trigram engine and its random twin are at the top of the queue'));
    document.getElementById('indverdict').innerHTML = '<span class="s">waiting for the first readings (every 100 steps)</span>'; return;
  }
  const M = { nev: 'nevermore/natural_max_score', prev: 'stars/previous_word/max_score', copy: 'nevermore/natural_copy_gain' };
  let d; try { d = await get('/api/series?runs=' + encodeURIComponent(runs.map(r => r.name).join(',')) + '&metrics=' + encodeURIComponent(Object.values(M).join(','))); } catch (e) { return; }
  const key = JSON.stringify(d); if (key === indKey) return; indKey = key;
  const twin = r => /random/.test(r.name), seedOf = r => (r.name.match(/-s(\d+)$/) || [])[1] || '1';
  const draw = (id, metric, mark, label) => {
    const traces = [], shapes = [];
    for (const r of runs) {
      const sr = (d[r.name] || {})[metric]; if (!sr) continue;
      const col = twin(r) ? tok('muted') : tok('good');
      traces.push({ x: sr[0], y: sr[1], mode: 'lines', name: `${twin(r) ? 'random twin' : 'trigram engine'}, seed ${seedOf(r)}`, line: { color: col, width: 1.8, dash: seedOf(r) === '1' ? 'solid' : 'dash' },
        hovertemplate: `${esc(r.name)}<br>step %{x}<br>${label} %{y:.3f}<extra></extra>` });
      const i = sr[1].findIndex(v => v != null && v >= mark);
      if (i >= 0) { traces.push({ x: [sr[0][i]], y: [sr[1][i]], mode: 'markers', marker: { color: col, size: 10, symbol: 'star' }, showlegend: false, hovertemplate: `${esc(r.name)} first lights it at step ${sr[0][i]}<extra></extra>` }); }
    }
    if (!traces.length) { empty(id, 'no readings yet'); return null; }
    shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: mark, y1: mark, line: { color: tok('accent'), dash: 'dot', width: 1.4 } });
    plot(id, traces, layout({ xaxis: { title: { text: 'step' } }, yaxis: { title: { text: label } }, shapes, legend: { orientation: 'h', y: -0.2 } }));
    return true;
  };
  draw('indnevermore', M.nev, 0.3, 'Nevermore (natural score)');
  draw('indprev', M.prev, 0.5, 'previous-word');
  draw('indcopy', M.copy, 0.5, 'copy gain (nats/token)');
  // the verdict, by the rule
  const lit = r => { const sr = (d[r.name] || {})[M.nev]; if (!sr) return null; const i = sr[1].findIndex(v => v != null && v >= 0.3); return i >= 0 ? sr[0][i] : false; };
  const eng = runs.filter(r => !twin(r)), tw = runs.filter(twin);
  const engLit = eng.filter(r => lit(r)).length, twLit = tw.filter(r => lit(r)).length;
  const best = rs => Math.max(-Infinity, ...rs.map(r => { const sr = (d[r.name] || {})[M.nev]; return sr ? Math.max(...sr[1].filter(v => v != null)) : -Infinity; }));
  const success = engLit + twLit >= 2 && (engLit >= 2 || twLit >= 2), byRepetition = engLit >= 2 && twLit === 0;
  document.getElementById('indverdict').innerHTML = `<span class="${pillCls(success ? 'good' : '')}">${success ? 'lit on two seeds' : 'not lit on two seeds yet'}</span>
    ${byRepetition ? `<span class="${pillCls('good')}">repetition did it</span>` : ''}
    <span class="s">trigram engine: ${engLit} of ${eng.length} seeds lit${isFinite(best(eng)) ? `, best ${best(eng).toFixed(3)}` : ''} · random twin: ${twLit} of ${tw.length}${isFinite(best(tw)) ? `, best ${best(tw).toFixed(3)}` : ''} · earlier 300k Nevermores: 0.00 to 0.01</span>`;
}


// ==================================================================================== governance
// (#/governance; thorp/vsm.py, /api/governance; UI.md "Governance"): Beer's Viable System Model, S5 at the top down to S1.
// Each band a Card with its name, purpose and code, then that system's live numbers from the audit. Read-only.
let govKey = null;
const govOpen = new Set();
async function loadGovernance() {
  const el = document.getElementById('govbands'); if (!el) return;
  let d; try { d = await get('/api/governance'); } catch (e) { return; }
  const key = JSON.stringify(d) + [...govOpen].join(','); if (key === govKey) return; govKey = key;
  const A = d.audit || {}, sys = Object.fromEntries((d.systems || []).map(x => [x.key, x]));
  const pol = (A.S3 || {}).policies || {}, stmt = A.S5 || {}, breaking = A.breaking || {};
  const chips = s => (s.members || []).map(m => `<span class="${pillCls('')} mono govchip">${esc(m)}</span>`).join('');
  const band = (k, live) => { const s = sys[k] || { key: k }; return `<section class="${cardCls(false, 'panel govband')}" data-sys="${k}"><div class="govhead"><span class="govkey">${k}</span><div><h2>${esc(s.name || '')}</h2><div class="s">${esc(s.purpose || '')}</div></div></div>
    <div class="govchips">${chips(s)}</div><div class="govlive">${live}</div></section>`; };
  const enforcedBadge = on => on ? `<span class="${pillCls('good')}">enforced</span>` : `<span class="${pillCls('accent')}">advisory</span>`;
  // S5 policy
  const s5 = `<table data-nosort><thead><tr><th>policy</th><th>statement</th><th>adopted</th><th></th></tr></thead><tbody>${Object.entries(stmt).map(([k, p]) => `<tr><td><b>${esc(k)}</b></td><td>${esc(p.statement)}</td><td class="s">${esc(p.adopted || '')}</td><td>${enforcedBadge(p.enforced)}</td></tr>`).join('')}</tbody></table>
    <p class="s">A policy is switched on (enforced at the gate, S3) or left advisory by Justin, in data/policies.json; not from here.</p>`;
  // S4 intelligence
  const s4a = A.S4 || {};
  const s4 = `<div class="govstats"><a href="#/leaderboard" class="govstat"><b>${(s4a.competitors || []).length}</b><span>2–4B competitors</span></a><a href="#/leaderboard" class="govstat"><b>${(s4a.reference_ladder || []).length}</b><span>models on the reference ladder</span></a></div>
    <div class="s">${(s4a.competitors || []).map(m => `<a href="#/leaderboard/competitor/${encodeURIComponent(m)}">${esc(_shortModel(m))}</a>`).join(' · ')}</div>`;
  // S3 control: each policy's breaking runs, the stores policy first and large
  const order = Object.keys(pol).sort((a, b) => (b === 'stores') - (a === 'stores') || (pol[b].queued_runs_breaking_it || 0) - (pol[a].queued_runs_breaking_it || 0));
  const s3 = `<div class="govstats">${order.map(k => { const p = pol[k], n = p.queued_runs_breaking_it || 0, x = p.queued_runs_excepted || 0; return `<div class="govstat${k === 'stores' ? ' big' : ''}${n ? ' warn' : ' ok'}"><b>${n}</b><span>queued voyage${n === 1 ? '' : 's'} breaking <b>${esc(k)}</b> ${enforcedBadge(p.enforced)}${x ? `<br><b class="govexc">${x}</b> excepted${p.exception ? `: ${esc(p.exception)}` : ''}` : ''}</span></div>`; }).join('')}
      <div class="govstat"><b>${(A.S3 || {}).runs_not_finished ?? '–'}</b><span>voyages started and not finished</span></div></div>
    ${pol.stores && !pol.stores.enforced && pol.stores.queued_runs_breaking_it ? `<div class="${alertCls('open')}">The stores policy: ${pol.stores.queued_runs_breaking_it} of ${(A.S1 || {}).queued ?? '–'} queued voyages read outside the ship's stores. Whether to enforce it is the decision pending with Justin.</div>` : ''}
    ${order.filter(k => (breaking[k] || []).length).map(k => { const open = govOpen.has(k), lines = breaking[k];
      return `<div class="govbreak"><button class="${btnCls('ghost')}" data-gov="${esc(k)}">${open ? '▾' : '▸'} the voyages breaking ${esc(k)} (${pol[k].queued_runs_breaking_it}${lines.length < pol[k].queued_runs_breaking_it ? `, the first ${lines.length} shown` : ''})</button>${open ? `<div class="govlines">${lines.map(l => `<span class="mono">${esc(l)}</span>`).join('')}</div>` : ''}</div>`; }).join('')}`;
  // S2 coordination
  const lints = (A.S2 || {}).queue_lints || [], helmOf = (A.S2 || {}).helm;
  const helmLine = helmOf ? `<div><span class="${pillCls('good')}">at the helm</span> <b>${esc(helmOf.name || '')}</b> <span class="s">${esc(helmOf.kind || '')}${helmOf.pid ? ` · pid ${helmOf.pid}` : ''}${helmOf.since ? ` · since ${esc(String(helmOf.since).slice(11, 16))}` : ''}</span></div>` : '<div class="s">no voyage at the helm (S2 takes it with the next voyage to sail)</div>';
  const s2 = helmLine + (lints.length ? `<div class="${alertCls('no')}"><ul class="govlints">${lints.map(l => `<li>${esc(l)}</li>`).join('')}</ul></div>` : `<span class="${pillCls('good')}">no collisions</span> <span class="s">the queue lints clean: one GPU, one queue, no shared file written twice</span>`);
  // S1 operations
  const vs = (A.S1 || {}).expeditions || (A.S1 || {}).voyages || {}, rank = st => STATES.indexOf(st);
  const present = STATES.filter(st => Object.values(vs).includes(st));
  const s1 = `<div class="govstats"><div class="govstat"><b>${(A.S1 || {}).queued ?? '–'}</b><span>voyages queued</span></div>${present.map(st => `<div class="govstat${st === 'awaiting orders' ? ' warn' : ''}"><b>${Object.values(vs).filter(x => x === st).length}</b><span>expeditions ${esc(st)}</span></div>`).join('')}</div>
    <div class="govvoy">${Object.entries(vs).sort((a, b) => rank(a[1]) - rank(b[1])).map(([k, st]) => `<a href="#/expeditions/${esc(k)}">${esc(VOYAGE_NAME[k] || k)}</a> ${statePill(st)}`).join('<span class="govsep"></span>')}</div>`;
  el.innerHTML = band('S5', s5) + band('S4', s4) + band('S3', s3) + band('S2', s2) + band('S1', s1);
  el.querySelectorAll('[data-gov]').forEach(b => b.onclick = () => { const k = b.dataset.gov; govOpen.has(k) ? govOpen.delete(k) : govOpen.add(k); govKey = null; loadGovernance(); });
  if (!Object.keys(VOYAGE_NAME).length) get('/api/expeditions').then(v => { v.forEach(x => { VOYAGE_NAME[x.key] = x.name; }); govKey = null; loadGovernance(); }).catch(() => {});
}


// ---- the Stars tab's grid (#/discoveries/stars): every star Thorp measures by class of ship. A cell is the class's best
// reading against the star's mark, green where a sailing lit it (one head, or two together), shaded toward the mark where
// none has; the card judge's verdict beside the star.
function drawStarGrid() {
  const tb = document.querySelector('#starclassgrid tbody'); if (!tb || !discStars) return;
  const presets = [...new Set(discStars.flatMap(s => s.ships.map(x => x.preset)).filter(Boolean))].sort((a, b) => classRank(a) - classRank(b));
  document.querySelector('#starclassgrid thead').innerHTML = `<tr><th>star</th><th>the mark</th>${presets.map(p => `<th>${classLink(p)}</th>`).join('')}<th>the judge</th></tr>`;
  const levelled = [...discStars].sort((a, b) => (a.level ?? 9) - (b.level ?? 9) || a.name.localeCompare(b.name));
  tb.innerHTML = levelled.map(s => {
    const f = CARD_FACE[s.key];
    const cells = presets.map(p => {
      const mine = s.ships.filter(x => x.preset === p);
      if (!mine.length) return `<td class="cen q">–</td>`;
      const lit = mine.map(x => ({ x, at: x.steps_to_lit ?? x.shared_steps_to_lit, shared: x.steps_to_lit == null && x.shared_steps_to_lit != null })).filter(o => o.at != null).sort((a, b) => a.at - b.at)[0];
      const best = Math.max(...mine.map(x => x.best ?? -Infinity));
      const near = isFinite(best) && s.threshold ? Math.max(0, Math.min(1, best / s.threshold)) : 0;
      return lit ? `<td class="cen lit" title="first lit by ${esc(lit.x.ship_name || lit.x.name)} at step ${lit.at}${lit.shared ? ' (two heads together)' : ''}; ${mine.length} sailing${mine.length === 1 ? '' : 's'} read">✓ <span class="s">${lit.at}</span></td>`
        : `<td class="cen" style="--near:${(100 * near).toFixed(0)}%" title="best ${isFinite(best) ? best.toFixed(3) : '–'} of ${s.threshold} over ${mine.length} sailing${mine.length === 1 ? '' : 's'}">${isFinite(best) ? best.toFixed(2) : '–'}</td>`;
    }).join('');
    return `<tr><td>${f ? `<span class="suitmark">${f.rank}${f.suit}</span> ` : ''}<b>${esc(s.name)}</b><div class="s">level ${s.level ?? '–'}${(s.rests_on || []).length ? ` · rests on ${esc(s.rests_on.map(k => (discStars.find(x => x.key === k) || {}).name || k).join(', '))}` : ''}</div></td>
      <td>${s.threshold}</td>${cells}<td>${cardBadge((discData || {}).card_verdicts, s.key) || '<span class="s">–</span>'}</td></tr>`;
  }).join('') || `<tr><td colspan="${presets.length + 3}" class="${emptyCls(true)}">no star measured yet</td></tr>`;
}


// ==================================================================================== the words since 2026-11-07 16:20
// (fleet.TERMS): an expedition is a line of experiments (was a voyage), a voyage is one ship's run (was a run or a sailing),
// a library is a book list (was a shelf). The code keeps its old names (voyageKey, shelvesData, run_id); the page says the new.

// ---- the queue at a glance (top of #/expeditions; thorp.expeditions.overview, /api/expeditions/overview)
let ovKey = null;
async function loadOverview() {
  const el = document.getElementById('expoverview'); if (!el) return;
  let d; try { d = await get('/api/expeditions/overview'); } catch (e) { return; }
  const key = JSON.stringify(d); if (key === ovKey) return; ovKey = key;
  const q = d.queue || {}, sea = d.at_sea || [], ex = d.expeditions || [];
  let fresh = false; ex.forEach(e => { if (e.key && e.status && expState[e.key] !== e.status) { expState[e.key] = e.status; fresh = true; } });
  if (fresh && voyagesData) { voyagesKey = null; loadVoyages(); }
  const helm = d.helm ? `<div class="ovsea"><span class="${pillCls('good')}">at the helm</span> <b>${esc(d.helm.name || '')}</b> <span class="s">${esc(d.helm.kind || '')}${d.helm.pid ? ` · pid ${d.helm.pid}` : ''}${d.helm.since ? ` · since ${esc(String(d.helm.since).slice(11, 16))}` : ''}</span></div>`
    : `<div class="ovsea s">no helm yet: the voyage at sea was launched before the helm (S2) existed, so it shows from the ledger</div>`;
  const name = k => (ex.find(e => e.key === k) || {}).name || VOYAGE_NAME[k] || k;
  const atSea = sea.length ? sea.map(r => `<div class="ovsea"><span class="${pillCls('running')}">at sea</span> <a href="#${shipHash(r.name)}"><b>${esc(r.name)}</b></a>
      <div class="s">${esc(r.ship || '')}${r.expedition ? ` · <a href="#/expeditions/${esc(r.expedition)}">${esc(name(r.expedition))}</a>` : ''}${r.started ? ` · since ${esc(String(r.started).slice(11, 16))}` : ''}</div></div>`).join('') : '<div class="s">no voyage at sea</div>';
  const total = ex.reduce((a, e) => a + (e.queued || 0), 0) || q.voyages || 0;
  const bar = `<div class="ovbar" title="the queue: ${q.voyages} voyages, about ${q.hours_left} hours">${ex.filter(e => e.queued).map((e, i) => `<span style="flex-grow:${e.queued};background:${PALETTE[i % PALETTE.length]}" title="${esc(e.name)}: ${e.queued} queued, next at #${e.next_in_queue}"></span>`).join('')}</div>
    <div class="ovq"><b>${q.voyages ?? '–'}</b> voyages to sail · about <b>${q.hours_left ?? '–'}</b> hours${q.voyages_without_a_time ? ` <span class="s">(${q.voyages_without_a_time} with no time yet, so more)</span>` : ''}${q.steps ? ` · ${q.steps} queue command${q.steps === 1 ? '' : 's'}` : ''}</div>
    ${(q.lints || []).length ? `<div class="${alertCls('no')}">${q.lints.map(l => esc(l)).join('<br>')}</div>` : ''}`;
  const rows = ex.map((e, i) => `<tr><td><span class="ovsw" style="background:${e.queued ? PALETTE[ex.filter(x => x.queued).indexOf(e) % PALETTE.length] : 'transparent'}"></span> ${e.key === '(no expedition)' ? `<i>${esc(e.name)}</i>` : `<a href="#/expeditions/${esc(e.key)}"><b>${esc(e.name)}</b></a>`}</td>
      <td>${statePill(e.status, e.declared)}</td><td>${e.at_sea ? `<span class="${pillCls('running')}">${e.at_sea} at sea</span>` : ''}</td>
      <td>${e.queued || '–'}</td><td>${e.next_in_queue ? `#${e.next_in_queue}` : '–'}</td><td>${e.finished || '–'}</td><td>${e.failed ? `<span class="bad">${e.failed}</span>` : '–'}</td></tr>`).join('');
  el.innerHTML = `<div class="ovtop"><div>${atSea}${helm}</div><div class="ovqueue">${bar}</div></div>
    <div class="scroll"><table data-nosort><thead><tr><th>expedition</th><th title="S2's view, from the helm and the queue; the declared word on hover">state</th><th></th><th>queued</th><th>next at</th><th>finished</th><th>failed</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// ---- where a voyage's reading came from (thorp.library.aboard, /api/voyages/where): a badge per voyage
const WHERE_TONE = { 'the prose stores': 'good', 'the trigram stores': 'good', 'drawn from the stores': 'blue', 'outside the stores': 'accent' };
const whereCache = new Map();
async function whereBadges(ids, elOf) {
  const want = ids.filter(id => !whereCache.has(id));
  if (want.length) { try { Object.entries(await get('/api/voyages/where?runs=' + want.join(','))).forEach(([k, v]) => whereCache.set(k, v)); } catch (e) { return; } }
  for (const id of ids) {
    const w = whereCache.get(id), el = elOf(id);
    if (!el || !w || el.querySelector('.wherebadge')) continue;
    el.insertAdjacentHTML('beforeend', ` <span class="${pillCls(WHERE_TONE[w] || '')} wherebadge" title="where this voyage's reading came from">${esc(w)}</span>`);
  }
}

// ---- the library aboard a voyage (the ship page; /api/voyage/<run_id>/library)
let aboardKey = null;
async function drawAboard(run) {
  const sec = document.getElementById('aboardpanel'), el = document.getElementById('aboard'); if (!sec || !el) return;
  if (!run || !run.run_id) { sec.hidden = true; return; }
  let d; try { d = await get(`/api/voyage/${encodeURIComponent(run.run_id)}/library`); } catch (e) { d = null; }
  if (!d || d.error || !d.libraries) { sec.hidden = true; return; }
  const key = run.run_id + JSON.stringify(d.libraries); if (key === aboardKey) return; aboardKey = key;
  sec.hidden = false;
  el.innerHTML = `<div class="ovq">${d.where ? `<span class="${pillCls(WHERE_TONE[d.where] || '')}">${esc(d.where)}</span> ` : ''}<b>${d.books ?? '–'}</b> books · about <b>${big(d.tokens)}</b> tokens${d.recorded ? '' : ` <span class="s" title="this voyage sailed before the library aboard was recorded (16:40), so it is worked out from its spec; the lists may have changed since">(worked out from its spec)</span>`}</div>
    <div class="scroll"><table data-nosort><thead><tr><th>library</th><th>stage</th><th>where</th><th>books</th><th>hash</th></tr></thead><tbody>${d.libraries.map(l => `<tr><td><a href="#/library" data-lib="${esc(l.path)}"><b>${esc(l.name || l.path)}</b></a><div class="s mono">${esc(l.path)}</div></td>
      <td>${esc(l.stage || '–')}</td><td><span class="${pillCls(WHERE_TONE[l.where] || '')}">${esc(l.where || '')}</span></td><td>${l.books ?? '–'}</td><td class="mono s">${esc((l.sha1 || '').slice(0, 10))}</td></tr>`).join('')}</tbody></table></div>
    ${d.opt_in ? `<div class="${alertCls('open')}">opted out of the stores: ${esc(d.opt_in)}</div>` : ''}
    ${(d.refused || []).length ? `<div class="s">refused: ${d.refused.map(r => `<span class="mono">${esc(r)}</span>`).join(', ')}</div>` : ''}`;
  el.querySelectorAll('[data-lib]').forEach(a => a.onclick = e => { e.preventDefault(); shelfOpen = a.dataset.lib; location.hash = '#/library'; });
}


// ---- an expedition's state, as S2 works it out from the helm and the queue (expeditions.overview; since 16:35): at sea (at
// most one), under way (voyages queued), in port (planned), home (done), paused, awaiting orders (declared running with
// nothing at sea or queued: stalled, or done and not closed). The hand-set word is `declared`.
const STATES = ['at sea', 'under way', 'awaiting orders', 'paused', 'in port', 'home'];
const STATE_TONE = { 'at sea': 'running', 'under way': 'blue', 'in port': '', home: 'good', paused: 'accent', 'awaiting orders': 'bad' };
const STATE_NOTE = { 'at sea': 'a voyage of it is at sea now', 'under way': 'voyages of it are queued', 'in port': 'planned, nothing queued yet', home: 'done',
  paused: 'paused', 'awaiting orders': 'declared running with nothing at sea or queued: stalled, or done and not closed' };
const expState = {};  // key -> S2's state, from the overview
const statePill = (st, declared) => st ? `<span class="${pillCls(STATE_TONE[st] ?? '')}${st === 'awaiting orders' ? ' awaiting' : ''}" title="${esc(STATE_NOTE[st] || st)}${declared && declared !== st ? `; declared ${esc(declared)}` : ''}">${esc(st)}</span>` : '';
const expPill = v => expState[v.key] ? statePill(expState[v.key], v.status) : statusPill(v.status);


// ---- the observation deck (each expedition's page, "On the water"; /api/observation): its voyages at sea, read live from
// their logs. Per voyage: how far it has come and how long it has left, its loss (a sparkline), speed and memory, the four
// necessary cards as they stand, and its telegrams, newest first. With none at sea: where its next voyage stands.
let deckKey = null;
async function drawDeck(v) {
  const el = document.getElementById('obsdeck'); if (!el) return;
  let d; try { d = await get('/api/observation?expedition=' + encodeURIComponent(v.key)); } catch (e) { return; }
  if (voyageKey !== v.key) return;
  const key = JSON.stringify(d); if (key === deckKey) return; deckKey = key;
  const hm = s => s == null ? '–' : s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min` : s >= 60 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`;
  const spark = l => {
    if (!l || !l[1] || l[1].length < 2) return '';
    const ys = l[1], W = 220, H = 40, lo = Math.min(...ys), hi = Math.max(...ys), sx = i => (W - 2) * i / (ys.length - 1) + 1, sy = y => H - 2 - (H - 4) * (hi > lo ? (y - lo) / (hi - lo) : 0.5);
    return `<svg class="obsspark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="loss over the last steps"><polyline points="${ys.map((y, i) => `${sx(i).toFixed(1)},${sy(y).toFixed(1)}`).join(' ')}"/></svg>`;
  };
  const cardChip = (k, c) => {
    const f = CARD_FACE[k] || {}, best = Math.max(c.one ?? -Infinity, c.shared ?? -Infinity);
    return `<span class="obscard${c.lit ? ' lit' : ''}" title="${esc((discStars.find(s => s.key === k) || {}).name || k)}: one head ${c.one != null ? c.one.toFixed(3) : '–'}${c.shared != null ? `, two together ${c.shared.toFixed(3)}` : ''}; the mark ${c.threshold}"><span class="minicard${c.lit ? ' on' : ''}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span> ${isFinite(best) ? best.toFixed(2) : '–'}<i class="s"> / ${c.threshold}</i></span>`;
  };
  const ship = r => {
    const pct = r.step && r.steps_total ? Math.min(100, 100 * r.step / r.steps_total) : 0;
    return `<div class="obsship">
      <div class="obshead"><span class="${pillCls('running')}">at sea</span> <a href="#${shipHash(r.name)}"><b>${esc(r.name)}</b></a>
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
      <div class="telegrams"><div class="k">telegrams <span class="s">from the ship, newest first</span></div>
        ${(r.telegrams || []).map(t => `<div class="telegram ${t.kind}"><span class="tgtime">${esc(t.time || (t.step != null ? 'step ' + t.step : ''))}</span><span class="tgtext">${esc(t.text)}</span></div>`).join('') || '<div class="s">no word from the ship yet</div>'}</div>
    </div>`;
  };
  if (d.at_sea && d.at_sea.length) { el.innerHTML = d.at_sea.map(ship).join(''); return; }
  const where = d.next_in_queue ? `its next voyage is <b>#${d.next_in_queue}</b> in the queue (${d.queued} of its voyages queued)` : d.state === 'home' ? 'it is home: every voyage has come back' : d.state === 'awaiting orders' ? 'it is awaiting orders: nothing of it at sea or queued' : 'nothing of it is queued';
  const other = (d.elsewhere || [])[0];
  el.innerHTML = `<div class="${emptyCls()}">no voyage of this expedition is at sea: ${where}.${other ? ` At sea now: <a href="#${shipHash(other.name)}">${esc(other.name)}</a>${other.expedition ? `, of <a href="#/expeditions/${esc(other.expedition)}">${esc(VOYAGE_NAME[other.expedition] || other.expedition)}</a>` : ''}.` : ''}</div>`;
}


// ---- the expedition page's tabs. Overview, Findings: always. At sea: while any of it is at sea, queued, paused or awaiting
// orders (S2's state). Fleet: once it has a ship or a voyage. Inside: once one of its voyages recorded soundings (the
// journey's base). A tab that doesn't apply is hidden; an address naming one falls back to Overview.
const expTabOk = {};
function showExpTab() {
  const ok = expTabOk[voyageKey] || {};
  if (ok[expTab] === false) { expTab = 'overview'; history.replaceState(null, '', location.pathname + '#/expeditions/' + voyageKey); }
  document.querySelectorAll('#voyage .etab').forEach(t => t.classList.toggle('active', t.dataset.etab === expTab));
  document.querySelectorAll('#expnav a').forEach(a => { a.hidden = ok[a.dataset.etab] === false; setTab(a, a.dataset.etab === expTab); });
  // charts drawn while their tab was hidden have no width
  document.querySelectorAll('#voyage .etab.active .js-plotly-plot').forEach(el => Plotly.Plots.resize(el));
}
async function gateExpTabs(v) {
  const st = expState[v.key] || '';
  const ok = { overview: true, findings: true,
    'at-sea': ['at sea', 'under way', 'paused', 'awaiting orders'].includes(st) || (!st && v.status === 'running') || v.runs.some(r => r.status === 'running'),
    fleet: !!(v.runs.length || (v.ships || []).length),
    inside: (expTabOk[v.key] || {}).inside };  // unknown until the soundings are asked for: shown meanwhile
  expTabOk[v.key] = ok; if (v.key === voyageKey) showExpTab();
  // Inside: ask whether any of its voyages recorded soundings
  const names = v.runs.filter(r => !r.set_aside).map(r => r.name).slice(-40);
  if (!names.length) { ok.inside = false; if (v.key === voyageKey) showExpTab(); return; }
  try {
    const d = await get('/api/series?runs=' + encodeURIComponent(names.join(',')) + '&metrics=' + encodeURIComponent('soundings/layer_0/bpb'));
    ok.inside = Object.values(d).some(m => Object.keys(m).length);
  } catch (e) { return; }
  if (v.key === voyageKey) showExpTab();
}

// ---- Findings: every voyage on each measure the expedition is judged by (its outcomes), the latest reading, the best marked
let expReadingsKey = null;
async function drawExpReadings(v) {
  const tb = document.querySelector('#voyagereadings tbody'); if (!tb) return;
  const outs = (v.outcomes || []).filter(o => o.metric && !/[*<]/.test(o.metric)).slice(0, 10);
  const runs = v.runs.filter(r => !r.set_aside && r.name);
  const head = document.querySelector('#voyagereadings thead');
  if (!outs.length || !runs.length) { head.innerHTML = ''; tb.innerHTML = `<tr><td class="${emptyCls(true)}">${outs.length ? 'no voyage has sailed on it yet' : 'it declares no measure the ledger records'}</td></tr>`; return; }
  let d; try { d = await get('/api/series?runs=' + encodeURIComponent(runs.slice(-40).map(r => r.name).join(',')) + '&metrics=' + encodeURIComponent(outs.map(o => o.metric).join(','))); } catch (e) { return; }
  if (v.key !== voyageKey) return;
  const key = v.key + JSON.stringify(d); if (key === expReadingsKey) return; expReadingsKey = key;
  const last = (r, m) => { const sr = (d[r.name] || {})[m]; return sr && sr[1].length ? sr[1][sr[1].length - 1] : null; };
  const best = outs.map(o => { const vals = runs.map(r => last(r, o.metric)).filter(x => x != null); if (!vals.length) return null; return /lower|less|smaller/.test(o.better || '') ? Math.min(...vals) : Math.max(...vals); });
  head.innerHTML = `<tr><th>voyage</th><th>ship</th>${outs.map(o => `<th title="${esc(o.metric)}; better is ${esc(o.better || '')}">${esc(o.about)}</th>`).join('')}</tr>`;
  const read = runs.filter(r => outs.some(o => last(r, o.metric) != null));
  tb.innerHTML = read.slice().reverse().map(r => `<tr><td><a href="#${shipHash(r.name)}">${esc(r.name)}</a></td><td class="s">${esc(r.ship_name || r.ship || '')}</td>
    ${outs.map((o, i) => { const x = last(r, o.metric); return x == null ? '<td class="s">–</td>' : `<td class="${x === best[i] ? 'good' : ''}">${fmt(x)}${x === best[i] ? ' ★' : ''}</td>`; }).join('')}</tr>`).join('')
    || `<tr><td colspan="${outs.length + 2}" class="${emptyCls(true)}">none of its voyages has a reading on these measures yet</td></tr>`;
}

