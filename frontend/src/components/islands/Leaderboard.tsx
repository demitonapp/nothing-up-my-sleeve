// Leaderboard (UI.md "Leaderboard"), as a client island. /leaderboard is the way in: the four size
// bands as cards (extra small under 1B, small 1B–4B, medium 4B–32B, large above 32B), then what is not
// one size's: ARC-AGI-2, the four Faces' scorecard, Smoking Qwen and the every-ship table. Each card
// opens its size's own page (/leaderboard/<band>, the `band` prop): the ranked chaining board and the
// approach board for that size. A size with no chaining reading yet carries its likeliest candidates
// to approach instead. The competitor and lab sub-views are their own pages for now (they keep the
// shared script); this page no longer loads dashboard.ts.

import { useEffect, useState } from 'react';
import { cardCls, checkCls, crumbCls, emptyCls, selectCls } from '@/lib/ui';
import { esc } from '@/lib/format';
import { TabNav } from '@/components/TabNav';
import { TestCard } from '@/components/TestCard';
import { StepsBoard } from '@/components/islands/StepsBoard';
import { CategoryCards } from '@/components/islands/CategoryCards';
import { CATEGORY_FACE, TEST_ALIASES, TEST_CATEGORIES } from '@/lib/testCategories';
import { sectionProps, useApi } from '@/lib/useApi';
import { bandCardsHtml, boardHtml, candidatesHtml, drawSmokingChart, facesHtml, runsHtml, smokingHtml } from '@/scripts/views/leaderboard-main';
import { arcAi2Html, ifevalHtml } from '@/scripts/views/leaderboard-steps';
import { BAND, BANDS, bandOf, sizeOf, type SizeBand } from '@/scripts/views/bands';
import { PUBLIC_EDITION } from '@/lib/edition';

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
  const faces = lb.data?.faces ? facesHtml(lb.data.faces, rungs) : null;
  const smoking = sq.data ? smokingHtml(sq.data) : null;
  // the landing's boards: the chaining board is the small class's (the only class with a reading);
  // ARC and IFEval are read across every size the payload holds, with the size in their own column
  const arcAll = lb.data ? arcAi2Html(lb.data, 'all') : null;
  const ifevalAll = lb.data ? ifevalHtml(lb.data, 'all') : null;
  const chainBest = (lb.data?.table || []).filter((r: any) => r.group === 'chaining').sort((a: any, b: any) => b.chaining_lift - a.chaining_lift)[0];
  const chainStat = chainBest ? `<div class="sqp"><b class="good">${Number(chainBest.chaining_lift).toFixed(3)}</b><span>${esc(chainBest.name)}, the best chaining lift through the door</span></div>` : '';
  const arcLead = arcAll?.lead || '';
  const ifevalLead = ifevalAll?.lead || '';
  const publishedLead = (lb.data?.reasoning?.published || [])[0];
  const reasonStat = publishedLead ? `<div class="sqp"><b>${Number(publishedLead.score).toFixed(1)}</b><span>${esc(publishedLead.label)}, the published lead; our ARC arm is a pilot</span></div>` : '';
  const faceReference = (lb.data?.faces?.reference || [])[0];
  const faceFleet = [...(lb.data?.faces?.fleet || [])].sort((a: any, b: any) => (b.held || []).length - (a.held || []).length)[0];
  const facesStat = faceReference ? `<div class="sqp"><b>${(faceFleet?.held || []).length} of 4</b><span>${esc(faceFleet?.name || 'our fleet')} holds the most of ours; ${esc(faceReference.label)} holds ${(faceReference.held || []).length} of 4</span></div>` : '';
  // a category is its own page now (13 November): the landing's old ?test=knowledge addresses forward to it
  useEffect(() => {
    if (band) return;
    const k = new URLSearchParams(window.location.search).get('test');
    if (k) window.location.replace(`/leaderboard/${TEST_ALIASES[k] || k}`);
  }, [band]);

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
          <h1><a className={crumbCls('back')} href="/leaderboard">← leaderboard</a> <span>{bandInfo?.name}</span> <span className="q">{bandInfo?.range}: {byStepsBand ? 'under 1B nothing chains two facts yet, so the board is ranked by AI2 ARC — Easy as the anchor and Challenge beside it, the one peer-recognised test at this size — with the steps to chaining, and each of our ships beside the outside model ten times its size, below' : 'the models of this size that chain, ranked by how well, and those not chaining yet, ranked by how close'}.{!PUBLIC_EDITION && <> The method is under <a href="/discoveries/tests?test=chaining">Discoveries, Tests: chaining two facts</a></>}</span></h1>
          <TabNav
            ariaLabel="model size"
            items={BANDS.map((b) => ({ key: b.key, label: <>{b.name} <span className="s">{b.range}</span></>, href: `/leaderboard/${b.key}`, active: b.key === band }))}
          />
        </>
      ) : (
        <>
          <h1>Leaderboard <span className="q">one card a category of test — logic, knowledge, reasoning, instruction following, coding, agent, long context and the four Faces (abilities): open a card for its page, with every test in it and the leaderboard on each; the boards by size are folded at the foot.{!PUBLIC_EDITION && <> The method is under <a href="/discoveries/tests?test=chaining">Discoveries, Tests: chaining two facts</a></>}</span></h1>
        </>
      )}

      {band && <CategoryCards lb={lb.data} error={lb.error} band={sizeTab} faces={faces} logicBack={byStepsBand ? undefined : <>
      <div>
        <h3 className="tbacktitle">Chaining <span className="note">the models through the door, ranked by chaining lift (the mean lift on the four chaining tests): a lift that clears the noise (+0.03), a chaining gain above its noise ({lb.data?.steps?.gain_noise ?? 0.05}) and at least one test performed. {isSmall ? 'The small class is measured on the four chaining tests.' : measuredChaining ? 'This class is measured on the four chaining tests.' : sizeTab === 'medium' ? 'The medium class is the next goal, and has no chaining reading yet.' : `The ${sizeTab} class has no chaining reading yet.`}</span></h3>
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
      </div>

      <div>
        <h3 className="tbacktitle">{measuredChaining ? 'Approaching chaining' : `The ${cands.length} likeliest ${sizeTab} candidates`} <span className="note">{measuredChaining
          ? "the closest to chaining: the cards every chainer holds, then following one premise. Models not through the door, including those whose tests pass with no chaining gain behind them, ranked by how many of the four necessary cards they hold, then by the logic deck's one-hop lift"
          : `no ${sizeTab} model has a chaining reading yet; these are the targets to approach, most likely first`}</span></h3>
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
      </div>

      </>} />}

      {byStepsBand && <StepsBoard lb={lb.data} error={lb.error} band={sizeTab} />}

      {!band && <>
      <section className={cardCls(false, 'panel')} id="lbtests">
        <h2>The categories of test <span className="note">one card a category, with the tests we measure and the published tests beside them: open one for its own page, with every test in it as a card and the leaderboard on each. A published reading is Artificial Analysis's, never ours; the boards by size are folded at the foot of the page</span></h2>
        {lb.data ? (
          <div className="testcards">
            {TEST_CATEGORIES.map((c) => {
              const f = CATEGORY_FACE[c.key];
              const stat = { logic: chainStat, knowledge: arcLead, reasoning: reasonStat, instruction: ifevalLead, abilities: facesStat }[c.key];
              return (
                <TestCard
                  key={c.key}
                  id={c.key}
                  href={`/leaderboard/${c.key}`}
                  art={f.art}
                  plate={c.label}
                  name={c.label}
                  tag={f.tag}
                  about={f.about}
                  ours={c.ours}
                  published={c.published}
                  link={f.link}
                  stat={stat}
                />
              );
            })}
          </div>
        ) : (
          <div className={emptyCls()}>{lb.error ? `the leaderboard could not be read: ${lb.error}` : 'reading the leaderboard…'}</div>
        )}
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

      <details className={cardCls(false, 'panel lbfold')} id="lbbands">
        <summary><h2>The boards by size <span className="note">the full chaining board and the approach board for one class: extra small under 1B, small 1B–4B, medium 4B–32B, large above 32B</span></h2></summary>
        <div className="cards bandcards" dangerouslySetInnerHTML={{ __html: lb.data ? bandCardsHtml(lb.data) : '' }} />
      </details>
      </>}
    </div>
  );
}
