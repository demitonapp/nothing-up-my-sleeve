// One size's page (UI.md "Model pages"), as a controller over the size island's shell: the seven tabs
// (overview, goals, training, scoring, waypoints, fitouts, bet) and their sub-views. The chart libraries
// are imported inside the drawers that draw them, so the server-rendered shell stays free of Plotly.

import { big, esc, fmt, fmtBytes, get, signed } from '../../lib/format';
import { alertCls, btnCls, cardCls, emptyCls, pillCls, selectCls, toggleCls } from '../../lib/ui';
import { CLASS_ALIASES, route, shipHash, slugOf, WSUBS } from '../router';
import type { Route } from '../router';
import { renderRunGrid } from '../../lib/rungrid';
import { renderHand, miniHand } from '../../lib/cards';
import { CARD_FACE } from '../../lib/deck';
import { NEEDED, minicards } from './leaderboard';
import { fitoutCard } from './fitouts';
import { ASK_QUESTIONS, chose, hopeRank, lookingFor, showPiece } from './ask';
import { mathsIndex, mathsTable } from './maths';
import { MOVE_LABEL, fmtTok, fallText, hms, TRAIT_LABEL, firstAt, lastOf, statusPill, STAR_LABEL, scaffoldBar, starHeadline, familyBar, cardArt, causeCell } from './helpers';

type Payload = any;
type Ladder = any;

const RECENT = 30;
const api = (u: string): Promise<any> => get(u);
const chart = () => import('../../lib/charts');
const guarded = async (fn: () => unknown, what: string): Promise<void> => {
  try { await fn(); } catch (e) {
    console.error(what + ' failed', e);
    const host = document.getElementById('rung');
    if (!host) return;
    const bar = document.createElement('div');
    bar.className = 'fbmsg bad';
    bar.textContent = `${what} failed: ${String((e as Error)?.message || e)}`;
    host.prepend(bar);
  }
};

