// S5's feedback, the first thing on S5's page (13 November, Justin: "I'd like feedback to be the main UX function. So
// that I go into that page, as Justin, in order to see what feedback has been received from the other units and then
// it categorizes those into a taxonomy that will allow the intelligence layer in S4 to make good decisions").
// Everything the other systems send up (thorp/viable/s5_policy/feedback.py, /api/liberty-machine/feedback), each item
// with its source, sorted into the taxonomy's five categories: what S4 does with it when it next plans. The category
// tiles and the source chips filter the list. Read-only: a proposal is decided with `thorp proposals sign N`.

import { useMemo, useState } from 'react';
import { cardCls, emptyCls, pillCls, toggleCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

type Item = {
  id: string; category: string; kind: string; source: string; by: string; title: string; detail: string;
  at: string | null; area: string; count: number; usd: number | null; minutes: number | null; ref: Record<string, any>;
};
type Category = { key: string; name: string; means: string; s4: string };
type Payload = {
  version: string; at: string; days: number; counts: Record<string, number>; items: Item[]; unread: Record<string, string>;
  taxonomy: { version: string; adopted: string; categories: Category[]; kinds: { key: string; category: string; about: string }[] };
};

const when = (iso: string | null): string => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};

// the source as a reader says it: a system by its name, else who filed it
const SOURCE_NAME: Record<string, string> = {
  S1: 'S1 Operations', S2: 'S2 Coordination', S3: 'S3 Control', 'S3*': 'S3* Audit', S4: 'S4 Intelligence', S5: 'S5 Policy',
  session: 'a Claude session', person: 'a person',
};
// the category's tone: what needs Justin is the accent, what broke is bad, the rest stays quiet
const TONE: Record<string, string> = { DECIDE: 'accent', CONSTRAIN: '', REPAIR: 'bad', CALIBRATE: 'blue', LEARN: '' };

function stake(i: Item): string {
  const out: string[] = [];
  if (i.usd) out.push(`$${i.usd.toFixed(2)}`);
  if (i.minutes) out.push(`${Math.round(i.minutes)} min`);
  if (i.count > 1) out.push(`${i.count} records`);
  return out.join(' · ');
}

function Row({ i }: { i: Item }) {
  const s = stake(i);
  return (
    <li className="py-2 border-b border-border last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className={pillCls('')} title={SOURCE_NAME[i.source] || i.source}>{i.source}</span>
        <span className={pillCls(TONE[i.category] || '')}>{i.kind}</span>
        <b>{i.title}</b>
        {s ? <span className="s">{s}</span> : null}
      </div>
      {i.detail ? <div className="mt-1">{i.kind === 'proposal' ? <><b>Asks:</b> {i.detail}</> : i.detail}</div> : null}
      {i.kind === 'proposal' && i.ref.why ? <div className="s mt-1">{i.ref.why}</div> : null}
      <div className="s mt-1">
        from {i.by}{i.area ? ` · ${i.area}` : ''}{i.at ? ` · ${when(i.at)}` : ''}
        {i.kind === 'proposal' ? <> · <code>thorp proposals sign {i.ref.proposal} --words "…"</code></> : null}
      </div>
    </li>
  );
}

export function S5Feedback() {
  const { data, error } = useApi<Payload>('/api/liberty-machine/feedback', 60000);
  const [cat, setCat] = useState<string | null>(null);
  const [src, setSrc] = useState<string | null>(null);

  const sources = useMemo(() => {
    const n: Record<string, number> = {};
    for (const i of data?.items || []) n[i.source] = (n[i.source] || 0) + 1;
    return Object.entries(n).sort((a, b) => b[1] - a[1]);
  }, [data]);

  if (error && !data) return <section className={cardCls(false, 'panel')}><h2>Feedback to S5</h2><div className={emptyCls()}>the feedback could not be read: {error}</div></section>;
  if (!data) return <section className={cardCls(false, 'panel')}><h2>Feedback to S5</h2><div className={emptyCls()}>reading what the systems sent up…</div></section>;

  const cats = data.taxonomy.categories;
  const shown = data.items.filter((i) => (!cat || i.category === cat) && (!src || i.source === src));
  const total = data.items.length;

  return (
    <section className={cardCls(false, 'panel')} id="s5feedback">
      <h2>Feedback to S5 <span className="note">what the other systems have sent up, each with its source, sorted by what S4 does with it when it next plans. Read from the records they already keep: the proposals filed to S5, the last turn of the queue&apos;s cycle and its audit, and {data.days} days of the gate, the judge, the charter audit and the lanes</span></h2>

      {/* the five categories, each a filter: its count, what it means, what S4 does with it */}
      <div className="grid gap-2 mt-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-5" role="group" aria-label="Filter by category">
        {cats.map((c) => {
          const on = cat === c.key;
          return (
            <button
              key={c.key}
              type="button"
              aria-pressed={on}
              onClick={() => setCat(on ? null : c.key)}
              className={`text-left rounded-md border p-2 cursor-pointer bg-transparent ${on ? 'border-primary' : 'border-border hover:border-foreground'}`}
            >
              <div className="flex items-baseline gap-2">
                <b className={`text-2xl font-semibold ${data.counts[c.key] && c.key === 'DECIDE' ? 'text-primary' : ''}`}>{data.counts[c.key] || 0}</b>
                <span className="font-semibold">{c.name}</span>
              </div>
              <div className="s">{c.means}</div>
              <div className="s mt-1">S4: {c.s4}</div>
            </button>
          );
        })}
      </div>

      {/* who sent it */}
      <div className="flex flex-wrap items-center gap-1.5 mt-3" role="group" aria-label="Filter by source">
        <span className="s mr-1">from</span>
        <button type="button" className={toggleCls()} data-state={src === null ? 'on' : 'off'} onClick={() => setSrc(null)}>everyone · {total}</button>
        {sources.map(([s, n]) => (
          <button key={s} type="button" className={toggleCls()} data-state={src === s ? 'on' : 'off'} title={SOURCE_NAME[s] || s} onClick={() => setSrc(src === s ? null : s)}>
            {s} · {n}
          </button>
        ))}
      </div>

      {Object.keys(data.unread || {}).length ? (
        <div className="s mt-2">Not read this time: {Object.entries(data.unread).map(([k, v]) => `${k} (${v})`).join('; ')}</div>
      ) : null}

      {/* the items, under their category */}
      {shown.length ? cats.filter((c) => shown.some((i) => i.category === c.key)).map((c) => {
        const mine = shown.filter((i) => i.category === c.key);
        return (
          <div key={c.key} className="mt-4">
            <h3 className="m-0">{c.name} <span className="s">· {mine.length} · {c.means}; S4 should {c.s4}</span></h3>
            <ul className="list-none m-0 p-0">{mine.map((i) => <Row key={i.id} i={i} />)}</ul>
          </div>
        );
      }) : <div className={`${emptyCls()} mt-3`}>{total ? 'nothing under this filter' : 'nothing has been sent up'}</div>}

      <details className="mt-4">
        <summary className="s cursor-pointer">The taxonomy ({data.taxonomy.version}): each kind of record, and the category it always falls in</summary>
        <ul className="govlints mt-2">
          {data.taxonomy.kinds.map((k) => <li key={k.key}><span className={pillCls(TONE[k.category] || '')}>{k.key}</span> {k.category.toLowerCase()}: {k.about}</li>)}
        </ul>
        <p className="note mt">S4&apos;s code reads the same list with <code>thorp.viable.s5_policy.feedback.for_s4()</code>; <code>thorp feedback</code> prints it.</p>
      </details>
    </section>
  );
}
