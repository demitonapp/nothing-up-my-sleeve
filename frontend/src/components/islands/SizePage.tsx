// One size's page (UI.md "Model pages"), as a client island: the seven tabs and each tab's sub-views.
// The shells are JSX; the data renderers and charts are scripts/views/size-page.ts, loaded at run time.

import { useEffect, useMemo, useRef, useState } from 'react';
import { btnCls, cardCls, crumbCls, emptyCls, fieldCls, rangeCls, selectCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import { initRunGrid } from '@/lib/rungrid';
import { shipHash } from '@/scripts/router';
import { isSizePage, modelHref, renderSizePage, rungFor, setSizeSelection, sizeAddress } from '@/scripts/views/size-page';
import SectionNav from '../SectionNav';
import { TabNav } from '../TabNav';
import Chat from './Chat';

const MTABS = ['overview', 'goals', 'training', 'scoring', 'waypoints', 'sops', 'chat'];
const SSUBS = ['maths', 'ask', 'language', 'shapes', 'number', 'physics', 'life', 'return', 'logic', 'versus'];
const WSUBS = ['expected', 'envelope', 'stars'];

export default function SizePage({ initialPath = '/' }: { initialPath?: string }) {
  const route = useRoute();
  const [path, setPath] = useState(initialPath);
  const [sel, setSel] = useState<{ expedition: string; voyage: string }>({ expedition: '', voyage: '' });

  useEffect(() => { setPath(route); }, [route]);
  const mine = isSizePage(path);
  const ladder = useApi<any>('/api/ladder', 15000, mine);
  const exps = useApi<any>('/api/expeditions/overview', 300000, mine);
  const chatModels = useApi<any>('/api/chat/models', 60000, mine);
  const wired = useRef(false);

  const readSelection = (): void => {
    const q = new URLSearchParams(location.search);
    setSel({ expedition: q.get('expedition') || '', voyage: q.get('voyage') || '' });
  };

  useEffect(() => {
    const read = (): void => {
      setPath(location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname);
      readSelection();
    };
    read();
    const onPop = (): void => read();
    window.addEventListener('popstate', onPop);
    window.addEventListener('hashchange', onPop);
    return () => { window.removeEventListener('popstate', onPop); window.removeEventListener('hashchange', onPop); };
  }, []);

  const addr = sizeAddress(path);
  const rung = useMemo(() => (ladder.data ? rungFor(ladder.data, addr.key) : null), [ladder.data, addr.key]);
  // the chat tab talks to this size's best ship that has a reachable checkpoint (the chat models are the
  // leaderboard's ships, best first); a size with none keeps the message
  const chatShip = rung
    ? ((chatModels.data && chatModels.data.models) || []).find((m: any) => m.kind === 'thorp' && m.available && String(m.ship_key || '').startsWith(rung.preset + ':'))
    : null;
  const tab = MTABS.includes(addr.tab) ? addr.tab : 'overview';
  // one size, one address: a class slug ('towing-tank', 'measured-mile', or an old one such as 'faces' or 'augustus') or an old /sizes link is rewritten to the size's preset
  // ('300k'), the canonical identifier, keeping the tab and sub-view (10 November)
  const canonical = useMemo(
    () => (rung ? modelHref(rung, tab, tab === 'scoring' ? addr.ssub : tab === 'waypoints' ? addr.wsub : addr.osub) : null),
    [rung, tab, addr.ssub, addr.wsub, addr.osub],
  );

  useEffect(() => {
    if (!mine || !canonical) return;
    const hash = location.hash.startsWith('#/');
    const search = location.search;
    const want = (hash ? '#' + canonical : canonical) + search;
    if ((hash ? location.hash : location.pathname + search) === want) return;
    history.replaceState(null, '', want);
    setPath(canonical);
  }, [mine, canonical, path]);

  useEffect(() => {
    if (!mine || !ladder.data) return;
    let live = true;
    void (async () => {
      if (!wired.current) {
        wired.current = true;
        // warm the reader once: its book links are on the tomes, the shelves and the essays
        try { await import('@/lib/reader'); } catch { /* no reader on this page */ }
        const goShip = (id: string): void => {
          const lr = ((ladder.data && ladder.data.runs) || []).find((x: any) => x.run_id === id || x.name === id);
          location.href = lr && lr.ship_key ? shipHash(lr.ship_key, lr.name) : shipHash(lr ? lr.name : id);
        };
        initRunGrid(goShip);
      }
      if (!live) return;
      setSizeSelection(sel);
      await renderSizePage(path, ladder.data);
    })();
    return () => { live = false; };
  }, [mine, path, ladder.data, sel.expedition, sel.voyage]);

  const sizeRuns = useMemo(
    () => ((ladder.data?.runs || []) as any[]).filter((x) => x.preset === rung?.preset && !String(x.name || '').startsWith('smoke')),
    [ladder.data, rung],
  );
  const expKeys = useMemo(
    () => [...new Set(sizeRuns.map((x) => String(x.voyage || '')).filter(Boolean))].sort() as string[],
    [sizeRuns],
  );
  const expName = (k: string): string => (((exps.data && exps.data.expeditions) || []) as any[]).find((e) => e.key === k)?.name || k;
  const voyRuns = useMemo(() => sizeRuns.filter((x) => !sel.expedition || x.voyage === sel.expedition), [sizeRuns, sel.expedition]);
  const applySel = (next: { expedition: string; voyage: string }): void => {
    setSel(next);
    const q = new URLSearchParams(location.search);
    if (next.expedition) q.set('expedition', next.expedition); else q.delete('expedition');
    if (next.voyage) q.set('voyage', next.voyage); else q.delete('voyage');
    const qs = q.toString();
    const base = location.hash.startsWith('#/') ? location.hash.split('?')[0] : location.pathname;
    history.replaceState(null, '', base + (qs ? `?${qs}` : ''));
  };
  const onExp = (expedition: string): void => applySel({ expedition, voyage: '' });
  const onVoy = (voyage: string): void => {
    const run = sizeRuns.find((x) => x.run_id === voyage);
    applySel({ expedition: voyage ? String(run?.voyage || sel.expedition) : sel.expedition, voyage });
  };
  const selRun = sizeRuns.find((x) => x.run_id === sel.voyage);

  if (!mine) return null;
  const keep = typeof window === 'undefined' ? '' : location.search;
  const href = (mt: string, sub?: string): string => (rung ? modelHref(rung, mt, sub || null) : `/ships/${encodeURIComponent(addr.key)}${mt === 'overview' ? '' : '/' + mt}`) + keep;
  const isS = (s: string): boolean => tab === 'scoring' && addr.ssub === s;
  const isW = (w: string): boolean => tab === 'waypoints' && addr.wsub === w;

  return (
    <div {...sectionProps('rung')} id="rung">
      <SectionNav />
      <h1 className="crumbs"><a className={crumbCls('back')} href="/orbitals">Orbitals</a> <span className="sep">/</span> <span className="here" id="rungtitle">{rung ? `${rung.preset} · ${rung.name}` : 'reading the ship…'}</span></h1>
      <div className="handtools" id="shipsel" style={{ margin: '2px 0 10px' }}>
        <label className="note" htmlFor="expsel">expedition</label>
        <select className={selectCls('')} id="expsel" value={sel.expedition} onChange={(e) => onExp(e.target.value)} title="the expedition its charts and readings follow">
          <option value="">all expeditions</option>
          {expKeys.map((k) => <option key={k} value={k}>{expName(k)}</option>)}
        </select>
        <label className="note" htmlFor="voysel">voyage</label>
        <select className={selectCls('')} id="voysel" value={sel.voyage} onChange={(e) => onVoy(e.target.value)} title="one voyage; leave it on the median to use the expedition's median reading at each step">
          <option value="">{sel.expedition ? 'median of the expedition' : 'every voyage'}</option>
          {voyRuns.map((x) => <option key={x.run_id} value={x.run_id}>{x.name}{x.ship ? ` · ${x.ship}` : ''}</option>)}
        </select>
        <span className="note" id="selnote">{sel.voyage ? `one voyage: ${selRun?.name || sel.voyage}` : sel.expedition ? `median of ${voyRuns.length} ${expName(sel.expedition)} voyage${voyRuns.length === 1 ? '' : 's'}` : 'every voyage at this size'}</span>
      </div>
      <TabNav
        id="modelnav"
        ariaLabel="ship sections"
        items={MTABS.map((t) => ({
          key: t,
          label: t === 'sops' ? 'SOPs' : t[0].toUpperCase() + t.slice(1),
          href: href(t),
          active: tab === t,
          data: { 'data-mtab': t },
        }))}
      />

      <div className={`mtab${tab === 'goals' ? ' active' : ''}`} data-mtab="goals">
        <section className={cardCls(false, 'panel')} id="roadpanel">
          <h2>The road to quantum mechanics <span className="note">the seven waypoints, bottom to top; green is performed by this size, outlined is inherited from a smaller size (carried up, still to show here), grey is open. ◆ marks a gate. The 300k's job is to climb as high as it can in a way that scales to the 1m</span></h2>
          <div className="roadlegend">
            <span className="item"><span className="chip mine">&#9670; gate, still open</span> a gate expected at this size, not performed yet</span>
            <span className="item"><span className="chip done">&#10003; performed</span> performed here</span>
            <span className="item"><span className="chip above">1m</span> above this size</span>
            <span className="item"><span className="chip taught">taught</span> taught or a reference</span>
            <span className="item"><b>the basics</b> the floor · <b>the ladder</b> the climb</span>
          </div>
          <div className="goalroute" id="goalroute"><div className={emptyCls()}>reading the ship's goals…</div></div>
        </section>
      </div>

      <div className={`mtab${tab === 'overview' ? ' active' : ''}`} data-mtab="overview">
        <section className={cardCls(false, 'panel')} id="expusepanel">
          <h2>How this ship has been used <span className="note">every voyage at this size, grouped by the expedition that claimed it: how many voyages and ships it contributed, how they ended, the best Forgotten Tomes score, the standards it sailed under, and when</span></h2>
          <div id="expuse"><div className={emptyCls()}>reading the expeditions…</div></div>
        </section>
        <section className={cardCls(false, 'panel')} id="gridpanel">
          <h2>Every voyage at this size <span className="note">one square per voyage in the order they started; the brighter the green, the better the reading chosen below (bpb lower, cause higher), by quartile of the voyages scored on it; an outlined square is running</span></h2>
          <div className="handtools" data-filters>
            <label className="note" htmlFor="gridmetric">colour by</label>
            <select className={selectCls('')} id="gridmetric" defaultValue="bpb">
              <option value="bpb">Forgotten Tomes bpb</option>
              <option value="cause">cause gain</option>
            </select>
            <span className="note" id="gridmetricnote">bpb: 16 held-out books, lower is better · cause: the logic deck's cause gain, higher is better</span>
          </div>
          <div id="rungridsum" className="gridsum" />
          <div id="rungrid" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2>The Forgotten Tomes score, voyage by voyage <span className="note">bits per byte on 16 books Qwen 3.8 cannot have read, lower is better; one dot per scored voyage in the order they started, the line is the best so far, dotted lines are Qwen models scored the same way</span></h2>
          <div className="chart tall" id="ftchart" />
          <div className="s mt" id="ftnote" />
        </section>
      </div>

      <div className={`mtab${tab === 'training' ? ' active' : ''}`} data-mtab="training">
        <section className={cardCls(false, 'panel')}>
          <h2>The star chart, against Qwen3 4B <span className="note">the ten points of the chart, each reading divided by its own mark: Qwen3 4B (which chains) against this ship's newest voyage, read live while it trains. Above the dotted line a point clears its mark; the gap between the lines is how far the ship is behind on that point, and where its line is above, it is ahead</span></h2>
          <div className="chart" id="sizejourney" />
          <div className="s" id="sizejourneynote" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <div className="handtools" style={{ border: 0, padding: 0, margin: 0 }}><label className="note" htmlFor="soppick">SOP</label><select className={selectCls('')} id="soppick" data-remember /><span className="note" id="sopnote">every run, chart and reading below is built to this version (or to all of them)</span></div>
        </section>
        <section className={cardCls(false, 'panel')} id="watchpanel">
          <h2>Watch it train <span className="note">this size's voyage at sea (else its latest home), read every 30 seconds: where it is in its stages and passes, the cards it has drawn and when, and the readings that matter, by tokens read</span></h2>
          <div id="watchhead" className="watchhead"><div className={emptyCls()}>looking for a voyage…</div></div>
          <div id="watchstages" className="watchstages" />
          <div id="watchdrawn" className="watchdrawn" />
          <div className="watchgrid">
            <div><h3>Loss and learning rate</h3><div className="chart" id="watchloss" /></div>
            <div><h3>Judge books, bits per byte <span className="s">lower is better</span></h3><div className="chart" id="watchbpb" /></div>
            <div><h3>Shapes <span className="s">top guess right</span></h3><div className="chart" id="watchshapes" /></div>
            <div><h3>The cards <span className="s">each against its mark</span></h3><div className="chart" id="watchcards" /></div>
            <div><h3>Copying and chaining <span className="s">copy gain (nats), one-hop lift, cause gain</span></h3><div className="chart" id="watchchain" /></div>
            <div><h3>The log</h3><pre id="watchlog" className="watchlog" /></div>
          </div>
        </section>
        <section className={cardCls(false, 'panel')}><div className="rungover" id="rungover" /></section>
        <section className={cardCls(false, 'panel')}>
          <h2>Training loss <span className="note">nats per token on the training library, the latest 12 voyages at this size</span></h2>
          <div className="chart" id="losschart" />
        </section>
      </div>

      <div className={`mtab${tab === 'scoring' ? ' active' : ''}`} data-mtab="scoring">
        <section className={cardCls(false, 'panel')} id="sopsummarypanel">
          <h2>The SOP run, and what it means <span className="note">this ship's newest voyage: the standard it was built to, its scores, and what those numbers say about that standard — a reading, not a verdict on the ship alone</span></h2>
          <div id="sopsummary"><div className={emptyCls()}>reading the voyage…</div></div>
        </section>
        <section className={cardCls(false, 'panel')} id="starpanel">
          <h2>The star chart, against Qwen3 4B <span className="note">the ten points of the chart, each reading divided by its own mark: Qwen3 4B (which chains) against this ship's newest voyage, read live while it trains. Above the dotted line a point clears its mark; the gap between the lines is how far the ship is behind on that point, and where its line is above, it is ahead</span></h2>
          <div className="chart" id="sopchart" />
          <div className="s mt" id="starnote" />
        </section>
        <section className={cardCls(false, 'panel')} id="cardstrippanel">
          <h2>The four cards <span className="note">what a model must hold before it can chain (every model that chains holds all four): each card's best reading by a voyage of this size against its mark, held when a voyage ended lit, touched when one only passed it; beside them, whether it chains cause and effect</span></h2>
          <div id="cardstrip" className="cardstrip"><div className={emptyCls()}>reading the cards…</div></div>
          <div className="s" id="bestship" />
        </section>

        <TabNav
          id="scnav"
          ariaLabel="scoring sections"
          items={SSUBS.map((s) => ({
            key: s,
            label: s[0].toUpperCase() + s.slice(1),
            href: href('scoring', s),
            active: isS(s),
            data: { 'data-ssub': s },
          }))}
        />
        <div className={`ssub${isS('ask') ? ' active' : ''}`} data-ssub="ask">
          <section className={cardCls(false, 'panel')} id="askpanel">
            <h2>Ask the best version <span className="note">type a line and read what it guesses comes next: its ten likeliest next words (or two words, or the raw pieces it actually predicts), no sampling; or let it answer; the rudimentary questions below each carry the answer we would hope for, and "run all" shows where that answer ranks among its guesses</span></h2>
            <div id="askwho" className="askwho" />
            <div className="askrow">
              <select className={selectCls()} id="askvoyage" aria-label="the voyage to ask" />
              <select className={selectCls()} id="askmode" aria-label="what to guess"><option value="1">guess the next word</option><option value="2">guess the next two words</option><option value="pieces">guess the next piece (as it sees it)</option></select>
            </div>
            <textarea className={fieldCls()} id="asktext" rows={2} placeholder="Once upon a" />
            <div className="askrow"><button className={btnCls('default')} id="askguess" type="button">Guess</button><button className={btnCls()} id="askanswer" type="button">Answer</button><button className={btnCls()} id="askall" type="button">Run all the questions</button></div>
            <div id="askchips" className="askchips" />
            <div id="askout" className="askout" />
          </section>
        </div>
        <div className={`ssub${isS('maths') ? ' active' : ''}`} data-ssub="maths">
          <section className={cardCls(false, 'panel')} id="mathspanel">
            <h2>The maths book <span className="note">nine chapters after Augustus De Morgan's <i>Elements of Arithmetic</i>, his sections in his order, eight sums each in plain words ("Two and three make"); each chapter opens its section of the book in the reader; each sum's answer against its rival, the answer of the mistake a learner makes at that chapter. A sum is right when the answer is among the ship's ten guesses and above the rival; a chapter is learnt at six of eight; the ship has learnt the book up to the first chapter it has not</span></h2>
            <div className="askrow"><select className={selectCls()} id="mathssop" aria-label="the SOP to read the book from" title="the SOP: only voyages built to it are offered" /><select className={selectCls()} id="mathsvoyage" aria-label="the voyage to read the book with" /><button className={btnCls('default')} id="mathsrun" type="button">Read the book</button></div>
            <div id="mathsout" className="askout" />
          </section>
        </div>
        <div className={`ssub${isS('language') ? ' active' : ''}`} data-ssub="language">
          <h2 className="band">Science <span className="q">how well it predicts text it has never seen: bits per byte, lower is better</span></h2>
          <section className={cardCls(false, 'panel')}><h2>What we measure <span className="note">"to come" is not built yet</span></h2>
            <div className="scroll"><table id="sciencemetrics"><thead><tr><th>metric</th><th>what it tells us</th><th>better is</th><th>state</th><th id="scorenowhead">now</th></tr></thead><tbody /></table></div></section>
          <section className={cardCls(false, 'panel')}><h2>Scoreboard <span className="note">the Forgotten Tomes and the voyage's English held-out books, then the held-out score by kind of byte <b className="recentnote" /></span></h2>
            <div className="scroll"><table id="scienceboard"><thead /><tbody /></table></div></section>
          <section className={cardCls(false, 'panel')} id="calpanel" data-kind="proxy" hidden>
            <h2>Calibration against 9m <span className="note">the same library and passes at both sizes; the proxy is trusted only if it orders the libraries as 9m does. Forgotten Tomes bits per byte, English, lower is better</span></h2>
            <div className="row"><div className="scroll"><table id="caltable"><thead><tr><th>library</th><th>passes</th><th>9m voyage</th><th>9m score</th><th>1m voyage</th><th>1m score</th></tr></thead><tbody /></table><p className="note" id="calverdict" /></div><div className="chart" id="calchart" /></div>
          </section>
          <section className={cardCls(false, 'panel')}><h2>Bits per byte by kind of byte <span className="note">spelling is "inside a word"; one bar per voyage; lower is better</span></h2><div className="chart" id="splitchart" /></section>
          <section className={cardCls(false, 'panel')}>
            <h2>The Forgotten Tomes, book by book <span className="note">the best voyage at this size, the latest voyages and Qwen; click a book to read it</span></h2>
            <div className="scroll bookswrap"><table id="tomestable" className="clickable"><thead /><tbody /></table></div>
          </section>
          <h2 className="band">Art <span className="q">how its writing compares with real books: the laws of text, grammar, voice</span></h2>
          <section className={cardCls(false, 'panel')}><h2>What we measure <span className="note">"to come" is not built yet</span></h2>
            <div className="scroll"><table id="artmetrics"><thead><tr><th>metric</th><th>what it tells us</th><th>better is</th><th>state</th></tr></thead><tbody /></table></div></section>
          <section className={cardCls(false, 'panel')}><h2>Scoreboard <span className="note">the laws on the text it writes, model beside the books' own value (ref) <b className="recentnote" /></span></h2>
            <div className="scroll"><table id="artboard"><thead /><tbody /></table></div></section>
          <section className={cardCls(false, 'panel')}><h2>The laws: model against the books <span className="note">model value ÷ the books' value; closer to the dotted line at 1 is better</span></h2><div className="chart" id="lawchart" /></section>
        </div>
        <div className={`ssub${isS('shapes') ? ' active' : ''}`} data-ssub="shapes">
          <section className={cardCls(false, 'panel')}><h2>Shapes <span className="note">the parts-of-speech taxonomy at every reading (s5_policy/taxonomy.py): is the top guess the right part of speech, the right Ogden kind (thing, quality, operation, mark), the right keyed word; and what kind of word it expects against what the judge books hold</span></h2>
            <div className="chart" id="shapeschart" /><div id="shapesmass" className="shapesmass" /></section>
        </div>
        {['number', 'physics', 'life', 'return'].map((k) => (
          <div key={k} className={`ssub${isS(k) ? ' active' : ''}`} data-ssub={k}>
            <section className={cardCls(false, 'panel')}><h2 id={`subj-${k}-title`}>{k[0].toUpperCase() + k.slice(1)} <span className="note" id={`subj-${k}-about`} /></h2><div id={`subj-${k}`} className="subject"><div className={emptyCls()}>reading the tests…</div></div></section>
          </div>
        ))}
        <div className={`ssub${isS('versus') ? ' active' : ''}`} data-ssub="versus">
          <section className={cardCls(false, 'panel')}><h2>Versus <span className="note">this size's voyage against a reference model on every reading both have: the trick tests, the logic deck, the cards and copying, and the judge books' bits per byte; each put as a share of the reference's level so they rank together</span></h2>
            <div id="vspick" className="vspick" /><div id="vsbody"><div className={emptyCls()}>reading…</div></div></section>
        </div>
        <div className={`ssub${isS('logic') ? ' active' : ''}`} data-ssub="logic">
          <section className={cardCls(false, 'panel')}><h2 id="subj-logic-title">Logic <span className="note" id="subj-logic-about" /></h2><div id="subj-logic" className="subject"><div className={emptyCls()}>reading the tests…</div></div></section>
        </div>
      </div>

      <div className={`mtab${tab === 'waypoints' ? ' active' : ''}`} data-mtab="waypoints">
        <TabNav
          id="wpnav"
          ariaLabel="waypoint sections"
          items={WSUBS.map((w, i) => ({
            key: w,
            label: `${i + 1} · ${w[0].toUpperCase() + w.slice(1)}`,
            href: href('waypoints', w),
            active: isW(w),
            data: { 'data-wsub': w },
          }))}
        />
        <section className={cardCls(false, 'panel')}><div className="wpsteps" id="wpsteps" />
          <div className="handtools mt" data-filters><label className="note" htmlFor="wpfilter">step to quantum physics</label><select className={selectCls('')} id="wpfilter" data-remember title="filter the tricks by waypoint"><option value="">all seven</option></select></div></section>
        {WSUBS.map((w) => (
          <div key={w} className={`wsub${isW(w) ? ' active' : ''}`} data-wsub={w}>
            <section className={cardCls(false, 'panel')}>
              <h2>{w[0].toUpperCase() + w.slice(1)} <span className="note">{w === 'expected' ? 'what the field already shows at this size or smaller: the tricks to prove first, so the ship is known to match the field before it tries to beat it' : w === 'envelope' ? "this size's goals, and those it carries up from smaller sizes, that nobody has shown at this size: the field shows them only in bigger models" : 'the ambitious tricks: goals of the bigger sizes, nearest first. A ship of this size performing one is a find'}</span></h2>
              <div className="scroll"><table id={`wp-${w}`} className="clickable"><thead /><tbody /></table></div>
            </section>
          </div>
        ))}
        <h2 className="band">The instruments <span className="q">the stars, Nevermores and traits as measured on this size's voyages, behind the tricks above</span></h2>
        <section className={cardCls(false, 'panel')}>
          <h2>Stars in reach <span className="note">the kinds of head this size is expected to reach (the star chart's "expected from" at or below it), and how its own voyages are doing on each; <span id="reachnext" /></span></h2>
          <div className="scroll"><table id="reachtable"><thead><tr><th>kind of head</th><th>family</th><th>expected from</th><th>why</th><th>on this size</th></tr></thead><tbody /></table></div>
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2>Waypoints, voyage by voyage <span className="note">the training step at which each voyage first passed each waypoint; "not yet" is measured but not reached, – is not measured on that voyage <b className="recentnote" /></span></h2>
          <div className="scroll"><table id="waypointtable"><thead /><tbody /></table></div>
        </section>
        <h2 className="band">Nevermores <span className="q">induction heads: at a word seen before, a head looks back to what followed it last time and bets it comes again; they form suddenly</span><span className="bandtools"><button className={btnCls('outline', '')} data-essay="nevermore">Read: what a Nevermore is</button><button className={btnCls('outline', '')} id="readpassage">Read the test passage</button></span></h2>
        <section className={cardCls(false, 'panel')} id="handpanel">
          <h2>The hand <span className="note">each card is one attention head, rows by layer from the top; a card turns face up (♠) when its head becomes a Nevermore, 0.3 or more on either test; until then its face shows through as far as the head has come. The big number is the real-prose score, the corner one the random test. Bigger models show their strongest five</span></h2>
          <div className="handtools"><select className={selectCls('')} id="handrun" title="the voyage whose hand is shown" /><button className={btnCls('outline', '')} id="handplay" title="deal the hand step by step">▶ play</button><input className={rangeCls('')} type="range" id="handstep" min={0} max={0} defaultValue={0} /><span id="handlabel" /></div>
          <div id="hand" />
        </section>
        <div className="row">
          <section className={cardCls(false, 'panel')}><h2>The strongest head <span className="note">its Nevermore score on a real passage read twice, by training step (where one shows first); the line crossing 0.3 is the moment a Nevermore forms; the latest 12 voyages</span></h2><div className="chart" id="nvchart" /></section>
          <section className={cardCls(false, 'panel')}><h2>Copy gain <span className="note">nats per token the model saves on the second copy of a sequence, which only a model that copies can; higher is better</span></h2><div className="chart" id="copychart" /></section>
        </div>
        <h2 className="band">Traits <span className="q">can its hidden state tell fiction, verse and first person apart on books it has never read; found at the dotted line, learned when it also clears the bag-of-tokens and untrained-model floors</span><span className="bandtools"><button className={btnCls('outline', '')} data-essay="traits">Read: how traits are found</button></span></h2>
        <div className="row3">
          {['fiction', 'verse', 'first_person'].map((t) => <section key={t} className={cardCls(false, 'panel')}><h2>{t === 'first_person' ? 'First person' : t[0].toUpperCase() + t.slice(1)}</h2><div className="chart short" id={`trait-${t}`} /></section>)}
        </div>
      </div>

      <div className={`mtab${tab === 'chat' ? ' active' : ''}`} data-mtab="chat">
        <section className={cardCls(false, 'panel')} id="sizechat">
          <h2>Chat <span className="note">with the best ship at this size that has a checkpoint to talk to{chatShip ? `: ${chatShip.name}` : ''}; experimental, and every answer is audited with the heads and cards that lit</span></h2>
          {chatShip
            ? <Chat shipKey={chatShip.ship_key} embedded />
            : <div className={emptyCls()}>{chatModels.data ? 'no ship at this size has a checkpoint the chat can reach yet' : 'reading the ships…'}</div>}
        </section>
      </div>

      <div className={`mtab${tab === 'sops' ? ' active' : ''}`} data-mtab="sops">
        <section className={cardCls(false, 'panel')}>
          <h2>SOPs <span className="note">the standard operating procedure a voyage is built to: each version's phases, content, optimiser, the depth it gives this size, its runs here and its scores; the current standard first, and a version with a ship at sea is locked</span></h2>
          <div id="classsops"><div className={emptyCls()}>reading the SOPs…</div></div>
        </section>
      </div>

    </div>
  );
}