// ---- the address -----------------------------------------------------------------------------------
export interface SizeAddress { key: string; tab: string; wsub: string; ssub: string; osub: string | null }
export const isSizePage = (path: string): boolean => route(path.replace(/^#/, '')).page === 'rung';
export const sizeAddress = (path: string): SizeAddress => {
  const rt: Route = route(path.replace(/^#/, ''));
  return {
    key: (rt.rung as string) || '',
    tab: (rt.mtab as string) || 'overview',
    wsub: (rt.wsub as string) || 'expected',
    ssub: (rt.ssub as string) || 'maths',
    osub: (rt.osub as string | null) ?? null,
  };
};
export const rungFor = (ladder: Ladder, key: string): Payload | null =>
  ladder && ladder.rungs ? ladder.rungs.find((r: any) => slugOf(r) === key || r.preset === key || slugOf(r) === CLASS_ALIASES[key]) || null : null;
export const modelHref = (r: Payload, mt = 'overview', sub: string | null = null): string =>
  `/sizes/${slugOf(r)}${mt === 'overview' && !sub ? '' : '/' + mt}${mt === 'waypoints' && sub && sub !== 'expected' ? '/' + sub : ''}${mt === 'scoring' && sub && sub !== 'maths' ? '/' + sub : ''}${mt === 'overview' && sub ? '/' + sub : ''}`;
/** The size's runs, narrowed by the SOP picked on the Training tab (module state, as before). */
let sopPick = '';
export const rungRuns = (ladder: Ladder, preset: string): any[] =>
  (ladder.runs || []).filter((r: any) => r.preset === preset && !(r.name || '').startsWith('smoke') && (!sopPick || String(r.sop || '') === sopPick));

const classRank = (ladder: Ladder, preset: string): number => {
  const i = ladder && ladder.rungs ? ladder.rungs.findIndex((r: any) => r.preset === preset) : -1;
  return i < 0 ? 99 : i;
};
const classLink = (ladder: Ladder, preset: string): string => {
  const c = ladder && ladder.rungs ? ladder.rungs.find((x: any) => x.preset === preset) : null;
  return c ? `<a href="${modelHref(c)}">${esc(c.preset)} · ${esc(c.name)}</a>` : esc(preset || '–');
};
const fillStepFilter = (sel: HTMLSelectElement | null, wps: any[]): void => {
  if (!sel) return;
  if (sel.options.length === wps.length + 1) return;
  const was = sel.value;
  sel.innerHTML = '<option value="">all seven</option>' + wps.map((w, i) => `<option value="${esc(w.key)}">${i + 1}. ${esc(w.name)}</option>`).join('');
  sel.value = was;
};

// ---- the run: one request in flight at a time; the island polls and calls this -----------------------
let lastRung = '', lastTab = '', lastSub = '';
let dataKeys: Record<string, string> = {};
const changed = (key: string, value: string): boolean => { if (dataKeys[key] === value) return false; dataKeys[key] = value; return true; };
export const resetSizeKeys = (): void => { dataKeys = {}; };

/** Draw everything the route asks for. `ladder` is the polled /api/ladder payload. */
export async function renderSizePage(path: string, ladder: Ladder): Promise<void> {
  const addr = sizeAddress(path);
  const r = rungFor(ladder, addr.key) || (ladder && ladder.rungs ? ladder.rungs[0] : null);
  if (!r) return;
  if (lastRung !== r.preset) { lastRung = r.preset; sopPick = ''; resetSizeKeys(); }
  lastTab = addr.tab; lastSub = addr.tab === 'scoring' ? addr.ssub : addr.wsub;
  const title = document.getElementById('rungtitle'); if (title) title.textContent = `${r.preset} · ${r.name}`;
  const job = document.getElementById('rungjob'); if (job) job.textContent = r.job || '';
  document.querySelectorAll<HTMLElement>('#rung [data-kind]').forEach((el) => { el.hidden = !(el.dataset.kind || '').split(' ').includes(r.kind || slugOf(r)); });
  // the SOPs this size has sailed
  const sopSel = document.getElementById('soppick') as HTMLSelectElement | null;
  if (sopSel) {
    const vers = [...new Set((ladder.runs || []).filter((x: any) => x.preset === r.preset).map((x: any) => x.sop).filter(Boolean))].sort() as string[];
    if (!vers.includes(sopPick) && sopPick) sopPick = '';
    const sig = vers.join(',') + '|' + sopPick;
    if (changed('sop', sig)) {
      sopSel.innerHTML = `<option value="">all versions</option>` + vers.map((v) => `<option value="${esc(v)}">v${esc(v)}</option>`).join('');
      sopSel.value = sopPick;
      sopSel.onchange = () => { sopPick = sopSel.value; resetSizeKeys(); void renderSizePage(path, ladder); };
    }
  }
  const allRuns = rungRuns(ladder, r.preset), runs = allRuns.slice(-RECENT), capped = allRuns.length > runs.length;
  document.querySelectorAll<HTMLElement>('#rung .recentnote').forEach((el) => { el.textContent = capped ? `(the latest ${runs.length} of ${allRuns.length} runs)` : ''; });

  if (addr.tab === 'overview') {
    await guarded(() => drawDeck(r, addr.osub), 'the deck');
    renderRunGrid(r, allRuns, null);
    drawFtProgress(ladder, allRuns);
    await guarded(() => sopSummary(r, ladder), 'the SOP run');
  }
  if (addr.tab === 'goals' || addr.tab === 'scoring') await guarded(() => classGoals(r, ladder), 'the goals');
  if (addr.tab === 'goals') { await guarded(() => drawGoalNotes(r, ladder), 'the goal notes'); }
  if (addr.tab === 'training') {
    await guarded(() => drawRungOverview(r), 'the model facts');
    void guarded(() => sizeJourney(r), 'the star chart');
    void guarded(() => drawWatch(r, path), 'the watch');
    void guarded(() => drawDepth(r), 'the depth');
    void guarded(() => drawLossChart(r), 'the training loss');
  }
  if (addr.tab === 'scoring') {
    void guarded(() => classGoals(r, ladder), 'the goals');
    await guarded(() => classCards(r), 'the four cards');
    await guarded(() => drawScience(r, runs, capped), 'the scoring boards');
    await guarded(() => drawScoreLive(r), 'the live score');
    void guarded(() => drawTomes(r, allRuns, ladder), 'the Forgotten Tomes');
    if (r.kind === 'proxy') void guarded(() => drawCalibration(r, ladder, allRuns), 'the calibration');
    const sub = addr.ssub;
    if (sub === 'shapes') await guarded(() => classShapes(r), 'the shapes');
    else if (sub === 'versus') await guarded(() => classVersus(r, path), 'the versus');
    else if (sub === 'maths') await guarded(() => mathsBook(r, ladder), 'the maths book');
    else if (sub === 'ask') await guarded(() => askPanel(r, ladder), 'the ask panel');
    else if (!['language'].includes(sub)) await guarded(() => classSubject(r, sub), 'the subject');
  }
  if (addr.tab === 'waypoints') {
    void guarded(() => classSteps(r, ladder), 'the waypoint steps');
    void guarded(() => starsInReach(r, ladder), 'the stars in reach');
    await guarded(() => renderWaypoints(r, ladder), 'the waypoint table');
  }
  if (addr.tab === 'fitouts') await guarded(() => classFitouts(r), 'the fitouts');
  if (addr.tab === 'bet') await guarded(() => classWager(r, path), 'the wager');
}

// ---- Overview: the four cards, the deck, the SOP run, the run grid and the Forgotten Tomes ----------
let cardsKey = '';
async function classCards(r: Payload): Promise<void> {
  const el = document.getElementById('cardstrip'); if (!el) return;
  let d: Payload;
  try { d = await api(`/api/class_cards?preset=${encodeURIComponent(r.preset)}`); } catch { el.innerHTML = `<div class="${emptyCls()}">the cards could not be read</div>`; return; }
  const key = JSON.stringify(d);
  if (key === cardsKey && el.dataset.preset === r.preset) return;
  cardsKey = key; el.dataset.preset = r.preset;
  if (!d.read) { el.innerHTML = `<div class="${emptyCls()}">no voyage at ${esc(r.preset)} has read the cards yet</div>`; return; }
  const f2 = (v: number | null | undefined) => v == null ? '–' : v.toFixed(2);
  const scale = (c: any) => Math.max(1, c.threshold * 2, (c.best || {}).value || 0);
  const tile = (c: any) => {
    const s = scale(c), at = (v: number | null | undefined) => `${Math.max(0, Math.min(100, 100 * (v || 0) / s))}%`, end = c.end_best || {}, peak = c.best || {};
    const state = c.held ? 'held' : c.lit ? 'touched' : 'not drawn';
    const cls = c.held ? 'good' : c.lit ? 'warn' : 'bad';
    return `<div class="ctile ${cls}">
      <div class="ctop"><b>${esc(c.name)}</b><span class="${pillCls(c.held ? 'good' : c.lit ? '' : 'bad')}">${state}</span></div>
      <div class="cbig">${f2(end.value)}<span class="s"> / mark ${f2(c.threshold)}</span></div>
      <div class="ctrack" title="ended at ${f2(end.value)} (the best a finished voyage ended with); peaked at ${f2(peak.value)} at step ${peak.step ?? '–'}; the line is the mark">
        <i class="cend" style="width:${at(end.value)}"></i><i class="cpeak" style="left:${at(peak.value)}"></i><i class="cmark" style="left:${at(c.threshold)}"></i></div>
      <div class="s">${c.held ? `held by ${c.held_by.length} of ${d.voyages} voyages` : c.lit ? `touched by ${c.lit_by.length}, held by none` : `no voyage reached the mark`}</div>
      <div class="s">best: ${end.run ? `<a href="${shipHash(end.run)}" class="mono">${esc(end.run)}</a>` : '–'}${peak.value != null && peak.value > (end.value ?? -1) + 0.005 ? ` · peak ${f2(peak.value)} at step ${peak.step}` : ''}</div>
      ${c.now ? `<div class="s">newest voyage ended at ${f2(c.now.value)}</div>` : ''}</div>`;
  };
  const cz = d.cause || {}, rng = cz.finished_range;
  const cause = `<div class="ctile ${cz.chains ? 'good' : 'bad'}">
      <div class="ctop"><b>Chains cause and effect?</b><span class="${pillCls(cz.chains ? 'good' : 'bad')}">${cz.chains ? 'yes' : 'not yet'}</span></div>
      <div class="cbig">${rng ? `${rng[0] >= 0 ? '+' : ''}${f2(rng[0])} to ${rng[1] >= 0 ? '+' : ''}${f2(rng[1])}` : '–'}</div>
      <div class="s">the logic deck's cause gain where finished voyages ended; above +${f2(cz.noise)} clears the noise of eight items (Qwen3 4B: +0.94)</div>
      ${cz.best ? `<div class="s">passing peak +${f2(cz.best.value)} (<span class="mono">${esc(cz.best.run)}</span>, step ${cz.best.step}), not counted</div>` : ''}</div>`;
  el.innerHTML = `<div class="csum"><b>${d.held} of 4</b> cards held${d.touched > d.held ? `, ${d.touched} touched` : ''} · ${d.read} of ${d.voyages} voyages read the cards · ${cz.chains ? 'it chains' : 'it does not chain yet'}</div>
    <div class="cgrid">${d.cards.map(tile).join('')}${cause}</div>`;
}

// ---- the deck at a size --------------------------------------------------------------------------
const flipped = new Set<string>();
const deckWhich = (): string => { try { return localStorage.getItem('thorp.deck.which') || 'cards'; } catch { return 'cards'; } };
const deckSwitch = (which: string): string => `<div class="darrange" role="tablist" aria-label="which deck"><span class="s">deck</span>${[['cards', 'the 16 cards'], ['logic', 'the logic deck']].map(([k, l]) => `<button type="button" role="tab" class="${toggleCls()}" data-state="${which === k ? 'on' : 'off'}" aria-selected="${which === k}" data-deckwhich="${k}">${l}</button>`).join('')}</div>`;
function wireDeckSwitch(el: HTMLElement, r: Payload): void {
  el.querySelectorAll<HTMLElement>('[data-deckwhich]').forEach((b) => { b.onclick = () => { try { localStorage.setItem('thorp.deck.which', b.dataset.deckwhich!); } catch { /* blocked */ } cardsKey = ''; void drawDeck(r, null); }; });
}
async function drawDeck(r: Payload, osub: string | null): Promise<void> {
  const el = document.getElementById('deckclass'); if (!el) return;
  if (osub) { await classLogicRelation(r, el, osub.slice(6)); return; }
  if (deckWhich() === 'logic') { await classLogicDeck(r, el); return; }
  let d: Payload;
  try { d = await api(`/api/class_deck?preset=${encodeURIComponent(r.preset)}`); } catch { el.innerHTML = `<div class="${emptyCls()}">the deck could not be read (a dashboard server started before it existed has to be restarted)</div>`; return; }
  const key = JSON.stringify(d);
  if (!changed('deck', key) && el.dataset.preset === r.preset && el.dataset.shown === 'cards') return;
  el.dataset.preset = r.preset; el.dataset.shown = 'cards';
  const tok = (t: number | null) => t == null ? '' : t >= 1e6 ? `${Math.round(t / 1e6)}M` : `${Math.round(t / 1e3)}k`;
  const byKey = Object.fromEntries(d.cards.map((c: any) => [c.key, c]));
  const scanAbout = Object.fromEntries((d.scansions || []).map((s: any) => [s.key, `${s.name}: ${s.about}`]));
  const scanOf = Object.fromEntries((d.scansions || []).map((s: any) => [s.key, s]));
  const conOf = Object.fromEntries(d.constellations.map((k: any) => [k.key, k]));
  const sentence = (t: string) => t ? `${t.charAt(0).toUpperCase()}${t.slice(1)}${/[.!?]$/.test(t) ? '' : '.'}` : '';
  const stageRule: Record<string, string> = { 'Basic': 'A Basic: one attention head, in one layer.',
    'Stage 1': 'A Stage 1: played only above a Basic of its suit held in an earlier layer.',
    'Face': 'A Face: traded in when the cards beneath it are held in order and what it does passes its mark.' };
  const back = (c: any) => {
    const k = conOf[c.constellation] || {}, s = scanOf[c.scansion];
    const fragile = c.fragility && !/^(none known|not yet seen|uncharted)$/.test(c.fragility) ? c.fragility : '';
    return `<div class="dface dback" aria-hidden="${flipped.has(c.key) ? 'false' : 'true'}">
      <div class="dbhead"><span class="suit">${esc(k.suit || '')}</span><b>${esc(c.name)}</b></div>
      <div class="s">${esc(c.stage)} · ${esc(k.name || '')}: ${esc(k.about || '')}</div>
      <div class="dwhat">${esc(sentence(c.ability))}</div>
      <div class="s">${esc(stageRule[c.stage] || '')}</div>
      ${s ? `<div class="s"><b>${esc(s.name)}.</b> ${esc(sentence(s.about))}</div>` : ''}
      ${fragile ? `<div class="s"><b>Fragile:</b> ${esc(sentence(fragile))}</div>` : ''}
      <div class="dhint s">click to turn back</div>
    </div>`;
  };
  const tile = (c: any) => {
    const pct = c.voyages_read ? Math.round(100 * c.played / c.voyages_read) : 0;
    const barTo = c.best != null && c.mark ? Math.min(100, Math.round(100 * c.best / (c.mark * 2))) : 0;
    const up = flipped.has(c.key);
    return `<div class="dcard r-${esc(c.rarity)}${up ? ' flipped' : ''}" data-card="${esc(c.key)}" role="button" tabindex="0" aria-pressed="${up}" title="click to turn the card over">
      <div class="dface dfront" aria-hidden="${up}">
      <div class="dart"><img src="/art/${esc(c.key)}.png" alt="" loading="lazy" onerror="this.style.display='none'"><span class="dstage">${esc(c.stage)}</span><span class="dcost" title="layers that must stand in order">${c.cost}</span><span class="drarity">${esc(c.rarity)}</span>${c.scansion ? `<span class="dscan" title="${esc(scanAbout[c.scansion] || '')}">${esc(c.scansion)}</span>` : ''}</div>
      <div class="dname">${esc(c.name)}</div>
      ${!c.charted ? '<div class="s">uncharted: Thorp has no reading for it yet</div>' : `
      <div class="dstat"><b>${c.played}</b> of ${c.voyages_read} voyages played it${c.voyages_read ? ` (${pct}%)` : ''}</div>
      <div class="s">Ogden: ${c.ogden_played} of ${c.ogden_read}</div>
      ${c.first_tokens_median != null ? `<div class="s">first played at ${tok(c.first_tokens_median)} tokens (median)${c.usual_layer != null ? `, usually layer ${c.usual_layer}` : ''}</div>` : ''}
      ${c.best != null ? `<div class="dbar" title="its best reading against its mark (the line)"><i style="width:${barTo}%"></i><b style="left:50%"></b></div><div class="s">best ${c.best.toFixed(2)} (mark ${c.mark})${c.best_voyage ? ` · <span class="mono">${esc(c.best_voyage.replace('fu-ogden-v0-1', 'Ogden'))}</span>` : ''}</div>` : (c.mark != null ? `<div class="s">read by its ability (mark ${c.mark})</div>` : '')}`}
      ${c.on.length ? `<div class="s">evolves from ${c.on.map((o: string) => esc(byKey[o] ? (byKey[o] as any).name : o)).join(' + ')}</div>` : ''}
      </div>${back(c)}
    </div>`;
  };
  let arrange = 'constellation'; try { arrange = localStorage.getItem('thorp.deck.arrange') || 'constellation'; } catch { /* blocked */ }
  if (arrange === 'scansion' && !d.scansions) arrange = 'constellation';
  const order = Object.fromEntries(d.cards.map((c: any, i: number) => [c.key, i]));
  const sw = `<div class="darrange" role="tablist" aria-label="arrange the deck"><span class="s">arrange by</span>${[['constellation', 'constellation'], ['scansion', 'scansion']].map(([k, l]) => `<button type="button" role="tab" class="${toggleCls()}" data-state="${arrange === k ? 'on' : 'off'}" aria-selected="${arrange === k}" data-arrange="${k}"${k === 'scansion' && !d.scansions ? ' disabled' : ''}>${l}</button>`).join('')}</div>`;
  const body = arrange === 'scansion'
    ? d.scansions.map((s: any) => { const cs = d.cards.filter((c: any) => c.scansion === s.key).sort((a: any, b: any) => order[a.key] - order[b.key]);
        return `<div class="dscanrow"><div class="dscanhead"><b>${esc(s.name)}</b> <span class="s">${esc(s.about)} · ${cs.length} card${cs.length === 1 ? '' : 's'}</span></div><div class="dgrid">${cs.map(tile).join('')}</div></div>`; }).join('')
      + (d.cards.some((c: any) => !c.scansion) ? `<div class="dscanrow"><div class="dscanhead"><b>Unscanned</b></div><div class="dgrid">${d.cards.filter((c: any) => !c.scansion).map(tile).join('')}</div></div>` : '')
    : d.constellations.map((k: any) => `<div class="drow"><div class="dsuit"><span class="suit">${esc(k.suit)}</span><b>${esc(k.name)}</b><span class="s">${esc(k.about)}</span></div>${d.cards.filter((c: any) => c.constellation === k.key).map(tile).join('')}</div>`).join('');
  el.innerHTML = `<div class="dtop"><div class="s dsum">${d.voyages} voyage${d.voyages === 1 ? '' : 's'} of the ${esc(d.class)} class on the ledger, ${d.read} with card readings${d.read ? '' : ': the deck fills in as its first voyage reads'}</div><div class="dswitches">${deckSwitch('cards')}${sw}</div></div>` + body;
  wireDeckSwitch(el, r);
  el.querySelectorAll<HTMLElement>('[data-arrange]').forEach((b) => { b.onclick = () => { try { localStorage.setItem('thorp.deck.arrange', b.dataset.arrange!); } catch { /* blocked */ } void drawDeck(r, null); }; });
  el.querySelectorAll<HTMLElement>('.dcard[data-card]').forEach((card) => {
    const turn = (): void => {
      const up = card.classList.toggle('flipped');
      card.setAttribute('aria-pressed', String(up));
      card.querySelector('.dfront')!.setAttribute('aria-hidden', String(up));
      card.querySelector('.dback')!.setAttribute('aria-hidden', String(!up));
      if (up) flipped.add(card.dataset.card!); else flipped.delete(card.dataset.card!);
    };
    card.onclick = turn;
    card.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); turn(); } };
  });
}

let logicKey = '';
async function classLogicDeck(r: Payload, el: HTMLElement): Promise<void> {
  let d: Payload;
  try { d = await api(`/api/class_logic?preset=${encodeURIComponent(r.preset)}`); } catch { el.innerHTML = deckSwitch('logic') + `<div class="${emptyCls()}">the logic deck could not be read (a dashboard server started before it existed has to be restarted)</div>`; wireDeckSwitch(el, r); return; }
  const key = JSON.stringify(d);
  if (key === logicKey && el.dataset.preset === r.preset && el.dataset.shown === 'logic') return;
  logicKey = key; el.dataset.preset = r.preset; el.dataset.shown = 'logic';
  const short = (n: string) => (n || '').replace('fu-ogden-v0-1', 'Ogden').replace('fu-ogden-v0-2', 'Ogden v0.2').replace('-pre', '');
  const refName = (n: string) => (n || '').split('/').pop()!.replace(/-(bf16|4bit)$/, '');
  const f = (v: number | null | undefined) => v == null ? '–' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;
  const bar = d.references.find((x: any) => x.model === d.bar);
  const best = (rel: string) => d.voyages.reduce((b: any, v: any) => (v.gains[rel] && (!b || v.gains[rel].gain > b.g.gain)) ? { v, g: v.gains[rel] } : b, null);
  const pos = (x: number) => Math.max(0, Math.min(100, 50 + 100 * x));
  const meter = (g: any, cls: string) => g ? `<div class="lgbar ${cls}" title="${f(g.gain)} (90% band ${f(g.lo)} to ${f(g.hi)})"><i style="left:${pos(Math.min(g.lo ?? g.gain, g.gain))}%;width:${Math.max(1, pos(Math.max(g.hi ?? g.gain, g.gain)) - pos(Math.min(g.lo ?? g.gain, g.gain)))}%"></i><b style="left:${pos(g.gain)}%"></b></div>` : '<div class="s">not read</div>';
  const tiles = d.deck.map((x: any) => {
    const b = best(x.relation), q = bar && bar.gains[x.relation];
    return `<a class="dcard lgcard lglink" href="${modelHref(r, 'overview', 'logic-' + x.relation)}" title="the ${esc(x.relation)} relation in detail">${cardArt('logic_' + x.relation)}<div class="dname">${esc(x.relation)} <span class="s">→ in detail</span></div><div class="s">${esc(x.about)} · ${x.items} items</div>
      ${x.example ? `<div class="lgex"><span class="s">${esc(x.example.prompt)}</span> <b>${esc(x.example.idea)}</b> <span class="s">not</span> <i>${esc(x.example.rival)}</i></div>` : ''}
      <div class="lgrow"><span class="s">this size${b ? ` (${esc(short(b.v.voyage))}, ${b.v.deck}-item)` : ''}</span>${meter(b && b.g, 'mine')}<span class="lgv">${f(b && b.g.gain)}</span></div>
      <div class="lgrow"><span class="s">${esc(refName(d.bar))}${bar ? ` (${bar.deck}-item)` : ''}</span>${meter(q, 'ref')}<span class="lgv">${f(q && q.gain)}</span></div>
    </a>`;
  }).join('');
  const rels = [...d.relations, 'overall', 'one_hop'];
  const head = `<tr><th>model</th><th>deck</th>${rels.map((x: string) => `<th>${x === 'one_hop' ? 'one-hop' : x}</th>`).join('')}</tr>`;
  const cell = (g: any, rel: string) => { if (!g) return '<td class="s">–</td>'; const ok = rel !== 'one_hop' && g.gain >= d.mark && (g.lo == null || g.lo > 0); return `<td class="${ok ? 'pass' : ''}" title="${g.lo != null ? `90% band ${f(g.lo)} to ${f(g.hi)}; ${g.chained}/${g.items} items chained` : ''}">${f(g.gain)}${ok ? ' ✓' : ''}</td>`; };
  const row = (name: string, deck: string, gains: any, mine: boolean) => `<tr${mine ? ' class="mine"' : ''}><td>${name}</td><td class="s">${deck}</td>${rels.map((x: string) => cell(gains[x], x)).join('')}</tr>`;
  el.innerHTML = `<div class="dtop"><div class="s dsum">The logic deck: ${d.deck.reduce((a: number, x: any) => a + x.items, 0)} items in five relations, on invented words so knowledge cannot answer. The chaining gain is both premises against the stronger alone (the mark ${d.mark}); the bar is the band a model's own items allow. The 50m's reason for being.</div>${deckSwitch('logic')}</div>
    <div class="dgrid lggrid">${tiles}</div>
    <h3>Every reading <span class="s">this size's voyages first (the 40-item deck where read, else the 8-item deck), then the reference models by size; ✓ at the mark with the band above zero</span></h3>
    <div class="scroll"><table class="subjtable">${head}${d.voyages.map((v: any) => row(`<span class="mono">${esc(short(v.voyage))}</span>`, `${v.deck}-item`, v.gains, true)).join('')}${d.references.map((x: any) => row(esc(refName(x.model)), `${x.deck}-item`, x.gains, false)).join('')}</table></div>`;
  wireDeckSwitch(el, r);
}

async function classLogicRelation(r: Payload, el: HTMLElement, rel: string): Promise<void> {
  el.dataset.shown = 'relation:' + rel;
  let d: Payload;
  try { d = await api(`/api/logic_relation?preset=${encodeURIComponent(r.preset)}&relation=${encodeURIComponent(rel)}`); } catch { el.innerHTML = `<div class="${emptyCls()}">the relation could not be read (a dashboard server started before it existed has to be restarted)</div>`; return; }
  const f = (v: number | null | undefined) => v == null ? '–' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;
  const short = (n: string) => (n || '').replace('fu-ogden-v0-1', 'Ogden').replace('fu-ogden-v0-2', 'Ogden v0.2').replace('-pre', '');
  const refName = (n: string) => (n || '').split('/').pop()!.replace(/-(bf16|4bit)$/, '');
  const M = (p: number | null) => p == null ? '' : p >= 1e9 ? `${(p / 1e9).toFixed(1)}B` : `${Math.round(p / 1e6)}M`;
  const back = `<a class="s" href="${modelHref(r, 'overview')}">← the logic deck</a>`;
  const nav = d.relations.map((x: string) => x === rel ? `<b>${esc(x)}</b>` : `<a href="${modelHref(r, 'overview', 'logic-' + x)}">${esc(x)}</a>`).join(' · ');
  const hi = (text: string, words: string[]) => words.filter(Boolean).reduce((t, w) => t.split(w).join(`<u>${w}</u>`), esc(text));
  const variants = d.item.map((v: any) => `<tr><td><b>${esc(v.variant)}</b><div class="s">${esc(v.about)}</div></td><td>${hi(v.prompt, [v.bridge, v.distractor])} <b class="good">${esc(v.idea)}</b> <span class="s">not</span> <span class="bad">${esc(v.rival)}</span></td></tr>`).join('');
  const bars = (rows: any[], label: (x: any) => string) => rows.filter((x) => x.gain).map((x) => {
    const g = x.gain, pos = (v: number) => Math.max(0, Math.min(100, 50 + 100 * v));
    const ok = g.gain >= d.mark && g.lo > 0;
    return `<div class="lgline"><span class="lgname">${label(x)}</span><div class="lgbar ${x.model === d.bar ? 'ref' : x.voyage ? '' : 'other'}" title="90% band ${f(g.lo)} to ${f(g.hi)}; ${g.chained}/${g.items} items chained"><i style="left:${pos(g.lo)}%;width:${Math.max(1, pos(g.hi) - pos(g.lo))}%"></i><b style="left:${pos(g.gain)}%"></b></div><span class="lgv">${f(g.gain)}${ok ? ' ✓' : ''}</span></div>`;
  }).join('');
  const kn = d.knockout ? `<p class="s">Silencing each card's 16 strongest heads in ${esc(refName(d.knockout.model))} (baseline gain on this relation ${f(d.knockout.baseline)}), the drop in this relation's gain (positive: the card helps it):</p><table class="subjtable">${d.knockout.drops.map((x: any) => `<tr><td>${esc(x.condition)}</td><td>${f(x.drop)}</td></tr>`).join('')}</table>`
    : `<p class="s">Not read yet: the knockout of Qwen3 4B (every card's and suit's heads silenced, this relation's gain re-read) is queued after the 21m. Until it is in, the cards above are a hypothesis.</p>`;
  const per = d.per_item.map((p: any) => `<details><summary><span class="mono">${esc(short(p.voyage))}</span> <span class="s">${p.deck}-item deck, step ${p.step}: ${p.items.filter((i: any) => i.chained).length} of ${p.items.length} items chained</span></summary><table class="subjtable"><tr><th>item</th><th>both premises</th><th>first alone</th><th>second alone</th><th>one hop</th><th></th></tr>${p.items.map((i: any) => `<tr><td class="mono">${esc(i.item)}</td><td>${f(i.both)}</td><td>${f(i.first)}</td><td>${f(i.second)}</td><td>${f(i.one_hop)}</td><td>${i.chained ? '<span class="good">chained</span>' : '<span class="s">not</span>'}</td></tr>`).join('')}</table></details>`).join('');
  el.innerHTML = `<div class="lgdetail">${back}<div class="s lgnav">${nav}</div>
    <h3>${esc(d.title)} <span class="s">· ${d.items} items</span></h3>
    <p>${esc(d.asks)}</p>
    <h4>The steps a model must take</h4><ol>${d.steps.map((x: string) => `<li>${esc(x)}</li>`).join('')}</ol>
    <h4>How it is built</h4><p class="s">${esc(d.built)}</p>
    <h4>One item, in every way it is asked <span class="s">the middle term and the distractor underlined; the right answer, then the rival</span></h4>
    <div class="scroll"><table class="subjtable lgvariants">${variants}</table></div>
    ${d.examples.length ? `<p class="s">Three more: ${d.examples.map((x: any) => `${esc(x.prompt)} <b>${esc(x.idea)}</b>`).join(' · ')}</p>` : ''}
    <h4>The cards it should need <span class="s">a hypothesis from how the items are built; the knockout tests it</span></h4>
    <ul>${d.cards.map((c: any) => `<li><b>${esc(c.name)}</b> <span class="s">(${esc(c.suit)})</span>: ${esc(c.why)}</li>`).join('')}</ul>
    <h4>What silencing them does</h4>${kn}
    <h4>Why it is hard</h4><p class="s">${esc(d.hard)}</p>
    <h4>The chaining gain on ${esc(rel)} <span class="s">both premises against the stronger alone; the bar is the 90% band, the dotted line the mark (${d.mark})</span></h4>
    ${bars(d.voyages, (x) => `<span class="mono">${esc(short(x.voyage))}</span> <span class="s">${x.deck}-item</span>`)}
    ${bars(d.references, (x) => `${esc(refName(x.model))} <span class="s">${M(x.params)}, ${x.deck}-item</span>`)}
    <h4>This size, item by item</h4>${per || '<p class="s">no voyage of this size has read the logic deck yet</p>'}
    <h4>All ${d.all_items.length} items <span class="s">each asked with both premises (the middle term and the distractor underlined), its answer and the rival; for every reader of the 40-item deck, ✓ where it chained the item (both premises above zero and above either alone)${d.readers.length ? '' : ': none has read the 40-item deck yet, so the columns fill in as the readings land'}</span></h4>
    <div class="scroll"><table class="subjtable lgall"><tr><th>item</th><th>question</th><th>answer</th>${d.readers.map((x: string) => `<th class="mono">${esc(x)}</th>`).join('')}</tr>${d.all_items.map((it: any) => `<tr><td class="mono">${esc(it.item)}</td><td>${hi(it.prompt, [it.bridge, it.distractor])}</td><td><b class="good">${esc(it.idea)}</b><div class="s">not <span class="bad">${esc(it.rival)}</span></div></td>${d.readers.map((x: string) => { const rr = it.results[x]; return rr ? `<td title="both ${f(rr.both)}, first ${f(rr.first)}, second ${f(rr.second)}">${rr.chained ? '<span class="good">✓</span>' : '<span class="s">✗</span>'} <span class="s">${f(rr.both)}</span></td>` : '<td class="s">–</td>'; }).join('')}</tr>`).join('')}</table></div></div>`;
}

let sopKey = '';
async function sopSummary(r: Payload, ladder: Ladder): Promise<void> {
  const el = document.getElementById('sopsummary'); if (!el) return;
  let d: Payload; try { d = await api(`/api/star_points?preset=${encodeURIComponent(r.preset)}`); } catch { return; }
  const runs = (ladder.runs || []).filter((x: any) => x.preset === r.preset && !(x.name || '').startsWith('smoke'));
  const latest = runs.sort((a: any, b: any) => String(b.started || '').localeCompare(String(a.started || '')))[0];
  const [lc, sr, sc] = await Promise.all([
    api(`/api/ladder_chaining?sop=${encodeURIComponent(latest && latest.sop || '')}`).catch(() => null),
    api('/api/suit_ratings').catch(() => null),
    api(`/api/sop_scores?preset=${encodeURIComponent(r.preset)}`).catch(() => null),
  ]);
  const chaining = lc ? (((lc.sizes || []).find((x: any) => x.size === r.preset) || {}).chaining ?? null) : null;
  const mine = sr ? ((sr.ships || []).find((x: any) => x.size === r.preset) || null) : null;
  const suits = mine ? [['copying', mine.copying], ['position', mine.position], ['comparing', mine.comparing], ['carrying', mine.carrying]] : null;
  const key = JSON.stringify([d.points, chaining, suits, sc && sc.versions, latest && latest.sop, latest && latest.name, latest && latest.status, latest && latest.started]);
  if (key === sopKey && document.getElementById('sopchart')) return;
  sopKey = key;
  const ps = (d.points || []).filter((p: any) => p.ours != null);
  const clears = ps.filter((p: any) => p.ours >= 1).length;
  const qwen = 0.538;
  const gapTxt = chaining == null ? 'no chaining reading yet' : `${chaining.toFixed(3)} against Qwen's ${qwen.toFixed(3)}`;
  const verdict = chaining == null ? 'The voyage has not been read on the chaining deck yet, so the standard is unjudged.'
    : chaining >= qwen ? 'This run matches or beats Qwen3 4B on chaining — the standard is working at this size.'
    : chaining > 0.05 ? 'This run chains, but behind Qwen3 4B: the standard is building some of the circuit.'
    : 'This run chains close to zero: at this size the standard is not yet building the circuit, whatever its cards read.';
  const points = ps.map((p: any) => `<tr><td class="s">${p.n}. ${esc(p.role)}</td><td>${p.ours.toFixed(2)}</td><td class="s">${p.qwen == null ? '–' : p.qwen.toFixed(2)}</td></tr>`).join('');
  const versions = sc ? (sc.versions || []).map((v: any) => {
    const ch = v.chaining == null ? '–' : v.chaining.toFixed(3);
    const gap = v.gap == null ? '' : `${v.gap > 0 ? '+' : ''}${v.gap.toFixed(3)}`;
    return `<tr><td class="mono">v${esc(v.sop)}</td><td>${esc(v.status)}</td><td><b>${ch}</b></td><td>${gap}</td><td>${v.clears}/${v.of}</td></tr>`;
  }).join('') : '';
  el.innerHTML = `<div class="libsum">
      <div class="libstats">
        <div class="libstat"><b>${esc(latest ? latest.sop ? 'v' + latest.sop : 'no SOP' : '–')}</b><span>the standard of the newest voyage</span></div>
        <div class="libstat"><b>${chaining == null ? '–' : chaining.toFixed(3)}</b><span>chaining (Qwen 0.538)</span></div>
        <div class="libstat"><b>${clears}/${ps.length}</b><span>chart points clearing their mark</span></div>
        <div class="libstat"><b>${suits ? suits.filter((s: any) => s[1] != null && s[1] >= 1).length + '/4' : '–'}</b><span>suits at or above their marks</span></div>
      </div>
      <div class="k">What it means</div><div>${esc(verdict)} ${esc(gapTxt)}.</div>
      ${suits ? `<div class="k mt">The suits</div><div class="s">${suits.map((s: any) => `${esc(s[0])} ${s[1] == null ? '–' : s[1].toFixed(2)}`).join(' · ')}</div>` : ''}
      <div class="k mt">The star chart, against Qwen3 4B</div><div class="chart" id="sopchart"></div>
      <div class="k mt">By SOP version <span class="s">the reasoning results at this size, one row a version: so a 0.0.6 run can be read beside 0.0.5 without leaving the ship</span></div>
      <div id="sopversions" class="s">${sc ? `<div class="scroll"><table class="selbooks"><thead><tr><th>version</th><th>status</th><th>chaining</th><th>gap to Qwen</th><th>points cleared</th></tr></thead><tbody>${versions}</tbody></table></div>` : 'the versions could not be read'}</div>
      ${points ? `<div class="k mt">The points, against Qwen</div><div class="scroll"><table class="selbooks"><tbody>${points}</tbody></table></div>` : ''}
      <div class="s mt">${latest ? `newest voyage ${esc(latest.name)}${latest.status ? ' · ' + esc(latest.status) : ''}` : ''}</div>
    </div>`;
  const { starChart } = await import('../../lib/panel');
  starChart('sopchart', ps, { label: r.preset, height: 300, ticks: 9 });
}

let ftKey = '';
function drawFtProgress(ladder: Ladder, allRuns: any[]): void {
  void (async () => {
    const { plot, layout, C, PALETTE } = await chart();
    const ext = (ladder.external || []).filter((x: any) => x.set === 'hole-cards-unseen' && x.bpb_mean_en != null);
    const pts = allRuns.map((x: any, i: number) => ({ x, i: i + 1 })).filter((p: any) => p.x.ft_en != null);
    const key = pts.map((p: any) => p.x.run_id + p.x.ft_en).join(',') + '|' + ext.length;
    if (key === ftKey) return;
    ftKey = key;
    if (!pts.length) { const { empty } = await chart(); empty('ftchart', 'no voyage at this size has a Forgotten Tomes score yet'); return; }
    let best = Infinity;
    const bestSoFar = pts.map((p: any) => (best = Math.min(best, p.x.ft_en)));
    plot('ftchart', [
      { type: 'scattergl', mode: 'markers', name: 'a voyage', x: pts.map((p: any) => p.i), y: pts.map((p: any) => p.x.ft_en),
        text: pts.map((p: any) => `${p.x.ship || p.x.name} · ${p.x.name}`), hovertemplate: 'run %{x}: %{text}<br>%{y:.3f} bpb<extra></extra>',
        marker: { size: 6, color: C.blue, opacity: 0.55 } },
      { type: 'scatter', mode: 'lines', name: 'best so far', x: pts.map((p: any) => p.i), y: bestSoFar, line: { color: C.good, width: 2, shape: 'hv' },
        hovertemplate: 'best so far %{y:.3f}<extra></extra>' },
    ], layout({ xaxis: { title: 'voyage, in the order they started', gridcolor: C.line },
      yaxis: { title: 'bits per byte', gridcolor: C.line, range: (() => {
        const ys = [...pts.map((p: any) => p.x.ft_en), ...ext.map((x: any) => x.bpb_mean_en)], lo = Math.min(...ys), hi = Math.max(...ys), pad = (hi - lo) * 0.06 || 0.05;
        return [lo - pad, hi + pad]; })() },
      legend: { orientation: 'h', y: 1.08 },
      shapes: ext.map((x: any, i: number) => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: x.bpb_mean_en, y1: x.bpb_mean_en, line: { color: PALETTE[(i + 4) % PALETTE.length], dash: 'dot' } })),
      annotations: ext.map((x: any, i: number) => ({ xref: 'paper', x: 1, xanchor: 'right', y: x.bpb_mean_en, yanchor: 'bottom', showarrow: false,
        text: `${x.model.split('/').pop()} ${x.bpb_mean_en.toFixed(3)}`, font: { size: 10, color: PALETTE[(i + 4) % PALETTE.length] } })) }));
  })();
}

