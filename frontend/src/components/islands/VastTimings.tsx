// The Vast tab's timing table (/settings/server): where a hire's time went, as three categories — setup,
// training and home. Setup is every phase before the run (provision, ssh, code, data, manifest, environment);
// training is the only phase that uses the GPU; home pulls the checkpoints and logs onto this Mac and releases
// the box, so it is billed on Vast but spends this Mac's network and disk. Parsed by
// thorp.dash.settings.charters from data/runs/charter.log and joined to the spend log by instance; the last
// row is live, its open phase timed to now. The point of the table is the load: a 9 GB setup beside a 4-minute
// run (UI.md, "Settings").

import type { ReactNode } from 'react';
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

/** The tasks under setup, in the order they run; the table names the heaviest and keeps the rest in a tooltip. */
const SETUP_KEYS: CharterPhase[] = ['provision', 'ssh', 'code', 'data', 'board', 'env'];

const PHASES: { key: CharterPhase; title: string; about: string }[] = [
  { key: 'provision', title: 'Provision', about: 'the hire to the box being up' },
  { key: 'ssh', title: 'SSH', about: 'the box being up to answering ssh' },
  { key: 'code', title: 'Code', about: 'the code tar to the box' },
  { key: 'data', title: 'Data', about: 'the data tar: the corpus and shards the run reads' },
  { key: 'board', title: 'Manifest', about: 'the manifest, the spec and the papers' },
  { key: 'env', title: 'Environment', about: 'uv sync --group torch' },
  { key: 'train', title: 'Training', about: 'from "at sea" to the end of the run' },
  { key: 'home', title: 'Home', about: 'the checkpoints and logs pulled onto this Mac, then the release' },
];

