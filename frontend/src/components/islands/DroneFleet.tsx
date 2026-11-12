// The drone fleet under S1 operations (12 November, Justin: "under Liberty Machine S1 Operations we have a fleet of
// drones. The first drone in the fleet will be the browser drone"). The card is drawn as the Liberty Machine's five
// cards are (LibertyMachineCards.tsx): a fal plate, a number, a name and the job. The drone's own page is the pilot
// list — which model it flies — and the launch form; the run it is flying, its screenshots and its step
// log are read from the same /api/drones payload the chat tool writes.
//
// The data layer is thorp/drones.py; the art is 'drone-browser' in dash/art/generate_art.py.

import { useEffect, useState } from 'react';
import { artSrc } from '@/scripts/views/helpers';
import { EmailAccounts } from './EmailAccounts';
import { LiveVoice } from './LiveVoice';
import { useApi } from '@/lib/useApi';
import { btnCls, cardCls, emptyCls, pillCls } from '@/lib/ui';

interface Download {
  model: string;
  state: 'queued' | 'downloading' | 'ready' | 'error';
  error?: string | null;
}

interface Pilot {
  key: string;
  label: string;
  source: string;
  params_b: number;
  harness: 'fara' | 'generic' | 'text';
  note: string;
  recommended: boolean;
  experimental: boolean;
  installed: boolean;
  size_gb: number;
  download?: Download | null;
}

interface Step {
  n: number;
  thought: string;
  action: string;
  args: Record<string, unknown>;
  ok: boolean;
  note: string;
}

interface Run {
  id: string;
  state: 'queued' | 'running' | 'done' | 'needs_user' | 'error' | 'stopped';
  goal: string;
  url?: string | null;
  model_label: string;
  steps: number;
  max_steps: number;
  started: string;
  finished?: string | null;
  answer?: string | null;
  error?: string | null;
  question?: string | null;
  thought?: string | null;
  shot?: string | null;
  profile?: 'fresh' | 'signed-in';
  log: Step[];
}

interface Bridge {
  configured: boolean;
  mode?: string;
  options: string[];
  voice?: string[];
  safety?: string[];
}

interface FleetDrone {
  key: string;
  label: string;
  name: string;
  purpose: string;
  art: string;
  kind: 'browser' | 'email' | 'phone';
  selected_label: string;
  busy: boolean;
  latest: Run | null;
  runs: number;
  bridge?: Bridge | null;
}

interface Fleet {
  drones: FleetDrone[];
}

interface PhoneTurn {
  role: 'drone' | 'person';
  text: string;
  at: string;
}

interface PhoneCall {
  id: string;
  state: 'open' | 'thinking' | 'done' | 'error';
  goal: string;
  pilot_label: string;
  started: string;
  finished?: string | null;
  error?: string | null;
  transcript: PhoneTurn[];
  speak?: boolean;
}

interface BrowserSite {
  key: string;
  label: string;
  mark: string;
  tone: string;
  url: string;
  goal: string;
  needs_login: boolean;
  hint: string;
  state?: { signed_in: boolean | null; checked: string; url?: string; title?: string; note?: string } | null;
}

interface BrowserSites {
  chrome_running: boolean;
  profile: string;
  port: number;
  sites: BrowserSite[];
}

interface PhoneState {
  active: PhoneCall | null;
  calls: PhoneCall[];
  bridge: Bridge;
  tts: boolean;
  pilot_ready: boolean;
}

interface Payload {
  drone: { key: string; label: string; name: string; purpose: string; art: string; kind: 'browser' | 'email' | 'phone' };
  bridge?: Bridge | null;
  models: Pilot[];
  selected: string;
  selected_label: string;
  runs: Run[];
  latest: Run | null;
  not_flyable: { label: string; why: string }[];
  busy: boolean;
  server: { running: boolean; port?: number | null };
  phone?: PhoneState | null;
}

