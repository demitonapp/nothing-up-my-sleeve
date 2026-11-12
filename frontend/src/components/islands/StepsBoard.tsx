// The extra small band's lower boards (UI.md "Leaderboard"; the test cards moved to CategoryCards.tsx on 13 November). Once: AI2 ARC first (11 November, Justin: "have the
// leaderboard for ARC easy and challenge be the primary leaderboard here"), then the steps to
// chaining, each ship beside the outside model ten times its size, the readings against size, and
// ARC-AGI-2 for the band. Drawn by Leaderboard.tsx in place of the chaining and approach boards,
// which rank by a chaining lift that is noise under 1B. The renderers are
// views/leaderboard-steps.ts; the readings are thorp/arc_ai2.py and thorp/steps.py.

import { useEffect, useState } from 'react';
import { cardCls, emptyCls, selectCls } from '@/lib/ui';
import { drawStepsChart, STEP_METRICS, tenTimesHtml } from '@/scripts/views/leaderboard-steps';
import type { SizeBand } from '@/scripts/views/bands';

export function StepsBoard({ lb, error, band }: { lb: any; error: string | null; band: SizeBand }) {
  const [metric, setMetric] = useState('one_hop');
  const tenth = lb ? tenTimesHtml(lb, band) : null;
  const st = lb?.steps || {};

  useEffect(() => {
    if (lb) void drawStepsChart(lb, band, metric);
  }, [lb, band, metric]);

  if (!lb) return <section className={cardCls(false, 'panel')}><div className={emptyCls()}>{error ? `the leaderboard could not be read: ${error}` : 'reading the leaderboard…'}</div></section>;

  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>At a tenth the size <span className="note">the claim, as a table: each of our ships beside the outside model nearest ten times its size, measure by measure</span></h2>
        <div className="sqhead" dangerouslySetInnerHTML={{ __html: tenth?.lead || '' }} />
        <div className="scroll">
          <table id="lbtenth" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: tenth?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: tenth?.body || '' }} />
          </table>
        </div>
        <p className="note mt">The outside model is the one read nearest ten times the ship's parameters, and only from five to twenty times; a ship with none that close has no row to stand beside. Each cell is ours, then theirs. A one-hop lift within {st.one_hop_noise ?? 0.05} or a chaining gain within {st.gain_noise ?? 0.05} of the other is a <b>tie</b>; the cards and the steps are counts, so they tie only when equal. A ship <b>matches</b> when it is behind on nothing read on both sides. A ship on one sailing is one seed: its row is a reading, not yet a result.</p>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>Against size <span className="note">one reading against parameters, our ships and the outside models as two lines: the same reading at a tenth the size is our line sitting a decade to the left</span></h2>
        <div className="handtools">
          <label className="note" htmlFor="lbstepmetric">reading</label>
          <select className={selectCls('')} id="lbstepmetric" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {STEP_METRICS.map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}
          </select>
        </div>
        <div className="chart" id="lbstepschart" />
      </section>
    </>
  );
}
