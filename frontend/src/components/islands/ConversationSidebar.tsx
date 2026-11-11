// The chat's left rail (11 November, Justin: "Chat has to be a primary component of the UI. So it needs to
// have a permanent left sidebar which when opens shows all the recent conversations by model"; then "we
// also need an ability to save a chat").
//
// Always beside the chat, open or closed. Open, it lists every thread this browser has, grouped by model:
// a saved thread carries its title and a ★, a draft is titled by its first question. A click opens a
// thread, the × forgets it, and Save names the chat you are in so the next one with the same model starts
// beside it instead of replacing it.

import { useEffect, useMemo, useState } from 'react';
import { listThreads, removeThread, subscribe, type Thread } from '@/lib/conversations';

const when = (t: number): string => {
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};

const lastLine = (t: Thread): string => {
  const last = [...t.messages].reverse().find((m) => m.text);
  return (last?.text || '').replace(/\s+/g, ' ').slice(0, 90);
};

export default function ConversationSidebar({ activeId, onOpen, onNew, onSave, open, onOpenChange }: {
  activeId: string;
  onOpen: (t: Thread) => void;
  onNew: () => void;
  onSave: (id: string, title: string) => void;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [naming, setNaming] = useState('');
  useEffect(() => {
    const sync = (): void => setThreads(listThreads());
    sync();
    return subscribe(sync);
  }, []);

  // grouped by model, the model with the newest thread first, each model's threads newest first
  const groups = useMemo(() => {
    const by = new Map<string, Thread[]>();
    for (const t of threads) {
      const list = by.get(t.key);
      if (list) list.push(t);
      else by.set(t.key, [t]);
    }
    return [...by.values()];
  }, [threads]);

  const active = threads.find((t) => t.id === activeId);

  if (!open) {
    return (
      <aside className="chatrail closed" aria-label="conversations">
        <button
          type="button"
          className="chatrailtoggle"
          onClick={() => onOpenChange(true)}
          title="recent conversations"
          aria-label={`recent conversations (${threads.length})`}
        >
          <span aria-hidden="true">☰</span>
          {threads.length ? <span className="chatrailcount">{threads.length}</span> : null}
        </button>
      </aside>
    );
  }

  return (
    <aside className="chatrail" aria-label="recent conversations">
      <div className="chatrailhead">
        <b>Conversations</b>
        <span className="note">{threads.length}</span>
        <button type="button" className="chatrailtoggle" onClick={() => onOpenChange(false)} title="collapse" aria-label="collapse the conversations">‹</button>
      </div>
      <div className="chatrailacct">
        <button type="button" className="chatrailnew" onClick={onNew}>+ New chat</button>
        {active && !active.saved ? (
          <button
            type="button"
            className="chatrailsave"
            onClick={() => setNaming(active.title || '')}
            title="save this chat so the next one with the same model starts beside it"
          >
            ★ Save this chat
          </button>
        ) : null}
      </div>
      {naming !== '' && active ? (
        <form
          className="chatrailform"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(active.id, naming.trim() || active.title);
            setNaming('');
          }}
        >
          <input
            autoFocus
            value={naming}
            onChange={(e) => setNaming(e.target.value)}
            placeholder="name this chat"
            aria-label="name this chat"
          />
          <button type="submit">save</button>
          <button type="button" onClick={() => setNaming('')} aria-label="cancel">×</button>
        </form>
      ) : null}
      <div className="chatraillist">
        {threads.length === 0 ? (
          <p className="note chatrailempty">No conversations yet. Ask a model something and it is kept here, on this browser.</p>
        ) : null}
        {groups.map((rows) => (
          <div key={rows[0].key} className="chatrailgroup">
            <div className="chatrailgroupname">{rows[0].name}</div>
            {rows.map((t) => (
              <div key={t.id} className={`chatrailrow${t.id === activeId ? ' active' : ''}`}>
                <button type="button" className="chatrailopen" onClick={() => onOpen(t)} title={`open ${t.title}`}>
                  <span className="chatrailtitle">
                    {t.saved ? <span className="chatrailstar" aria-label="saved">★</span> : null}
                    {t.title || lastLine(t) || 'an untitled chat'}
                  </span>
                  <span className="note chatrailmeta">
                    {t.messages.filter((m) => m.role === 'you').length} turn{t.messages.filter((m) => m.role === 'you').length === 1 ? '' : 's'}
                    {' · '}{when(t.updatedAt)}{t.id === activeId ? ' · here' : ''}
                  </span>
                  {lastLine(t) ? <span className="chatraillast">{lastLine(t)}</span> : null}
                </button>
                <button
                  type="button"
                  className="chatraildel"
                  onClick={() => removeThread(t.id)}
                  title="forget this conversation"
                  aria-label={`forget ${t.title}`}
                >×</button>
              </div>
            ))}
          </div>
        ))}
      </div>
    </aside>
  );
}
