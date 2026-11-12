// The Vast tab's timing table (/settings/server, 12 November): where a hire's time went, task by task —
// the box coming up, its ssh, the code, the data, the manifest and papers, the torch environment, the
// run, and the bring-home. Parsed by thorp.dash.settings.charters from data/runs/charter.log and joined
// to the spend log by instance; the last row is live, its open phase timed to now. The point of the
// table is the load: a 9 GB data tar beside a 4-minute run (UI.md, "Settings").

import { cardCls, emptyCls, pillCls } from '@/lib/ui';

export type CharterPhase = 'provision' | 'ssh' | 'code' | 'data' | 'board' | 'env' | 'train' | 'home';

export interface Charter {
  name: string;
  instance: number;
  gpu: string;
  dph: number;
  quote_hours: number;
  quote_cost: number;
  started: string;
  status: string;
  total_s: number;
  cost: number;
  rate: number | null;
  phases: Record<CharterPhase, number | null>;
  open: CharterPhase | null;
  note: string | null;
}

export interface Charters {
  error?: string;
  at: string;
  charters: Charter[];
}

const PHASES: { key: CharterPhase; label: string; title: string; about: string; colour: string }[] = [
  { key: 'provision', label: 'provision', title: 'Provision', about: 'the hire to the box being up', colour: 'var(--muted)' },
  { key: 'ssh', label: 'ssh', title: 'SSH', about: 'the box being up to answering ssh', colour: 'var(--track)' },
  { key: 'code', label: 'code', title: 'Code', about: 'the code tar to the box', colour: 'var(--blue)' },
  { key: 'data', label: 'data', title: 'Data', about: 'the data tar: the corpus and shards the run reads', colour: 'var(--accent)' },
  { key: 'board', label: 'board', title: 'Manifest', about: 'the manifest, the spec and the papers', colour: 'var(--c5)' },
  { key: 'env', label: 'env', title: 'Environment', about: 'uv sync --group torch', colour: 'var(--c9)' },
  { key: 'train', label: 'train', title: 'Training', about: 'from "at sea" to the end of the run', colour: 'var(--good)' },
  { key: 'home', label: 'home', title: 'Bring home', about: 'the bring-home and the release', colour: 'var(--track)' },
];

