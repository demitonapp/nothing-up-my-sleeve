// The chat's saved conversations (11 November, Justin: "ok so we also need an ability to save a chat
// then"): a chat is a thread, several a model, each kept in this browser.
//
// The first cut kept one conversation a model, so a second chat replaced the first — which is fine until
// a chat is worth keeping. A thread now has an id and a title: every chat is written as it happens (a
// draft, titled by its first question), and "Save" gives it a name and marks it, so the next chat with
// the same model starts a new thread instead of overwriting the saved one. Saved threads are never
// pruned; drafts are, oldest first, once there are more than KEEP_DRAFTS of them.
//
// A thread can be filed in a folder (13 November, Justin: "past chats need to have a folder concept for
// cataloguing"): `folder` is its name, '' or absent for unfiled. A folder exists while a chat is filed in
// it; one made before anything is filed in it is kept in this browser's folder list until it is.
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
  folder?: string;
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
const FOLDERS = 'thorp.chat.folders.v1';

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
  // a chat filed in a folder is kept like a saved one: it was catalogued, so the draft prune leaves it
  const kept = (t: Thread): boolean => t.saved || !!(t.folder || '').trim();
  const saved = all.filter(kept).slice(0, MAX_THREADS);
  const drafts = all.filter((t) => !kept(t)).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, KEEP_DRAFTS);
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
/** Postgres, best-effort: the local store is the fast one; the server copy is what survives a browser. */
function push(t: Thread): void {
  void fetch('/api/chat/threads', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(t),
  }).catch(() => { /* the local store still has it */ });
}

export function saveThread(t: Thread): void {
  if (!t.id) return;
  const all = read().filter((x) => x.id !== t.id);
  const next = { ...t, updatedAt: Date.now() };
  all.push(next);
  write(all);
  push(next);
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
  push(t);
  return t;
}

/** File chats in a folder ('' unfiles them). */
export function fileThreads(ids: string[], folder: string): void {
  const name = folder.trim();
  const all = read();
  const moved: Thread[] = [];
  for (const t of all) {
    if (!ids.includes(t.id) || (t.folder || '') === name) continue;
    t.folder = name;
    t.updatedAt = Date.now();
    moved.push(t);
  }
  if (!moved.length) return;
  write(all);
  moved.forEach(push);
}

const readFolders = (): string[] => {
  try {
    const raw = JSON.parse(localStorage.getItem(FOLDERS) || '[]');
    return Array.isArray(raw) ? raw.filter((f): f is string => typeof f === 'string' && !!f.trim()) : [];
  } catch {
    return [];
  }
};
const writeFolders = (names: string[]): void => {
  try { localStorage.setItem(FOLDERS, JSON.stringify([...new Set(names)])); } catch { /* blocked */ }
  window.dispatchEvent(new CustomEvent(EVENT));
};

/** Every folder: those a chat is filed in, and those made here and not yet used, by name. */
export const listFolders = (): string[] =>
  [...new Set([...readFolders(), ...read().map((t) => (t.folder || '').trim()).filter(Boolean)])].sort((a, b) =>
    a.localeCompare(b, undefined, { sensitivity: 'base' }));

/** A new, empty folder. */
export function addFolder(name: string): void {
  const n = name.trim();
  if (n) writeFolders([...readFolders(), n]);
}

/** Rename a folder: every chat in it moves with it. */
export function renameFolder(from: string, to: string): void {
  const n = to.trim();
  if (!n || n === from) return;
  writeFolders([...readFolders().filter((f) => f !== from), n]);
  fileThreads(read().filter((t) => (t.folder || '') === from).map((t) => t.id), n);
}

/** Remove a folder. Its chats are kept, unfiled. */
export function dropFolder(name: string): void {
  writeFolders(readFolders().filter((f) => f !== name));
  fileThreads(read().filter((t) => (t.folder || '') === name).map((t) => t.id), '');
}

export function removeThread(id: string): void {
  write(read().filter((t) => t.id !== id));
  void fetch('/api/chat/threads/delete', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id }),
  }).catch(() => { /* the local store still forgot it */ });
}

/** Merge the server's threads into this browser's store (newest wins per id), then tell the pages.
 *  A slow read leaves the local store untouched. */
export async function syncThreads(): Promise<void> {
  try {
    const r = await fetch('/api/chat/threads');
    if (!r.ok) return;
    const d = (await r.json()) as { threads?: Thread[] };
    const incoming = d.threads || [];
    if (!incoming.length) return;
    const all = read();
    const byId = new Map(all.map((t) => [t.id, t]));
    let changed = false;
    for (const t of incoming) {
      const have = byId.get(t.id);
      if (!have || (t.updatedAt || 0) > (have.updatedAt || 0)) { byId.set(t.id, t); changed = true; }
      // a folder this browser holds and the server lacks (filed while the server kept no folders): sent again
      else if ((have.folder || '') !== (t.folder || '')) push(have);
    }
    if (!changed) return;
    write([...byId.values()].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)));
  } catch {
    /* offline: the local store is the store */
  }
}

// one sync a page: the server's threads land in the local store before the first sidebar render
if (typeof window !== 'undefined') {
  window.setTimeout(() => { void syncThreads(); }, 0);
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