// ---- Training --------------------------------------------------------------------------------------
function drawRungOverview(r: Payload): void {
  const el = document.getElementById('rungover'); if (!el) return;
  el.innerHTML = [
    ['overview', r.overview], ['shape', `${r.layers} layers × ${r.width} wide, ${r.heads} heads`],
    ['parameters', `${big(r.total)} (${big(r.non_embedding)} non-embedding)`], ['where it trains', r.where],
    ['judged by', r.scored], ['status', r.status],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${esc(v)}</div></div>`).join('');
}
async function sizeJourney(r: Payload): Promise<void> {
  const el = document.getElementById('sizejourney'); if (!el) return;
  let d: Payload; try { d = await api(`/api/star_points?preset=${encodeURIComponent(r.preset)}`); } catch { return; }
  const { starChart } = await import('../../lib/panel');
  starChart(el, d.points, { label: r.preset, height: 380 });
}
let watchTimer: number | undefined = undefined;
let watchPreset = '';
async function drawWatch(r: Payload, path: string): Promise<void> {
  const head = document.getElementById('watchhead'); if (!head) return;
  if (watchPreset !== r.preset) { watchPreset = r.preset; }
  if (watchTimer) window.clearTimeout(watchTimer);
  let d: Payload;
  try { d = await api(`/api/watch?preset=${encodeURIComponent(r.preset)}&sop=${encodeURIComponent(sopPick)}`); } catch { head.innerHTML = `<div class="${emptyCls()}">the voyage could not be read (a dashboard server started before the Watch panel has to be restarted)</div>`; return; }
  const again = (): void => { if (isSizePage(location.pathname) && sizeAddress(path).tab === 'training') void drawWatch(r, path); };
  if (d.voyage && d.voyage.status === 'at sea') watchTimer = window.setTimeout(again, 30000);
  if (!d.voyage) { head.innerHTML = `<div class="${emptyCls()}">no voyage of this size on the ledger yet</div>`; return; }
  const v = d.voyage, w = d.where, M = (x: number | null) => x == null ? '–' : `${(x / 1e6).toFixed(x < 1e8 ? 1 : 0)}M`;
  const pct = w.total_steps ? Math.min(100, 100 * w.step / w.total_steps) : 0;
  head.innerHTML = `<div class="wtop"><span class="${pillCls(v.status === 'at sea' ? 'running' : 'good')}">${esc(v.status)}</span> <b class="mono">${esc(v.name)}</b>
      <span class="s">${esc((v.model || {}).preset || '')} · ${esc((v.model || {}).positions || '')} · lr ${v.lr ?? '–'}${v.fitout ? ` · fitout ${esc(v.fitout.key)}${v.fitout.variation ? ' ~ ' + esc(v.fitout.variation) : ''}` : ''}</span></div>
    <div class="wnums"><div><b>${w.step.toLocaleString()}</b><span class="s"> of ${w.total_steps ? Math.round(w.total_steps).toLocaleString() : '–'} steps</span></div>
      <div><b>${M(w.tokens)}</b><span class="s"> of ${M(w.tokens_total)} tokens</span></div>
      <div><b>pass ${w.pass ?? '–'}</b><span class="s"> of ${w.passes}</span></div>
      <div><b>${w.tokens_per_s ? Math.round(w.tokens_per_s).toLocaleString() : '–'}</b><span class="s"> tokens a second</span></div>
      <div><b>${hms(w.elapsed_s)}</b><span class="s"> sailing</span></div>
      <div><b>${v.status === 'at sea' ? hms(w.eta_s) : 'home'}</b><span class="s">${v.status === 'at sea' ? ' to go (readings included)' : ''}</span></div></div>
    <div class="wprog"><i style="width:${pct}%"></i></div>
    <div class="s">${w.last_reading_s_ago != null && v.status === 'at sea' ? `last reading ${Math.round(w.last_reading_s_ago)} s ago · the panel reads again every 30 s` : ''}</div>`;
  const all = [...(d.stages || []), ...(d.post || [])];
  const passes = all.reduce((a: number, s: any) => a + (s.passes || 1), 0) || 1;
  const herePass = (w.pass || 1) - 1 + ((w.tokens_total ? (w.tokens % (w.tokens_total / w.passes)) / (w.tokens_total / w.passes) : 0));
  const stagesEl = document.getElementById('watchstages');
  if (stagesEl) stagesEl.innerHTML = `<div class="wstagebar">${all.map((s: any, si: number) => {
      const width = 100 * (s.passes || 1) / passes;
      const isThis = si < d.stages.length;
      const cells = Array.from({ length: s.passes || 1 }, (_, k) => {
        const state = !isThis ? 'later' : (k < Math.floor(herePass) ? 'done' : k === Math.floor(herePass) ? 'now' : 'later');
        const fill = state === 'now' ? Math.round(100 * (herePass - Math.floor(herePass))) : state === 'done' ? 100 : 0;
        return `<div class="wpass ${state}" title="${esc(s.name)}, pass ${k + 1} of ${s.passes}"><i style="width:${fill}%"></i><span>pass ${k + 1}</span></div>`;
      }).join('');
      return `<div class="wstage" style="flex:${width}"><div class="wsname"><b>${esc(s.phase)}</b>${s.name !== s.phase ? ` · ${esc(s.name)}` : ''} <span class="s">${esc((s.library || '').replace('lists/', ''))}${s.lr ? ` · lr ${s.lr}` : ''}</span></div><div class="wpasses">${cells}</div></div>`;
    }).join('')}</div>${d.post.length ? '' : '<div class="s">one stage: this voyage is pretraining only (the fitout has no post-training)</div>'}${scaffoldBar(d.scaffold, w.tokens)}`;
  const drawn = document.getElementById('watchdrawn');
  if (drawn) drawn.innerHTML = d.drawn.length ? `<div class="s">cards drawn, in order (the deck's rules):</div><div class="wchips">${d.drawn.map((c: any) => `<span class="wchip"><img src="/art/${esc(c.card)}.png" alt="" onerror="this.style.display='none'"><b>${esc(c.card.replace(/_/g, ' '))}</b><span class="s">${M(c.tokens)} tokens${c.layer != null ? ` · layer ${c.layer}` : ''}</span></span>`).join('')}</div>` : '<div class="s">no card drawn yet</div>';
  const { plot, layout, C, PALETTE, empty } = await chart();
  const S = d.series, xs = (p: any[]) => p.map((q) => q[0] / 1e6), ys = (p: any[]) => p.map((q) => q[1]);
  const lay = (yt: string, extra: any = {}) => layout({ xaxis: { title: 'tokens read (millions)', gridcolor: C.line }, yaxis: { title: yt, gridcolor: C.line }, showlegend: true, ...extra });
  const line = (k: string, name: string, i: number, more: any = {}) => S[k] && S[k].length ? [{ type: 'scatter', mode: S[k].length > 30 ? 'lines' : 'lines+markers', name, x: xs(S[k]), y: ys(S[k]), line: { color: PALETTE[i % PALETTE.length] }, ...more }] : [];
  plot('watchloss', [...line('loss', 'loss', 0), ...line('lr', 'learning rate', 1, { yaxis: 'y2' }), ...line('scaffold_loss', 'scaffold pull (distance from the pattern)', 6), ...line('scaffold_weight', 'scaffold weight', 7, { yaxis: 'y2', line: { color: PALETTE[7 % PALETTE.length], dash: 'dot' } })], lay('loss (nats a token)', { yaxis2: { overlaying: 'y', side: 'right', title: 'learning rate', showgrid: false } }));
  if (S.bpb && S.bpb.length) plot('watchbpb', line('bpb', 'Forgotten Tomes', 2), lay('bits per byte')); else empty('watchbpb', 'the judge books are read every 640 steps');
  plot('watchshapes', [...line('upos', 'part of speech', 3), ...line('ogden', 'Ogden kind', 4), ...line('keyed', 'keyed word', 5)], lay('right', { yaxis: { tickformat: '.0%', gridcolor: C.line, title: 'top guess right' } }));
  const marks: [string, string, number][] = [['previous_word', 'previous-word', 0.5], ['nevermore', 'induction (Nevermore look, one head)', 0.3], ['nevermore_shared', 'induction (two heads of a layer together)', 0.3], ['comparator', 'comparator', 0.3], ['words_back', 'words back', 0.3], ['mover', 'mover', 0.2]];
  plot('watchcards', marks.flatMap(([k, n], i) => line(k, n, i)), lay('reading', { shapes: [...new Set(marks.map((m) => m[2]))].map((y) => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color: C.accent, dash: 'dot', width: 1 } })) }));
  plot('watchchain', [...line('copy_gain', 'copy gain (nats)', 0), ...line('one_hop', 'one-hop lift', 1), ...line('cause', 'cause gain', 2)], lay('', { shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0, y1: 0, line: { color: C.line } }] }));
  const log = document.getElementById('watchlog'); if (log) log.textContent = d.log.join('\n');
}

