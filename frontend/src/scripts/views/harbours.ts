// The harbours (UI.md "Harbours"), as typed renderers: the home page's harbour cards (Schi'mint, Vavatch End
// and Masaq' Reach), and one harbour's ships, rules, ships fitting out and the foreign models in Masaq' Reach. Pure:
// each takes the ladder and the ships and returns the HTML string the island writes; the island owns the poll.

import { big, esc } from '../../lib/format';
import { cardCls, crumbCls, emptyCls, pillCls } from '../../lib/ui';
import { artImg, artSrc, flagImg } from './helpers';
import { BANDS, BAND, bandCardHtml, bandOf, sizeOf, type SizeBand } from './bands';

type Payload = any;


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
  sub: 'ships' | 'shipbuilder' | 'berth';
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
  // The orbitals' addresses: /orbitals/demiton, /orbitals/masaq-reach, and the old /harbours aliases. A
  // size band may sit directly after the harbour (/masaq-reach/xsmall) or after its ships view
  // (/masaq-reach/ships/xsmall), since the trading orbital's All ships view is its own page.
  const m = /^\/(?:orbitals|harbours?)\/([^/]+)(?:\/(ships|shipbuilder|berth)(?:\/(xsmall|small|medium|large))?|\/(xsmall|small|medium|large))?/.exec(head);
  if (!m) return { harbour: null, sub: 'ships', section: null, band: null };
  const rawBand = m[3] || m[4];
  const band = rawBand === 'xsmall' || rawBand === 'small' || rawBand === 'medium' || rawBand === 'large' ? (rawBand as SizeBand) : null;
  return { harbour: harbourKey(decodeURIComponent(m[1])), sub: m[2] === 'shipbuilder' ? 'shipbuilder' : m[2] === 'berth' ? 'berth' : 'ships', section: null, band };
};

const shipRuns = (ladder: Payload, preset: string): any[] =>
  ((ladder && ladder.runs) || []).filter((r: any) => r.preset === preset && !(r.name || '').startsWith('smoke'));

const scorePlaceholder = `<span>Chaining –</span><span>Qwen 0.54</span>`;

export interface HarbourView { img: string; label: string; note: string }

/** The five views on the back of each harbour's card (11 November, Justin: "the cards to harbours to flip so
 *  each harbour has 5 images showing the different aspects of the harbour"): the harbour's own plate first,
 *  then four more from `HARBOUR_VIEWS` in backend/thorp/dash/art/generate_art.py, which makes the images. */
export const HARBOUR_VIEWS: Record<string, HarbourView[]> = {
  schimint: [
    { img: 'schimint', label: 'the ring', note: 'The first Orbital rising over black water, where a young crew meets its first class.' },
    { img: 'schimint-drill', label: 'the drill', note: 'Crews learn the plainest skills first: rope before sail, the 300k before the 21m.' },
    { img: 'schimint-school', label: 'the chart school', note: 'Where the SOP is taught: the content, the fade, and the content by heart.' },
    { img: 'schimint-berth', label: 'the fitting-out berth', note: 'Augustus, Plato, Francis and Diderot lie half-rigged, each with its own lantern and its own job.' },
    { img: 'schimint-launch', label: 'the first voyage', note: 'A crew pulls away from the rim for its first run: one seed, one voyage, read at the end.' },
  ],
  'vavatch-end': [
    { img: 'vavatch-end', label: 'the yards', note: 'Half-built hulls cradled along the ring: the 50m, 100m and 350m are built here.' },
    { img: 'vavatch-end-slip', label: 'the slip', note: 'A keel as long as a street: the deepest ships are laid down on hired ground.' },
    { img: 'vavatch-end-forge', label: 'the forge', note: 'Heat and hammers for the heavy fittings, the work too hard for the Mac mini.' },
    { img: 'vavatch-end-launch', label: 'the launch', note: 'Down the ways at last: the one moment the whole yard stops to watch.' },
    { img: 'vavatch-end-gate', label: 'the hiring gate', note: 'Gangs are taken on by the hour: the GPUs are hired from Vast.ai and let go when the voyage ends.' },
  ],
  'masaq-reach': [
    { img: 'masaq-reach', label: 'the market', note: 'The Reach by lantern: ships of many worlds trading under one curved hull.' },
    { img: 'masaq-reach-quay', label: 'the quay', note: 'Foreign hulls of every build lie side by side: Qwen, Gemma, Phi and the rest.' },
    { img: 'masaq-reach-scales', label: 'the scales', note: 'Each outside ship is weighed on our decks: logic, cards and held-out books.' },
    { img: 'masaq-reach-exchange', label: 'the exchange', note: 'Where the readings are bargained over; none of these ships is ours to build.' },
    { img: 'masaq-reach-gauge', label: 'the gauge post', note: 'Ships are measured by size, small, medium and large, against our own fleet.' },
  ],
};

