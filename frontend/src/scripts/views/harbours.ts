// The harbours (UI.md "Harbours"), as typed renderers: the home page's harbour cards (Schi'mint, Vavatch End
// and Masaq' Reach), and one harbour's ships, rules, ships fitting out and the foreign models in Masaq' Reach. Pure:
// each takes the ladder and the ships and returns the HTML string the island writes; the island owns the poll.

import { big, esc } from '../../lib/format';
import { cardCls, crumbCls, emptyCls, pillCls } from '../../lib/ui';
import { artImg, flagImg } from './helpers';
import { BANDS, BAND, bandCardHtml, bandOf, sizeOf, type SizeBand } from './bands';

type Payload = any;

const classSlug = (name: string): string => (name || '').toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-');

/** The harbours are Orbitals now (11 November, Justin: "naming must change and art style accordingly"); the
 *  three old keys stay as aliases so an old address lands on the right one. */
export const HARBOUR_ALIASES: Record<string, string> = {
  phaleron: 'schimint',
  piraeus: 'vavatch-end',
  zayton: 'masaq-reach',
};
export const harbourKey = (k: string | null | undefined): string => HARBOUR_ALIASES[String(k || '')] || String(k || '');
export const isOldHarbour = (k: string | null | undefined): boolean => String(k || '') in HARBOUR_ALIASES;

export interface HarbourRoute {
  harbour: string | null;
  sub: 'ships' | 'shipbuilder';
  section: 'training' | 'fitting' | 'charting' | null;
  band: SizeBand | null;
}

export const harbourRoute = (path: string): HarbourRoute => {
  const head = path.split('?')[0].replace(/^#/, '');
  // the shipyard is its own address, beside the harbours, not under one: the builder harbour is Schi'mint.
  // /shipyard itself is the three cards; /shipyard/<section> opens the SOP at that section.
  const sm = /^\/shipyard(?:\/(training|fitting|charting|raiding))?\/?$/.exec(head);
  if (sm) {
    // the old /shipyard/raiding address is kept as an alias of charting
    const section = sm[1] === 'raiding' ? 'charting' : (sm[1] as HarbourRoute['section']);
    return { harbour: 'schimint', sub: 'shipbuilder', section: section || null, band: null };
  }
  const m = /^\/harbours?\/([^/]+)(?:\/(ships|shipbuilder|xsmall|small|medium|large))?/.exec(head);
  if (!m) return { harbour: null, sub: 'ships', section: null, band: null };
  const band = m[2] === 'xsmall' || m[2] === 'small' || m[2] === 'medium' || m[2] === 'large' ? (m[2] as SizeBand) : null;
  return { harbour: harbourKey(decodeURIComponent(m[1])), sub: m[2] === 'shipbuilder' ? 'shipbuilder' : 'ships', section: null, band };
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
    const nForeign = x.foreign ? ((ladder && ladder.foreign) || []).length : 0;
    const ships = x.foreign
      ? (nForeign ? `<span class="${pillCls('accent')}">${nForeign} foreign ship${nForeign === 1 ? '' : 's'}</span>` : '<span class="s">none read yet</span>')
      : rs.map((r: any) => `<span class="${pillCls('')}">${esc(r.name)} <span class="s">${esc(r.preset)}</span></span>`).join(' ');
    return `<a class="${cardCls(true, 'card harbourcard')}" href="/harbours/${encodeURIComponent(x.key)}">${artImg(x.key, 'cardart ship')}
      <div class="top"><span class="nm">${esc(x.name)}</span><span class="preset">${esc(x.aka)}</span></div>
      <div class="job">${esc(x.about)}</div>
      <div class="hships">${ships}</div>
      <div class="foot"><span>${esc(x.where)}</span><span class="${pillCls(x.foreign ? '' : live ? ' live' : '')}">${x.foreign ? 'read-only' : live ? live + ' running' : 'at rest'}</span></div>
      <div class="foot"><span>${x.foreign ? 'foreign ships only' : 'depth ' + (x.depth ? 'to ' + big(x.depth) + ' parameters' : 'no bottom')}</span><span>${x.foreign ? `${nForeign} foreign ship${nForeign === 1 ? '' : 's'}` : `${rs.length} ship${rs.length === 1 ? '' : 's'}`}</span></div>
      <div class="foot"><span>${x.foreign ? 'not ours to build' : `${done} finished voyage${done === 1 ? '' : 's'}`}</span><span></span></div></a>`;
  }).join('');
}