const DEPTH_CARDS: [string, string][] = [['previous_word', 'previous-word'], ['duplicate_word', 'duplicate-word'], ['induction', 'induction'],
  ['natural_book', 'the Nevermore'], ['attention_sink', 'the sink'], ['delimiter', 'the delimiter'],
  ['offset_2', 'words back'], ['rare_word', 'the rare word'], ['premise_marker', 'premise-marker'],
  ['comparator', 'the comparator'], ['bridge', 'the bridge'], ['mover', 'the mover']];
async function drawDepth(r: Payload): Promise<void> {
  const host = document.getElementById('rung'); if (!host) return;
  let panel = document.getElementById('depthpanel');
  if (!panel) { panel = document.createElement('section'); panel.id = 'depthpanel'; panel.className = 'panel mt'; host.appendChild(panel); }
  let d: Payload; try { d = await api(`/api/depth?preset=${encodeURIComponent(r.preset)}&sop=${encodeURIComponent(sopPick)}`); } catch { return; }
  const shapes = Object.entries(d.shapes || {}) as [string, any][]; if (!shapes.length) { panel.remove(); return; }
  panel.innerHTML = `<h2>The depth <span class="note">every shape of this size, drawn against its layers: the deck's order on the vertical axis, depth on the horizontal. A card is found where its colour is strongest; the last column is the layer it is read best in. In Qwen3 4B the copy cards sit two-thirds down; in the 300k there are only two layers to sit in</span></h2>` +
    shapes.map(([preset, s]) => {
      const layers = s.layers, all = Object.values(s.cards).flat() as number[], max = Math.max(1, ...all);
      const rows = DEPTH_CARDS.filter(([k]) => s.cards[k]).map(([k, label]) => {
        const vals = s.cards[k], best = vals.indexOf(Math.max(...vals));
        return `<tr><td class="s">${esc(label)}</td>` + Array.from({ length: layers }, (_, i) => {
          const v = vals[i] ?? 0, a = Math.max(0, v / max);
          return `<td title="${esc(label)} at layer ${i}: ${v}" style="background:color-mix(in srgb, var(--accent) ${Math.round(a * 85)}%, transparent)"></td>`;
        }).join('') + `<td class="s">L${best}</td></tr>`;
      }).join('');
      return `<div class="k mt">${esc(preset)} — ${layers} layers <span class="s">(${esc(String(s.run || '').slice(0, 44))}, ${esc(s.status || '')})</span></div>
        <div class="scroll"><table class="selbooks depthgrid"><thead><tr><th></th>${Array.from({ length: layers }, (_, i) => `<th class="s">${i}</th>`).join('')}<th>found</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }).join('');
}
async function drawLossChart(r: Payload): Promise<void> {
  const { plot, layout, C, PALETTE, empty } = await chart();
  try {
    const curves = await api('/api/rung?preset=' + encodeURIComponent(r.preset) + '&limit=12');
    const withLoss = curves.filter((c: any) => c.steps.length);
    if (!withLoss.length) empty('losschart', 'no training at this size yet');
    else plot('losschart', withLoss.map((c: any, i: number) => ({ type: 'scatter', mode: 'lines', name: c.ship || c.name, x: c.steps, y: c.loss, line: { color: PALETTE[i % PALETTE.length], width: 1.5 } })), layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title: 'loss', gridcolor: C.line } }));
  } catch { empty('losschart', 'could not load the curves'); }
}

// ---- Goals ----------------------------------------------------------------------------------------
let reachData: Payload = null, reachAt = 0;
async function reach(ladder: Ladder): Promise<Payload> {
  if (!reachData || Date.now() - reachAt > 30000) { try { reachData = await api('/api/discoveries'); reachAt = Date.now(); } catch { /* keep */ } }
  return reachData;
}
let goalsKey = '';
async function classGoals(r: Payload, ladder: Ladder): Promise<void> {
  const d = await reach(ladder); if (!d) return;
  const key = r.preset + JSON.stringify(d);
  if (!changed('goals', key) && document.querySelector('#goalroute .wp')) return;
  const kts = d.known_tricks || [], wps = d.waypoints || [], me = classRank(ladder, r.preset);
  const wpRank = (k: string) => wps.findIndex((w: any) => w.key === k), tname = Object.fromEntries(kts.map((t: any) => [t.key, t.name]));
  const where = (t: any) => t.target_class == null ? (t.taught ? 'taught' : 'beyond') : classRank(ladder, t.target_class) < me ? 'below' : classRank(ladder, t.target_class) === me ? 'mine' : 'above';
  const onClass = (t: any) => {
    const ft = t.fleet && (d.tricks || []).find((x: any) => x.key === t.fleet);
    if (!t.fleet) return { text: 'not measured yet', done: false };
    if (ft && ft.viable === false) return { text: 'not viable on Gutenberg in English', done: false };
    if (ft && !ft.evaluator) return { text: `pre-registered${ft.cutoff ? ` (cutoff ${ft.cutoff})` : ''} · evaluator not built yet`, done: false };
    const mine = ft ? ft.ships.filter((x: any) => x.preset === r.preset) : [];
    if (!mine.length) return { text: 'measured · no voyage of this size has a reading yet', done: false };
    const done = mine.filter((x: any) => x.performed_at != null), best = Math.max(...mine.map((x: any) => x.best));
    return { text: done.length ? `on ${done.length} of ${mine.length} sailings` : `best ${fmt(best)} of ${ft.threshold} on ${mine.length} sailings`, done: done.length > 0 };
  };
  const goals = kts.filter((t: any) => where(t) === 'mine'), carried = kts.filter((t: any) => where(t) === 'below');
  const level = goals.length ? wps[Math.max(...goals.map((t: any) => wpRank(t.waypoint)))] : null;
  const ceiling = level ? goals.filter((t: any) => t.waypoint === level.key) : [];
  const nextCls = ladder.rungs[me + 1], nextGoals = nextCls ? kts.filter((t: any) => t.target_class === nextCls.preset) : [];
  const done = goals.filter((t: any) => onClass(t).done).length;
  const cov = coverage(d, ladder, r.preset), filled = cov.reduce((n: number, c: any) => n + c.here, 0), inh = cov.reduce((n: number, c: any) => n + c.inherited, 0), all = cov.reduce((n: number, c: any) => n + c.total, 0);
  const C = await import('./chains');
  const covEl = document.getElementById('goalcoverage');
  if (covEl) covEl.innerHTML = cov.map((c: any, i: number) => `<div class="crow"><span class="cname">${i + 1}. ${esc(c.name)}</span>${C.coverageBar(c)}
    <span class="cnum">${c.here} here${c.inherited ? ` · ${c.inherited} inherited` : ''} · ${c.open} open of ${c.total}</span></div>`).join('')
    + `<div class="crow total"><span class="cname">the route</span>${C.coverageBar({ here: filled, inherited: inh, open: all - filled - inh, total: all })}<span class="cnum">${filled} here · ${inh} inherited · ${all - filled - inh} open of ${all}</span></div>`;
  const overEl = document.getElementById('goalsover');
  if (overEl) overEl.innerHTML = [
    ['the primary objective', (() => { const role = r.role || r.job || ''; const m = role.match(/^Primary objective:\s*([^.]*)\.?\s*(.*)$/i);
      return m ? `<b class="primarygoal">${esc(m[1])}</b>${m[2] ? `<div class="s">${esc(m[2])}</div>` : ''}<div class="s">beyond it: as many tricks as it can learn, carried up to the next class</div>`
        : `${role ? `<b class="primarygoal">${esc(role)}</b><div class="s">` : '<div>'}as many tricks as it can learn, building on all the tricks below it, carried up to the next class</div>`; })()],
    ['expected at this size', level ? `<b>${esc(level.name)}</b> (step ${wpRank(level.key) + 1} of ${wps.length})` : 'nothing from books at this size'],
    ['the expected edge', ceiling.length ? ceiling.map((t: any) => `<a href="/discoveries/${esc(t.key)}">${t.gate ? '◆ ' : ''}${esc(t.name)}</a>`).join(', ') + '<br><span class="s">where a ship this size is expected to stop; beyond it is pushing the envelope</span>' : '–'],
    ['filled so far', `${filled} of ${all} tricks performed here${inh ? `, ${inh} more inherited to carry up` : ''} · ${done} of the ${goals.length} the field expects`],
    ['carried up', carried.length ? `${carried.length} expected of smaller classes, kept, not relearned` : 'none: the first class on the ladder; everything it learns is carried up'],
    ['next class', nextCls ? `${classLink(ladder, nextCls.preset)} takes over with ${nextGoals.length}: ${nextGoals.slice(0, 4).map((t: any) => esc(t.name)).join(', ')}${nextGoals.length > 4 ? '…' : ''}` : 'the top of the ladder; beyond it, the horizon'],
  ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  const routeEl = document.getElementById('goalroute');
  if (routeEl) routeEl.innerHTML = [...wps].reverse().map((w: any) => {
    const ts = kts.filter((t: any) => t.waypoint === w.key).sort((a: any, b: any) => (a.target_class ? classRank(ladder, a.target_class) : 99) - (b.target_class ? classRank(ladder, b.target_class) : 99));
    const isLevel = level && level.key === w.key;
    return `<div class="wp${isLevel ? ' level' : ''}"><div class="wpname">${wpRank(w.key) + 1}. ${esc(w.name)}${isLevel ? ` <span class="${pillCls('accent')}">target level</span>` : ''}</div>
      <div class="chips">${ts.map((t: any) => { const s = where(t), st = s === 'mine' || s === 'below' ? onClass(t) : null;
        const tip = `${t.name}: ${s === 'mine' ? 'a goal of this size' : s === 'below' ? `carried up from ${t.target_class}` : s === 'above' ? `a goal of ${t.target_class}` : s === 'taught' ? 'a reference, taught not read' : 'beyond the ladder'}${st ? ' · ' + st.text : ''}`;
        return `<a class="chip ${s}${st && st.done ? ' done' : ''}" href="/discoveries/${esc(t.key)}" title="${esc(tip)}">${t.gate ? '◆ ' : ''}${esc(t.name)}${st && st.done ? ' ✓' : ''}${s === 'above' ? ` <span class="cls">${esc(t.target_class)}</span>` : ''}</a>`; }).join('')}</div></div>`;
  }).join('');
  fillStepFilter(document.getElementById('goalfilter') as HTMLSelectElement | null, wps);
  const gf = (document.getElementById('goalfilter') as HTMLSelectElement | null)?.value || '';
  const shown = goals.filter((t: any) => !gf || t.waypoint === gf);
  const tb = document.querySelector('#goaltable tbody');
  if (tb) tb.innerHTML = shown.length ? shown.sort((a: any, b: any) => wpRank(a.waypoint) - wpRank(b.waypoint)).map((t: any) => {
    const st = onClass(t);
    return `<tr data-trick="${esc(t.key)}" tabindex="0"><td><b>${esc(t.name)}</b>${C.leadNote(t, kts)}</td><td data-sort="${wpRank(t.waypoint)}">${esc((wps.find((w: any) => w.key === t.waypoint) || {}).name)}</td>
      <td>${t.gate ? '◆ gate' : 'milestone'}</td><td>${t.rests_on.length ? esc(t.rests_on.map((k: string) => tname[k] || k).join(', ')) : '–'}</td>
      <td data-sort="${t.field_params ?? ''}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td>
      <td>${st.done ? `<span class="${pillCls('good')}">performed</span> ` : ''}${esc(st.text)}</td></tr>`;
  }).join('') : `<tr><td colspan="6" class="${emptyCls(true)}">${goals.length ? 'none of this size\'s goals at this step' : 'no goals set for this size yet'}</td></tr>`;
  const gfEl = document.getElementById('goalfilter') as HTMLSelectElement | null;
  if (gfEl) gfEl.onchange = () => { dataKeys['goals'] = ''; void classGoals(r, ladder); };
  wireTrickRows();
}
function coverage(data: Payload, ladder: Ladder, preset: string): any[] {
  const kts = data.known_tricks || [], wps = data.waypoints || [], me = classRank(ladder, preset);
  const performedBy = (t: any) => { const ft = t.fleet && (data.tricks || []).find((x: any) => x.key === t.fleet); return ft ? ft.ships.filter((x: any) => x.performed_at != null).map((x: any) => x.preset) : []; };
  return wps.map((w: any) => {
    const ts = kts.filter((t: any) => t.waypoint === w.key && !t.taught);
    let here = 0, inherited = 0;
    for (const t of ts) {
      const by = performedBy(t);
      if (by.includes(preset)) here++;
      else if (by.some((p: string) => classRank(ladder, p) < me)) inherited++;
    }
    return { key: w.key, name: w.name, total: ts.length, here, inherited, open: ts.length - here - inherited };
  });
}
function drawGoalNotes(r: Payload, ladder: Ladder): void { void r; void ladder; }
function wireTrickRows(): void {
  document.querySelectorAll<HTMLElement>('#goaltable tr[data-trick], #wp-expected tr[data-trick], #wp-envelope tr[data-trick], #wp-stars tr[data-trick]').forEach((tr) => {
    tr.onclick = (e) => { if ((e.target as HTMLElement).closest('a')) return; location.href = '/discoveries/' + tr.dataset.trick; };
  });
}
const wsubOf = (path: string): string => sizeAddress(path).wsub;

// ---- Waypoints ------------------------------------------------------------------------------------
async function classSteps(r: Payload, ladder: Ladder): Promise<void> {
  const d = await reach(ladder); if (!d) return;
  const kts = d.known_tricks || [], wps = d.waypoints || [], me = classRank(ladder, r.preset), band = sizeBand(r.total);
  const wpRank = (k: string) => wps.findIndex((w: any) => w.key === k), heads = Object.fromEntries((d.known_heads || []).map((h: any) => [h.key, h]));
  const expected = kts.filter((t: any) => t.field_params != null && t.field_band_rank <= band);
  const ex = new Set(expected.map((t: any) => t.key));
  const envelope = kts.filter((t: any) => !ex.has(t.key) && t.target_class && classRank(ladder, t.target_class) <= me);
  const stars = kts.filter((t: any) => !ex.has(t.key) && t.target_class && classRank(ladder, t.target_class) > me);
  const sets: Record<string, any[]> = { expected, envelope, stars };
  const names: Record<string, string> = { expected: 'Expected', envelope: 'Pushing the envelope', stars: 'Exploring the stars' };
  const about: Record<string, string> = { expected: 'match the field at this size', envelope: 'what nobody has shown at this size', stars: 'the ambitious ones, for bigger classes' };
  const C = await import('./chains');
  const path = location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname;
  const wpSub = wsubOf(path);
  const stepsEl = document.getElementById('wpsteps');
  if (stepsEl) stepsEl.innerHTML = WSUBS.map((k, i) => {
    const ts = sets[k], st = ts.map((t: any) => C.trickOnClass(t, r.preset, d)), done = st.filter((x: any) => x.done).length, meas = st.filter((x: any) => x.measured).length;
    const proven = ts.length && done === ts.length;
    return `<a class="st${k === wpSub ? ' on' : ''}${proven ? ' proven' : ''}" href="${modelHref(r, 'waypoints', k)}"><div class="t">${i + 1} · ${names[k]}</div>
      <div class="c">${about[k]} · ${ts.length} trick${ts.length === 1 ? '' : 's'} · ${meas} measured · ${done} performed</div></a>`;
  }).join('');
  fillStepFilter(document.getElementById('wpfilter') as HTMLSelectElement | null, wps);
  const wf = (document.getElementById('wpfilter') as HTMLSelectElement | null)?.value || '';
  const head = '<tr><th>step</th><th>trick</th><th>the field shows it at</th><th>goal class</th><th>stars needed (on this size)</th><th>on this size</th></tr>';
  for (const k of WSUBS) {
    const rows = sets[k].filter((t: any) => !wf || t.waypoint === wf).sort((a: any, b: any) => wpRank(a.waypoint) - wpRank(b.waypoint) || a.field_band_rank - b.field_band_rank);
    const table = document.getElementById('wp-' + k) as HTMLTableElement | null;
    if (!table) continue;
    table.tHead!.innerHTML = head;
    table.tBodies[0].innerHTML = rows.length ? rows.map((t: any) => {
      const st = C.trickOnClass(t, r.preset, d);
      return `<tr data-trick="${esc(t.key)}" tabindex="0"><td data-sort="${wpRank(t.waypoint)}">${wpRank(t.waypoint) + 1}. ${esc((wps.find((w: any) => w.key === t.waypoint) || {}).name || t.waypoint)}</td>
        <td><b>${t.gate ? '◆ ' : ''}${esc(t.name)}</b>${t.taught ? ' <span class="s">(taught, not read)</span>' : ''}${C.leadNote(t, kts)}</td>
        <td data-sort="${t.field_params ?? ''}" title="${esc(t.field_at)}"><span class="sizeband">${esc(t.field_band)}</span></td>
        <td data-sort="${t.target_class ? classRank(ladder, t.target_class) : 99}">${t.target_class ? classLink(ladder, t.target_class) : '<span class="s">none</span>'}</td>
        <td>${t.stars.length ? t.stars.map((s: string) => C.starOnClass(heads[s], r.preset, d)).join('<br>') : '<span class="s">none charted</span>'}</td>
        <td data-sort="${st.sort}">${st.done ? `<span class="${pillCls('good')}">performed</span> ` : ''}${esc(st.text)}</td></tr>`;
    }).join('') : `<tr><td colspan="6" class="${emptyCls(true)}">${sets[k].length ? 'none at this step' : k === 'expected' ? 'nothing: the field shows no trick at this size; everything here is pushing the envelope' : k === 'envelope' ? 'no goals at this size beyond what the field already shows' : 'nothing above this size on the ladder'}</td></tr>`;
  }
  const wfEl = document.getElementById('wpfilter') as HTMLSelectElement | null;
  if (wfEl) wfEl.onchange = () => { void classSteps(r, ladder); };
  wireTrickRows();
}
const sizeBand = (n: number): number => Math.min(6, Math.max(0, Math.floor(Math.log10(n)) - 5));
const FAMILY: Record<string, string> = { position: 'position', copying: 'copying', circuit: 'the indirect-object circuit', suppression: 'suppression', structure: 'grammar and reference', task: 'the task' };
async function starsInReach(r: Payload, ladder: Ladder): Promise<void> {
  const d = await reach(ladder); if (!d) return;
  const me = classRank(ladder, r.preset), heads = d.known_heads || [];
  const inReach = heads.filter((h: any) => h.expected_from && classRank(ladder, h.expected_from) <= me).sort((a: any, b: any) => classRank(ladder, a.expected_from) - classRank(ladder, b.expected_from));
  const next = heads.filter((h: any) => h.expected_from && classRank(ladder, h.expected_from) === me + 1);
  const nextEl = document.getElementById('reachnext'); if (nextEl) nextEl.textContent = next.length ? `next in reach, one size up: ${next.map((h: any) => h.name).join(', ')}` : '';
  const tb = document.querySelector('#reachtable tbody');
  if (tb) tb.innerHTML = inReach.length ? inReach.map((h: any) => {
    const st = h.star && (d.stars || []).find((x: any) => x.key === h.star);
    let cell = '<td data-sort="9" class="s">not measured yet</td>';
    if (st) {
      const mine = st.ships.filter((x: any) => x.preset === r.preset), lit = mine.filter((x: any) => x.steps_to_lit != null), sh = mine.filter((x: any) => x.shared_steps_to_lit != null);
      const best = Math.max(-1, ...mine.map((x: any) => x.best ?? -1));
      cell = !mine.length ? '<td data-sort="8" class="s">measured, but no voyage of this size has a reading yet</td>'
        : `<td data-sort="${lit.length ? 0 : sh.length ? 1 : 2}">${lit.length ? `<span class="${pillCls('good')}">lit</span>` : sh.length ? `<span class="${pillCls('accent')}">lit shared</span>` : `<span class="${pillCls('')}">not lit yet</span>`}
          ${lit.length ? `on ${lit.length}` : sh.length ? `on ${sh.length}` : `best ${fmt(best)}`} of ${mine.length} sailings · threshold ${st.threshold}</td>`;
    }
    return `<tr><td><b>${esc(h.name)}</b></td><td>${esc(FAMILY[h.family] || h.family)}</td><td data-sort="${classRank(ladder, h.expected_from)}">${classLink(ladder, h.expected_from)}</td>
      <td class="s">${esc(h.expected_why || '')}</td>${cell}</tr>`;
  }).join('') : '<tr><td colspan="5" class="' + emptyCls(true) + '">no kind of head is expected this small</td></tr>';
}

// ---- the hand, waypoint by waypoint ---------------------------------------------------------------
let wpKey = '', wpData: Payload = null;
const hand = { run: null as string | null, idx: null as number | null, timer: 0 };
const handRuns = (): any[] => wpData ? wpData.runs.filter((x: any) => x.hands && x.hands.length) : [];
function drawHand(prevIdx: number | null = null): void {
  const el = document.getElementById('hand'), pick = document.getElementById('handrun') as HTMLSelectElement | null, slider = document.getElementById('handstep') as HTMLInputElement | null;
  const tools = document.querySelector<HTMLElement>('#handpanel .handtools'), runs = handRuns();
  if (!el || !tools || !pick || !slider) return;
  if (!runs.length) {
    tools.hidden = true;
    el.innerHTML = `<div class="${emptyCls()}">no voyage at this size has per-head Nevermore scores yet; they arrive with the queue (every 250 steps) and <span class="mono">scripts/score_nevermore.sh</span></div>`;
    return;
  }
  tools.hidden = false;
  const ids = runs.map((x: any) => x.run_id).join(',');
  if (pick.dataset.ids !== ids) {
    pick.innerHTML = [...runs].reverse().map((x: any) => `<option value="${esc(x.run_id)}">${esc(x.ship || x.name)} · ${esc(x.name)}</option>`).join('');
    pick.dataset.ids = ids;
  }
  if (!runs.some((x: any) => x.run_id === hand.run)) hand.run = runs[runs.length - 1].run_id;
  pick.value = hand.run || '';
  const run = runs.find((x: any) => x.run_id === hand.run), hs = run.hands, last = hs.length - 1;
  const i = hand.idx == null ? last : Math.min(hand.idx, last);
  slider.max = String(last); slider.value = String(i); slider.disabled = last === 0;
  const label = document.getElementById('handlabel');
  if (label) label.textContent = `step ${hs[i].step} · reading ${i + 1} of ${hs.length}${hand.idx == null ? ' (latest, live)' : ''}`;
  renderHand(el, hs[i], wpData.nevermore_threshold, prevIdx != null ? hs[prevIdx] : null);
}
function stopDeal(): void { window.clearInterval(hand.timer); hand.timer = 0; const b = document.getElementById('handplay'); if (b) b.textContent = '▶ play'; }

function wireHand(): void {
  const pick = document.getElementById('handrun') as HTMLSelectElement | null;
  const slider = document.getElementById('handstep') as HTMLInputElement | null;
  const play = document.getElementById('handplay');
  if (pick) pick.onchange = () => { stopDeal(); hand.run = pick.value; hand.idx = null; drawHand(); };
  if (slider) slider.oninput = () => {
    stopDeal();
    const run = handRuns().find((x: any) => x.run_id === hand.run);
    if (!run) return;
    const was = hand.idx ?? run.hands.length - 1, v = +slider.value;
    hand.idx = v >= run.hands.length - 1 ? null : v;
    drawHand(v > was ? was : null);
  };
  if (play) play.onclick = () => {
    if (hand.timer) { stopDeal(); return; }
    const run = handRuns().find((x: any) => x.run_id === hand.run);
    if (!run) return;
    hand.idx = 0; drawHand();
    play.textContent = '❚❚ pause';
    hand.timer = window.setInterval(() => {
      const last = run.hands.length - 1, was = hand.idx;
      if (was == null || was >= last) { hand.idx = null; stopDeal(); drawHand(); return; }
      hand.idx = was + 1; drawHand(was);
    }, 900);
  };
}
async function renderWaypoints(r: Payload, ladder: Ladder): Promise<void> {
  const { info } = await import('../../lib/info');
  const { runCells } = await import('./scoring');
  let d: Payload;
  try { d = await api('/api/waypoints?preset=' + encodeURIComponent(r.preset) + '&limit=' + RECENT); } catch { return; }
  const key = JSON.stringify(d);
  if (key === wpKey) return;
  wpKey = key; wpData = d;
  drawHand();
  wireHand();
  const passage = document.getElementById('readpassage'); if (passage) passage.dataset.book = d.natural_book;
  const thr = d.nevermore_threshold, found = d.trait_found, margin = d.trait_margin, core = d.core_traits;
  const stepCell = (v: number | null | undefined) => v === undefined ? '<td>–</td>' : v === null ? '<td data-sort="">not yet</td>' : `<td data-sort="${v}">step ${v}</td>`;
  const traitAt = (t: any) => {
    if (!t || !t.best) return { found: undefined, learned: undefined };
    const fl = (i: number) => Math.max(...['floor_bow', 'floor_init'].map((k) => (t[k] && t[k].value[t[k].step.indexOf(t.best.step[i])]) ?? -Infinity));
    const hasFloors = t.floor_bow || t.floor_init;
    const fi = t.best.value.findIndex((v: number) => v >= found);
    const li = hasFloors ? t.best.value.findIndex((v: number, i: number) => v >= found && v - fl(i) >= margin) : -2;
    return { found: fi < 0 ? null : t.best.step[fi], learned: li === -2 ? undefined : li < 0 ? null : t.best.step[li] };
  };
  const headEl = document.querySelector('#waypointtable thead');
  if (headEl) headEl.innerHTML = `<tr><th>ship</th><th>name</th><th>status</th><th>Nevermore formed</th>
    <th>real prose best${info('nevermore')}</th><th>random best${info('nevermore')}</th><th>Nevermores (real / random)</th><th>where</th><th>hand</th><th>copy gain${info('copygain')}</th>
    ${core.map((t: string) => `<th>${TRAIT_LABEL[t] || t} found</th><th>${TRAIT_LABEL[t] || t} learned</th>`).join('')}<th>language families found</th></tr>`;
  const bodyEl = document.querySelector('#waypointtable tbody');
  if (bodyEl) bodyEl.innerHTML = d.runs.length ? d.runs.map((x: any) => {
    const nv = x.nevermore, fams = Object.keys(x.traits).filter((t) => t.startsWith('family/'));
    const famFound = fams.filter((t) => traitAt(x.traits[t]).found != null).length;
    const a = firstAt(nv.natural_max_score, (v: number) => v >= thr), b = firstAt(nv.max_score, (v: number) => v >= thr);
    const formed = a === undefined && b === undefined ? undefined : [a, b].filter((v) => v != null).sort((p, q) => (p as number) - (q as number))[0] ?? null;
    const L = lastOf(nv.natural_best_layer), H = lastOf(nv.natural_best_head);
    const count = (k: string) => lastOf(nv[k]) == null ? '–' : String(Math.round(lastOf(nv[k])));
    return `<tr>${runCells(x)}${stepCell(formed)}<td>${fmt(lastOf(nv.natural_max_score), 3)}</td><td>${fmt(lastOf(nv.max_score), 3)}</td>
      <td>${nv.natural_count || nv.count ? `${count('natural_count')} / ${count('count')}` : '–'}</td>
      <td>${L == null ? '–' : `layer ${Math.round(L)}, head ${Math.round(H)}`}</td><td>${miniHand(x.hands && x.hands[x.hands.length - 1], thr)}</td>
      <td>${fmt(lastOf(nv.natural_copy_gain) ?? lastOf(nv.copy_gain), 2)}</td>
      ${core.map((t: string) => { const q = traitAt(x.traits[t]); return stepCell(q.found) + stepCell(q.learned); }).join('')}
      <td>${fams.length ? `${famFound} of ${fams.length}` : '–'}</td></tr>`;
  }).join('') : `<tr><td colspan="${11 + 2 * core.length}" class="${emptyCls(true)}">no voyages at ${esc(r.preset)} yet</td></tr>`;
  const { plot, layout, C, PALETTE, empty } = await chart();
  const recent = d.runs.slice(-12);
  const lines = (pick: (x: any) => any, id: string, title: string, msg: string, extra: any = {}) => {
    const rs = recent.filter((x: any) => pick(x) && pick(x).step.length);
    if (!rs.length) return empty(id, msg);
    plot(id, rs.map((x: any, i: number) => ({ type: 'scatter', mode: 'lines+markers', name: x.ship || x.name, x: pick(x).step, y: pick(x).value,
      line: { color: PALETTE[i % PALETTE.length], width: 1.5 }, marker: { size: 4 } })),
      layout({ xaxis: { title: 'step', gridcolor: C.line }, yaxis: { title, gridcolor: C.line }, ...extra }));
  };
  const hline = (y: number) => ({ shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color: C.accent, dash: 'dot' } }] });
  const nvMsg = `no voyage at ${esc(r.preset)} has Nevermore scores on the ledger yet: queued voyages record them every 250 steps, loop voyages at their last step, and <span class="mono">scripts/score_nevermore.sh</span> scores every finished 1m and 9m voyage once. First test readings: none formed anywhere yet; Smaller Pieces (9m, vocabulary 4,096) has one forming in its top layer, 0.12 on real prose`;
  lines((x: any) => x.nevermore.natural_max_score || x.nevermore.max_score, 'nvchart', 'Nevermore score', nvMsg, { ...hline(thr), yaxis: { title: 'Nevermore score', gridcolor: C.line, range: [0, 1] } });
  lines((x: any) => x.nevermore.natural_copy_gain || x.nevermore.copy_gain, 'copychart', 'nats per token', nvMsg);
  for (const t of core) lines((x: any) => x.traits[t] && x.traits[t].best, 'trait-' + t, 'held-out AUC',
    `no voyage at ${esc(r.preset)} has trait probes yet; add <span class="mono">probes</span> to eval.evaluators`, { ...hline(found), showlegend: false });
  void (async () => {
    try {
      const { stagesFor, common, band } = await import('../../lib/stages');
      const m = await stagesFor(recent.map((x: any) => x.run_id));
      band('#rung', common(m));
    } catch { /* stage bands are an overlay */ }
  })();
  document.querySelectorAll<HTMLElement>('[data-essay]').forEach((b) => {
    b.onclick = () => { void import('../../lib/reader').then((m) => m.openEssay(b.dataset.essay!)); };
  });
  const rp = document.getElementById('readpassage');
  if (rp) rp.onclick = () => { if (rp.dataset.book) void import('../../lib/reader').then((m) => m.openBook(rp.dataset.book!)); };
  void ladder;
}

// ---- the scoring boards ---------------------------------------------------------------------------
async function drawScience(r: Payload, runs: any[], capped: boolean): Promise<void> {
  const { info } = await import('../../lib/info');
  const { ART, LAW_COLS, SPLIT_LABEL, metricRows, runCells } = await import('./scoring');
  const none = (n: number) => `<tr><td colspan="${n}" class="${emptyCls(true)}">no voyages at ${esc(r.preset)} yet</td></tr>`;
  const sm = document.querySelector('#sciencemetrics tbody'); if (sm) sm.innerHTML = metricRows((r.metrics || []).filter((m: any) => !ART.has(m[0])));
  const am = document.querySelector('#artmetrics tbody'); if (am) am.innerHTML = metricRows((r.metrics || []).filter((m: any) => ART.has(m[0])));
  const sh = document.querySelector('#scienceboard thead');
  if (sh) sh.innerHTML = `<tr><th>ship</th><th>name</th><th>status</th><th>Forgotten Tomes${info('ft')}</th>
    <th>held-out bpb (en)${info('bpb')}</th>${Object.entries(SPLIT_LABEL).map(([k, l]) => `<th>${l}${info(k)}</th>`).join('')}</tr>`;
  const sb = document.querySelector('#scienceboard tbody');
  if (sb) sb.innerHTML = runs.length ? runs.map((x: any) => `<tr>${runCells(x)}<td>${fmt(x.ft_en)}</td><td>${fmt(x.bpb_en)}</td>
    ${Object.keys(SPLIT_LABEL).map((c) => `<td>${fmt(x.split[c])}</td>`).join('')}</tr>`).join('') : none(10);
  const cell = (m: number | null, ref: number | null, dg: number) => m == null ? '–' : `${fmt(m, dg)}${ref == null ? '' : ` <span class="s">/ ${fmt(ref, dg)}</span>`}`;
  const ah = document.querySelector('#artboard thead');
  if (ah) ah.innerHTML = `<tr><th>ship</th><th>name</th><th>status</th>${LAW_COLS.map((c) => `<th>${c[1]}${info(c[0])}<br><span class="s">model / ref</span>${info('modelref')}</th>`).join('')}</tr>`;
  const ab = document.querySelector('#artboard tbody');
  if (ab) ab.innerHTML = runs.length ? runs.map((x: any) => `<tr>${runCells(x)}
    ${LAW_COLS.map(([k, , dg]) => `<td>${cell(x.laws[k], x.ref[k], dg)}</td>`).join('')}</tr>`).join('') : none(3 + LAW_COLS.length);
  const { plot, layout, C, PALETTE, empty } = await chart();
  const split = runs.filter((x: any) => Object.values(x.split).some((v) => v != null));
  if (!split.length) empty('splitchart', runs.length ? 'the split arrives when scripts/queue_9m.sh re-scores the finished voyages, after tonight\'s pool voyages' : 'no voyages at this size yet');
  else plot('splitchart', split.map((x: any, i: number) => ({ type: 'bar', name: x.ship || x.name, x: Object.values(SPLIT_LABEL),
    y: Object.keys(SPLIT_LABEL).map((c) => x.split[c]), marker: { color: PALETTE[i % PALETTE.length] } })),
    layout({ barmode: 'group', yaxis: { title: 'bits per byte', gridcolor: C.line } }));
  const ratioKeys = LAW_COLS.filter((c) => !c[0].endsWith('_js'));
  const laws = runs.filter((x: any) => Object.values(x.laws).some((v) => v != null));
  if (!laws.length) empty('lawchart', runs.length ? 'the laws arrive with the same re-score' : 'no voyages at this size yet');
  else plot('lawchart', laws.map((x: any, i: number) => ({ type: 'bar', name: x.ship || x.name, x: ratioKeys.map((c) => c[1]),
    y: ratioKeys.map(([k]) => x.laws[k] != null && x.ref[k] ? x.laws[k] / x.ref[k] : null), marker: { color: PALETTE[i % PALETTE.length] } })),
    layout({ barmode: 'group', yaxis: { title: 'model ÷ books', gridcolor: C.line },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: C.accent, dash: 'dot' } }] }));
}

let scoreKey = '';
async function drawScoreLive(r: Payload): Promise<void> {
  const tb = document.querySelector('#sciencemetrics tbody'); if (!tb) return;
  tb.querySelectorAll('tr').forEach((tr) => { if ((tr as HTMLTableRowElement).cells.length < 5) (tr as HTMLTableRowElement).insertCell(-1).className = 'scorenow'; });
  let d: Payload; try { d = await api('/api/class_score?preset=' + encodeURIComponent(r.preset)); } catch { return; }
  const key = JSON.stringify(d); if (key === scoreKey) return; scoreKey = key;
  const head = document.getElementById('scorenowhead'); if (head) head.innerHTML = d.version ? `now <span class="s">${esc(d.version)}</span>` : 'now';
  const cell = (name: string) => { const tr = [...(tb as HTMLTableSectionElement).rows].find((x: HTMLTableRowElement) => (x.cells[0].innerText || '').trim().toLowerCase() === name); return tr && tr.cells[4]; };
  const minis = (c: any) => minicards(c || {});
  const census = d.census ? (d.census.written ? (d.census.held != null ? `<div class="s">best cards held in the census: ${d.census.held} of 4, by ${esc(d.census.variation)}</div>` : '<div class="s">the census has no readings yet</div>') : '<div class="s">the census around its fitout has not landed yet</div>') : '';
  const c1 = cell('cards held');
  if (c1) c1.innerHTML = d.version ? `${minis(d.cards)} <b>${d.held} of 4</b>${census}` : `<span class="s">no version yet</span>${census}`;
  const c2 = cell('cause and effect');
  if (c2) c2.innerHTML = d.version ? causeCell(d.cause) : '<span class="s">no version yet</span>';
  const c3 = cell('chaining two facts');
  if (c3) c3.innerHTML = d.version ? `<span class="${d.chaining != null && d.chaining > 0.03 ? 'good' : 's'}" title="the mean lift on the four chaining tests; above 0.03 it leaves the noise">${d.chaining != null ? signed(d.chaining) : '–'}</span>${d.chaining != null && d.chaining <= 0.03 ? ' <span class="s">in the noise</span>' : ''}` : '<span class="s">no version yet</span>';
  if (d.ship_key && c1) c1.insertAdjacentHTML('beforeend', `<div class="s"><a href="/leaderboard/thorp/${encodeURIComponent(d.ship_key)}">${esc(d.version)}'s hand →</a></div>`);
}

let tomesKey = '';
async function drawTomes(r: Payload, allRuns: any[], ladder: Ladder): Promise<void> {
  const { info } = await import('../../lib/info');
  const scored = allRuns.filter((x: any) => x.ft_en != null);
  const best = [...scored].sort((a: any, b: any) => a.ft_en - b.ft_en)[0];
  const pick = [...new Set([best, ...scored.slice(-4)].filter(Boolean).map((x: any) => x.ship || x.name))] as string[];
  const key = [r.preset, pick.join(','), Math.floor(Date.now() / 60000)].join('|');
  if (key === tomesKey) return;
  tomesKey = key;
  const head = document.querySelector('#tomestable thead'), body = document.querySelector('#tomestable tbody');
  if (!head || !body) return;
  let tomesData: Payload;
  try { tomesData = await api('/api/tomes'); } catch { body.innerHTML = `<tr><td class="${emptyCls(true)}">could not load the deck</td></tr>`; return; }
  if (!tomesData || !tomesData.scores || !tomesData.books) { body.innerHTML = `<tr><td class="${emptyCls(true)}">could not load the deck</td></tr>`; return; }
  const outside = Object.keys(tomesData.scores).filter((k) => !(ladder.runs || []).some((x: any) => (x.ship || x.name) === k));
  const cols = [...pick.filter((k) => tomesData.scores[k]), ...outside];
  const label = (c: string) => c === (best && (best.ship || best.name)) ? `${esc(c)} <span class="${pillCls('good')}">best</span>` : esc(c);
  head.innerHTML = `<tr><th>title</th><th>author</th><th>released</th><th>size</th>${cols.map((c) => `<th>${label(c)}${info('ft')}</th>`).join('')}</tr>`;
  body.innerHTML = tomesData.books.map((b: any) => `<tr data-book="${b.book_id}"><td>${esc(b.title)}</td><td>${esc(b.author)}</td><td>${esc(b.released)}</td>
    <td>${fmtBytes(b.bytes)}</td>${cols.map((c) => `<td>${fmt(tomesData.scores[c][b.book_id])}</td>`).join('')}</tr>`).join('');
}

async function drawCalibration(r: Payload, ladder: Ladder, allRuns: any[]): Promise<void> {
  const tb = document.querySelector('#caltable tbody'); if (!tb) return;
  const big9 = (ladder.runs || []).filter((x: any) => x.preset === ladder.rungs.find((q: any) => q.kind !== 'proxy').preset);
  const pairs = allRuns.map((p: any) => ({ p, n: big9.find((n: any) => n.recipe === p.recipe && n.passes === p.passes && n.seed === p.seed && n.status === 'finished') })).filter((x: any) => x.n);
  tb.innerHTML = pairs.map(({ p, n }: any) => `<tr><td>${esc((p.recipe || '').replace('lists/', '').replace('.csv', ''))}</td>
    <td>${p.passes ?? '–'}</td><td>${n ? esc(n.ship || n.name) : '–'}</td><td>${fmt(n && n.ft_en)}</td><td>${esc(p.ship || p.name)}</td><td>${fmt(p.ft_en)}</td></tr>`).join('');
  const both = pairs.filter(({ p, n }: any) => n && n.ft_en != null && p.ft_en != null);
  const rank = (a: number[]) => a.map((v) => a.filter((w) => w < v).length);
  let verdict = `${both.length} of ${pairs.length} libraries scored at both sizes.`;
  if (both.length >= 3) {
    const a = rank(both.map((x: any) => x.n.ft_en)), b = rank(both.map((x: any) => x.p.ft_en)), k = a.length;
    const rho = 1 - 6 * a.reduce((s: number, v: number, i: number) => s + (v - b[i]) ** 2, 0) / (k * (k * k - 1));
    verdict += ` Rank agreement (Spearman) ${rho.toFixed(2)}: ${rho >= 0.8 ? 'the proxy orders the libraries as 9m does' : 'not yet trustworthy'}.`;
  } else verdict += ' Rank agreement needs at least three; the 9m voyages are re-scored on the Forgotten Tomes by the queue.';
  const cv = document.getElementById('calverdict'); if (cv) cv.textContent = verdict;
  const { plot, layout, C, empty } = await chart();
  if (!both.length) empty('calchart', 'points appear when a library has a Forgotten Tomes score at both sizes');
  else plot('calchart', [{ type: 'scatter', mode: 'markers+text', x: both.map((x: any) => x.n.ft_en), y: both.map((x: any) => x.p.ft_en),
    text: both.map((x: any) => x.n.ship || x.n.name), textposition: 'top center', marker: { size: 10, color: C.accent } }],
    layout({ xaxis: { title: '9m score', gridcolor: C.line }, yaxis: { title: '1m score', gridcolor: C.line } }));
  void r;
}

// ---- the scoring sub-pages ------------------------------------------------------------------------
let subjData: Payload = null, subjAt = 0, subjPreset = '';
async function classSubject(r: Payload, key: string): Promise<void> {
  const el = document.getElementById('subj-' + key); if (!el) return;
  if (!subjData || subjPreset !== r.preset || Date.now() - subjAt > 60000) {
    try { subjData = await api(`/api/class_subjects?preset=${encodeURIComponent(r.preset)}`); subjAt = Date.now(); subjPreset = r.preset; }
    catch { el.innerHTML = `<div class="${emptyCls()}">the tests could not be read</div>`; return; }
  }
  const S = subjData.subjects[key]; if (!S) return;
  const about = document.getElementById(`subj-${key}-about`); if (about) about.textContent = S.about;
  const short = (n: string) => n.replace('fu-ogden-v0-1', 'Ogden').replace('-pre', '');
  const tests = [...S.tests].sort((a: any, b: any) => (b.mine - a.mine));
  const vs = subjData.voyages;
  const cell = (rd: any) => rd.value == null ? '<td class="s">–</td>' : `<td class="${rd.passed ? 'pass' : ''}" title="score ${rd.score == null ? '–' : rd.score.toFixed(2)} at step ${rd.step}">${rd.value >= 0 ? '+' : ''}${rd.value.toFixed(2)}${rd.passed ? ' ✓' : ''}</td>`;
  const mine = tests.filter((t: any) => t.mine);
  const relLinks = key === 'logic' ? `<p class="lgnav">The logic deck's five relations, each in detail: ${['order', 'cause', 'membership', 'proportion', 'counterfactual'].map((x) => `<a href="${modelHref(r, 'overview', 'logic-' + x)}">${x}</a>`).join(' · ')}</p>` : '';
  el.innerHTML = relLinks + `<p class="s">${mine.length ? `This size's own step${mine.length > 1 ? 's' : ''} on this track: <b>${mine.map((t: any) => esc(t.name)).join(', ')}</b>. The others are other classes' goals, shown for where it stands on the way up.` : `This size has no step of its own on this track; the readings show where it stands.`} A test passes when its lift (the true answer's share over the floor) reaches its mark; each test has only a few dozen items, so seeds differ.</p>
    <div class="scroll"><table class="subjtable"><thead><tr><th>test</th><th>whose step</th><th>mark</th>${vs.map((v: string) => `<th class="mono" title="${esc(v)}">${esc(short(v))}</th>`).join('')}</tr></thead>
    <tbody>${tests.map((t: any) => `<tr${t.mine ? ' class="mine"' : ''}><td title="${esc(t.about)}"><b>${esc(t.name)}</b><div class="s">${esc(t.about.slice(0, 140))}${t.about.length > 140 ? '…' : ''}</div></td>
      <td>${t.goal_class ? esc(t.goal_class) : '<span class="s">the explorer</span>'}${t.mine ? ' <b>(this size)</b>' : ''}</td><td>≥ ${t.threshold}</td>${t.readings.map(cell).join('')}</tr>`).join('')}</tbody></table></div>
    <div class="chart" id="subjchart-${key}"></div>`;
  const { plot, layout, C, PALETTE } = await chart();
  const traces: any[] = [];
  mine.forEach((t: any) => t.readings.forEach((rd: any) => { if (rd.series && rd.series.length) traces.push({ type: 'scatter', mode: 'lines', name: `${t.name} · ${short(rd.voyage)}`, x: rd.series.map((p: any) => p[0] / 1e6), y: rd.series.map((p: any) => p[1]), line: { color: PALETTE[traces.length % PALETTE.length] } }); }));
  if (traces.length) plot(`subjchart-${key}`, traces, layout({ xaxis: { title: 'tokens read (millions)', gridcolor: C.line }, yaxis: { title: 'lift', gridcolor: C.line, zeroline: true },
    shapes: mine.map((t: any) => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: t.threshold, y1: t.threshold, line: { color: C.accent, dash: 'dot' } })) }));
  else { const e = document.getElementById(`subjchart-${key}`); if (e) e.innerHTML = `<div class="${emptyCls()}">no voyage of this size has read its own step on this track yet</div>`; }
}

