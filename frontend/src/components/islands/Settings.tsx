// Settings (/settings, the cog in the header; /api/settings, thorp/dash/settings.py): what the dashboard
// runs on. Read-only: the disk and what is kept on it, the store, the server and its machine, the
// switches and keys, and the lanes. Each part is read on its own server-side, so one that failed says
// why and the rest still stands.

import { useState } from 'react';
import { cardCls, btnCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi } from '@/lib/useApi';
import { shipHash } from '@/scripts/router';

interface Part { key: string; name: string; about: string; path: string; bytes: number | null }
interface Storage {
  error?: string;
  disk: { total: number; used: number; free: number; at: string } | null;
  ours: number;
  parts: Part[];
  checkpoints: { count: number; top: { run_id: string; bytes: number; name?: string; ship?: string; status?: string; steps: number }[] };
  models: { count: number; top: { model: string; bytes: number }[] };
  measured: number;
}
interface Store {
  error?: string; url: string; ok: boolean; version?: string; bytes?: number; table_count?: number;
  holds: { ledger: boolean; library: boolean; queue: boolean } | null;
  tables?: { name: string; bytes: number; rows: number }[];
}
interface Server {
  error?: string; version: string | null; branch: string; commit: string; commit_subject: string; commit_at: string;
  uncommitted: number; python: string; frameworks: Record<string, string | null>; platform: string; chip: string;
  cores: number | null; memory: number | null; pid: number; started: number; uptime: number; built: number | null; executable: string;
}
interface SettingsData {
  storage: Storage;
  store: Store;
  server: Server;
  paths: { name: string; path: string; about: string; exists: boolean }[] | { error: string };
  environment: { error?: string; switches: { name: string; value: string | null; about: string }[]; keys: { name: string; set: boolean; about: string }[] };
  lanes: { error?: string; lanes: { lane: string; seats: number; out: string | null }[] };
}

