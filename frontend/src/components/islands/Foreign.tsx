// A foreign ship (UI.md "Masaq' Reach"): an outside model read on Nothing up my sleeve's decks, shown in the Market
// Harbour so it can be spied on. Read-only — no spec, no ledger run, no weights. This is the first
// panel converted from dashboard.ts to a typed client island (the rest follow it).

import { useEffect, useState } from 'react';
import { big } from '@/lib/format';
import { btnCls, cardCls, crumbCls, emptyCls, pillCls, selectCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import Chat from './Chat';
import { BAND, bandOf, sizeOf } from '@/scripts/views/bands';
import SectionNav from '../SectionNav';
import { TabNav } from '../TabNav';

interface ForeignLogic {
  [k: string]: number | null | undefined;
}

interface VersionRow {
  key: string; label: string; model: string; params: number | null;
  tuning: 'instruct' | 'base' | 'unknown'; cached: boolean; read: boolean; current: boolean;
}

interface TokenRow { token: string; id: number | null; single: boolean; embedding: boolean; roles: string[] }

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
  versions?: VersionRow[];
  control_tokens?: TokenRow[];
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
  const tab = parts[2] === 'chat' ? 'chat' : parts[2] === 'versions' ? 'versions' : 'readings';
  const { data: d, error } = useApi<ForeignData>(key ? `/api/foreign?key=${encodeURIComponent(key)}` : null);
  // the way back is the size band this ship sits in, not the harbour's landing (11 November, Justin)
  const band = d ? BAND(bandOf(sizeOf(d))) : null;
  // the chat tab can talk to either side of the family: the page's checkpoint, or its pulled base/instruct twin
  const [chatKey, setChatKey] = useState<string | null>(null);
  useEffect(() => { setChatKey(key || null); }, [key]);
  const href = (t: string): string => `/foreign/${encodeURIComponent(key)}${t === 'chat' ? '/chat' : t === 'versions' ? '/versions' : ''}`;

  return (
    <div {...sectionProps('foreign')}>
      <SectionNav />
      <h1>
        <a className={crumbCls('back')} href={band ? `/harbours/masaq-reach/${band.key}` : '/harbours/masaq-reach'} title={band ? `back to Masaq' Reach's ${band.name} band` : "back to Masaq' Reach"}>← {band ? band.name : "Masaq' Reach"}</a>{' '}
        <span>{d?.label || key || 'foreign ship'}</span>{' '}
        <span className="q">
          {d ? (
            <>
              {d.flag ? <img className="flag" src={`/flags/${encodeURIComponent(d.flag)}.svg`} alt={d.flag_name || d.flag} title={d.flag_name || d.flag} loading="lazy" /> : null}{' '}
              {d.model} · {d.params ? `${big(d.params)} parameters` : 'parameters unknown'} · a foreign ship in the Reach
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
          <TabNav
            id="foreignnav"
            ariaLabel="foreign ship sections"
            items={[
              { key: 'readings', label: 'Readings', href: href('readings'), active: tab === 'readings' },
              { key: 'versions', label: 'Versions', href: href('versions'), active: tab === 'versions' },
              { key: 'chat', label: 'Chat', href: href('chat'), active: tab === 'chat' },
            ]}
          />
          <div className={`shiptab${tab === 'readings' ? ' active' : ''}`}>
            <ForeignBody d={d} />
          </div>
          <div className={`shiptab${tab === 'versions' ? ' active' : ''}`}>
            {tab === 'versions' ? <VersionsBody d={d} /> : null}
          </div>
          <div className={`shiptab${tab === 'chat' ? ' active' : ''}`}>
            {tab === 'chat' ? (
              <>
                <h1>Chat <span className="q">with this foreign ship&apos;s own weights; its answer is a continuation, with no head audit (the audit reads our own GPT)</span></h1>
                {d.versions && d.versions.length > 1 ? (
                  <div className="handtools" data-filters>
                    <label className="note" htmlFor="chatver">version</label>
                    <select id="chatver" className={selectCls('')} value={chatKey || d.key} onChange={(e) => setChatKey(e.target.value)}>
                      {d.versions.map((v) => (
                        <option key={v.key} value={v.key} disabled={!v.cached}>
                          {v.tuning} · {v.label}{v.cached ? '' : ' (not pulled)'}
                        </option>
                      ))}
                    </select>
                    <span className="note">the base checkpoint continues text; its instruct twin was trained to answer</span>
                  </div>
                ) : null}
                <Chat key={chatKey || d.key} modelKey={chatKey || d.key} embedded />
              </>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function VersionsBody({ d }: { d: ForeignData }) {
  const rows = d.versions || [];
  const hasBoth = rows.some((r) => r.tuning === 'instruct') && rows.some((r) => r.tuning === 'base');
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>Base and instruct <span className="note">one family, both sides of the tuning line: a base checkpoint continues text; an instruct twin was trained to answer. “Read” means it has readings and its own page</span></h2>
      <div className="scroll">
        <table>
          <thead><tr><th>version</th><th>checkpoint</th><th>parameters</th><th>weights</th><th>page</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <td><span className={pillCls(r.tuning === 'instruct' ? 'good' : r.tuning === 'base' ? 'accent' : '')}>{r.tuning}</span></td>
                <td><b>{r.label}</b>{r.current ? <span className="s"> · this page</span> : null}<div className="s mono">{r.model}</div></td>
                <td>{r.params ? big(r.params) : '–'}</td>
                <td>{r.cached ? 'pulled' : <span className="s">not pulled</span>}</td>
                <td>{r.read ? <a href={`/foreign/${encodeURIComponent(r.key)}`}>read →</a> : <span className="s">not read yet</span>}</td>
              </tr>
            ))}
            {rows.length ? null : <tr><td colSpan={5} className={emptyCls(true)}>no base or instruct checkpoint is in the registry</td></tr>}
          </tbody>
        </table>
      </div>
      {rows.length && !hasBoth ? (
        <p className="note mt">No twin is in the registry: {d.label} was published as <b>{rows[0].tuning}</b> only, so there is no other side to compare.</p>
      ) : null}
    </section>
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
      <ControlTokens d={d} />
    </>
  );
}

function ControlTokens({ d }: { d: ForeignData }) {
  const [showAll, setShowAll] = useState(false);
  const all = useApi<any>(showAll ? '/api/foreign_control_tokens' : null, 0);
  const rows = d.control_tokens || [];
  return (
    <section className={cardCls(false, 'panel')} id="foreigncontroltokens" style={{ marginTop: 14 }}>
      <h2>Control tokens <span className="note">the special pieces {d.label}&apos;s own tokeniser declares — bos/eos/unk/pad, its added specials and the markers its chat template uses — with the id, whether the token is a single piece, and whether that id is inside its embedding table (an added piece past the vocabulary has no row until the embeddings are resized)</span></h2>
      {rows.length ? (
        <div className="scroll">
          <table className="lbtable">
            <thead><tr><th>token</th><th>id</th><th>one piece</th><th>in the embeddings</th><th>role</th></tr></thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.token}>
                  <td className="mono">{t.token}</td>
                  <td>{t.id ?? '–'}</td>
                  <td>{t.single ? 'yes' : 'no'}</td>
                  <td>{t.embedding ? 'yes' : <span className="accent">no — added past the vocabulary</span>}</td>
                  <td className="s">{(t.roles || []).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className={emptyCls()}>this ship&apos;s tokeniser is not in the MLX cache, so its control tokens cannot be read</div>}
      <details className="archive" onToggle={(e) => { if ((e.target as HTMLDetailsElement).open) setShowAll(true); }}>
        <summary>Every foreign ship&apos;s control tokens <span className="note">the same table across the Market Harbour: what each tokeniser declares and what is not in its embeddings</span></summary>
        {!showAll ? null : !all.data ? <div className={emptyCls()}>reading the tokenisers…</div> : (
          <div className="scroll">
            <table className="lbtable">
              <thead><tr><th>ship</th><th>control tokens</th><th>not in the embeddings</th></tr></thead>
              <tbody>
                {(all.data.models || []).map((m: any) => {
                  const ts = m.tokens || [];
                  return (
                    <tr key={m.key}>
                      <td><a href={`/foreign/${encodeURIComponent(m.key)}`}>{m.label}</a></td>
                      <td className="s">{ts.length ? ts.map((t: TokenRow) => t.token).join(' ') : 'not cached'}</td>
                      <td className="s">{ts.filter((t: TokenRow) => !t.embedding).map((t: TokenRow) => t.token).join(' ') || '–'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </section>
  );
}
