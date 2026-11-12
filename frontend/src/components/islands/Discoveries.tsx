// Discoveries (UI.md "Tricks of the trade"), as a typed client island. It serves every discoveries route
// from one page — the index with its four subtabs (overview, stars, skills, tests), one trick
// (/discoveries/<trick>), one chain (/discoveries/chains/<key>) and the traits (/discoveries/traits) —
// reading the route itself, as the old router did. The chaining method lives in Tests and the registry
// in Skills (10 November: the two tabs deprecated, their content folded in and their old addresses
// redirected). The dense renderers are
// in scripts/views/discoveries.ts; this file owns the shell (ported from components/Discoveries.astro),
// the route and the data. Charts (ECharts) are imported lazily inside the effects: the page is server-
// rendered, and nothing that touches document may be imported at module load.
//
// Since 12 November the island lives in the two orbitals (lib/discoveryPaths.ts): Demiton's discoveries at
// /orbitals/demiton/discoveries (and the shipyard's Charting, the same page) are what our fleet found; Masaq'
// Reach's at /orbitals/masaq/discoveries are the head kinds research has named, the census's cards beyond the
// sixteen and the Qwen 4B mapping. The old /discoveries addresses are sent to their new homes.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { btnCls, cardCls, checkCls, crumbCls, emptyCls, selectCls } from '@/lib/ui';
import { routePath, sectionProps, useApi, useRoute } from '@/lib/useApi';
import { shipHash } from '@/scripts/router';
import { esc } from '@/lib/format';
import { DEMITON_DISCOVERIES as DB, MASAQ_DISCOVERIES as MB, MASAQ_SUBS, QWEN4B_PAGE, newHome, type MasaqSub } from '@/lib/discoveryPaths';
import SectionNav from '../SectionNav';
import { AxisDoors, FieldMapView } from '../FieldMap';
import { axisBySlug, ourSection } from '@/lib/fieldMap';
import { TabNav } from '../TabNav';
import {
  cardDeckHtml,
  chainPageHtml,
  chainsTableHtml,
  drawBridge,
  drawStarDeviation,
  drawStarJourney,
  drawScaffoldChart,
  drawTrickChart,
  emptyChart,
  headFamilies,
  headsHtml,
  methodHtml,
  scaffoldHtml,
  scaffoldRows,
  scaffoldSummary,
  skillLadderHtml,
  starGridHtml,
  starsCardsHtml,
  trickBands,
  trickPageHtml,
  trickRouteHtml,
  trickRowsHtml,
  traitsHtml,
  twoFactTests,
  twoFactsHtml,
  cardsBeyondHtml,
  type DiscData,
  type Rung,
  type StarPoint,
} from '@/scripts/views/discoveries';

type Sub = 'overview' | 'skills' | 'quantum-tests' | 'stars';
type DView = 'index' | 'trick' | 'chain' | 'traits' | 'domain' | 'masaq' | 'map' | 'landing' | 'pending';

interface Parsed {
  view: DView;
  sub: Sub;
  trick: string | null;
  chain: string | null;
  domain: string | null;
  masaq?: MasaqSub;
  axis?: string; // the field map (13 November): an axis's address segment, and a category of it
  cat?: string | null;
}

const DSUBS: Sub[] = ['overview', 'skills', 'quantum-tests', 'stars'];
const DECK_VARIANTS: Record<string, string> = {
  both: 'both premises', first: 'first only', second: 'second only', swapped: 'swapped',
  padded: 'padded', one_hop: 'one hop', three_hop: 'three hops',
};
// the Tests tab: the four quantum chains, the two item decks, and the chaining two facts method
type TestTab = 'quantum' | 'logic' | 'cause' | 'chaining';
const TEST_TABS: { key: TestTab; label: string }[] = [
  { key: 'quantum', label: 'Quantum tests' },
  { key: 'logic', label: 'The 40 logic items' },
  { key: 'cause', label: 'The 96 cause items' },
  { key: 'chaining', label: 'Chaining two facts' },
];
// Demiton's stars: what our ships have lit. The census, the personas, the cards beyond the sixteen and the Qwen
// mapping moved to the Reach (12 November); their old ?tab= addresses are sent there (discoveryPaths.newHome).
type StarTab = 'heads' | 'cards';
const STAR_TABS: { key: StarTab; label: string }[] = [
  { key: 'heads', label: 'Lit by size' },
  { key: 'cards', label: 'The 16 cards' },
];
// Masaq' Reach's discoveries: the head kinds research has named, the census's cards beyond the sixteen, the Qwen mapping
const MASAQ_TABS: { key: MasaqSub; label: string }[] = [
  { key: 'kinds', label: 'Head kinds' },
  { key: 'cards', label: 'Cards beyond the sixteen' },
  { key: 'unsorted', label: 'Still to be sorted' },
];
const masaqHref = (s: MasaqSub): string => (s === 'kinds' ? MB : `${MB}/${s}`);
// the four doors of Discoveries, in the order they are read (the section row uses the same labels)
const DISC_TABS: { key: Sub; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'stars', label: 'Stars' },
  { key: 'skills', label: 'Skills' },
  { key: 'quantum-tests', label: 'Tests' },
];
// the cards that are not one head (or not a head at all): the split the audit has to resolve
const HEADLESS_CARDS = [
  { card: 'bridge', kind: 'latent state', why: 'the middle term at the conclusion, read as a curve over layers — not a head' },
  { card: 'counter', kind: 'probe', why: 'sentence position read linearly from the residual stream' },
  { card: 'scales', kind: 'behaviour', why: 'the logic deck’s order gain, with no single head named' },
  { card: 'nevermore', kind: 'circuit', why: 'the induction circuit — many heads, not one' },
  { card: 'mover', kind: 'circuit', why: 'the name-mover circuit — usually a pair of heads' },
  { card: 'comparator', kind: 'pair', why: 'two heads in a layer, read on their shared score' },
];
const DOMAINS: Record<string, { title: string; waypoint: string; image: string; blurb: string; links: [string, string][] }> = {
  physics: {
    title: 'Physics', waypoint: 'physics', image: '/art/fall-physics.svg',
    blurb: 'The physical world in numbers: intuition, school mechanics, college physics, graduate questions and the quantum problems beyond.',
    links: [[`${DB}/tests`, 'The quantum tests'], [`${DB}/skills`, 'The whole ladder']],
  },
  maths: {
    title: 'Maths', waypoint: 'mathematics', image: '/art/fall-maths.svg',
    blurb: 'Symbols and proof: algebra, competition problems, calculus and the proofs that hold them together.',
    links: [[`${DB}/skills`, 'The whole ladder and every trick']],
  },
  reasoning: {
    title: 'Reasoning', waypoint: 'reasoning', image: '/art/fall-reasoning.svg',
    blurb: 'Putting what is known to work: deduction, word problems, learning a task from examples and planning a route through it.',
    links: [[`${DB}/tests?test=chaining`, 'Chaining two facts'], [`${DB}/skills`, 'The whole ladder']],
  },
  philosophy: {
    title: 'Philosophy', waypoint: 'discovery', image: '/art/fall-philosophy.svg',
    blurb: "The ideas the books do not yet hold: the explorer's four tests — the Origin, energy, Mendeleev's gaps and the eternal return — and the quanta beyond them.",
    links: [[`${DB}/tests`, 'The quantum tests'], [`${DB}/skills`, 'The whole ladder']],
  },
};

// The charting section's own addresses: the same four tabs, kept under /shipyard/charting so a click there
// stays in charting (10 November, Justin: "it should still be charting"). 'tells' is the charting name for
// the stars tab; 'stars', 'quantum', 'two-facts' and 'registry' are accepted as aliases and redirected.
const CHARTING_SUBS: Record<string, Sub> = {
  '': 'overview', overview: 'overview', skills: 'skills', quantum: 'skills',
  tests: 'quantum-tests', 'two-facts': 'quantum-tests', registry: 'skills',
  tells: 'stars', stars: 'stars', cards: 'stars',
};
const chartingHref = (s: Sub): string =>
  `/shipyard/charting${s === 'overview' ? '' : '/' + (s === 'stars' ? 'tells' : s === 'skills' ? 'skills' : s === 'quantum-tests' ? 'tests' : s)}`;

