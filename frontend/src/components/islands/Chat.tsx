// The chat page: one question at a time to one of Nothing up my sleeve's ships on the leaderboard.
// Experimental — the models are small and not instruction-tuned, so a run without a chat/QA arm
// continues prose rather than answers. The list comes from /api/chat/models, which reads the
// leaderboard, so every ship it can reach with a checkpoint is here (thorp.chat).
//
// Each answer carries an audit: the attention heads that lit while the answer was written, where
// each answer token looked back, the star tests read on this prompt, and the cards the ship holds
// (thorp.chat._audit). It is the same trace the Tests tab reads for an outside model, on our own GPT.

import { useEffect, useState } from 'react';
import { btnCls, cardCls, emptyCls, fieldCls, pillCls, selectCls } from '@/lib/ui';
import { fmt, fmtParams, postJSON } from '@/lib/format';
import { sectionProps, useApi } from '@/lib/useApi';

interface ModelRun { run: string; run_id: string; step: string }
interface Model {
  kind: 'thorp' | 'foreign';
  model?: string | null;
  ship_key: string;
  name: string;
  params: number | null;
  cards_held: number | null;
  cards: Record<string, { lit?: boolean; lit_shared?: boolean; max?: number; shared?: number }> | null;
  available: boolean;
  run: ModelRun | null;
  runs: string[];
  why: string | null;
}
interface ModelsPayload { models: Model[] }

interface Card {
  key: string; name: string;
  held: boolean | null; held_score: number | null; held_shared: number | null;
  mark: number; head: string | null;
  live: boolean | null; live_score: number | null; live_head: string | null;
  note: string;
}
interface Star { key: string; name: string; score: number; mark: number; lit: boolean; head: string; layer: number; head_no: number }
interface Head {
  layer: number; head: number; trigger: number; concentration: number; peak_weight: number;
  aimed_at: string | null; aimed_weight: number; sink: number; previous: number; offset2: number;
  induction: number; duplicate: number; delimiter: number; route: string; route_multiple: number;
  star: string | null; card: string | null;
}
interface Lookup { answer_index: number; token: string; layer: number; head: number; weight: number; looked_at: string; looked_at_index: number }
interface Audit {
  readable: boolean; reason?: string;
  layers?: number; heads_count?: number; prompt_tokens?: number; answer_tokens?: number;
  heads?: Head[]; selective?: Head[]; stars?: Star[]; cards?: Card[]; lookups?: Lookup[];
}
interface Msg {
  role: 'you' | 'thorp'; text: string;
  model?: string; step?: string; audit?: Audit | null;
}
interface ChatReply { run?: string; model?: string; step: string; prompt: string; format: string; answer: string; audit?: Audit; error?: string }

const headName = (h: { layer: number; head: number }): string => `L${String(h.layer).padStart(2, '0')}.H${String(h.head).padStart(2, '0')}`;
const heldLabel = (v: boolean | null): string => (v == null ? 'unread' : v ? 'held' : 'not held');
const liveLabel = (v: boolean | null): string => (v == null ? 'not read here' : v ? 'lit' : 'unlit');

