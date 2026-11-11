// The chat page: one question at a time to one of Nothing up my sleeve's ships on the leaderboard.
// Experimental — the models are small and not instruction-tuned, so a run without a chat/QA arm
// continues prose rather than answers. The list comes from /api/chat/models, which reads the
// leaderboard, so every ship it can reach with a checkpoint is here (thorp.chat).
//
// Each answer carries an audit: the attention heads that lit while the answer was written, where
// each answer token looked back, the star tests read on this prompt, and the cards the ship holds
// (thorp.chat._audit). It is the same trace the Tests tab reads for an outside model, on our own GPT.

import { useEffect, useRef, useState } from 'react';
import { btnCls, cardCls, emptyCls, fieldCls, pillCls, selectCls } from '@/lib/ui';
import { fmt, fmtParams, postJSON } from '@/lib/format';
import RichText from '@/lib/richtext';
import ConversationSidebar from './ConversationSidebar';
import { autoTitle, getThread, markSaved, newId, saveThread, threadsFor, type StoredMessage, type Thread } from '@/lib/conversations';
import { chatHref } from './CommandPalette';
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
  facts?: ChatFacts | null;
  why: string | null;
}
interface ThinkingSupport { mode: 'toggle' | 'auto' | 'none'; default: boolean; why?: string }
interface ChatFacts {
  preset?: string | null; family?: string | null; layers?: number | null; width?: number | null; heads?: number | null;
  context?: number | null; positions?: string | null; backend?: string | null; precision?: string | null;
  vocab?: number | null; tokeniser?: string | null; byte_fallback?: boolean | null; train_on?: string | null;
  control_tokens?: string[]; control_in_embeddings?: boolean; turns?: string | null;
  recipe?: string | null; passes?: number | null; clean?: string | null; sop?: string | null; step?: string | null;
  repo?: string | null; quant?: string | null; chat_template?: boolean; tuning?: string | null;
  thinking?: ThinkingSupport | null;
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
  reasoning?: string; meta?: ChatMeta;
}
interface ChatMeta {
  settings?: { temperature?: number; max_tokens?: number; thinking?: string };
  prompt_tokens?: number; answer_tokens?: number; reasoning_tokens?: number;
  cached_tokens?: number; cache_pct?: number; dropped_turns?: number;
  seconds?: number; tok_s?: number; finish?: string; rendered?: string;
}
interface ChatReply { run?: string; model?: string; step: string; prompt: string; format: string; answer: string; reasoning?: string; thinking?: string; meta?: ChatMeta; audit?: Audit; error?: string }

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

const RING_R = 9;
const RING_C = 2 * Math.PI * RING_R;

/** How much of the model's context window this conversation has taken: a ring, the percent beside it,
 *  and the detail on hover or focus. The count is over every turn, which is what the conversation is;
 *  the chat sends one question at a time, so the model's own prompt is the latest question alone, and
 *  the card says so rather than letting a full ring be read as a full prompt. A ring with no window
 *  recorded stays grey and says "not recorded", never 0%. */