let vsRef: string | null = null, vsVoyage: string | null = null, vsPreset = '';
async function classVersus(r: Payload, path: string): Promise<void> {
  const body = document.getElementById('vsbody'); if (!body) return;
  if (vsPreset !== r.preset) { vsPreset = r.preset; vsVoyage = null; body.innerHTML = `<div class="${emptyCls()}">reading…</div>`; const p = document.getElementById('vspick'); if (p) p.innerHTML = ''; }
  const asked = r.preset;
  try { vsRef = vsRef || localStorage.getItem('thorp.vs.ref'); } catch { /* blocked */ }
  const q = `preset=${encodeURIComponent(r.preset)}${vsRef ? `&ref=${encodeURIComponent(vsRef)}` : ''}${vsVoyage ? `&voyage=${encodeURIComponent(vsVoyage)}` : ''}`;
  let d: Payload; try { d = await api(`/api/class_vs?${q}`); } catch { body.innerHTML = `<div class="${emptyCls()}">the comparison could not be read (a dashboard server started before it existed has to be restarted)</div>`; return; }
  if (asked !== vsPreset) return;
  const short = (n: string) => (n || '').replace('fu-ogden-v0-1', 'Ogden').replace('-pre', '');
  const refName = (n: string) => (n || '').split('/').pop();
  const pick = document.getElementById('vspick');
  if (pick) pick.innerHTML = `<label class="s">voyage <select id="vsvoyage">${d.voyages.map((v: string) => `<option value="${esc(v)}"${v === d.voyage ? ' selected' : ''}>${esc(short(v))}</option>`).join('')}</select></label>
    <label class="s">against <select id="vsref">${d.refs.map((x: string) => `<option value="${esc(x)}"${x === d.ref ? ' selected' : ''}>${esc(refName(x))}</option>`).join('')}</select></label>`;
  const vsel = document.getElementById('vsvoyage') as HTMLSelectElement | null, rsel = document.getElementById('vsref') as HTMLSelectElement | null;
  if (vsel) vsel.onchange = () => { vsVoyage = vsel.value; void classVersus(r, path); };
  if (rsel) rsel.onchange = () => { vsRef = rsel.value; try { localStorage.setItem('thorp.vs.ref', vsRef!); } catch { /* blocked */ } void classVersus(r, path); };
  if (!d.voyage) { body.innerHTML = `<div class="${emptyCls()}">no voyage of this size has read the trick tests yet</div>`; return; }
  const by = Object.fromEntries(d.rows.map((x: any) => [x.key, x]));
  const val = (x: any, v: number | null) => v == null ? '–' : x.unit === 'pairs of 24' ? `${v}/24` : x.unit === 'cards' ? `${v} of 16` : v.toFixed(x.unit === 'bits a byte' ? 3 : 2);
  const pct = (s: number | null) => s == null ? '–' : `${Math.round(100 * s)}%`;
  const tag = (x: any) => x.noise ? ' <span class="s" title="within the test\'s noise: two pairs of 24, or 0.05 nats">≈ noise</span>' : '';
  const card = (keys: string[], title: string, sub: string) => `<div class="vscol"><h3>${title} <span class="s">${sub}</span></h3><ol class="vslist">${keys.map((k) => { const x = by[k];
      return `<li><b>${esc(x.name)}</b>${tag(x)}<div class="vsnums"><span class="vsme">${val(x, x.mine)}</span> <span class="s">against</span> <span>${val(x, x.ref)}</span> <span class="vsshare ${x.share >= 1 ? 'ahead' : x.share < 0.25 ? 'far' : ''}">${pct(x.share)} of ${esc(refName(d.ref))}</span></div><div class="s">${esc(x.about.slice(0, 120))}${x.about.length > 120 ? '…' : ''}${x.note ? ` · ${esc(x.note)}` : ''}</div></li>`; }).join('')}</ol></div>`;
  const groups = ['language', 'card', 'logic deck', 'trick test'];
  const rows = [...d.rows].sort((a: any, b: any) => groups.indexOf(a.group) - groups.indexOf(b.group) || ((b.share ?? -9) - (a.share ?? -9)));
  body.innerHTML = `<p class="s"><span class="mono">${esc(short(d.voyage))}</span> ${d.status === 'running' ? `at sea, step ${(d.step || 0).toLocaleString()} of ${d.total_steps ? Math.round(d.total_steps).toLocaleString() : '–'}` : 'home'}, against ${esc(refName(d.ref))}. The share is how much of the reference's level this voyage reaches: for a trick test, pairs right above chance (12 of 24) over the reference's; for a lift or a card, ours over theirs; for bits per byte, theirs over ours. Above 100% is ahead. A trick test has 24 pairs, so two pairs either way is noise.</p>
    <div class="vsgrid">${card(d.closer, 'Closest', 'or ahead')}${card(d.further, 'Furthest away', '')}</div>
    <h3>Every reading</h3><div class="scroll"><table class="subjtable"><thead><tr><th>reading</th><th>kind</th><th>whose step</th><th>${esc(short(d.voyage))}</th><th>${esc(refName(d.ref))}</th><th>share</th></tr></thead><tbody>${rows.map((x: any) => `<tr><td><b>${esc(x.name)}</b>${tag(x)}${x.note ? `<div class="s">${esc(x.note)}</div>` : ''}</td><td class="s">${esc(x.group)}</td><td class="s">${esc(x.whose || '')}</td><td>${val(x, x.mine)}</td><td>${val(x, x.ref)}</td><td><span class="vsshare ${x.share >= 1 ? 'ahead' : x.share != null && x.share < 0.25 ? 'far' : ''}">${pct(x.share)}</span></td></tr>`).join('')}</tbody></table></div>`;
}