const RUN_TONE: Record<string, string> = {
  done: 'good', running: 'running', queued: 'blue', needs_user: 'accent', error: 'bad', stopped: 'bad',
};
const RUN_WORD: Record<string, string> = {
  done: 'landed', running: 'flying', queued: 'waiting', needs_user: 'needs you', error: 'crashed', stopped: 'stopped',
};

const ago = (at?: string | null): string => {
  if (!at) return '';
  const s = Math.max(0, (Date.now() - new Date(at).getTime()) / 1000);
  if (s < 90) return `${Math.round(s)}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
};

const post = async (url: string, body: unknown): Promise<any> => {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await resJson(r);
  if (!r.ok) throw new Error(j?.error || `${r.status} ${r.statusText}`);
  return j;
};

const resJson = async (r: Response): Promise<any> => {
  try { return await r.json(); } catch { return null; }
};

/** The fleet, on S1's page: one card per drone, under the band. */
export function S1Drones() {
  const { data, error } = useApi<Fleet>('/api/drones/fleet', 8000);
  if (error) return <div className={emptyCls()}>the fleet could not be read: {error}</div>;
  if (!data) return <div className={emptyCls()}>reading the fleet…</div>;
  const flying = data.drones.some((d) => d.busy);
  const runs = data.drones.reduce((n, d) => n + d.runs, 0);
  return (
    <section className="dronefleet" aria-label="The fleet">
      <div className="dronefleethead">
        <h2>The fleet <span className="q">the workers under S1 operations, each a machine that does one job on demand</span></h2>
        <span className="s">{data.drones.length} drone(s) · {runs} run(s) on record · {flying ? 'a drone is flying now' : 'all drones at rest'}</span>
      </div>
      <nav className="harbours shipyardgrid demitonyard fleet libertymachinecards">
        {data.drones.map((d) => {
          const waiting = d.kind !== 'browser' && !d.bridge?.configured;
          const tone = d.busy ? 'running' : waiting ? 'accent' : '';
          const state = d.busy
            ? (d.kind === 'phone' ? 'on a call' : 'flying')
            : waiting
              ? 'no mailbox'
              : d.kind === 'phone'
                ? 'local test'
                : 'at rest';
          const latest = d.latest;
          return (
            <a key={d.key} className={cardCls(true, 'card harbourcard shipyardcard dronecard')} href={`/orbitals/demiton/liberty-machine/operations/${d.key}`}>
              <img className="cardart ship" src={artSrc(d.art)} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} />
              <div className="yardplate">
                <span className="yardnum">{d.label}</span>
                <span className="yardrule" aria-hidden="true" />
                <span className="nm">{d.name}</span>
                <span className="job">{d.purpose}</span>
                <span className="dronecardline">
                  <span className={pillCls(tone)}>{state}</span>
                  <span className="s">flies <b>{d.selected_label}</b></span>
                  {latest ? <span className="s">last {RUN_WORD[latest.state] || latest.state} {ago(latest.finished || latest.started)}</span> : null}
                </span>
                <span className="yardopen">open {d.label} {d.name.toLowerCase()} →</span>
              </div>
            </a>
          );
        })}
      </nav>
    </section>
  );
}

/** The mail or phone bridge: what is chosen, what it needs, and the terms. */
function BridgePanel({ bridge, isEmail, waiting }: { bridge?: Bridge | null; isEmail: boolean; waiting: boolean }) {
  const local = bridge?.mode === 'local';
  return (
    <section className={cardCls(false, 'panel dronemailbridge')}>
      <h2>{isEmail ? 'Mail bridge' : 'Phone bridge'}</h2>
      <p className="s">{isEmail
        ? 'The email drone has a pilot; it does not yet have a way into a mailbox. The transport is your choice, so the drone says the three ways rather than assuming one.'
        : 'The phone drone is on the local test line: you play the person, the pilot thinks, and macOS say speaks. No carrier, no number, no microphone yet.'}</p>
      <p><span className={pillCls(waiting ? 'accent' : 'good')}>{bridge?.configured ? (local ? 'local test line' : 'configured') : 'not configured'}</span></p>
      <ol className="dronemailoptions">
        {(bridge?.options || []).map((x) => <li key={x}>{x}</li>)}
      </ol>
      {bridge?.voice?.length ? (
        <>
          <h3 className="dronesub">Voice stack</h3>
          <ul className="dronemailoptions">{bridge.voice.map((x) => <li key={x}>{x}</li>)}</ul>
        </>
      ) : null}
      {bridge?.safety?.length ? (
        <>
          <h3 className="dronesub">Safety</h3>
          <ul className="dronemailoptions">{bridge.safety.map((x) => <li key={x}>{x}</li>)}</ul>
        </>
      ) : null}
      <p className="s">{isEmail
        ? 'Drafting can be added before sending; sending stays off until an account is in data/email.json.'
        : local
          ? 'Every turn is spoken aloud and kept as text. A real line comes later, behind the same safety terms.'
          : 'The line stays silent until one of the three is chosen.'}</p>
    </section>
  );
}

/** The four sites the browser drone is tested against, and the signed-in profile they need. */
function TestSites({ data, busy, onSignIn, onCheck, onRun, onOpenChrome }: {
  data: BrowserSites | null;
  busy: boolean;
  onSignIn: (site: string) => void;
  onCheck: (site: string) => void;
  onRun: (site: BrowserSite) => void;
  onOpenChrome: () => void;
}) {
  if (!data) return <div className={emptyCls()}>reading the test sites…</div>;
  return (
    <section className={cardCls(false, 'panel browsersites')}>
      <div className="browsersiteshead">
        <div>
          <h2>Test sites</h2>
          <p className="s">LinkedIn, X and Google Analytics need your own session. Sign in once in the
            dedicated Chrome profile, then the drone acts inside it — in a window you can watch.</p>
        </div>
        <div className="browsersiteschrome">
          <span className={pillCls(data.chrome_running ? 'good' : '')}>{data.chrome_running ? 'Chrome open' : 'Chrome closed'}</span>
          <button className={btnCls('ghost')} disabled={busy} onClick={onOpenChrome}>open signed-in Chrome</button>
        </div>
      </div>
      <div className="sitegrid">
        {data.sites.map((site) => {
          const verdict = site.state?.signed_in;
          const tone = verdict === true ? 'good' : verdict === false ? 'bad' : 'accent';
          const word = verdict === true ? 'signed in' : verdict === false ? 'sign in' : 'not checked';
          return (
            <div key={site.key} className={`sitecard ${site.tone}`}>
              <div className="sitehead">
                <span className={`sitemark ${site.tone}`}>{site.mark}</span>
                <b>{site.label}</b>
                <span className={pillCls(tone)}>{word}</span>
              </div>
              <p className="s">{site.hint}</p>
              {site.state?.note ? <p className="s sitenote">{site.state.note}</p> : null}
              {site.state?.checked ? <p className="s">checked {ago(site.state.checked)}</p> : null}
              <div className="siteactions">
                {site.needs_login ? (
                  <button className={btnCls('outline')} disabled={busy} onClick={() => onSignIn(site.key)}>open sign-in</button>
                ) : null}
                <button className={btnCls('ghost')} disabled={busy} onClick={() => onCheck(site.key)}>check</button>
                <button className={btnCls('default')} disabled={busy} onClick={() => onRun(site)}>run test</button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** The browser drone's own page: the pilot it flies, the task it is given, and the run as it happens. */
export function DronePage({ drone = 'browser' }: { drone?: string }) {
  const [tick, setTick] = useState(0);
  const [sitesTick, setSitesTick] = useState(0);
  const [signedIn, setSignedIn] = useState(true);
  const { data, error } = useApi<Payload>(`/api/drones?drone=${drone}&t=${tick}`, 3500);
  const sitesApi = useApi<BrowserSites>(drone === 'browser' ? `/api/drones/browser/sites?t=${sitesTick}` : null, 8000);
  const [picked, setPicked] = useState<string | null>(null);
  const [goal, setGoal] = useState('');
  const [url, setUrl] = useState('');
  const [steps, setSteps] = useState(15);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [show, setShow] = useState<string | null>(null);
  const [agenda, setAgenda] = useState('');
  const [line, setLine] = useState('');
  const [fresh, setFresh] = useState(false);

  useEffect(() => {
    if (data && picked === null) setPicked(data.selected);
  }, [data, picked]);

  if (error) return <div className={emptyCls()}>the drone could not be read: {error}</div>;
  if (!data) return <div className={emptyCls()}>reading the drone…</div>;

  const d = data.drone;
  const selected = picked || data.selected;
  const chosen = data.models.find((m) => m.key === selected);
  const latest = data.latest;
  const shown = data.runs.find((r) => r.id === show) || latest;
  const isEmail = d.kind === 'email';
  const isPhone = d.kind === 'phone';
  const bridge = data.bridge;
  const phone = data.phone;
  const phoneCall = fresh ? null : (phone?.active ?? (phone?.calls?.length ? phone.calls[0] : null));
  const flying = d.kind === 'browser' && (data.busy || data.runs.some((r) => r.state === 'running' || r.state === 'queued'));
  const waiting = (isEmail || isPhone) && !bridge?.configured;

  const act = async (fn: () => Promise<any>) => {
    setBusy(true); setMsg(null);
    try { await fn(); } catch (e) { setMsg(String((e as Error)?.message ?? e)); } finally { setBusy(false); }
  };

  const launch = () => act(async () => {
    if (!goal.trim()) throw new Error('give the drone a goal first');
    const r = await post('/api/drones/task', {
      goal, url: url.trim() || undefined, model: selected, max_steps: steps,
      profile: signedIn ? 'signed-in' : 'fresh',
    });
    setShow(r.run?.id || null);
  });

  const startCall = () => act(async () => {
    if (!agenda.trim()) throw new Error('say what the call is for');
    await post('/api/drones/phone/start', { goal: agenda.trim(), pilot: selected, speak: true });
    setAgenda(''); setLine(''); setFresh(false); setTick((n) => n + 1);
  });

  const sendLine = () => act(async () => {
    if (!phoneCall || !line.trim()) return;
    await post('/api/drones/phone/turn', { id: phoneCall.id, text: line.trim() });
    setLine(''); setTick((n) => n + 1);
  });

  const signIn = (site: string) => act(async () => {
    await post('/api/drones/browser/signin', { site });
    setSitesTick((n) => n + 1);
  });

  const checkSite = (site: string) => act(async () => {
    const r = await post('/api/drones/browser/check', { site });
    setMsg(`${r.title || site}: ${r.note || (r.signed_in ? 'signed in' : 'not signed in')}`);
    setSitesTick((n) => n + 1);
  });

  const runSite = (site: BrowserSite) => act(async () => {
    const r = await post('/api/drones/task', {
      goal: site.goal, url: site.url, model: selected, max_steps: 20, profile: 'signed-in',
    });
    setShow(r.run?.id || null);
    setTick((n) => n + 1);
  });

  const hangup = () => act(async () => {
    if (!phoneCall) return;
    await post('/api/drones/phone/end', { id: phoneCall.id });
    setTick((n) => n + 1);
  });

  return (
    <div className="dronepage">
      <p className="s"><a href="/orbitals/demiton/liberty-machine/operations">← S1 Operations</a></p>
      <h1>{d.label} {d.name}</h1>
      <p className="s dronepurpose">{d.purpose}</p>

      <div className="dronepagebar">
        <span className={pillCls(flying ? 'running' : waiting ? 'accent' : isPhone && data.phone?.active ? 'running' : '')}>{flying ? 'flying' : waiting ? 'no mailbox' : isPhone ? (data.phone?.active ? 'on a call' : 'local test line') : 'at rest'}</span>
        <span className="s">flies <b>{data.selected_label}</b></span>
        {d.kind === 'browser' && data.server.running ? <span className="s mono">llama.cpp :{data.server.port}</span> : null}
        {msg ? <span className={pillCls('bad')}>{msg}</span> : null}
      </div>

      {isEmail ? <EmailAccounts /> : null}
      {isPhone ? <LiveVoice /> : null}
      {d.kind === 'browser' ? (
        <TestSites
          data={sitesApi.data}
          busy={busy}
          onSignIn={(x) => void signIn(x)}
          onCheck={(x) => void checkSite(x)}
          onRun={(x) => void runSite(x)}
          onOpenChrome={() => void signIn('search')}
        />
      ) : null}

      <div className="dronegrid">
        <section className={cardCls(false, 'panel dronemodels')}>
          <h2>Pilot <span className="q">which model flies this drone</span></h2>
          <p className="s">{isEmail
            ? 'A pilot is a text GGUF on the Hub, run by llama.cpp on this Mac. Only a downloaded pilot can be chosen.'
            : isPhone
              ? 'A pilot is a text GGUF on the Hub, run by llama.cpp on this Mac: it thinks while the voice stack listens and speaks. Only a downloaded pilot can be chosen.'
              : 'A pilot is a GGUF on the Hub and its vision projector, run by llama.cpp on this Mac. Only a downloaded pilot can be chosen.'}</p>
          <div className="dronemodelrows">
            {data.models.map((m) => {
              const on = m.key === selected;
              const dl = m.download?.state;
              return (
                <div key={m.key} className={`dronemodel${on ? ' on' : ''}`}>
                  <input
                    type="radio"
                    name="pilot"
                    checked={on}
                    disabled={!m.installed || busy}
                    onChange={() => { setPicked(m.key); void act(async () => { await post('/api/drones/select', { drone: d.key, model: m.key }); }); }}
                    aria-label={`fly ${m.label}`}
                  />
                  <div className="dronemodelbody">
                    <div className="dronemodelhead">
                      <b>{m.label}</b>
                      <span className={pillCls('')}>{m.params_b}B</span>
                      {m.recommended ? <span className={pillCls('good')}>recommended</span> : null}
                      {m.experimental ? <span className={pillCls('accent')}>experimental</span> : null}
                      {m.installed ? <span className={pillCls('blue')}>{m.size_gb} GB on disk</span> : <span className={pillCls('')}>not downloaded</span>}
                    </div>
                    <p className="s">{m.note}</p>
                    <p className="s mono dronemodelsrc">{m.source} · {m.harness === 'fara' ? 'Fara harness' : m.harness === 'text' ? 'text pilot' : 'generic harness'}</p>
                  </div>
                  {!m.installed ? (
                    <button
                      className={btnCls('outline')}
                      disabled={busy || dl === 'queued' || dl === 'downloading'}
                      onClick={() => void act(async () => { await post('/api/drones/download', { model: m.key }); })}
                    >
                      {dl === 'queued' || dl === 'downloading' ? 'downloading…' : dl === 'error' ? 'retry download' : 'download'}
                    </button>
                  ) : null}
                  {dl === 'error' ? <span className={pillCls('bad')} title={m.download?.error || ''}>download failed</span> : null}
                </div>
              );
            })}
          </div>
          {d.kind === 'browser' ? (
            <p className="s dronenotflyable">
              Not in the fleet: {data.not_flyable.map((x) => <span key={x.label}><b>{x.label}</b> — {x.why}. </span>)}
            </p>
          ) : null}
        </section>

        {isEmail ? (
          <section className={cardCls(false, 'panel dronemailbehaviour')}>
            <h2>What the drone does</h2>
            <p className="s">The email drone reads the connected mailbox, drafts a reply in the thread's own
              voice, and never sends without you. Drafting comes first; sending is a switch you turn on.</p>
            <ul className="dronemailoptions">
              <li>one mailbox at a time, chosen above</li>
              <li>every mailbox is tested against IMAP and SMTP before it is trusted</li>
              <li>passwords and tokens stay on this Mac; the page never reads them back</li>
              <li>the pilot writes, the mailbox carries it</li>
            </ul>
          </section>
        ) : isPhone ? (
          <section className={cardCls(false, 'panel dronephonecall')}>
            <h2>Test call <span className="q">local line: no number is dialled</span></h2>
            {phoneCall ? (
              <>
                <div className="dronepagebar">
                  <span className={pillCls(phoneCall.state === 'error' ? 'bad' : phoneCall.state === 'done' ? 'good' : 'running')}>
                    {phoneCall.state === 'open' ? 'on the line'
                      : phoneCall.state === 'thinking' || busy ? 'thinking…'
                        : phoneCall.state === 'done' ? 'call ended' : 'call failed'}
                  </span>
                  <span className="s">{phoneCall.pilot_label} · {phoneCall.transcript.length} turn(s)</span>
                  {phone?.tts ? <span className={pillCls('blue')}>spoken aloud</span> : <span className={pillCls('accent')}>silent: no say</span>}
                </div>
                <div className="dronetranscript">
                  {phoneCall.transcript.map((t, i) => (
                    <div key={i} className={`droneturn ${t.role}`}>
                      <span className="dronerole">{t.role === 'drone' ? 'drone' : 'person'}</span>
                      <p>{t.text}</p>
                    </div>
                  ))}
                </div>
                {phoneCall.error ? <p className={pillCls('bad')}>{phoneCall.error}</p> : null}
                {phoneCall.state === 'open' || phoneCall.state === 'thinking' ? (
                  <>
                    <div className="droneturnform">
                      <input
                        className="dronetext"
                        value={line}
                        placeholder="what the person says…"
                        onChange={(e) => setLine(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') void sendLine(); }}
                        disabled={busy || phoneCall.state === 'thinking'}
                      />
                      <button className={btnCls('default')} disabled={busy || phoneCall.state === 'thinking' || !line.trim()} onClick={() => void sendLine()}>
                        say it
                      </button>
                    </div>
                    <div className="dronelaunchrow">
                      <button className={btnCls('ghost')} disabled={busy} onClick={() => void hangup()}>hang up</button>
                    </div>
                  </>
                ) : (
                  <button className={btnCls('outline')} onClick={() => { setFresh(true); setLine(''); }}>start another call</button>
                )}
                <p className="s">Local test line: you are the person. The drone speaks through macOS say; no carrier and no number.</p>
              </>
            ) : (
              <>
                <label className="dronelabel" htmlFor="phone-goal">what is the call for?</label>
                <textarea
                  id="phone-goal"
                  className="dronetext"
                  rows={4}
                  value={agenda}
                  placeholder="Ask the supplier whether the oak boards are ready, and when they ship."
                  onChange={(e) => setAgenda(e.target.value)}
                />
                <div className="dronelaunchrow">
                  <button className={btnCls('default')} disabled={busy || !chosen?.installed} onClick={() => void startCall()}>
                    start the test call
                  </button>
                </div>
                <p className="s">{chosen?.installed
                  ? 'No number: this is a local test line. The drone says it is an AI, every turn is spoken aloud, and the transcript is kept.'
                  : 'Download a text pilot first; the pilot thinks while the voice stack listens and speaks.'}</p>
              </>
            )}
          </section>
        ) : (
          <section className={cardCls(false, 'panel dronelaunch')}>
            <h2>Give it a task</h2>
            <label className="dronelabel" htmlFor="drone-goal">the goal, in words</label>
            <textarea
              id="drone-goal"
              className="dronetext"
              rows={4}
              value={goal}
              placeholder="Find the cheapest paperback of Moby Dick on a bookshop site and tell me the price."
              onChange={(e) => setGoal(e.target.value)}
            />
            <label className="dronelabel" htmlFor="drone-url">start on (optional)</label>
            <input id="drone-url" className="dronetext" value={url} placeholder="https://example.com" onChange={(e) => setUrl(e.target.value)} />
            <div className="dronelaunchrow">
              <label className="dronelabel" htmlFor="drone-steps">steps</label>
              <input
                id="drone-steps"
                type="number"
                min={1}
                max={30}
                value={steps}
                onChange={(e) => setSteps(Math.max(1, Math.min(30, Number(e.target.value) || 15)))}
                className="dronesteps"
              />
              <button className={btnCls('default')} disabled={busy || flying || !chosen?.installed} onClick={() => void launch()}>
                {flying ? 'a task is flying…' : 'launch the drone'}
              </button>
            </div>
            <label className="mailcheck droneprofile">
              <input type="checkbox" checked={signedIn} onChange={(e) => setSignedIn(e.target.checked)} />
              use the signed-in Chrome profile
            </label>
            <p className="s">A launch starts a real Chrome and gives it {steps} steps. The signed-in profile is
              what LinkedIn, X and Google Analytics need; leave it off for a public page. It stops at a sign-in,
              a payment or an irreversible action and asks you first.</p>
          </section>
        )}
      </div>

      {isPhone ? <BridgePanel bridge={phone?.bridge} isEmail={false} waiting={false} /> : null}

      {d.kind === 'browser' && shown ? (
        <section className={cardCls(false, 'panel dronerun')}>
          <div className="dronerunhead">
            <h2>Run <span className="mono s">{shown.id}</span></h2>
            <span className={pillCls(RUN_TONE[shown.state] || '')}>{RUN_WORD[shown.state] || shown.state}</span>
            <span className="s">{shown.model_label} · {shown.steps}/{shown.max_steps} steps · {shown.profile === 'signed-in' ? 'signed-in profile · ' : ''}{ago(shown.finished || shown.started)}</span>
          </div>
          <p className="dronergoal">{shown.goal}</p>
          {shown.state === 'needs_user' && shown.question ? <p className={pillCls('accent')}>asks: {shown.question}</p> : null}
          {shown.answer ? <p className="dronerunanswer">{shown.answer}</p> : null}
          {shown.error ? <p className={pillCls('bad')}>{shown.error}</p> : null}
          <div className="dronerunbody">
            <div className="droneshotwrap">
              {shown.shot ? <img className="droneshot" src={`/api/drones/shot?id=${encodeURIComponent(shown.id)}&v=${shown.steps}`} alt="the drone's last screenshot" /> : <div className={emptyCls()}>no screenshot yet</div>}
            </div>
            <ol className="dronelog">
              {(shown.log || []).map((s) => (
                <li key={s.n} className={s.ok ? '' : 'bad'}>
                  <span className="mono">{s.n}</span> <b>{s.action}</b>
                  {s.note ? <span className="s"> — {s.note}</span> : null}
                  {s.thought ? <div className="s dronethought">{s.thought}</div> : null}
                </li>
              ))}
            </ol>
          </div>
        </section>
      ) : null}

      {d.kind === 'browser' ? (<section className={cardCls(false, 'panel droneruns')}>
        <h2>Runs <span className="q">what the drone has been asked, newest first</span></h2>
        {data.runs.length ? (
          <div className="scroll">
            <table data-nosort>
              <thead><tr><th>when</th><th>state</th><th>pilot</th><th>steps</th><th>goal</th><th></th></tr></thead>
              <tbody>
                {data.runs.map((r) => (
                  <tr key={r.id} className={r.id === shown?.id ? 'sel' : ''}>
                    <td className="s mono">{r.started.replace('T', ' ').slice(5, 16)}</td>
                    <td><span className={pillCls(RUN_TONE[r.state] || '')}>{RUN_WORD[r.state] || r.state}</span></td>
                    <td className="s">{r.model_label}</td>
                    <td className="s">{r.steps}/{r.max_steps}</td>
                    <td className="s">{r.goal.slice(0, 90)}{r.goal.length > 90 ? '…' : ''}</td>
                    <td><button className={btnCls('ghost')} onClick={() => setShow(r.id)}>open</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className={emptyCls()}>no runs yet: give the drone a task above, or ask the chat terminal to.</div>}
      </section>) : null}
    </div>
  );
}