export function ContextMeter({ used, context, next, turns, last }: {
  used: number; context: number | null; next: number; turns: number; last?: ChatMeta | null;
}) {
  const [open, setOpen] = useState(false);
  const share = context && context > 0 ? Math.min(1, used / context) : null;
  const tone = share == null ? 'var(--line)' : share >= 0.9 ? 'var(--bad)' : share >= 0.7 ? 'var(--accent)' : 'var(--good)';
  // under 10% a whole-number percent would sit at 0 for a whole conversation, so it keeps one decimal
  const pct = share == null ? null : 100 * share;
  const shown = pct == null ? '–' : pct >= 10 ? `${Math.round(pct)}%` : `${pct.toFixed(1)}%`;
  const left = context != null ? Math.max(0, context - used) : null;
  const after = left != null ? Math.max(0, left - next) : null;
  const label = pct == null
    ? 'context used: the window is not recorded for this model'
    : `context used: ${shown}, ${used} of ${context} tokens`;
  return (
    <span
      className="note"
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'help' }}
      tabIndex={0}
      role="img"
      aria-label={label}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <svg width={22} height={22} viewBox="0 0 22 22" aria-hidden="true">
        <circle cx={11} cy={11} r={RING_R} fill="none" stroke="var(--line)" strokeWidth={3} />
        <circle
          cx={11} cy={11} r={RING_R} fill="none" stroke={tone} strokeWidth={3}
          strokeDasharray={`${(share ?? 0) * RING_C} ${RING_C}`}
          strokeLinecap="round"
          transform="rotate(-90 11 11)"
        />
      </svg>
      <b>{shown}</b>
      {open ? (
        <span
          role="tooltip"
          style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0, zIndex: 40, width: 300,
            padding: '10px 12px', borderRadius: 8, border: '1px solid var(--line)',
            background: 'var(--raise)', color: 'var(--text)', boxShadow: '0 8px 24px rgba(0,0,0,.18)',
            textAlign: 'left', lineHeight: 1.45, fontFamily: 'inherit',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <b>context</b>
            <span className="mono">{context == null ? 'not recorded' : `${context.toLocaleString()} tokens`}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span>this conversation</span>
            <span className="mono">{used.toLocaleString()} tok{pct == null ? '' : ` · ${shown}`}</span>
          </div>
          {left != null ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span>left</span>
              <span className="mono">{left.toLocaleString()} tok</span>
            </div>
          ) : null}
          {after != null ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span>left after a full answer</span>
              <span className="mono">{after.toLocaleString()} tok</span>
            </div>
          ) : null}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span>turns</span>
            <span className="mono">{turns}</span>
          </div>
          {last ? (
            <div style={{ marginTop: 6, borderTop: '1px solid var(--line)', paddingTop: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span>last turn</span>
                <span className="mono">{last.prompt_tokens ?? '–'} asked → {last.answer_tokens ?? '–'} answer</span>
              </div>
              {last.reasoning_tokens ? (
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span>of which reasoning</span>
                  <span className="mono">{last.reasoning_tokens} tok</span>
                </div>
              ) : null}
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span>it ended</span>
                <span className={last.finish === 'length' ? 'accent' : ''}>
                  {last.finish === 'length' ? 'at the length cap' : last.finish ? 'at the end of the answer' : 'not recorded'}
                </span>
              </div>
            </div>
          ) : null}
          <div style={{ marginTop: 6, color: 'var(--muted)' }}>
            counted with the model&apos;s own tokeniser, over every turn of this chat. The chat sends one question at a time,
            so the model&apos;s own prompt is the latest question; the total is what the whole conversation would take if it
            were carried.
          </div>
        </span>
      ) : null}
    </span>
  );
}

const valueOf = (m: Model): string => (m.kind === 'foreign' ? String(m.model || '') : m.run?.run || '');