type CatKey = 'setup' | 'train' | 'home';
const CATEGORIES: { key: CatKey; title: string; colour: string; about: string }[] = [
  { key: 'setup', title: 'Setup', colour: 'var(--blue)', about: 'everything before the run: provision, ssh, code, data, manifest and the torch environment' },
  { key: 'train', title: 'Training', colour: 'var(--good)', about: 'the run itself: the only part that uses the GPU' },
  { key: 'home', title: 'Home', colour: 'var(--accent)', about: 'the checkpoint and log pull onto this Mac, then the release' },
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
const setupOf = (c: Charter): number => SETUP_KEYS.reduce((n, k) => n + (c.phases[k] || 0), 0);
const catValue = (c: Charter, key: CatKey): number =>
  key === 'setup' ? setupOf(c) : c.phases[key] || 0;
const catOfPhase = (k: CharterPhase): CatKey => (k === 'train' ? 'train' : k === 'home' ? 'home' : 'setup');
const titleOf = (k: CharterPhase): string => PHASES.find((p) => p.key === k)?.title ?? k;
const setupParts = (c: Charter) =>
  SETUP_KEYS.map((k) => ({ key: k, v: c.phases[k] || 0 })).filter((x) => x.v > 0).sort((a, b) => b.v - a.v);
const setupTitle = (c: Charter): string =>
  setupParts(c).map((x) => `${titleOf(x.key)} ${secs(x.v)}`).join(' · ') || 'nothing reached';

function CatBar({ c, big = false }: { c: Charter; big?: boolean }) {
  return (
    <div className={`phasebar${big ? ' big' : ''}`} aria-hidden="true">
      {CATEGORIES.map((cat) => {
        const v = catValue(c, cat.key);
        return v ? <i key={cat.key} style={{ width: `${(100 * v) / Math.max(1, c.total_s)}%`, background: cat.colour }} /> : null;
      })}
    </div>
  );
}

function Legend({ c, values = false }: { c?: Charter; values?: boolean }) {
  return (
    <div className="phaselegend">
      {CATEGORIES.map((cat) => {
        const v = c ? catValue(c, cat.key) : null;
        const current = Boolean(c?.open && catOfPhase(c.open) === cat.key);
        return (
          <span key={cat.key} className={current ? 'now' : ''} title={cat.about}>
            <i style={{ background: cat.colour }} />{cat.title}
            {values && v ? <> <b>{secs(v)}</b></> : null}
          </span>
        );
      })}
    </div>
  );
}

/** The hire running now: what it is doing, how long it has taken, and where the hour has gone. */
function LiveHire({ c }: { c: Charter }) {
  const open = PHASES.find((p) => p.key === c.open);
  const over = overOf(c);
  return (
    <section className={cardCls(false, 'panel vastnow')}>
      <div className="vastnowhead">
        <div className="vastnowid">
          <h2>The ship out <span className="note">the hire running now: what it is doing, how long it has taken, and where the hour has gone — setup, training and home</span></h2>
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
            <div className="s">{open ? `${secs(phaseOf(c, open.key))} · ${catOfPhase(open.key) === 'setup' ? 'setup' : catOfPhase(open.key)}` : '–'}</div>
          </div>
          <div className="stat">
            <div className="k">spent</div>
            <div className="v">{money(c.cost)}</div>
            <div className="s">of {money(c.quote_cost)} quoted</div>
          </div>
        </div>
      </div>
      <CatBar c={c} big />
      <Legend c={c} values />
    </section>
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
        <h2>Where the time goes <span className="note">every recent hire from the charter&apos;s own log, in three parts: <b>setup</b> (everything before the run), <b>training</b> (the only part that uses the GPU) and <b>home</b> (the pull onto this Mac and the release). The heaviest setup task is named under its figure; hover for the rest. The last hire is timed to now</span></h2>
        {rows.length === 0 ? <div className={emptyCls()}>no hire has reached a box yet: the first charter writes its steps here</div> : (
          <>
            <div className="vasttabletop"><Legend /><span className="s">parsed from <code>data/runs/charter.log</code>, joined to the spend log by instance</span></div>
            <div className="scroll mt">
              <table id="vasttimings" data-nosort>
                <colgroup>
                  <col style={{ width: '27%' }} /><col style={{ width: '17%' }} /><col style={{ width: '13%' }} />
                  <col style={{ width: '12%' }} /><col style={{ width: '12%' }} /><col style={{ width: '8%' }} />
                  <col style={{ width: '8%' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">voyage</th>
                    {CATEGORIES.map((cat) => (
                      <th key={cat.key} scope="col" className={cat.key === 'setup' ? '' : 'sep'} title={cat.about}>{cat.title}</th>
                    ))}
                    <th scope="col">total</th>
                    <th scope="col">cost</th>
                    <th scope="col">rate</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => {
                    const over = overOf(c);
                    const isLive = liveOf(c);
                    const openCat = c.open ? catOfPhase(c.open) : null;
                    const setup = Math.min(setupOf(c), c.total_s);
                    const train = c.phases.train || 0;
                    const home = c.phases.home || 0;
                    const parts = setupParts(c);
                    const duty = c.total_s ? Math.round((100 * train) / c.total_s) : 0;
                    const catCell = (key: CatKey, value: number, sub?: ReactNode) => (
                      <td className={`num${key === 'setup' ? '' : ' sep'}${openCat === key ? ' open' : ''}`}
                        title={key === 'setup' ? setupTitle(c) : CATEGORIES.find((x) => x.key === key)?.about}>
                        {value ? (openCat === key ? <b>{secs(value)}</b> : secs(value)) : <span className="s">–</span>}
                        {value && sub ? <div className="s">{sub}</div> : null}
                      </td>
                    );
                    return (
                      <tr key={`${c.instance}-${c.started}`} className={isLive ? 'now' : ''}>
                        <td className="who">
                          <div className="whoname"><b>{c.name}</b> <span className={pillCls(pillFor(c.status))}>{c.status}</span></div>
                          <div className="s">{c.gpu} · ${c.dph.toFixed(3)}/h · {when(c.started)}</div>
                          <div className="s">quoted {c.quote_hours.toFixed(2)} h · {money(c.quote_cost)}{c.note ? ` · ${c.note}` : ''}</div>
                          <CatBar c={c} />
                        </td>
                        {catCell('setup', setup, parts.slice(0, 1).map((x) => `${titleOf(x.key)} ${secs(x.v)}`).join(''))}
                        {catCell('train', train, train ? `${duty}% duty` : undefined)}
                        {catCell('home', home, home ? 'onto this Mac' : undefined)}
                        <td className={`num${over > 0 ? ' over' : ''}`}>
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
        <p className="note mt"><b>Setup</b> is provision, ssh, the code tar, the data tar, the manifest and the torch environment; the heaviest is named under its figure, the rest in its tooltip. <b>Training</b> is the only category that uses the GPU, so its share of the hire is the duty cycle. <b>Home</b> is pulled onto this Mac — it is billed on the box but spends this Mac&apos;s network and disk, so it competes with the Mac lane. A red total is a hire over its quote. As of {when(data.at)}.</p>
      </section>
    </>
  );
}