const parse = (route: string): Parsed => {
  const bits = route.split('?')[0].split('/').filter(Boolean);
  // Masaq' Reach's discoveries: one view with its three tabs
  if (bits[0] === 'orbitals' && bits[1] === 'masaq' && bits[2] === 'discoveries') {
    const m = (MASAQ_SUBS as readonly string[]).includes(bits[3] || '') ? (bits[3] as MasaqSub) : 'kinds';
    return { view: 'masaq', sub: 'skills', trick: null, chain: null, domain: null, masaq: m };
  }
  // Demiton's discoveries read as the old /discoveries did: the same tabs, tricks, chains and doors under its base
  if (bits[0] === 'orbitals' && bits[1] === 'demiton' && bits[2] === 'discoveries') bits.splice(0, 3, 'discoveries');
  const at = (i: number): string | undefined => (bits[i] ? decodeURIComponent(bits[i]) : undefined);
  // the field on two axes (13 November): /<axis>, then /<axis>/<category> (lib/fieldMap.ts)
  if (bits[0] === 'discoveries' && axisBySlug(bits[1])) {
    return { view: 'map', sub: 'overview', trick: null, chain: null, domain: null, axis: bits[1], cat: at(2) || null };
  }
  // the cards moved to the shipyard's charting section (9 November, Justin: "this /discoveries/cards needs
  // to move to /shipyard/charting"): the same island, reached from the yard
  if (bits[0] === 'shipyard' && bits[1] === 'charting') {
    const sub = CHARTING_SUBS[bits[2] || ''] || 'overview';
    return { view: 'index', sub, trick: null, chain: null, domain: null };
  }
  // not yet read (the server's render): no view, so the landing does not flash another page first
  if (bits[0] !== 'discoveries') return { view: 'pending', sub: 'overview', trick: null, chain: null, domain: null };
  const b = at(1);
  const c = at(2);
  if (b === 'chains' && c) return { view: 'chain', sub: 'skills', trick: null, chain: c, domain: null };
  // Demiton's root is the landing, the two axis cards (13 November); what was its overview is the jobs page
  if (!b || b === 'overview') return { view: 'landing', sub: 'overview', trick: null, chain: null, domain: null };
  if (b === 'jobs') return { view: 'index', sub: 'overview', trick: null, chain: null, domain: null };
  // the two deprecated tabs still answer; canonicalPath rewrites the address to their new home
  if (b === 'two-facts') return { view: 'index', sub: 'quantum-tests', trick: null, chain: null, domain: null };
  if (b === 'registry') return { view: 'index', sub: 'skills', trick: null, chain: null, domain: null };
  if (b === 'quantum') return { view: 'index', sub: 'skills', trick: null, chain: null, domain: null };
  if (b === 'tests') return { view: 'index', sub: 'quantum-tests', trick: null, chain: null, domain: null };
  // the cards and the tells are one page now: Stars (14 November, the heads and the cards side by side)
  if (b === 'cards' || b === 'stars') return { view: 'index', sub: 'stars', trick: null, chain: null, domain: null };
  if ((DSUBS as string[]).includes(b)) return { view: 'index', sub: b as Sub, trick: null, chain: null, domain: null };
  if (b === 'traits') return { view: 'traits', sub: 'skills', trick: null, chain: null, domain: null };
  if (b === 'mathematics') return { view: 'domain', sub: 'overview', trick: null, chain: null, domain: 'maths' };
  if (b in DOMAINS) return { view: 'domain', sub: 'overview', trick: null, chain: null, domain: b };
  return { view: 'trick', sub: 'skills', trick: b, chain: null, domain: null };
};

const subHref = (s: Sub, charting: boolean): string => {
  if (charting) return chartingHref(s);
  if (s === 'overview') return `${DB}/jobs`;
  if (s === 'stars') return `${DB}/stars`;
  if (s === 'skills') return `${DB}/skills`;
  return `${DB}/tests`;
};

/** The page an address is drawn on: a Demiton address (its base or the shipyard's Charting), the Reach's, or
 *  another page entirely. A move between two of them is a page load, so the crumbs and the header follow. */
const pageOf = (p: string): 'demiton' | 'charting' | 'masaq' | 'elsewhere' => {
  const path = p.split('?')[0];
  if (path === DB || path.startsWith(`${DB}/`)) return 'demiton';
  if (path === '/shipyard/charting' || path.startsWith('/shipyard/charting/')) return 'charting';
  if (path === MB || path.startsWith(`${MB}/`)) return 'masaq';
  return 'elsewhere';
};

// The two deprecated tabs (10 November): their old addresses still answer and are rewritten to where the
// content lives now. A deep link to chaining opens the Tests tab on the chaining method.
const canonicalPath = (route: string): string | null => {
  // an old /discoveries address, or a Stars tab that moved to the Reach (12 November)
  const moved = newHome(route);
  if (moved) return moved;
  const bits = route.split('?')[0].split('/').filter(Boolean);
  if (bits[0] === 'orbitals' && bits[1] === 'demiton' && bits[2] === 'discoveries') {
    if (bits[3] === 'two-facts') return `${DB}/tests?test=chaining`;
    if (bits[3] === 'registry') return `${DB}/skills`;
  }
  if (bits[0] === 'shipyard' && bits[1] === 'charting') {
    if (bits[2] === 'two-facts') return '/shipyard/charting/tests?test=chaining';
    if (bits[2] === 'registry') return '/shipyard/charting/skills';
  }
  return null;
};

const openEssay = async (name: string): Promise<void> => {
  const { openEssay: open } = await import('@/lib/reader');
  await open(name);
};


/** The four questions: name, what it teaches, its mark. */
const questionsRows = (d: any): string => (d?.questions || [])
  .map((q: any) => `<tr><td><b>${esc(q.name)}</b></td><td class="s">${esc(q.teaches || '')}</td><td>${q.mark}</td></tr>`)
  .join('') || '<tr><td colspan="3" class="s">reading the questions…</td></tr>';

/** The jobs: seeded layer against found layer, first lit, per size. */
const atlasRows = (d: any): string => (d?.cards || []).map((c: any) => `<tr>
    <td><b>${esc(c.name)}</b> <span class="s">${esc(c.suit)}</span></td>
    <td class="s">${esc(c.job || '')}${c.needs && c.needs.length ? ` <span class="s">needs ${esc(c.needs.join(', '))}</span>` : ''}</td>
    <td>${c.mark ?? '–'}</td><td>${esc(c.tier || 'untested')}</td>
    ${(d.sizes || []).map((x: string) => {
      const f = (c.found || {})[x] || null, sd = (c.seeded || {})[x];
      const seeded = sd == null ? '<span class="s">–</span>' : `L${sd}`;
      const found = f && f.layer != null
        ? ` · <b>L${f.layer}</b> <span class="s">${f.depth}%${f.first_lit != null ? `, ${f.first_lit}` : ''}</span>`
        : ' · <span class="s">not found</span>';
      return `<td>${seeded}${found}</td>`;
    }).join('')}
  </tr>`).join('') || '<tr><td colspan="8" class="s">reading the deck…</td></tr>';


/** The sieve: each card as a band by depth (0-100% of the ship), one column per size. Cards are ordered by
 *  where the fleet finds them, so a card's row is its usual band down the stack whatever the ship's height. */
const sieveHtml = (d: any): string => {
  if (!d?.cards) return '<div class="s">reading the sieve…</div>';
  const sizes: string[] = d.sizes || [];
  const layers: Record<string, number> = d.layers || {};
  const cardsInput: any[] = d.cards || [];
  const rows = cardsInput
    .map((c: any) => {
      const ds = sizes.map((x) => ((c.found || {})[x] || {}).depth).filter((v: any) => v != null) as number[];
      return { c, mean: ds.length ? ds.reduce((a, b) => a + b, 0) / ds.length : 999, min: Math.min(...ds), max: Math.max(...ds) };
    })
    .sort((a, b) => a.mean - b.mean);
  const head = `<div class="svrow svhead"><span class="svname">job</span>${sizes.map((x) =>
    `<span class="svcol">${esc(x)} <span class="s">${layers[x]} layers</span></span>`).join('')}</div>`;
  const body = rows.map(({ c, min, max }) => `<div class="svrow">
      <span class="svname">${esc(c.name)} <span class="s">${esc(c.tier || '')}</span></span>
      ${sizes.map((x) => {
        const f = (c.found || {})[x] || null;
        if (!f || f.depth == null) return '<span class="svcol"><span class="svtrack"><span class="svband" style="opacity:.12"></span></span><span class="s">–</span></span>';
        const band = Number.isFinite(min) && Number.isFinite(max) && max > min
          ? `<span class="svband" style="left:${min}%;width:${max - min}%"></span>` : '';
        return `<span class="svcol"><span class="svtrack">${band}<i class="svdot" style="left:${f.depth}%" title="${esc(x)}: L${f.layer} of ${layers[x]} (${f.depth}%)"></i></span><span class="s">L${f.layer} · ${f.depth}%</span></span>`;
      }).join('')}
    </div>`).join('');
  return `<div class="sieve">${head}${body}</div><div class="s sienote">One row a job, one column a ship size; the dot is where that size's tell was found, the shaded band the range across the fleet, and the axis is depth from the first layer (left) to the last (right).</div>`;
};

