// Discoveries (UI.md "Tricks of the trade"), as a typed client island. It serves every discoveries route
// from one page — the index with its five subtabs (chaining two facts, quantum mechanics, the registry of
// tricks, stars, cards), one trick (/discoveries/<trick>), one chain (/discoveries/chains/<key>) and the
// traits (/discoveries/traits) — reading the route itself, as the old router did. The dense renderers are
// in scripts/views/discoveries.ts; this file owns the shell (ported from components/Discoveries.astro),
// the route and the data. Charts (Plotly) are imported lazily inside the effects: the page is server-
// rendered, and nothing that touches document may be imported at module load.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { btnCls, cardCls, checkCls, crumbCls, selectCls, tabCls, tabsCls } from '@/lib/ui';
import { routePath, sectionProps, useApi, useRoute } from '@/lib/useApi';
import { shipHash } from '@/scripts/router';
import { esc } from '@/lib/format';
import {
  cardDeckHtml,
  chainPageHtml,
  chainsTableHtml,
  drawBridge,
  drawStarDeviation,
  drawStarJourney,
  drawTrickChart,
  emptyChart,
  headFamilies,
  headsHtml,
  methodHtml,
  starGridHtml,
  starsCardsHtml,
  trickBands,
  trickPageHtml,
  trickRouteHtml,
  trickRowsHtml,
  traitsHtml,
  twoFactTests,
  twoFactsHtml,
  type DiscData,
  type Rung,
  type StarPoint,
} from '@/scripts/views/discoveries';

type Sub = 'overview' | 'two-facts' | 'quantum' | 'registry' | 'stars' | 'cards';
type DView = 'index' | 'trick' | 'chain' | 'traits';

interface Parsed {
  view: DView;
  sub: Sub;
  trick: string | null;
  chain: string | null;
}

const DSUBS: Sub[] = ['overview', 'two-facts', 'quantum', 'registry', 'stars', 'cards'];

const parse = (route: string): Parsed => {
  const bits = route.split('?')[0].split('/').filter(Boolean);
  const at = (i: number): string | undefined => (bits[i] ? decodeURIComponent(bits[i]) : undefined);
  // the cards moved to the shipyard's charting section (9 November, Justin: "this /discoveries/cards needs
  // to move to /shipyard/charting"): the same island, reached from the yard
  if (bits[0] === 'shipyard' && bits[1] === 'charting') {
    // the charting section: the deck's overview by default, its cards and its tells under it
    const sub = bits[2] === 'cards' ? 'cards' : bits[2] === 'tells' ? 'stars' : 'overview';
    return { view: 'index', sub: sub as Sub, trick: null, chain: null };
  }
  if (bits[0] !== 'discoveries') return { view: 'index', sub: 'two-facts', trick: null, chain: null };
  const b = at(1);
  const c = at(2);
  if (b === 'chains' && c) return { view: 'chain', sub: 'two-facts', trick: null, chain: c };
  if (!b) return { view: 'index', sub: 'two-facts', trick: null, chain: null };
  if ((DSUBS as string[]).includes(b)) return { view: 'index', sub: b as Sub, trick: null, chain: null };
  if (b === 'traits') return { view: 'traits', sub: 'two-facts', trick: null, chain: null };
  return { view: 'trick', sub: 'two-facts', trick: b, chain: null };
};

