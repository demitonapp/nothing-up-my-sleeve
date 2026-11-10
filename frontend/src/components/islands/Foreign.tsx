// A foreign ship (UI.md "Zayton"): an outside model read on Nothing up my sleeve's decks, shown in the Market
// Harbour so it can be spied on. Read-only — no spec, no ledger run, no weights. This is the first
// panel converted from dashboard.ts to a typed client island (the rest follow it).

import { big } from '@/lib/format';
import { crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';

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
  const key = decodeURIComponent((route.split('/')[2] || '').trim());
  const { data: d, error } = useApi<ForeignData>(key ? `/api/foreign?key=${encodeURIComponent(key)}` : null);

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
        <ForeignBody d={d} />
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
