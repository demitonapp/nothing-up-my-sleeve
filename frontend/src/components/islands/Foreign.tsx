// A foreign ship (UI.md "Zayton"): an outside model read on Nothing up my sleeve's decks, shown in the Market
// Harbour so it can be spied on. Read-only — no spec, no ledger run, no weights. This is the first
// panel converted from dashboard.ts to a typed client island (the rest follow it).

import { big } from '@/lib/format';
import { btnCls, crumbCls, emptyCls, pillCls, tabCls, tabsCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import Chat from './Chat';

interface ForeignLogic {
  [k: string]: number | null | undefined;
}

interface ForeignData {
  key: string;
  label: string;
  model: string;
  params: number | null;
  flag: string | null;
  flag_name?: string;
  hole_cards: { bpb: number | null; books: number | null } | null;
  logic: ForeignLogic | null;
  logic40: ForeignLogic | null;
  deck: { played?: string[]; falls?: Record<string, number> } | null;
  knockout: { verdict?: Record<string, unknown>; layers?: number | null } | null;
  chaining: Record<string, number | null> | null;
  chaining_lift: number | null;
}

const RELATIONS = ['gain', 'lift', 'score', 'gain_cause', 'gain_order', 'gain_membership', 'gain_proportion', 'gain_counterfactual'];

const f2 = (v: number | null | undefined): string => (v == null ? '–' : Number(v).toFixed(2));

const Stat = ({ k, v, s }: { k: string; v: string; s?: string }) => (
  <div className="govstat"><b>{v}</b><span>{k}{s ? ` · ${s}` : ''}</span></div>
);

export default function Foreign() {
  const route = useRoute();
  const parts = route.split('/').filter(Boolean); // ['foreign', key, tab?]
  const key = decodeURIComponent((parts[1] || '').trim());
  const tab = parts[2] === 'chat' ? 'chat' : 'readings';
  const { data: d, error } = useApi<ForeignData>(key ? `/api/foreign?key=${encodeURIComponent(key)}` : null);
  const href = (t: string): string => `/foreign/${encodeURIComponent(key)}${t === 'chat' ? '/chat' : ''}`;

  return (
    <div {...sectionProps('foreign')}>
      <h1>
        <a className={crumbCls('back')} href="/harbours/zayton">← Zayton</a>{' '}
        <span>{d?.label || key || 'foreign ship'}</span>{' '}
        <span className="q">
          {d ? (
            <>
              {d.flag ? <img className="flag" src={`/flags/${encodeURIComponent(d.flag)}.svg`} alt={d.flag_name || d.flag} title={d.flag_name || d.flag} loading="lazy" /> : null}{' '}
              {d.model} · {d.params ? `${big(d.params)} parameters` : 'parameters unknown'} · a foreign ship in Zayton
            </>
          ) : null}
        </span>
      </h1>
      {error ? (
        <div className={emptyCls()}>
          this foreign ship could not be read: {error} (restart <span className="mono">thorp dash</span> if this server predates it)
        </div>
      ) : !d ? (
        <div className={emptyCls()}>reading the foreign ship…</div>
      ) : (
        <>
          <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="foreignnav">
            <a className={tabCls('')} data-state={tab === 'readings' ? 'active' : 'inactive'} href={href('readings')}>Readings</a>
            <a className={tabCls('')} data-state={tab === 'chat' ? 'active' : 'inactive'} href={href('chat')}>Chat</a>
          </nav>
          <div className={`shiptab${tab === 'readings' ? ' active' : ''}`}>
            <ForeignBody d={d} />
          </div>
          <div className={`shiptab${tab === 'chat' ? ' active' : ''}`}>
            {tab === 'chat' ? (
              <>
                <h1>Chat <span className="q">with this foreign ship&apos;s own weights; its answer is a continuation, with no head audit (the audit reads our own GPT)</span></h1>
                <Chat modelKey={d.key} embedded />
              </>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function ForeignBody({ d }: { d: ForeignData }) {
  const lg = d.logic || {};
  const lg40 = d.logic40 || {};
  const ch = d.chaining || {};
  const played = d.deck?.played || [];
  const falls = d.deck?.falls || {};
  const chrows = Object.entries(ch).slice(0, 12);

  return (
    <>
      <img className="foreignart" src={`/art/${encodeURIComponent(d.key)}.png`} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} />
      <p style={{ margin: '8px 0 14px' }}>
        <a className={btnCls()} href={`/foreign/${encodeURIComponent(d.key)}/chat`}>Chat with this ship</a>{' '}
        <span className="note">experimental: the foreign ship&apos;s own MLX weights answer, if they are cached; no head audit on an outside model.</span>
      </p>
      <div className="harbourrules">
        <div className="k">
          A spyglass, not a ship of ours{' '}
          <span className="s">{d.label} is an outside model. Its readings are kept in s4.outside_readings; it has no spec, no ledger run and no weights here. Read-only.</span>
        </div>
      </div>
      <div className="govstats">
        <Stat k="held-out English" v={d.hole_cards ? f2(d.hole_cards.bpb) : '–'} s={d.hole_cards ? `${d.hole_cards.books} books, bpb` : 'not read'} />
        <Stat k="logic gain" v={f2(lg.gain)} s="8-item" />
        <Stat k="logic lift" v={f2(lg.lift)} s="8-item" />
        <Stat k="logic score" v={f2(lg.score)} s="8-item" />
        <Stat k="chaining lift" v={f2(d.chaining_lift)} s="four rungs" />
      </div>
      <div className="fbwrap">
        <div className="fbmain">
          <div className="fblabel">The logic deck <span className="s">8-item and 40-item readings</span></div>
          <div className="scroll">
            <table className="lbtable">
              <thead><tr><th>metric</th><th>8-item</th><th>40-item</th></tr></thead>
              <tbody>
                {RELATIONS.map((k) => (
                  <tr key={k}><td className="mono">{k}</td><td>{f2(lg[k])}</td><td>{f2(lg40[k])}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="fblabel">Cards it plays <span className="s">from its deck reading</span></div>
          <div className="s">
            {played.length ? played.map((x) => <span key={x} className={pillCls('good')}>{x}</span>) : 'no deck reading'}
          </div>
          <div className="fblabel">Falls <span className="s">cards it does not reach</span></div>
          <div className="s">
            {Object.entries(falls).slice(0, 20).map(([k, v]) => `${k} ${v}`).join(' · ') || '–'}
          </div>
        </div>
        <div className="fbpalette">
          <div className="fblabel">Chained two facts <span className="s">the four rungs' grades</span></div>
          <div className="scroll">
            <table className="lbtable">
              <tbody>
                {chrows.length ? chrows.map(([k, v]) => (
                  <tr key={k}><td className="mono">{k}</td><td>{f2(v)}</td></tr>
                )) : <tr><td className="s">no chain grades</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="fblabel">Knockout</div>
          <div className="s">
            {d.knockout ? `${Object.keys(d.knockout.verdict || {}).length} cards checked; ${d.knockout.layers || '–'} layers` : 'not read'}
          </div>
        </div>
      </div>
    </>
  );
}
