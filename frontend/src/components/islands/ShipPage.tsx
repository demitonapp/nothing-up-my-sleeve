// One ship (UI.md "Ship"), as a client island: its header, sailings, the stages and the library aboard,
// then six tabs of charts. The shells are JSX; the data and chart panels are the typed renderers in
// scripts/views/ship.ts, imported at run time (ECharts touches `self` and `document` at load).

import { useEffect, useMemo, useRef, useState } from 'react';
import { cardCls, crumbCls, pillCls, selectCls, tabCls, tabsCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import { shipHash } from '@/scripts/router';
import { isShipPage, loadAboard, shipAddress, chooseShip, shipHeader, stageListHtml } from '@/scripts/views/ship-page';

const TABS = ['betting', 'books', 'languages', 'sieves', 'attention', 'traits'];

export default function ShipPage() {
  const route = useRoute();
  const [path, setPath] = useState('/');

  useEffect(() => { setPath(route); }, [route]);
  const mine = isShipPage(path);
  const ladder = useApi<any>('/api/ladder', 60000, mine);
  const ships = useApi<any[]>('/api/ships', 60000, mine);
  const runs = useApi<any[]>('/api/runs', 5000, mine);
  const exps = useApi<any[]>('/api/expeditions', 300000, mine);
  const root = useRef<HTMLDivElement>(null);
  const [tick, setTick] = useState(0);
  const busy = useRef(false);

  useEffect(() => {
    const read = (): void => setPath(location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname);
    read();
    const onPop = (): void => read();
    window.addEventListener('popstate', onPop);
    window.addEventListener('hashchange', onPop);
    return () => { window.removeEventListener('popstate', onPop); window.removeEventListener('hashchange', onPop); };
  }, []);

  // a legacy ?run= opens that ship
  useEffect(() => {
    if (!runs.data) return;
    const q = new URLSearchParams(location.search).get('run');
    if (!q || path !== '/') return;
    const r = runs.data.find((x) => x.run_id === q || x.name === q);
    if (r) { const next = shipHash(r.ship_key || r.name, r.name); history.replaceState(null, '', next); setPath(next); }
  }, [runs.data, path]);

  const addr = shipAddress(path);
  const ship = useMemo(() => chooseShip(ships.data, runs.data, addr), [ships.data, runs.data, addr.key, addr.sailing]);
  const tab = TABS.includes(addr.tab) ? addr.tab : 'betting';
  const expeditionNames = useMemo(() => Object.fromEntries((exps.data || []).map((x: any) => [x.key, x.name])), [exps.data]);
  const rung = useMemo(() => ((ladder.data && ladder.data.rungs) || []).find((x: any) => x.preset === (ship.ship ? ship.ship.preset : ship.run && ship.run.preset)) || null, [ladder.data, ship.ship, ship.run]);
  const header = useMemo(() => shipHeader(rung, ship.ship, ship.run, addr.key, tab, expeditionNames), [rung, ship.ship, ship.run, addr.key, tab, expeditionNames]);
  const key = ship.ship ? ship.ship.key : ship.run ? (ship.run.ship_key || ship.run.name) : addr.key || '';
  const sailing = ship.ship && ship.run ? ship.run.name : null;
  const selected = ship.run ? ship.run.run_id : null;

  // the run's charts refresh while the tab is open (the API is slow; 30 s is the watch panel's beat too)
  useEffect(() => {
    if (!mine) return;
    const t = window.setInterval(() => setTick((x) => x + 1), 30000);
    return () => window.clearInterval(t);
  }, [mine]);


  // the header, the sails and the run overview follow the poll
  useEffect(() => {
    if (!mine) return;
    const cls = document.getElementById('shipclass') as HTMLAnchorElement | null;
    if (cls) { cls.textContent = header.classText; if (header.classHref) cls.href = header.classHref; else cls.removeAttribute('href'); }
    const name = document.getElementById('shipname'); if (name) name.textContent = header.name;
    const fit = document.getElementById('shipfitout'); if (fit) fit.textContent = header.fitout;
    const tags = document.getElementById('shiptags'); if (tags) tags.innerHTML = header.tags;
    const sails = document.getElementById('sailings'); if (sails) sails.innerHTML = header.sailings;
    const sum = document.getElementById('stripsum'); if (sum) sum.textContent = ship.run ? `${header.statShip} · ${header.status}` : '';
  }, [mine, header, ship.run]);

  // the stages and the library aboard, for the sailing on show
  useEffect(() => {
    if (!mine) return;
    let live = true;
    const stagePanel = document.getElementById('stagepanel'), stageBody = document.querySelector('#stagetable tbody');
    const aboardPanel = document.getElementById('aboardpanel'), aboard = document.getElementById('aboard');
    if (!stagePanel || !stageBody || !aboardPanel || !aboard) return;
    if (!selected) { stagePanel.hidden = true; aboardPanel.hidden = true; return; }
    (async () => {
      try {
        const stages = await (await import('@/lib/stages')).stagesFor([selected]);
        if (!live) return;
        const h = stageListHtml(stages[selected] || null);
        stagePanel.hidden = h.hidden; stageBody.innerHTML = h.rows;
      } catch { /* stages are an overlay */ }
      const a = await loadAboard(selected);
      if (!live) return;
      aboardPanel.hidden = a.hidden; aboard.innerHTML = a.html;
      aboard.querySelectorAll<HTMLAnchorElement>('[data-lib]').forEach((x) => { x.onclick = (e) => { e.preventDefault(); location.href = '/library'; }; });
    })();
    return () => { live = false; };
  }, [mine, selected]);

  // the run's panels: the run itself, its metrics and evals, drawn by the typed ship views
  useEffect(() => {
    if (!mine || !selected || busy.current) return;
    let alive = true;
    busy.current = true;
    (async () => {
      const s = await import('@/scripts/views/ship');
      const get = async (u: string): Promise<any> => (await fetch(u)).json();
      try {
        const [r, m] = await Promise.all([get('/api/run?run=' + selected), get('/api/metrics?run=' + selected)]);
        if (!alive) return;
        const rec = (r.recipe && r.recipe.data) || [];
        const fams = [...new Set(rec.map((b: any) => b.family).concat(Object.values(s.holeMeta(r)).map((b: any) => b.family)))].filter(Boolean).sort() as string[];
        const { PALETTE } = await import('@/lib/charts');
        const famColour = (f: string): string => PALETTE[Math.max(0, fams.indexOf(f)) % PALETTE.length];
        const series = s.bookSeries(m, r);
        const gk = (await import('@/lib/analysis')).kinksOf(m, 'grad_norm/');
        s.headline(r, m, gk);
        if (tab === 'betting') {
          const [evals, cmp, content] = await Promise.all([get('/api/evals?run=' + selected), get('/api/compare'), get('/api/experiment?prefix=content-')]);
          if (!alive) return;
          s.contentPanel(content || []);
          s.claimPanel(cmp || []);
          s.comparePanel(cmp || []);
          s.matchedPanel(cmp || []);
          s.truthGapPanel(cmp || []);
          s.lossPanel(m, r.sets || []);
          s.bpbPanel(evals, r);
        } else if (tab === 'books') {
          s.bookPanels(m, r, series, fams, famColour);
          s.fallbackPanel(r);
        } else if (tab === 'languages') {
          const evals = await get('/api/evals?run=' + selected);
          if (!alive) return;
          s.languagePanels(r, evals, series, fams, famColour);
        } else if (tab === 'sieves') {
          s.heat('gradheat', m, 'grad_norm/', gk, 'log10');
          s.heat('moveheat', m, 'update_ratio/', (await import('@/lib/analysis')).kinksOf(m, 'update_ratio/'), 'log10');
          s.kinkPanel(m, gk);
          const sv = await import('@/scripts/views/ship-sieves');
          await sv.drawShipSieves(m, r);
        } else if (tab === 'attention') {
          s.attnPanels(m);
          s.speedPanel(m);
        } else if (tab === 'traits') {
          s.probePanel(r, gk);
          s.ladderPanel(r, m);
          s.samplesPanel(r);
        }
        try {
          const bands = await import('@/lib/stages');
          const st = await bands.stagesFor([selected]);
          bands.band('#ship', st[selected]);
        } catch { /* stage bands are an overlay */ }
      } catch (e) {
        const t = document.getElementById('updated');
        if (t) t.textContent = 'error: ' + String((e as Error).message || e);
      } finally {
        busy.current = false;
      }
    })();
    return () => { alive = false; };
  }, [mine, selected, tab, tick]);

  // the run overview folds away; the choice is remembered per viewer
  useEffect(() => {
    if (!mine) return;
    const el = document.getElementById('stripwrap') as HTMLDetailsElement | null;
    if (!el) return;
    try { if (localStorage.getItem('thorp.strip') === 'closed') el.open = false; } catch { /* blocked */ }
    const onToggle = (): void => { try { localStorage.setItem('thorp.strip', el.open ? 'open' : 'closed'); } catch { /* blocked */ } };
    el.addEventListener('toggle', onToggle);
    return () => el.removeEventListener('toggle', onToggle);
  }, [mine]);

  if (!mine) return null;
  const tabState = (t: string): 'active' | 'inactive' => (tab === t ? 'active' : 'inactive');
  const go = (t: string): string => shipHash(key, sailing, t);
  return (
    <div {...sectionProps('ship')} ref={root}>
      <h1><a className={crumbCls('back')} href="/harbours">← harbours</a> <a className={crumbCls('crumb')} id="shipclass" /> <span id="shipname" /> <span id="shiptags" /> <span className="q" id="shipfitout" /></h1>
      <div className="sailings"><span className="k">voyages</span><span id="sailings" /><span className="sub" id="title" /></div>
      <section className={cardCls(false, 'panel')} id="stagepanel" hidden>
        <h2>Stages <span className="note">this voyage read its libraries in stages, in order, under one learning-rate schedule; each step chart below shows them as bands</span></h2>
        <div className="scroll"><table id="stagetable" data-nosort><thead><tr><th>#</th><th>stage</th><th>library</th><th>passes</th><th>steps</th><th>tokens</th></tr></thead><tbody /></table></div>
      </section>
      <section className={cardCls(false, 'panel')} id="aboardpanel" hidden>
        <h2>Library aboard <span className="note">the libraries this voyage carried (thorp.library.aboard): each one's stage, where it came from (the prose stores, the trigram stores, drawn from the stores, or outside the stores), its books and its hash; the decks it refused; its opt-in, if it read outside the stores</span></h2>
        <div id="aboard" />
      </section>
      <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="shipnav">
        {TABS.map((t) => <a key={t} className={tabCls('')} data-state={tabState(t)} data-stab={t} href={go(t)}>{t[0].toUpperCase() + t.slice(1)}</a>)}
      </nav>

      <details className={cardCls(false, 'panel')} id="stripwrap" open><summary>The ship at a glance <span className="note" id="stripsum" /></summary><div className="strip" id="strip" /></details>

      <div className={`shiptab${tab === 'betting' ? ' active' : ''}`} id="betting">
        <h1>Betting performance <span className="q">how well the machine bets on books it has never seen, and how fast that improves</span></h1>
        <section className={cardCls(false, 'panel')}><div className="strip" id="numbers" /></section>
        <section className={cardCls(false, 'panel')} id="contentpanel">
          <h2><span className={pillCls('solid allruns')} title="this panel compares every voyage on the ledger; it does not follow the voyage picker">all voyages</span>The content experiment <span className="note">does what is on the library change how well the model bets on unseen books, its traits, its kinks or its sieves? Fifteen 9m ships, five libraries, the same bytes, tokens and test; the rule was written before any library was cut (DECISIONS.md)</span></h2>
          <div className="claim" id="contentverdict" />
          <div id="contentships" />
          <div className="chart tall" id="contentchart" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2><span className={pillCls('solid allruns')} title="this panel compares every voyage on the ledger; it does not follow the voyage picker">all voyages</span>The claim, and what the ledger says about it</h2>
          <div className="claim" id="claim" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2><span className={pillCls('solid allruns')} title="this panel compares every voyage on the ledger; it does not follow the voyage picker">all voyages</span>Libraries compared: guessing accuracy against tokens seen <span className="note">hole-card bits per byte, every voyage on the ledger; the slope is the learning speed</span></h2>
          <div className="chart tall" id="compare" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2><span className={pillCls('solid allruns')} title="this panel compares every voyage on the ledger; it does not follow the voyage picker">all voyages</span>Matched tokens <span className="note">each voyage's hole-card bits per byte interpolated at the same tokens seen, so libraries of different sizes compare honestly; – where the voyage has not reached that point</span></h2>
          <div id="matched" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2><span className={pillCls('solid allruns')} title="this panel compares every voyage on the ledger; it does not follow the voyage picker">all voyages</span>The truth gap <span className="note">bits per byte on the truths deck (one treatise per field) minus the literature hole cards, at the same step; a library that narrows it taught the laws, not just the register</span></h2>
          <div id="truthgap" />
        </section>
        <section className={cardCls(false, 'panel')}><h2>Training loss, 100-step EMA, eval cross-entropy, learning rate</h2><div className="chart tall" id="loss" /></section>
        <section className={cardCls(false, 'panel')}><h2>Bits per byte per hole card</h2><div className="chart tall" id="bpb" /></section>
      </div>

      <div className={`shiptab${tab === 'books' ? ' active' : ''}`} id="books">
        <h1>Books <span className="q">which books are learned fast, which teach, and which the tokeniser cannot read</span></h1>
        <div className="row">
          <section className={cardCls(false, 'panel')}><h2>Loss by book <span className="note">each recipe book's own descent, mean over each 50-step window, coloured by family</span></h2><div className="chart tall" id="bookloss" /></section>
          <section className={cardCls(false, 'panel')}><h2>Loss by kind <span className="note">mean over the books that carry the trait against the ones that do not</span></h2><div className="chart tall" id="kindloss" /></section>
        </div>
        <section className={cardCls(false, 'panel')}>
          <h2>When each book is learned <span className="note">half-life: the step at which a book has made half the drop it has made so far; sooner is a book of formulae, later is a book that is still teaching</span></h2>
          <div className="chart tall" id="halflife" />
          <div className="foot">What each book contributed to the hole-card score (the heart of the dice, section 13) is not on this page yet: it is a gradient per book at the final checkpoint, computed once a voyage ends.</div>
        </section>
        <section className={cardCls(false, 'panel')}><h2>Byte-fallback rate per book <span className="note">the share of a book's tokens the tokeniser had to spell out in raw bytes</span></h2><div className="chart" id="fallback" /></section>
      </div>

      <div className={`shiptab${tab === 'languages' ? ' active' : ''}`} id="languages">
        <h1>Language groups <span className="q">what the library is made of by family, and how each family is learned and scored</span></h1>
        <div className="row3">
          <section className={cardCls(false, 'panel')}><h2>Recipe: tokens by language family</h2><div className="chart" id="families" /></section>
          <section className={cardCls(false, 'panel')}><h2>Loss by family <span className="note">mean over the family's recipe books</span></h2><div className="chart" id="familyloss" /></section>
          <section className={cardCls(false, 'panel')}><h2>Hole-card bits per byte by family <span className="note">latest eval, mean over the family's held-out books</span></h2><div className="chart" id="familybpb" /></section>
        </div>
      </div>

      <div className={`shiptab${tab === 'sieves' ? ' active' : ''}`} id="sieves">
        <h1>Sieves <span className="q">how the ship answers the wind, layer by layer: how hard each layer is pushed, how far it moves, and which way it steers</span></h1>
        <section className={cardCls(false, 'panel')}>
          <p className="lede">The <b>wind</b> is the error on each guess: how far the bet was from the word that came, felt by every weight that took part. A <b>tack</b> is the ship's answer, one training update: its direction from the wind, its size from the learning rate. <b>Trim</b> is how the tack is set. The three sieves read every layer's tacks, every 50 steps; a <b>kink</b> (◆) is the step where a layer changes regime, the break of a two-line fit, firm after <span id="kinkrule" />.</p>
        </section>
        <div className="cards" id="sievecards" />
        <div className="row">
          <section className={cardCls(false, 'panel')}><h2>Gradient push per layer <span className="note">log10 of the pre-clip norm; ◆ the kink</span></h2><div className="chart" id="gradheat" /></section>
          <section className={cardCls(false, 'panel')}><h2>Weight move per layer <span className="note">log10 of the move since the last record over the size of the weights; ◆ the kink</span></h2><div className="chart" id="moveheat" /></section>
        </div>
        <div className="row">
          <section className={cardCls(false, 'panel')}><h2>The kink <span className="note">each layer's push, fitted as two lines; the break is where the layer changes regime</span></h2><div className="chart" id="kinks" /></section>
          <section className={cardCls(false, 'panel')}>
            <h2>Where each layer broke</h2>
            <div className="scroll"><table className="kinks" id="kinktable"><thead><tr><th>layer</th><th>kink at step</th><th>which way</th><th>slope before</th><th>slope after</th><th>strength</th><th /></tr></thead><tbody /></table></div>
            <div className="foot" id="kinknote" />
          </section>
        </div>
        <section className={cardCls(false, 'panel')}><h2>Heading <span className="note">the cosine between each layer's last two moves: 1 holds its angle, 0 wanders, below 0 comes about</span></h2><div className="chart" id="sieve-heading" /></section>
        <section className={cardCls(false, 'panel')}>
          <h2>Settled <span className="note">for each layer, the first step its heading stays at 0.8 or more for three records running, beside the step any star lit in that layer; do headings settle from the bottom up, and does a layer settle when its star lights?</span></h2>
          <div className="scroll"><table id="settledtable"><thead><tr><th>layer</th><th>heading settled at</th><th>heading now</th><th>push kink</th><th>stars lit in this layer</th></tr></thead><tbody /></table></div>
        </section>
      </div>

      <div className={`shiptab${tab === 'attention' ? ' active' : ''}`} id="attention">
        <h1>Attention and MLP <span className="q">within each layer, whether the learning lands in attention or in the MLP, and what the engine is doing</span></h1>
        <div className="row3">
          <section className={cardCls(false, 'panel')}><h2>Push: attention over MLP <span className="note">log10 of the ratio per layer; above zero the attention half is pushed harder</span></h2><div className="chart" id="attnpush" /></section>
          <section className={cardCls(false, 'panel')}><h2>Move: attention over MLP <span className="note">log10 of the ratio of relative moves per layer</span></h2><div className="chart" id="attnmove" /></section>
          <section className={cardCls(false, 'panel')}><h2>Throughput and memory</h2><div className="chart" id="speed" /></section>
        </div>
      </div>

      <div className={`shiptab${tab === 'traits' ? ' active' : ''}`} id="traits-section">
        <h1>Traits <span className="q">whether any direction in the machine separates a kind of book it has never seen, and what it says when asked</span></h1>
        <section className={cardCls(false, 'panel')}>
          <h2 id="probesh">Traits: is there a direction? <span className="note">a difference-of-means direction fitted on the library, scored on the hole cards; YES needs AUC ≥ 0.8 at some layer with two or more held-out books a side</span></h2>
          <div className="controls" id="traitctl" style={{ display: 'flex', gap: 16, alignItems: 'center', margin: '4px 0 10px', fontSize: 12 }}>
            <label>sort by <select className={selectCls('')} id="traitsort"><option value="layer">sieve layer</option><option value="first">first step found</option><option value="auc">best AUC</option><option value="name">name</option></select></label>
            <label>step <select className={selectCls('')} id="traitstep" /></label>
            <span className="note" id="traitnote" />
          </div>
          <div className="traits" id="traits" />
          <div className="chart short" id="probeheat" />
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2 id="ladderh">The curiosity ladder <span className="note">six precursors of curiosity, bottom first, each measured on the held-out books against the untrained model (and, for the two probe rungs, a bag of tokens); the prediction is that they appear in order</span></h2>
          <div className="claim" id="ladderverdict" />
          <div id="ladder" />
          <div className="chart short" id="laddertime" />
        </section>
        <div className="row">
          <section className={cardCls(false, 'panel')}><h2 id="samplesh">Samples</h2><div className="samples" id="samples" /></section>
          <section className={cardCls(false, 'panel')}><h2 id="top10h">Next token</h2><div className="chart" id="top10" /></section>
        </div>
      </div>
    </div>
  );
}
