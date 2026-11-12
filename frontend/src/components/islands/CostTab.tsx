// The settings page's Cost tab (/settings/cost; /api/settings/cost, thorp/dash/cost.py): what the GPUs hired
// from Vast.ai cost, by hour, day, week or month. Each hire's cost is spread over the time it was hired, so a
// bar is what was being spent in that hour or day; the week is the budget's own (Monday to Sunday, UTC). Each
// bar is stacked by what the money bought: a voyage that trained, a hire that never trained, a smoke test.
// Read-only: the budget is S5's term, set with `thorp charter terms`.

import { useState } from 'react';
import type { ReactNode } from 'react';
import { cardCls, emptyCls, pillCls, toggleCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

type By = 'hour' | 'day' | 'week' | 'month';
type Kind = 'trained' | 'never_trained' | 'smoke';
interface Bucket { start: string; label: string; now: boolean; trained: number; never_trained: number; smoke: number; total: number; hours: number; hires: number }
interface CostData {
  at: string; by: By; about: string; hires: number;
  buckets: Bucket[];
  now: { hour: number; day: number; week: number; month: number; cycle: number; all: number };
  budget: { weekly: number; week_left: number; voyage: number; cycle_hours: number; week_starts: string; counted: number | null;
            uncounted: { name: string; gpu: string; cost: number; status: string }[] };
  by_kind: Record<Kind, number>;
  by_gpu: { gpu: string; cost: number; hires: number; hours: number; never_trained: number }[];
  out: { name: string; gpu: string; dph: number; cost: number; since: string }[];
  top: { name: string; gpu: string; kind: Kind; cost: number; hours: number; start: string; status: string }[];
}

const BYS: { key: By; label: string }[] = [
  { key: 'hour', label: 'By hour' },
  { key: 'day', label: 'By day' },
  { key: 'week', label: 'By week' },
  { key: 'month', label: 'By month' },
];
/** What the money bought, in a fixed order and colour (the page's chart tokens; status colours are kept for status). */
const KINDS: { key: Kind; title: string; colour: string; about: string }[] = [
  { key: 'trained', title: 'Trained', colour: 'var(--blue)', about: 'a voyage that reached the sea and trained' },
  { key: 'never_trained', title: 'Never trained', colour: 'var(--accent)', about: 'a box that died fitting out, a voyage that sank in its first minutes, or a hire recalled' },
  { key: 'smoke', title: 'Smoke tests', colour: 'var(--c5)', about: 'the GPU checks: a few minutes on each class' },
];

const money = (v: number | null | undefined): string => {
  if (v == null) return '–';
  if (v === 0) return '$0';
  return v < 0.01 ? '<$0.01' : `$${v.toFixed(2)}`;
};
const when = (iso: string | null | undefined): string => {
  if (!iso) return '–';
  const d = new Date(iso);
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};
const kindTitle = (k: Kind): string => KINDS.find((x) => x.key === k)?.title ?? k;

function Stat({ k, v, s }: { k: string; v: ReactNode; s?: ReactNode }) {
  return <div className="stat"><div className="k">{k}</div><div className="v">{v}</div><div className="s">{s}</div></div>;
}

function Legend() {
  return (
    <div className="phaselegend">
      {KINDS.map((k) => <span key={k.key} title={k.about}><i style={{ background: k.colour }} />{k.title}</span>)}
    </div>
  );
}

/** Vertical stacked bars, one a bucket; the tallest sets the scale. A bar's title is its tooltip. */
function Bars({ rows, by }: { rows: Bucket[]; by: By }) {
  const most = Math.max(...rows.map((r) => r.total), 0);
  if (!most) return <div className={emptyCls()}>nothing was spent in this range</div>;
  const every = rows.length > 24 ? Math.ceil(rows.length / 12) : 1; // a label every few bars when there are many
  return (
    <div className="costchart" role="img" aria-label={`spend ${by} by ${by}: the table below has every figure`}>
      <div className="costaxis s"><span>{money(most)}</span><span>{money(most / 2)}</span><span>$0</span></div>
      <div className="costbars" style={{ gridTemplateColumns: `repeat(${rows.length}, minmax(0, 1fr))` }}>
        {rows.map((r, i) => (
          <div key={r.start} className={`costcol${r.now ? ' now' : ''}`}
            title={`${r.label}${r.now ? ' (so far)' : ''}: ${money(r.total)}${KINDS.filter((k) => r[k.key] > 0).map((k) => `\n  ${k.title} ${money(r[k.key])}`).join('')}${r.hires ? `\n  ${r.hires} hire${r.hires === 1 ? '' : 's'} began` : ''}`}>
            <div className="coststack" style={{ height: `${(100 * r.total) / most}%` }}>
              {KINDS.map((k) => (r[k.key] > 0 ? <i key={k.key} style={{ flexGrow: r[k.key], background: k.colour }} /> : null))}
            </div>
            <span className="costlabel s">{i % every === 0 || r.now ? r.label : ''}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CostTab() {
  const [by, setBy] = useState<By>('day');
  const { data: d, error } = useApi<CostData>(`/api/settings/cost?by=${by}`, 60000);
  if (error && !d) return <section className={cardCls(false, 'panel')}><h2>Cost</h2><div className={emptyCls()}>the cost could not be read: {error}. A server started before this tab was added has no /api/settings/cost: restart <code>thorp dash</code>.</div></section>;
  if (!d) return <section className={cardCls(false, 'panel')}><h2>Cost</h2><div className={emptyCls()}>reading the spend…</div></section>;
  const b = d.budget;
  const shown = d.buckets.filter((r) => r.total > 0 || r.now);
  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>Cost <span className="note">what the GPUs hired from Vast.ai have cost, from S3&apos;s spend log. Each hire&apos;s cost is spread over the time it was hired, so a bar is what was being spent then; lower is better</span></h2>
        <div className="strip">
          <Stat k="this hour" v={money(d.now.hour)} />
          <Stat k="today" v={money(d.now.day)} />
          <Stat k="this week" v={money(d.now.week)} s={`of ${money(b.weekly)} budget · ${money(b.week_left)} left`} />
          <Stat k="this month" v={money(d.now.month)} />
          <Stat k="all time" v={money(d.now.all)} s={`${d.hires} hire${d.hires === 1 ? '' : 's'}`} />
        </div>
        <div className="spendbar mt" role="img" aria-label={`the week: ${money(d.now.week)} of ${money(b.weekly)}`} title={`the week: ${money(d.now.week)} of ${money(b.weekly)}`}>
          <i style={{ display: 'block', height: '100%', width: `${Math.min(100, (100 * d.now.week) / Math.max(0.01, b.weekly))}%`, background: 'var(--blue)' }} />
        </div>
        <div className="s mt">The week began {when(b.week_starts)} (Monday 00:00 UTC). This planning cycle ({b.cycle_hours} h) has spent {money(d.now.cycle)}; one voyage may cost at most {money(b.voyage)}.</div>
        {b.counted != null && b.uncounted.length ? (
          <p className="note mt">The budget itself counts {money(b.counted)} this week: {b.uncounted.length} ship{b.uncounted.length === 1 ? ' was' : 's were'} released by hand and logged no cost ({b.uncounted.map((u) => `${u.name} on an ${u.gpu}, about ${money(u.cost)}`).join('; ')}). They are charged here at their hourly rate, so this tab reads higher than the budget by {money(Math.max(0, d.now.week - b.counted))}.</p>
        ) : null}
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>Spend over time <span className="note">{d.about}; hover a bar for its split. The bar marked is the one running now, so far</span></h2>
        <div className="mt" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
          {BYS.map((x) => (
            <button key={x.key} type="button" className={toggleCls()} data-state={by === x.key ? 'on' : 'off'} aria-pressed={by === x.key} onClick={() => setBy(x.key)}>{x.label}</button>
          ))}
          <span style={{ marginLeft: 'auto' }}><Legend /></span>
        </div>
        <Bars rows={d.buckets} by={by} />
        <details className="setfold">
          <summary>Every {by} with spend <span className="s">{shown.length} of {d.buckets.length}</span></summary>
          <div className="scroll">
            <table className="costtable" data-nosort>
              <thead><tr><th>{by}</th><th className="num">spent</th>{KINDS.map((k) => <th key={k.key} className="num">{k.title.toLowerCase()}</th>)}<th className="num">GPU hours</th><th className="num">hires begun</th></tr></thead>
              <tbody>
                {[...shown].reverse().map((r) => (
                  <tr key={r.start}>
                    <td><b>{r.label}</b>{r.now ? <span className="s"> · so far</span> : null}</td>
                    <td className="num"><b>{money(r.total)}</b></td>
                    {KINDS.map((k) => <td key={k.key} className="num">{r[k.key] ? money(r[k.key]) : <span className="s">–</span>}</td>)}
                    <td className="num">{r.hours ? r.hours.toFixed(1) : '–'}</td>
                    <td className="num">{r.hires || '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <div className="row">
        <section className={cardCls(false, 'panel')}>
          <h2>What it bought <span className="note">all time</span></h2>
          <div className="scroll">
            <table className="costtable" data-nosort>
              <thead><tr><th>kind</th><th className="num">spent</th><th className="num">share</th></tr></thead>
              <tbody>
                {KINDS.map((k) => (
                  <tr key={k.key}>
                    <td><span className="costdot" style={{ background: k.colour }} /> <b>{k.title}</b><div className="s">{k.about}</div></td>
                    <td className="num">{money(d.by_kind[k.key])}</td>
                    <td className="num">{d.now.all ? `${Math.round((100 * d.by_kind[k.key]) / d.now.all)}%` : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className={cardCls(false, 'panel')}>
          <h2>By GPU class <span className="note">all time</span></h2>
          <div className="scroll">
            <table className="costtable" data-nosort>
              <thead><tr><th>class</th><th className="num">spent</th><th className="num">hires</th><th className="num">hours</th><th className="num">never trained</th></tr></thead>
              <tbody>
                {d.by_gpu.map((g) => (
                  <tr key={g.gpu}>
                    <td><b>{g.gpu}</b></td>
                    <td className="num">{money(g.cost)}</td>
                    <td className="num">{g.hires}</td>
                    <td className="num">{g.hours.toFixed(1)}</td>
                    <td className="num">{g.never_trained ? money(g.never_trained) : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className={cardCls(false, 'panel')}>
        <h2>The costliest hires <span className="note">all time, the ten that cost most{d.out.length ? `; ${d.out.length} out now, charged to the minute` : ''}</span></h2>
        <div className="scroll">
          <table className="costtable" data-nosort>
            <thead><tr><th>voyage</th><th>class</th><th>hired</th><th className="num">hours</th><th className="num">spent</th><th>what it bought</th></tr></thead>
            <tbody>
              {d.top.map((t, i) => (
                <tr key={`${t.start}-${i}`}>
                  <td><b>{t.name}</b><div className="s">{t.status}</div></td>
                  <td>{t.gpu}</td>
                  <td className="s">{when(t.start)}</td>
                  <td className="num">{t.hours.toFixed(2)}</td>
                  <td className="num">{money(t.cost)}</td>
                  <td><span className={pillCls(t.kind === 'trained' ? 'blue' : t.kind === 'never_trained' ? 'accent' : '')}>{kindTitle(t.kind)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note mt">Only the Vast.ai hires are here: they are the only money in the spend log. This Mac&apos;s own electricity is not measured. As of {when(d.at)}.</p>
      </section>
    </>
  );
}
