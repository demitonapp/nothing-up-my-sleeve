// A measured band's tests (12 November, Justin: "in the leaderboard /leaderboard/medium add cards for
// IFBench, Multi IF, Artifacts Bench, Terminal Bench and others as how we've done on the xsmall
// leaderboard"). The extra small band reads its tests from our own voyages; the medium band has no
// reading of ours yet, so its cards carry the *published* field — Artificial Analysis's November 2026
// numbers for the five medium models that have one — and say so on every card and in the note.
//
// The data is frontend/src/data/benchmarks.json: a build artifact like foreign.json, not a measurement.
// The cards are the extra small band's (components/TestCard.tsx); a test with no art gets its group's
// mark on the plate.

import { useEffect, useState } from 'react';
import { TestCard } from '@/components/TestCard';
import { cardCls, emptyCls } from '@/lib/ui';
import { esc, fmtParams } from '@/lib/format';
import { bandOf, type SizeBand } from '@/scripts/views/bands';
import bench from '@/data/benchmarks.json';

type Test = (typeof bench.tests)[number];
type Model = (typeof bench.models)[number];

const pct = (v: number, unit: string): string => (unit === '%' ? `${v.toFixed(1)}%` : String(Math.round(v)));

/** The rows of one test's board: the models of this band, best first, unread last. */
export function boardHtml(test: Test, models: Model[]): { head: string; body: string; lead: string; ranked: number } {
  const rows = models
    .map((m) => ({ m, v: (test.values as Record<string, number | null>)[m.key] ?? null }))
    .sort((a, b) => (b.v ?? -Infinity) - (a.v ?? -Infinity));
  const ranked = rows.filter((r) => r.v != null);
  const head = `<tr><th>#</th><th>model</th><th>parameters</th><th>score <span class="s">${test.unit === '%' ? 'percent' : 'Elo'}</span></th></tr>`;
  const body = rows.map((r) => {
    const i = ranked.findIndex((x) => x.m.key === r.m.key);
    const rank = r.v == null ? '–' : String(i + 1);
    return `<tr class="lb-outside${r.v == null ? ' unread' : ''}"><td>${rank}</td>
      <td><b>${esc(r.m.label)}</b><div class="s">${esc(r.m.maker)}</div></td>
      <td>${fmtParams(r.m.params)}</td>
      <td>${r.v == null ? '<span class="s">not published</span>' : `<b>${pct(r.v, test.unit)}</b>`}</td></tr>`;
  }).join('') || `<tr><td colspan="4" class="${emptyCls(true)}">no ${esc(test.name)} reading for this band</td></tr>`;
  const best = ranked[0];
  const lead = best
    ? `<div class="sqp"><b class="good">${pct(best.v as number, test.unit)}</b><span>${esc(best.m.label)}, the best of ${ranked.length} published</span></div>
       <div class="sqp"><b>${ranked.length}</b><span>of ${models.length} medium models have a published reading</span></div>`
    : `<div class="sqp"><b>–</b><span>no published reading for this band</span></div>`;
  return { head, body, lead, ranked: ranked.length };
}

/** The published tests of one leaderboard category (lib/testCategories.ts), one small board each over every
 *  outside model that has a reading, for the back of that category's card on /leaderboard. */
export function PublishedBoards({ keys, band }: { keys: string[]; band?: SizeBand }) {
  const tests = keys.map((k) => (bench.tests as Test[]).find((t) => t.key === k)).filter((t): t is Test => !!t);
  if (!tests.length) return null;
  // on a size page only that band's models; Artificial Analysis's readings here cover the medium class alone
  const models = (bench.models as Model[]).filter((m) => !band || bandOf(m.params) === band);
  if (!models.length) return <p className="note mt">No published reading for this size: {esc(bench.source.name)}'s readings here cover only the medium class (4B–32B), so these tests have no outside model to stand beside at this size yet.</p>;
  return (
    <>
      {tests.map((t) => {
        const b = boardHtml(t, models);
        return (
          <div key={t.key}>
            <h3 className="tbacktitle">Published · {t.name} <span className="note">{esc(bench.source.name)}'s readings, not ours; {t.unit === '%' ? 'percent' : 'Elo'}, higher is better · <a href={t.link.href} target="_blank" rel="noreferrer">{t.link.label} ↗</a></span></h3>
            <div className="scroll">
              <table data-nosort>
                <thead dangerouslySetInnerHTML={{ __html: b.head }} />
                <tbody dangerouslySetInnerHTML={{ __html: b.body }} />
              </table>
            </div>
          </div>
        );
      })}
    </>
  );
}

export function BenchBoard({ band }: { band: SizeBand }) {
  const [open, setOpen] = useState<string | null>(null);
  // a test can be opened by address (?open=ifbench), so a card's board is linkable
  useEffect(() => {
    const k = new URLSearchParams(window.location.search).get('open');
    if (k) setOpen(k);
  }, []);
  const models = (bench.models as Model[]).filter((m) => bandOf(m.params) === band);
  if (!models.length) return null;
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The tests <span className="note">one card a test this class is read on, from the published field: turn a card over for its board. These are Artificial Analysis's November 2026 readings, not ours — no model of this band has been read on them here yet</span></h2>
      <div className={`testcards${open ? ' has-open' : ''}`}>
        {(bench.tests as Test[]).map((t) => {
          const board = boardHtml(t, models);
          return (
            <TestCard
              key={t.key}
              id={t.key}
              open={open}
              setOpen={setOpen}
              plate={t.group}
              name={t.name}
              tag={t.group}
              about={t.about}
              link={t.link}
              stat={board.lead}
            >
              <h3 className="tbacktitle">{t.name} <span className="note">published readings, the medium band; {t.unit === '%' ? 'percent' : 'Elo'}, higher is better</span></h3>
              <div className="scroll">
                <table data-nosort>
                  <thead dangerouslySetInnerHTML={{ __html: board.head }} />
                  <tbody dangerouslySetInnerHTML={{ __html: board.body }} />
                </table>
              </div>
            </TestCard>
          );
        })}
      </div>
      <p className="note mt">Source: <a href={bench.source.href} target="_blank" rel="noreferrer">{esc(bench.source.name)}</a>. {esc(bench.source.note)} A published score is never our measurement: when a medium model is sailed on one of these tests, its reading joins this board with its own row and its own card, and the published rows stay beside it.</p>
    </section>
  );
}
