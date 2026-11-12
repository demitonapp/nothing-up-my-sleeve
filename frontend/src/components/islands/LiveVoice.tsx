// The phone drone's live voice line (12 November, Justin: "download and connect personaplex to the call
// drone"). PersonaPlex is a full-duplex speech-to-speech model: microphone in, its own voice out, no text
// in the middle. The MLX Q4 build runs locally and serves its own UI on 127.0.0.1:8998; this panel owns
// that process and embeds the UI. The typed test line stays below it as the transcript-friendly path.
//
// The weights are not MIT: CC BY-NC 4.0 plus the NVIDIA Open Model License, so non-commercial. The panel
// says so rather than hiding it.

import { useState } from 'react';
import { btnCls, cardCls, emptyCls, pillCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

interface PL {
  installed: boolean;
  running: boolean;
  url: string;
  port: number;
  model: string;
  artifact_gib: number;
  license: string;
  local: boolean;
  log: string;
}

const post = async (url: string): Promise<PL> => {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const j = await r.json();
  if (!r.ok) throw new Error(j?.error || `${r.status} ${r.statusText}`);
  return j as PL;
};

export function LiveVoice() {
  const [tick, setTick] = useState(0);
  const { data, error } = useApi<PL>(`/api/drones/phone/personaplex?t=${tick}`, 8000);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setMsg(null);
    try { await fn(); setTick((n) => n + 1); }
    catch (e) { setMsg(String((e as Error)?.message ?? e)); }
    finally { setBusy(false); }
  };

  if (error) return <div className={emptyCls()}>the live voice line could not be read: {error}</div>;
  if (!data) return <div className={emptyCls()}>reading the live voice line…</div>;

  return (
    <section className={cardCls(false, 'panel livevoice')}>
      <div className="livevoicehead">
        <div>
          <h2>Live voice <span className="q">PersonaPlex, full duplex</span></h2>
          <p className="s">The microphone in, PersonaPlex's own voice out: it listens while it speaks, handles
            interruptions, and never turns the conversation into text. Audio stays on this Mac.</p>
        </div>
        <div className="livevoiceactions">
          <span className={pillCls(data.running ? 'good' : '')}>{data.running ? 'running' : data.installed ? 'stopped' : 'not installed'}</span>
          {data.running ? (
            <button className={btnCls('ghost')} disabled={busy} onClick={() => void act(() => post('/api/drones/phone/personaplex/stop'))}>stop</button>
          ) : (
            <button className={btnCls('default')} disabled={busy || !data.installed} onClick={() => void act(() => post('/api/drones/phone/personaplex/start'))}>
              {busy ? 'starting…' : 'start live voice'}
            </button>
          )}
          <a className={btnCls('ghost')} href={data.url} target="_blank" rel="noreferrer">open in a tab ↗</a>
        </div>
      </div>

      <div className="livevoicemeta">
        <span className={pillCls('blue')}>{data.model}</span>
        <span className={pillCls('')}>{data.artifact_gib} GiB</span>
        <span className={pillCls('accent')} title={data.license}>{data.license}</span>
        <span className="s">English only · loopback :{data.port}</span>
      </div>

      {msg ? <p className={pillCls('bad')}>{msg}</p> : null}

      {data.running ? (
        <iframe
          className="liveframe"
          title="PersonaPlex live voice"
          src={data.url}
          allow="microphone; autoplay; clipboard-write"
        />
      ) : (
        <div className={emptyCls()}>
          {data.installed
            ? 'start it, then allow the microphone in the frame; the first reply takes a moment while the voice prompt loads'
            : 'the PersonaPlex artifact is not on disk; download it into data/models/personaplex-edge-q4'}
        </div>
      )}

      <p className="s">The typed test line below is the transcript-friendly path and keeps the safety gates.
        This live line is the real voice model; its weights are non-commercial (CC BY-NC 4.0 + NVIDIA Open
        Model License), and the page keeps that badge beside it.</p>
    </section>
  );
}
