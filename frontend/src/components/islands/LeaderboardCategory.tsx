// One category of test on its own page (13 November, Justin: "each category on the leaderboard needs its own
// page with all the relevant tests as cards with pros and cons of the test, and then when clicking on that
// test have the leaderboard show on that test"): /leaderboard/<category>. One card a test, with what it is, its
// pros and its cons (lib/testCatalog.ts); a click turns the card over and the leaderboard for that test shows.
// Our own tests read their boards from /api/leaderboard; a published test's board is Artificial Analysis's
// readings (data/benchmarks.json), kept apart from ours and never compared with them.

import { useEffect, useState } from 'react';
import { cardCls, crumbCls, emptyCls } from '@/lib/ui';
import { esc, fmtParams } from '@/lib/format';
import { TestCard } from '@/components/TestCard';
import { TabNav } from '@/components/TabNav';
import { PublishedBoards } from '@/components/islands/BenchBoard';
import { sectionProps, useApi } from '@/lib/useApi';
import { TEST_CATEGORIES } from '@/lib/testCategories';
import { catalogOf, type CatalogTest } from '@/lib/testCatalog';
import { boardHtml, faceBoardHtml, reasoningHtml } from '@/scripts/views/leaderboard-main';
import { arcAi2Html, ifevalHtml } from '@/scripts/views/leaderboard-steps';
import { bandOf, sizeOf } from '@/scripts/views/bands';
import bench from '@/data/benchmarks.json';

type Bench = (typeof bench.tests)[number];

const fixed = (x: number | null | undefined, n = 3): string => (x == null || !Number.isFinite(Number(x)) ? '–' : Number(x).toFixed(n));

/** The logic deck's board: every model with a reading, by its score, with the chaining gain beside it. */
function logicDeckHtml(lb: any): { head: string; body: string } {
  const rows = (lb?.table || []).filter((r: any) => r.logic && r.logic.score != null).sort((a: any, b: any) => b.logic.score - a.logic.score);
  const head = '<tr><th>#</th><th>model</th><th>parameters</th><th>score <span class="s">share right</span></th><th>chaining gain <span class="s">both premises less the better one</span></th><th>performed</th></tr>';
  const body = rows.map((r: any, i: number) => `<tr class="${r.kind === 'thorp' ? 'lb-thorp' : 'lb-outside'}"><td>${i + 1}</td><td><b>${esc(r.name)}</b></td><td>${fmtParams(r.params)}</td>
    <td><b>${fixed(r.logic.score)}</b></td><td>${fixed(r.logic.gain)}</td><td>${r.logic.performed ? '<span class="good">✓</span>' : '<span class="s">–</span>'}</td></tr>`).join('')
    || `<tr><td colspan="6" class="${emptyCls(true)}">no model has been read on the logic deck yet</td></tr>`;
  return { head, body };
}

/** The cause deck's board: the logic deck's chaining gain on its cause items, the one per-model reading held. */
function causeDeckHtml(lb: any): { head: string; body: string } {
  const rows = (lb?.table || []).filter((r: any) => r.cause_gain != null).sort((a: any, b: any) => b.cause_gain - a.cause_gain);
  const head = '<tr><th>#</th><th>model</th><th>parameters</th><th>cause-and-effect gain <span class="s">the mark is 0.1</span></th></tr>';
  const body = rows.map((r: any, i: number) => `<tr class="${r.kind === 'thorp' ? 'lb-thorp' : 'lb-outside'}"><td>${i + 1}</td><td><b>${esc(r.name)}</b></td><td>${fmtParams(r.params)}</td>
    <td><b class="${r.cause_gain >= 0.1 ? 'good' : ''}">${fixed(r.cause_gain)}</b></td></tr>`).join('')
    || `<tr><td colspan="4" class="${emptyCls(true)}">no model has a cause-and-effect reading yet</td></tr>`;
  return { head, body };
}

/** The chip on a card: where the test comes from, and how often its paper is cited (the audit's measure of how widely it is respected). */
const tagOf = (t: CatalogTest, published: boolean): string => {
  const base = published ? 'published' : t.tag || '';
  return t.cites ? `${base} · cited ~${t.cites.toLocaleString()}×` : base;
};

