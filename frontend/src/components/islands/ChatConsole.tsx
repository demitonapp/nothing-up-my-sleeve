// The chat console: a permanent drawer that slides up from the bottom of every page (11 November, Justin:
// "There needs to be a permanent chat model that slides up from the bottom of the screen. Very elegant,
// fal image of wooden carvings like a beautiful ship navigation panel built in the hey day or the merchant
// navy days. It slides up and then it's the chat console, where you can choose any instruct model you
// want, see the context window, and also save notes").
//
// The panel is carved oak and brass, drawn as SVG (`Woodwork`): grain, bevelled rails, brass screws and a
// nameplate. There is no image generator wired to this repository (no fal key — `data/secrets` holds only
// the Vast key), so the wood is drawn rather than generated. A generated plate drops in by CSS alone: save
// it as `public/art/chat-console.png`, then enable the two commented rules at the end of the console's
// block in `styles/global.css`, which paint the bar with the image and hide the drawn grain.
//
// It is a compact sibling of /chat: the same /api/chat, the same conversation store (a console chat is a
// thread, saved and listed on the chat page too), the same context meter, plus notes.

import { useEffect, useMemo, useRef, useState } from 'react';
import { ContextMeter } from './Chat';
import { autoTitle, getThread, listThreads, markSaved, newId, saveThread, type Thread } from '@/lib/conversations';

interface Model {
  kind: 'thorp' | 'foreign';
  model?: string | null;
  ship_key: string;
  name: string;
  params: number | null;
  available: boolean;
  run: { run: string; step: string } | null;
  facts?: {
    context?: number | null;
    tuning?: string | null;
    chat_template?: boolean;
    thinking?: { mode: 'toggle' | 'auto' | 'none'; default: boolean; why?: string } | null;
  } | null;
}
interface Meta { prompt_tokens?: number; answer_tokens?: number; reasoning_tokens?: number; cached_tokens?: number; cache_pct?: number; dropped_turns?: number; finish?: string; seconds?: number; tok_s?: number; settings?: any; think_capped?: boolean }
interface Say { role: 'you' | 'thorp'; text: string; model?: string; meta?: Meta; thinking?: string }
interface DbNote { id: number; note: string; model_label?: string; thinking?: string; session_id?: string; created_at?: string }
interface QRow { id: number; folder: string; question: string; model?: string | null; created_at?: string }
interface QFolder { name: string; count: number }
interface Reply { answer?: string; error?: string; step?: string; meta?: Meta }
// the answer while it is being written: what has arrived of the reasoning and of the answer, and how many tokens
interface Live { text: string; thinking: string; n: number }

// the labs, as thorp/labs.py LABS and the leaderboard's MAKER: a lab first, then its model
const LABS: [RegExp, string][] = [
  [/qwen/i, 'Alibaba'],
  [/llama/i, 'Meta'],
  [/phi/i, 'Microsoft'],
  [/pythia/i, 'EleutherAI'],
  [/gemma/i, 'Google'],
  [/smollm/i, 'Hugging Face'],
  [/gpt-oss/i, 'OpenAI'],
  [/maincoder/i, 'Maincode'],
];
const labOf = (m: Model): string => (LABS.find(([re]) => re.test(`${m.model || ''} ${m.name}`)) || [null, 'Other'])[1] as string;

const convoKeyOf = (m: Model): string => (m.kind === 'foreign' ? `foreign:${m.model}` : `ship:${m.ship_key}`);
const hrefOf = (m: Model): string => (m.kind === 'foreign' ? `/chat?model=${encodeURIComponent(String(m.model || ''))}` : `/chat?ship=${encodeURIComponent(m.ship_key)}`);

