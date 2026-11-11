// The chat's saved conversations (11 November, Justin: "ok so we also need an ability to save a chat
// then"): a chat is a thread, several a model, each kept in this browser.
//
// The first cut kept one conversation a model, so a second chat replaced the first — which is fine until
// a chat is worth keeping. A thread now has an id and a title: every chat is written as it happens (a
// draft, titled by its first question), and "Save" gives it a name and marks it, so the next chat with
// the same model starts a new thread instead of overwriting the saved one. Saved threads are never
// pruned; drafts are, oldest first, once there are more than KEEP_DRAFTS of them.
//
// `localStorage`, slot `thorp.chat.threads.v2`; a v1 store (one a model) is migrated once, its
// conversations arriving as saved threads.

export interface StoredMessage {
  role: 'you' | 'thorp';
  text: string;
  model?: string;
  step?: string;
  reasoning?: string;
  meta?: unknown;
  audit?: unknown;
}

export interface Thread {
  id: string;
  key: string; // the model: `foreign:gemma-3-270m`, `ship:300k:2980e0eca706`
  name: string; // the model, as the chat names it
  kind: 'thorp' | 'foreign';
  model?: string | null;
  shipKey?: string;
  href: string;
  title: string;
  saved: boolean;
  createdAt: number;
  updatedAt: number;
  messages: StoredMessage[];
}

const SLOT = 'thorp.chat.threads.v2';
const V1 = 'thorp.chat.conversations.v1';
const KEEP_DRAFTS = 20;
const MAX_THREADS = 60;
const MAX_MESSAGES = 40;
const EVENT = 'thorp:conversations';

export const newId = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

/** A title from the first question: the first line, cut at 60 characters. */
export const autoTitle = (messages: StoredMessage[]): string => {
  const first = messages.find((m) => m.role === 'you' && m.text.trim());
  const text = (first?.text || 'a chat').replace(/\s+/g, ' ').trim();
  return text.length > 60 ? `${text.slice(0, 59)}…` : text;
};

const clean = (t: Thread): Thread => ({ ...t, messages: t.messages.slice(-MAX_MESSAGES) });

const read = (): Thread[] => {
  try {
    const raw = JSON.parse(localStorage.getItem(SLOT) || 'null');
    if (Array.isArray(raw)) return raw.filter((t: Thread) => t && typeof t.id === 'string' && Array.isArray(t.messages)) as Thread[];
  } catch {
    /* unreadable: fall through to the migration */
  }
  return migrate();
};

/** The v1 store (one conversation a model) became saved threads, once. */
function migrate(): Thread[] {
  try {
    const old = JSON.parse(localStorage.getItem(V1) || 'null');
    if (!Array.isArray(old) || !old.length) return [];
    const now = Date.now();
    const threads: Thread[] = old.map((c: Record<string, unknown>, i: number) => {
      const messages = (c.messages as StoredMessage[]) || [];
      return {
        id: `v1-${String(c.key)}`,
        key: String(c.key),
        name: String(c.name || c.key),
        kind: (c.kind as 'thorp' | 'foreign') || 'foreign',
        model: (c.model as string | null) ?? null,
        shipKey: (c.shipKey as string) || '',
        href: String(c.href || '/chat'),
        title: autoTitle(messages),
        saved: true,
        createdAt: now - (old.length - i) * 1000,
        updatedAt: Number(c.updatedAt) || now - (old.length - i) * 1000,
        messages,
      };
    });
    write(threads);
    return threads;
  } catch {
    return [];
  }
}

function write(all: Thread[]): void {
  const saved = all.filter((t) => t.saved).slice(0, MAX_THREADS);
  const drafts = all.filter((t) => !t.saved).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, KEEP_DRAFTS);
  const keep = [...saved, ...drafts].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_THREADS);
  const put = (rows: Thread[]): void => localStorage.setItem(SLOT, JSON.stringify(rows.map(clean)));
  try {
    put(keep);
  } catch {
    // over quota: the audits go first, then the oldest threads
    try {
      put(keep.map((t) => ({ ...t, messages: t.messages.map(({ audit: _a, ...m }) => m) })));
    } catch {
      try {
        put(keep.slice(0, 10));
      } catch {
        /* a browser that will not keep them: the chat still works, the history does not */
      }
    }
  }
  window.dispatchEvent(new CustomEvent(EVENT));
}

/** Every thread, newest first. */
export const listThreads = (): Thread[] => read().slice().sort((a, b) => b.updatedAt - a.updatedAt);

/** One model's threads, newest first. */
export const threadsFor = (key: string): Thread[] => listThreads().filter((t) => t.key === key);

export const getThread = (id: string): Thread | undefined => read().find((t) => t.id === id);

/** Write a thread (by id), replacing it if it is there. */
export function saveThread(t: Thread): void {
  if (!t.id) return;
  const all = read().filter((x) => x.id !== t.id);
  all.push({ ...t, updatedAt: Date.now() });
  write(all);
}

/** Name a thread and keep it: a saved thread survives the draft prune and is never overwritten by the next chat. */
export function markSaved(id: string, title: string): Thread | undefined {
  const all = read();
  const t = all.find((x) => x.id === id);
  if (!t) return undefined;
  t.saved = true;
  t.title = title.trim() || t.title || autoTitle(t.messages);
  t.updatedAt = Date.now();
  write(all);
  return t;
}

export function removeThread(id: string): void {
  write(read().filter((t) => t.id !== id));
}

export function subscribe(fn: () => void): () => void {
  const onLocal = (): void => fn();
  window.addEventListener(EVENT, onLocal);
  window.addEventListener('storage', onLocal);
  return () => {
    window.removeEventListener(EVENT, onLocal);
    window.removeEventListener('storage', onLocal);
  };
}
