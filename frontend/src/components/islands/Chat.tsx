// The chat page: one question at a time to a finished ship's latest checkpoint. Experimental — the
// models are small and not instruction-tuned; the 9m's checkpoint is still queued, so the 1m is the
// run to exercise the interface until it lands.

import { useState } from 'react';
import { btnCls, cardCls, fieldCls, selectCls } from '@/lib/ui';
import { sectionProps } from '@/lib/useApi';

type Msg = { role: 'you' | 'thorp'; text: string };

const RUNS = [
  { key: '9m@v0.0.6', label: 'the 9m (first chat target — checkpoint still queued)' },
  { key: '1m@v0.0.6-fulldeck', label: 'the 1m fulldeck (test the interface)' },
];

export default function Chat() {
  const [run, setRun] = useState(RUNS[0].key);
  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');

  const send = async (): Promise<void> => {
    const q = input.trim();
    if (!q || busy) return;
    setMsgs((m) => [...m, { role: 'you', text: q }]);
    setInput('');
    setBusy(true);
    setNote('');
    try {
      const r = await fetch(`/api/chat?run=${encodeURIComponent(run)}&q=${encodeURIComponent(q)}`);
      const d = await r.json();
      if (d.error) setNote(String(d.error));
      else setMsgs((m) => [...m, { role: 'thorp', text: String(d.answer || '') }]);
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div {...sectionProps('chat')}>
      <h1>Chat <span className="q">with a finished ship; experimental: the models are small and not instruction-tuned, so a run without a chat/QA arm continues prose rather than answers</span></h1>
      <section className={cardCls(false, 'panel')}>
        <div className="handtools" data-filters>
          <label className="note" htmlFor="chatrun">ship</label>
          <select id="chatrun" className={selectCls('')} value={run} onChange={(e) => { setRun(e.target.value); setMsgs([]); setNote(''); }} title="the finished run to load">
            {RUNS.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
          </select>
          <span className="note">the 9m's first checkpoint is still queued; choose the 1m to exercise the interface.</span>
        </div>
        <div aria-live="polite" style={{ display: 'grid', gap: 8, margin: '12px 0', minHeight: 80 }}>
          {msgs.length === 0 ? <p className="note">No messages yet. Ask something; the model answers from its latest checkpoint.</p> : null}
          {msgs.map((m, i) => (
            <p key={i} style={{ margin: 0, padding: '8px 10px', borderRadius: 6, border: '1px solid var(--line)', background: m.role === 'you' ? 'transparent' : 'var(--panel, transparent)' }}>
              <b>{m.role === 'you' ? 'you' : 'ship'}:</b> {m.text}
            </p>
          ))}
          {busy ? <p className="note">reading the checkpoint and sampling…</p> : null}
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
            placeholder="Ask the ship a question…"
            aria-label="Your question"
            style={{ flex: 1 }}
          />
          <button className={btnCls()} type="submit" disabled={busy || !input.trim()}>{busy ? 'thinking…' : 'send'}</button>
        </form>
      </section>
    </div>
  );
}
