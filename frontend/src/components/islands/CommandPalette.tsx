// The command palette (11 November, Justin: "can you add a cmd K whereby I can choose type a model to
// chat to and be navigated to it"): ⌘K or Ctrl+K on any page opens a filter over every model the chat
// can reach — a Nothing up my sleeve ship with a finished checkpoint, a foreign model with its weights
// cached — and ⏎ opens that model's chat page, ⇥/↑↓ to move, esc to close.
//
// Mounted in the layout, so it is the same palette everywhere; it reads /api/chat/models the first time
// it opens, never on page load, and the list is the chat's own list (available, with a target), so the
// palette can never send you to a ship that cannot answer.

import { useEffect, useMemo, useRef, useState } from 'react';
import foreign from '@/data/foreign.json';
import { fmtParams } from '@/lib/format';
import { fieldCls } from '@/lib/ui';

/** The foreign ships with a page of their own (data/foreign.json, written from thorp.foreign.models).
 *  A model read for a chat and not in this list still has a chat — on /chat, preselected — so the
 *  palette never sends anyone to a harbour address that is not a route in dev. */
const FOREIGN_PAGES = new Set<string>((foreign as { keys: string[] }).keys);

export interface Model {
  kind: 'thorp' | 'foreign';
  model?: string | null;
  ship_key: string;
  name: string;
  params: number | null;
  available: boolean;
  run: { run: string; step: string } | null;
  why: string | null;
}

/** A model's chat page: the ship's own tab for our ships, the harbour ship's for a foreign one that has
 *  a page, and /chat preselected for a foreign one that does not. The ship key is used as it is written
 *  (`300k:2980e0eca706`): its colon is a legal path character, and percent-encoding it misses the route. */
export const chatHref = (m: Pick<Model, 'kind' | 'model' | 'ship_key'>): string => {
  if (m.kind === 'foreign') {
    const key = String(m.model || '');
    return FOREIGN_PAGES.has(key) ? `/foreign/${key}/chat` : `/chat?model=${encodeURIComponent(key)}`;
  }
  return `/ships/${m.ship_key}/chat`;
};

/** The list, filtered and ranked: a name that starts with what was typed first, then a name that holds
 *  it, then the bigger model first, then the alphabet. Pure, so the ranking can be read without a browser. */
export function filterModels(models: Model[] | null, q: string): Model[] {
  const needle = q.trim().toLowerCase();
  return (models || [])
    .map((m) => {
      const name = m.name.toLowerCase();
      const hay = `${name} ${String(m.model || '').toLowerCase()} ${m.ship_key.toLowerCase()}`;
      const where = needle ? hay.indexOf(needle) : 0;
      return { m, where, starts: name.startsWith(needle) ? 0 : 1 };
    })
    .filter((x) => x.where >= 0)
    .sort((a, b) => a.starts - b.starts || (b.m.params || 0) - (a.m.params || 0) || a.m.name.localeCompare(b.m.name))
    .map((x) => x.m);
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [at, setAt] = useState(0);
  const [models, setModels] = useState<Model[] | null>(null);
  const [error, setError] = useState('');
  const box = useRef<HTMLInputElement | null>(null);

  // ⌘K anywhere opens it; esc closes it; a button in the header can ask for it by name
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    const onAsk = (): void => setOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('thorp:palette', onAsk);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('thorp:palette', onAsk);
    };
  }, []);

  // read the models the first time it opens, never on page load
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
        if (live) setError(String((e as Error)?.message ?? e));
      }
    })();
    return () => {
      live = false;
    };
  }, [open, models]);

  useEffect(() => {
    if (!open) return;
    setQ('');
    setAt(0);
    const t = window.setTimeout(() => box.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  const rows = useMemo(() => filterModels(models, q), [models, q]);

  const go = (m: Model | undefined): void => {
    if (!m) return;
    setOpen(false);
    location.assign(chatHref(m));
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setAt((i) => Math.min(rows.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setAt((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      go(rows[at]);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      setAt((i) => (rows.length ? (i + 1) % rows.length : 0));
    }
  };

  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="chat with a model"
      style={{ position: 'fixed', inset: 0, zIndex: 120, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh', background: 'rgba(0,0,0,.5)' }}
      onClick={() => setOpen(false)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(640px, 92vw)', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 24px 60px rgba(0,0,0,.4)', overflow: 'hidden' }}
      >
        <input
          ref={box}
          className={fieldCls('')}
          value={q}
          onChange={(e) => { setQ(e.target.value); setAt(0); }}
          onKeyDown={onKeyDown}
          placeholder="Type a model to chat to…"
          aria-label="model to chat to"
          aria-controls="cmdkrows"
          autoComplete="off"
          spellCheck={false}
          style={{ width: '100%', border: 0, borderBottom: '1px solid var(--line)', borderRadius: 0, padding: '12px 14px', fontSize: '1em' }}
        />
        <div id="cmdkrows" role="listbox" aria-label="models" style={{ maxHeight: '48vh', overflowY: 'auto' }}>
          {error ? <div className="note" style={{ padding: '12px 14px' }}>the models could not be read: {error}</div> : null}
          {!error && models == null ? <div className="note" style={{ padding: '12px 14px' }}>reading the models…</div> : null}
          {!error && models != null && !rows.length ? (
            <div className="note" style={{ padding: '12px 14px' }}>no model with a checkpoint or cached weights matches “{q.trim()}”</div>
          ) : null}
          {rows.map((m, i) => (
            <button
              key={`${m.kind}:${m.ship_key}`}
              type="button"
              role="option"
              aria-selected={i === at}
              onMouseEnter={() => setAt(i)}
              onClick={() => go(m)}
              style={{
                display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                padding: '9px 14px', border: 0, borderBottom: '1px solid var(--line)',
                background: i === at ? 'var(--raise)' : 'transparent', color: 'inherit', font: 'inherit',
              }}
            >
              <span style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
                <b>{m.name}</b>
                <span className="note">{fmtParams(m.params)}</span>
              </span>
              <span className="note" style={{ display: 'block', marginTop: 2 }}>
                {m.kind === 'foreign' ? `foreign · ${m.model}` : `our ship · ${m.run ? `checkpoint ${m.run.step}` : m.ship_key}`}
              </span>
            </button>
          ))}
        </div>
        <div className="note" style={{ padding: '8px 14px', display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span>↑↓ choose · ⏎ chat · esc close</span>
          <span>{models ? `${rows.length} of ${models.length}` : ''}</span>
        </div>
      </div>
    </div>
  );
}
