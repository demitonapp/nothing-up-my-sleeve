// The yard's compute, live from Postgres (10 November): the Mac lane's seats (s2.lanes) and the Vast.ai
// lane's key (s5.provider_credentials, never shown back) and seats. The coordinator and the charter read
// these rows, so a change here takes effect without a restart.
import { useEffect, useState } from 'react';
import { btnCls, cardCls, fieldCls } from '@/lib/ui';

type C = { mac_seats: number; vast_seats: number; helm_seats: number; at_sea: string[]; two_at_once: string[]; queue: number };
type V = { has_key: boolean; key_hint: string; seats: number };

export default function YardConstraints() {
  const [c, setC] = useState<C | null>(null);
  const [v, setV] = useState<V | null>(null);
  const [seats, setSeats] = useState(1);
  const [vseats, setVseats] = useState(1);
  const [vkey, setVkey] = useState('');
  const [msg, setMsg] = useState('');
  const load = async () => {
    try {
      const [a, b] = await Promise.all([fetch('/api/constraints'), fetch('/api/vast')]);
      const d = (await a.json()) as C; const e = (await b.json()) as V;
      setC(d); setV(e); setSeats(d.mac_seats ?? 1); setVseats(e.seats ?? 1);
    } catch { setMsg('could not read the store'); }
  };
  useEffect(() => { void load(); }, []);
  const saveMac = async () => {
    setMsg('saving…');
    const r = await fetch('/api/constraints', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mac_seats: seats }) });
    if (r.ok) { setC((await r.json()) as C); setMsg('mac saved'); } else setMsg('failed');
  };
  const saveVast = async () => {
    setMsg('saving…');
    const r = await fetch('/api/vast', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: vkey || undefined, seats: vseats }) });
    if (r.ok) { setV((await r.json()) as V); setVkey(''); setMsg('vast saved'); } else setMsg('failed');
  };
  if (!c || !v) return <section className={cardCls(false, 'panel')}><div className="s">reading the yard’s compute…</div></section>;
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>Your compute <span className="note">from Postgres: the Mac lane’s seats (`s2.lanes`) and the Vast.ai lane’s key (`s5.provider_credentials`) and seats. The coordinator and the charter read these rows; nothing here is a file or an environment variable</span></h2>
      <div className="row">
        <div className="tfs"><b>{c.mac_seats}</b><span>Mac seats (slipways)</span></div>
        <div className="tfs"><b>{v.seats}</b><span>Vast seats</span></div>
        <div className="tfs"><b>{c.two_at_once.join(', ')}</b><span>hulls allowed to share the GPU</span></div>
        <div className="tfs"><b>{c.queue}</b><span>lines queued{c.at_sea.length ? `; ${c.at_sea.length} at sea` : ''}</span></div>
      </div>
      <div className="handtools mt">
        <label className="note" htmlFor="yardseats">Mac seats</label>
        <input id="yardseats" type="number" min={1} max={8} value={seats} onChange={(e) => setSeats(Number(e.target.value))} className={fieldCls('w-20')} />
        <button className={btnCls('outline', '')} onClick={() => void saveMac()}>save mac</button>
      </div>
      <div className="handtools mt">
        <label className="note" htmlFor="vastkey">Vast.ai key</label>
        <input id="vastkey" type="password" placeholder={v.has_key ? `held (${v.key_hint})` : 'paste a key'} value={vkey} onChange={(e) => setVkey(e.target.value)} className={fieldCls('w-72')} />
        <label className="note" htmlFor="vastseats">seats</label>
        <input id="vastseats" type="number" min={1} max={8} value={vseats} onChange={(e) => setVseats(Number(e.target.value))} className={fieldCls('w-20')} />
        <button className={btnCls('outline', '')} onClick={() => void saveVast()}>save vast</button>
        {msg ? <span className="s">{msg}</span> : null}
      </div>
      <p className="note">Only a 300k hull may take the Mac’s second seat (two 1m or 9m do not fit on one GPU). A Vast.ai hire is one seat per instance; the budget and the charter terms are under <span className="mono">thorp charter terms</span>.</p>
    </section>
  );
}