async function classShapes(r: Payload): Promise<void> {
  const el = document.getElementById('shapesmass'); if (!el) return;
  let d: Payload; try { d = await api(`/api/class_shapes?preset=${encodeURIComponent(r.preset)}`); } catch { el.innerHTML = `<div class="${emptyCls()}">the shapes could not be read</div>`; return; }
  const { plot, layout, C, PALETTE, empty } = await chart();
  if (!d.voyages.length) { empty('shapeschart', 'no voyage of this size carries the shapes readings yet'); el.innerHTML = ''; return; }
  const short = (n: string) => n.replace('fu-ogden-v0-1', 'Ogden').replace('-pre', '');
  const names: Record<string, string> = { 'shapes/upos_top1': 'part of speech', 'shapes/ogden_top1': 'Ogden kind', 'shapes/keyed_top1': 'keyed word' };
  const dash: Record<string, string> = { 'shapes/upos_top1': 'solid', 'shapes/ogden_top1': 'dot', 'shapes/keyed_top1': 'dash' };
  const traces: any[] = [];
  d.voyages.forEach((v: any, i: number) => Object.keys(names).forEach((m) => { const s = v.series[m] || []; if (s.length) traces.push({ type: 'scatter', mode: 'lines', name: `${names[m]} · ${short(v.voyage)}`, x: s.map((p: any) => p[0] / 1e6), y: s.map((p: any) => p[1]), line: { color: PALETTE[i % PALETTE.length], dash: dash[m] } }); }));
  plot('shapeschart', traces, layout({ xaxis: { title: 'tokens read (millions)', gridcolor: C.line }, yaxis: { title: 'top guess right', tickformat: '.0%', gridcolor: C.line } }));
  const v = d.voyages[0];
  const pct = (x: number | null) => x == null ? '–' : `${Math.round(100 * x)}%`;
  el.innerHTML = `<h3>What kind of word it expects <span class="s">${esc(short(v.voyage))}, its latest reading: its probability on each kind of word against the judge books' own share</span></h3>
    <div class="scroll"><table class="subjtable"><thead><tr><th>kind of word</th><th>expects</th><th>the text holds</th><th></th></tr></thead><tbody>${d.fine.filter((t: string) => (v.truth[t] || 0) > 0.004 || (v.mass[t] || 0) > 0.004).map((t: string) => {
      const m = v.mass[t] || 0, h = v.truth[t] || 0, gap = m - h;
      return `<tr><td><b>${esc(t)}</b> <span class="s">${esc(d.about[t] || '')}</span></td><td>${pct(m)}</td><td>${pct(h)}</td><td class="s">${Math.abs(gap) < 0.02 ? 'about right' : gap > 0 ? 'over-expects' : 'under-expects'}</td></tr>`; }).join('')}</tbody></table></div>`;
}