/** A conversation is one a model: keyed by what the model is, not by the run it happens to be sailing. */
const convoKeyOf = (m: Model): string => (m.kind === 'foreign' ? `foreign:${m.model}` : `ship:${m.ship_key}`);

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
  const [thinkingMode, setThinkingMode] = useState<'on' | 'off'>('on');
  const [showReasoning, setShowReasoning] = useState(true);
  const [maxTokens, setMaxTokens] = useState(512);
  const [railOpen, setRailOpen] = useState(true);
  // notes (11 November): one session id per chat, reset when the model changes; a note carries the
  // model, the session, and the whole reasoning trace of the session so far
  const [sessionId, setSessionId] = useState<string>(() => (globalThis.crypto?.randomUUID?.() || String(Date.now())));
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [noteMsg, setNoteMsg] = useState('');
  const [noteAll, setNoteAll] = useState(false);
  const [noteTick, setNoteTick] = useState(0);
  // the default model (11 November): a saved choice for /chat, used when no ?ship/?model asks for one
  const [defaultTarget, setDefaultTarget] = useState<string | null>(null);
  const [defaultLoaded, setDefaultLoaded] = useState(false);
  const picked = useRef(false);
  useEffect(() => {
    try { setDefaultTarget(localStorage.getItem('thorp.chat.default')); } catch { setDefaultTarget(null); }
    setDefaultLoaded(true);
  }, []);

  useEffect(() => {
    setSessionId(globalThis.crypto?.randomUUID?.() || String(Date.now()));
    setNoteText('');
    setNoteMsg('');
  }, [shipKey, modelKey]);

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

  // the thread this target is in, kept in this browser: the newest thread for the model when the target
  // changes, a fresh one on the first message. Saved where the messages change, never in an effect on
  // `msgs` (an effect would write the previous model's messages under the new model's key).
  const convoKey = selected ? convoKeyOf(selected) : '';
  const [threadId, setThreadId] = useState('');
  // the thread's id as it is now, not as of the last render: a send saves twice (the question, then the
  // answer), and the second save must find the thread the first one started rather than start another
  // (11 November: every new chat left a one-message twin in the list)
  const threadRef = useRef('');
  useEffect(() => {
    threadRef.current = threadId;
  }, [threadId]);
  const msgsRef = useRef<Msg[]>([]);
  useEffect(() => {
    msgsRef.current = msgs;
  }, [msgs]);
  useEffect(() => {
    if (!convoKey) return;
    const latest = threadsFor(convoKey)[0];
    setThreadId(latest?.id || '');
    setMsgs(((latest?.messages as unknown as Msg[]) || []).slice());
  }, [convoKey]);

  /** Write the messages into this model's thread, starting one on the first message of a chat. */
  const persist = (next: Msg[]): void => {
    if (!convoKey || !selected || !next.length) return;
    const id = threadRef.current;
    const base: Thread = id && getThread(id) ? (getThread(id) as Thread) : {
      id: newId(),
      key: convoKey,
      name: selected.name,
      kind: selected.kind,
      model: selected.model ?? null,
      shipKey: selected.ship_key,
      href: chatHref(selected),
      title: '',
      saved: false,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };
    const messages = next as unknown as StoredMessage[];
    saveThread({ ...base, title: base.title || autoTitle(messages), messages });
    if (id !== base.id) {
      threadRef.current = base.id;
      setThreadId(base.id);
    }
  };

  // the context meter: every turn's own reading, summed; the window is the model's own
  const contextWindow = selected?.facts?.context ?? null;
  const turnMeta = msgs.filter((m) => m.role === 'thorp' && m.meta).map((m) => m.meta as ChatMeta);
  const ctxUsed = turnMeta.reduce((n, m) => n + (m.prompt_tokens ?? 0) + (m.answer_tokens ?? 0) + (m.reasoning_tokens ?? 0), 0);
  const ctxTurns = msgs.filter((m) => m.role === 'you').length;

  // a model with a thinking switch starts on its template's default; one without keeps the toggle inert
  useEffect(() => {
    const t = selected?.facts?.thinking;
    if (t && t.mode === 'toggle') setThinkingMode(t.default ? 'on' : 'off');
  }, [selected?.ship_key, selected?.facts?.thinking?.mode]);

  const noteKey = selected ? (selected.kind === 'foreign' ? selected.model : selected.ship_key) : null;
  const notesUrl = noteOpen
    ? `/api/chat/notes?limit=100${noteAll || !noteKey ? '' : `&model=${encodeURIComponent(String(noteKey))}`}&_=${noteTick}`
    : null;
  const notesApi = useApi<any>(notesUrl, 0);
  const thinking = msgs
    .filter((m) => m.role === 'thorp')
    .map((m, i) => (m.reasoning ? `--- thinking, turn ${i + 1} ---
${m.reasoning}` : ''))
    .filter(Boolean)
    .join('\n\n');

  const saveNote = async (): Promise<void> => {
    const q = noteText.trim();
    if (!q || !selected) return;
    try {
      const r = await fetch('/api/chat/notes', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          kind: selected.kind,
          model_key: noteKey,
          model_label: selected.name,
          run: selected.kind === 'foreign' ? selected.model : selected.run?.run,
          note: q,
          thinking,
          conversation: msgs.map((m) => ({ role: m.role, text: m.text, reasoning: m.reasoning || '', meta: m.meta || null })),
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setNoteText('');
      setNoteMsg(`note saved · ${new Date().toLocaleTimeString()}`);
      setNoteTick((t) => t + 1);
    } catch (e) {
      setNoteMsg(`could not save: ${(e as Error).message}`);
    }
  };

  // /chat?ship=<ship_key> and /chat?model=<key> preselect a target (the old ship-page links), then
  // the saved default, then the largest Thorp ship. It is chosen once: changing the select afterwards
  // must not be overridden by the default.
  useEffect(() => {
    if (embedded || !available.length || !defaultLoaded || picked.current) return;
    picked.current = true;
    const q = new URLSearchParams(location.search);
    const ship = q.get('ship'), wantModel = q.get('model');
    const want = wantModel
      ? available.find((m) => m.kind === 'foreign' && m.model === wantModel)
      : ship ? available.find((m) => m.ship_key === ship) : null;
    const largest = thorp.slice().sort((a, b) => (b.params || 0) - (a.params || 0))[0];
    const saved = defaultTarget ? available.find((m) => valueOf(m) === defaultTarget) : null;
    const next = want ? valueOf(want) : saved ? valueOf(saved) : valueOf(largest || available[0]);
    if (next !== target) setTarget(next);
  }, [models.data, available.length, embedded, defaultTarget, defaultLoaded]);

  const send = async (qArg?: string, historyArg?: Msg[]): Promise<void> => {
    const q = (qArg ?? input).trim();
    if (!q || busy || !selected) return;
    const mine: Msg = { role: 'you', text: q };
    const nextUser = [...msgsRef.current, mine];
    msgsRef.current = nextUser;
    setMsgs(nextUser);
    persist(nextUser);
    if (qArg === undefined) setInput('');
    setBusy(true);
    setNote('');
    try {
      // the thread so far goes to every ship: a foreign one renders it in its own template, a Thorp ship has
      // it written as the turns its voyage read (thorp.chat.prompt_for), the oldest dropped when it no longer fits
      const history = (historyArg ?? msgsRef.current.slice(0, -1)).map((h) => ({ role: h.role === 'you' ? 'user' : 'assistant', text: h.text }));
      const body = selected.kind === 'foreign'
        ? { model: selected.model, q, tokens: maxTokens, temperature: 0.7, thinking: thinkingMode, history }
        : { run: selected.run!.run, q, tokens: maxTokens, temperature: 0.7, thinking: thinkingMode, history };
      const d = await postJSON<ChatReply>('/api/chat', body);
      if (d.error) setNote(String(d.error));
      else {
        const said: Msg = { role: 'thorp', text: String(d.answer || ''), model: selected.name, step: d.step, audit: d.audit || null, reasoning: d.reasoning || '', meta: d.meta };
        const nextSaid = [...msgsRef.current, said];
        msgsRef.current = nextSaid;
        setMsgs(nextSaid);
        persist(nextSaid);
      }
    } catch (e) {
      setNote(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const root = embedded ? { className: 'chatembed' } : { ...sectionProps('chat'), className: 'section active chatpage' };
  const openConversation = (t: Thread): void => {
    if (embedded) {
      location.assign(t.href);
      return;
    }
    const m = all.find((x) => convoKeyOf(x) === t.key);
    if (m) setTarget(valueOf(m));
    setThreadId(t.id);
    setMsgs((t.messages as unknown as Msg[]).slice());
  };
  const newConversation = (): void => {
    setMsgs([]);
    setThreadId('');
    setNote('');
  };
  const saveConversation = (id: string, title: string): void => {
    markSaved(id, title);
  };
  return (
    <div {...root}>
      <div className="chatlayout">
      <ConversationSidebar
        activeId={threadId}
        onOpen={openConversation}
        onNew={newConversation}
        onSave={saveConversation}
        open={railOpen}
        onOpenChange={setRailOpen}
      />
      <div className="chatmain">
      {embedded ? null : (
        <h1>Chat <span className="q">with Nothing up my sleeve’s small ships from the leaderboard and the foreign ships in Masaq' Reach; experimental: the models are small and not instruction-tuned, so a run without a chat/QA arm continues prose rather than answers. A Nothing up my sleeve answer is audited: the heads that lit while it was written, what each token looked up, and the cards the ship holds (thorp.chat); a foreign answer is the outside model’s own continuation, with no audit</span></h1>
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
              onChange={(e) => { setTarget(e.target.value); setNote(''); }}
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
            <button
              type="button"
              className={btnCls(defaultTarget && selected && valueOf(selected) === defaultTarget ? 'default' : 'outline', '')}
              onClick={() => {
                if (!selected) return;
                const v = valueOf(selected);
                try {
                  if (defaultTarget === v) { localStorage.removeItem('thorp.chat.default'); setDefaultTarget(null); }
                  else { localStorage.setItem('thorp.chat.default', v); setDefaultTarget(v); }
                } catch { /* blocked */ }
              }}
              disabled={!selected}
              title={defaultTarget ? 'the default model opens /chat when no ?ship or ?model is given' : 'make this the model /chat opens with'}
            >{defaultTarget && selected && valueOf(selected) === defaultTarget ? 'default ✓' : 'make default'}</button>
            {defaultTarget && selected && valueOf(selected) !== defaultTarget ? <span className="note">default: <span className="mono">{defaultTarget}</span></span> : null}
            <span className="note">
              {selected ? (
                selected.kind === 'foreign'
                  ? <>the foreign ship <b>{selected.name}</b> ({fmtParams(selected.params)}): its own MLX weights; the answer is its continuation, no head audit.</>
                  : <>the leaderboard’s {fmtParams(selected.params)}; its run <span className="mono">{selected.run?.run}</span>, checkpoint {selected.run?.step}; {selected.cards_held ?? '–'} of 4 necessary cards held.</>
              ) : models.error ? `the ships could not be read: ${models.error}` : 'reading the ships…'}
            </span>
          </div>
        )}

        {selected && selected.facts ? (
          <details className="chatparams">
            <summary>Parameters <span className="note">the model behind this chat, and whether its control tokens are in the embeddings</span></summary>
            <dl>
              {selected.facts.repo ? <><dt>model</dt><dd className="mono">{selected.facts.repo}</dd></> : null}
              <dt>size</dt>
              <dd>{fmtParams(selected.params)}{selected.facts.preset ? ` · preset ${selected.facts.preset}` : ''}{selected.facts.quant && selected.facts.quant !== '–' ? ` · ${selected.facts.quant}` : ''}</dd>
              {selected.facts.layers ? <><dt>shape</dt><dd>{selected.facts.layers} layers · {selected.facts.width} wide · {selected.facts.heads} heads</dd></> : null}
              {selected.facts.context ? <><dt>context</dt><dd>{selected.facts.context} tokens{selected.facts.positions ? ` · ${selected.facts.positions}` : ''}</dd></> : null}
              {selected.facts.backend ? <><dt>backend</dt><dd>{selected.facts.backend} · {selected.facts.precision || '–'}</dd></> : null}
              {selected.facts.tokeniser ? <><dt>tokeniser</dt><dd>{selected.facts.tokeniser} · vocab {selected.facts.vocab ?? '–'}{selected.facts.byte_fallback ? ' · byte fallback' : ''}</dd></> : null}
              {selected.facts.train_on ? <><dt>trained on</dt><dd>{selected.facts.train_on}</dd></> : null}
              {selected.facts.recipe ? <><dt>corpus</dt><dd>{selected.facts.recipe}{selected.facts.passes ? ` · ${selected.facts.passes} passes` : ''}{selected.facts.clean ? ` · ${selected.facts.clean}` : ''}</dd></> : null}
              {selected.facts.chat_template !== undefined ? <><dt>chat template</dt><dd>{selected.facts.chat_template ? 'applied: the model is asked in its own turn format' : 'none: the raw question is continued'}</dd></> : null}
              {selected.facts.tuning ? (
                <>
                  <dt>tuning</dt>
                  <dd>{selected.facts.tuning === 'instruct'
                    ? 'instruction-tuned: it was trained to answer'
                    : selected.facts.tuning === 'base'
                      ? <span className="accent">base checkpoint: pretrained only, it continues text rather than answering</span>
                      : 'not recorded'}</dd>
                </>
              ) : null}
              <dt>thinking</dt>
              <dd>
                {selected.facts.thinking?.mode === 'toggle'
                  ? <>a switch: {selected.facts.thinking.default ? 'on' : 'off'} by default; turn it off for a direct answer</>
                  : selected.facts.thinking?.mode === 'auto'
                    ? <span className="accent">automatic: the template always reasons and has no off switch</span>
                    : <span className="s">none: this model has no reasoning mode</span>}
              </dd>
              {selected.facts.control_tokens !== undefined ? (
                <>
                  <dt>control tokens</dt>
                  <dd>
                    {selected.facts.control_tokens && selected.facts.control_tokens.length
                      ? <><span className="mono">{selected.facts.control_tokens.join(' ')}</span> · in the embeddings as single pieces</>
                      : <span className="s">none: the tokeniser declares no control symbols, so none are in the embeddings</span>}
                  </dd>
                </>
              ) : null}
              {selected.facts.turns !== undefined ? (
                <>
                  <dt>turn training</dt>
                  <dd>{selected.facts.turns ? <span className="mono">{selected.facts.turns}</span> : <span className="s">none: this run read prose, not question/answer turns</span>}</dd>
                </>
              ) : null}
              {selected.facts.sop ? <><dt>SOP</dt><dd>{selected.facts.sop}</dd></> : null}
              {selected.facts.step ? <><dt>checkpoint</dt><dd className="mono">{selected.facts.step}</dd></> : null}
              {selected.run?.run ? <><dt>run</dt><dd className="mono">{selected.run.run}</dd></> : null}
            </dl>
          </details>
        ) : null}

        {selected ? (
          <div className="handtools chatcontrols">
            {selected.facts?.thinking?.mode === 'toggle' ? (
              <label className="note">thinking{' '}
                <select className={selectCls('')} value={thinkingMode} onChange={(e) => setThinkingMode(e.target.value as 'on' | 'off')} disabled={busy} title="the model's own reasoning mode; off asks it to answer directly">
                  <option value="on">on</option>
                  <option value="off">off</option>
                </select>
              </label>
            ) : selected.facts?.thinking?.mode === 'auto' ? (
              <span className={pillCls('accent')} title={selected.facts?.thinking?.why}>thinking: automatic</span>
            ) : (
              <span className="note" title={selected.facts?.thinking?.why || ''}>thinking: not supported</span>
            )}
            <label className="note"><input type="checkbox" checked={showReasoning} onChange={(e) => setShowReasoning(e.target.checked)} /> show reasoning</label>
            <label className="note">max tokens{' '}
              <input type="number" min={16} max={1024} step={16} value={maxTokens} onChange={(e) => setMaxTokens(Math.max(16, Math.min(1024, Number(e.target.value) || 16)))} style={{ width: 64 }} disabled={busy} />
            </label>
          </div>
        ) : null}

        {selected?.facts?.tuning === 'base' ? (
          <p className="note accent" style={{ margin: '2px 0 8px' }}>
            base checkpoint: its chat template formats the question, but the weights are pretrained only — expect it to continue text rather than answer. An instruction-tuned (<span className="mono">-it</span>) sibling is the one to chat with.
          </p>
        ) : null}

        {!embedded && !models.loading && !available.length ? (
          <div className={emptyCls()}>{models.error ? `the chat targets could not be read: ${models.error}` : 'No Nothing up my sleeve ship with a finished checkpoint, and no foreign ship with its MLX weights cached.'}</div>
        ) : null}

        {embedded && !selected ? null : (
          <>
            <div className="chatlog" aria-live="polite" style={{ display: 'grid', gap: 8, margin: '12px 0', minHeight: 80 }}>
              {msgs.length === 0 ? <p className="note">No messages yet. Ask something; a Nothing up my sleeve ship answers from its latest checkpoint and the audit opens under the answer, a foreign ship from its own weights.</p> : null}
              {msgs.map((m, i) => (
                <div key={i} style={{ margin: 0, padding: '8px 10px', borderRadius: 6, border: '1px solid var(--line)', background: m.role === 'you' ? 'transparent' : 'var(--panel, transparent)' }}>
                  {m.role === 'thorp' && m.reasoning && showReasoning ? (
                    <details className="chatthink" open={i === msgs.length - 1}>
                      <summary>reasoning{m.meta?.reasoning_tokens ? ` · ${m.meta.reasoning_tokens} tokens` : ''}</summary>
                      <div className="chatthinktext">{m.reasoning}</div>
                    </details>
                  ) : null}
                  <div>
                    <b>{m.role === 'you' ? 'you' : (m.model || 'ship')}:</b>{' '}
                    {m.role === 'you'
                      ? m.text
                      : m.text
                        ? <RichText text={m.text} />
                        : m.reasoning ? <span className="s">no final answer: it was still reasoning when the budget ran out</span> : ''}
                  </div>
                  {m.role === 'thorp' && m.meta ? (
                    <div className="note chatmeta">
                      {m.meta.prompt_tokens ?? '–'} prompt → {m.meta.answer_tokens ?? '–'} answer
                      {m.meta.reasoning_tokens ? ` + ${m.meta.reasoning_tokens} reasoning` : ''}
                      {m.meta.cache_pct != null ? ` · ${m.meta.cache_pct}% cached (${m.meta.cached_tokens ?? 0} prompt tokens from the KV cache)` : ''}
                      {m.meta.dropped_turns ? <> · <span className="accent">{m.meta.dropped_turns} oldest turns left out to fit the window</span></> : ''}
                      {m.meta.seconds != null ? ` · ${m.meta.seconds}s` : ''}
                      {m.meta.tok_s != null ? ` · ${m.meta.tok_s} tok/s` : ''}
                      {' · '}{m.meta.finish === 'length' ? <span className="accent">stopped at length</span> : 'stopped at the end'}
                      {' · thinking '}{m.meta.settings?.thinking || 'none'}
                    </div>
                  ) : null}
                  {m.role === 'thorp' && m.meta?.rendered ? (
                    <details className="chatprompt"><summary>the prompt it received</summary><pre>{m.meta.rendered}</pre></details>
                  ) : null}
                  {m.role === 'thorp' && m.meta?.finish === 'length' && selected?.kind === 'foreign' ? (
                    <div className="note" style={{ marginTop: 4 }}>
                      <button type="button" className={btnCls('outline', '')} onClick={() => void send('Continue the answer exactly where it stopped, without repeating anything.', msgsRef.current.slice(0, i + 1))} disabled={busy}>
                        continue in a new message
                      </button>
                    </div>
                  ) : null}
                  {m.role === 'thorp' && m.step ? <div className="note">checkpoint {m.step}</div> : null}
                  {m.role === 'thorp' && m.audit ? <AuditPanel a={m.audit} open={i === msgs.length - 1} /> : null}
                </div>
              ))}
              {busy ? <p className="note">{selected?.kind === 'foreign' ? 'loading the weights, sampling…' : 'reading the checkpoint, sampling, and tracing every head…'}</p> : null}
            </div>
            {note ? <p className="note" style={{ color: 'var(--bad, inherit)' }}>{note}</p> : null}
            {noteOpen ? (
              <div className="chatnote">
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="A note on this conversation: it is tagged with the model, this session, and the whole thinking so far"
                  rows={3}
                  disabled={!selected}
                />
                <div className="handtools">
                  <button type="button" className={btnCls('default', '')} onClick={() => void saveNote()} disabled={!noteText.trim() || !selected}>Save note</button>
                  <span className="note">session <span className="mono">{sessionId.slice(0, 8)}</span> · {selected?.name || 'no model'}{thinking ? ` · ${msgs.filter((m) => m.role === 'thorp' && m.reasoning).length} thinking turn${msgs.filter((m) => m.role === 'thorp' && m.reasoning).length === 1 ? '' : 's'}` : ' · no thinking yet'}</span>
                  <span className="note">{noteMsg}</span>
                </div>
                <details className="chatnotes" open>
                  <summary>Saved notes <span className="note">{notesApi.data ? `${notesApi.data.notes.length} for ${noteAll || !selected ? 'every model' : selected.name}` : 'reading…'}</span>
                    <label className="note" style={{ marginLeft: 8, textTransform: 'none', letterSpacing: 0 }}><input type="checkbox" checked={noteAll} onChange={(e) => setNoteAll(e.target.checked)} /> all models</label>
                  </summary>
                  <div className="chatnotelist">
                    {(notesApi.data?.notes || []).map((n: any) => (
                      <div key={n.id} className="chatnoterow">
                        <div className="note">{new Date(n.created_at).toLocaleString()} · <b>{n.model_label || n.model_key}</b> · session <span className="mono">{String(n.session_id || '').slice(0, 8)}</span></div>
                        <div>{n.note}</div>
                        {n.thinking ? <details><summary>thinking ({n.thinking.split('\n').filter(Boolean).length} lines)</summary><pre>{n.thinking}</pre></details> : null}
                      </div>
                    ))}
                    {notesApi.data && !(notesApi.data.notes || []).length ? <div className="note">no notes saved yet</div> : null}
                  </div>
                </details>
              </div>
            ) : null}
            <div className="chatfoot">
              <ContextMeter
                used={ctxUsed}
                context={contextWindow}
                next={maxTokens}
                turns={ctxTurns}
                last={turnMeta[turnMeta.length - 1]}
              />
              <form
                onSubmit={(e) => { e.preventDefault(); void send(); }}
                style={{ display: 'flex', gap: 8, alignItems: 'center', flex: 1 }}
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
              <button type="button" className={btnCls('outline', '')} onClick={() => setNoteOpen((o) => !o)} title="take a note on this conversation" aria-pressed={noteOpen}>{noteOpen ? 'close note' : 'note'}</button>
            </div>
          </>
        )}
      </section>
      </div>
      </div>
    </div>
  );
}