/** The carved panel: oak, brass and a rope border, as SVG so it scales and costs no request. */
function Woodwork() {
  return (
    <svg className="consolewood" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="oak" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4a2f1b" />
          <stop offset="0.18" stopColor="#6b4527" />
          <stop offset="0.55" stopColor="#5a3920" />
          <stop offset="1" stopColor="#3a2413" />
        </linearGradient>
        <linearGradient id="brass" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f6e2a8" />
          <stop offset="0.45" stopColor="#c9a24a" />
          <stop offset="1" stopColor="#8a6a25" />
        </linearGradient>
        <filter id="carve" x="-5%" y="-20%" width="110%" height="160%">
          <feDropShadow dx="0" dy="1" stdDeviation="0.6" floodColor="#1b0f06" floodOpacity="0.9" />
          <feDropShadow dx="0" dy="-1" stdDeviation="0.4" floodColor="#b98a52" floodOpacity="0.35" />
        </filter>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.006 0.42" numOctaves="4" seed="11" result="n" />
          <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.32  0 0 0 0 0.18  0 0 0 0 0.08  0 0 0 0.5 0" />
        </filter>
      </defs>
      <rect width="1200" height="120" fill="url(#oak)" />
      <rect width="1200" height="120" filter="url(#grain)" opacity="0.55" />
      {/* the bevelled rails: a lit top edge, a shadowed bottom */}
      <rect x="0" y="0" width="1200" height="5" fill="#8d6035" opacity="0.55" />
      <rect x="0" y="5" width="1200" height="2" fill="#2a1809" opacity="0.7" />
      <rect x="0" y="108" width="1200" height="12" fill="#2b190a" opacity="0.85" />
      <rect x="0" y="110" width="1200" height="2" fill="#a97a44" opacity="0.35" />
      {/* carved scrolls, one either side of the nameplate */}
      {[120, 1080].map((x, i) => (
        <g key={i} transform={`translate(${x} 62)`} filter="url(#carve)" opacity="0.85">
          <path d="M-58 0 q18 -18 36 0 q-18 18 -36 0 z M58 0 q-18 -18 -36 0 q18 18 36 0 z" fill="none" stroke="#c9a24a" strokeWidth="1.2" opacity="0.55" />
          <circle r="17" fill="none" stroke="#8f6a2e" strokeWidth="1" opacity="0.5" />
        </g>
      ))}
      {/* the brass screws along the rails */}
      {Array.from({ length: 24 }, (_, i) => 24 + i * 50).map((x) => (
        <g key={x} transform={`translate(${x} 14)`}>
          <circle r="3.2" fill="url(#brass)" />
          <circle r="3.2" fill="none" stroke="#4a3413" strokeWidth="0.6" />
          <path d="M-2.2 0 H2.2" stroke="#5b4318" strokeWidth="0.8" />
        </g>
      ))}
      {Array.from({ length: 24 }, (_, i) => 24 + i * 50).map((x) => (
        <g key={`b${x}`} transform={`translate(${x} 100)`}>
          <circle r="2.6" fill="url(#brass)" opacity="0.85" />
          <path d="M-1.8 0 H1.8" stroke="#5b4318" strokeWidth="0.7" />
        </g>
      ))}
    </svg>
  );
}