/** The home page's two orbitals (12 November, Justin: "the analogy is orbitals for the homepage. The
 *  demiton orbital and then the trading orbital where all the other labs and their ships reside").
 *  Demiton is our own: the lab and every ship it builds, with the training ring and the deep yards as its
 *  berths. The trading orbital is Masaq' Reach, where every other lab and its ships reside; its card opens
 *  the Labs tab. The old harbour pages stay reachable from Demiton's berth links. */
export const DEMITON = {
  key: 'demiton',
  name: 'Demiton',
  aka: 'our orbital',
  about: 'our own orbital: the lab and the fleet it builds, from the 300k to the 350m. The shipyard draws them; the training ring and the deep yards are its berths.',
  where: 'this Mac mini and the hired yards',
  depth: null,
  lane: 'mac',
  ship_builder: '',
  foreign: false,
  flag: 'demiton',
};

/** The five views on Demiton's own card, in the same order as a harbour's: the ring, then the two berths
 *  where our ships are built, then the tank and the mile where a hull is measured. */
export const DEMITON_VIEWS: HarbourView[] = [
  { img: 'demiton', label: 'the ring', note: 'Our own Orbital: the ring where the lab builds and sails its fleet, from the 300k to the 350m.' },
  { img: 'schimint', label: 'the training ring', note: 'The first berth: where the youngest ships are laid down and the first class is learned.' },
  { img: 'vavatch-end', label: 'the deep yards', note: 'The second berth: the 50m, 100m and 350m are built on hired ground, too deep for the Mac.' },
  { img: 'towing-tank', label: 'the towing tank', note: 'One small hull after another drawn down the same water, and every reading written in the ledger.' },
  { img: 'measured-mile', label: 'the measured mile', note: 'The marked water where a real hull is timed between two posts, to check what the tank predicted.' },
];

/** The back of a harbour card: the first view large, the five as thumbnails. Images carry `data-src` and are
 *  fetched on the first flip (`views/harbourflip.ts`), so the home page does not load fifteen plates up front. */
const harbourBackHtml = (key: string, name: string, views: HarbourView[], href = `/orbitals/${encodeURIComponent(key)}`): string =>
  `<div class="${cardCls(false, 'card harbourcard hface hback')}" inert aria-label="${esc(name)}: five views">
    <div class="hshotbox"><img class="hshot" data-src="${esc(artSrc(views[0].img))}" alt="${esc(views[0].label)}"></div>
    <div class="hcap"><b class="hcaplabel">${esc(views[0].label)}</b><span class="hcapnote">${esc(views[0].note)}</span></div>
    <div class="hthumbs" role="group" aria-label="${esc(name)} views">${views.map((v, i) =>
      `<button type="button" class="hthumb${i === 0 ? ' on' : ''}" data-hview="${i}" aria-label="${esc(v.label)}" aria-pressed="${i === 0}"><img data-src="${esc(artSrc(v.img))}" alt=""></button>`).join('')}</div>
    <div class="hbackfoot"><a href="${esc(href)}">open ${esc(name)} →</a></div></div>`;

/** The home page: the two orbitals, each a card that flips to its five views. Demiton carries our own fleet
 *  and opens our orbital; the trading orbital carries the houses and opens the Labs view. */
