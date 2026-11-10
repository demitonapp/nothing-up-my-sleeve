// Leaderboard (UI.md "Leaderboard"), as a client island: the ranked chaining board, the approach
// board, Smoking Qwen and the every-ship table. The competitor and lab sub-views are their own pages
// for now (they keep the shared script); this page no longer loads dashboard.ts.

import { useEffect, useState } from 'react';
import { cardCls, checkCls, emptyCls, selectCls } from '@/lib/ui';
import { sectionProps, useApi } from '@/lib/useApi';
import { boardHtml, drawSmokingChart, runsHtml, smokingHtml } from '@/scripts/views/leaderboard-main';

export default function Leaderboard() {
  const lb = useApi<any>('/api/leaderboard', 60000);
  const sq = useApi<any>('/api/smoking_qwen', 60000);
  const ladder = useApi<any>('/api/ladder', 300000);
  const [want, setWant] = useState('');
  const [showFc, setShowFc] = useState(true);
  const [showPy, setShowPy] = useState(true);

  const rungs: { preset: string; name: string; total: number }[] = (ladder.data?.rungs || []).map((r: any) => ({ preset: r.preset, name: r.name, total: r.total }));
  const order = (p: string): number => { const i = rungs.findIndex((r) => r.preset === p); return i < 0 ? 99 : i; };
  const presets = [...new Set<string>((lb.data?.ships || []).map((r: any) => r.preset).filter(Boolean))].sort((a, b) => order(a) - order(b));
  const nameOf = (p: string): string => (rungs.find((r) => r.preset === p) || { name: '' }).name;

  const runs = lb.data ? runsHtml(lb.data, want, rungs) : null;
  const board = lb.data ? boardHtml(lb.data, sq.data || {}, rungs, showFc, showPy) : null;
  const smoking = sq.data ? smokingHtml(sq.data) : null;

  useEffect(() => {
    if (sq.data) void drawSmokingChart(sq.data);
  }, [sq.data]);

  return (
    <div {...sectionProps('leaderboard')}>
      <h1>Leaderboard <span className="q">two boards on chaining two facts: the models that chain, ranked by how well; and those not chaining yet, ranked by how close they are. The method is under <a href="/discoveries">Discoveries, chaining two facts</a></span></h1>
      <section className={cardCls(false, 'panel')}>
        <h2>Chaining <span className="note">the models whose chaining lift clears the noise (+0.03), ranked by it: the mean lift on the four chaining tests</span></h2>
        <div className="handtools">
          <label><input className={checkCls('')} type="checkbox" checked={showFc} onChange={(e) => setShowFc(e.target.checked)} /> Thorp's forecasts</label>
          <label><input className={checkCls('')} type="checkbox" checked={showPy} onChange={(e) => setShowPy(e.target.checked)} /> the reference ladder (Pythia, smaller Qwen)</label>
          <span className="note" id="lbfcnote" dangerouslySetInnerHTML={{ __html: board?.note || '' }} />
        </div>
        <div className="scroll">
          <table id="lbtable" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: board?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: board?.body || '' }} />
          </table>
        </div>
        <p className="note mt">The leaderboard is the four chaining tests only (Nature's breeder, the mill test, the between test, the pigeonhole test; 96 pairs), each cell its lift and share of pairs right, ✓ when performed (lift 0.1 and two in three right); Thorp's other tests are internal. The chaining gain is the logic deck's: invented words and counterfactual premises, each item asked with both premises and with one; the lift with both less the better single premise, the proof that a pass is chaining, not knowing or one premise. A Thorp size is its best ship, its voyages averaged. The 2–4B models (Qwen, Phi, Llama, Gemma, SmolLM, base checkpoints where one exists) are the competitors: Thorp must chain two facts as well as each at a tenth its size, and they never grade the chains (the reference ladder does). Forecast rows (italic) are Thorp's own sizes fitted against size, straight (conservative) and bending (probable), as Smoking Qwen fits them; while fewer than three sizes are above the noise (0.03) they are curves through noise, shown but not trusted. "Thorp matches it at" is the size where each fit reaches that model's lift; "a tenth its size" is each fit's reading there, with the probability it reaches that model's lift once forecastable. Performed at <b id="lbthr">{board?.thr || ''}</b>.</p>
        {!lb.data && !lb.error ? <div className={emptyCls()}>reading the leaderboard…</div> : null}
        {lb.error ? <div className={emptyCls()}>the leaderboard could not be read: {lb.error}</div> : null}
      </section>
      <section className={cardCls(false, 'panel')}>
        <h2>Approaching chaining <span className="note">the closest to chaining: the cards every chainer holds, then following one premise. Models not chaining yet, ranked by how many of the four necessary cards they hold, then by the logic deck's one-hop lift</span></h2>
        <div className="scroll">
          <table id="lbapproach" data-nosort>
            <thead><tr><th>#</th><th>model</th><th>parameters</th><th>the necessary cards <span className="s">P♣ N♠ M♦ C♥</span></th><th title="the logic deck's lift on one-hop items: following one premise">one-hop lift</th><th title="the logic deck's chaining gain on its cause items; eight items: a strong reading counts, a small one is noise">cause and effect</th><th title="below +0.03 it is noise">chaining lift <span className="s">noise</span></th></tr></thead>
            <tbody dangerouslySetInnerHTML={{ __html: board?.approach || '' }} />
          </table>
        </div>
        <p className="note mt">Below the line nothing is ranked by chaining lift: below +0.03 it is noise. The four cards are the ones every model that chains plays (the card judge's necessary cards); one hop is following a single premise, the step before chaining two. One-hop lifts within 0.05 of each other are noise, so those rows tie and share a rank (=5), listed biggest first. Cause and effect, on both boards, is the logic deck's chaining gain on its cause items: eight items, so a strong reading counts and a small one is noise (the mark, 0.1, dotted).</p>
      </section>

      <details className={cardCls(false, 'panel lbfold')} id="lbfoldsmoke" onToggle={(e) => { if (e.currentTarget.open && sq.data) void drawSmokingChart(sq.data); }}>
        <summary><h2>Smoking the 2–4B range <span className="note">P(a Thorp a tenth the size of each 2–4B model chains two facts as well as it), the least of them over the range: the fits, the backtest and the rule</span></h2></summary>
        <div id="smokingqwen">
          <div className="sqhead" id="sqhead" dangerouslySetInnerHTML={{ __html: smoking?.head || '' }} />
          <div className="row sqrow">
            <div className="chart tall" id="sqchart" />
            <div className="sqside">
              <div className="k">Does the method work? <span className="s">the same fit where the answer is known</span></div>
              <div id="sqbacktest" dangerouslySetInnerHTML={{ __html: smoking?.backtest || '' }} />
              <div className="k mt">The rule <span className="s">pre-registered (DECISIONS.md, "Smoking Qwen, pre-registered")</span></div>
              <p className="s" id="sqrule">{smoking?.rule || ''}</p>
            </div>
          </div>
        </div>
      </details>

      <details className={cardCls(false, 'panel lbfold')}>
        <summary><h2>Every ship <span className="note">every ship with chaining readings, its voyages averaged, by chaining lift</span></h2></summary>
        <div className="handtools" data-filters>
          <label className="note" htmlFor="lbclass">size</label>
          <select className={selectCls('')} id="lbclass" value={want} onChange={(e) => setWant(e.target.value)}>
            <option value="">every size</option>
            {presets.map((p) => <option key={p} value={p}>{p}{nameOf(p) ? ` · ${nameOf(p)}` : ''}</option>)}
          </select>
          <span className="note" id="lbcount">{runs?.count || ''}</span>
        </div>
        <div className="scroll">
          <table id="lbruns">
            <thead dangerouslySetInnerHTML={{ __html: runs?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: runs?.body || '' }} />
          </table>
        </div>
      </details>
    </div>
  );
}
