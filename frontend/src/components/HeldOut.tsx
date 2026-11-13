// The Library's third section, Held out (13 November, Justin: "we need an easy place to find tools heldout and all
// the other type of "hole" type content"): every set a ship is scored on and never trains on, in three groups (the
// questions the legs' tests ask, the decks of books, the field's own tests), each opening to its items. The data is
// backend/thorp/heldout.py, through /api/heldout and /api/heldout_items. A set opens at /library/held-out?set=<key>.

import { useEffect, useState } from 'react';
import { cardCls, emptyCls, fieldCls, pillCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

interface HeldSet {
  key: string; name: string; group: 'questions' | 'books' | 'outside'; path: string; status: string;
  tests: string; reads: string; made: string; present: boolean; count: number | null;
  kinds: Record<string, number>; specs: string[];
}
interface HeldItem { key: string; kind: string; question: string; before: string[][]; expect: string[][] }
interface ItemsData { key: string; total: number; of: number; offset: number; items: HeldItem[]; error?: string }

const GROUPS: [HeldSet['group'], string, string][] = [
  ['questions', 'Questions the ships are asked', 'held out of the legs’ lessons: each item has its question and what a right answer is'],
  ['books', 'Books the ships are scored on', 'whole books no training run reads; a ship is scored on how cheaply it predicts them'],
  ['outside', 'The field’s own tests', 'kept under data/, as their licences keep them out of the repository'],
];
const PAGE = 40;

const setFromUrl = (): string => (typeof location === 'undefined' ? '' : new URLSearchParams(location.search).get('set') || '');

export default function HeldOut() {
  const { data, error } = useApi<{ sets: HeldSet[] }>('/api/heldout', 60000);
  const [open, setOpen] = useState('');
  useEffect(() => {
    const read = () => setOpen(setFromUrl());
    read();
    window.addEventListener('popstate', read);
    return () => window.removeEventListener('popstate', read);
  }, []);
  const choose = (key: string) => {
    const next = key === open ? '' : key;
    history.pushState(null, '', next ? `/library/held-out?set=${encodeURIComponent(next)}` : '/library/held-out');
    setOpen(next);
  };

  if (error) return <div className={emptyCls()}>the held-out sets could not be read: {error} (restart <span className="mono">thorp dash</span> if this server predates them)</div>;
  if (!data) return <div className={emptyCls()}>reading the held-out sets…</div>;
  const sets = data.sets || [];
  const chosen = sets.find((s) => s.key === open) || null;

  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>Held out <span className="note">everything a ship is tested on and never trains on, so a score measures what it learned, not what it memorised. Open a set to read its items</span></h2>
        {GROUPS.map(([g, title, note]) => {
          const these = sets.filter((s) => s.group === g);
          if (!these.length) return null;
          return (
            <div key={g} className="mt">
              <h3>{title}</h3>
              <p className="s heldnote">{note}</p>
              <div className="heldgrid">
                {these.map((s) => (
                  <button key={s.key} type="button" className={`heldcard${open === s.key ? ' on' : ''}${s.status === 'retired' ? ' retired' : ''}`} onClick={() => choose(s.key)} aria-expanded={open === s.key}>
                    <span className="heldtop">
                      <b>{s.name}</b>
                      <span className={pillCls('')}>{s.status}</span>
                    </span>
                    <span className="heldcount">{s.count == null ? 'not fetched' : `${s.count.toLocaleString()} ${g === 'books' ? (s.count === 1 ? 'book' : 'books') : 'items'}`}{s.specs.length ? ` · read by ${s.specs.length} spec${s.specs.length === 1 ? '' : 's'}` : ''}</span>
                    <span className="heldtests">{s.tests}</span>
                    <span className="mono s">{s.path}</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </section>
      {chosen ? <SetView key={chosen.key} s={chosen} /> : null}
    </>
  );
}

function SetView({ s }: { s: HeldSet }) {
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const [offset, setOffset] = useState(0);
  const [showSpecs, setShowSpecs] = useState(false);
  const url = s.group === 'outside' ? null
    : `/api/heldout_items?key=${encodeURIComponent(s.key)}&q=${encodeURIComponent(q)}&kind=${encodeURIComponent(kind)}&offset=${offset}&limit=${PAGE}`;
  const { data, error } = useApi<ItemsData>(url, 600000);
  useEffect(() => setOffset(0), [q, kind]);
  useEffect(() => { document.getElementById('heldset')?.scrollIntoView({ block: 'start', behavior: 'smooth' }); }, []);
  const kinds = Object.entries(s.kinds);
  const specs = showSpecs ? s.specs : s.specs.slice(0, 6);

  return (
    <section className={cardCls(false, 'panel')} id="heldset">
      <h2>{s.name} <span className="note mono">{s.path}</span></h2>
      <dl className="helddl">
        <dt>tests</dt><dd>{s.tests}</dd>
        <dt>read by</dt><dd>{s.reads}</dd>
        <dt>made</dt><dd>{s.made}</dd>
        {s.specs.length ? (
          <>
            <dt>specs</dt>
            <dd>
              {specs.map((n) => <span key={n} className="mono heldspec">{n}</span>)}
              {s.specs.length > 6 ? <button type="button" className="selchip" onClick={() => setShowSpecs(!showSpecs)}>{showSpecs ? 'fewer' : `and ${s.specs.length - 6} more`}</button> : null}
            </dd>
          </>
        ) : null}
      </dl>
      {s.group === 'outside' ? (
        <div className={emptyCls()}>its items are kept under <span className="mono">{s.path}</span> and read by the test itself; the scores are on the <a href="/leaderboard">leaderboard</a></div>
      ) : (
        <>
          <div className="heldtools">
            <input className={fieldCls()} type="search" placeholder="search the questions and answers…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="search this set" />
            {kinds.length ? (
              <span className="heldkinds">
                <button type="button" className={`selchip${kind === '' ? ' on' : ''}`} onClick={() => setKind('')}>every kind</button>
                {kinds.map(([k, n]) => (
                  <button key={k} type="button" className={`selchip${kind === k ? ' on' : ''}`} onClick={() => setKind(kind === k ? '' : k)}>{k} <i>{n}</i></button>
                ))}
              </span>
            ) : null}
          </div>
          {error ? <div className={emptyCls()}>could not read the items: {error}</div>
            : !data ? <div className={emptyCls()}>reading…</div>
            : data.error ? <div className={emptyCls()}>{data.error}</div>
            : (
              <>
                <div className="s mt">{data.total === data.of ? `${data.of.toLocaleString()} items` : `${data.total.toLocaleString()} of ${data.of.toLocaleString()} items`}{data.total > PAGE ? ` · ${offset + 1}–${Math.min(offset + PAGE, data.total)}` : ''}</div>
                <ol className="helditems">
                  {data.items.map((it) => (
                    <li key={it.key}>
                      <div className="heldhead"><span className="mono s">{it.key}</span>{it.kind ? <span className={pillCls('')}>{it.kind}</span> : null}</div>
                      {it.before.length ? (
                        <div className="heldbefore">{it.before.map((t, i) => <div key={i}>{t.join(' — ')}</div>)}</div>
                      ) : null}
                      <div className="heldq">{it.question}</div>
                      <dl className="heldexpect">
                        {it.expect.map(([label, text]) => (
                          <div key={label}><dt>{label}</dt><dd className={label === 'call' ? 'mono' : ''}>{text}</dd></div>
                        ))}
                      </dl>
                    </li>
                  ))}
                </ol>
                {data.total > PAGE ? (
                  <div className="heldpager">
                    <button type="button" className="selchip" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>← earlier</button>
                    <button type="button" className="selchip" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>later →</button>
                  </div>
                ) : null}
              </>
            )}
        </>
      )}
    </section>
  );
}
