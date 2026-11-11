// Notes kept from the chat console (11 November, Justin: "and also save notes"): a line written mid-chat,
// kept in this browser beside the threads, with the model it was written against.
//
// Small and local: a note is a sentence you did not want to lose while reading an answer, not a document.
// It carries the thread it came from when there is one, so a note can be found again from the chat.

export interface Note {
  id: string;
  text: string;
  model: string;
  threadId?: string;
  createdAt: number;
}

const SLOT = 'thorp.chat.notes.v1';
const MAX = 300;
const EVENT = 'thorp:notes';

export const newNoteId = (): string => `n${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

const read = (): Note[] => {
  try {
    const raw = JSON.parse(localStorage.getItem(SLOT) || '[]');
    return Array.isArray(raw) ? (raw as Note[]).filter((n) => n && typeof n.text === 'string') : [];
  } catch {
    return [];
  }
};

function write(all: Note[]): void {
  try {
    localStorage.setItem(SLOT, JSON.stringify(all.slice(0, MAX)));
  } catch {
    try {
      localStorage.setItem(SLOT, JSON.stringify(all.slice(0, 50)));
    } catch {
      /* a browser that will not keep them: the console still works */
    }
  }
  window.dispatchEvent(new CustomEvent(EVENT));
}

export const listNotes = (): Note[] => read().sort((a, b) => b.createdAt - a.createdAt);

export function addNote(text: string, model: string, threadId?: string): Note | null {
  const t = text.trim();
  if (!t) return null;
  const n: Note = { id: newNoteId(), text: t, model, threadId, createdAt: Date.now() };
  write([n, ...read()]);
  return n;
}

export function removeNote(id: string): void {
  write(read().filter((n) => n.id !== id));
}

export function subscribeNotes(fn: () => void): () => void {
  const onLocal = (): void => fn();
  window.addEventListener(EVENT, onLocal);
  window.addEventListener('storage', onLocal);
  return () => {
    window.removeEventListener(EVENT, onLocal);
    window.removeEventListener('storage', onLocal);
  };
}
