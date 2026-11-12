// The fleet's checkpoints on the Liberty Machine's S1 page (12 November, Justin: "audit and review the
// checkpoints. Take their findings and update them in the liberty machine and then clean it up"): what is on disk,
// what is kept and why, what is stale, and what the last cleanup freed. The audit and the verdicts are
// thorp/checkpoints.py's; this panel only draws them. Read-only: the cleanup is `python -m thorp.checkpoints clean`.

import { cardCls, emptyCls, pillCls } from '@/lib/ui';
import { fmtBytes } from '@/lib/format';
import { useApi } from '@/lib/useApi';

type Entry = {
  run_id: string;
  name: string;
  preset: string;
  status: string;
  finished?: string | null;
  step?: number | null;
  bytes: number;
  verdict: 'keep' | 'delete';
  reasons: string[];
};
type Audit = {
  at: string;
  count: number;
  bytes: number;
  kept_bytes: number;
  delete_bytes: number;
  delete_count: number;
  disk: { bytes: number | null; total: number | null };
  entries: Entry[];
};
type Removed = Pick<Entry, 'run_id' | 'name' | 'preset' | 'bytes' | 'reasons'>;
type Payload = { audit: Audit | null; last_cleanup: { at: string; freed_bytes: number; deleted: Removed[] } | null };

const when = (iso?: string | null): string => {
  if (!iso) return '–';
  const d = new Date(iso);
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};

export function Checkpoints() {
  const { data, error } = useApi<Payload>('/api/liberty-machine/checkpoints', 60000);
  const a = data?.audit, last = data?.last_cleanup;
  if (error) return <section className={cardCls(false, 'panel')}><h2>Checkpoints</h2><div className={emptyCls()}>the checkpoints could not be read: {error}</div></section>;
  if (!a) return <section className={cardCls(false, 'panel')}><h2>Checkpoints</h2><div className={emptyCls()}>reading the fleet's saved minds…</div></section>;
  const rows = a.entries.slice(0, 18);
  return (
    <section className={cardCls(false, 'panel')} id="checkpoints">
      <h2>Checkpoints <span className="note">every saved mind on this Mac, against the run that wrote it: at sea, the latest and best of each class, and what a queued voyage reads are kept; everything else that finished is superseded, and everything that did not finish is stale. The cleanup is <code>python -m thorp.checkpoints clean</code></span></h2>
      <div className="govstats">
        <div className="govstat"><b>{a.count}</b><span>checkpoint sets</span></div>
        <div className="govstat"><b>{fmtBytes(a.bytes)}</b><span>on disk</span></div>
        <div className="govstat ok"><b>{fmtBytes(a.kept_bytes)}</b><span>kept ({a.count - a.delete_count})</span></div>
        <div className={`govstat${a.delete_count ? ' warn' : ' ok'}`}><b>{a.delete_bytes ? fmtBytes(a.delete_bytes) : '0 B'}</b><span>stale ({a.delete_count})</span></div>
        <div className="govstat"><b>{fmtBytes(a.disk.bytes)}</b><span>free on the Mac</span></div>
      </div>
      {last ? <p className="s">Last cleanup {when(last.at)}: <b>{last.deleted.length}</b> checkpoint set{last.deleted.length === 1 ? '' : 's'} removed, <b>{fmtBytes(last.freed_bytes)}</b> freed.</p> : null}
      {last && last.deleted.length ? <details className="s"><summary>What the last cleanup removed (largest first)</summary><ul className="qvlist">{[...last.deleted].sort((x, y) => y.bytes - x.bytes).slice(0, 10).map((d) => <li key={d.run_id}><b className="mono">{d.name}</b> <span className="s">{d.preset} · {fmtBytes(d.bytes)} · {d.reasons.join('; ')}</span></li>)}</ul>{last.deleted.length > 10 ? <p className="s">and {last.deleted.length - 10} more; the record is data/checkpoint-cleanup.json.</p> : null}</details> : null}
      <div className="scroll">
        <table data-nosort>
          <thead><tr><th>voyage</th><th>class</th><th>state</th><th>size</th><th>step</th><th>verdict</th><th>why</th></tr></thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.run_id} className={e.verdict === 'delete' ? 'warn' : ''}>
                <td><b className="mono">{e.name}</b><div className="s mono">{e.run_id.slice(0, 12)}</div></td>
                <td><span className={pillCls('')}>{e.preset}</span></td>
                <td className="s">{e.status}</td>
                <td className="s">{fmtBytes(e.bytes)}</td>
                <td className="s">{e.step != null ? e.step.toLocaleString() : '–'}</td>
                <td>{e.verdict === 'delete' ? <span className={pillCls('bad')}>stale</span> : <span className={pillCls('good')}>keep</span>}</td>
                <td className="s">{e.reasons.join('; ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {a.entries.length > rows.length ? <p className="s">Showing the {rows.length} largest of {a.entries.length}; the full audit is <code>python -m thorp.checkpoints</code>.</p> : null}
      <p className="s">A checkpoint is only deleted when it is neither at sea, nor the latest or best of its class, nor read by a queued voyage, nor finished in the last 24 hours. Empty or unknown directories are left alone.</p>
    </section>
  );
}
