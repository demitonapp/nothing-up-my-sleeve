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
// It is the chat now (12 November, Justin: "the main chat page can be deprecated. We'll only use the
// terminal"): the same /api/chat, the same conversation store, the same context meter, plus notes. The
// /chat address is retired to a notice that hands its model to this console and opens it.

import { useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from 'react';
import { ContextMeter } from './Chat';
import ConsoleConnect from './ConsoleConnect';
import LanguageSetting from './LanguageSetting';
import RichText from '@/lib/richtext';
import {
  PUBLIC_EDITION, SERVER_CONNECTION, chatStream, connKey, loadConnection, recentConnections, saveConnection, stillThere,
  type Connection,
} from '@/lib/providers';
import {
  addFolder, autoTitle, dropFolder, fileThreads, getThread, listFolders, listThreads, markSaved, newId, removeThread,
  renameFolder, saveThread, subscribe, type Thread,
} from '@/lib/conversations';

// The console is three sections you open like an accordion (13 November, Justin: "sections you can click, so
// for the chat to expand, you click the middle section, and then if you want past chats etc left section and
// if you want settings right section … pop 2/3 or 1/3 or all 3"). Each third of the bar opens its own column
// of the drawer, alone or beside the others; the drawer is open while any one of them is.
interface Panes { past: boolean; chat: boolean; set: boolean }
const NONE: Panes = { past: false, chat: false, set: false };
const anyOpen = (p: Panes): boolean => p.past || p.chat || p.set;

const ago = (t: number): string => {
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};
const lastLine = (t: Thread): string => ([...t.messages].reverse().find((m) => m.text)?.text || '').replace(/\s+/g, ' ').slice(0, 90);

interface Model {
  kind: 'thorp' | 'foreign';
  // a model this browser talks to itself, on the visitor's machine or a cloud provider (lib/providers.ts,
  // 13 November); absent for the models Thorp's own server runs
  via?: Connection;
  // a Demiton ship that answers (the 9m's talk legs, thorp.chat.talking_models): its lab, and the checkpoints it kept
  // with their readings, so the one we talk to is chosen by its reading and not only by its last step
  talks?: boolean;
  lab?: string;
  checkpoints?: { step: number; bpb?: number | null; stopped?: number | null }[];
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
    tools?: { format: string | null; why?: string } | null;
  } | null;
}
interface Meta { prompt_tokens?: number; answer_tokens?: number; reasoning_tokens?: number; cached_tokens?: number; cache_pct?: number; dropped_turns?: number; finish?: string; seconds?: number; tok_s?: number; settings?: any; think_capped?: boolean; tool_calls?: ToolCall[] }
interface Say { role: 'you' | 'thorp'; text: string; model?: string; meta?: Meta; thinking?: string }
interface DbNote { id: number; note: string; model_label?: string; thinking?: string; session_id?: string; created_at?: string }
interface QRow { id: number; folder: string; question: string; model?: string | null; created_at?: string }
interface QFolder { name: string; count: number }
interface Reply { answer?: string; error?: string; step?: string; meta?: Meta }
// the answer while it is being written: what has arrived of the reasoning and of the answer, and how many tokens
interface Live { text: string; thinking: string; n: number; tools: ToolCall[] }
// one tool call the model made and what the tool gave back (thorp/chat_tools.py, 12 November)
interface ToolCall { round: number; name: string; arguments: Record<string, unknown>; result: Record<string, unknown> }

/** A tool call as a line in the thread: the call, then what it returned (or its error). */
/** One tool call, folded (12 November, Justin: "tool calls text need be able to be collapsible"): closed,
 *  the call and its result's one-line summary; open, every field of the result, one a line. */
function ToolLine({ c }: { c: ToolCall }) {
  const args = Object.entries(c.arguments || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
  const res = c.result || {};
  const bad = 'error' in res;
  const head = bad ? String(res.error) : typeof res.summary === 'string' ? res.summary : typeof res.answer === 'string' ? res.answer : '';
  const fields = Object.entries(res).filter(([k]) => !(k === 'summary' && !bad));
  return (
    <details className={`consoletool${bad ? ' bad' : ''}`}>
      <summary>
        <span className="consoletoolname">⚙ {c.name || 'unknown'}({args})</span>
        {head ? <span className="consoletoolhead">→ {head}</span> : null}
      </summary>
      <div className="consoletoolres">
        {fields.map(([k, v]) => (
          <div key={k} className="consoletoolfield">
            <b>{k}</b>
            {typeof v === 'string' ? <span>{v}</span> : <pre>{JSON.stringify(v, null, 2)}</pre>}
          </div>
        ))}
      </div>
    </details>
  );
}

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
  [/ling/i, 'InclusionAI'],
  [/falcon|tiiuae/i, 'TII'],
];
const labOf = (m: Model): string => m.lab || (LABS.find(([re]) => re.test(`${m.model || ''} ${m.name}`)) || [null, 'Other'])[1] as string;

const convoKeyOf = (m: Model): string => (m.via ? connKey(m.via) : m.kind === 'foreign' ? `foreign:${m.model}` : `ship:${m.ship_key}`);
const hrefOf = (m: Model): string => (m.via ? '' : m.kind === 'foreign' ? `/chat?model=${encodeURIComponent(String(m.model || ''))}` : `/chat?ship=${encodeURIComponent(m.ship_key)}`);

/** A browser connection as one of the console's models: no thinking switch (what it streams of its reasoning
 *  is shown), no tools (they run on Thorp's server), and the window where the provider gave one. */
const modelOfConnection = (c: Connection): Model => ({
  kind: 'foreign', via: c, model: c.model, ship_key: `conn:${c.provider}:${c.base}`, name: c.modelLabel || c.model, lab: c.label,
  params: null, available: true, run: null,
  facts: {
    context: c.context ?? null, tuning: 'instruct',
    thinking: { mode: 'none', default: false, why: 'set by the model itself: what it streams of its reasoning is shown above its answer' },
    tools: { format: null, why: 'Thorp’s tools run on its own server, so they are for Thorp’s own models' },
  },
});

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

const num = (v: number | null | undefined): string => (v == null ? '–' : v.toLocaleString());

/** The machine's own numbers, kept out of the answer's line: dim, tabular, and quiet under the prose. */
function SayMeta({ meta, context, budget }: { meta: Meta; context: number | null; budget: number }) {
  const used = (meta.prompt_tokens ?? 0) + (meta.answer_tokens ?? 0) + (meta.reasoning_tokens ?? 0);
  const share = context ? Math.round((100 * used) / context) : null;
  return (
    <div className="consolemeta">
      {meta.reasoning_tokens ? (
        <span className="think">{meta.reasoning_tokens.toLocaleString()} thought{meta.think_capped ? ', capped' : ''}</span>
      ) : null}
      <span>{num(meta.prompt_tokens)} → {num(meta.answer_tokens)} tokens</span>
      {share != null ? <span>{share < 1 && used > 0 ? '<1' : share}% of {Math.round(context! / 1000)}k window</span> : null}
      {meta.cache_pct != null ? <span className={meta.cached_tokens ? 'ok' : 'dim'}>{meta.cache_pct}% cached</span> : null}
      {meta.dropped_turns ? <span className="warn">{meta.dropped_turns} turns left out</span> : null}
      {meta.seconds != null ? <span>{meta.seconds}s</span> : null}
      {meta.tok_s != null ? <span>{meta.tok_s} tok/s</span> : null}
      <span className="dim">{num(meta.settings?.max_tokens ?? budget)} budget</span>
    </div>
  );
}