/** A size on disk, in the units the Finder uses (powers of ten). */
const bytes = (v: number | null | undefined): string => {
  if (v == null) return '–';
  if (v >= 1e12) return `${(v / 1e12).toFixed(2)} TB`;
  if (v >= 1e9) return `${(v / 1e9).toFixed(v >= 1e11 ? 0 : 1)} GB`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(v >= 1e8 ? 0 : 1)} MB`;
  return `${Math.max(0, v / 1e3).toFixed(0)} KB`;
};
const pct = (part: number | null | undefined, whole: number | null | undefined): string =>
  !part || !whole ? '–' : part / whole < 0.001 ? '<0.1%' : `${(100 * part / whole).toFixed(part / whole < 0.1 ? 1 : 0)}%`;
const when = (t: number | null | undefined): string => (t ? new Date(t * 1000).toLocaleString() : '–');
const span = (s: number): string => {
  const m = Math.floor(s / 60), h = Math.floor(m / 60), d = Math.floor(h / 24);
  return d ? `${d} d ${h % 24} h` : h ? `${h} h ${m % 60} min` : m ? `${m} min` : 'under a minute';
};

/** A size as a bar against the biggest of its table, so the eye finds what is heavy. */
function Bar({ value, of }: { value: number | null; of: number }) {
  const w = value && of ? Math.max(1, Math.round(100 * value / of)) : 0;
  return <span className="setbar" aria-hidden="true"><i style={{ width: `${w}%` }} /></span>;
}

function Failed({ what, error }: { what: string; error: string }) {
  return <div className={emptyCls()}>{what} could not be read: {error}</div>;
}

export default function Settings() {
  const [fresh, setFresh] = useState(0);
  // the first read uses the server's minute-old sizes; "measure again" asks for them now
  const { data: d, error } = useApi<SettingsData>(fresh ? `/api/settings?fresh=1&n=${fresh}` : '/api/settings', 60000);
  const st = d?.storage, pg = d?.store, sv = d?.server, env = d?.environment;
  const parts = st?.parts || [];
  const most = Math.max(1, ...parts.map((p) => p.bytes || 0));
  const disk = st?.disk;
  const others = disk && st ? Math.max(0, disk.used - st.ours) : 0;

  return (
    <div {...sectionProps('settings')}>
      <h1>Settings <span className="q">what this dashboard runs on: the disk and what is kept on it, the store, the server and its machine, the switches and the lanes. Nothing is changed from this page; each part says where it is set</span></h1>

      {error && !d ? <div className={emptyCls()}>the settings could not be read: {error}. A server started before this page was added has no /api/settings: restart <code>thorp dash</code>.</div>
        : !d ? <div className={emptyCls()}>reading the settings…</div>
        : (
          <>
            <section className={cardCls(false, 'panel')}>
              <h2>Storage <span className="note">the space each part takes on disk, measured {st?.measured ? new Date(st.measured * 1000).toLocaleTimeString() : ''} <button type="button" className={btnCls('ghost')} onClick={() => setFresh((n) => n + 1)}>measure again</button></span></h2>
              {!st || st.error ? <Failed what="the disk" error={st?.error || 'no answer'} /> : (
                <>
                  <div className="govstats">
                    <div className="govstat big"><b>{bytes(st.ours)}</b><span>kept by Nothing up my sleeve</span></div>
                    {disk ? <div className={`govstat${disk.free / disk.total < 0.1 ? ' warn' : ''}`}><b>{bytes(disk.free)}</b><span>free of {bytes(disk.total)}</span></div> : null}
                    {parts[0] ? <div className="govstat"><b>{bytes(parts[0].bytes)}</b><span>the biggest part: {parts[0].name.toLowerCase()}</span></div> : null}
                    <div className="govstat"><b>{st.checkpoints.count}</b><span>voyages with checkpoints</span></div>
                    <div className="govstat"><b>{st.models.count}</b><span>outside models downloaded</span></div>
                  </div>
                  {disk ? (
                    <>
                      <div className="setdisk mt" role="img" aria-label={`the disk: ${bytes(st.ours)} ours, ${bytes(others)} everything else, ${bytes(disk.free)} free`}>
                        <i className="ours" style={{ width: `${100 * st.ours / disk.total}%` }} title={`Nothing up my sleeve: ${bytes(st.ours)}`} />
                        <i className="others" style={{ width: `${100 * others / disk.total}%` }} title={`everything else on the disk: ${bytes(others)}`} />
                      </div>
                      <div className="setkey s"><span><i className="ours" /> Nothing up my sleeve {bytes(st.ours)} ({pct(st.ours, disk.total)})</span><span><i className="others" /> everything else on the disk {bytes(others)}</span><span><i /> free {bytes(disk.free)} ({pct(disk.free, disk.total)})</span></div>
                    </>
                  ) : null}
                  <div className="scroll mt">
                    <table id="setparts" data-nosort>
                      <thead><tr><th>part</th><th>size</th><th>share <span className="s">of ours</span></th><th></th><th>what it is</th><th>where</th></tr></thead>
                      <tbody>
                        {parts.map((p) => (
                          <tr key={p.key}>
                            <td><b>{p.name}</b></td>
                            <td className="num">{bytes(p.bytes)}</td>
                            <td className="num">{pct(p.bytes, st.ours)}</td>
                            <td><Bar value={p.bytes} of={most} /></td>
                            <td className="s">{p.about}</td>
                            <td><code>{p.path}</code></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="note mt">A size is the space taken on disk (<code>du</code>), so a file the disk shares between two folders counts once where it lies. The disk's own free space is what macOS reports for the volume the data sits on. Nothing here is deleted from the dashboard: a checkpoint belongs to a voyage in the ledger, and an outside model is fetched again the next time it is read.</p>

                  <details className="setfold">
                    <summary>The heaviest checkpoints <span className="s">the {st.checkpoints.top.length} biggest of {st.checkpoints.count} voyages' folders</span></summary>
                    <div className="scroll">
                      <table data-nosort>
                        <thead><tr><th>voyage</th><th>size</th><th></th><th>saved steps</th><th>status</th><th>ship</th></tr></thead>
                        <tbody>
                          {st.checkpoints.top.map((c) => (
                            <tr key={c.run_id}>
                              <td>{c.name ? <a href={shipHash(c.name)} title={c.run_id}>{c.name}</a> : <code title="no voyage of this id in the ledger">{c.run_id.slice(0, 12)}</code>}</td>
                              <td className="num">{bytes(c.bytes)}</td>
                              <td><Bar value={c.bytes} of={st.checkpoints.top[0]?.bytes || 1} /></td>
                              <td className="num">{c.steps || '–'}</td>
                              <td>{c.status ? <span className={pillCls(c.status === 'finished' ? 'good' : c.status === 'running' ? 'running' : '')}>{c.status}</span> : <span className="s">not in the ledger</span>}</td>
                              <td className="s">{c.ship || ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>

                  <details className="setfold">
                    <summary>The outside models <span className="s">{st.models.count} in the Hugging Face cache, biggest first</span></summary>
                    <div className="scroll">
                      <table data-nosort>
                        <thead><tr><th>model</th><th>size</th><th></th></tr></thead>
                        <tbody>
                          {st.models.top.map((m) => (
                            <tr key={m.model}>
                              <td>{m.model}</td>
                              <td className="num">{bytes(m.bytes)}</td>
                              <td><Bar value={m.bytes} of={st.models.top[0]?.bytes || 1} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </>
              )}
            </section>

            <div className="row">
              <section className={cardCls(false, 'panel')}>
                <h2>The store <span className="note">Postgres: the ledger, the library, the queue and the VSM's records. Its address is <code>THORP_PG</code></span></h2>
                {!pg || (pg.error && !pg.url) ? <Failed what="the store" error={pg?.error || 'no answer'} /> : (
                  <>
                    <dl className="setlist">
                      <dt>status</dt><dd>{pg.ok ? <span className={pillCls('good')}>answering</span> : <span className={pillCls('bad')}>down</span>}{pg.error ? <div className="s">{pg.error}</div> : null}</dd>
                      <dt>address</dt><dd><code>{pg.url}</code></dd>
                      {pg.version ? <><dt>version</dt><dd>PostgreSQL {pg.version}</dd></> : null}
                      {pg.bytes != null ? <><dt>size</dt><dd>{bytes(pg.bytes)} in {pg.table_count} tables</dd></> : null}
                      {pg.holds ? <><dt>it holds</dt><dd>{(['ledger', 'library', 'queue'] as const).map((k) => (
                        <span key={k} className={pillCls(pg.holds![k] ? 'good' : '')} title={pg.holds![k] ? `the ${k} is read from the store` : `the ${k} is still read from its file`}>{k}{pg.holds![k] ? '' : ': on file'}</span>
                      ))}</dd></> : null}
                    </dl>
                    {pg.tables?.length ? (
                      <div className="scroll mt">
                        <table data-nosort>
                          <thead><tr><th>the biggest tables</th><th>size</th><th></th><th>rows <span className="s">about</span></th></tr></thead>
                          <tbody>
                            {pg.tables.map((t) => (
                              <tr key={t.name}>
                                <td><code>{t.name}</code></td>
                                <td className="num">{bytes(t.bytes)}</td>
                                <td><Bar value={t.bytes} of={pg.tables![0].bytes || 1} /></td>
                                <td className="num">{t.rows.toLocaleString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </>
                )}
              </section>

              <section className={cardCls(false, 'panel')}>
                <h2>Server and machine <span className="note">the process answering this page, and what it runs on</span></h2>
                {!sv || sv.error ? <Failed what="the server" error={sv?.error || 'no answer'} /> : (
                  <dl className="setlist">
                    <dt>version</dt><dd>thorp {sv.version || '–'}</dd>
                    <dt>commit</dt><dd><code>{sv.commit || '–'}</code> on {sv.branch || '–'}{sv.uncommitted ? <span className="s"> · {sv.uncommitted} file{sv.uncommitted === 1 ? '' : 's'} changed since</span> : null}<div className="s">{sv.commit_subject}{sv.commit_at ? ` · ${new Date(sv.commit_at).toLocaleString()}` : ''}</div></dd>
                    <dt>started</dt><dd>{when(sv.started)} <span className="s">up {span(sv.uptime)} · pid {sv.pid}</span></dd>
                    <dt>dashboard built</dt><dd>{sv.built ? when(sv.built) : <span className="s">not built: <code>pnpm --dir frontend build</code></span>}</dd>
                    <dt>Python</dt><dd>{sv.python} <span className="s"><code>{sv.executable}</code></span></dd>
                    <dt>frameworks</dt><dd>{Object.entries(sv.frameworks).map(([k, v]) => <span key={k} className={pillCls('')} title={v ? '' : 'not installed here'}>{k} {v || '–'}</span>)}</dd>
                    <dt>machine</dt><dd>{sv.chip}<div className="s">{sv.cores ? `${sv.cores} cores · ` : ''}{sv.memory ? `${Math.round(sv.memory / 2 ** 30)} GB memory · ` : ''}{sv.platform}</div></dd>
                    <dt>lanes</dt><dd>{d.lanes?.error ? <span className="s">{d.lanes.error}</span> : (d.lanes?.lanes || []).map((l) => (
                      <div key={l.lane}><b>{l.lane}</b>: {l.seats} seat{l.seats === 1 ? '' : 's'} <span className="s">{l.out ? `· ${l.out} at sea` : '· in port'}</span></div>
                    ))}<div className="s">set on the <a href="/expeditions/queue">queue</a></div></dd>
                  </dl>
                )}
              </section>
            </div>

            <div className="row">
              <section className={cardCls(false, 'panel')}>
                <h2>Switches <span className="note">the environment <code>thorp dash</code> was started with; a dash is the default. Set them where the server is launched (<code>.claude/launch.json</code>, or the shell)</span></h2>
                {!env || env.error ? <Failed what="the environment" error={env?.error || 'no answer'} /> : (
                  <div className="scroll">
                    <table data-nosort>
                      <thead><tr><th>switch</th><th>value</th><th>what it does</th></tr></thead>
                      <tbody>
                        {env.switches.map((s) => (
                          <tr key={s.name} className={s.value == null ? 'setunset' : ''}>
                            <td><code>{s.name}</code></td>
                            <td>{s.value == null ? <span className="s">–</span> : <b>{s.value}</b>}</td>
                            <td className="s">{s.about}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className={cardCls(false, 'panel')}>
                <h2>Keys and places <span className="note">whether each key is present, never its value; and where everything lives</span></h2>
                {env && !env.error ? (
                  <dl className="setlist">
                    {env.keys.map((k) => (
                      <div key={k.name} className="contents">
                        <dt><code>{k.name}</code></dt>
                        <dd><span className={pillCls(k.set ? 'good' : '')}>{k.set ? 'set' : 'not set'}</span><div className="s">{k.about}</div></dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                {Array.isArray(d.paths) ? (
                  <dl className="setlist mt">
                    {d.paths.map((p) => (
                      <div key={p.name} className="contents">
                        <dt>{p.name}</dt>
                        <dd><code>{p.path}</code>{p.exists ? null : <span className={pillCls('accent')}>missing</span>}<div className="s">{p.about}</div></dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                <p className="note mt">The rules a voyage sails under are not here: the policies and their switches are on <a href="/vsm/s5">the VSM, S5</a>, and the standing queue and its seats on <a href="/expeditions/queue">Expeditions, Queue</a>.</p>
              </section>
            </div>
          </>
        )}
    </div>
  );
}
