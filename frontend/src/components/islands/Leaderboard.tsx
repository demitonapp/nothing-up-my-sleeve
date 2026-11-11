// Leaderboard (UI.md "Leaderboard"), as a client island. /leaderboard is the way in: the four size
// bands as cards (extra small under 1B, small 1B–4B, medium 4B–32B, large above 32B), then what is not
// one size's: ARC-AGI-2, the four Faces' scorecard, Smoking Qwen and the every-ship table. Each card
// opens its size's own page (/leaderboard/<band>, the `band` prop): the ranked chaining board and the
// approach board for that size. A size with no chaining reading yet carries its likeliest candidates
// to approach instead. The competitor and lab sub-views are their own pages for now (they keep the
// shared script); this page no longer loads dashboard.ts.

import { useEffect, useState } from 'react';
import { cardCls, checkCls, crumbCls, emptyCls, selectCls } from '@/lib/ui';
import { TabNav } from '@/components/TabNav';
import { StepsBoard } from '@/components/islands/StepsBoard';
import { sectionProps, useApi } from '@/lib/useApi';
import { bandCardsHtml, boardHtml, candidatesHtml, drawSmokingChart, facesHtml, reasoningHtml, runsHtml, smokingHtml } from '@/scripts/views/leaderboard-main';
import { BAND, BANDS, bandOf, sizeOf, type SizeBand } from '@/scripts/views/bands';