export default function ChatConsole() {
  const [panes, setPanes] = useState<Panes>(NONE);
  const open = anyOpen(panes);
  // the sections last opened together, so ⌘J brings back the same arrangement (kept in this browser)
  const lastPanes = useRef<Panes>({ past: false, chat: true, set: false });
  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem('thorp.chat.consolepanes') || 'null');
      if (p && anyOpen(p)) lastPanes.current = { past: !!p.past, chat: !!p.chat, set: !!p.set };
    } catch { /* storage blocked */ }
  }, []);
  useEffect(() => {
    if (!open) return;
    lastPanes.current = panes;
    try { localStorage.setItem('thorp.chat.consolepanes', JSON.stringify(panes)); } catch { /* blocked */ }
  }, [panes, open]);
  const togglePane = (k: keyof Panes): void => setPanes((p) => ({ ...p, [k]: !p[k] }));
  const closeAll = (): void => setPanes(NONE);
  const rootRef = useRef<HTMLDivElement | null>(null);
  // past chats: every thread this browser keeps, newest first, kept current as threads are written
  const [threads, setThreads] = useState<Thread[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  useEffect(() => {
    const sync = (): void => { setThreads(listThreads()); setFolders(listFolders()); };
    sync();
    return subscribe(sync);
  }, []);
  // a past chat opened for another model: loaded once that model is chosen
  const wantThread = useRef('');
  const [pastMsg, setPastMsg] = useState('');
  // the catalogue (13 November, Justin: "past chats need to have a folder concept for cataloguing"): chats are
  // filed in folders by dragging a row onto a folder or with its folder button; folders fold shut, and a
  // search reads titles, models, folders and last lines
  const [pastQuery, setPastQuery] = useState('');
  const [folding, setFolding] = useState(''); // the chat whose folder is being chosen
  const [folderDraft, setFolderDraft] = useState('');
  const [newFolder, setNewFolder] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<{ from: string; to: string } | null>(null);
  const [dropOn, setDropOn] = useState<string | null>(null);
  const dragId = useRef('');
  const [shut, setShut] = useState<string[]>([]);
  useEffect(() => {
    try {
      const v = JSON.parse(localStorage.getItem('thorp.chat.foldershut') || '[]');
      if (Array.isArray(v)) setShut(v.filter((x) => typeof x === 'string'));
    } catch { /* blocked */ }
  }, []);
  const toggleShut = (name: string): void => setShut((v) => {
    const next = v.includes(name) ? v.filter((x) => x !== name) : [...v, name];
    try { localStorage.setItem('thorp.chat.foldershut', JSON.stringify(next)); } catch { /* blocked */ }
    return next;
  });
  const [models, setModels] = useState<Model[] | null>(null);
  const [modelsErr, setModelsErr] = useState('');
  const [err, setErr] = useState('');
  // where the model lives (13 November, lib/providers.ts): this computer, a cloud key, or Thorp's own server.
  // undefined until this browser is read; null when it has none, and the chat column is the connect page
  const [conn, setConn] = useState<Connection | null | undefined>(undefined);
  const [connecting, setConnecting] = useState(false);
  const [health, setHealth] = useState<{ ok: boolean; why?: string } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let c = loadConnection();
    if (c === undefined) {
      // decided once a browser: one that used the console before connections existed was talking to Thorp's own
      // models, and stays there; any other is new, and opens on the connect page. The chats themselves are no
      // sign (the server's threads are synced into every browser), so the console's own drawer settings are read.
      let legacy = false;
      try {
        legacy = !PUBLIC_EDITION && ['thorp.chat.default', 'thorp.chat.consolepanes', 'thorp.chat.consoleh'].some((k) => localStorage.getItem(k) != null);
      } catch { /* blocked */ }
      c = legacy ? SERVER_CONNECTION : null;
      saveConnection(c);
    }
    if (PUBLIC_EDITION && c?.wire === 'thorp') c = null;
    setConn(c ?? null);
  }, []);
  const connect = (c: Connection): void => {
    saveConnection(c);
    setConn(c);
    setConnecting(false);
    setFailed(false);
    setErr('');
    setPanes((p) => ({ ...p, chat: true }));
  };
  // a remembered local server is asked whether it is still up whenever the drawer opens, so the bar's dot
  // says so before a question is lost to it
  useEffect(() => {
    if (!conn || conn.wire === 'thorp') { setHealth(null); return; }
    let live = true;
    void stillThere(conn).then((h) => { if (live) setHealth(h); });
    return () => { live = false; };
  }, [conn, open]);
  const [pick, setPick] = useState('');
  const [lab, setLab] = useState('');
  const [step, setStep] = useState(''); // the checkpoint of a Demiton ship; '' is its latest
  const [think, setThink] = useState(true);
  // tool calling (12 November): on by default where the model's template takes tools the console reads
  const [useTools, setUseTools] = useState(true);
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
  // the question library (11 November): questions kept against groups, loaded from s4.chat_questions. It lives
  // in the past-chats section as its own default folder (13 November, Justin: "questions need to be moved from
  // main chat, to the folder section and it's a default folder that allows saving not chats but only questions")
  const [questionDraft, setQuestionDraft] = useState('');
  const [qGroup, setQGroup] = useState('inbox');
  const qDraftBox = useRef<HTMLTextAreaElement | null>(null);
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
  // Reading is the console's first job (12 November): the drawer's height and the answer's size belong to
  // the reader, not to the page, so both are kept in this browser and the panel is dragged by its top edge.
  const [panelH, setPanelH] = useState(0); // 0: the stylesheet's height
  const [resizing, setResizing] = useState(false);
  const [answerFs, setAnswerFs] = useState(15.5);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ y: number; h: number } | null>(null);
  useEffect(() => {
    try {
      const h = Number(localStorage.getItem('thorp.chat.consoleh'));
      if (h >= 260) setPanelH(h);
      const fs = Number(localStorage.getItem('thorp.chat.consolefs'));
      if (fs >= 13 && fs <= 20) setAnswerFs(fs);
    } catch { /* storage blocked */ }
  }, []);
  useEffect(() => {
    try { if (panelH >= 260) localStorage.setItem('thorp.chat.consoleh', String(Math.round(panelH))); } catch { /* blocked */ }
  }, [panelH]);
  useEffect(() => {
    try { localStorage.setItem('thorp.chat.consolefs', String(answerFs)); } catch { /* blocked */ }
  }, [answerFs]);
  const setPanel = (h: number): void => {
    const max = Math.max(280, window.innerHeight - 40);
    setPanelH(Math.max(280, Math.min(max, h)));
  };
  const onResizeDown = (e: ReactPointerEvent<HTMLDivElement>): void => {
    dragRef.current = { y: e.clientY, h: panelRef.current?.getBoundingClientRect().height ?? window.innerHeight * 0.72 };
    setResizing(true);
    e.currentTarget.setPointerCapture(e.pointerId);
    e.preventDefault();
  };
  const onResizeMove = (e: ReactPointerEvent<HTMLDivElement>): void => {
    const d = dragRef.current;
    if (d) setPanel(d.h + (d.y - e.clientY));
  };
  const onResizeUp = (e: ReactPointerEvent<HTMLDivElement>): void => {
    dragRef.current = null;
    setResizing(false);
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* already gone */ }
  };
  const resetPanel = (): void => {
    setPanelH(0);
    try { localStorage.removeItem('thorp.chat.consoleh'); } catch { /* blocked */ }
  };
  const session = useRef(newId());
  // a model picked from a lab page, handed to the console by a `thorp:chat` event (12 November)
  const [wanted, setWanted] = useState('');
  const field = useRef<HTMLInputElement | null>(null);
  const said = useRef<Say[]>([]);

  useEffect(() => {
    said.current = says;
  }, [says]);

  // The lab pages' "chat" action (12 November): a lab's ship is added to the terminal by name. The console
  // opens at once; the model is selected when its list arrives, so a slow /api/chat/models does not lose it.
  useEffect(() => {
    const onChat = (e: Event): void => {
      const d = (e as CustomEvent).detail || {};
      if (d.model) setWanted(String(d.model));
      if (d.refresh) setModels(null); // a model just downloaded: read the list again
      if (d.connect) setConnecting(true); // Settings' "connect your box" (13 November): open on the connect page
      setPanes((p) => (p.chat ? p : { ...p, chat: true }));
    };
    window.addEventListener('thorp:chat', onChat);
    return () => window.removeEventListener('thorp:chat', onChat);
  }, []);

  // Only models that answer: an outside instruction-tuned model, or a Demiton leg that was taught turns (the 9m's
  // talk legs, 12 November). A base checkpoint continues prose instead of answering, so a Nothing up my sleeve row of one would be a lie.
  // The choice is a sequence — the lab first, then the model within it (11 November, Justin: "in the model
  // selection it's a sequence. Choose the lab. and then choose the relevant model. Only show instruct
  // models, so no Nothing up my sleeve model exists yet").
  const instruct = useMemo(
    () => (models || []).filter((m) => m.available && (m.talks || (m.kind === 'foreign' && m.model && m.facts?.tuning === 'instruct'))),
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
  const serverChosen = useMemo(
    () => inLab.find((m) => convoKeyOf(m) === pick) || inLab[0] || null,
    [inLab, pick],
  );
  const browserModel = useMemo(() => (conn && conn.wire !== 'thorp' ? modelOfConnection(conn) : null), [conn]);
  const chosen = browserModel || (conn?.wire === 'thorp' ? serverChosen : null);
  const showConnect = connecting || conn === null;
  const contextWindow = chosen?.facts?.context ?? null;
  const tokens = contextWindow ? Math.max(1, Math.round(budgetShare * contextWindow)) : 4096;
  // a provider's own output limit is usually far under a tenth of a long window, so a browser model asks for 8k at most
  const browserTokens = Math.min(tokens, 8192);
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
    setLab(labs.includes('Demiton') ? 'Demiton' : labs[0] || ''); // our own lab first (12 November, Justin)
    setPick('');
  }, [labs, lab, instruct, defaultKey]);
  // a checkpoint belongs to the model it was chosen for
  useEffect(() => { setStep(''); }, [chosen?.ship_key]);

  useEffect(() => {
    if (!wanted || !instruct.length) return;
    const m = instruct.find((x) => x.model === wanted || convoKeyOf(x) === wanted);
    if (!m) return;
    setLab(labOf(m));
    setPick(convoKeyOf(m));
    setWanted('');
    if (conn?.wire !== 'thorp') connect(SERVER_CONNECTION); // a lab page's ship is one of Thorp's own
  }, [instruct, wanted]);

  useEffect(() => {
    if (!open || models || PUBLIC_EDITION) return;
    let live = true;
    void (async () => {
      try {
        const r = await fetch('/api/chat/models');
        const d = await r.json();
        if (!live) return;
        setModels(((d.models || []) as Model[]).filter((m) => m.available && (m.run || m.model)));
      } catch (e) {
        if (live) { setModels([]); setModelsErr(String((e as Error)?.message ?? e)); }
      }
    })();
    return () => {
      live = false;
    };
  }, [open, models]);

  // the thread follows the model: the past chat asked for, else its newest, else a fresh one on the first
  // message. Only a change of model moves it, so closing and reopening the drawer keeps the chat you were in.
  useEffect(() => {
    if (!chosen) return;
    const key = convoKeyOf(chosen);
    const asked = wantThread.current ? getThread(wantThread.current) : undefined;
    wantThread.current = '';
    const t = asked && asked.key === key ? asked : listThreads().find((x) => x.key === key);
    threadRef.current = t?.id || '';
    setThreadId(t?.id || '');
    setSays(((t?.messages as unknown as Say[]) || []).slice());
  }, [chosen?.kind, chosen?.model, chosen?.ship_key]);

  // a past chat, from the left section: its model is chosen if it is not already, and the chat opens on it
  const openThread = (t: Thread): void => {
    if (busy) { setPastMsg('wait for the answer being written'); return; }
    // a chat with a model this browser connected itself: that connection is made again
    const via = t.key.startsWith('conn:')
      ? (conn && conn.wire !== 'thorp' && connKey(conn) === t.key ? conn : recentConnections().find((c) => connKey(c) === t.key))
      : undefined;
    const m = via ? modelOfConnection(via) : instruct.find((x) => convoKeyOf(x) === t.key);
    if (!m) { setPastMsg(`${t.name} is not on the console's list now`); return; }
    setPastMsg('');
    setConnecting(false);
    if (via && !(chosen && convoKeyOf(chosen) === t.key)) {
      wantThread.current = t.id;
      connect(via);
    } else if (!via && conn?.wire !== 'thorp') {
      wantThread.current = t.id;
      setLab(labOf(m));
      setPick(t.key);
      connect(SERVER_CONNECTION);
    } else if (chosen && convoKeyOf(chosen) === t.key) {
      const msgs = ((t.messages as unknown as Say[]) || []).slice();
      said.current = msgs;
      threadRef.current = t.id;
      setThreadId(t.id);
      setSays(msgs);
    } else {
      wantThread.current = t.id;
      setLab(labOf(m));
      setPick(t.key);
    }
    setPanes((p) => ({ ...p, chat: true }));
  };

  // the connect page opens at its top; a long thread opens on its newest turn, where the reading left off
  useEffect(() => {
    if (!panes.chat || !showConnect) return;
    const frame = requestAnimationFrame(() => { if (chatBox.current) chatBox.current.scrollTop = 0; });
    return () => cancelAnimationFrame(frame);
  }, [panes.chat, showConnect]);
  useEffect(() => {
    if (!panes.chat || showConnect) return;
    const el = chatBox.current;
    if (!el) return;
    const frame = requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    return () => cancelAnimationFrame(frame);
  }, [panes.chat, threadId, showConnect]);

  // the thinking switch follows the model: a template with an off switch starts on its own default, one
  // that always reasons is on and cannot be turned off, one with no reasoning mode is off and inert
  const thinking = chosen?.facts?.thinking;
  const thinkingToggle = thinking?.mode === 'toggle';
  const thinkingAuto = thinking?.mode === 'auto';
  useEffect(() => {
    setThink(thinking?.mode === 'none' ? false : (thinking?.default ?? false));
  }, [chosen?.ship_key, chosen?.model, thinking?.mode, thinking?.default]);
  // a ship of ours taught the tool leg says so in its facts too (13 November): the switch is the same for both
  const toolsInfo = chosen?.facts?.tools ?? null;
  const toolsOk = !!toolsInfo?.format;

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
    if (panes.past && !PUBLIC_EDITION) void loadQuestions(); // the question library is Thorp's server's
  }, [panes.past]);

  const lastAsked = useMemo(() => [...says].reverse().find((s) => s.role === 'you')?.text.trim() || '', [says]);

  const keepQuestion = async (): Promise<void> => {
    const q = questionDraft.trim();
    if (!q) return;
    try {
      const r = await fetch('/api/chat/questions', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ question: q, folder: qGroup.trim() || 'inbox', model: chosen?.name || null }),
      });
      if (!r.ok) throw new Error(await r.text());
      setQuestionDraft('');
      setQMsg('question kept');
      await loadQuestions();
    } catch (e) {
      setQMsg(`could not save: ${(e as Error).message}`);
    }
  };

  const forgetQuestion = async (id: number): Promise<void> => {
    try {
      const r = await fetch('/api/chat/questions/delete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      if (r.status === 404) throw new Error('this dashboard cannot forget questions yet: restart thorp dash');
      if (!r.ok) throw new Error(await r.text());
      setQRows((v) => v.filter((x) => x.id !== id));
      setQMsg('');
      await loadQuestions();
    } catch (e) {
      setQMsg(`could not forget it: ${(e as Error).message}`);
    }
  };

  // the input's "keep": the Questions folder opens in the left section with the question ready to save
  const keepFromInput = (q: string): void => {
    setQuestionDraft(q);
    setQMsg('');
    setPanes((p) => ({ ...p, past: true }));
    if (shut.includes('~questions')) toggleShut('~questions');
    window.setTimeout(() => qDraftBox.current?.focus(), 320);
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
    if (panes.chat) window.setTimeout(() => field.current?.focus(), 260);
  }, [panes.chat]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key.toLowerCase() === 'j' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPanes((p) => (anyOpen(p) ? NONE : lastPanes.current));
      } else if (e.key === 'Escape' && open) {
        closeAll();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // A press outside the console minimises it (12 November, Justin: "clicking outside the chat terminal
  // should minimise it"). The press, not the click: a selection dragged out of a reply ends outside and
  // must not close it, and a page's own "chat" button still opens it, because its click comes after.
  // Nothing is lost: the conversation, a reply still arriving and the draft all stay as they were.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent): void => {
      if (e.button !== 0) return;
      const root = rootRef.current;
      if (root && e.target instanceof Node && !root.contains(e.target)) closeAll();
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
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
        ? { model: chosen.model, q, tokens, temperature: 0.7, thinking: think ? 'on' : 'off', think_tokens: thinkCap, history, tools: toolsOk && useTools ? 'on' : 'off' }
        : { run: chosen.run?.run, q, tokens, temperature: 0.7, history, ...(step ? { step } : {}),
            // a ship taught to think or to call (13 November): the same two switches the foreign ships take
            ...(thinkingToggle ? { thinking: think ? 'on' : 'off' } : {}), ...(toolsOk ? { tools: useTools ? 'on' : 'off' } : {}) };
      const via = chosen.via;
      const turns = [...history.map((h) => ({ role: h.role as 'user' | 'assistant', content: h.text })), { role: 'user' as const, content: q }];
      setLastReq(via ? { provider: via.label, base: via.base, model: via.model, max_tokens: browserTokens, temperature: 0.7, messages: turns.length } : body);
      // the answer comes a line an event (/api/chat/stream): shown as it is written, and stoppable
      const ctl = new AbortController();
      stopper.current = ctl;
      const acc: Live = { text: '', thinking: '', n: 0, tools: [] };
      let painting = 0;
      const paint = (): void => {
        if (painting) return;
        painting = window.requestAnimationFrame(() => { painting = 0; setLive({ ...acc }); });
      };
      setLive({ ...acc });
      let d: Reply | null = null;
      try {
        if (via) {
          // a model this browser connected: asked straight from here, never through Thorp's server
          const t0 = performance.now();
          const res = await chatStream(via, turns, { maxTokens: browserTokens, temperature: 0.7, signal: ctl.signal }, (dl) => {
            if (dl.kind === 'reasoning') acc.thinking += dl.text;
            else acc.text += dl.text;
            acc.n += 1;
            paint();
          });
          const secs = (performance.now() - t0) / 1000;
          d = {
            answer: res.answer.trim(),
            meta: {
              prompt_tokens: res.promptTokens, answer_tokens: res.answerTokens, reasoning_tokens: res.reasoningTokens, cached_tokens: res.cachedTokens,
              finish: res.finish, seconds: Math.round(secs * 10) / 10,
              tok_s: res.answerTokens && secs > 0 ? Math.round((10 * res.answerTokens) / secs) / 10 : undefined,
              settings: { max_tokens: browserTokens, provider: via.label, model: via.model },
            },
          };
          (d as any).reasoning = res.reasoning.trim();
        } else {
        const r = await fetch('/api/chat/stream',{ method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
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
            } else if (ev.event === 'tool') {
              acc.tools = [...acc.tools, ev as ToolCall];
              if (acc.text && !acc.text.endsWith(' ')) acc.text += ' ';
              paint();
            } else if (ev.event === 'done') d = ev.reply as Reply;
            else if (ev.event === 'error') d = { error: String(ev.error) };
          }
        }
        if (!d) throw new Error('the answer ended before it was finished');
        }
      } catch (e) {
        if (!ctl.signal.aborted) throw e;
        // stopped by the reader: what had arrived is kept, and said to be unfinished
        d = { answer: acc.text.trim(), meta: { finish: 'stopped', settings: { max_tokens: via ? browserTokens : tokens } } };
        (d as any).reasoning = acc.thinking.trim();
        if (!acc.text.trim() && !acc.thinking.trim()) d = null;
      } finally {
        if (painting) window.cancelAnimationFrame(painting);
        stopper.current = null;
        setLive(null);
      }
      if (!d) return;
      setFailed(!!d.error);
      if (!d.error) setHealth((h) => (h?.ok === false ? { ok: true } : h)); // it answered, so it is there
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
      setFailed(true);
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

  // the threads by folder: each folder by name, then the unfiled (where a new chat lands) last, so the
  // catalogue is not pushed off the column by a long inbox; each folder's chats newest first. A search shows
  // only the folders it finds something in.
  const pastQ = pastQuery.trim().toLowerCase();
  const shownThreads = pastQ
    ? threads.filter((t) => `${t.title} ${t.name} ${t.folder || ''} ${lastLine(t)}`.toLowerCase().includes(pastQ))
    : threads;
  const pastGroups = folders.map((f) => ({ name: f, rows: shownThreads.filter((t) => (t.folder || '').trim() === f) }))
    .concat([{ name: '', rows: shownThreads.filter((t) => !(t.folder || '').trim()) }])
    .filter((g) => (pastQ ? g.rows.length > 0 : g.name !== '' || g.rows.length > 0 || folders.length > 0));
  const fileInto = (id: string, folder: string): void => {
    fileThreads([id], folder);
    const name = folder.trim() || '~unfiled'; // the folder it went to opens, so the chat is seen to land
    if (shut.includes(name)) toggleShut(name);
  };
  const listed = new Set([...instruct.map(convoKeyOf), ...recentConnections().map(connKey), ...(conn && conn.wire !== 'thorp' ? [connKey(conn)] : [])]);
  // the bar's dot: green when the model is there, amber while it answers, red when it is not answering
  const dot = busy ? 'wait' : !chosen ? 'off' : failed || health?.ok === false ? 'bad' : 'ok';
  const dotWhy = !chosen ? 'no model connected yet' : health?.ok === false ? health.why : failed ? 'the last question failed: see the chat' : busy ? 'answering' : 'connected';
  const barModel = conn === null
    ? 'no model yet: open to connect one'
    : chosen ? `${chosen.name}${chosen.via ? ` · ${chosen.via.where === 'local' ? `${chosen.via.label}, this computer` : chosen.via.label}` : ''}`
      : conn?.wire === 'thorp' && modelsErr ? 'Thorp’s models could not be read' : 'reading the models…';
  const openConnect = (): void => { setConnecting(true); setPanes((p) => ({ ...p, chat: true })); };
  const thinkOn = thinkingAuto || (thinkingToggle && think);
  const setSummary = chosen
    ? `thinking ${thinkingAuto ? 'auto' : thinkOn ? 'on' : 'off'} · tools ${toolsOk && useTools ? 'on' : 'off'} · ${Math.round(budgetShare * 100)}% budget`
    : 'the model, thinking, tools and budget';
  const hereTitle = threads.find((t) => t.id === threadId)?.title;

  return (
    <div
      ref={rootRef}
      className={`console${open ? ' open' : ''}${resizing ? ' resizing' : ''}`}
      aria-label="chat console"
      style={{ '--consoleh': panelH ? `${Math.round(panelH)}px` : undefined, '--consolefs': `${answerFs}px` } as CSSProperties}
    >
      {/* the bar is three plates: past chats, the chat, settings. Each opens its own column of the drawer. */}
      <div className="consolebar" role="group" aria-label="the chat console's sections">
        <Woodwork />
        <button
          type="button"
          className="consoleseg past"
          onClick={() => togglePane('past')}
          aria-pressed={panes.past}
          aria-controls="consolepast"
          title={panes.past ? 'close past chats' : 'open past chats'}
        >
          <span className="consolesegicon" aria-hidden="true">☰</span>
          <span className="consoleplate">
            <span className="consoletitle">Past chats</span>
            <span className="consolenote">{threads.length ? `${threads.length} kept${hereTitle ? ` · here: ${hereTitle}` : ''}` : 'none yet'}</span>
          </span>
        </button>
        <button
          type="button"
          className="consoleseg mid"
          onClick={() => togglePane('chat')}
          aria-pressed={panes.chat}
          aria-controls="consolechatcol"
          title={panes.chat ? 'close the chat (⌘J closes every section)' : 'open the chat (⌘J)'}
        >
          <span className="consoleplate">
            <span className="consoletitle">The chat console</span>
            <span className="consolenote"><i className={`cdot ${dot}`} title={dotWhy} aria-label={dotWhy} />{barModel}{open ? ' · ⌘J, esc or a click outside to close' : ' · ⌘J'}</span>
          </span>
          <span className="consolemeter">
            <ContextMeter used={used} context={chosen?.facts?.context ?? null} next={256} turns={says.filter((s) => s.role === 'you').length} last={last} />
          </span>
          <span className="consolechevron" aria-hidden="true">{panes.chat ? '▾' : '▴'}</span>
        </button>
        <button
          type="button"
          className="consoleswitchmodel"
          onClick={() => (showConnect && panes.chat && conn ? setConnecting(false) : openConnect())}
          title={conn ? 'switch model: one on this computer, a cloud model, or another' : 'connect a model: one on this computer, or a cloud model with your key'}
        >
          <span aria-hidden="true">⇄</span><span className="consoleswitchword">{conn ? 'switch model' : 'connect'}</span>
        </button>
        <button
          type="button"
          className="consoleseg set"
          onClick={() => togglePane('set')}
          aria-pressed={panes.set}
          aria-controls="consoleset"
          title={panes.set ? 'close settings' : 'open settings: the model, thinking, tools, budget and text size'}
        >
          <span className="consoleplate">
            <span className="consoletitle">Settings</span>
            <span className="consolenote">{setSummary}</span>
          </span>
          <span className="consolesegicon" aria-hidden="true">⚙</span>
        </button>
      </div>

      <div className="consolepanel" id="consolepanel" role="region" aria-label="chat console" ref={panelRef}>
        {/* the top edge is the drawer's handle: drag it, or focus it and use ↑ ↓ */}
        <div
          className="consoleresize"
          role="separator"
          aria-orientation="horizontal"
          aria-label="resize the console"
          tabIndex={0}
          title="drag to resize this console · double-click to reset"
          onPointerDown={onResizeDown}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeUp}
          onPointerCancel={onResizeUp}
          onDoubleClick={resetPanel}
          onKeyDown={(e) => {
            if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
            e.preventDefault();
            setPanel((panelRef.current?.getBoundingClientRect().height ?? 520) + (e.key === 'ArrowUp' ? 48 : -48));
          }}
        />
        <div className="consolecols">
          {/* ---- left: past chats, catalogued in folders */}
          <section id="consolepast" className={`consolecol consolepast${panes.past ? ' on' : ''}`} aria-label="past chats" inert={!panes.past}>
            <div className="consolecolhead">
              <b>Past chats</b>
              <span className="note">{threads.length}</span>
              <button type="button" className="consolbtn" onClick={() => setNewFolder((v) => (v === null ? '' : null))} aria-pressed={newFolder !== null} title="make a folder to file chats in">+ Folder</button>
              <button type="button" className="consolbtn" onClick={() => { startNewChat(); setPanes((p) => ({ ...p, chat: true })); }} disabled={busy} title="start a new conversation with this model">+ New chat</button>
            </div>
            <div className="consolepastsearch">
              <input
                type="search"
                value={pastQuery}
                onChange={(e) => setPastQuery(e.target.value)}
                placeholder="search titles, models, folders…"
                aria-label="search past chats"
              />
            </div>
            <datalist id="consolefolderlist">
              {folders.map((f) => <option key={f} value={f} />)}
            </datalist>
            <div className="consolepastlist">
              {newFolder !== null ? (
                <form
                  className="consolefolderform"
                  onSubmit={(e) => { e.preventDefault(); addFolder(newFolder); setNewFolder(null); }}
                >
                  <input
                    autoFocus
                    value={newFolder}
                    onChange={(e) => setNewFolder(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setNewFolder(null); } }}
                    placeholder="the new folder's name"
                    aria-label="the new folder's name"
                  />
                  <button type="submit" className="consolbtn" disabled={!newFolder.trim()}>make</button>
                  <button type="button" className="consolepastdel" onClick={() => setNewFolder(null)} aria-label="cancel">×</button>
                </form>
              ) : null}
              {/* the Questions folder: the default folder, pinned first. It holds kept questions, never chats (a
                  chat dragged over it is not taken), grouped as the library groups them; a question clicked goes
                  into the chat's box. */}
              {(() => {
                const qs = pastQ
                  ? qRows.filter((r) => `${r.question} ${r.folder} ${r.model || ''}`.toLowerCase().includes(pastQ))
                  : qRows;
                if (pastQ && !qs.length) return null;
                const isShut = !pastQ && shut.includes('~questions');
                const groups = [...new Set(qs.map((r) => r.folder))].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
                return (
                  <div className="consolefolder questions">
                    <div className="consolefolderhead">
                      <button
                        type="button"
                        className="consolefoldername"
                        onClick={() => toggleShut('~questions')}
                        aria-expanded={!isShut}
                        title={isShut ? 'open your kept questions' : 'fold the questions shut'}
                      >
                        <span className="consolefoldercaret" aria-hidden="true">{isShut ? '▸' : '▾'}</span>
                        <span className="consolefoldertext">Questions</span>
                        <span className="consolefoldercount">{qRows.length}</span>
                      </button>
                      <span className="consolefoldertag" title="the default folder: it keeps questions, not chats">questions only</span>
                    </div>
                    {isShut ? null : (
                      <>
                        <form className="consoleqkeep" onSubmit={(e) => { e.preventDefault(); void keepQuestion(); }}>
                          <textarea
                            ref={qDraftBox}
                            value={questionDraft}
                            onChange={(e) => setQuestionDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void keepQuestion(); }
                              else if (e.key === 'Escape' && questionDraft) { e.stopPropagation(); setQuestionDraft(''); }
                            }}
                            placeholder="a question to keep… (enter saves, shift-enter a new line)"
                            rows={2}
                            aria-label="a question to keep"
                          />
                          <div className="consolefolderform">
                            <input value={qGroup} onChange={(e) => setQGroup(e.target.value)} list="consoleqgroups" placeholder="group" aria-label="the question's group" title="the group it is kept under" />
                            <button type="submit" className="consolbtn" disabled={!questionDraft.trim()}>save</button>
                          </div>
                          <datalist id="consoleqgroups">
                            {qFolders.map((f) => <option key={f.name} value={f.name} />)}
                          </datalist>
                          {qMsg ? <p className="consolefolderempty">{qMsg}</p> : null}
                        </form>
                        {qs.length === 0 ? <p className="consolefolderempty">No questions yet: type one above, or use “keep” beside the chat’s box.</p> : null}
                        {groups.map((name) => {
                          const rows = qs.filter((r) => r.folder === name);
                          return (
                            <div key={name} className="consoleqgroup">
                              <div className="consoleqgroupname">{name} <span>{rows.length}</span></div>
                              {rows.map((r) => (
                                <div key={r.id} className="consolepastrow consoleqline">
                                  <button
                                    type="button"
                                    className="consolepastopen"
                                    onClick={() => {
                                      setInput(r.question);
                                      setPanes((p) => ({ ...p, chat: true }));
                                      window.setTimeout(() => field.current?.focus(), 320);
                                    }}
                                    title="put this question in the chat's box"
                                  >
                                    <span className="consoleqtext">{r.question}</span>
                                    <span className="consolepastmeta">
                                      {r.model ? `asked of ${r.model}` : 'kept'}{r.created_at ? ` · ${ago(Date.parse(String(r.created_at).replace(' ', 'T')))}` : ''}
                                    </span>
                                  </button>
                                  <button
                                    type="button"
                                    className="consolepastdel"
                                    onClick={() => void forgetQuestion(r.id)}
                                    title="forget this question"
                                    aria-label="forget this question"
                                  >×</button>
                                </div>
                              ))}
                            </div>
                          );
                        })}
                      </>
                    )}
                  </div>
                );
              })()}
              {pastMsg ? <p className="consolewarn">{pastMsg}</p> : null}
              {threads.length === 0 ? <p className="note consolepastempty">No conversations yet. Ask a model something and it is kept here, in this browser and in Postgres.</p> : null}
              {pastQ && !pastGroups.length ? <p className="note consolepastempty">Nothing matches “{pastQuery.trim()}”.</p> : null}
              {pastGroups.map((g) => {
                const isShut = !pastQ && shut.includes(g.name || '~unfiled');
                return (
                  <div
                    key={g.name || '~unfiled'}
                    className={`consolefolder${dropOn === g.name ? ' drop' : ''}${g.name ? '' : ' unfiled'}`}
                    onDragOver={(e) => {
                      if (!dragId.current) return;
                      e.preventDefault();
                      e.dataTransfer.dropEffect = 'move';
                      if (dropOn !== g.name) setDropOn(g.name);
                    }}
                    onDragLeave={(e) => {
                      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropOn((d) => (d === g.name ? null : d));
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const id = dragId.current;
                      dragId.current = '';
                      setDropOn(null);
                      if (id) fileInto(id, g.name);
                    }}
                  >
                    {renaming && renaming.from === g.name && g.name ? (
                      <form
                        className="consolefolderform"
                        onSubmit={(e) => { e.preventDefault(); renameFolder(renaming.from, renaming.to); setRenaming(null); }}
                      >
                        <input
                          autoFocus
                          value={renaming.to}
                          onChange={(e) => setRenaming({ from: renaming.from, to: e.target.value })}
                          onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setRenaming(null); } }}
                          aria-label={`rename the folder ${g.name}`}
                        />
                        <button type="submit" className="consolbtn" disabled={!renaming.to.trim()}>rename</button>
                        <button type="button" className="consolepastdel" onClick={() => setRenaming(null)} aria-label="cancel">×</button>
                      </form>
                    ) : (
                      <div className="consolefolderhead">
                        <button
                          type="button"
                          className="consolefoldername"
                          onClick={() => toggleShut(g.name || '~unfiled')}
                          aria-expanded={!isShut}
                          title={isShut ? 'open this folder' : 'fold this folder shut'}
                        >
                          <span className="consolefoldercaret" aria-hidden="true">{isShut ? '▸' : '▾'}</span>
                          <span className="consolefoldertext">{g.name || 'Unfiled'}</span>
                          <span className="consolefoldercount">{g.rows.length}</span>
                        </button>
                        {g.name ? (
                          <>
                            <button type="button" className="consolefolderact" onClick={() => setRenaming({ from: g.name, to: g.name })} title="rename this folder" aria-label={`rename the folder ${g.name}`}>✎</button>
                            <button type="button" className="consolefolderact" onClick={() => dropFolder(g.name)} title="remove this folder: its chats are kept, unfiled" aria-label={`remove the folder ${g.name}`}>×</button>
                          </>
                        ) : null}
                      </div>
                    )}
                    {isShut ? null : g.rows.length === 0 ? (
                      <p className="consolefolderempty">{g.name ? 'empty: drag a chat here, or use a chat’s folder button' : 'every chat is filed'}</p>
                    ) : g.rows.map((t) => {
                      const turns = t.messages.filter((m) => m.role === 'you').length;
                      const here = listed.has(t.key);
                      return (
                        <div key={t.id}>
                          <div
                            className={`consolepastrow${t.id === threadId ? ' active' : ''}`}
                            draggable
                            onDragStart={(e) => {
                              dragId.current = t.id;
                              e.dataTransfer.effectAllowed = 'move';
                              e.dataTransfer.setData('text/plain', t.title || t.id);
                            }}
                            onDragEnd={() => { dragId.current = ''; setDropOn(null); }}
                          >
                            <button type="button" className="consolepastopen" onClick={() => openThread(t)} disabled={!here} title={here ? `open ${t.title || 'this chat'} · drag it onto a folder to file it` : `${t.name} is not on the console's list now`}>
                              <span className="consolepasttitle">
                                {t.saved ? <span className="consolepaststar" aria-label="saved">★</span> : null}
                                {t.title || lastLine(t) || 'an untitled chat'}
                              </span>
                              <span className="consolepastmeta">{t.name}{here ? '' : ' (not on the list now)'} · {turns} turn{turns === 1 ? '' : 's'} · {ago(t.updatedAt)}{t.id === threadId ? ' · here' : ''}</span>
                              {lastLine(t) ? <span className="consolepastlast">{lastLine(t)}</span> : null}
                            </button>
                            <button
                              type="button"
                              className={`consolepastfile${folding === t.id ? ' on' : ''}`}
                              onClick={() => { setFolding((v) => (v === t.id ? '' : t.id)); setFolderDraft(t.folder || ''); }}
                              aria-pressed={folding === t.id}
                              title={t.folder ? `filed in ${t.folder}: move it` : 'file this chat in a folder'}
                              aria-label={`file ${t.title || 'this chat'} in a folder`}
                            >
                              <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M1.5 3.5h4.2l1.4 1.6h7.4v7.9H1.5z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" /></svg>
                            </button>
                            <button
                              type="button"
                              className="consolepastdel"
                              onClick={() => { if (t.id === threadId) startNewChat(); removeThread(t.id); }}
                              disabled={busy && t.id === threadId}
                              title="forget this conversation"
                              aria-label={`forget ${t.title || 'this chat'}`}
                            >×</button>
                          </div>
                          {folding === t.id ? (
                            <form
                              className="consolefolderform inrow"
                              onSubmit={(e) => { e.preventDefault(); fileInto(t.id, folderDraft); setFolding(''); }}
                            >
                              <input
                                autoFocus
                                list="consolefolderlist"
                                value={folderDraft}
                                onChange={(e) => setFolderDraft(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setFolding(''); } }}
                                placeholder="a folder, new or old; empty unfiles"
                                aria-label="the folder to file this chat in"
                              />
                              <button type="submit" className="consolbtn">{folderDraft.trim() ? 'file' : 'unfile'}</button>
                            </form>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </section>

          {/* ---- middle: the chat */}
          <section id="consolechatcol" className={`consolecol consolemain${panes.chat ? ' on' : ''}`} aria-label="chat" inert={!panes.chat}>
            <div className="consolehead">
              <button
                type="button"
                className="consolemodel"
                onClick={() => (showConnect && conn ? setConnecting(false) : openConnect())}
                title={showConnect && conn ? 'back to the chat' : 'switch model'}
              ><i className={`cdot ${dot}`} title={dotWhy} /> {chosen ? `${chosen.name}${chosen.via ? ` · ${chosen.via.label}` : ''}` : conn === null ? 'connect a model' : 'reading the models…'}{step ? ` · step ${step}` : ''}</button>
              <span className="consoleheadgap" aria-hidden="true" />
              {PUBLIC_EDITION ? null : (
              <button type="button" className="consolbtn" onClick={() => setNotesOpen((v) => !v)} aria-pressed={notesOpen}>
                Notes{notes.length ? ` (${notes.length})` : ''}
              </button>
              )}
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
              <button type="button" className="consolbtn" onClick={startNewChat} disabled={!says.length || busy} title="clear this conversation and start a new one">New chat</button>
            </div>

            <div className="consolebody">
              <div className="consolechat" aria-live="polite" ref={chatBox}>
                <div className="consoletranscript">
                  {showConnect ? (
                    <ConsoleConnect
                      current={conn ?? null}
                      serverModels={PUBLIC_EDITION ? null : instruct.length || null}
                      onPick={connect}
                      onClose={conn ? () => setConnecting(false) : undefined}
                    />
                  ) : (<>
                  {says.length === 0 ? (
                    <div className="consoleintro">
                      <span className="consolemsgwho">{chosen ? chosen.name : 'the console'}</span>
                      <p className="note">{chosen?.via
                        ? `Connected to ${chosen.via.model} on ${chosen.via.label}${chosen.via.where === 'local' ? ', on this computer' : ''}. Ask it anything: this browser asks it directly, and the thread is kept here.`
                        : chosen ? 'Ask it anything. The answer is its own continuation; the thread is kept, and notes sit beside it.'
                          : conn?.wire === 'thorp' && modelsErr ? `Thorp’s own models could not be read (${modelsErr}).` : 'reading the models…'}</p>
                      {conn?.wire === 'thorp' && !chosen && (modelsErr || (models && !instruct.length)) ? (
                        <p className="note"><button type="button" className="consolbtn" onClick={openConnect}>connect another model</button></p>
                      ) : null}
                    </div>
                  ) : null}
                  {health?.ok === false ? (
                    <p className="consolewarn">{health.why} <button type="button" className="consolbtn" onClick={openConnect}>switch model</button></p>
                  ) : null}
                  {says.map((s, i) => (
                    <article key={i} className={`consolemsg ${s.role === 'you' ? 'is-you' : 'is-model'}`}>
                      <div className="consolemsghead">
                        <span className="consolemsgwho">{s.role === 'you' ? 'you' : (s.model || 'model')}</span>
                        {s.meta && (s.meta.finish === 'length' || s.meta.finish === 'stopped') ? (
                          <span
                            className={`consolemsgend ${s.meta.finish === 'length' ? 'warn' : 'dim'}`}
                            title={s.meta.finish === 'length' ? 'stopped at the token budget, not at its own end' : 'stopped by you: what had arrived is kept'}
                          >{s.meta.finish === 'length' ? 'budget reached' : 'stopped'}</span>
                        ) : null}
                      </div>
                      {s.meta?.tool_calls?.length ? <div className="consoletools">{s.meta.tool_calls.map((c, j) => <ToolLine key={j} c={c} />)}</div> : null}
                      <div className="consolemsgtext"><RichText text={s.text} /></div>
                      {s.role === 'thorp' && s.meta?.answer_tokens === 0 && s.meta?.finish === 'length' ? (
                        <p className="consolewarn">The whole {s.meta.settings?.max_tokens ?? tokens}-token budget went to thinking, so no answer was written: raise the budget or turn thinking off.</p>
                      ) : null}
                      {s.meta ? <SayMeta meta={s.meta} context={chosen?.facts?.context ?? null} budget={tokens} /> : null}
                      {s.role === 'thorp' && s.thinking ? (
                        <details className="consolethink">
                          <summary>thinking<span className="note">{s.meta?.reasoning_tokens ? ` · ${s.meta.reasoning_tokens.toLocaleString()} tokens` : ''}</span></summary>
                          <pre>{s.thinking}</pre>
                        </details>
                      ) : null}
                    </article>
                  ))}
                  {live ? (
                    <article className="consolemsg is-model is-live">
                      <div className="consolemsghead">
                        <span className="consolemsgwho">{chosen?.name || 'model'}</span>
                        <span className="consolemsgend">
                          {live.text ? 'writing' : live.thinking ? 'thinking' : 'reading the prompt'}…
                          {live.n ? ` · ${live.n.toLocaleString()} tokens` : ''}
                        </span>
                      </div>
                      {live.tools.length ? <div className="consoletools">{live.tools.map((c, j) => <ToolLine key={j} c={c} />)}</div> : null}
                      {live.text ? <div className="consolemsgtext"><RichText text={live.text} /></div> : null}
                      {live.thinking ? (
                        <details className="consolethink" open={!live.text}>
                          <summary>thinking…</summary>
                          <pre ref={thinkBox}>{live.thinking}</pre>
                        </details>
                      ) : null}
                    </article>
                  ) : busy ? <p className="note consolewait">sampling…</p> : null}
                  {err ? <p className="consoleerr">{err}{chosen?.via ? <> <button type="button" className="consolbtn" onClick={openConnect}>switch model</button></> : null}</p> : null}
                  </>)}
                </div>
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
                placeholder={chosen ? `ask ${chosen.name}…` : conn === null ? 'connect a model above to start' : 'reading the models…'}
                aria-label="your question"
                disabled={!chosen || showConnect}
              />
              {/* an empty box keeps the last question asked: sending clears the box, so otherwise the button is dead
                  exactly when someone wants to keep what they just asked */}
              <button type="button" className="consolbtn" onClick={() => keepFromInput(input.trim() || lastAsked)} disabled={!input.trim() && !lastAsked} title={input.trim() || !lastAsked ? 'keep this question in the Questions folder' : 'keep your last question in the Questions folder'}>keep</button>
              {busy && live ? (
                <button type="button" className="consolbtn primary" onClick={() => stopper.current?.abort()} title="stop this answer: what has arrived is kept">stop</button>
              ) : (
                <button type="submit" className="consolbtn primary" disabled={busy || !input.trim() || !chosen || showConnect}>{busy ? '…' : 'send'}</button>
              )}
            </form>
          </section>

          {/* ---- right: settings */}
          <section id="consoleset" className={`consolecol consoleset${panes.set ? ' on' : ''}`} aria-label="settings" inert={!panes.set}>
            <div className="consolecolhead"><b>Settings</b></div>
            <div className="consolesetlist">
              <div className="consolesetrow">
                <span className="consolesetname">model from</span>
                <span className="consolesetline consoleconnrow">
                  <i className={`cdot ${dot}`} title={dotWhy} />
                  <span>{!conn ? 'nothing connected yet' : conn.wire === 'thorp' ? 'Thorp’s own models, on this server' : `${conn.label}, ${conn.where === 'local' ? 'on this computer' : 'with your key'}`}</span>
                  <button type="button" className="consolbtn" onClick={openConnect}>{conn ? 'switch' : 'connect'}</button>
                  {chosen?.via ? <span className="consolesetwhy">{chosen.via.model} · asked from this browser{chosen.via.where === 'cloud' ? ', the key never leaves it' : ''}</span> : null}
                </span>
              </div>
              {conn?.wire === 'thorp' ? (<>
              <label className="consolesetrow">
                <span className="consolesetname">lab</span>
                <select
                  value={lab}
                  onChange={(e) => { setLab(e.target.value); setPick(''); }}
                  aria-label="lab"
                  title="who made the model"
                  disabled={busy}
                >
                  {labs.length === 0 ? <option value="">reading the labs…</option> : null}
                  {labs.map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </label>
              {/* the favourite is a model, not a lab (11 November, Justin: "favourite not the lab, but rather the
                  model"): the star sits on the model it keeps, and the kept one is starred in the list */}
              <div className="consolesetrow">
                <span className="consolesetname">model</span>
                <span className="consolesetline">
                  <select
                    value={chosen ? convoKeyOf(chosen) : ''}
                    onChange={(e) => setPick(e.target.value)}
                    aria-label="model"
                    title="the models this lab makes that answer: instruction-tuned, or a Demiton leg taught to talk"
                    disabled={!inLab.length || busy}
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
                    title={chosen?.model && defaultKey === chosen.model ? `${chosen.name} is your favourite: the console opens on it (click to clear)` : `favourite ${chosen?.name || 'this model'}: the console opens on it`}
                  >{chosen?.model && defaultKey === chosen.model ? '★' : '☆'}</button>
                </span>
                {contextWindow ? <span className="consolesetwhy">a {contextWindow.toLocaleString()}-token window</span> : null}
              </div>
              </>) : null}
              {chosen?.checkpoints?.length ? (
                <label className="consolesetrow">
                  <span className="consolesetname">checkpoint</span>
                  <select
                    value={step}
                    onChange={(e) => setStep(e.target.value)}
                    aria-label="checkpoint"
                    title="every checkpoint this leg kept, with its reading on held-out exchanges: bits per byte (lower is better) and how often it ends its own turn"
                  >
                    <option value="">latest (step {chosen.run?.step?.replace('step-', '')})</option>
                    {[...chosen.checkpoints].reverse().map((c) => (
                      <option key={c.step} value={String(c.step)}>
                        step {c.step}{c.bpb != null ? ` · ${c.bpb.toFixed(2)} bpb` : ''}{c.stopped != null ? ` · ends turn ${Math.round(c.stopped * 100)}%` : ''}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <div className="consolesetrow">
                <span className="consolesetname">thinking</span>
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
                  <span className="consoleswitchlabel">{thinkingAuto ? 'auto' : thinkOn ? 'on' : 'off'}</span>
                </label>
                {thinkOn ? (
                  <span className="consolesetline" title={thinkCapNow ? `the reasoning is closed at ${thinkCapNow.toLocaleString()} tokens and the answer written in the rest of the budget (never more than half the budget)` : 'no cap: the reasoning and the answer share the budget as they fall'}>
                    <span className="consolesetwhy">capped at</span>
                    <select value={thinkCap} onChange={(e) => setThinkCap(Number(e.target.value))} aria-label="thinking cap">
                      {[256, 512, 1024, 2048, 4096, 8192].map((n) => (
                        <option key={n} value={n}>{Math.min(n, Math.floor(tokens / 2)).toLocaleString()} tokens</option>
                      ))}
                      <option value={0}>no cap</option>
                    </select>
                  </span>
                ) : !thinkingToggle && !thinkingAuto ? <span className="consolesetwhy">{thinking?.why || 'this model has no reasoning mode'}</span> : null}
              </div>
              <div className="consolesetrow">
                <span className="consolesetname">tools</span>
                <label
                  className={`consoleswitch${toolsOk && useTools ? ' on' : ''}${!toolsOk ? ' inert' : ''}`}
                  title={toolsOk ? (chosen?.kind === 'foreign' ? `calculate, current_time, board_score, queue_status, liberty_machine_status, system_status, expedition_status, browser_task and browser_task_status: ${toolsInfo?.why || ''}` : (toolsInfo?.why || '')) : (toolsInfo?.why || 'tools are for the foreign ships whose chat template takes them, and our ships taught the tool leg')}
                >
                  <input
                    type="checkbox"
                    checked={toolsOk && useTools}
                    disabled={!toolsOk}
                    onChange={(e) => setUseTools(e.target.checked)}
                    aria-label="tools"
                  />
                  <span className="consoleswitchtrack" aria-hidden="true"><span className="consoleswitchthumb" /></span>
                  <span className="consoleswitchlabel">{toolsOk && useTools ? 'on' : 'off'}</span>
                </label>
                {!toolsOk ? <span className="consolesetwhy">{toolsInfo?.why || 'tools are for the foreign ships whose chat template takes them, and our ships taught the tool leg'}</span> : null}
              </div>
              <label className="consolesetrow" title="the whole completion's budget: the reasoning and the answer share it">
                <span className="consolesetname">budget</span>
                <select value={budgetShare} onChange={(e) => setBudgetShare(Number(e.target.value))} aria-label="token budget" title={contextWindow ? `a share of the ${contextWindow.toLocaleString()}-token window: ${tokens.toLocaleString()} tokens` : 'this model\'s window is not known, so the budget is a fixed 4096 tokens'}>
                  {[0.1, 0.25, 0.5, 0.75].map((p) => (
                    <option key={p} value={p}>{Math.round(p * 100)}% of the window{contextWindow ? ` · ${Math.max(1, Math.round(p * contextWindow)).toLocaleString()} tokens` : ''}</option>
                  ))}
                </select>
                {!contextWindow ? <span className="consolesetwhy">the window is not known, so the budget is a fixed 4,096 tokens</span> : null}
                {chosen?.via && browserTokens < tokens ? <span className="consolesetwhy">a model connected from this browser is asked for {browserTokens.toLocaleString()} tokens at most</span> : null}
              </label>
              <div className="consolesetrow">
                <span className="consolesetname">answer text</span>
                <span className="consolesetline" role="group" aria-label="answer text size">
                  <button type="button" className="consolbtn" onClick={() => setAnswerFs((v) => Math.max(13, v - 1))} title="smaller answer text" aria-label="smaller answer text">A−</button>
                  <span className="consolesetwhy">{answerFs}px</span>
                  <button type="button" className="consolbtn" onClick={() => setAnswerFs((v) => Math.min(20, v + 1))} title="larger answer text" aria-label="larger answer text">A+</button>
                </span>
              </div>
              {/* the site's language (13 November, Justin): the Liberty Machine keeps the choice; Tiny Aya Earth translates the site */}
              {!PUBLIC_EDITION ? <LanguageSetting /> : null}
              <div className="consolesetrow">
                <span className="consolesetname">debug</span>
                <label className={`consoleswitch${debug ? ' on' : ''}`} title="show the last request and reply beside the chat">
                  <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} aria-label="debug" />
                  <span className="consoleswitchtrack" aria-hidden="true"><span className="consoleswitchthumb" /></span>
                  <span className="consoleswitchlabel">{debug ? 'on' : 'off'}</span>
                </label>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