/** A class's art key where it differs from its name: the 300k's class is called Faces and its plate is Pan
 *  (the 300k is Pan, playing cards with the universe), so the card had drawn no frame at all. */
const CLASS_ART: Record<string, string> = { faces: 'pan' };
const classArt = (name: string): string => CLASS_ART[classSlug(name)] || classSlug(name);

function shipCard(ladder: Payload, r: any): string {
  const runs = shipRuns(ladder, r.preset);
  const live = runs.filter((x: any) => x.status === 'running').length;
  const done = runs.filter((x: any) => x.status === 'finished').length;
  const nlive = (r.metrics || []).filter((m: any) => m[2] === 'live').length;
  return `<a class="${cardCls(true, 'card classcard')}" href="/ships/${encodeURIComponent(r.preset)}">${artImg(classArt(r.name), 'cardart ship')}
    <div class="top"><span class="preset">${esc(r.preset)}</span><span class="nm">${esc(r.name)}</span></div>
    <div class="job">${esc(r.role || r.job)}</div>
    <div class="foot"><span>${big(r.total)} params · ${esc(String(r.where || '').split(' (')[0])}</span>
    <span class="${pillCls(live ? ' live' : '')}">${live ? live + ' running' : esc(r.status)}</span></div>
    <div class="foot"><span>${done} finished voyage${done === 1 ? '' : 's'}</span><span>${nlive} of ${(r.metrics || []).length} metrics live</span></div>
    <div class="foot cscore" data-cscore="${esc(r.preset)}">${scorePlaceholder}</div></a>`;
}

/** Masaq' Reach's outside models, one per model key: the registry holds two files for Qwen3-0.6B (one with a
 *  published size and one without), and a band must not draw the same ship twice. The sized entry wins. */
function foreignShips(ladder: Payload): any[] {
  const by = new Map<string, any>();
  for (const x of (ladder && ladder.foreign) || []) {
    const prev = by.get(x.key);
    if (!prev || (sizeOf(prev) == null && sizeOf(x) != null)) by.set(x.key, x);
  }
  return [...by.values()];
}

const foreignCard = (x: any, harbour: any): string => {
  const p = sizeOf(x);
  return `<a class="${cardCls(true, 'card classcard')}" href="/foreign/${encodeURIComponent(x.key)}">${artImg(x.key, 'cardart ship')}
    <div class="top"><span class="preset">${p ? big(p) : '–'}</span><span class="nm">${flagImg(x.flag, x.flag_name)} ${esc(x.label)}</span></div>
    <div class="job">an outside model in ${esc(harbour.name)}: read-only decks, logic, cards and held-out books</div>
    <div class="foot"><span>${x.chained ? 'chain-graded' : 'no chain grades'}</span><span class="${pillCls('accent')}">foreign</span></div></a>`;
};

/** Masaq' Reach: the three size bands first (small 300k–4B, medium 4B–32B, large above 32B), each opening the
 *  outside ships in it. The band card carries our own fleet where it falls, so the scale is read against
 *  ships we built rather than a bare number. */
