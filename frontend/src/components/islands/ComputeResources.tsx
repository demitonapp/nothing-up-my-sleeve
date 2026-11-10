// The yard's compute resources (10 November): add a machine, test it, see which ships fit its harbours, and
// cap a cloud resource's day and week. All of it is `s1.compute_resources` in Postgres.
import { useEffect, useState } from 'react';
import { btnCls, cardCls, fieldCls } from '@/lib/ui';

type R = any;

function Row({ r, onChanged }: { r: R; onChanged: () => void }) {
  const c = r.caps || {};
  const [caps, setCaps] = useState<any>({
    daily_usd: c.daily_usd ?? '', weekly_usd: c.weekly_usd ?? '',
    daily_hours: c.daily_hours ?? '', weekly_hours: c.weekly_hours ?? '',
  });
  const post = async (body: any) => {
    await fetch('/api/compute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    onChanged();
  };
  const fits = Object.entries(r.bench?.fits || {}).filter(([, v]) => v).map(([k]) => k);
  const cell = (k: string) => (
    <input type="number" value={caps[k]} placeholder={k.replace('_', ' ')} className={fieldCls('w-20')}
      onChange={(e) => setCaps({ ...caps, [k]: e.target.value })} />
  );
  return (
    <tr>
      <td><b>{r.name}</b><div className="s">{r.kind} · {r.specs?.chip || '—'} · {r.specs?.memory_gb ?? '?'} GB · {r.specs?.cpu_cores ?? '?'} cores</div></td>
      <td>{r.bench?.tokens_s ? `${Math.round(r.bench.tokens_s).toLocaleString()} tok/s` : '<span class="s">not tested</span>'}
        <div className="s">{r.bench?.peak_memory_gb != null ? `${r.bench.peak_memory_gb} GB peak` : ''}</div></td>
      <td>{fits.length ? fits.join(', ') : '—'}</td>
      <td>{cell('daily_usd')} {cell('weekly_usd')}<div className="s">USD / day · week</div>
        {cell('daily_hours')} {cell('weekly_hours')}<div className="s">hours / day · week</div>
        <button className={btnCls('outline', '')} onClick={() => void post({ action: 'caps', resource_id: r.resource_id, caps })}>save caps</button></td>
      <td><button className={btnCls('outline', '')} onClick={() => void post({ action: 'test', resource_id: r.resource_id })}>run test</button></td>
    </tr>
  );
}

export default function ComputeResources() {
  const [rs, setRs] = useState<R[]>([]);
  const [msg, setMsg] = useState('');
  const load = async () => {
    try { const d = await (await fetch('/api/compute')).json(); setRs(d.resources || []); } catch { setMsg('could not read the store'); }
  };
  useEffect(() => { void load(); }, []);
  const add = async (kind: string) => {
    setMsg('adding…');
    await fetch('/api/compute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'add', kind, name: kind === 'mac' ? 'This Mac' : 'Cloud GPU' }) });
    await load(); setMsg('added');
  };
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>Compute resources <span className="note">the machines the yard can run on, from `s1.compute_resources`: what each is (specs), what a test measured (tokens/s, peak memory), the ships its harbours hold, and the caps a cloud resource may spend. The test is provisional: forward-pass throughput, so the large-ship fits are optimistic</span></h2>
      <div className="scroll"><table className="selbooks" data-nosort>
        <thead><tr><th>resource</th><th>last test</th><th>harbours it holds</th><th>caps</th><th></th></tr></thead>
        <tbody>{rs.length ? rs.map((r) => <Row key={r.resource_id} r={r} onChanged={() => void load()} />) : <tr><td colSpan={5} className="s">no compute resource yet</td></tr>}</tbody>
      </table></div>
      <div className="handtools mt">
        <button className={btnCls('outline', '')} onClick={() => void add('mac')}>add this Mac</button>
        <button className={btnCls('outline', '')} onClick={() => void add('cloud')}>add a cloud GPU</button>
        {msg ? <span className="s">{msg}</span> : null}
      </div>
    </section>
  );
}