function CardChip({ c }: { c: Card }) {
  const tone = c.live === true ? 'good' : c.live === false ? 'bad' : '';
  return (
    <div style={{ border: '1px solid var(--line)', borderRadius: 8, padding: '8px 10px', minWidth: 150 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <b>{c.name}</b>
        <span className={pillCls(c.held === true ? 'good' : c.held === false ? 'bad' : '')}>{heldLabel(c.held)}</span>
      </div>
      <div className="note" style={{ marginTop: 4 }}>
        {c.head ? <span className="mono">{c.head}</span> : c.key === 'bridge' ? 'no single head' : 'head not named'}
        {' · '}
        <span className={tone}>{liveLabel(c.live)}</span>
        {c.live_score != null ? ` ${fmt(c.live_score, 2)} / ${fmt(c.mark, 2)}` : ''}
      </div>
      <div className="note">
        held: {fmt(c.held_score, 2)} / {fmt(c.mark, 2)}
        {c.held_shared != null ? ` (shared ${fmt(c.held_shared, 2)})` : ''}
      </div>
      <div className="note">{c.note}</div>
    </div>
  );
}

function HeadTable({ heads }: { heads: Head[] }) {
  return (
    <div className="scroll">
      <table data-nosort>
        <thead>
          <tr><th>head</th><th>trigger</th><th>aimed at</th><th>previous</th><th>induction</th><th>star</th><th>card</th></tr>
        </thead>
        <tbody>
          {heads.map((h) => (
            <tr key={`${h.layer}-${h.head}`}>
              <td className="mono">{headName(h)}</td>
              <td>{fmt(h.trigger, 2)}</td>
              <td>“{h.aimed_at || '–'}”</td>
              <td>{fmt(h.previous, 2)}</td>
              <td>{fmt(h.induction, 2)}</td>
              <td>{h.star || '–'}</td>
              <td>{h.card || '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditPanel({ a, open = false }: { a: Audit; open?: boolean }) {
  if (!a.readable) {
    return <p className="note">The audit could not be read: {a.reason || 'unknown reason'}.</p>;
  }
  const heads = (a.heads || []).slice(0, 8);
  const lookups = (a.lookups || []).slice(0, 12);
  const cards = a.cards || [];
  const stars = (a.stars || []).filter((s) => s.lit).slice(0, 8);
  const selective = (a.selective || []).slice(0, 8);
  const liveCards = cards.filter((c) => c.live === true).length;
  const litHeads = heads.filter((h) => h.star || h.card).length;
  return (
    <details open={open} style={{ marginTop: 8 }}>
      <summary className="note" style={{ cursor: 'pointer' }}>
        audit · {a.answer_tokens || 0} answer tokens · {liveCards} card{liveCards === 1 ? '' : 's'} live · {litHeads} named head{litHeads === 1 ? '' : 's'} in the top eight · {a.layers || 0} layers × {a.heads_count || 0} heads
      </summary>

      <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
        <div>
          <div className="k">The hand <span className="s">the cards this ship holds, read over all its sailings; “this answer” re-reads the card’s test on this prompt where the test fits one</span></div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {cards.map((c) => <CardChip key={c.key} c={c} />)}
          </div>
        </div>

        {stars.length ? (
          <div>
            <div className="k">Star tests lit on this answer <span className="s">the same tests the leaderboard reads, on this prompt: one word back, two back, the opening mark, repeated words, induction, punctuation</span></div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {stars.map((s) => (
                <span key={s.key} className={pillCls('good')} title={`${s.score} against ${s.mark}`}>
                  {s.name} <span className="mono">{s.head}</span> {fmt(s.score, 2)}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <div className="k">Heads that lit over the answer <span className="s">each head’s strongest attention over the tokens the answer was chosen from, ranked; “aimed at” is the token most of that attention landed on; a card names the head the run’s own readings know</span></div>
          <HeadTable heads={heads} />
        </div>

        {selective.length ? (
          <div>
            <div className="k">Heads aimed at content <span className="s">the same ranking without the sink heads, which park on the opening mark when they have nothing to read</span></div>
            <HeadTable heads={selective} />
          </div>
        ) : null}

        {lookups.length ? (
          <div>
            <div className="k">What each answer token looked up <span className="s">the head and the question-side token it read hardest when it wrote the token</span></div>
            <div className="scroll">
              <table data-nosort>
                <thead>
                  <tr><th>answer token</th><th>head</th><th>looked at</th><th>weight</th></tr>
                </thead>
                <tbody>
                  {lookups.map((l) => (
                    <tr key={l.answer_index}>
                      <td className="mono">{l.token || '–'}</td>
                      <td className="mono">{headName(l)}</td>
                      <td>“{l.looked_at}”</td>
                      <td>{fmt(l.weight, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>
    </details>
  );
}

const valueOf = (m: Model): string => (m.kind === 'foreign' ? String(m.model || '') : m.run?.run || '');

/** The chat panel. On /chat it lists every target; on a ship page it is embedded with that ship
 *  fixed (`shipKey` for a Nothing up my sleeve ship, `modelKey` for a foreign one) and hides the
 *  picker, so the ship's own tab is the whole chat. */
export default function Chat({ shipKey, modelKey, embedded = false }: { shipKey?: string; modelKey?: string; embedded?: boolean } = {}) {
  const models = useApi<ModelsPayload>('/api/chat/models', 0);
  const [target, setTarget] = useState('');
  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');

  const all = models.data?.models || [];
  const available = all.filter((m) => m.available && (m.run || m.model));
  const thorp = available.filter((m) => m.kind !== 'foreign');
  const foreign = available.filter((m) => m.kind === 'foreign');

  // an embedded chat is pinned to the page's ship; the full list only picks for /chat
  const fixed = embedded
    ? modelKey
      ? all.find((m) => m.kind === 'foreign' && m.model === modelKey) || null
      : shipKey
        ? all.find((m) => m.kind !== 'foreign' && m.ship_key === shipKey) || null
        : null
    : null;
  const unavailable = fixed && !(fixed.available && (fixed.run || fixed.model)) ? fixed : null;
  const selected = fixed
    ? (unavailable ? null : fixed)
    : available.find((m) => valueOf(m) === target) || available[0] || null;

  // /chat?ship=<ship_key> and /chat?model=<key> preselect a target (the old ship-page links)
  useEffect(() => {
    if (embedded || !available.length) return;
    const q = new URLSearchParams(location.search);
    const ship = q.get('ship'), wantModel = q.get('model');
    const want = wantModel
      ? available.find((m) => m.kind === 'foreign' && m.model === wantModel)
      : ship ? available.find((m) => m.ship_key === ship) : null;
    const largest = thorp.slice().sort((a, b) => (b.params || 0) - (a.params || 0))[0];
    const next = want ? valueOf(want) : target || valueOf(largest || available[0]);
    if (next !== target) setTarget(next);
  }, [models.data, target, embedded]);

  const send = async (): Promise<void> => {
    const q = input.trim();
    if (!q || busy || !selected) return;
    setMsgs((m) => [...m, { role: 'you', text: q }]);
    setInput('');
    setBusy(true);
    setNote('');
    try {
      const body = selected.kind === 'foreign'
        ? { model: selected.model, q, tokens: 80, temperature: 0.7 }
        : { run: selected.run!.run, q, tokens: 80, temperature: 0.7 };
      const d = await postJSON<ChatReply>('/api/chat', body);
      if (d.error) setNote(String(d.error));
      else setMsgs((m) => [...m, { role: 'thorp', text: String(d.answer || ''), model: selected.name, step: d.step, audit: d.audit || null }]);
    } catch (e) {
      setNote(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const root = embedded ? { className: 'chatembed' } : sectionProps('chat');
  return (
    <div {...root}>
      {embedded ? null : (
        <h1>Chat <span className="q">with Nothing up my sleeve’s small ships from the leaderboard and the foreign ships in Zayton; experimental: the models are small and not instruction-tuned, so a run without a chat/QA arm continues prose rather than answers. A Nothing up my sleeve answer is audited: the heads that lit while it was written, what each token looked up, and the cards the ship holds (thorp.chat); a foreign answer is the outside model’s own continuation, with no audit</span></h1>
      )}
      <section className={cardCls(false, 'panel')}>
        {embedded ? (
          <div className="handtools" data-filters>
            <span className="note">
              {selected ? (
                selected.kind === 'foreign'
                  ? <>chatting with <b>{selected.name}</b> ({fmtParams(selected.params)}): its own MLX weights; the answer is its continuation, with no head audit.</>
                  : <>chatting with <b>{selected.name}</b> · run <span className="mono">{selected.run?.run}</span> · checkpoint {selected.run?.step} · {selected.cards_held ?? '–'} of 4 necessary cards held. Every answer is audited below.</>
              ) : models.error
                ? `the ships could not be read: ${models.error}`
                : models.loading
                  ? 'reading the ship…'
                  : unavailable
                    ? `this ship cannot chat yet: ${unavailable.why || 'no finished checkpoint or cached weights'}`
                    : 'this ship has no chat target: it is not on the leaderboard, or it has no finished checkpoint.'}
            </span>
          </div>
        ) : (
          <div className="handtools" data-filters>
            <label className="note" htmlFor="chatrun">ship</label>
            <select
              id="chatrun"
              className={selectCls('')}
              value={selected ? valueOf(selected) : ''}
              onChange={(e) => { setTarget(e.target.value); setMsgs([]); setNote(''); }}
              disabled={busy}
              title="the ship to load: a Nothing up my sleeve finished run with a checkpoint, or a foreign model whose MLX weights are cached"
            >
              {models.loading ? <option value="">reading the ships…</option> : null}
              {thorp.length ? (
                <optgroup label="Nothing up my sleeve">
                  {thorp.map((m) => (
                    <option key={m.ship_key} value={m.run!.run}>
                      {m.name} · {fmtParams(m.params)} params · {m.run!.step}
                    </option>
                  ))}
                </optgroup>
              ) : null}
              {foreign.length ? (
                <optgroup label="foreign ships">
                  {foreign.map((m) => (
                    <option key={m.ship_key} value={String(m.model)}>
                      {m.name} · {fmtParams(m.params)} · its own weights
                    </option>
                  ))}
                </optgroup>
              ) : null}
            </select>
            <span className="note">
              {selected ? (
                selected.kind === 'foreign'
                  ? <>the foreign ship <b>{selected.name}</b> ({fmtParams(selected.params)}): its own MLX weights; the answer is its continuation, no head audit.</>
                  : <>the leaderboard’s {fmtParams(selected.params)}; its run <span className="mono">{selected.run?.run}</span>, checkpoint {selected.run?.step}; {selected.cards_held ?? '–'} of 4 necessary cards held.</>
              ) : models.error ? `the ships could not be read: ${models.error}` : 'reading the ships…'}
            </span>
          </div>
        )}

        {!embedded && !models.loading && !available.length ? (
          <div className={emptyCls()}>{models.error ? `the chat targets could not be read: ${models.error}` : 'No Nothing up my sleeve ship with a finished checkpoint, and no foreign ship with its MLX weights cached.'}</div>
        ) : null}

        {embedded && !selected ? null : (
          <>
            <div aria-live="polite" style={{ display: 'grid', gap: 8, margin: '12px 0', minHeight: 80 }}>
              {msgs.length === 0 ? <p className="note">No messages yet. Ask something; a Nothing up my sleeve ship answers from its latest checkpoint and the audit opens under the answer, a foreign ship from its own weights.</p> : null}
              {msgs.map((m, i) => (
                <div key={i} style={{ margin: 0, padding: '8px 10px', borderRadius: 6, border: '1px solid var(--line)', background: m.role === 'you' ? 'transparent' : 'var(--panel, transparent)' }}>
                  <div>
                    <b>{m.role === 'you' ? 'you' : (m.model || 'ship')}:</b> {m.text}
                  </div>
                  {m.role === 'thorp' && m.step ? <div className="note">checkpoint {m.step}</div> : null}
                  {m.role === 'thorp' && m.audit ? <AuditPanel a={m.audit} open={i === msgs.length - 1} /> : null}
                </div>
              ))}
              {busy ? <p className="note">{selected?.kind === 'foreign' ? 'loading the weights, sampling…' : 'reading the checkpoint, sampling, and tracing every head…'}</p> : null}
            </div>
            {note ? <p className="note" style={{ color: 'var(--bad, inherit)' }}>{note}</p> : null}
            <form
              onSubmit={(e) => { e.preventDefault(); void send(); }}
              style={{ display: 'flex', gap: 8, alignItems: 'center' }}
            >
              <input
                className={fieldCls('')}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={selected ? `Ask ${selected.name} a question…` : 'Ask the ship a question…'}
                aria-label="Your question"
                style={{ flex: 1 }}
                disabled={!selected}
              />
              <button className={btnCls()} type="submit" disabled={busy || !input.trim() || !selected}>{busy ? 'thinking…' : 'send'}</button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