const secs = (v: number | null | undefined): string => {
  if (v == null) return '–';
  const s = Math.max(0, Math.round(v));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} m ${s % 60} s`;
  return `${Math.floor(m / 60)} h ${m % 60} m`;
};
const when = (iso: string | null | undefined): string => {
  if (!iso) return '–';
  const d = new Date(iso);
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};
const money = (v: number): string => `$${v.toFixed(2)}`;
const pillFor = (status: string): string =>
  status === 'released' ? 'good' : status === 'at sea' || status === 'fitting out' ? 'accent' : 'bad';
const liveOf = (c: Charter): boolean => Boolean(c.open) || c.status === 'at sea' || c.status === 'fitting out';
const overOf = (c: Charter): number => Math.max(0, c.total_s - c.quote_hours * 3600);
const phaseOf = (c: Charter, key: CharterPhase): number | null => c.phases[key];

/** The hire running now, at the top of the tab: its task bar, what it is doing and what the hour has cost. */
function LiveHire({ c }: { c: Charter }) {
  const open = PHASES.find((p) => p.key === c.open);
  const over = overOf(c);
  return (
    <section className={cardCls(false, 'panel vastnow')}>
      <div className="vastnowhead">
        <div className="vastnowid">
          <h2>The ship out <span className="note">the hire running now: what it is doing, how long it has taken, and where the hour has gone</span></h2>
          <div className="vastnowname"><b>{c.name}</b> <span className={pillCls(pillFor(c.status))}>{c.status}</span></div>
          <div className="s">{c.gpu} · ${c.dph.toFixed(3)}/h · instance {c.instance} · hired {when(c.started)}</div>
        </div>
        <div className="vastnowstats">
          <div className="stat">
            <div className="k">elapsed</div>
            <div className="v">{secs(c.total_s)}</div>
            <div className="s">{over > 0 ? <span className="over">{secs(over)} over</span> : `of ${c.quote_hours.toFixed(2)} h quote`}</div>
          </div>
          <div className="stat">
            <div className="k">now</div>
            <div className="v">{open ? open.title : '–'}</div>
            <div className="s">{open ? secs(phaseOf(c, open.key)) : '–'}</div>
          </div>
          <div className="stat">
            <div className="k">spent</div>
            <div className="v">{money(c.cost)}</div>
            <div className="s">of {money(c.quote_cost)} quoted</div>
          </div>
        </div>
      </div>
      <div className="phasebar big" aria-hidden="true">
        {PHASES.map((p) => {
          const v = phaseOf(c, p.key);
          return v ? <i key={p.key} style={{ width: `${(100 * v) / Math.max(1, c.total_s)}%`, background: p.colour }} /> : null;
        })}
      </div>
      <div className="phaselegend">
        {PHASES.map((p) => {
          const v = phaseOf(c, p.key);
          return v ? (
            <span key={p.key} className={c.open === p.key ? 'now' : ''}>
              <i style={{ background: p.colour }} />{p.title} <b>{secs(v)}</b>
            </span>
          ) : null;
        })}
      </div>
    </section>
  );
}

/** The colour key, for the row bars below. */
function Legend() {
  return (
    <div className="phaselegend">
      {PHASES.map((p) => <span key={p.key}><i style={{ background: p.colour }} />{p.title}</span>)}
    </div>
  );
}

export function VastTimings({ data }: { data: Charters }) {
  if (data.error) return <section className={cardCls(false, 'panel')}><h2>Where the time goes</h2><div className={emptyCls()}>the hires&apos; timings could not be read: {data.error}</div></section>;
  const rows = data.charters || [];
  const live = rows.find((c) => liveOf(c));
  return (
    <>
      {live ? <LiveHire c={live} /> : null}
      <section className={cardCls(false, 'panel')}>
        <h2>Where the time goes <span className="note">every recent hire from the charter&apos;s own log, task by task, so the expensive step is named. A bar is each task&apos;s share of the hire; the live hire&apos;s open task is bold and timed to now</span></h2>
        {rows.length === 0 ? <div className={emptyCls()}>no hire has reached a box yet: the first charter writes its steps here</div> : (
          <>
            <div className="vasttabletop"><Legend /><span className="s">parsed from <code>data/runs/charter.log</code>, joined to the spend log by instance</span></div>
            <div className="scroll mt">
              <table id="vasttimings" data-nosort>
                <colgroup>
                  <col style={{ width: '23%' }} />
                  {PHASES.map((p) => <col key={p.key} style={{ width: '6.5%' }} />)}
                  <col style={{ width: '8%' }} /><col style={{ width: '6%' }} /><col style={{ width: '8%' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th rowSpan={2} scope="col">voyage</th>
                    <th colSpan={6} scope="colgroup" className="grp">fit-out</th>
                    <th colSpan={2} scope="colgroup" className="grp sep">the run</th>
                    <th rowSpan={2} scope="col" className="sep">total</th>
                    <th rowSpan={2} scope="col">cost</th>
                    <th rowSpan={2} scope="col">rate</th>
                  </tr>
                  <tr>
                    {PHASES.map((p) => <th key={p.key} scope="col" className={p.key === 'train' ? 'sep' : ''} title={p.about}>{p.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => {
                    const over = overOf(c);
                    const isLive = liveOf(c);
                    return (
                      <tr key={`${c.instance}-${c.started}`} className={isLive ? 'now' : ''}>
                        <td className="who">
                          <div className="whoname"><b>{c.name}</b> <span className={pillCls(pillFor(c.status))}>{c.status}</span></div>
                          <div className="s">{c.gpu} · ${c.dph.toFixed(3)}/h · {when(c.started)}</div>
                          <div className="s">quoted {c.quote_hours.toFixed(2)} h · {money(c.quote_cost)}{c.note ? ` · ${c.note}` : ''}</div>
                          <div className="phasebar" aria-hidden="true">
                            {PHASES.map((p) => {
                              const v = phaseOf(c, p.key);
                              return v ? <i key={p.key} style={{ width: `${(100 * v) / Math.max(1, c.total_s)}%`, background: p.colour }} /> : null;
                            })}
                          </div>
                        </td>
                        {PHASES.map((p) => (
                          <td key={p.key} className={`num${c.open === p.key ? ' open' : ''}${p.key === 'train' ? ' sep' : ''}`} title={p.about}>
                            {phaseOf(c, p.key) == null ? <span className="s">–</span> : c.open === p.key ? <b>{secs(phaseOf(c, p.key))}</b> : secs(phaseOf(c, p.key))}
                          </td>
                        ))}
                        <td className={`num sep${over > 0 ? ' over' : ''}`}>
                          {secs(c.total_s)}
                          <div className="s">{over > 0 ? `+${secs(over)} over` : `of ${c.quote_hours.toFixed(2)} h`}</div>
                        </td>
                        <td className="num">{money(c.cost)}</td>
                        <td className="num">{c.rate != null ? `${Math.round(c.rate / 1000).toLocaleString()}k/s` : <span className="s">–</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
        <p className="note mt">A phase with a dash was never reached (or the log does not say). <b>Data</b> is the tar or rsync of the corpus and shards; <b>Manifest</b> is the manifest, the spec and the papers; <b>Environment</b> is <code>uv sync --group torch</code>. A red total is a hire over its quote. As of {when(data.at)}.</p>
      </section>
    </>
  );
}