export default function ChatConsole() {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<Model[] | null>(null);
  const [err, setErr] = useState('');
  const [pick, setPick] = useState('');
  const [lab, setLab] = useState('');
  const [think, setThink] = useState(true);
  const [says, setSays] = useState<Say[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [threadId, setThreadId] = useState('');
  // the thread's id as it is now, not as of the last render: a send saves twice (the question, then the
  // answer), and the second save must find the thread the first one started rather than start another
  // (11 November: every new chat left a one-message twin in the list)
  const threadRef = useRef('');
  useEffect(() => {
    threadRef.current = threadId;
  }, [threadId]);
  const [notesOpen, setNotesOpen] = useState(false);
  const [note, setNote] = useState('');
  const [notes, setNotes] = useState<DbNote[]>([]);
  const [noteMsg, setNoteMsg] = useState('');
  const [saveMsg, setSaveMsg] = useState('');
  // the question library (11 November): questions kept against folders, loaded from s4.chat_questions
  const [questionsOpen, setQuestionsOpen] = useState(false);
  const [questionDraft, setQuestionDraft] = useState('');
  const [folder, setFolder] = useState('inbox');
  const [qRows, setQRows] = useState<QRow[]>([]);
  const [qFolders, setQFolders] = useState<QFolder[]>([]);
  const [qMsg, setQMsg] = useState('');
  // the budget is a share of the model's context window (11 November), so it means the same thing for a
  // 1k-window ship and a 262k-window Qwen; with no known window it falls back to a fixed 4096
  const [budgetShare, setBudgetShare] = useState(0.1);
  // the thinking has its own cap (11 November, Justin: "let's cap thinking separately"): the reasoning is
  // closed there and the answer written in the rest. 0 is no cap. The server holds it to half the budget.
  const [thinkCap, setThinkCap] = useState(1024);
  // the answer as it arrives (11 November, Justin: "stream the tokens"), and the handle that stops it
  const [live, setLive] = useState<Live | null>(null);
  const stopper = useRef<AbortController | null>(null);
  const chatBox = useRef<HTMLDivElement | null>(null);
  const thinkBox = useRef<HTMLPreElement | null>(null);
  // the default (11 November): the same key /chat uses, so a starred model opens both
  const [defaultKey, setDefaultKey] = useState('');
  useEffect(() => {
    try { setDefaultKey(localStorage.getItem('thorp.chat.default') || ''); } catch { setDefaultKey(''); }
  }, []);
  const [debug, setDebug] = useState(false);
  const [lastReq, setLastReq] = useState<any>(null);
  const [lastReply, setLastReply] = useState<any>(null);
  const session = useRef(newId());
  const field = useRef<HTMLInputElement | null>(null);
  const said = useRef<Say[]>([]);

  useEffect(() => {
    said.current = says;
  }, [says]);

  // Only instruction-tuned models, and only outside ones: a base checkpoint continues prose instead of
  // answering, and no Nothing up my sleeve ship is instruction-tuned yet, so a Thorp row would be a lie.
  // The choice is a sequence — the lab first, then the model within it (11 November, Justin: "in the model
  // selection it's a sequence. Choose the lab. and then choose the relevant model. Only show instruct
  // models, so no Thorp model exists yet").
  const instruct = useMemo(
    () => (models || []).filter((m) => m.kind === 'foreign' && m.available && m.model && m.facts?.tuning === 'instruct'),
    [models],
  );
  const labs = useMemo(() => {
    const seen: string[] = [];
    for (const m of instruct) {
      const l = labOf(m);
      if (!seen.includes(l)) seen.push(l);
    }
    return seen.sort((a, b) => a.localeCompare(b));
  }, [instruct]);
  const inLab = useMemo(() => instruct.filter((m) => labOf(m) === lab), [instruct, lab]);
  const chosen = useMemo(
    () => inLab.find((m) => convoKeyOf(m) === pick) || inLab[0] || null,
    [inLab, pick],
  );
  const contextWindow = chosen?.facts?.context ?? null;
  const tokens = contextWindow ? Math.max(1, Math.round(budgetShare * contextWindow)) : 4096;
  const thinkCapNow = thinkCap > 0 ? Math.max(1, Math.min(thinkCap, Math.floor(tokens / 2))) : 0;

  // a lab is chosen before a model: the starred default if one is saved, else the first lab. The
  // default is applied once, not on every selection, so choosing another model is not overridden.
  const appliedDefault = useRef('');
  useEffect(() => {
    if (!defaultKey || !instruct.length || appliedDefault.current === defaultKey) return;
    const saved = instruct.find((m) => m.model === defaultKey);
    if (!saved) return;
    appliedDefault.current = defaultKey;
    setLab(labOf(saved));
    setPick(convoKeyOf(saved));
  }, [instruct, defaultKey]);
  useEffect(() => {
    if (defaultKey && instruct.some((m) => m.model === defaultKey)) return;
    if (lab && labs.includes(lab)) return;
    setLab(labs[0] || '');
    setPick('');
  }, [labs, lab, instruct, defaultKey]);

  useEffect(() => {
    if (!open || models) return;
    let live = true;
    void (async () => {
      try {
        const r = await fetch('/api/chat/models');
        const d = await r.json();
        if (!live) return;
        setModels(((d.models || []) as Model[]).filter((m) => m.available && (m.run || m.model)));
      } catch (e) {
        if (live) setErr(String((e as Error)?.message ?? e));
      }
    })();
    return () => {
      live = false;
    };
  }, [open, models]);

  // the thread follows the model: its newest, else a fresh one on the first message
  useEffect(() => {
    if (!open || !chosen) return;
    const key = convoKeyOf(chosen);
    const latest = listThreads().find((t) => t.key === key);
    setThreadId(latest?.id || '');
    setSays(((latest?.messages as unknown as Say[]) || []).slice());
  }, [open, chosen?.kind, chosen?.model, chosen?.ship_key]);

  // the thinking switch follows the model: a template with an off switch starts on its own default, one
  // that always reasons is on and cannot be turned off, one with no reasoning mode is off and inert
  const thinking = chosen?.facts?.thinking;
  const thinkingToggle = thinking?.mode === 'toggle';
  const thinkingAuto = thinking?.mode === 'auto';
  useEffect(() => {
    setThink(thinking?.mode === 'none' ? false : (thinking?.default ?? false));
  }, [chosen?.ship_key, chosen?.model, thinking?.mode, thinking?.default]);

  const loadQuestions = async (): Promise<void> => {
    try {
      const r = await fetch('/api/chat/questions');
      const d = await r.json();
      setQRows(d.questions || []);
      setQFolders(d.folders || []);
    } catch (e) {
      setQMsg(`could not read questions: ${(e as Error).message}`);
    }
  };
  useEffect(() => {
    if (questionsOpen) void loadQuestions();
  }, [questionsOpen]);

  const lastAsked = useMemo(() => [...says].reverse().find((s) => s.role === 'you')?.text.trim() || '', [says]);

  const keepQuestion = async (): Promise<void> => {
    const q = questionDraft.trim();
    if (!q) return;
    try {
      const r = await fetch('/api/chat/questions', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ question: q, folder: folder.trim() || 'inbox', model: chosen?.name || null }),
      });
      if (!r.ok) throw new Error(await r.text());
      setQuestionDraft('');
      setQMsg('question kept');
      await loadQuestions();
    } catch (e) {
      setQMsg(`could not save: ${(e as Error).message}`);
    }
  };

  const notesFor = chosen ? (chosen.kind === 'foreign' ? chosen.model : chosen.run?.run) : null;
  const loadNotes = useMemo(() => async (): Promise<void> => {
    if (!notesFor) return;
    try {
      const r = await fetch(`/api/chat/notes?limit=50&model=${encodeURIComponent(String(notesFor))}`);
      const d = await r.json();
      setNotes(d.notes || []);
    } catch (e) {
      setNoteMsg(`could not read notes: ${(e as Error).message}`);
    }
  }, [notesFor]);
  useEffect(() => {
    if (notesOpen) void loadNotes();
  }, [notesOpen, loadNotes, notesFor]);

  useEffect(() => {
    if (open) window.setTimeout(() => field.current?.focus(), 260);
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key.toLowerCase() === 'j' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (!live) return;
    const el = chatBox.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
    const t = thinkBox.current;
    if (t) t.scrollTop = t.scrollHeight;
  }, [live]);

  const last = [...says].reverse().find((s) => s.meta)?.meta;
  const used = says.reduce((n, s) => n + (s.meta?.prompt_tokens ?? 0) + (s.meta?.answer_tokens ?? 0) + (s.meta?.reasoning_tokens ?? 0), 0);

  const persist = (next: Say[]): void => {
    if (!chosen || !next.length) return;
    const id = threadRef.current;
    const base: Thread = id && getThread(id) ? (getThread(id) as Thread) : {
      id: newId(), key: convoKeyOf(chosen), name: chosen.name, kind: chosen.kind,
      model: chosen.model ?? null, shipKey: chosen.ship_key, href: hrefOf(chosen),
      title: '', saved: false, createdAt: Date.now(), updatedAt: Date.now(), messages: [],
    };
    saveThread({ ...base, title: base.title || autoTitle(next as never), messages: next as never });
    if (id !== base.id) {
      threadRef.current = base.id;
      setThreadId(base.id);
    }
  };

  const send = async (): Promise<void> => {
    const q = input.trim();
    if (!q || busy || !chosen) return;
    setInput('');
    setBusy(true);
    setErr('');
    const mine: Say = { role: 'you', text: q };
    const nextUser = [...said.current, mine];
    said.current = nextUser;
    setSays(nextUser);
    persist(nextUser);
    try {
      // the thread so far, so a follow-up ("Ok so can you…") sees what it follows. The whole thread: the
      // server drops the oldest turns only when it no longer fits the window, so the prompt keeps the same
      // opening turn to turn and the model's KV cache can reuse it (a sliding window would miss every time).
      // The question just asked is `q`, not history.
      const history = said.current
        .slice(0, -1)
        .filter((s) => s.text)
        .map((s) => ({ role: s.role === 'you' ? 'user' : 'assistant', text: s.text }));
      const body = chosen.kind === 'foreign'
        ? { model: chosen.model, q, tokens, temperature: 0.7, thinking: think ? 'on' : 'off', think_tokens: thinkCap, history }
        : { run: chosen.run?.run, q, tokens, temperature: 0.7, thinking: think ? 'on' : 'off' };
      setLastReq(body);
      // the answer comes a line an event (/api/chat/stream): shown as it is written, and stoppable
      const ctl = new AbortController();
      stopper.current = ctl;
      const acc: Live = { text: '', thinking: '', n: 0 };
      let painting = 0;
      const paint = (): void => {
        if (painting) return;
        painting = window.requestAnimationFrame(() => { painting = 0; setLive({ ...acc }); });
      };
      setLive({ ...acc });
      let d: Reply | null = null;
      try {
        const r = await fetch('/api/chat/stream', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
        if (r.status === 404) throw new Error('this dashboard has no /api/chat/stream yet: restart thorp dash');
        if (!r.ok || !r.body) throw new Error(`the dashboard answered ${r.status}`);
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          for (let nl = buf.indexOf('\n'); nl >= 0; nl = buf.indexOf('\n')) {
            const line = buf.slice(0, nl).trim();
            buf = buf.slice(nl + 1);
            if (!line) continue;
            const ev = JSON.parse(line);
            if (ev.event === 'delta') {
              if (ev.kind === 'reasoning') acc.thinking += ev.text;
              else acc.text += ev.text;
              acc.n = ev.n ?? acc.n + 1;
              paint();
            } else if (ev.event === 'done') d = ev.reply as Reply;
            else if (ev.event === 'error') d = { error: String(ev.error) };
          }
        }
        if (!d) throw new Error('the answer ended before it was finished');
      } catch (e) {
        if (!ctl.signal.aborted) throw e;
        // stopped by the reader: what had arrived is kept, and said to be unfinished
        d = { answer: acc.text.trim(), meta: { finish: 'stopped', settings: { max_tokens: tokens } } };
        (d as any).reasoning = acc.thinking.trim();
        if (!acc.text.trim() && !acc.thinking.trim()) d = null;
      } finally {
        if (painting) window.cancelAnimationFrame(painting);
        stopper.current = null;
        setLive(null);
      }
      if (!d) return;
      if (d.error) setErr(String(d.error));
      else {
        setLastReply(d);
        const answer: Say = { role: 'thorp', text: String(d.answer || ''), model: chosen.name, meta: d.meta, thinking: (d as any).reasoning || '' };
        const next = [...said.current, answer];
        said.current = next;
        setSays(next);
        persist(next);
      }
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  // a fresh conversation: the thread is detached (the old one stays in the store), the session id
  // rotates so notes are filed against the new chat, and the transcript clears
  const startNewChat = (): void => {
    said.current = [];
    setSays([]);
    setThreadId('');
    session.current = newId();
    setInput('');
    setErr('');
    setNoteMsg('');
    setSaveMsg('');
    setLastReq(null);
    setLastReply(null);
  };

  const keepNote = async (): Promise<void> => {
    if (!chosen || !note.trim()) return;
    const thinking = says.filter((s) => s.role === 'thorp' && s.thinking).map((s) => s.thinking).join('\n\n');
    try {
      const r = await fetch('/api/chat/notes', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: threadId || session.current,
          kind: chosen.kind,
          model_key: chosen.kind === 'foreign' ? chosen.model : chosen.run?.run,
          model_label: chosen.name,
          run: chosen.kind === 'foreign' ? chosen.model : chosen.run?.run,
          note,
          thinking,
          conversation: says.map((s) => ({ role: s.role === 'you' ? 'user' : 'assistant', text: s.text })),
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setNote('');
      setNoteMsg('note saved to the database');
      await loadNotes();
    } catch (e) {
      setNoteMsg(`could not save: ${(e as Error).message}`);
    }
  };

  return (
    <div className={`console${open ? ' open' : ''}`} aria-label="chat console">
      <button
        type="button"
        className="consolebar"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="consolepanel"
        title={open ? 'close the console (⌘J)' : 'open the chat console (⌘J)'}
      >
        <Woodwork />
        <span className="consoleplate">
          <span className="consoletitle">The chat console</span>
          <span className="consolenote">{chosen ? chosen.name : 'reading the models…'}{open ? ' · ⌘J or esc to close' : ' · ⌘J'}</span>
        </span>
        <span className="consolemeter">
          <ContextMeter used={used} context={chosen?.facts?.context ?? null} next={256} turns={says.filter((s) => s.role === 'you').length} last={last} />
        </span>
        <span className="consolechevron" aria-hidden="true">{open ? '▾' : '▴'}</span>
      </button>

      <div className="consolepanel" id="consolepanel" role="region" aria-label="chat">
        <div className="consolehead">
          <label className="note consolepick">
            lab{' '}
            <select
              value={lab}
              onChange={(e) => { setLab(e.target.value); setPick(''); }}
              aria-label="lab"
              title="who made the model"
            >
              {labs.length === 0 ? <option value="">reading the labs…</option> : null}
              {labs.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </label>
          {/* the favourite is a model, not a lab (11 November, Justin: "favourite not the lab, but rather the
              model"): the star sits on the model it keeps, and the kept one is starred in the list */}
          <label className="note consolepick">
            model{' '}
            <select
              value={chosen ? convoKeyOf(chosen) : ''}
              onChange={(e) => setPick(e.target.value)}
              aria-label="model"
              title="the instruction-tuned checkpoints this lab makes"
              disabled={!inLab.length}
            >
              {inLab.map((m) => (
                <option key={convoKeyOf(m)} value={convoKeyOf(m)}>{m.model && m.model === defaultKey ? `★ ${m.name}` : m.name}</option>
              ))}
            </select>
            <button
              type="button"
              className={`consolstar${chosen?.model && defaultKey === chosen.model ? ' on' : ''}`}
              onClick={() => {
                if (!chosen?.model) return;
                const on = defaultKey === chosen.model;
                try {
                  if (on) localStorage.removeItem('thorp.chat.default');
                  else localStorage.setItem('thorp.chat.default', chosen.model);
                } catch { /* blocked */ }
                setDefaultKey(on ? '' : chosen.model);
              }}
              disabled={!chosen?.model}
              aria-pressed={!!chosen?.model && defaultKey === chosen.model}
              aria-label={chosen?.model && defaultKey === chosen.model ? `${chosen.name} is your favourite model` : `make ${chosen?.name || 'this model'} your favourite model`}
              title={chosen?.model && defaultKey === chosen.model ? `${chosen.name} is your favourite: the console and /chat open on it (click to clear)` : `favourite ${chosen?.name || 'this model'}: the console and /chat open on it`}
            >{chosen?.model && defaultKey === chosen.model ? '★' : '☆'}</button>
          </label>
          <label
            className={`consoleswitch${think && (thinkingToggle || thinkingAuto) ? ' on' : ''}${!thinkingToggle && !thinkingAuto ? ' inert' : ''}`}
            title={thinking?.why || (thinkingToggle ? 'the model\'s own reasoning mode: off asks it to answer directly' : 'this model has no reasoning mode')}
          >
            <input
              type="checkbox"
              checked={thinkingToggle ? think : thinkingAuto}
              disabled={!thinkingToggle && !thinkingAuto}
              onChange={(e) => setThink(e.target.checked)}
              aria-label="thinking"
            />
            <span className="consoleswitchtrack" aria-hidden="true"><span className="consoleswitchthumb" /></span>
            <span className="consoleswitchlabel">thinking {thinkingAuto ? 'auto' : think && (thinkingToggle || thinkingAuto) ? 'on' : 'off'}</span>
          </label>
          <label className="note consolepick" title="the whole completion's budget: the reasoning and the answer share it">
            budget{' '}
            <select value={budgetShare} onChange={(e) => setBudgetShare(Number(e.target.value))} aria-label="token budget" title={contextWindow ? `a share of the ${contextWindow.toLocaleString()}-token window: ${tokens.toLocaleString()} tokens` : 'this model\'s window is not known, so the budget is a fixed 4096 tokens'}>
              {[0.1, 0.25, 0.5, 0.75].map((p) => (
                <option key={p} value={p}>{Math.round(p * 100)}%{contextWindow ? ` · ${Math.max(1, Math.round(p * contextWindow)).toLocaleString()}` : ''}</option>
              ))}
            </select>
          </label>
          {thinkingAuto || (thinkingToggle && think) ? (
            <label className="note consolepick" title={thinkCapNow ? `the reasoning is closed at ${thinkCapNow.toLocaleString()} tokens and the answer written in the rest of the budget (never more than half the budget)` : 'no cap: the reasoning and the answer share the budget as they fall'}>
              thinking ≤{' '}
              <select value={thinkCap} onChange={(e) => setThinkCap(Number(e.target.value))} aria-label="thinking cap">
                {[256, 512, 1024, 2048, 4096, 8192].map((n) => (
                  <option key={n} value={n}>{Math.min(n, Math.floor(tokens / 2)).toLocaleString()}</option>
                ))}
                <option value={0}>no cap</option>
              </select>
            </label>
          ) : null}
          <button type="button" className="consolbtn" onClick={() => setNotesOpen((v) => !v)} aria-pressed={notesOpen}>
            Notes{notes.length ? ` (${notes.length})` : ''}
          </button>
          <button type="button" className="consolbtn" onClick={() => setQuestionsOpen((v) => !v)} aria-pressed={questionsOpen}>
            Questions{qRows.length ? ` (${qRows.length})` : ''}
          </button>
          <button type="button" className="consolbtn" onClick={() => setDebug((v) => !v)} aria-pressed={debug}>Debug</button>
          <button
            type="button"
            className="consolbtn"
            disabled={!threadId || !says.length}
            title="name this chat and keep it (Postgres, and this browser)"
            onClick={() => {
              if (!threadId) return;
              const t = markSaved(threadId, autoTitle(says as never));
              setSaveMsg(t ? 'chat saved' : 'could not save');
            }}
          >Save chat</button>
          {saveMsg ? <span className="note">{saveMsg}</span> : null}
          <button type="button" className="consolbtn" onClick={startNewChat} disabled={!says.length} title="clear this conversation and start a new one">New chat</button>
          {chosen ? <a className="consolbtn" href={hrefOf(chosen)} title="open this model's chat page">Full page ↗</a> : null}
        </div>

        <div className="consolebody">
          <div className="consolechat" aria-live="polite" ref={chatBox}>
            {says.length === 0 ? (
              <p className="note">{chosen ? `Ask ${chosen.name} something. The answer is its own continuation; the console keeps the thread, and notes beside it.` : 'reading the models…'}</p>
            ) : null}
            {says.map((s, i) => (
              <p key={i} className={s.role === 'you' ? 'consoleyou' : 'consoleanswer'}>
                <b>{s.role === 'you' ? 'you' : (s.model || 'model')}:</b> {s.text}
                {s.meta ? (
                  <span className="consolestatus">
                    <span className={s.meta.finish === 'length' ? 'warn' : s.meta.finish === 'stopped' ? 'dim' : 'ok'} title={s.meta.finish === 'length' ? 'stopped at the token budget, not at its own end' : s.meta.finish === 'stopped' ? 'stopped by you: what had arrived is kept' : 'ended on its own turn'}>{s.meta.finish === 'length' ? '⏹' : s.meta.finish === 'stopped' ? '◼ stopped' : '✓'}</span>
                    <span className={s.meta.reasoning_tokens ? 'think' : 'dim'} title={s.meta.reasoning_tokens ? `${s.meta.reasoning_tokens} tokens of thinking${s.meta.think_capped ? ': closed at its cap, not by the model' : ''}` : 'no thinking'}>◆{s.meta.reasoning_tokens ? ` ${s.meta.reasoning_tokens}` : ''}{s.meta.think_capped ? ' capped' : ''}</span>
                    <span title="prompt → answer tokens">{s.meta.prompt_tokens ?? '–'} → {s.meta.answer_tokens ?? '–'}</span>
                    {s.meta.cache_pct != null ? (
                      <span className={s.meta.cached_tokens ? 'ok' : 'dim'} title={`${s.meta.cached_tokens ?? 0} of the prompt's tokens read from the KV cache, not evaluated again`}>⚡ {s.meta.cache_pct}% cached</span>
                    ) : null}
                    {s.meta.dropped_turns ? (
                      <span className="warn" title={`the ${s.meta.dropped_turns} oldest turns were left out so the thread fits the window`}>−{s.meta.dropped_turns} turns</span>
                    ) : null}
                    {chosen?.facts?.context ? (
                      <span title={`${s.meta.prompt_tokens ?? 0} prompt + ${s.meta.answer_tokens ?? 0} answer + ${s.meta.reasoning_tokens ?? 0} thinking of a ${chosen.facts.context.toLocaleString()}-token window`}>{Math.round(100 * (((s.meta.prompt_tokens ?? 0) + (s.meta.answer_tokens ?? 0) + (s.meta.reasoning_tokens ?? 0)) / chosen.facts.context))}%</span>
                    ) : null}
                    {s.meta.seconds != null ? <span title="seconds">{s.meta.seconds}s</span> : null}
                    <span className="dim" title="the budget this answer had">{s.meta.settings?.max_tokens ?? tokens} max</span>
                  </span>
                ) : null}
                {s.role === 'thorp' && s.meta?.answer_tokens === 0 && s.meta?.finish === 'length' ? (
                  <span className="note consoleerr"> · the whole {s.meta.settings?.max_tokens ?? tokens}-token budget went to thinking, so no answer was written: raise the budget or turn thinking off</span>
                ) : null}
                {s.role === 'thorp' && s.thinking ? (
                  <details className="consoledebug"><summary>thinking ({s.meta?.reasoning_tokens ?? '–'} tokens)</summary><pre>{s.thinking}</pre></details>
                ) : null}
              </p>
            ))}
            {live ? (
              <p className="consoleanswer">
                <b>{chosen?.name || 'model'}:</b> {live.text}
                <span className="consolestatus">
                  <span className="think">{live.text ? 'writing' : live.thinking ? 'thinking' : 'reading the prompt'}…</span>
                  {live.n ? <span className="dim">{live.n.toLocaleString()} tokens</span> : null}
                </span>
                {live.thinking ? (
                  <details className="consoledebug" open={!live.text}><summary>thinking…</summary><pre ref={thinkBox}>{live.thinking}</pre></details>
                ) : null}
              </p>
            ) : busy ? <p className="note">sampling…</p> : null}
            {err ? <p className="note consoleerr">{err}</p> : null}
          </div>
          {debug ? (
            <div className="consoledebug">
              <div className="note">last request</div>
              <pre>{JSON.stringify(lastReq, null, 2)}</pre>
              <div className="note">last reply (answer trimmed)</div>
              <pre>{JSON.stringify(lastReply ? { ...lastReply, answer: lastReply.answer ? `${lastReply.answer.slice(0, 200)}…` : '', reasoning: undefined } : null, null, 2)}</pre>
              {lastReply?.meta?.rendered ? <><div className="note">the prompt it received</div><pre>{lastReply.meta.rendered}</pre></> : null}
            </div>
          ) : null}
          {questionsOpen ? (
            <div className="consolenotes consolequestions">
              <div className="consoleqnew">
                <textarea value={questionDraft} onChange={(e) => setQuestionDraft(e.target.value)} placeholder="a question to keep…" rows={2} aria-label="a question to keep" />
                <div className="consoleqrow">
                  <input value={folder} onChange={(e) => setFolder(e.target.value)} list="qfolders" placeholder="folder" aria-label="folder" />
                  <datalist id="qfolders">
                    {qFolders.map((f) => <option key={f.name} value={f.name} />)}
                  </datalist>
                  <button type="button" className="consolbtn" onClick={() => void keepQuestion()} disabled={!questionDraft.trim()}>Save question</button>
                  {qMsg ? <span className="note">{qMsg}</span> : null}
                </div>
              </div>
              <div className="consolenoteslist">
                {qRows.length === 0 ? <p className="note">No questions yet.</p> : null}
                {qFolders.map((f) => {
                  const rows = qRows.filter((r) => r.folder === f.name);
                  return (
                    <details key={f.name} open>
                      <summary>{f.name} <span className="note">{rows.length}</span></summary>
                      {rows.map((r) => (
                        <button key={r.id} type="button" className="consoleqitem" onClick={() => { setInput(r.question); setQuestionsOpen(false); }} title="put this question in the box">
                          {r.question}
                          {r.model ? <span className="note"> · {r.model}</span> : null}
                        </button>
                      ))}
                    </details>
                  );
                })}
              </div>
            </div>
          ) : null}
          {notesOpen ? (
            <div className="consolenotes">
              <div className="consolenotesnew">
                <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="a line worth keeping…" rows={3} aria-label="a note" />
                <button type="button" className="consolbtn" onClick={() => void keepNote()} disabled={!note.trim()}>Save note</button>
                {noteMsg ? <span className="note">{noteMsg}</span> : null}
              </div>
              <div className="consolenoteslist">
                {notes.length === 0 ? <p className="note">No notes yet.</p> : null}
                {notes.slice(0, 50).map((n) => (
                  <div key={n.id} className="consolenoterow">
                    <span>{n.note}</span>
                    <span className="note">{n.model_label}{n.created_at ? ` · ${new Date(n.created_at).toLocaleString()}` : ''}</span>
                    {n.thinking ? <details><summary>thinking</summary><pre>{n.thinking}</pre></details> : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <form className="consoleinput" onSubmit={(e) => { e.preventDefault(); void send(); }}>
          <input
            ref={field}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={chosen ? `ask ${chosen.name}…` : 'reading the models…'}
            aria-label="your question"
            disabled={!chosen}
          />
          {/* an empty box keeps the last question asked: sending clears the box, so otherwise the button is dead
              exactly when someone wants to keep what they just asked */}
          <button type="button" className="consolbtn" onClick={() => { setQuestionDraft(input.trim() || lastAsked); setQuestionsOpen(true); }} disabled={!input.trim() && !lastAsked} title={input.trim() || !lastAsked ? 'keep this question in the library' : 'keep your last question in the library'}>keep ?</button>
          {busy && live ? (
            <button type="button" className="consolbtn primary" onClick={() => stopper.current?.abort()} title="stop this answer: what has arrived is kept">stop</button>
          ) : (
            <button type="submit" className="consolbtn primary" disabled={busy || !input.trim() || !chosen}>{busy ? '…' : 'send'}</button>
          )}
        </form>
      </div>
    </div>
  );
}