// ---- Ask the best version -------------------------------------------------------------------------
let askWired = false, askPreset = '', askBest: Payload = null, askQuestions: any[] = ASK_QUESTIONS, askSet = 'world', classQuestions: Payload = null, logicQuestions: any[] | null = null;
async function askPanel(r: Payload, ladder: Ladder): Promise<void> {
  const who = document.getElementById('askwho'), sel = document.getElementById('askvoyage') as HTMLSelectElement | null;
  if (!who || !sel) return;
  if (askPreset !== r.preset) {
    askPreset = r.preset; askBest = null; who.innerHTML = `<span class="s">finding the best ${esc(r.preset)}…</span>`; sel.innerHTML = '';
    ['askguess', 'askanswer', 'askall'].forEach((id) => { const b = document.getElementById(id) as HTMLButtonElement | null; if (b) b.disabled = true; });
    const out = document.getElementById('askout'); if (out) out.innerHTML = '';
    let d: Payload; try { d = await api(`/api/class_best?preset=${encodeURIComponent(r.preset)}`); } catch { who.textContent = 'the best version could not be read'; return; }
    askBest = d.best;
    const b = d.best;
    who.innerHTML = b ? `Talking to ${b.name && b.name !== b.ship ? `<b>${esc(b.name)}</b> · ` : ''}<a href="${shipHash(b.ship_key)}">${b.name && b.name !== b.ship ? esc(b.ship) : `<b>${esc(b.ship)}</b>`}</a> · ${b.sailings} voyage${b.sailings === 1 ? '' : 's'}${b.objective ? ` · <b>${esc(b.objective.label)}</b> ${(100 * b.objective.value).toFixed(1)}%` : ''}${b.chaining_lift != null ? ` · chaining lift ${b.chaining_lift >= 0 ? '+' : ''}${b.chaining_lift.toFixed(3)}` : ''}<div class="s">${esc(b.why)}</div>`
      : `<span class="s">the leaderboard has no best ${esc(r.preset)} yet: pick a voyage</span>`;
    const best = b ? b.runs : [];
    sel.innerHTML = (best.length ? `<optgroup label="the best version">${best.map((n: string) => `<option value="${esc(n)}">${esc(n)}</option>`).join('')}</optgroup>` : '')
      + `<optgroup label="every finished voyage of this size">${d.voyages.filter((v: any) => !best.includes(v.name)).map((v: any) => `<option value="${esc(v.name)}">${esc(v.name)}</option>`).join('')}</optgroup>`;
    if (b && b.run) sel.value = b.run;
    ['askguess', 'askanswer', 'askall'].forEach((id) => { const el = document.getElementById(id) as HTMLButtonElement | null; if (el) el.disabled = !sel.value; });
    try {
      const q = await api(`/api/ask_questions?preset=${encodeURIComponent(r.preset)}`);
      classQuestions = q.questions.length ? q : null;
      logicQuestions = (q.logic || []).length ? q.logic : null;
    } catch { classQuestions = null; logicQuestions = null; }
    askSet = classQuestions ? 'class' : 'world';
  }
  askQuestions = askSet === 'logic' && logicQuestions ? logicQuestions : askSet === 'class' && classQuestions ? classQuestions.questions : ASK_QUESTIONS;
  const chips = document.getElementById('askchips');
  if (chips) chips.innerHTML = (classQuestions ? `<div class="askset"><button type="button" class="askchip${askSet === 'class' ? ' on' : ''}" data-set="class">its own size: ${classQuestions.words_back} word${classQuestions.words_back === 1 ? '' : 's'} back, from the Ogden corpus</button><button type="button" class="askchip${askSet === 'world' ? ' on' : ''}" data-set="world">world knowledge (beyond the keel)</button>${logicQuestions ? `<button type="button" class="askchip${askSet === 'logic' ? ' on' : ''}" data-set="logic" title="two items of each relation from the 40-item logic deck, on invented words: the premises force one answer, and the rival is the one they rule out">the logic deck: ${logicQuestions.length} chains, each against its rival</button>` : ''}</div>` : '')
    + askQuestions.map((q, i) => `<button type="button" class="askchip" data-i="${i}" title="${esc(q.about)}: we hope for “${esc(q.hope)}”">${esc(q.text.replace('\n', ' '))}</button>`).join('');
  if (askWired) return; askWired = true;
  const out = document.getElementById('askout')!, ta = document.getElementById('asktext') as HTMLTextAreaElement;
  const run = () => (document.getElementById('askvoyage') as HTMLSelectElement).value;
  const noVoyage = () => { if (run()) return false; out.innerHTML = `<div class="${emptyCls()}">no voyage chosen yet</div>`; return true; };
  const mode = () => ((document.getElementById('askmode') as HTMLSelectElement) || {}).value || '1';
  const guessesFor = (text: string) => api(`/api/table/guesses?run=${encodeURIComponent(run())}&k=10&mode=${mode()}&text=${encodeURIComponent(text)}`);
  const busy = (on: boolean) => ['askguess', 'askanswer', 'askall'].forEach((id) => { const el = document.getElementById(id) as HTMLButtonElement | null; if (el) el.disabled = on; });
  const guessTable = (g0: any, hope: string | null, rival: string | null) => {
    const carried = g0.mode !== 'pieces' ? g0.guesses.filter((x: any) => x.continues) : [];
    const g = { ...g0, guesses: g0.mode !== 'pieces' ? g0.guesses.filter((x: any) => !x.continues) : g0.guesses };
    const rank = hope ? hopeRank(g.guesses, hope) : null;
    const rrank = rival ? hopeRank(g.guesses, rival) : null;
    const verdict = rival ? ` · the rival “${esc(rival)}”: ${rrank ? `guess ${rrank}` : 'not in its ten'} · <b>${chose(rank, rrank)}</b>` : '';
    const note = carried.length ? `<div class="s carried">it may not take “${esc(carried[0].of)}” as finished: ${carried.slice(0, 3).map((x: any) => `“${esc(x.word)}” ${(100 * x.p).toFixed(1)}%`).join(', ')} (it carries your last word on: a prompt that stops on a word cannot say the word is finished)</div>` : '';
    return `${lookingFor(g)}<div class="s">${esc(g.run)} at step ${g.step} · ${g.seconds}s${hope ? ` · hoped for “${esc(hope)}”: ${rank ? `<b>guess ${rank}</b>` : '<b>not in its ten</b>'}` : ''}${verdict}</div>${note}
      <div class="guesses">${g.guesses.map((x: any, i: number) => `<div class="guess${hope && rank === i + 1 ? ' hit' : ''}"><span class="mono" title="${x.continues ? `carries on “${esc(x.of)}” with “${esc(x.piece)}”` : ''}">${x.continues ? `<span class="s">${esc(x.of)}→</span>${esc(x.word)}` : esc(x.piece === true ? showPiece(x.word) : x.word)}</span><i style="width:${Math.max(2, Math.round(100 * x.p))}%"></i><span class="s">${(100 * x.p).toFixed(1)}%</span>${x.tag ? `<span class="postag pos-${esc(x.coarse || '')}" title="${esc(x.tag)}: its commonest part of speech in the Ogden corpus">${esc(x.tag)}</span>` : ''}</div>`).join('')}</div>
      ${g.mode !== 'pieces' ? '<div class="s">the likeliest new words it reaches; the rest of the probability is words it rarely spells</div>' : ''}`;
  };
  const guess = async (text: string, hope: string | null, rival: string | null): Promise<void> => {
    if (!text.trim()) { out.innerHTML = `<div class="${emptyCls()}">type something first</div>`; return; }
    if (noVoyage()) return;
    busy(true); out.innerHTML = `<div class="${emptyCls()}">loading the voyage and reading its guesses (the first time a voyage loads takes a few seconds)…</div>`;
    try { out.innerHTML = guessTable(await guessesFor(text), hope, rival); } catch (e) { out.innerHTML = `<div class="${emptyCls()}">${esc(String((e as Error).message || e))}</div>`; }
    busy(false);
  };
  (document.getElementById('askguess') as HTMLButtonElement | null)?.addEventListener('click', () => { const q = askQuestions.find((x) => x.text === ta.value) || ({} as any); void guess(ta.value, q.hope, q.rival); });
  document.getElementById('askchips')?.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest('.askchip') as HTMLElement | null; if (!b) return;
    if (b.dataset.set) { askSet = b.dataset.set; void askPanel(r, ladder); return; }
    const q = askQuestions[+b.dataset.i!]; ta.value = q.text; void guess(q.text, q.hope, q.rival); });
  (document.getElementById('askanswer') as HTMLButtonElement | null)?.addEventListener('click', async () => {
    const q = ta.value.trim(); if (!q || noVoyage()) return;
    busy(true); out.innerHTML = `<div class="${emptyCls()}">it is answering…</div>`;
    try {
      const res = await fetch('/api/table/reply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run: run(), question: q, history: [], temperature: 0.8, max_tokens: 80 }) });
      const d = await res.json() as any; if (!res.ok || d.error) throw new Error(d.error || res.statusText);
      out.innerHTML = `<div class="s">${esc(run())} at step ${d.step} · ${d.tokens} pieces in ${d.seconds}s · kept in its Table Talk transcript</div><div class="askanswer">${esc(d.answer) || '<span class="s">(nothing)</span>'}</div>`;
    } catch (e) { out.innerHTML = `<div class="${emptyCls()}">${esc(String((e as Error).message || e))}</div>`; }
    busy(false);
  });
  (document.getElementById('askall') as HTMLButtonElement | null)?.addEventListener('click', async () => {
    if (noVoyage()) return;
    busy(true); const rows: any[] = [];
    const draw = () => {
      const hit = rows.filter((x) => x.rank).length, logic = askQuestions.some((q: any) => q.rival);
      const won = rows.filter((x) => x.q.rival && chose(x.rank, x.rrank) === 'the premises').length;
      out.innerHTML = `<div class="s">${esc(run())} · ${hit} of ${rows.length} hoped-for answers among its ten guesses${logic ? ` · <b>${won} of ${rows.length}</b> chains answered as the premises say, above the rival` : ''}${rows.length < askQuestions.length ? ' · reading…' : ''}</div>
        <div class="scroll"><table class="asktable"><thead><tr><th>question</th><th>about</th><th>hoped for</th><th>its rank</th>${logic ? '<th>the rival</th><th>its rank</th><th>it chose</th>' : ''}<th title="its ten guesses' probability summed by part of speech: what kind of word it expects next">looking for</th><th>its first three guesses</th></tr></thead><tbody>${rows.map((x) => `<tr${x.rank === 1 ? ' class="sel"' : ''}><td class="mono">${esc(x.q.text.replace('\n', ' '))}</td><td class="s">${esc(x.q.about)}</td><td>${esc(x.q.hope)}</td>
          <td>${x.err ? '<span class="s">failed</span>' : x.rank ? `<b>${x.rank}</b>` : '<span class="s">not in ten</span>'}</td>${logic ? `<td>${esc(x.q.rival || '')}</td><td>${x.err ? '' : x.rrank ? x.rrank : '<span class="s">not in ten</span>'}</td><td>${x.err ? '' : `<span class="${pillCls(chose(x.rank, x.rrank) === 'the premises' ? 'good' : chose(x.rank, x.rrank) === 'the rival' ? 'bad' : '')}">${chose(x.rank, x.rrank)}</span>`}</td>` : ''}<td>${x.g && x.g.looking_for ? x.g.looking_for.slice(0, 2).map((t: any) => `<span class="postag" title="${esc(t.about || '')}">${esc(t.tag)} ${Math.round(100 * t.share)}%</span>`).join(' ') : ''}</td><td class="mono">${x.g ? x.g.guesses.slice(0, 3).map((g: any) => `${esc(g.piece === true ? showPiece(g.word) : g.word)} <span class="s">${(100 * g.p).toFixed(0)}%</span>`).join(' · ') : ''}</td></tr>`).join('')}</tbody></table></div>`;
    };
    for (const q of askQuestions) {
      try { const g0 = await guessesFor(q.text); const g = { ...g0, guesses: g0.mode !== 'pieces' ? g0.guesses.filter((x: any) => !x.continues) : g0.guesses }; rows.push({ q, g, rank: hopeRank(g.guesses, q.hope), rrank: q.rival ? hopeRank(g.guesses, q.rival) : null }); } catch { rows.push({ q, err: true }); }
      draw();
    }
    busy(false);
  });
}

