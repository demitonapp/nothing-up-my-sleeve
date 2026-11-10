// The harbours (UI.md "Harbours"), as typed renderers: the home page's two harbour cards, and one
// harbour's ships, rules, ships fitting out and the foreign models in Zayton. Pure: each takes the
// ladder and the ships and returns the HTML string the island writes; the island owns the poll.

import { big, esc } from '../../lib/format';
import { cardCls, crumbCls, emptyCls, pillCls } from '../../lib/ui';
import { artImg, flagImg } from './helpers';

type Payload = any;

const classSlug = (name: string): string => (name || '').toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-');

export interface HarbourRoute {
  harbour: string | null;
  sub: 'ships' | 'shipbuilder';
  section: 'training' | 'fitting' | 'charting' | null;
}

export const harbourRoute = (path: string): HarbourRoute => {
  const head = path.split('?')[0].replace(/^#/, '');
  // the shipyard is its own address, beside the harbours, not under one: the builder harbour is Phaleron.
  // /shipyard itself is the three cards; /shipyard/<section> opens the SOP at that section.
  const sm = /^\/shipyard(?:\/(training|fitting|charting|raiding))?\/?$/.exec(head);
  if (sm) {
    // the old /shipyard/raiding address is kept as an alias of charting
    const section = sm[1] === 'raiding' ? 'charting' : (sm[1] as HarbourRoute['section']);
    return { harbour: 'phaleron', sub: 'shipbuilder', section: section || null };
  }
  const m = /^\/harbours?\/([^/]+)(?:\/(ships|shipbuilder))?/.exec(head);
  if (!m) return { harbour: null, sub: 'ships', section: null };
  return { harbour: decodeURIComponent(m[1]), sub: m[2] === 'shipbuilder' ? 'shipbuilder' : 'ships', section: null };
};

const shipRuns = (ladder: Payload, preset: string): any[] =>
  ((ladder && ladder.runs) || []).filter((r: any) => r.preset === preset && !(r.name || '').startsWith('smoke'));

const scorePlaceholder = `<span>Chaining –</span><span>Qwen 0.54</span>`;

/** The home page: one card per harbour, its sizes, its depth and how many voyages are running. */
export function harbourCardsHtml(ladder: Payload): string {
  const hs = (ladder && ladder.harbours) || [];
  if (!hs.length) {
    // a server not yet restarted sends no harbours: show every size as one plain group
    return (ladder.rungs || []).map((r: any) => shipCard(ladder, r)).join('');
  }
  return hs.map((x: any) => {
    const rs = (ladder.rungs || []).filter((r: any) => r.harbour === x.key);
    const live = rs.reduce((n: number, r: any) => n + shipRuns(ladder, r.preset).filter((v: any) => v.status === 'running').length, 0);
    const done = rs.reduce((n: number, r: any) => n + shipRuns(ladder, r.preset).filter((v: any) => v.status === 'finished').length, 0);
    return `<a class="${cardCls(true, 'card harbourcard')}" href="/harbours/${encodeURIComponent(x.key)}">${artImg(x.key, 'cardart ship')}
      <div class="top"><span class="nm">${esc(x.name)}</span><span class="preset">${esc(x.aka)}</span></div>
      <div class="job">${esc(x.about)}</div>
      <div class="hships">${rs.map((r: any) => `<span class="${pillCls('')}">${esc(r.name)} <span class="s">${esc(r.preset)}</span></span>`).join(' ')}</div>
      <div class="foot"><span>${esc(x.where)}</span><span class="${pillCls(live ? ' live' : '')}">${live ? live + ' running' : 'at rest'}</span></div>
      <div class="foot"><span>depth ${x.depth ? 'to ' + big(x.depth) + ' parameters' : 'no bottom'}</span><span>${rs.length} ship${rs.length === 1 ? '' : 's'}</span></div>
      <div class="foot"><span>${done} finished voyage${done === 1 ? '' : 's'}</span><span></span></div></a>`;
  }).join('');
}

function shipCard(ladder: Payload, r: any): string {
  const runs = shipRuns(ladder, r.preset);
  const live = runs.filter((x: any) => x.status === 'running').length;
  const done = runs.filter((x: any) => x.status === 'finished').length;
  const nlive = (r.metrics || []).filter((m: any) => m[2] === 'live').length;
  return `<a class="${cardCls(true, 'card classcard')}" href="/ships/${encodeURIComponent(r.preset)}">${artImg(classSlug(r.name), 'cardart ship')}
    <div class="top"><span class="preset">${esc(r.preset)}</span><span class="nm">${esc(r.name)}</span></div>
    <div class="job">${esc(r.role || r.job)}</div>
    <div class="foot"><span>${big(r.total)} params · ${esc(String(r.where || '').split(' (')[0])}</span>
    <span class="${pillCls(live ? ' live' : '')}">${live ? live + ' running' : esc(r.status)}</span></div>
    <div class="foot"><span>${done} finished voyage${done === 1 ? '' : 's'}</span><span>${nlive} of ${(r.metrics || []).length} metrics live</span></div>
    <div class="foot cscore" data-cscore="${esc(r.preset)}">${scorePlaceholder}</div></a>`;
}

/** One harbour: its depth and every size's draught against it, then its ships, the ones fitting out and
 *  (in Zayton) the foreign models. */
export function harbourShipsHtml(ladder: Payload, key: string): string {
  const hs = (ladder && ladder.harbours) || [];
  const h = hs.find((x: any) => x.key === key);
  if (!h) return `<div class="${emptyCls()}">no harbour called ${esc(key)}${hs.length ? `: ${hs.map((x: any) => esc(x.name)).join(', ')}` : ''}</div>`;
  const rules = (() => {
    const logs = (ladder.rungs || []).map((r: any) => Math.log10(r.total));
    const lo = Math.min(...logs) - 0.1, hi = Math.max(...logs) + 0.1;
    const at = (n: number): string => `${(100 * (Math.log10(n) - lo) / (hi - lo)).toFixed(1)}%`;
    // the depth is not shown here (9 November, Justin): the page lists this harbour's ships, not the rule
    // that decides where they lie. The lane stays, as it is what the harbour is for.
    return `<div class="harbourrules" style="grid-column:1/-1"><div class="k">The harbour <span class="s">the ships that sail from here, and the lane they sail on</span></div>
      <div class="hrule"><b>Lane</b> ${esc(h.lane === 'mac' ? 'the Mac lane (MLX)' : 'the Vast lane (torch on CUDA)')}</div>
      <div class="rungcards">${(ladder.rungs || []).filter((r: any) => r.harbour === h.key).map((r: any) => {
        const art = RUNG_ART[r.preset];
        return `<a class="${cardCls(true, 'card classcard rungcard')}" href="/ships/${encodeURIComponent(r.preset)}">
          ${art ? `<img class="cardart" src="/art/${art}.png" alt="" loading="lazy">` : ''}
          <div class="top"><span class="preset">${esc(r.preset)}</span><span class="nm">${esc(rungName(r.preset, r.name))}</span></div>
          <div class="job">${esc(r.name || '')}${r.role ? ` · ${esc(r.role)}` : ''}</div>
          <div class="foot"><span>${big(r.total)} parameters</span><span class="s">${esc(String(r.status || ''))}</span></div></a>`;
      }).join('')}</div></div>`;
  })();
  const foreign = h.key !== 'zayton' || !((ladder && ladder.foreign) || []).length ? '' :
    `<div class="k" style="grid-column:1/-1">Foreign ships <span class="s">outside models, read on the same decks: not Nothing up my sleeve ships, but here so they can be spied on</span></div>`
    + ladder.foreign.map((x: any) => `<a class="${cardCls(true, 'card classcard')}" href="/foreign/${encodeURIComponent(x.key)}">${artImg(x.key, 'cardart ship')}
      <div class="top"><span class="preset">${x.params ? big(x.params) : '–'}</span><span class="nm">${flagImg(x.flag, x.flag_name)} ${esc(x.label)}</span></div>
      <div class="job">an outside model in Zayton: read-only decks, logic, cards and held-out books</div>
      <div class="foot"><span>${x.chained ? 'chain-graded' : 'no chain grades'}</span><span class="${pillCls('accent')}">foreign</span></div></a>`).join('');
  // the rung cards inside "The harbour" are this harbour's ships (9 November: "the page lists this
  // harbour's ships, not the rule that decides where they lie"); the same sizes are not drawn twice
  // below them (10 November, Justin: "remove the bottom 3 cards"), and the fitting-out cards are not
  // drawn here either (10 November, Justin: "remove the second row of cards"); the API still carries
  // `fitting_out`, so the ships can be listed elsewhere without another query
  return rules + foreign;
}

/** The current version's score under a ship card (/api/class_score): chaining leads, the goal's distance
 *  and the cards held beside it. */
export function classScoreHtml(s: Payload, preset: string): { html: string; title: string } {
  const QWEN = 0.538;
  if (!s || !s.version) return { html: scorePlaceholder, title: '' };
  const ch = s.chaining;
  return {
    html: `<span>Chaining <b>${ch == null ? '–' : ch.toFixed(2)}</b></span><span>Qwen 0.54 · ${s.held ?? '–'} of 4 cards</span>`,
    title: `the goal: chaining lift against Qwen3 4B's ${QWEN.toFixed(2)}. ${s.version}${s.ship ? ' (' + s.ship + ')' : ''}: ${ch == null ? 'no chaining reading yet' : ch.toFixed(3)}`,
  };
}

export const harbourTitle = (ladder: Payload, key: string | null): string => {
  if (!key) return 'Harbours';
  const h = ((ladder && ladder.harbours) || []).find((x: any) => x.key === key);
  return h ? h.name : key;
};

export const harbourAbout = (ladder: Payload, key: string | null): string => {
  if (!key) return '';
  const h = ((ladder && ladder.harbours) || []).find((x: any) => x.key === key);
  return h ? `${h.aka || ''}: ${h.about || ''}` : '';
};

export const harbourTabs = (ladder: Payload, key: string | null): { ships: string; shipbuilder: string | null } => {
  if (!key) return { ships: '/harbours', shipbuilder: null };
  const h = ((ladder && ladder.harbours) || []).find((x: any) => x.key === key);
  return { ships: `/harbours/${encodeURIComponent(key)}/ships`, shipbuilder: h && h.ship_builder ? '/shipyard' : null };
};


/** The shipyard's three sections, as cards like the harbours' (the landing at /shipyard). */
/** The ladder in the soundings' language (9 November, Justin: "I like set two"): each rung's role, not its
 *  ship name. The keys (preset) stay what the ledger names; this is what the page calls them. */
export const RUNG_METAPHOR: Record<string, string> = {
  '300k': 'the sounding', '1m': 'the survey', '9m': 'the landfall',
  '21m': 'the passage', '50m': 'the crossing', '100m': 'the ocean', '350m': 'the new world',
};
export const rungName = (preset: string, fallback = ''): string => RUNG_METAPHOR[preset] || fallback || preset;
/** The fal image each rung wears (backend/thorp/dash/art/generate_art.py, LADDER). */
export const RUNG_ART: Record<string, string> = {
  '300k': 'sounding', '1m': 'survey', '9m': 'landfall',
  '21m': 'passage', '50m': 'crossing', '100m': 'ocean', '350m': 'new_world',
};

export function shipyardCardsHtml(): string {
  const cards: [string, string, string, string][] = [
    ['charting', 'Charting', 'sorting out the charts the voyage is planned on: the route, the stars, and the suits', 'charting'],
    ['hulls', 'Hull sizes', "each rung's layers, width, heads and head width: the shape a ship is built to, set in Postgres", 'hulls'],
    ['constraints', 'The yard’s constraints', 'the slipways, the tide, the clerk and the survey dock: the limits on how many voyages the yard can launch, and the levers that move them', 'shipyard'],
  ];
  return cards.map(([key, name, about, art]) => `<a class="${cardCls(true, 'card harbourcard shipyardcard')}" href="/shipyard/${key}">${artImg(art, 'cardart ship')}
    <div class="top"><span class="preset">shipyard</span><span class="nm">${esc(name)}</span></div>
    <div class="job">${esc(about)}</div>
    <div class="foot"><span>open the ${esc(name.toLowerCase())}</span><span class="${pillCls('accent')}">section</span></div></a>`).join('');
}