export default function Leaderboard({ band }: { band?: SizeBand }) {
  const lb = useApi<any>('/api/leaderboard', 60000);
  const sq = useApi<any>('/api/smoking_qwen', 60000);
  const ladder = useApi<any>('/api/ladder', 300000);
  const [want, setWant] = useState('');
  // the size this page is for; the landing page (no band) draws no board, only the cards that open one
  const sizeTab: SizeBand = band || 'small';
  const bandInfo = BAND(band);
  const [showFc, setShowFc] = useState(true);
  const [showPy, setShowPy] = useState(true);

  const rungs: { preset: string; name: string; total: number }[] = (ladder.data?.rungs || []).map((r: any) => ({ preset: r.preset, name: r.name, total: r.total }));
  const order = (p: string): number => { const i = rungs.findIndex((r) => r.preset === p); return i < 0 ? 99 : i; };
  const presets = [...new Set<string>((lb.data?.ships || []).map((r: any) => r.preset).filter(Boolean))].sort((a, b) => order(a) - order(b));
  const nameOf = (p: string): string => (rungs.find((r) => r.preset === p) || { name: '' }).name;

  // The three size bands are the Market Harbour's (bands.ts): small 300k–4B, medium 4B–32B, large
  // above 32B. A row is placed by its parameter count, not by the payload's older 30B boundary, so the
  // two pages cannot disagree.
  const table: any[] = lb.data?.table || [];
  const allCands: any[] = Object.values(lb.data?.candidates || {}).flat() as any[];
  const rowBand = (r: any): SizeBand => bandOf(sizeOf(r));
  const isSmall = sizeTab === 'small';
  // under 1B nothing chains, so the extra small band is read by the steps to chaining (StepsBoard)
  const byStepsBand = band === 'xsmall';
  const measured = table.filter((r: any) => rowBand(r) === sizeTab);
  const measuredChaining = measured.some((r: any) => r.group === 'chaining');
  const cands = allCands.filter((c: any) => rowBand(c) === sizeTab);

  const runs = lb.data ? runsHtml(lb.data, want, rungs) : null;
  // boardHtml filters its table by size_class; hand it the band's rows with that label so one definition
  // of the bands serves the whole board
  const boardData = lb.data ? { ...lb.data, table: measured.map((r: any) => ({ ...r, size_class: sizeTab })) } : null;
  const board = boardData ? boardHtml(boardData, sq.data || {}, rungs, showFc, showPy, sizeTab) : null;
  const candidate = lb.data ? candidatesHtml(cands, sizeTab) : null;
  const reasoning = lb.data?.reasoning ? reasoningHtml(lb.data.reasoning) : null;
  const faces = lb.data?.faces ? facesHtml(lb.data.faces, rungs) : null;
  const smoking = sq.data ? smokingHtml(sq.data) : null;

  useEffect(() => {
    if (!band && sq.data) void drawSmokingChart(sq.data);
  }, [band, sq.data]);

  // the sizes were tabs on this page once (?size=medium): an old address forwards to the size's page
  useEffect(() => {
    if (band) return;
    const s = new URLSearchParams(window.location.search).get('size');
    if (BAND(s)) window.location.replace(`/leaderboard/${s}`);
  }, [band]);

  return (
    <div {...sectionProps('leaderboard')}>
      {band ? (
        <>
          <h1><a className={crumbCls('back')} href="/leaderboard">← leaderboard</a> <span>{bandInfo?.name}</span> <span className="q">{bandInfo?.range}: {byStepsBand ? 'under 1B nothing chains two facts yet, so the board is ranked by AI2 ARC — Easy as the anchor and Challenge beside it, the one peer-recognised test at this size — with the steps to chaining, and each of our ships beside the outside model ten times its size, below' : 'the models of this size that chain, ranked by how well, and those not chaining yet, ranked by how close'}. The method is under <a href="/discoveries/tests?test=chaining">Discoveries, Tests: chaining two facts</a></span></h1>
          <TabNav
            ariaLabel="model size"
            items={BANDS.map((b) => ({ key: b.key, label: <>{b.name} <span className="s">{b.range}</span></>, href: `/leaderboard/${b.key}`, active: b.key === band }))}
          />
        </>
      ) : (
        <>
          <h1>Leaderboard <span className="q">the chaining boards by size — extra small under 1B, small 1B to 4B, medium 4B to 32B, large above 32B: the models that chain, ranked by how well; those not chaining yet, ranked by how close; the canonical intelligence ranking, ARC-AGI-2; and the four Faces — the Nevermore, Counter, Scales and Mover — beside Qwen 3 4B. The method is under <a href="/discoveries/tests?test=chaining">Discoveries, Tests: chaining two facts</a></span></h1>
          <div className="cards bandcards" dangerouslySetInnerHTML={{ __html: lb.data ? bandCardsHtml(lb.data) : '' }} />
        </>
      )}

      {byStepsBand && <StepsBoard lb={lb.data} error={lb.error} band={sizeTab} />}

      {band && !byStepsBand && <>
      <section className={cardCls(false, 'panel')}>
        <h2>Chaining <span className="note">the models through the door, ranked by chaining lift (the mean lift on the four chaining tests): a lift that clears the noise (+0.03), a chaining gain above its noise ({lb.data?.steps?.gain_noise ?? 0.05}) and at least one test performed. {isSmall ? 'The small class is measured on the four chaining tests.' : measuredChaining ? 'This class is measured on the four chaining tests.' : sizeTab === 'medium' ? 'The medium class is the next goal, and has no chaining reading yet.' : `The ${sizeTab} class has no chaining reading yet.`}</span></h2>
        {!lb.data ? (
          <div className={emptyCls()}>{lb.error ? `the leaderboard could not be read: ${lb.error}` : 'reading the leaderboard…'}</div>
        ) : isSmall ? (
          <>
            <div className="handtools">
              <label><input className={checkCls('')} type="checkbox" checked={showFc} onChange={(e) => setShowFc(e.target.checked)} /> Nothing up my sleeve's forecasts</label>
              <label><input className={checkCls('')} type="checkbox" checked={showPy} onChange={(e) => setShowPy(e.target.checked)} /> the reference ladder (Pythia, smaller Qwen)</label>
              <span className="note" id="lbfcnote" dangerouslySetInnerHTML={{ __html: board?.note || '' }} />
            </div>
            <div className="scroll">
              <table id="lbtable" data-nosort>
                <thead dangerouslySetInnerHTML={{ __html: board?.head || '' }} />
                <tbody dangerouslySetInnerHTML={{ __html: board?.body || '' }} />
              </table>
            </div>
            <p className="note mt">The leaderboard is the four chaining tests only (Nature's breeder, the mill test, the between test, the pigeonhole test; 96 pairs), each cell its lift and share of pairs right, ✓ when performed (lift 0.1 and two in three right); Nothing up my sleeve's other tests are internal. The chaining gain is the logic deck's: invented words and counterfactual premises, each item asked with both premises and with one; the lift with both less the better single premise, the proof that a pass is chaining, not knowing or one premise, so a model whose lift has no such gain behind it is on the approach board below, not here. A Nothing up my sleeve size is its best ship, its voyages averaged. The 2–4B models (Qwen, Phi, Llama, Gemma, SmolLM, base checkpoints where one exists) are the competitors: Nothing up my sleeve must chain two facts as well as each at a tenth its size, and they never grade the chains (the reference ladder does). Forecast rows (italic) are Nothing up my sleeve's own sizes fitted against size, straight (conservative) and bending (probable), as Smoking Qwen fits them; while fewer than three sizes are above the noise (0.03) they are curves through noise, shown but not trusted. "Nothing up my sleeve matches it at" is the size where each fit reaches that model's lift; "a tenth its size" is each fit's reading there, with the probability it reaches that model's lift once forecastable. Performed at <b id="lbthr">{board?.thr || ''}</b>.</p>
          </>
        ) : measured.some((r: any) => r.group === 'chaining') ? (
          <>
            <div className="scroll">
              <table id="lbtable" data-nosort>
                <thead dangerouslySetInnerHTML={{ __html: board?.head || '' }} />
                <tbody dangerouslySetInnerHTML={{ __html: board?.body || '' }} />
              </table>
            </div>
            <p className="note mt">A size class is measured on the four chaining tests only; a candidate is a target, not a result, and joins this board only once it has a chaining lift.</p>
          </>
        ) : (
          <>
            <div className={emptyCls()}>No {sizeTab} model has been scored on the four chaining tests yet. The likeliest candidates to approach are on the board below.</div>
            <p className="note mt">The four chaining tests are the only public measure. A candidate is a target, not a result: it joins this board only when it has a chaining lift on those tests. The small class's readings stay on their own page.</p>
          </>
        )}
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>{measuredChaining ? 'Approaching chaining' : `The ${cands.length} likeliest ${sizeTab} candidates`} <span className="note">{measuredChaining
          ? "the closest to chaining: the cards every chainer holds, then following one premise. Models not through the door, including those whose tests pass with no chaining gain behind them, ranked by how many of the four necessary cards they hold, then by the logic deck's one-hop lift"
          : `no ${sizeTab} model has a chaining reading yet; these are the targets to approach, most likely first`}</span></h2>
        {!lb.data ? null : measuredChaining ? (
          <>
            <div className="scroll">
              <table id="lbapproach" data-nosort>
                <thead><tr><th>#</th><th>model</th><th>parameters</th><th>the necessary cards <span className="s">P♣ N♠ M♦ C♥</span></th><th title="the logic deck's lift on one-hop items: following one premise">one-hop lift</th><th title="the logic deck's chaining gain: the lift with both premises less the better single premise; the door needs it above its noise">chaining gain<div className="s">logic deck</div></th><th title="the logic deck's chaining gain on its cause items; eight items: a strong reading counts, a small one is noise">cause and effect</th><th title="how many of the four chaining tests the model performs">passed</th><th title="below +0.03 it is noise; above it, a lift with no chaining gain behind it is not yet shown to be chaining">chaining lift</th></tr></thead>
                <tbody dangerouslySetInnerHTML={{ __html: board?.approach || '' }} />
              </table>
            </div>
            <p className="note mt">Below the line nothing is ranked by chaining lift: below +0.03 it is noise, and above it a lift with no chaining gain behind it (the logic deck's, above {lb.data?.steps?.gain_noise ?? 0.05}) is not yet shown to be chaining, however many of the four tests it performs. The four cards are the ones every model that chains plays (the card judge's necessary cards); one hop is following a single premise, the step before chaining two. One-hop lifts within 0.05 of each other are noise, so those rows tie and share a rank (=5), listed biggest first. Cause and effect, on both boards, is the logic deck's chaining gain on its cause items: eight items, so a strong reading counts and a small one is noise (the mark, 0.1, dotted).</p>
          </>
        ) : (
          <>
            <div className="scroll">
              <table id="lbcandidates" data-nosort>
                <thead dangerouslySetInnerHTML={{ __html: candidate?.head || '' }} />
                <tbody dangerouslySetInnerHTML={{ __html: candidate?.body || '' }} />
              </table>
            </div>
            <p className="note mt">The candidates are chosen on the evidence the board already has — the families that chain at 2–4B, the reasoning leaders of the open field, and one boundary case that fits a workstation — not on a chaining reading they do not have. Their order is a working order, not a result. The logic deck's gain and one-hop lift, where held, are the only evidence so far; the four chaining tests have not been run. A candidate enters the chaining board only when it has a chaining lift.</p>
          </>
        )}
      </section>

      </>}

      {!band && <>
      <section className={cardCls(false, 'panel')}>
        <h2>Reasoning <span className="note">the canonical intelligence ranking: ARC-AGI-2, pass@2 on the 120-task evaluation set. It is not comparable with the chaining lift — the chaining tests measure one skill on text, ARC-AGI-2 measures fluid intelligence on grids — so it stays a panel of its own. Published scores are the public leaderboard's, not our measurements; Nothing up my sleeve's reading is the Kipling ARC arm's.</span></h2>
        <div className="scroll">
          <table id="lbreasoning" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: reasoning?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: reasoning?.body || '' }} />
          </table>
        </div>
        <p className="note mt">{lb.data?.reasoning?.about || ''} The chaining board remains the near-term measure; ARC-AGI-2 is the north star the Kipling ARC arm is built towards (<a href="https://arcprize.org/arc-agi">ARC Prize</a>).</p>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>The four Faces <span className="note">the four Face cards' abilities — the Nevermore's copy gain, the Counter's sentence-position R², the Scales' order gain and the Mover's one-hop lift — beside Qwen 3 4B, the reference chainer. ✓ at the mark, ≈ within 10% of it; a class's cell names the run that gave its best in the title</span></h2>
        <div className="scroll">
          <table id="lbfaces" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: faces?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: faces?.body || '' }} />
          </table>
        </div>
        <p className="note mt">A Face is earned, not pinned: its ability passing is the card (the Nevermore predicts a repeated passage better the second time, the Counter reads how far into a sentence it is, the Scales orders the logic deck, the Mover follows one premise). The Mover is read by its one-hop ability, not its look: in Qwen 3 4B the head that scores highest on the Mover's look is a diffuse, sink-and-delimiter head, and the 300k's is its induction head, so the look is not the card. The fleet's row is each class's best ship for that Face (the run is in the cell's title); the reference is Qwen 3 4B, which itself holds two of the four by the marks and sits a hair under the Counter's.</p>
      </section>

      <details className={cardCls(false, 'panel lbfold')} id="lbfoldsmoke" onToggle={(e) => { if (e.currentTarget.open && sq.data) void drawSmokingChart(sq.data); }}>
        <summary><h2>Smoking the 2–4B range <span className="note">P(a Nothing up my sleeve a tenth the size of each 2–4B model chains two facts as well as it), the least of them over the range: the fits, the backtest and the rule</span></h2></summary>
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
      </>}
    </div>
  );
}