export function harbourCardsHtml(ladder: Payload): string {
  const hs = (ladder && ladder.harbours) || [];
  const rungs = (ladder && ladder.rungs) || [];
  if (!rungs.length && !hs.length) {
    return `<div class="${emptyCls()}">the orbitals could not be read. Restart <span class="mono">thorp dash</span> if it was just changed.</div>`;
  }
  const live = rungs.reduce((n: number, r: any) => n + shipRuns(ladder, r.preset).filter((v: any) => v.status === 'running').length, 0);
  const done = rungs.reduce((n: number, r: any) => n + shipRuns(ladder, r.preset).filter((v: any) => v.status === 'finished').length, 0);
  const nForeign = new Set(((ladder && ladder.foreign) || []).map((x: any) => x.key)).size;
  const houses = (ladder && ladder.labs) || [];
  // The card shows the houses' countries, not every name (12 November, Justin: "just show the country flag
  // with the labs count"): one flag per country, and the count stays in the foot below.
  const countries = [...new Map(houses.map((l: any) => [l.flag, l])).values()];
  const labPills = countries.length
    ? countries.map((l: any) => `<span class="${pillCls('')}">${flagImg(l.flag, l.country_name || l.flag)}</span>`).join(' ')
    : `<span class="${pillCls('')}">the houses</span>`;
  const demitonFront = `<a class="${cardCls(true, 'card harbourcard hface hfront')}" href="/orbitals/demiton">${artImg('demiton', 'cardart ship')}
    <div class="top"><span class="nm">Demiton</span><span class="preset">${flagImg('demiton', 'Demiton · Drake’s arms')} our orbital</span></div>
    <div class="job">${esc(DEMITON.about)}</div>
    <div class="hships">${rungs.map((r: any) => `<span class="${pillCls('')}">${esc(r.name)} <span class="s">${esc(r.preset)}</span></span>`).join(' ')}</div>
    <div class="foot"><span>${esc(DEMITON.where)}</span><span class="${pillCls(live ? 'live' : '')}">${live ? live + ' running' : 'at rest'}</span></div>
    <div class="foot"><span>${rungs.length} ship${rungs.length === 1 ? '' : 's'}</span><span>${done} finished voyage${done === 1 ? '' : 's'}</span></div>
    <div class="foot"><span>the training ring and the deep yards</span><span>our lab</span></div></a>`;
  const tradingFront = `<a class="${cardCls(true, 'card harbourcard hface hfront')}" href="/orbitals/masaq">${artImg('masaq-reach', 'cardart ship')}
    <div class="top"><span class="nm">Masaq' Reach</span><span class="preset">the trading orbital</span></div>
    <div class="job">Where every other lab and its ships reside: the houses, their fleets, and every outside model read on our decks. None of them is ours to build.</div>
    <div class="hships">${labPills}</div>
    <div class="foot"><span>the Reach</span><span class="${pillCls('accent')}">${houses.length || 11} house${(houses.length || 11) === 1 ? '' : 's'}</span></div>
    <div class="foot"><span>${nForeign} foreign ship${nForeign === 1 ? '' : 's'}</span><span>read-only</span></div>
    <div class="foot"><span>every one of them read on our decks</span><span>not ours to build</span></div></a>`;
  const flip = (key: string, name: string, front: string, views: HarbourView[], href: string): string =>
    `<div class="hflip" data-harbour="${esc(key)}"><div class="hflip-inner">${front}${harbourBackHtml(key, name, views, href)}</div>`
    + `<button type="button" class="hflipbtn" data-hflip aria-pressed="false" aria-label="Flip ${esc(name)} to see five views"><span class="hflipicon" aria-hidden="true">⟲</span><span class="hfliptext">5 views</span></button></div>`;
  return flip('demiton', 'Demiton', demitonFront, DEMITON_VIEWS, '/orbitals/demiton')
    + flip('masaq-reach', "Masaq' Reach", tradingFront, HARBOUR_VIEWS['masaq-reach'], '/orbitals/masaq');
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

/** Masaq' Reach, the trading orbital's **All ships** view: every outside ship, biggest first, with the
 *  four size bands as a filter. A filtered view is its own address (`/labs/ships/<band>`), so a
 *  band can be linked and the back button works; the Labs view is the same orbital's other tab (`/labs`). */
function foreignHarbourHtml(ladder: Payload, h: any, band: SizeBand | null): string {
  const ships = foreignShips(ladder);
  const info = band ? BAND(band) : null;
  const count = (b: SizeBand): number => ships.filter((x) => bandOf(sizeOf(x)) === b).length;
  const filter = `<div class="sizefilter" role="group" aria-label="filter the outside ships by size">
    <a class="${pillCls(band ? '' : 'accent')}" href="/orbitals/masaq/models">All <span class="s">${ships.length}</span></a>
    ${BANDS.map((b) => `<a class="${pillCls(band === b.key ? 'accent' : '')}" href="/orbitals/masaq/models/${b.key}" title="${esc(b.range)}">${esc(b.name)} <span class="s">${count(b.key)}</span></a>`).join('')}
  </div>`;
  const list = (band ? ships.filter((x) => bandOf(sizeOf(x)) === band) : ships)
    .sort((a, b) => (sizeOf(b) || 0) - (sizeOf(a) || 0));
  const head = `<div class="k" style="grid-column:1/-1">${list.length} outside ship${list.length === 1 ? '' : 's'}${info ? ` in ${esc(info.name.toLowerCase())} <span class="s">${esc(info.range)}` : ' in the Reach'} <span class="s">biggest first: not ours to build, read on our decks</span></div>`;
  return filter + head + (list.length
    ? list.map((x) => foreignCard(x, h)).join('')
    : `<div class="${emptyCls()}">no outside model read in this band yet: the largest read here is Qwen3.8-27B at 27B</div>`);
}

/** The trading orbital's Models view: four cards, one per size band, each with its art, the count of
 *  outside models in it and our own fleet there. A card opens that band's models. */
export function sizeBandCardsHtml(ladder: Payload): string {
  const ships = foreignShips(ladder);
  return BANDS.map((b) => {
    const inBand = ships.filter((x) => bandOf(sizeOf(x)) === b.key);
    const ours = ((ladder && ladder.rungs) || []).filter((r: any) => bandOf(sizeOf(r)) === b.key);
    const body = `<div>${inBand.length ? `<b>${inBand.length}</b> outside model${inBand.length === 1 ? '' : 's'}` : 'no outside model in this band yet'}</div>`
      + `<div class="s">our fleet here: ${ours.length ? ours.map((r: any) => esc(r.preset)).join(' · ') : 'none'}</div>`;
    return bandCardHtml(b, {
      href: `/orbitals/masaq/models/${b.key}`,
      body,
      feet: [[`${inBand.length} model${inBand.length === 1 ? '' : 's'}`, `${inBand.filter((x) => x.chained).length} chain-graded`]],
      cta: 'open the band →',
    });
  }).join('');
}

/** The trading orbital's Models view for one band: its ships, biggest first, with the size filter. */
export const foreignShipsHtml = (ladder: Payload, band: SizeBand | null = null): string =>
  foreignHarbourHtml(ladder, { name: "Masaq' Reach" }, band);

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
      // a candidate has no competitor page yet (it has no reading): its card opens its model card, not a 404
      const body = `${artImg(key, 'cardart ship')}
        <div class="top"><span class="preset">${p ? big(p) : '–'}</span><span class="nm">${esc(c.label)}</span></div>
        <div class="job">${esc(c.lab || 'a candidate')}${why ? `: ${esc(why.length > 150 ? why.slice(0, 149).trimEnd() + '…' : why)}` : ''}</div>
        <div class="foot"><span>not read yet</span><span class="${pillCls('accent')}">candidate</span></div>`;
      const cls = cardCls(true, 'card classcard candidatecard');
      return c.source
        ? `<a class="${cls}" href="${esc(c.source)}" target="_blank" rel="noreferrer">${body}</a>`
        : `<div class="${cls}">${body}</div>`;
    }).join('');
}