export default function Discoveries() {
  const mounted = useRoute();
  const [nav, setNav] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const route = nav ?? mounted;
  const parsed = parse(route);
  const { view, sub, trick: trickKey, chain: chainKey } = parsed;
  const domain = parsed.domain ? DOMAINS[parsed.domain] : null;
  const inCharting = route.split('?')[0].startsWith('/shipyard/charting');
  // a former tab of Demiton's discoveries is a page of its own now, titled by its entry on the axes (lib/fieldMap.ts)
  const section = view === 'index' && !inCharting ? ourSection(sub) : null;
  const masaqSub: MasaqSub = parsed.masaq || 'kinds';

  // the route the old router read: the hash first, then the path (a pasted path is answered by the server).
  // `ready` gates the sub-view endpoints: the first render is server-consistent (the default view), so
  // without it a stars or chain page would fetch a tab's payloads (the slow bootstrap) for nothing.
  // The two deprecated tabs' old addresses are rewritten to their new home on the way in.
  useEffect(() => {
    const read = (): void => {
      const p = routePath();
      // the query too: a Stars tab that moved to the Reach is named by it (?tab=census)
      const c = canonicalPath(p + (location.hash.startsWith('#/') ? '' : location.search));
      // an address whose new home is another page (the Reach, a model's page): go there, not draw it here
      if (c && pageOf(c) !== pageOf(p)) {
        window.location.replace(c);
        return;
      }
      if (c) {
        try {
          history.replaceState(null, '', c);
        } catch {
          /* a file:// page cannot replace the URL */
        }
      }
      setNav(c || p);
    };
    read();
    setReady(true);
    window.addEventListener('popstate', read);
    window.addEventListener('hashchange', read);
    return () => {
      window.removeEventListener('popstate', read);
      window.removeEventListener('hashchange', read);
    };
  }, []);

  const go = (p: string): void => {
    const target = canonicalPath(p) || p;
    // another page (Demiton to the Reach, or out to a model's page): load it, so the crumbs and header follow
    if (pageOf(target) !== pageOf(route)) {
      window.location.href = target;
      return;
    }
    try {
      history.pushState(null, '', target);
    } catch {
      /* a file:// page cannot push; the link still works */
    }
    setNav(target);
  };

  // the Tests tab: the four quantum chains, the two item decks, and the chaining method
  const [testsTab, setTestsTab] = useState<TestTab>('quantum');
  const disc = useApi<DiscData>('/api/discoveries', 30000);
  const ladder = useApi<any>('/api/ladder', 300000);
  const onStars = ready && view === 'index' && sub === 'stars';
  const onCards = ready && view === 'index' && sub === 'stars';
  const onTests = ready && view === 'index' && sub === 'quantum-tests';
  const onChaining = onTests && testsTab === 'chaining';
  const sq = useApi<any>(onChaining ? '/api/smoking_qwen' : null, 120000);
  const lb = useApi<any>(onChaining ? '/api/leaderboard' : null, 120000);
  const starPoints = useApi<{ points: StarPoint[] }>(onStars ? '/api/star_points' : null, 120000);
  const starDev = useApi<{ cards: any[] }>(onStars ? '/api/stars_deviation' : null, 120000);
  const deck = useApi<{ cards: any[] }>(onCards ? '/api/card_deck' : null, 120000);
  const decksApi = useApi<any>(onTests && (testsTab === 'logic' || testsTab === 'cause') ? '/api/decks' : null, 300000);
  const atlas = useApi<any>(view === 'index' && sub === 'overview' ? '/api/deck_atlas' : null, 300000);
  const chainsApi = useApi<any[]>('/api/chains', 120000, onTests && testsTab === 'quantum');
  const bridge = useApi<any>(onStars ? '/api/bridge' : null, 120000);
  // the Reach's tabs: the census of Qwen3 4B feeds the cards beyond the sixteen (its heads and personas are read
  // on its own page now, QWEN4B_PAGE)
  const onMasaq = ready && view === 'masaq';
  const census = useApi<any>(onMasaq && masaqSub === 'cards' ? '/api/heads?model=mlx-community%2FQwen3-4B-4bit' : null, 300000);

  const d = disc.data;
  const rungs: Rung[] = useMemo(() => (ladder.data?.rungs || []).map((r: any) => ({ preset: r.preset, name: r.name, total: r.total })), [ladder.data]);
  // the Stars tab: the heads, the cards, and what is still to be sorted between them
  const [starsTab, setStarsTab] = useState<StarTab>(() => {
    try {
      const t = new URLSearchParams(window.location.search).get('tab');
      if (t === 'heads' || t === 'cards') return t;
    } catch { /* no window */ }
    return 'heads';
  });
  const [deckVariant, setDeckVariant] = useState('both');
  const [deckRelation, setDeckRelation] = useState('');
  const deckSel = useMemo(() => (testsTab === 'logic' || testsTab === 'cause' ? (decksApi.data?.decks || []).find((x: any) => x.key === testsTab) || null : null), [decksApi.data, testsTab]);
  const deckRows = useMemo(() => (deckSel?.items || []).filter((it: any) => !deckRelation || it.relation === deckRelation), [deckSel, deckRelation]);
  // a test tab is a link: /discoveries/tests?test=cause opens the cause deck, ?test=chaining the chaining
  // method (the old ?deck= form still answers). The switcher writes it back.
  useEffect(() => {
    const search = typeof window !== 'undefined' ? window.location.search : '';
    const q = new URLSearchParams(search.length ? search : route.split('?')[1] || '');
    const t = q.get('test') ?? q.get('deck');
    setTestsTab(t === 'logic' || t === 'cause' || t === 'chaining' ? t : 'quantum');
  }, [route]);
  const pickTest = (k: TestTab): void => {
    setTestsTab(k);
    setDeckRelation('');
    try {
      const u = new URL(window.location.href);
      u.searchParams.delete('deck');
      if (k === 'quantum') u.searchParams.delete('test');
      else u.searchParams.set('test', k);
      history.replaceState(null, '', u);
    } catch { /* a file:// page cannot replace the URL */ }
  };
  // a Stars tab is a link too: /discoveries/stars?tab=unsorted
  useEffect(() => {
    const search = typeof window !== 'undefined' ? window.location.search : '';
    const t = new URLSearchParams(search).get('tab') ?? new URLSearchParams(route.split('?')[1] || '').get('tab');
    if (t === 'heads' || t === 'cards') setStarsTab(t);
  }, [route]);
  const pickStar = (k: StarTab): void => {
    setStarsTab(k);
    try {
      const u = new URL(window.location.href);
      if (k === 'heads') u.searchParams.delete('tab');
      else u.searchParams.set('tab', k);
      history.replaceState(null, '', u);
    } catch { /* a file:// page cannot replace the URL */ }
  };

  // the trick page: the fleet trick behind the known trick names the chart's payload
  const pageInfo = useMemo(() => (d && view === 'trick' ? trickPageHtml(d, rungs, trickKey) : null), [d, rungs, view, trickKey]);
  const ftKey = pageInfo?.chart?.fleetKey ?? null;
  const trickApi = useApi<any>(ftKey ? `/api/trick?key=${encodeURIComponent(ftKey)}` : null, 0);
  const pairKey = pageInfo?.pair?.chart?.fleetKey ?? null;
  const pairApi = useApi<any>(pairKey ? `/api/trick?key=${encodeURIComponent(pairKey)}` : null, 0);
  const chainApi = useApi<any>(chainKey ? `/api/chain?key=${encodeURIComponent(chainKey)}` : null, 0);

  // two facts: one example pair from each chaining test (/api/chain), fetched once per chain set
  const tests = useMemo(() => (d ? twoFactTests(d) : []), [d]);
  const chainSig = tests.map((t) => t.chain).join('|');
  const pulled = useRef<Record<string, any>>({});
  const [pulls, setPulls] = useState<(any | null)[]>([]);
  useEffect(() => {
    if (view !== 'index' || sub !== 'quantum-tests' || testsTab !== 'chaining' || !chainSig) return;
    let live = true;
    const keys = chainSig.split('|');
    const get = (k: string): Promise<any | null> =>
      pulled.current[k]
        ? Promise.resolve(pulled.current[k])
        : fetch(`/api/chain?key=${encodeURIComponent(k)}`)
            .then((r) => (r.ok ? r.json() : null))
            .then((x) => {
              if (x) pulled.current[k] = x;
              return x;
            })
            .catch(() => null);
    void Promise.all(keys.map(get)).then((v) => {
      if (live) setPulls(v);
    });
    return () => {
      live = false;
    };
  }, [view, sub, testsTab, chainSig]);

  // the chain toggle: a per-viewer choice, remembered (thorp.chainref)
  const [chainRef, setChainRef] = useState(false);
  useEffect(() => {
    try {
      setChainRef(localStorage.getItem('thorp.chainref') === 'on');
    } catch {
      /* no storage */
    }
  }, []);
  const setRef = (on: boolean): void => {
    setChainRef(on);
    try {
      localStorage.setItem('thorp.chainref', on ? 'on' : 'off');
    } catch {
      /* no storage */
    }
  };

  // filters, held in the island (the old panels rebuilt their selects' options each draw)
  const [waypoint, setWaypoint] = useState('');
  useEffect(() => {
    if (view !== 'index' || sub !== 'skills') return;
    const search = typeof window !== 'undefined' ? window.location.search : '';
    setWaypoint(new URLSearchParams(search).get('waypoint') || '');
  }, [route, view, sub]);
  const [band, setBand] = useState('');
  const [family, setFamily] = useState('');
  const [question, setQuestion] = useState<{ chain: string; step: number } | null>(null);
  useEffect(() => { setQuestion(null); }, [sub]);
  useEffect(() => {
    if (!question) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent): void => { if (e.key === 'Escape') setQuestion(null); };
    window.addEventListener('keydown', onKey);
    return () => { document.body.style.overflow = prev; window.removeEventListener('keydown', onKey); };
  }, [question]);

  // the charts. Each runs only on the subtab that shows it, after its data has arrived.
  useEffect(() => {
    if (view === 'index' && sub === 'stars' && starsTab === 'heads' && starPoints.data) void drawStarJourney(starPoints.data.points);
  }, [view, sub, starsTab, starPoints.data]);
  useEffect(() => {
    if (view === 'index' && sub === 'stars' && starsTab === 'heads' && starDev.data) void drawStarDeviation(starDev.data.cards);
  }, [view, sub, starsTab, starDev.data]);
  useEffect(() => {
    if (view === 'index' && sub === 'stars' && starsTab === 'heads' && bridge.data) void drawBridge(bridge.data, rungs);
  }, [view, sub, starsTab, bridge.data, rungs]);
  // the chart is redrawn only when a reading changes, not on every poll: the old drawers keyed on the
  // readings too, and a redraw resets the zoom
  const drawn = useRef<Record<string, string>>({});
  const trickSig = trickApi.data ? `${pageInfo?.chart?.fleetKey}|${(trickApi.data.runs || []).map((r: any) => `${r.run_id}:${r.value?.length}:${r.value?.[r.value.length - 1]}`).join(',')}` : '';
  useEffect(() => {
    if (view !== 'trick' || !pageInfo?.chart || !trickApi.data) return;
    if (drawn.current.trick === trickSig) return;
    drawn.current.trick = trickSig;
    void drawTrickChart('trickchart', trickApi.data, { name: pageInfo.chart.name, reference: pageInfo.chart.reference }, rungs.map((r) => r.preset));
  }, [view, pageInfo, trickApi.data, trickSig, rungs]);
  const pairSig = pairApi.data ? `${pageInfo?.pair?.chart?.fleetKey}|${(pairApi.data.runs || []).map((r: any) => `${r.run_id}:${r.value?.length}:${r.value?.[r.value.length - 1]}`).join(',')}` : '';
  useEffect(() => {
    if (view !== 'trick' || !pageInfo?.pair) return;
    if (!pageInfo.pair.chart) {
      if (pageInfo.pair.empty) void emptyChart('trickpairchart', pageInfo.pair.empty);
      return;
    }
    if (!pairApi.data || drawn.current.pair === pairSig) return;
    drawn.current.pair = pairSig;
    void drawTrickChart('trickpairchart', pairApi.data, { name: pageInfo.pair.chart.name, reference: pageInfo.pair.chart.reference }, rungs.map((r) => r.preset));
  }, [view, pageInfo, pairApi.data, pairSig, rungs]);

  // the scaffold across every model: held heads, the fade, and what dropped. Only voyages whose spec
  // pinned heads are here; the table still lists every model, so a gap is visible (10 November).
  const scaffThreshold = trickApi.data?.threshold ?? 0;
  const scaffRows = useMemo(() => (view === 'trick' && trickApi.data ? scaffoldRows(trickApi.data, scaffThreshold) : []), [view, trickApi.data, scaffThreshold]);
  const scaffSummary = useMemo(() => (scaffRows.length ? scaffoldSummary(scaffRows, rungs.map((r) => r.preset), scaffThreshold) : []), [scaffRows, rungs, scaffThreshold]);
  const scaffSig = scaffRows.map((r) => `${r.run_id}:${r.held}:${r.after}`).join(',');
  useEffect(() => {
    if (view !== 'trick' || !scaffRows.length || drawn.current.scaffold === scaffSig) return;
    drawn.current.scaffold = scaffSig;
    void drawScaffoldChart('scaffoldchart', scaffSummary, scaffThreshold, pageInfo?.chart?.name || 'reading');
  }, [view, scaffRows, scaffSummary, scaffSig, scaffThreshold]);

  const chainPage = useMemo(
    () => (d && view === 'chain' ? chainPageHtml(d, rungs, chainKey, chainApi.data, chainRef) : null),
    [d, rungs, view, chainKey, chainApi.data, chainRef],
  );

  // Build only the panel the page is showing: /api/discoveries is a multi-megabyte payload, and
  // rendering every sub-view's HTML on every tab made the first paint of Cards or Skills wait on
  // traits, stars and the registry too (10 November).
  const onSkills = view === 'index' && sub === 'skills';
  const traits = useMemo(() => (d && view === 'traits' ? traitsHtml(d) : null), [d, view]);
  const stars = useMemo(() => (d && sub === 'stars' ? starsCardsHtml(d) : ''), [d, sub]);
  const grid = useMemo(() => (d && sub === 'stars' ? starGridHtml(d, rungs) : null), [d, sub, rungs]);
  // the head kinds no card names (the Reach's head kinds tab): the 21 known heads minus the starred ones
  const uncarded = useMemo(() => (d && view === 'masaq' ? (d.known_heads || []).filter((h: any) => !h.star) : []), [d, view]);
  const chains = useMemo(() => (d && onSkills ? chainsTableHtml(d, rungs, chainRef) : null), [d, onSkills, rungs, chainRef]);
  const route1 = useMemo(() => (d && onSkills ? trickRouteHtml(d) : ''), [d, onSkills]);
  const skillLadder = useMemo(() => (d && onSkills ? skillLadderHtml(d) : ''), [d, onSkills]);
  const domainSkills = useMemo(() => (d && domain ? d.known_tricks.filter((t) => t.waypoint === domain.waypoint) : []), [d, domain]);
  const registry = useMemo(() => (d && onSkills ? trickRowsHtml(d, rungs, waypoint, band) : null), [d, onSkills, rungs, waypoint, band]);
  // the star chart (every head kind research has named) is the Reach's now
  const heads = useMemo(() => (d && view === 'masaq' && masaqSub === 'kinds' ? headsHtml(d, rungs, family) : null), [d, view, masaqSub, rungs, family]);
  const method = useMemo(() => (d && onChaining ? methodHtml(d, 'chaining', rungs) : null), [d, onChaining, rungs]);
  const tf = useMemo(() => (d && onChaining && sq.data && lb.data ? twoFactsHtml(d, sq.data, lb.data, pulls) : null), [d, onChaining, sq.data, lb.data, pulls]);

  const goShip = (id: string): void => {
    const lr = (ladder.data?.runs || []).find((r: any) => r.run_id === id || r.name === id);
    window.location.href = lr && lr.ship_key ? shipHash(lr.ship_key, lr.name) : shipHash(lr ? lr.name : id);
  };

  const onClick = (e: ReactMouseEvent): void => {
    const t = e.target as HTMLElement;
    const essay = t.closest('[data-essay]') as HTMLElement | null;
    if (essay) {
      e.preventDefault();
      void openEssay(essay.dataset.essay || '');
      return;
    }
    const a = t.closest('a') as HTMLAnchorElement | null;
    if (a) {
      const href = a.getAttribute('href') || '';
      // the cards live in the shipyard now, so its links are this island's too: navigate in place
      // rather than reloading the page (9 November: "clicking cards doesn't open the tab")
      // (and an old /discoveries link still drawn by a renderer is sent to its new home, in place)
      if (href.startsWith('/discoveries') || pageOf(href) !== 'elsewhere') {
        e.preventDefault();
        go(href);
      }
      return;
    }
    const trickRow = t.closest('tr[data-trick]') as HTMLElement | null;
    if (trickRow) {
      e.preventDefault();
      go(`${DB}/${trickRow.dataset.trick}`);
      return;
    }
    const traitRow = t.closest('tr[data-run]') as HTMLElement | null;
    if (traitRow) {
      e.preventDefault();
      goShip(traitRow.dataset.run || '');
    }
  };

  return (
    <div {...sectionProps('discoveries')} onClick={onClick}>
      <SectionNav />
      {/* the charting section lives under Orbitals > Demiton > Shipyard: its own title and its four tabs sit
          under the section row, while Discoveries' own tabs are the section row itself */}
      {inCharting ? (
        <h1>
          <a className={crumbCls('back')} href="/shipyard">← shipyard</a>{' '}
          Charting{' '}
          <span className="q">sorting out the charts the voyage is planned on: the route, the stars, and the suits</span>
        </h1>
      ) : view === 'landing' ? (
        <h1>
          <a className={crumbCls('back')} href="/orbitals/demiton">← Demiton</a>{' '}
          Discoveries{' '}
          <span className="q">what our own fleet has found: the jobs and where the ships do them, the skills on the ladder, the tests that judge them, and the stars our ships have lit. The head kinds research has named, and Qwen3 4B's own census, are in <a href={MB}>Masaq' Reach</a></span>
        </h1>
      ) : null}
      {section ? (
        <h1>
          <a className={crumbCls('back')} href={DB}>← discoveries</a>{' '}
          {section.title}{' '}
          <span className="q">{section.about}</span>
        </h1>
      ) : null}
      {/* ============================== the tricks of the trade */}
      <div className={`dview${view === 'index' ? ' active' : ''}`} data-dview="index">
        {view === 'index' && inCharting ? (
          <TabNav
            id={inCharting ? 'chartingnav' : 'discnav'}
            ariaLabel={inCharting ? 'charting sections' : 'discoveries sections'}
            items={DISC_TABS.map((t) => ({
              key: t.key,
              label: t.label,
              href: subHref(t.key, inCharting),
              active: view === 'index' && sub === t.key,
              data: { 'data-dsub': t.key },
            }))}
          />
        ) : null}

        {/* the tests: the four quantum chains, the two item decks, and how chaining two facts is measured */}
        <div className={`dsub${sub === 'quantum-tests' ? ' active' : ''}`} data-dsub="quantum-tests">
          <p className="q dsubintro">The <b>tests</b>: the four quantum chains, each climbed in six rungs from the keel to the explorer; the two item decks that ask whether a pass is chaining rather than knowledge — the <b>40 logic items</b> over five relations and the <b>96 cause items</b> that widen the one relation Qwen 4B shows a gain on; and <b>chaining two facts</b>, the claim and the method it is judged by.</p>
          <TabNav
            ariaLabel="Tests"
            tablist
            items={TEST_TABS.map((t) => ({
              key: t.key,
              label: t.label,
              active: testsTab === t.key,
              onClick: () => pickTest(t.key),
            }))}
          />
          {testsTab === 'quantum' ? (
            <section className={cardCls(false, 'panel')}>
              <h2>All the layers <span className="note">keel to explorer, smallest rung first; the last rung is the bet itself. ▲/✓ evidence and grades are on the Skills tab; the method is under Chaining two facts</span></h2>
              {chainsApi.error ? <div className={emptyCls()}>the tests could not be read: {chainsApi.error}</div>
                : !chainsApi.data ? <div className={emptyCls()}>reading the tests…</div>
                : <div className="qt">{chainsApi.data.map((ch: any) => (
                  <section className="qtchain" key={ch.key}>
                    <header><h3>{ch.name}</h3><p>{ch.idea}</p></header>
                    <div className="qtladder">{ch.steps.map((st: any, i: number) => (
                      <button type="button" className="qtstep" key={st.key} onClick={() => setQuestion({ chain: ch.key, step: i })}>
                        <span className="n">{i + 1}</span>
                        <b>{st.name}</b>
                        <span className="adds">{st.adds}</span>
                        <em>{st.rung?.name || st.rung?.preset || '–'} · {st.pairs?.length || 0} questions · mark {st.threshold ?? '–'}</em>
                      </button>
                    ))}</div>
                  </section>
                ))}</div>}
            </section>
          ) : testsTab === 'chaining' ? (
            <>
          <section className={cardCls(false, 'panel tfclaim')}>
            <h2>The claim</h2>
            <p className="tflead">A Nothing up my sleeve model <b>a tenth the size</b> of each 2–4B model chains two facts as well as it does. Chaining two facts is the trick: two premises, neither of which states the conclusion, put together into one that no sentence on the library states. This is how Nothing up my sleeve proves a model can do it, and how the claim is judged.</p>
            <div className="tfstatus" id="tfstatus" dangerouslySetInnerHTML={{ __html: tf?.status || '' }} />
          </section>

          {/* the methodology, as written in fleet.METHODS["chaining"] (rendered as written there, never rewritten here) */}
          <section className={cardCls(false, 'panel method')} id="method" hidden={!method}>
            <h2>Methodology: <span id="mname">{method?.name || ''}</span> <span className="note" id="mstatus">{method?.status || ''}</span></h2>
            <div className="k">The trick</div>
            <p className="mtrick" id="mtrick">{method?.trick || ''}</p>
            <div className="row mrow">
              <div className="mcol">
                <div className="k">Its parts <span className="s">and whether today's tests cover each</span></div>
                <div className="scroll"><table id="mparts" data-nosort><thead><tr><th>part</th><th>what it means</th><th>covered</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: method?.parts || '' }} /></table></div>
              </div>
              <div className="mcol">
                <div className="k">The gaps <span className="s">what the tests cannot yet rule out</span></div>
                <ul className="mgaps" id="mgaps" dangerouslySetInnerHTML={{ __html: method?.gaps || '' }} />
              </div>
            </div>
            <div className="k mt">The controls <span className="s">planned: the logic deck</span></div>
            <div className="scroll"><table id="mcontrols" data-nosort><thead><tr><th>control</th><th>what it does</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: method?.controls || '' }} /></table></div>
            <div className="k mt">The metric</div>
            <p className="mmetric" id="mmetric">{method?.metric || ''}</p>
            <div className="k mt">The cards it needs <span className="s">the stars that do the trick: in the deck (measured; pulsing when lit on any voyage) or planned</span></div>
            <div className="cards mcards" id="mcards" dangerouslySetInnerHTML={{ __html: method?.cards || '' }} />
          </section>

          <h2 className="tfhead">How it is measured and judged today</h2>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">1</div><div className="tfb">
              <h2>The test: matched pairs</h2>
              <p>Each chaining test is 24 pairs. A pair is a passage that ends mid-sentence, then two endings matched in length and plainness: <b className="good">the idea</b>, which follows only if the two facts in the passage are put together, and <b className="bad">a rival</b>, which reads as naturally but does not follow. The passage is split into its <b>premise</b> (the facts) and its <b>frame</b> (the closing words the ending hangs on). There are four chaining tests, one on each of the explorer's chains, 96 pairs in all; a model bets on every pair and never sees any of them in training.</p>
              <div className="scroll"><table className="pairs" id="tfexamples" data-nosort><thead><tr><th>chain</th><th>the passage: premise / <b>frame</b></th><th>the idea</th><th>its rival</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: tf?.examples || '' }} /></table></div>
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">2</div><div className="tfb">
              <h2>The measure: lift, what the premise adds</h2>
              <p>For each ending the model's surprise is read in <b>bits per byte</b> (so tokenisers of different sizes compare). Its <b>preference</b> is the rival's surprise less the idea's: positive means it bets on the idea. But an ending can win on its words alone (a commoner word, a frame that leans one way), so the same preference is read again after <b>the frame alone</b>, and taken away:</p>
              <div className="tfformula">lift = [ bpb(rival | premise + frame) − bpb(idea | premise + frame) ] − [ bpb(rival | frame) − bpb(idea | frame) ]</div>
              <p>So <b>lift is what the premise adds</b>: zero for a model that only knows which words go together, positive only when the facts before the frame move the bet toward the idea. The <b>share right</b> is the fraction of pairs whose lift is above zero.</p>
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">3</div><div className="tfb">
              <h2>Performed: the mark and the share</h2>
              <p>A test is <b>performed</b> when, at the same reading, the mean lift is at least <b id="tfthr">{tf?.thr ?? 0.1}</b> <i>and</i> at least <b id="tfshare">{tf?.share || 'two in three'}</b> pairs are right, so a few large lifts cannot carry a model that is guessing on the rest. The untrained model, same seed, is the <b>floor</b>; untrained and small models sit within about <b id="tfnoise">{tf?.noise ?? 0.03}</b> of zero, which is the <b>noise</b>: nothing inside it counts as a reading.</p>
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">4</div><div className="tfb">
              <h2>The test is graded before it is trusted</h2>
              <p>Each chaining test is the fifth rung of a chain of six (keel to explorer), and a chain is <b>graded</b> only when it gets harder at every rung across a ladder of outside models (Pythia 14m to 410m, Qwen3 0.6B to 4B): no model passes a rung while failing one below it, fewer pass each rung than the one below, and every rung is passed by someone. A test that a small model passes and a large one fails is a broken test, not a discovery. The 2–4B models the claim is judged against <b>never grade the test</b> they are scored on.</p>
              <div className="tfgrades" id="tfgrades" dangerouslySetInnerHTML={{ __html: tf?.grades || '' }} />
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">5</div><div className="tfb">
              <h2>The score: the chaining lift</h2>
              <p>A model's <b>chaining lift</b> is its mean lift on the four chaining tests. It is the one number <a href="/leaderboard">the leaderboard</a> ranks every model on, outside and Nothing up my sleeve alike, read on the same 96 pairs. Below the 50m, where a size is not yet expected to chain, its progress is its <b>climb</b>: on each chain the rungs performed from the bottom, plus the next rung's share of its mark, the mean of the four (0 to 5).</p>
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">6</div><div className="tfb">
              <h2>The forecast: from the sizes Nothing up my sleeve can train to the size it can't</h2>
              <p>The Mac cannot train a 400M model, so the claim is a forecast. Each Nothing up my sleeve size's best voyage gives one point, chaining lift against parameters, and two curves are fitted in log parameters: a <b>straight line</b> (conservative) and a <b>bending curve</b> (probable, since chaining bends upward with size in the outside models). Each is read at a tenth of each competitor's size. A <b>bootstrap</b> (1,000 draws, resampling the pairs and the seeds) gives a 5–95% band and <b>P</b>, the share of draws at or above the competitor's chaining lift. No forecast is made until <b>three sizes</b> are above the noise: a curve through noise extrapolates nothing.</p>
              <p>The method is <b>backtested</b> where the answer is known, fitting the smaller outside models to predict the larger:</p>
              <div id="tfbacktest" dangerouslySetInnerHTML={{ __html: tf?.backtest || '' }} />
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">7</div><div className="tfb">
              <h2>The rule, pre-registered</h2>
              <p>The claim is <b>made</b> when the forecast is trusted (three sizes above the noise) and P ≥ 0.9 on the straight line for <b>every</b> competitor in the 2–4B range. It is <b>probable</b> when only the bending curve reaches 0.9. Anything less is not claimed. The rule was written down before the readings (DECISIONS.md, "Smoking Qwen, pre-registered"), so it cannot bend to them.</p>
            </div>
          </section>
            </>
          ) : (
            <section className={cardCls(false, 'panel')}>
              <h2>{deckSel?.name || 'Reading the deck…'} <span className="note">{deckSel?.about || ''}</span></h2>
              <div className="handtools" data-filters>
                {(deckSel?.relations || []).length > 1 ? (
                  <label className="note">relation
                    <select className={selectCls('ml')} value={deckRelation} onChange={(e) => setDeckRelation(e.target.value)}>
                      <option value="">every relation</option>
                      {(deckSel?.relations || []).map((r: string) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </label>
                ) : null}
                <label className="note">variant
                  <select className={selectCls('ml')} value={deckVariant} onChange={(e) => setDeckVariant(e.target.value)}>
                    {(deckSel?.variants || []).map((v: string) => <option key={v} value={v}>{DECK_VARIANTS[v] || v}</option>)}
                  </select>
                </label>
                <span className="note">{deckRows.length} of {deckSel?.count || 0} items</span>
              </div>
              {decksApi.error ? <div className={emptyCls()}>the decks could not be read: {decksApi.error}</div> : null}
              <div className="scroll">
                <table id="discDeckItems" className="selbooks" data-nosort>
                  <thead><tr><th>#</th><th>item</th><th>relation</th><th>the passage and its frame</th><th>the idea</th><th>its rival</th><th>bridge</th></tr></thead>
                  <tbody>
                    {deckRows.map((it: any, i: number) => {
                      const v = (it.variants || {})[deckVariant] || (it.variants || {}).both || {};
                      return (
                        <tr key={it.item}>
                          <td>{i + 1}</td>
                          <td className="s">{it.item}</td>
                          <td>{it.relation}</td>
                          <td className="s">{v.prompt}</td>
                          <td className="good">{v.idea}</td>
                          <td className="bad">{v.rival}</td>
                          <td>{v.bridge}</td>
                        </tr>
                      );
                    })}
                    {!deckRows.length ? <tr><td colSpan={7} className="s">reading the deck…</td></tr> : null}
                  </tbody>
                </table>
              </div>
              {testsTab === 'cause' ? (
                <p className="note mt">The target is the <b>order-free gain</b>: the worse of the two premise orders against the better single premise, not the raw both-premise lift. The three-hop row is shown but is not part of the target — on the current ships it reads high while the two-hop gain is zero.</p>
              ) : null}
            </section>
          )}
        </div>

        {/* the long road: seven waypoints to quantum mechanics, and the explorer's four discovery chains on it */}
        <div className={`dsub${sub === 'skills' ? ' active' : ''}`} data-dsub="skills">
          <section className={cardCls(false, 'panel')}>
            <h2>Every skill on the ladder <span className="note">the seven steps to quantum mechanics, and the skills charted on each; open a skill for its stars, its readings and its place in the climb. ◆ marks a gate a ship must perform before it moves on</span></h2>
            <div dangerouslySetInnerHTML={{ __html: skillLadder }} />
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The route to quantum physics <span className="note">seven waypoints, each resting on the one before; a waypoint's gate tricks (◆) are the ones a ship must perform before it moves on</span></h2>
            <div className="route" id="trickroute" dangerouslySetInnerHTML={{ __html: route1 }} />
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The discovery chains <span className="note">the explorer's four tests (the Origin, energy, Mendeleev's gaps, the eternal return), each reached in six rungs, one per size, keel to explorer; the last row says what a model at each rung is, according to the four. Every size is scored on every rung; each cell is every size's best lift and best share of pairs right; ✓ is performed under the share rule (lift at 0.1 and two pairs in three right, at the same reading), ▲ passed below its size, ⚠ passed below its size while a bigger size fails it, so the pairs want auditing; Qwen3 0.6B for scale. Under each chain's name, its grade: graded when it gets harder at every rung across all the models read (no model passes a rung it fails below, fewer pass each rung, every rung reached)</span></h2>
            <div className="handtools"><label><input className={checkCls('')} type="checkbox" id="chainrefidx" checked={chainRef} onChange={(e) => setRef(e.target.checked)} /> show the reference ladder <span className="note">(Pythia 14m to 410m and Qwen3 0.6B to 4B, read on the same pairs)</span></label></div>
            <div className="scroll"><table id="chaintable" data-nosort><thead dangerouslySetInnerHTML={{ __html: chains?.head || '' }} /><tbody dangerouslySetInnerHTML={{ __html: chains?.body || '' }} /></table></div>
          </section>
        </div>

        {/* the overview: the cards are jobs, the questions they pass, and where the 0.0.5 fleet puts them */}
        <div className={`dsub${sub === 'overview' ? ' active' : ''}`} data-dsub="overview">
          {/* the four doors are cards of their own under the axes now; the shipyard's Charting keeps them here */}
          {inCharting ? <div className="discdoors">
            <a className="discdoor" href={`${DB}/physics`}>
              <img src="/art/fall-physics.svg" alt="" loading="lazy" />
              <div className="db"><span className="dk">Physics</span><b>The physical world, in numbers</b><p>Mechanics, energy and the quantum horizon: what the books say, and what they do not.</p></div>
            </a>
            <a className="discdoor" href={`${DB}/maths`}>
              <img src="/art/fall-maths.svg" alt="" loading="lazy" />
              <div className="db"><span className="dk">Maths</span><b>Symbols and proof</b><p>Algebra, calculus, competition problems and the proofs that hold them together.</p></div>
            </a>
            <a className="discdoor" href={`${DB}/reasoning`}>
              <img src="/art/fall-reasoning.svg" alt="" loading="lazy" />
              <div className="db"><span className="dk">Reasoning</span><b>Putting knowledge to work</b><p>Deduction, word problems and planning: the step from knowing a fact to using it.</p></div>
            </a>
            <a className="discdoor" href={`${DB}/philosophy`}>
              <img src="/art/fall-philosophy.svg" alt="" loading="lazy" />
              <div className="db"><span className="dk">Philosophy</span><b>The ideas the books do not hold</b><p>The explorer's tests — Origin, energy, Mendeleev's gaps and the eternal return — and the quanta beyond.</p></div>
            </a>
          </div> : null}
          <p className="q dsubintro">The cards are <b>jobs</b> — the work a model must be able to do to pass a question, not a place in the network. A <b>tell</b> is a head that passes the job's mark: it tells you the job is being done, and like any tell it can lie — a pinned head tells you about the pin.</p>
          <section className={cardCls(false, 'panel')}>
            <h2>The four questions <span className="note">the chaining tests: what a model has to do, not what it knows</span></h2>
            <div className="scroll"><table><thead><tr><th>question</th><th>what it teaches</th><th>mark</th></tr></thead>
              <tbody dangerouslySetInnerHTML={{ __html: questionsRows(atlas.data) }} /></table></div>
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The sieve <span className="note">where the fleet finds each job, by depth: one column a size, ordered by the layer the fleet finds it on, so a job's row is its usual band whatever the ship's height</span></h2>
            <div dangerouslySetInnerHTML={{ __html: sieveHtml(atlas.data) }} />
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The jobs, and where the 0.0.5 fleet finds them <span className="note">each card: the job it names, the mark that counts as doing it, its retention (keeper, decayer, untested), the layer the SOP seeds it at — and the layer each size actually found the tell on, with the step it first lit</span></h2>
            <div className="scroll"><table id="deckatlas"><thead><tr><th>job</th><th>what it does</th><th>mark</th><th>keeps</th>{(atlas.data?.sizes || []).map((x: string) => <th key={x}>{x} <span className="s">seeded · found (first lit)</span></th>)}</tr></thead>
              <tbody dangerouslySetInnerHTML={{ __html: atlasRows(atlas.data) }} /></table></div>
          </section>
        </div>

        {/* the stars: all the head kinds and the sixteen cards, side by side */}
        <div className={`dsub${sub === 'stars' ? ' active' : ''}`} data-dsub="stars">
          <p className="q dsubintro">What inside does it? The stars <b>our ships have lit</b>, size by size and against Qwen3 4B, and <b>the sixteen cards</b> a ship is built from. A card is a job; a star is a head that passes the job's mark, and lit shared when the best layer's two strongest heads reach it together. The item decks that score the jobs live under <a href={subHref('quantum-tests', inCharting)}>Tests</a>; every head kind attention research has named, and the cards beyond the sixteen, are in <a href={MB}>Masaq' Reach</a>.</p>
          <TabNav
            ariaLabel="Stars"
            tablist
            items={STAR_TABS.map((t) => ({
              key: t.key,
              label: t.label,
              active: starsTab === t.key,
              onClick: () => pickStar(t.key),
            }))}
          />
          {starsTab === 'cards' ? (
          <>
          <section className={cardCls(false, 'panel')}>
            <h2>The sixteen cards, card by card <span className="note">each card: its suit, its mark (what counts as lit), whether teaching it keeps (keeper, decayer, or never tested), and the best reading any Nothing up my sleeve ship has reached against Qwen3 4B's own</span></h2>
            <div className="scroll"><table id="discCards" className="selbooks"><thead><tr><th>card</th><th>suit</th><th>mark</th><th>keeps</th><th>best Nothing up my sleeve</th><th>Qwen 4B</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: deck.data ? cardDeckHtml(deck.data) : '<tr><td colspan="6" class="s">reading the deck…</td></tr>' }} /></table></div>
          </section>
          <p className="note">The behavioural clusters of Qwen3 4B's census, the cards beyond these sixteen, are in <a href={`${MB}/cards`}>Masaq' Reach</a>.</p>
          </>
          ) : (
          <>
          <section className={cardCls(false, 'panel')}>
            <h2>Lit by size <span className="note">every star Nothing up my sleeve measures, by size of ship: a cell is the size's best reading against the star's mark, green where a voyage has lit it (the first voyage and step on hover), shaded by how close it came where none has; the card judge's verdict beside each</span></h2>
            <div className="scroll"><table id="starclassgrid" data-nosort><thead dangerouslySetInnerHTML={{ __html: grid?.head || '' }} /><tbody dangerouslySetInnerHTML={{ __html: grid?.body || '' }} /></table></div>
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The ten points, as two lines <span className="note">each of the chart's ten points on the horizontal axis, its reading divided by that point's own mark on the vertical: Qwen3 4B, the model that chains, against our smallest ship (the 300k). Above the dotted line a point clears its mark. The gap between the lines is how far we are behind on that point — and where our line is above, we are ahead</span></h2>
            <div className="chart" id="starjourney" />
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>300k against Qwen3 4B <span className="note">the chart as a deviation: each point's reading in our smallest ship less the same reading in a model that chains, divided by the card's own mark. Right of zero is a point we hold better than a 4B; left is a point it holds and we do not. The tier on each row says whether the card is a keeper, a decayer, or one no voyage has ever tested</span></h2>
            <div className="chart" id="stardev" />
          </section>
          <div className="handtools"><button className={btnCls('outline', '')} data-essay="nevermore">Read: what a Nevermore is</button></div>
          <div className="cards" id="starcards" dangerouslySetInnerHTML={{ __html: stars }} />
          <section className={cardCls(false, 'panel')}>
            <h2>The bridge, layer by layer <span className="note">the bridge card is a curve over layers, not one head: how strongly the answer's position carries the middle term two premises share (the slowest deer), read by the soundings at each layer, in nats; one line per voyage that read it, coloured by size; the dotted line is the provisional threshold. Two hops need it resolved in the middle layers, before the second hop: resolved too late, the chain fails</span></h2>
            <div className="chart" id="bridgechart" />
          </section>
          <p className="note">Every kind of head attention research has named, with its state in our fleet, is the <a href={MB}>star chart in Masaq' Reach</a>; Qwen3 4B's 1,152 heads and its persona vectors are on <a href={QWEN4B_PAGE}>its own page</a>.</p>
          </>
          )}
        </div>

        {/* every trick known, measured or not — the registry, folded into Skills (10 November) */}
        <div className={`dsub${sub === 'skills' ? ' active' : ''}`} data-dsub="skills-registry">
          <section className={cardCls(false, 'panel')}>
            <h2>Every trick, measured or not <span className="note">the registry, under the ladder: a trick is what a model can do, judged from outside by its bets; open one for the stars that do it and Nothing up my sleeve's progress, size by size. "The field shows it at" is the size band (one order of magnitude, in parameters) where the trick is documented in standard models, not a proven smallest size; hover a band for the detail. "Nothing up my sleeve's goal size" is the size expected to reach it, about an order of magnitude smaller than the field where the depth it needs allows; ◆ marks a gate, performed before a ship moves on to the next waypoint</span></h2>
            <div className="handtools" data-filters>
              <label className="note" htmlFor="trickfamily">waypoint</label>
              <select className={selectCls('')} id="trickfamily" value={waypoint} onChange={(e) => setWaypoint(e.target.value)}>
                <option value="">all</option>
                {(d?.waypoints || []).map((w) => <option key={w.key} value={w.key}>{w.name}</option>)}
              </select>
              <label className="note" htmlFor="trickband">the field shows it at</label>
              <select className={selectCls('')} id="trickband" data-remember value={band} onChange={(e) => setBand(e.target.value)}>
                <option value="">any size</option>
                {(d ? trickBands(d) : []).map((b) => <option key={b.rank} value={String(b.rank)}>{b.label}</option>)}
              </select>
              <span className="note" id="trickcount">{registry?.count || ''}</span>
            </div>
            <div className="scroll"><table id="tricktable" className="clickable"><thead><tr><th>waypoint</th><th>trick</th><th>what it does</th><th>the field shows it at</th><th>how sure</th><th>stars needed</th><th>Nothing up my sleeve so far</th><th>Nothing up my sleeve's goal size</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: registry?.body || '' }} /></table></div>
            <p className="note mt">Also: <a href={MB}>every kind of head (the star chart, in Masaq' Reach)</a> · <a href={`${DB}/traits`}>traits</a></p>
          </section>
        </div>
      </div>

      {/* ============================== one trick */}
      <div className={`dview${view === 'trick' ? ' active' : ''}`} data-dview="trick">
        <h1><a className={crumbCls('back')} href={DB}>← discoveries</a> <span id="tricktitle">{pageInfo?.title || 'reading…'}</span> <span id="trickstate" dangerouslySetInnerHTML={{ __html: pageInfo?.state || '' }} /> <span className="q" id="trickdoes">{pageInfo?.does || ''}</span></h1>
        <section className={cardCls(false, 'panel')}><div className="rungover" id="trickover" dangerouslySetInnerHTML={{ __html: pageInfo ? (pageInfo.over || '<div class="s">no detail is written for this trick yet</div>') : '<div class="s">reading the trick…</div>' }} /></section>
        <section className={cardCls(false, 'panel')}>
          <h2>The stars needed to learn it <span className="note">the mechanisms inside thought to do this trick, each with where it is expected and its state in Nothing up my sleeve</span></h2>
          <div className="scroll"><table id="trickstars"><thead><tr><th>kind of head</th><th>what it does</th><th>rests on</th><th>expected from</th><th>first lit in</th><th>in Nothing up my sleeve</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: pageInfo?.stars || '' }} /></table></div>
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2>How Nothing up my sleeve is tracking, size by size <span className="note">each size of ship, how many of its voyages have been measured on this trick and how many performed it; the target is a tenth of the field's size</span></h2>
          <div className="scroll"><table id="tricktrack"><thead><tr><th>size</th><th>parameters</th><th>against the field</th><th>voyages measured</th><th>performed</th><th>best</th><th>first performed</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: pageInfo?.track || '' }} /></table></div>
        </section>
        <div className="row" id="trickcharts">
          <section className={cardCls(false, 'panel')} id="trickchartpanel" hidden={!pageInfo?.chart}>
            <h2>The trick, voyage by voyage <span className="note">its reading at every step, one line per voyage, coloured by size; the amber dotted line is the mark that counts as performed, the grey one the floor (an untrained ship), and labelled lines are outside models</span></h2>
            <div className="chart tall" id="trickchart" />
          </section>
          <section className={cardCls(false, 'panel')} id="trickpairpanel" hidden={!pageInfo?.pair}>
            <h2 id="trickpairtitle" dangerouslySetInnerHTML={{ __html: pageInfo?.pair?.title || 'Beside it' }} />
            <div className="chart tall" id="trickpairchart" />
          </section>
        </div>
        <section className={cardCls(false, 'panel')} id="scaffoldpanel" hidden={!scaffRows.length}>
          <h2>How the scaffold held, across every model <span className="note">pinned heads are a loan: <b>held</b> is the best reading while the heads were pinned, <b>after the fade</b> is the first reading once they were faded out, <b>drop</b> is what the fade cost, and <b>kept</b> is what remains above the untrained floor. A model with no scaffolded voyage is listed as a gap, not left out</span></h2>
          <div dangerouslySetInnerHTML={{ __html: scaffoldHtml(scaffRows, scaffSummary, rungs, scaffThreshold) }} />
          <div className="chart tall" id="scaffoldchart" />
        </section>
      </div>

      {/* ============================== one chain: the explorer's test told as a climb, keel to explorer */}
      <div className={`dview${view === 'chain' ? ' active' : ''}`} data-dview="chain">
        <h1><a className={crumbCls('back')} href={DB}>← discoveries</a> <span id="chaintitle">{chainPage?.title || ''}</span> <span id="chainstrand" dangerouslySetInnerHTML={{ __html: chainPage?.strand || '' }} /></h1>
        <section className={cardCls(false, 'panel')}><div className="rungover" id="chainover" dangerouslySetInnerHTML={{ __html: chainPage?.over || '' }} /></section>
        <div className="handtools"><label><input className={checkCls('')} type="checkbox" id="chainrefpage" checked={chainRef} onChange={(e) => setRef(e.target.checked)} /> show the reference ladder <span className="note">(Pythia 14m to 410m and Qwen3 0.6B to 4B beside each step's evidence)</span></label></div>
        <div id="chainsteps" dangerouslySetInnerHTML={{ __html: chainPage?.steps || '' }} />
      </div>

      {/* ============================== the traits */}
      <div className={`dview${view === 'traits' ? ' active' : ''}`} data-dview="traits">
        <h1><a className={crumbCls('back')} href={DB}>← discoveries</a> Traits <span className="q">can a ship's hidden state tell fiction, verse, first person or a language family apart on books it has never read; found at the threshold, learned when it also clears the floors</span></h1>
        <div className="handtools"><button className={btnCls('outline', '')} data-essay="traits">Read: how traits are found</button></div>
        <section className={cardCls(false, 'panel')}><div className="scroll"><table id="traittable" className="clickable"><thead dangerouslySetInnerHTML={{ __html: traits?.head || '' }} /><tbody dangerouslySetInnerHTML={{ __html: traits?.body || '' }} /></table></div></section>
      </div>

      {domain && (
        <div className={`dview${view === 'domain' ? ' active' : ''}`} data-dview="domain">
          <h1><a className={crumbCls('back')} href={DB}>← discoveries</a> {domain.title}</h1>
          <section className={cardCls(false, 'panel')}>
            <div className="domainhero">
              <img src={domain.image} alt="" />
              <div><div className="k">A door into the discoveries</div><h2>{domain.title}</h2><p>{domain.blurb}</p></div>
            </div>
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The skills in this door <span className="note">every skill charted on the {domain.title.toLowerCase()} step of the ladder; open one for its stars, its readings and its place in the climb</span></h2>
            {domainSkills.length ? <div className="domainskills">{domainSkills.map((t) => (
              <a className={`skill${t.fleet ? ' measured' : ''}`} href={`${DB}/${esc(t.key)}`} key={t.key}>
                <b>{t.gate ? '◆ ' : ''}{t.name}</b><span>{t.does}</span>
                <em>{t.fleet ? 'measured by Nothing up my sleeve' : 'not measured yet'}{t.target_class ? ` · goal ${t.target_class}` : ''}{t.taught ? ' · taught' : ''}</em>
              </a>
            ))}</div> : <div className={emptyCls()}>no skill is charted on this step yet</div>}
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>Where to go next</h2>
            <div className="handtools">{domain.links.map(([href, label]) => <a className={btnCls('outline', '')} href={href} key={href}>{label}</a>)}</div>
          </section>
        </div>
      )}

      {/* ============================== the landing: the two axis cards, and nothing else (13 November) */}
      <div className={`dview${view === 'landing' ? ' active' : ''}`} data-dview="landing">
        {view === 'landing' ? <AxisDoors /> : null}
      </div>

      {/* ============================== the field on two axes: an axis's categories, or one category's discoveries */}
      <div className={`dview${view === 'map' ? ' active' : ''}`} data-dview="map">
        {view === 'map' && parsed.axis ? <FieldMapView slug={parsed.axis} cat={parsed.cat || null} /> : null}
      </div>

      {/* ============================== Masaq' Reach's discoveries: the head kinds research has named, the cards beyond
          the sixteen, and the Qwen 4B mapping (12 November: moved out of Demiton's Stars tab) */}
      <div className={`dview${view === 'masaq' ? ' active' : ''}`} data-dview="masaq">
        <h1>
          <a className={crumbCls('back')} href="/orbitals/masaq">← Masaq' Reach</a>{' '}
          Discoveries{' '}
          <span className="q">what is known of the outside models and the research field: every kind of attention head the papers have named, the census's clusters beyond our sixteen cards, and the Qwen 4B mapping still to be sorted. What our own ships have found is in <a href={DB}>Demiton</a></span>
        </h1>
        <TabNav
          id="masaqdiscnav"
          ariaLabel="Masaq' Reach discoveries"
          items={MASAQ_TABS.map((t) => ({ key: t.key, label: t.label, href: masaqHref(t.key), active: view === 'masaq' && masaqSub === t.key }))}
        />
        {masaqSub === 'kinds' ? (
          <>
            <section className={cardCls(false, 'panel')}>
              <h2>The star chart <span className="note">every kind of attention head described so far. Those Nothing up my sleeve measures carry their state from the ledger; the rest are charted but not yet measured, each with how Nothing up my sleeve could measure it. "Rests on" is the dependency its source reports; a blank means none reported. "Expected from" is the smallest size predicted to reach it (the floor is depth: one hop per layer), set beside the smallest size where a voyage has lit it</span></h2>
              <div className="handtools" data-filters>
                <label className="note" htmlFor="headfamily">family</label>
                <select className={selectCls('')} id="headfamily" data-remember value={family} onChange={(e) => setFamily(e.target.value)}>
                  <option value="">all</option>
                  {(d ? headFamilies(d) : []).map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                </select>
                <span className="note" id="headcount">{heads?.count || ''}</span>
              </div>
              <div className="scroll"><table id="headtable"><thead><tr><th>kind of head</th><th>family</th><th>what it does</th><th>rests on</th><th>expected from</th><th>first lit in</th><th>in Nothing up my sleeve</th><th>first described</th><th>seen in</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: heads?.body || '' }} /></table></div>
            </section>
            <section className={cardCls(false, 'panel')}>
              <h2>Head kinds with no card <span className="note">{uncarded.length} of {(d?.known_heads || []).length} known head kinds: charted, but no card names them</span></h2>
              <div className="scroll">
                <table id="uncarded" className="selbooks">
                  <thead><tr><th>kind of head</th><th>family</th><th>what it does</th><th>expected from</th></tr></thead>
                  <tbody>
                    {uncarded.map((h: any) => (
                      <tr key={h.name}>
                        <td><b>{h.name}</b></td>
                        <td>{h.family}</td>
                        <td className="s">{h.does}</td>
                        <td>{h.expected_from || '—'}</td>
                      </tr>
                    ))}
                    {!uncarded.length ? <tr><td colSpan={4} className="s">every charted head names a card</td></tr> : null}
                  </tbody>
                </table>
              </div>
            </section>
            <section className={cardCls(false, 'panel')}>
              <h2>Cards with no single head <span className="note">the card is a job; these are read by a pair, a circuit, a probe or a state</span></h2>
              <div className="scroll">
                <table id="headless" className="selbooks">
                  <thead><tr><th>card</th><th>what reads it</th><th>why it is not one head</th></tr></thead>
                  <tbody>
                    {HEADLESS_CARDS.map((c) => (
                      <tr key={c.card}><td><b>{c.card}</b></td><td>{c.kind}</td><td className="s">{c.why}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <p className="note">Qwen3 4B's own heads, all 1,152 by category, and its persona vectors are on <a href={QWEN4B_PAGE}>its page in the Reach</a>.</p>
          </>
        ) : masaqSub === 'cards' ? (
          <>
            <p className="q dsubintro">The behavioural clusters of Qwen3 4B's head census: a cluster no card names is a candidate for one of the ten kinds with no star metric. The sixteen themselves, with our ships' best readings, are <a href={`${DB}/stars?tab=cards`}>Demiton's cards</a>.</p>
            {/* the renderer draws its own panel */}
            <div dangerouslySetInnerHTML={{ __html: census.data ? cardsBeyondHtml(census.data) : census.error ? `<div class="s">the head census could not be read: ${esc(census.error)}</div>` : '<div class="s">reading the head census…</div>' }} />
          </>
        ) : (
          <section className={cardCls(false, 'panel')}>
            <h2>Qwen 4B: still to be sorted <span className="note">the audit that fills the per-head and per-card columns</span></h2>
            <p className="note">The sixteen cards already have Qwen readings (<a href={`${DB}/stars?tab=cards`}>Demiton's cards</a>), and its 1,152 heads are censused (<a href={QWEN4B_PAGE}>its page</a>). The twenty-one head kinds do not yet have per-kind Qwen readings. When the cause and card audit lands, this tab becomes the mapping: per head kind in Qwen, per card in Qwen, and the rows that still have no home.</p>
          </section>
        )}
      </div>

      {question && (() => {
        const ch = (chainsApi.data || []).find((x: any) => x.key === question.chain);
        const st = ch?.steps?.[question.step];
        if (!ch || !st) return null;
        return (
          <div className="qmodal" role="dialog" aria-modal="true" aria-label={`${ch.name}: ${st.name} questions`} onClick={(e) => { if (e.target === e.currentTarget) setQuestion(null); }}>
            <div className="qmodalbox">
              <button type="button" className="qclose" aria-label="close" onClick={() => setQuestion(null)}>×</button>
              <div className="k">{ch.name} · step {question.step + 1} of {ch.steps.length}</div>
              <h3>{st.name}</h3>
              <p>{st.adds}</p>
              <p className="s">{st.rung ? `${st.rung.name || st.rung.preset} · ` : ''}performed at {st.threshold ?? '–'}{st.min_score != null ? ` and ${Math.round(100 * st.min_score)}% of pairs right` : ''}</p>
              {st.pairs?.length ? (
                <ol className="qlist">{st.pairs.map((p: any, i: number) => (
                  <li key={i}><div className="qprompt">{p.prompt}{p.frame ? <> <b>{p.frame}</b></> : null}</div>
                    <div className="qans"><span className="qidea">{p.idea}</span><span className="qrival">{p.rival}</span></div></li>
                ))}</ol>
              ) : <div className={emptyCls()}>this rung&apos;s questions are not written yet</div>}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