const subHref = (s: Sub): string => (s === 'overview' ? '/shipyard/charting'
  : s === 'cards' ? '/shipyard/charting/cards'
  : s === 'stars' ? '/shipyard/charting/tells'
  : s === 'two-facts' ? '/discoveries' : `/discoveries/${s}`);

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
  const { view, sub, trick: trickKey, chain: chainKey } = parse(route);

  // the route the old router read: the hash first, then the path (a pasted path is answered by the server).
  // `ready` gates the sub-view endpoints: the first render is server-consistent (the default view), so
  // without it a stars or chain page would fetch the two-facts payloads (the slow bootstrap) for nothing.
  useEffect(() => {
    setNav(routePath());
    setReady(true);
    const onPop = () => setNav(routePath());
    window.addEventListener('popstate', onPop);
    window.addEventListener('hashchange', onPop);
    return () => {
      window.removeEventListener('popstate', onPop);
      window.removeEventListener('hashchange', onPop);
    };
  }, []);

  const go = (p: string): void => {
    try {
      history.pushState(null, '', p);
    } catch {
      /* a file:// page cannot push; the link still works */
    }
    setNav(p);
  };

  const disc = useApi<DiscData>('/api/discoveries', 30000);
  const ladder = useApi<any>('/api/ladder', 300000);
  const onTwoFacts = ready && view === 'index' && sub === 'two-facts';
  const onStars = ready && view === 'index' && sub === 'stars';
  const onCards = ready && view === 'index' && (sub === 'cards' || sub === 'stars');
  const sq = useApi<any>(onTwoFacts ? '/api/smoking_qwen' : null, 120000);
  const lb = useApi<any>(onTwoFacts ? '/api/leaderboard' : null, 120000);
  const starPoints = useApi<{ points: StarPoint[] }>(onStars ? '/api/star_points' : null, 120000);
  const starDev = useApi<{ cards: any[] }>(onStars ? '/api/stars_deviation' : null, 120000);
  const deck = useApi<{ cards: any[] }>(onCards ? '/api/card_deck' : null, 120000);
  const atlas = useApi<any>(sub === 'overview' ? '/api/deck_atlas' : null, 300000);
  const bridge = useApi<any>(onStars ? '/api/bridge' : null, 120000);

  const d = disc.data;
  const rungs: Rung[] = useMemo(() => (ladder.data?.rungs || []).map((r: any) => ({ preset: r.preset, name: r.name, total: r.total })), [ladder.data]);

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
    if (view !== 'index' || sub !== 'two-facts' || !chainSig) return;
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
  }, [view, sub, chainSig]);

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
  const [band, setBand] = useState('');
  const [family, setFamily] = useState('');

  // the charts. Each runs only on the subtab that shows it, after its data has arrived.
  useEffect(() => {
    if (view === 'index' && sub === 'stars' && starPoints.data) void drawStarJourney(starPoints.data.points);
  }, [view, sub, starPoints.data]);
  useEffect(() => {
    if (view === 'index' && sub === 'stars' && starDev.data) void drawStarDeviation(starDev.data.cards);
  }, [view, sub, starDev.data]);
  useEffect(() => {
    if (view === 'index' && sub === 'stars' && bridge.data) void drawBridge(bridge.data, rungs);
  }, [view, sub, bridge.data, rungs]);
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

  const chainPage = useMemo(
    () => (d && view === 'chain' ? chainPageHtml(d, rungs, chainKey, chainApi.data, chainRef) : null),
    [d, rungs, view, chainKey, chainApi.data, chainRef],
  );

  const traits = d ? traitsHtml(d) : null;
  const stars = d ? starsCardsHtml(d) : '';
  const grid = d ? starGridHtml(d, rungs) : null;
  const chains = d ? chainsTableHtml(d, rungs, chainRef) : null;
  const route1 = d ? trickRouteHtml(d) : '';
  const registry = d ? trickRowsHtml(d, rungs, waypoint, band) : null;
  const heads = d ? headsHtml(d, rungs, family) : null;
  const method = d ? methodHtml(d, 'chaining', rungs) : null;
  const tf = d && sq.data && lb.data ? twoFactsHtml(d, sq.data, lb.data, pulls) : null;

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
      if (href.startsWith('/discoveries') || href.startsWith('/shipyard')) {
        e.preventDefault();
        go(href);
      }
      return;
    }
    const trickRow = t.closest('tr[data-trick]') as HTMLElement | null;
    if (trickRow) {
      e.preventDefault();
      go(`/discoveries/${trickRow.dataset.trick}`);
      return;
    }
    const traitRow = t.closest('tr[data-run]') as HTMLElement | null;
    if (traitRow) {
      e.preventDefault();
      goShip(traitRow.dataset.run || '');
    }
  };

  const tab = (s: Sub): { className: string; 'data-state': string; 'data-dsub': string; href: string; 'aria-current'?: 'page' } => ({
    className: tabCls(''),
    'data-state': view === 'index' && sub === s ? 'active' : 'inactive',
    'data-dsub': s,
    href: subHref(s),
    ...(view === 'index' && sub === s ? { 'aria-current': 'page' as const } : {}),
  });

  return (
    <div {...sectionProps('discoveries')} onClick={onClick}>
      {/* ============================== the tricks of the trade */}
      <div className={`dview${view === 'index' ? ' active' : ''}`} data-dview="index">
        <h1>Tricks of the trade</h1>
        <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="discnav">
          <a {...tab('overview')}>Overview</a>
          <a {...tab('two-facts')}>Chaining two facts</a>
          <a {...tab('quantum')}>Quantum mechanics</a>
          <a {...tab('registry')}>Registry of tricks</a>
          <a {...tab('stars')}>Tells</a>
          <a {...tab('cards')}>Cards</a>
        </nav>

        {/* the trick in focus: how Thorp proves a model chains two facts (the heart of the leaderboard, and of the claim) */}
        <div className={`dsub${sub === 'two-facts' ? ' active' : ''}`} data-dsub="two-facts">
          <section className={cardCls(false, 'panel tfclaim')}>
            <h2>The claim</h2>
            <p className="tflead">A Thorp model <b>a tenth the size</b> of each 2–4B model chains two facts as well as it does. Chaining two facts is the trick: two premises, neither of which states the conclusion, put together into one that no sentence on the library states. This is how Thorp proves a model can do it, and how the claim is judged.</p>
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
              <p>A model's <b>chaining lift</b> is its mean lift on the four chaining tests. It is the one number <a href="/leaderboard">the leaderboard</a> ranks every model on, outside and Thorp alike, read on the same 96 pairs. Below the 50m, where a size is not yet expected to chain, its progress is its <b>climb</b>: on each chain the rungs performed from the bottom, plus the next rung's share of its mark, the mean of the four (0 to 5).</p>
            </div>
          </section>

          <section className={cardCls(false, 'panel tfstep')}>
            <div className="tfn">6</div><div className="tfb">
              <h2>The forecast: from the sizes Thorp can train to the size it can't</h2>
              <p>The Mac cannot train a 400M model, so the claim is a forecast. Each Thorp size's best voyage gives one point, chaining lift against parameters, and two curves are fitted in log parameters: a <b>straight line</b> (conservative) and a <b>bending curve</b> (probable, since chaining bends upward with size in the outside models). Each is read at a tenth of each competitor's size. A <b>bootstrap</b> (1,000 draws, resampling the pairs and the seeds) gives a 5–95% band and <b>P</b>, the share of draws at or above the competitor's chaining lift. No forecast is made until <b>three sizes</b> are above the noise: a curve through noise extrapolates nothing.</p>
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
        </div>

        {/* the long road: seven waypoints to quantum mechanics, and the explorer's four discovery chains on it */}
        <div className={`dsub${sub === 'quantum' ? ' active' : ''}`} data-dsub="quantum">
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

        {/* the cards: the sixteen-card deck, one row a card, read on the fleet */}
        <div className={`dsub${sub === 'cards' ? ' active' : ''}`} data-dsub="cards">
          <p className="q dsubintro">The sixteen cards, the goal's unit: the deck a ship is built from, each card with its mark, its suit, whether teaching it keeps, and how the fleet's best ship at each size reads it — against Qwen3 4B.</p>
          <section className={cardCls(false, 'panel')}>
            <h2>The deck, card by card <span className="note">each card: its suit, its mark (what counts as lit), whether teaching it keeps (keeper, decayer, or never tested), and the best reading any Thorp ship has reached against Qwen3 4B's own</span></h2>
            <div className="scroll"><table id="discCards" className="selbooks"><thead><tr><th>card</th><th>suit</th><th>mark</th><th>keeps</th><th>best Thorp</th><th>Qwen 4B</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: deck.data ? cardDeckHtml(deck.data) : '<tr><td colspan="6" class="s">reading the deck…</td></tr>' }} /></table></div>
          </section>
        </div>

        {/* the stars: the attention heads that do the tricks, each a card */}
        <div className={`dsub${sub === 'stars' ? ' active' : ''}`} data-dsub="stars">
          <p className="q dsubintro">What inside does it? Attention heads that do one recognisable job. A star is lit when one head reaches its mark, and lit shared when the best layer's two strongest heads reach it together; some rest on others. Five of them are the cards every model that chains two facts plays.</p>
          <section className={cardCls(false, 'panel')}>
            <h2>Lit by size <span className="note">every star Thorp measures, by size of ship: a cell is the size's best reading against the star's mark, green where a voyage has lit it (the first voyage and step on hover), shaded by how close it came where none has; the card judge's verdict beside each</span></h2>
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
          <section className={cardCls(false, 'panel')}>
            <h2>The star chart <span className="note">every kind of attention head described so far. Those Thorp measures carry their state from the ledger; the rest are charted but not yet measured, each with how Thorp could measure it. "Rests on" is the dependency its source reports; a blank means none reported. "Expected from" is the smallest size predicted to reach it (the floor is depth: one hop per layer), set beside the smallest size where a voyage has lit it</span></h2>
            <div className="handtools" data-filters>
              <label className="note" htmlFor="headfamily">family</label>
              <select className={selectCls('')} id="headfamily" data-remember value={family} onChange={(e) => setFamily(e.target.value)}>
                <option value="">all</option>
                {(d ? headFamilies(d) : []).map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
              </select>
              <span className="note" id="headcount">{heads?.count || ''}</span>
            </div>
            <div className="scroll"><table id="headtable"><thead><tr><th>kind of head</th><th>family</th><th>what it does</th><th>rests on</th><th>expected from</th><th>first lit in</th><th>in Thorp</th><th>first described</th><th>seen in</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: heads?.body || '' }} /></table></div>
          </section>
        </div>

        {/* every trick known, measured or not */}
        <div className={`dsub${sub === 'registry' ? ' active' : ''}`} data-dsub="registry">
          <section className={cardCls(false, 'panel')}>
            <h2>The tricks <span className="note">a trick is what a model can do, judged from outside by its bets; open one for the stars that do it and Thorp's progress, size by size. "The field shows it at" is the size band (one order of magnitude, in parameters) where the trick is documented in standard models, not a proven smallest size; hover a band for the detail. "Thorp's goal size" is the size expected to reach it, about an order of magnitude smaller than the field where the depth it needs allows; ◆ marks a gate, performed before a ship moves on to the next waypoint</span></h2>
            <div className="handtools" data-filters>
              <label className="note" htmlFor="trickfamily">waypoint</label>
              <select className={selectCls('')} id="trickfamily" data-remember value={waypoint} onChange={(e) => setWaypoint(e.target.value)}>
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
            <div className="scroll"><table id="tricktable" className="clickable"><thead><tr><th>waypoint</th><th>trick</th><th>what it does</th><th>the field shows it at</th><th>how sure</th><th>stars needed</th><th>Thorp so far</th><th>Thorp's goal size</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: registry?.body || '' }} /></table></div>
            <p className="note mt">Also: <a href="/discoveries/stars">every kind of head (the star chart)</a> · <a href="/discoveries/traits">traits</a></p>
          </section>
        </div>
      </div>

      {/* ============================== one trick */}
      <div className={`dview${view === 'trick' ? ' active' : ''}`} data-dview="trick">
        <h1><a className={crumbCls('back')} href="/discoveries">← discoveries</a> <span id="tricktitle">{pageInfo?.title || ''}</span> <span id="trickstate" dangerouslySetInnerHTML={{ __html: pageInfo?.state || '' }} /> <span className="q" id="trickdoes">{pageInfo?.does || ''}</span></h1>
        <section className={cardCls(false, 'panel')}><div className="rungover" id="trickover" dangerouslySetInnerHTML={{ __html: pageInfo?.over || '' }} /></section>
        <section className={cardCls(false, 'panel')}>
          <h2>The stars needed to learn it <span className="note">the mechanisms inside thought to do this trick, each with where it is expected and its state in Thorp</span></h2>
          <div className="scroll"><table id="trickstars"><thead><tr><th>kind of head</th><th>what it does</th><th>rests on</th><th>expected from</th><th>first lit in</th><th>in Thorp</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: pageInfo?.stars || '' }} /></table></div>
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2>How Thorp is tracking, size by size <span className="note">each size of ship, how many of its voyages have been measured on this trick and how many performed it; the target is a tenth of the field's size</span></h2>
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
      </div>

      {/* ============================== one chain: the explorer's test told as a climb, keel to explorer */}
      <div className={`dview${view === 'chain' ? ' active' : ''}`} data-dview="chain">
        <h1><a className={crumbCls('back')} href="/discoveries">← discoveries</a> <span id="chaintitle">{chainPage?.title || ''}</span> <span id="chainstrand" dangerouslySetInnerHTML={{ __html: chainPage?.strand || '' }} /></h1>
        <section className={cardCls(false, 'panel')}><div className="rungover" id="chainover" dangerouslySetInnerHTML={{ __html: chainPage?.over || '' }} /></section>
        <div className="handtools"><label><input className={checkCls('')} type="checkbox" id="chainrefpage" checked={chainRef} onChange={(e) => setRef(e.target.checked)} /> show the reference ladder <span className="note">(Pythia 14m to 410m and Qwen3 0.6B to 4B beside each step's evidence)</span></label></div>
        <div id="chainsteps" dangerouslySetInnerHTML={{ __html: chainPage?.steps || '' }} />
      </div>

      {/* ============================== the traits */}
      <div className={`dview${view === 'traits' ? ' active' : ''}`} data-dview="traits">
        <h1><a className={crumbCls('back')} href="/discoveries">← discoveries</a> Traits <span className="q">can a ship's hidden state tell fiction, verse, first person or a language family apart on books it has never read; found at the threshold, learned when it also clears the floors</span></h1>
        <div className="handtools"><button className={btnCls('outline', '')} data-essay="traits">Read: how traits are found</button></div>
        <section className={cardCls(false, 'panel')}><div className="scroll"><table id="traittable" className="clickable"><thead dangerouslySetInnerHTML={{ __html: traits?.head || '' }} /><tbody dangerouslySetInnerHTML={{ __html: traits?.body || '' }} /></table></div></section>
      </div>
    </div>
  );
}