/** Demiton, our own orbital: its two berths and every rung we build, from the 300k to the 350m. The two
 *  berth pages (Schi'mint's training ring and Vavatch End's deep yards) stay reachable from the links; the
 *  blocks beneath them are the same harbour pages' own ship lists, so the fleet is not written twice. */
export function demitonShipsHtml(ladder: Payload, view: 'overview' | 'berth' = 'overview'): string {
  const hs = (ladder && ladder.harbours) || [];
  const berths = ['schimint', 'vavatch-end'].map((k) => hs.find((x: any) => x.key === k)).filter(Boolean);
  // The four sections as image cards (12 November, Justin: "this page should rather have fal images for its
  // four sections: Berth, Shipyard, Library, Expeditions ... to allow the user to navigate"). The berth has its
  // own page (/orbitals/demiton/berth, the fleet); the other three open theirs.
  const sections: [string, string, string, string][] = [
    ['Berth', 'the two rings our fleet is built and sailed from, and every ship of it', '/orbitals/demiton/berth', 'demiton-berth'],
    ['Shipyard', 'where a ship is drawn before it is built: the SOP it reads, the stages it must build, and the standard it is held to', '/shipyard', 'demiton-shipyard'],
    ['Library', 'the books and sources our ships read, and what each one holds', '/library', 'demiton-library'],
    ['Expeditions', 'the voyages we send out: what is queued, what is running and what came back', '/expeditions', 'demiton-expeditions'],
    // the fifth (12 November, Justin: "VSM should have it's own card here ... with a fal image")
    ['VSM', 'how the fleet governs itself: operations, coordination, control and its audit, intelligence, and the policy Justin signs', '/vsm', 'demiton-vsm'],
  ];
  const links = `<div class="harbours shipyardgrid demitonyard five" style="grid-column:1/-1">${sections.map(([name, about, href, art], i) =>
    `<a class="${cardCls(true, 'card harbourcard shipyardcard')}" href="${esc(href)}">${artImg(art, 'cardart ship')}
      <div class="yardplate">
        <span class="yardnum">${String(i + 1).padStart(2, '0')}</span>
        <span class="yardrule" aria-hidden="true"></span>
        <span class="nm">${esc(name)}</span>
        <span class="job">${esc(about)}</span>
        <span class="yardopen">open the ${esc(name.toLowerCase())} →</span>
      </div></a>`).join('')}</div>`;
  // the overview is the four cards alone; the berth is its own page: the two rings and every ship of the fleet
  if (view === 'overview') return links;
  const rings = `<div class="harbourrules" style="grid-column:1/-1"><div class="k">The berths <span class="s">the two rings our fleet is built and sailed from</span></div>
    <div class="hrule"><b>The berths</b> ${berths.map((h: any) => `<a href="/orbitals/${encodeURIComponent(h.key)}">${esc(h.name)} · ${esc(h.aka)}</a>`).join(' · ') || 'the training ring and the deep yards'}</div></div>`;
  return rings + berths.map((h: any) => harbourShipsHtml(ladder, h.key)).join('');
}