function foreignHarbourHtml(ladder: Payload, h: any, band: SizeBand | null): string {
  const ships = foreignShips(ladder);
  if (!band) {
    return BANDS.map((b) => {
      const inBand = ships
        .filter((x) => bandOf(sizeOf(x)) === b.key)
        .sort((a, b2) => (sizeOf(b2) || 0) - (sizeOf(a) || 0));
      const ours = ((ladder && ladder.rungs) || []).filter((r: any) => bandOf(sizeOf(r)) === b.key);
      const preview = inBand.slice(0, 3).map((x) => `${esc(x.label)} (${sizeOf(x) ? big(sizeOf(x)) : '–'})`).join(' · ');
      const more = inBand.length > 3 ? ` and ${inBand.length - 3} more` : '';
      const fleet = ours.length ? ours.map((r: any) => esc(r.preset)).join(' · ') : 'none';
      const body = `<div>${inBand.length ? `<b>${inBand.length}</b> outside ship${inBand.length === 1 ? '' : 's'}${preview ? `: ${preview}${more}` : ''}` : 'no outside ship in this band yet'}</div>`
        + `<div class="s">our fleet here: ${fleet}</div>`;
      return bandCardHtml(b, {
        href: `/harbours/${encodeURIComponent(h.key)}/${b.key}`,
        body,
        feet: [[`${inBand.length} outside ship${inBand.length === 1 ? '' : 's'}`, `${inBand.filter((x) => x.chained).length} chain-graded`]],
        cta: 'open the band →',
      });
    }).join('');
  }
  const info = BAND(band);
  const list = ships
    .filter((x) => bandOf(sizeOf(x)) === band)
    .sort((a, b) => (sizeOf(b) || 0) - (sizeOf(a) || 0));
  const head = `<div class="k" style="grid-column:1/-1">${list.length} outside ship${list.length === 1 ? '' : 's'} in ${esc(info ? info.name.toLowerCase() : band)} <span class="s">${esc(info ? info.range : '')}, biggest first: not ours to build, read on our decks</span></div>`;
  return head + (list.length
    ? list.map((x) => foreignCard(x, h)).join('')
    : `<div class="${emptyCls()}">no outside model read in this band yet: the largest read here is Qwen3.8-27B at 27B</div>`);
}

/** The band's known-but-unread models, beside the read ships: the leaderboard's candidates, marked so a
 *  pulled model is visible before its reading lands. A candidate that already has a reading is not drawn
 *  twice. */
export function candidateCardsHtml(cands: any[], band: SizeBand, read: any[]): string {
  const norm = (x: any): string => String(x || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const readLabels = new Set((read || []).map((x) => norm(x.label)));
  const unread = (cands || []).filter(
    (c) => bandOf(sizeOf(c)) === band && !readLabels.has(norm(c.label)),
  );
  if (!unread.length) return '';
  return `<div class="k" style="grid-column:1/-1">Candidates in this band <span class="s">known outside models not read on our decks yet: they join the harbour when a reading lands</span></div>`
    + unread.map((c) => {
      const key = String(c.label || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const p = sizeOf(c);
      const why = String(c.why || '').replace(/\s+/g, ' ').trim();
      return `<a class="${cardCls(true, 'card classcard candidatecard')}" href="/leaderboard/competitor/${encodeURIComponent(c.model)}">
        ${artImg(key, 'cardart ship')}
        <div class="top"><span class="preset">${p ? big(p) : '–'}</span><span class="nm">${esc(c.label)}</span></div>
        <div class="job">${esc(c.lab || 'a candidate')}${why ? `: ${esc(why.length > 150 ? why.slice(0, 149).trimEnd() + '…' : why)}` : ''}</div>
        <div class="foot"><span>not read yet</span><span class="${pillCls('accent')}">candidate</span></div></a>`;
    }).join('');
}

/** One harbour: its depth and every size's draught against it, then its ships, the ones fitting out and
 *  (in the foreign-only Masaq' Reach) the three size bands or the outside models in one of them. */
export function harbourShipsHtml(ladder: Payload, key: string, band: SizeBand | null = null): string {
  const hs = (ladder && ladder.harbours) || [];
  const h = hs.find((x: any) => x.key === key);
  if (!h) return `<div class="${emptyCls()}">no harbour called ${esc(key)}${hs.length ? `: ${hs.map((x: any) => esc(x.name)).join(', ')}` : ''}</div>`;
  if (h.foreign) return foreignHarbourHtml(ladder, h, band);
  const rules = (() => {
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
  return rules;
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
  // the yard's cards are brass plates on a dark ground: a numeral, the name, a hairline rule, the job
  return cards.map(([key, name, about, art], i) => `<a class="${cardCls(true, 'card harbourcard shipyardcard')}" href="/shipyard/${key}">${artImg(art, 'cardart ship')}
    <div class="yardplate">
      <span class="yardnum">${String(i + 1).padStart(2, '0')}</span>
      <span class="yardrule" aria-hidden="true"></span>
      <span class="nm">${esc(name)}</span>
      <span class="job">${esc(about)}</span>
      <span class="yardopen">open the ${esc(name.toLowerCase())} →</span>
    </div></a>`).join('');
}