export default function LeaderboardCategory({ category }: { category: string }) {
  const cat = catalogOf(category);
  const meta = TEST_CATEGORIES.find((c) => c.key === category);
  const lb = useApi<any>('/api/leaderboard', 60000);
  const ladder = useApi<any>('/api/ladder', 300000);
  const sq = useApi<any>('/api/smoking_qwen', 60000, category === 'logic');
  const [open, setOpen] = useState<string | null>(null);
  // a test is linkable (?open=ifeval); the old ?test= addresses of the landing's cards still land here
  useEffect(() => {
    const k = new URLSearchParams(window.location.search).get('open');
    if (k) setOpen(k);
  }, []);

  if (!cat || !meta) return <div {...sectionProps('leaderboard')}><div className={emptyCls()}>no category of test is called {category}.</div></div>;

  const rungs = (ladder.data?.rungs || []).map((r: any) => ({ preset: r.preset, name: r.name, total: r.total }));
  const data = lb.data;
  const small = data ? (data.table || []).filter((r: any) => bandOf(sizeOf(r)) === 'small').map((r: any) => ({ ...r, size_class: 'small' })) : [];
  const chaining = data ? boardHtml({ ...data, table: small }, sq.data || {}, rungs, true, true, 'small') : null;

  const table = (h: { head: string; body: string } | null, id: string) => (
    <div className="scroll"><table id={id} data-nosort><thead dangerouslySetInnerHTML={{ __html: h?.head || '' }} /><tbody dangerouslySetInnerHTML={{ __html: h?.body || '' }} /></table></div>
  );

  /** The board on the back of a card: the leaderboard for that one test. */
  const back = (t: CatalogTest, title: string) => {
    if (t.board === 'published') return <PublishedBoards keys={[t.key]} />;
    if (!data) return <div className={emptyCls()}>{lb.error ? `the leaderboard could not be read: ${lb.error}` : 'reading the leaderboard…'}</div>;
    switch (t.board) {
      case 'logic-deck':
        return <><h3 className="tbacktitle">{title} <span className="note">every model read on the forty items, by share right; the chaining gain beside it is the lift with both premises less the better single premise, and a tick is a gain that clears its noise</span></h3>{table(logicDeckHtml(data), 'lbtestlogic')}</>;
      case 'cause-deck':
        return <><h3 className="tbacktitle">{title} <span className="note">the logic deck's chaining gain on its cause items — eight of them, so a strong value counts and a small one is noise. The full ninety-six-item deck has no per-model board yet</span></h3>{table(causeDeckHtml(data), 'lbtestcause')}</>;
      case 'chaining':
        return <><h3 className="tbacktitle">{title} <span className="note">the four chaining tests; the small class (1B–4B), the only class with a chaining reading: the models through the door, ranked by chaining lift, the forecasts and the reference ladder beside them. The other sizes are on their own pages</span></h3>{table(chaining, 'lbtestchaining')}<p className="note mt">Each cell is a lift and the share of pairs right; ✓ where performed (lift 0.1 and two in three right). A Nothing up my sleeve size is its best ship, its voyages averaged. The chaining gain is the logic deck's, the proof that a pass is chaining and not knowing or one premise.</p></>;
      case 'arc': {
        const a = arcAi2Html(data, 'all');
        return <><h3 className="tbacktitle">{title} <span className="note">every model read, across every size, ranked by ARC-Easy: the anchor, with ARC-Challenge the floor beside it. A question the tokeniser cannot spell, or one whose loss comes back non-finite, is skipped and counted, never scored wrong</span></h3><div className="sqhead" dangerouslySetInnerHTML={{ __html: a.lead || '' }} />{table(a, 'lbtestarc')}<p className="note mt">Chance is 25%. Not comparable with published ARC numbers, which are 25-shot and scored on the letter. Contamination is not ruled out.</p></>;
      }
      case 'ifeval': {
        const i = ifevalHtml(data, 'all');
        return <><h3 className="tbacktitle">{title} <span className="note">every reading across every size: prompt-level strict is the board, instruction-level strict sits beside it, and how each model was asked is its own column. A rigged row stands below the line and is never quoted without the word</span></h3><div className="sqhead" dangerouslySetInnerHTML={{ __html: i.lead || '' }} />{table(i, 'lbtestifeval')}</>;
      }
      case 'arcagi2': {
        const r = data.reasoning ? reasoningHtml(data.reasoning) : null;
        return <><h3 className="tbacktitle">{title} <span className="note">the published scores and our own readings, kept apart: a model prompted cold and a model trained on the ARC tasks are two different contests. A pilot is never compared with a published score</span></h3>{table(r, 'lbtestarcagi2')}<p className="note mt">{data.reasoning?.about || ''}</p></>;
      }
      case 'face': {
        const f = data.faces ? faceBoardHtml(data.faces, t.key, rungs) : null;
        return <><h3 className="tbacktitle">{title} <span className="note">each class's best ship for this Face beside Qwen 3 4B, the reference chainer: ✓ at the mark, ≈ within 10% of it. A Face is earned by its ability passing the mark, not pinned</span></h3>{table(f, `lbface${t.key}`)}</>;
      }
      default:
        return <><h3 className="tbacktitle">{title} <span className="note">there is no board for this test yet</span></h3><div className={emptyCls()}>{t.noBoard || 'no readings yet'}</div></>;
    }
  };

  return (
    <div {...sectionProps('leaderboard')}>
      <h1>
        <a className={crumbCls('back')} href="/leaderboard">← leaderboard</a> {meta.label}{' '}
        <span className="q">{cat.about}</span>
      </h1>
      <TabNav
        ariaLabel="categories of test"
        items={TEST_CATEGORIES.map((c) => ({ key: c.key, label: c.label, href: `/leaderboard/${c.key}`, active: c.key === category }))}
      />
      <section className={cardCls(false, 'panel')} id="lbcategory">
        <h2>The tests <span className="note">ours first, then the five most-cited industry standards, most cited first: how often a test's paper is cited is on its card. One card a test, with what it is good for and where it misleads: turn a card over for the leaderboard on that test. The pros and cons are our own reading, written for deciding what to trust; a published reading is Artificial Analysis's, never ours</span></h2>
        <div className={`testcards${open ? ' has-open' : ''}`}>
          {[...cat.tests].sort((a, b) => Number(b.source === 'ours') - Number(a.source === 'ours') || (b.cites ?? 0) - (a.cites ?? 0)).map((t) => {
            const p = t.source === 'published' ? ((bench.tests as Bench[]).find((x) => x.key === t.key) || null) : null;
            if (t.source === 'published' && !p) return null;
            const name = p ? p.name : t.name!;
            return (
              <TestCard
                key={t.key}
                id={t.key}
                open={open}
                setOpen={setOpen}
                art={`/art/lbtest-${t.key}.png`}
                plate={tagOf(t, !!p)}
                name={name}
                tag={tagOf(t, !!p)}
                about={p ? p.about : t.about!}
                link={p ? p.link : t.link!}
                pros={t.pros}
                cons={t.cons}
              >
                {back(t, name)}
              </TestCard>
            );
          })}
        </div>
      </section>
    </div>
  );
}

