// One outside model (or a Thorp ship version), rendered by its own island: the chaining result, the
// logic deck, its cards and every rung (UI.md "Leaderboard"). The dense tables are in
// views/competitor.ts; the charts are drawn after render.

import { useEffect, useState } from 'react';
import { cardCls, crumbCls, emptyCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import { competitorHtml, drawCompetitorCharts } from '@/scripts/views/competitor';

export default function Competitor() {
  const route = useRoute();
  const thorp = route.startsWith('/leaderboard/thorp/');
  const key = decodeURIComponent((route.split('/')[3] || '').trim());
  const url = !key ? null : thorp ? `/api/thorp?ship=${encodeURIComponent(key)}` : `/api/competitor?model=${encodeURIComponent(key)}`;
  const comp = useApi<any>(url, 120000);
  const disc = useApi<any>('/api/discoveries', 120000);
  const ko = useApi<any>(!thorp && key ? `/api/knockout?model=${encodeURIComponent(key)}` : null, 120000);
  const [knock, setKnock] = useState<string | null>(null);
  const [koData, setKoData] = useState<any>(null);

  const stars = disc.data?.stars || [];
  const html = comp.data ? competitorHtml(comp.data, stars) : null;

  useEffect(() => {
    if (html) void drawCompetitorCharts(html, thorp);
  }, [comp.data, disc.data]);

  useEffect(() => {
    const k = ko.data?.results?.[0];
    setKoData(k || null);
    if (!k) { setKnock(null); return; }
    let live = true;
    (async () => {
      // views/knockouts imports ECharts at module load: import it after the page is in the browser
      const { knockoutBlock } = await import('@/scripts/views/knockouts');
      if (live) setKnock(knockoutBlock(k, 'cpkochart'));
    })();
    return () => { live = false; };
  }, [ko.data]);

  useEffect(() => {
    // draw only once the block is actually in the DOM: the state update above commits first, but a
    // frame may still be pending, so wait for the element rather than let ECharts throw
    if (!knock || !koData) return;
    let live = true;
    const draw = () => {
      if (!live) return;
      if (!document.getElementById('cpkochart')) { requestAnimationFrame(draw); return; }
      void import('@/scripts/views/knockouts').then(({ knockoutChart }) => { if (live) knockoutChart(koData, 'cpkochart'); });
    };
    draw();
    return () => { live = false; };
  }, [knock, koData]);

  if (comp.error) {
    return (
      <div {...sectionProps('competitor')}>
        <h1><a className={crumbCls('back')} href="/leaderboard">← leaderboard</a> <span>{key || 'competitor'}</span></h1>
        <div className={emptyCls()}>this model could not be read: {comp.error}</div>
      </div>
    );
  }
  if (!html) {
    return (
      <div {...sectionProps('competitor')}>
        <h1><a className={crumbCls('back')} href="/leaderboard">← leaderboard</a> <span>{key || 'competitor'}</span></h1>
        <div className={emptyCls()}>reading the model (its readings take a while)…</div>
      </div>
    );
  }

  return (
    <div {...sectionProps('competitor')}>
      <h1><a className={crumbCls('back')} href="/leaderboard">← leaderboard</a> <span id="cptitle">{html.title}</span> <span id="cppills" dangerouslySetInnerHTML={{ __html: html.pills }} /></h1>
      <section className={cardCls(false, 'panel')}><div className="rungover" id="cpover" dangerouslySetInnerHTML={{ __html: html.over }} /></section>

      <section className={cardCls(false, 'panel')}>
        <h2>Chaining two facts <span className="note">the four chaining tests (each its lift and share of pairs right, ✓ performed: lift 0.1 and two in three right), and the logic deck, the proof that a pass is chaining: invented words and counterfactual premises, each item asked with both premises, with one, swapped and padded, and at one, two and three hops</span></h2>
        <div className="cpsum" id="cpsum" dangerouslySetInnerHTML={{ __html: html.sum }} />
        <div className="scroll"><table id="cptests" data-nosort><thead><tr><th>test</th><th>chain</th><th>lift</th><th>share right</th><th></th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: html.tests }} /></table></div>
        <div className="row cplogic">
          <div><div className="k">The logic deck: each way of asking <span className="s">mean lift; the gain is both premises less the better single one</span></div><div className="chart" id="cpvariants" /></div>
          <div><div className="k">By kind of relation <span className="s">the chaining gain on each</span></div><div className="chart" id="cprelations" /></div>
        </div>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>Its hand <span className="note">the stars that do the trick, as playing cards: a card lit inside the model (at its mark by one head, or shared by two) is in its hand; one it hasn't lit is still in the deck, set aside face down with how close it came; "unreadable" where its attention can't be read through MLX-LM. Every model, outside or Thorp, is read by the same reader with its own tokeniser (previous-word and Nevermore on Goldsmith's essays, cards.copying_cards)</span></h2>
        <div id="cpcards" dangerouslySetInnerHTML={{ __html: html.cards }} />
      </section>

      <section className={cardCls(false, 'panel')} id="cpknockout" hidden={!knock}>
        <h2>The knockout <span className="note">each card's 8 strongest heads silenced (their outputs zeroed on every pass) and the logic deck read again, beside three random draws of 8 heads from no card: a card is necessary when silencing it costs at least 0.1 of the cause gain (the comparator: the order gain) and more than twice the largest random drop (DECISIONS.md, "The knockout, pre-registered")</span></h2>
        <div id="cpknock" dangerouslySetInnerHTML={{ __html: knock || '' }} />
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>Every rung <span className="note">the four discovery chains, keel to the 50m (two facts chained); these are Thorp's internal measures, shown because this page describes the competitor. Each cell its lift and share right, ✓ performed</span></h2>
        <div className="scroll"><table id="cprungs" data-nosort><thead dangerouslySetInnerHTML={{ __html: html.rungsHead }} /><tbody dangerouslySetInnerHTML={{ __html: html.rungsBody }} /></table></div>
      </section>
    </div>
  );
}