// ---- the maths book -------------------------------------------------------------------------------
let mathsData: Payload = null, mathsWired = false;
async function mathsBook(r: Payload, ladder: Ladder): Promise<void> {
  const sel = document.getElementById('mathsvoyage') as HTMLSelectElement | null, out = document.getElementById('mathsout');
  if (!sel || !out) return;
  if (!mathsData) { try { mathsData = await api('/api/maths_book'); } catch { out.innerHTML = `<div class="${emptyCls()}">the maths book could not be read (a dashboard started before it existed has to be restarted)</div>`; return; } }
  const sopSel = document.getElementById('mathssop') as HTMLSelectElement | null;
  const fill = (): void => {
    const runs = (ladder.runs || []).filter((x: any) => x.preset === r.preset && !(x.name || '').startsWith('smoke'));
    const vers = [...new Set(runs.map((x: any) => x.sop).filter(Boolean))].sort() as string[];
    if (sopSel) {
      const keep = sopSel.value;
      sopSel.innerHTML = `<option value="">all versions</option>` + vers.map((v) => `<option value="${esc(v)}">v${esc(v)}</option>`).join('');
      sopSel.value = vers.includes(keep) ? keep : '';
    }
    const want = sopSel ? sopSel.value : '';
    const sig = `${r.preset}|${want}`;
    if (sel.dataset.built === sig && sel.options.length) return;
    const mine = runs.filter((x: any) => !want || String(x.sop || '') === want);
    if (mine.length) {
      const was = sel.value;
      sel.innerHTML = mine.map((x: any) => `<option value="${esc(x.name)}">${esc(x.name)}${x.status === 'running' ? ' · at sea' : ''}</option>`).join('');
      if (mine.some((x: any) => x.name === was)) sel.value = was;
      sel.dataset.preset = r.preset;
      sel.dataset.built = sig;
      return;
    }
    const a = document.getElementById('askvoyage') as HTMLSelectElement | null;
    if (a && a.options.length && sel.dataset.preset !== r.preset) { sel.innerHTML = a.innerHTML; sel.value = a.value; sel.dataset.preset = r.preset; }
  };
  if (sopSel && !sopSel.onchange) sopSel.onchange = () => { sel.value = ''; sel.dataset.preset = ''; sel.dataset.built = ''; fill(); };
  fill();
  if (!sel.options.length) { let n = 0; const t = window.setInterval(() => { fill(); if (sel.options.length || ++n > 60) window.clearInterval(t); }, 1000); }
  if (!out.innerHTML) out.innerHTML = mathsIndex(mathsData);
  if (mathsWired) return; mathsWired = true;
  document.getElementById('mathspanel')?.addEventListener('click', (e) => {
    const b = (e.target as HTMLElement).closest('[data-mbook]') as HTMLElement | null;
    if (b) void import('../../lib/reader').then((m) => m.openBook(b.dataset.mbook!, +b.dataset.at! || 0));
  });
  document.getElementById('mathsrun')?.addEventListener('click', async () => {
    fill(); const run = sel.value; if (!run) { out.innerHTML = `<div class="${emptyCls()}">no voyage chosen yet</div>`; return; }
    const btn = document.getElementById('mathsrun') as HTMLButtonElement; btn.disabled = true;
    const res: Record<string, any[]> = {};
    const draw = (done: boolean) => { out.innerHTML = mathsTable(mathsData, run, res, done); };
    for (const c of mathsData.chapters) {
      res[c.n] = [];
      for (const q of c.sums) {
        try {
          const g0 = await api(`/api/table/guesses?run=${encodeURIComponent(run)}&k=10&mode=1&text=${encodeURIComponent(q.text)}`);
          const gs = g0.guesses.filter((x: any) => !x.continues);
          const rank = hopeRank(gs, q.hope), rrank = hopeRank(gs, q.rival);
          res[c.n].push({ q, rank, rrank, ok: chose(rank, rrank) === 'the premises', top: gs.slice(0, 3) });
        } catch { res[c.n].push({ q, err: true }); }
        draw(false);
      }
    }
    draw(true); btn.disabled = false;
  });
}

// ---- the Navigator's Wager ------------------------------------------------------------------------
let wagerData: Payload = null, wagerRound: string | null = null, wagerWired = false, wagerPreset = '';
async function classWager(r: Payload, path: string): Promise<void> {
  const el = document.getElementById('wagertable'); if (!el) return;
  if (wagerPreset !== r.preset) { wagerPreset = r.preset; wagerRound = null; }
  let d: Payload;
  try { d = await api(`/api/wager?preset=${encodeURIComponent(r.preset)}`); } catch (e) {
    const old = /not valid JSON|not found|404/i.test(String((e as Error).message || e));
    el.innerHTML = `<div class="${emptyCls()}">${old ? 'this dashboard server was started before the Bet tab existed, so it has no wager to give: restart it (<span class="mono">uv run --project backend thorp dash</span>) and reload' : 'the wager could not be read: ' + esc(String((e as Error).message || e))}</div>`; return;
  }
  wagerData = d;
  const csel = document.getElementById('wagercontrol') as HTMLSelectElement | null, lsel = document.getElementById('wagerlever') as HTMLSelectElement | null;
  if (csel && csel.options.length !== d.controls.length) csel.innerHTML = d.controls.map((c: string) => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
  if (lsel && lsel.options.length !== d.levers.length) lsel.innerHTML = d.levers.map((l: any) => `<option value="${esc(l.key)}">${esc(l.name)}</option>`).join('');
  const aboutEl = document.getElementById('wagerleverabout');
  const about = (): void => { const l = lsel ? d.levers.find((x: any) => x.key === lsel.value) : null; if (aboutEl) aboutEl.textContent = l ? l.about : ''; };
  about();
  if (!wagerRound || !d.rounds.find((x: any) => x.key === wagerRound)) {
    let saved: string | null = null; try { saved = localStorage.getItem('thorp.wager.' + r.preset); } catch { /* blocked */ }
    wagerRound = (d.rounds.find((x: any) => x.key === saved) || d.rounds.find((x: any) => x.open) || d.rounds[0] || {}).key || null;
  }
  const roundsEl = document.getElementById('wagerrounds');
  if (roundsEl) roundsEl.innerHTML = d.rounds.length ? d.rounds.map((x: any) => {
    const s = x.settled ? `${x.winner === 'navigator' ? 'you won' : 'the House won'} ${x.score.navigator}–${x.score.house}`
      : x.pull_voyage.status === 'at sea' ? 'at sea' : x.in_queue ? 'queued' : x.open ? 'open: bet, then queue' : x.pull_voyage.status;
    return `<button type="button" class="wround${x.key === wagerRound ? ' on' : ''}" data-round="${esc(x.key)}"><b>${esc(x.lever)}</b><span class="s">${esc(x.pull.replace('fu-ogden-v0-1', 'Ogden'))}</span><span class="wstate">${esc(s)}</span></button>`;
  }).join('') : `<div class="${emptyCls()}">no rounds yet: deal one above</div>`;
  const R = d.rounds.find((x: any) => x.key === wagerRound);
  const head = document.getElementById('wagerhead');
  if (!head) return;
  if (!R) { head.innerHTML = ''; el.innerHTML = ''; } else {
    const chips = R.cards.filter((c: any) => c.bet && !c.bet.practice).length;
    const canQueue = R.pull_voyage.status === 'queued' && !R.in_queue;
    head.innerHTML = `<div class="whead"><div><b>${esc(R.lever)}</b> · ${esc(R.about || '')}</div>
      <div class="s">control <span class="mono">${esc(R.control)}</span> (${esc(R.control_voyage.status)}) → pull <span class="mono">${esc(R.pull)}</span> (${esc(R.in_queue ? 'in the queue' : R.pull_voyage.status)})</div>
      <div class="wscore"><span>chips ${chips} of ${d.chips}</span>${R.settled ? `<span>you <b>${R.score.navigator}</b> · Claude <b>${R.score.claude}</b> · the House <b>${R.score.house}</b> · <b>${R.winner === 'navigator' ? 'you win' : 'the House wins'}</b></span>` : '<span class="s">the outcome shows when both voyages are home</span>'}
      ${canQueue ? `<button class="${btnCls('default')}" type="button" id="wagerqueue">Queue the experiment</button>` : ''}</div></div>`;
    const byKey = Object.fromEntries(d.deck.map((c: any) => [c.key, c]));
    const scanAbout = Object.fromEntries((d.scansions || []).map((s: any) => [s.key, `${s.name}: ${s.about}`]));
    el.innerHTML = d.constellations.map((k: any) => `<div class="wrow"><div class="wsuit"><span class="suit">${esc(k.suit)}</span><b>${esc(k.name)}</b><span class="s">${esc(k.about)}</span></div>
      ${R.cards.filter((c: any) => (byKey[c.card] as any).constellation === k.key).map((c: any) => {
        const card = byKey[c.card] as any, bet = c.bet || {}, h = c.house;
        const disabled = !card.charted ? ' disabled' : '';
        return `<div class="wcard${card.charted ? '' : ' uncharted'}${c.outcome && bet.move ? (c.points > 0 ? ' won' : ' lost') : ''}" data-card="${esc(c.card)}">
          <div class="wart"><img src="/art/${esc(c.card)}.png" alt="" loading="lazy" onerror="this.style.display='none'"><span class="wstage">${esc(card.stage)}</span><span class="wcost">${card.cost}</span>${card.scansion ? `<span class="wscan" title="${esc(scanAbout[card.scansion] || '')}">${esc(card.scansion)}</span>` : ''}</div>
          <div class="wname">${esc(card.name)}</div>
          <div class="s wability">${esc(card.ability)}</div>
          ${card.on.length ? `<div class="s">evolves from: ${card.on.map((o: string) => esc(byKey[o].name)).join(' + ')}</div>` : ''}
          <div class="wfall"><span class="s">control:</span> ${fallText(c.control)}</div>
          ${R.settled || R.pull_voyage.status === 'at sea' ? `<div class="wfall"><span class="s">pull:</span> ${fallText(c.pull)}</div>` : ''}
          <div class="wbet"><select class="${selectCls()} wmove"${disabled}><option value="">no chip</option>${d.moves.map((m: string) => `<option value="${m}"${bet.move === m ? ' selected' : ''}>${MOVE_LABEL[m]}</option>`).join('')}</select>
            <select class="${selectCls()} wlayer"${disabled}><option value="">any layer</option>${Array.from({ length: 6 }, (_, i) => `<option value="${i}"${bet.layer === i ? ' selected' : ''}>layer ${i}</option>`).join('')}</select></div>
          <div class="s">${h ? `the House: ${esc(h.move)}${h.layer != null ? `, layer ${h.layer}` : ''}` : 'the House: no chip'}${bet.practice ? ' · <b>practice</b> (placed after sailing)' : ''}</div>
          ${c.claude ? `<div class="s wclaude">Claude: <b>${esc(c.claude.move)}</b>${c.claude.layer != null ? `, layer ${c.claude.layer}` : ''}${c.claude.practice ? ' (practice)' : ''}</div>` : ''}
          ${c.outcome ? `<div class="woutcome">moved: <b>${esc(c.outcome)}</b>${c.points != null ? ` · you ${c.points > 0 ? '+' : ''}${c.points}` : ''}${c.claude_points != null ? ` · Claude ${c.claude_points > 0 ? '+' : ''}${c.claude_points}` : ''}${c.house_points != null ? ` · the House ${c.house_points > 0 ? '+' : ''}${c.house_points}` : ''}</div>` : ''}
        </div>`;
      }).join('')}</div>`).join('');
  }
  if (wagerWired) return; wagerWired = true;
  if (lsel) lsel.onchange = about;
  const rr = () => r;
  document.getElementById('wagerdealbtn')?.addEventListener('click', async () => {
    try { const x = await (await import('../../lib/format')).postJSON<any>('/api/wager/deal', { preset: wagerPreset, control: csel!.value, lever: lsel!.value }); wagerRound = x.key; try { localStorage.setItem('thorp.wager.' + wagerPreset, x.key); } catch { /* blocked */ } void classWager(rr(), path); }
    catch (e) { const h = document.getElementById('wagerhead'); if (h) h.innerHTML = `<div class="${emptyCls()}">${esc(String((e as Error).message || e))}</div>`; }
  });
  roundsEl?.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest('.wround') as HTMLElement | null; if (!b) return; wagerRound = b.dataset.round!; try { localStorage.setItem('thorp.wager.' + wagerPreset, wagerRound); } catch { /* blocked */ } void classWager(rr(), path); });
  el.addEventListener('change', async (e) => {
    const tile = (e.target as HTMLElement).closest('.wcard') as HTMLElement | null; if (!tile) return;
    const mv = (tile.querySelector('.wmove') as HTMLSelectElement).value, ly = (tile.querySelector('.wlayer') as HTMLSelectElement).value;
    try { await (await import('../../lib/format')).postJSON('/api/wager/bet', { round: wagerRound, card: tile.dataset.card, move: mv || null, layer: ly === '' ? null : +ly }); }
    catch (err) { alert(String((err as Error).message || err)); }
    void classWager(rr(), path);
  });
  head.addEventListener('click', async (e) => {
    if ((e.target as HTMLElement).id !== 'wagerqueue') return;
    const R2 = wagerData.rounds.find((x: any) => x.key === wagerRound); if (!R2) return;
    if (!confirm(`Queue ${R2.pull}? It goes at the end of the standing queue and changes what the Mac trains next.`)) return;
    try { const x = await (await import('../../lib/format')).postJSON<any>('/api/wager/queue', { round: wagerRound }); alert(`${x.queued} is queued, position ${x.position}.`); }
    catch (err) { alert(String((err as Error).message || err)); }
    void classWager(rr(), path);
  });
}

// ---- Fitouts --------------------------------------------------------------------------------------
let fitKey = '';
async function classFitouts(r: Payload): Promise<void> {
  const el = document.getElementById('classfitouts'); if (!el) return;
  let d: Payload; try { d = await api('/api/fitouts?preset=' + encodeURIComponent(r.preset)); } catch { return; }
  if (!d.fitouts) { el.innerHTML = `<div class="${emptyCls()}">${d.error ? 'the fitouts could not be read: ' + esc(d.error) : 'reading the fitouts (a few seconds)…'}</div>`; return; }
  const key = r.preset + JSON.stringify(d); if (key === fitKey) return; fitKey = key;
  if (!d.fitouts.length) { el.innerHTML = '<div class="' + emptyCls() + '">no fitout curated for this size yet</div>'; return; }
  const stageOf = (run: string) => /-pre-/.test(run) ? ['pretraining', 0] : /-post(\d+)-/.test(run) ? [`post-training ${run.match(/-post(\d+)-/)![1]}`, +run.match(/-post(\d+)-/)![1]] : ['', 9];
  el.innerHTML = d.fitouts.map((f: any) => {
    const runs = [...(f.runs || [])].sort((a: any, b: any) => (stageOf(a.run)[1] as number) - (stageOf(b.run)[1] as number) || a.run.localeCompare(b.run));
    const rc = f.run_cards || {};
    const prog = `<div class="k mt">The cards each stage drew <span class="s">the four necessary cards' latest readings, voyage by voyage</span></div>
      <div class="scroll"><table class="decktable" data-nosort><thead><tr><th>stage</th><th>voyage</th><th></th>${NEEDED.map(([k, n]) => { const fc = CARD_FACE[k] || {}; return `<th>${fc.rank || ''}${fc.suit || ''} ${esc(n)}</th>`; }).join('')}</tr></thead><tbody>${runs.map((x: any) => {
        const c = rc[x.run];
        return `<tr><td>${esc(stageOf(x.run)[0])}</td><td>${c ? `<a href="${shipHash(x.run)}">${esc(x.run)}</a>` : esc(x.run)}</td><td>${statusPill(x.status || 'queued')}</td>${NEEDED.map(([k]) => {
          const v = c && c[k]; if (!v) return `<td class="s">${c ? 'no reading' : 'not sailed'}</td>`;
          const best = Math.max(v.one ?? -Infinity, v.shared ?? -Infinity), fc = CARD_FACE[k] || {};
          return `<td title="one head ${v.one != null ? v.one.toFixed(3) : '–'}${v.shared != null ? `, shared ${v.shared.toFixed(3)}` : ''}; the mark ${v.threshold}"><span class="minicard${v.lit ? ' on' : ''}"><b>${fc.rank || ''}</b><i>${fc.suit || ''}</i></span> ${isFinite(best) ? fmt(best) : '–'}</td>`;
        }).join('')}</tr>`;
      }).join('')}</tbody></table></div>`;
    return fitoutCard(f) + prog;
  }).join('');
  el.querySelectorAll<HTMLAnchorElement>('a.foshelf').forEach((a) => { a.onclick = (e) => { e.preventDefault(); location.href = '/library'; }; });
}

export { guarded as sizeGuarded };