/** One harbour: its depth and every size's draught against it, then its ships, the ones fitting out and
 *  (in the foreign-only Masaq' Reach) the three size bands or the outside models in one of them. */
export function harbourShipsHtml(ladder: Payload, key: string, band: SizeBand | null = null, sub = ''): string {
  if (key === DEMITON.key) return demitonShipsHtml(ladder, sub === 'berth' ? 'berth' : 'overview');
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
          <div class="job">${[sameName(rungName(r.preset, r.name), r.name) ? '' : esc(r.name || ''), r.role ? esc(r.role) : ''].filter(Boolean).join(' · ')}</div>
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
  if (!key) return 'Orbitals';
  if (key === DEMITON.key) return DEMITON.name;
  const h = ((ladder && ladder.harbours) || []).find((x: any) => x.key === key);
  return h ? h.name : key;
};

export const harbourAbout = (ladder: Payload, key: string | null): string => {
  if (!key) return '';
  if (key === DEMITON.key) return DEMITON.about;
  const h = ((ladder && ladder.harbours) || []).find((x: any) => x.key === key);
  return h ? `${h.aka || ''}: ${h.about || ''}` : '';
};

export const harbourTabs = (ladder: Payload, key: string | null): { ships: string; shipbuilder: string | null } => {
  if (!key) return { ships: '/harbours', shipbuilder: null };
  const h = ((ladder && ladder.harbours) || []).find((x: any) => x.key === key);
  return { ships: `/orbitals/${encodeURIComponent(key)}/ships`, shipbuilder: h && h.ship_builder ? '/shipyard' : null };
};


/** The shipyard's three sections, as cards like the harbours' (the landing at /shipyard). */
/** The ladder in the soundings' language (9 November, Justin: "I like set two"): each rung's role, not its
 *  ship name. The keys (preset) stay what the ledger names; this is what the page calls them. The two
 *  smallest left that set on 11 November (Justin: "i like towing tank, please update the fal images and the
 *  naming"; "Yes, rename 1m"): they were the sounding and the survey, and are now what their classes are
 *  called, so the card says one name, not two. The 9m and the 21m followed on 12 November (Justin: "Yes,
 *  rename both"): they were the landfall and the passage, and are the sea trial and the coasting run. */
export const RUNG_METAPHOR: Record<string, string> = {
  '300k': 'the towing tank', '1m': 'the measured mile', '9m': 'the sea trial',
  '21m': 'the coasting run', '50m': 'the crossing', '100m': 'the ocean', '350m': 'the new world',
};
export const rungName = (preset: string, fallback = ''): string => RUNG_METAPHOR[preset] || fallback || preset;
/** A rung called what its class is called says the name once (the card's title), not again before its job. */
const sameName = (a: string, b: string): boolean => (a || '').trim().toLowerCase() === (b || '').trim().toLowerCase();
/** The fal image each rung wears (backend/thorp/dash/art/generate_art.py, LADDER; the two smallest wear
 *  their class plates, CLASSES; the 9m and 21m wear theirs since 12 November, and landfall.png and
 *  passage.png stay on disk unused). */
export const RUNG_ART: Record<string, string> = {
  '300k': 'towing-tank', '1m': 'measured-mile', '9m': 'sea-trial',
  '21m': 'coasting-run', '50m': 'crossing', '100m': 'ocean', '350m': 'new_world',
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
