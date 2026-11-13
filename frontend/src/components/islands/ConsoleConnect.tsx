// The console's first page (13 November, Justin: "the chat terminal onboarding needs to be world class, so needs
// support for both local and cloud models and to plug them in as easy as possible"). It opens where the chat
// would be when this browser has no model yet, and again from the bar's switch.
//
// Two doors: a model on this computer (found by asking the usual local servers from this browser, listed, one
// click to use) and a cloud model (paste a key, it is checked with one cheap call, then the models it reaches
// are listed). Each thing that goes wrong in practice is taught rather than failed: a server that is not
// running gets its start and install lines, one with no models gets the pull command, one that refuses this
// page gets the exact one-line CORS setting. In the private edition a third, smaller door is Thorp's own models
// on its server (the MLX path the console always had).

import { useEffect, useMemo, useRef, useState } from 'react';
import '@/styles/console-connect.css';
import {
  CLOUD_PROVIDERS, LOCAL_SERVERS, PUBLIC_EDITION, SERVER_CONNECTION, checkKey, cloudConnection, connKey, forgetKey, forgetRecent, getKey,
  keyRemembered, localConnection, localNetworkAccess, pageIsLocal, pageOrigin, probeAddress, probeLocal, providerOfKey, recentConnections,
  setKey, type CloudProvider, type Connection, type ModelInfo, type Probe,
} from '@/lib/providers';

type View = 'home' | 'local' | 'cloud';


function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <span className="ccode">
      <code>{text}</code>
      <button
        type="button"
        className="ccopy"
        onClick={() => {
          void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1400); }).catch(() => { /* no clipboard */ });
        }}
        aria-label={`copy: ${text}`}
      >{done ? 'copied' : 'copy'}</button>
    </span>
  );
}

const kTokens = (n?: number | null): string => (n ? (n >= 1000 ? `${Math.round(n / 1000)}k window` : `${n} window`) : '');

function ModelList({ models, onPick, busyId, current }: { models: ModelInfo[]; onPick: (m: ModelInfo) => void; busyId?: string; current?: string }) {
  const [q, setQ] = useState('');
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? models.filter((m) => `${m.id} ${m.label || ''} ${m.note || ''}`.toLowerCase().includes(s)) : models;
  }, [models, q]);
  return (
    <div className="cmodels">
      {models.length > 10 ? (
        <input className="cfilter" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={`filter ${models.length} models…`} aria-label="filter the models" />
      ) : null}
      <div className="cmodellist" role="list">
        {shown.slice(0, 200).map((m) => (
          <button key={m.id} type="button" role="listitem" className={`cmodel${current === m.id ? ' on' : ''}`} onClick={() => onPick(m)} disabled={busyId === m.id}>
            <span className="cmodelname">{m.label && m.label !== m.id ? m.label : m.id}</span>
            <span className="cmodelnote">{[m.label && m.label !== m.id ? m.id : '', m.note, kTokens(m.context)].filter(Boolean).join(' · ')}</span>
            <span className="cmodelgo" aria-hidden="true">{current === m.id ? 'in use' : 'use →'}</span>
          </button>
        ))}
        {shown.length === 0 ? <p className="cdim">Nothing matches “{q.trim()}”.</p> : null}
      </div>
    </div>
  );
}

export default function ConsoleConnect({ current, serverModels, onPick, onClose, start = 'home' }: {
  current: Connection | null;
  serverModels: number | null; // Thorp's own models on this server, null where there are none to offer
  onPick: (c: Connection) => void;
  onClose?: () => void;
  start?: View;
}) {
  const [view, setView] = useState<View>(start);
  const origin = pageOrigin();
  const onThisMachine = pageIsLocal();

  // ---- local: every usual server asked at once, and asked again every few seconds while nothing answers, so
  // starting Ollama in a terminal is enough: the page finds it without a click
  const [probes, setProbes] = useState<Probe[]>(() => LOCAL_SERVERS.map((s) => ({ server: s, base: `http://localhost:${s.port}`, state: 'checking', models: [] })));
  const [scanning, setScanning] = useState(false);
  const [extra, setExtra] = useState<Probe | null>(null);
  const [address, setAddress] = useState('');
  const [addressBusy, setAddressBusy] = useState(false);
  // a page served from elsewhere reaches this computer only with the browser's leave (Chrome's local network access)
  const [lna, setLna] = useState<'granted' | 'denied' | 'prompt' | 'unknown'>('unknown');
  const scan = async (quiet = false): Promise<void> => {
    if (!quiet) setScanning(true);
    const [got, access] = await Promise.all([Promise.all(LOCAL_SERVERS.map((s) => probeLocal(s))), localNetworkAccess()]);
    setProbes(got);
    setLna(access);
    if (!quiet) setScanning(false);
  };
  const found = probes.filter((p) => p.state === 'found');
  const anyFound = found.length > 0 || extra?.state === 'found';
  const problems = probes.filter((p) => p.state === 'cors' || p.state === 'empty');
  useEffect(() => { void scan(); }, []);
  // listening: asked again while nothing is found, or while a server waits on a pull or a CORS setting
  const tries = useRef(0);
  useEffect(() => {
    if ((anyFound && !problems.length) || view === 'cloud' || scanning) return;
    if (tries.current > 45) return; // three minutes of listening, then the button does it
    const t = window.setTimeout(() => { tries.current += 1; void scan(true); }, 4000);
    return () => window.clearTimeout(t);
  }, [anyFound, problems.length, view, scanning, probes]);
  // each page of the connect flow opens at its top
  const rootRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { rootRef.current?.closest('.consolechat')?.scrollTo({ top: 0 }); }, [view]);

  // ---- cloud
  const [pid, setPid] = useState(() => (current?.where === 'cloud' ? current.provider : 'anthropic'));
  const provider = CLOUD_PROVIDERS.find((p) => p.id === pid) || CLOUD_PROVIDERS[0];
  const [base, setBase] = useState(() => (current?.provider === 'custom' ? current.base : ''));
  const baseOf = (p: CloudProvider): string => (p.id === 'custom' ? base.trim().replace(/\/+$/, '') : p.base);
  const [key, setKeyDraft] = useState('');
  const [remember, setRemember] = useState(true);
  const [checking, setChecking] = useState(false);
  const [cloudErr, setCloudErr] = useState('');
  const [hint, setHint] = useState('');
  const [cloudModels, setCloudModels] = useState<ModelInfo[] | null>(null);
  const kept = getKey(provider.id, baseOf(provider));
  useEffect(() => { setCloudModels(null); setCloudErr(''); setKeyDraft(''); }, [pid]);

  const check = async (p: CloudProvider, k: string): Promise<void> => {
    if (!k.trim() && !p.keyOptional) { setCloudErr(`paste your ${p.label} key first`); return; }
    setChecking(true);
    setCloudErr('');
    setCloudModels(null);
    try {
      const models = await checkKey(p, k, baseOf(p));
      if (!models.length) throw new Error(`the key works, but ${p.label} lists no chat models for it`);
      setKey(p.id, baseOf(p), k.trim(), remember);
      setKeyDraft('');
      setCloudModels(models);
    } catch (e) {
      setCloudErr(String((e as Error).message || e));
    } finally {
      setChecking(false);
    }
  };
  // a pasted key names its provider by its prefix: the right one is chosen and the key checked at once
  const onPaste = (text: string): void => {
    const who = providerOfKey(text);
    const p = CLOUD_PROVIDERS.find((x) => x.id === who);
    if (p && p.id !== pid && pid !== 'custom') {
      setHint(`that is a ${p.label} key: switched to ${p.label}`);
      setPid(p.id);
      window.setTimeout(() => { setKeyDraft(text); void check(p, text); }, 0);
      return;
    }
    setHint('');
    if (p || text.trim().length > 20) window.setTimeout(() => void check(provider, text), 0);
  };

  const [, bump] = useState(0);
  const recents = recentConnections().filter((c) => !current || connKey(c) !== connKey(current)).slice(0, 5);

  const dotOf = (p: Probe): string => (p.state === 'found' ? 'ok' : p.state === 'checking' ? 'wait' : p.state === 'down' ? 'off' : 'warn');
  const down = probes.filter((p) => p.state === 'down');

  const head = (title: string, back = true) => (
    <div className="chead">
      {back ? <button type="button" className="cback" onClick={() => setView('home')} aria-label="back">←</button> : null}
      <h2>{title}</h2>
      {onClose && current ? <button type="button" className="consolbtn" onClick={onClose}>back to the chat</button> : null}
    </div>
  );

  const localCardLine = scanning && !anyFound && probes.every((p) => p.state === 'checking')
    ? <span><i className="cdot wait" /> looking on this computer…</span>
    : anyFound
      ? <span><i className="cdot ok" /> found {found.map((p) => p.label || p.server.label).join(', ')}: {found.reduce((n, p) => n + p.models.length, 0)} model{found.reduce((n, p) => n + p.models.length, 0) === 1 ? '' : 's'}</span>
      : problems.length
        ? <span><i className="cdot warn" /> {problems[0].server.label} is running but {problems[0].state === 'cors' ? 'won’t let this page in yet' : 'has no models yet'}</span>
        : lna === 'denied'
          ? <span><i className="cdot bad" /> your browser is not letting this page reach your computer: it shows you how</span>
          : <span><i className="cdot off" /> nothing running yet: it shows you how</span>;

  if (view === 'home') {
    return (
      <div className="cconnect" ref={rootRef}>
        {head(current ? 'Switch model' : 'Connect a model', false)}
        <p className="clead">
          The console talks to a model you choose. Run one on this computer, or bring a key for a cloud model.
          {current ? ' Your past chats stay where they are.' : ' You can switch at any time from the bar.'}
        </p>
        <div className="cdoors">
          <section className="cdoor">
            <h3>On this computer</h3>
            <p className="cdim">Free and private: nothing leaves your machine. Ollama, LM Studio, llama.cpp, MLX, vLLM or Jan.</p>
            <p className="cfound" aria-live="polite">{localCardLine}</p>
            {anyFound ? (
              <div className="cquick">
                {found.flatMap((p) => p.models.slice(0, 3).map((m) => (
                  <button key={`${p.server.id}:${m.id}`} type="button" className="cquickbtn" onClick={() => onPick(localConnection(p, m))} title={`chat with ${m.id} on ${p.label || p.server.label}`}>
                    {m.id}<span>{p.label || p.server.label}</span>
                  </button>
                )))}
              </div>
            ) : null}
            <button type="button" className="consolbtn primary cdoorbtn" onClick={() => setView('local')}>
              {anyFound ? 'all local models →' : 'use a model on this computer →'}
            </button>
          </section>
          <section className="cdoor">
            <h3>A cloud model</h3>
            <p className="cdim">Anthropic, OpenAI, Google, OpenRouter, or any OpenAI-compatible endpoint. Paste your own key.</p>
            <p className="cfound"><span><i className="cdot lock" /> your key stays in this browser</span></p>
            <button type="button" className="consolbtn primary cdoorbtn" onClick={() => setView('cloud')}>use a cloud model →</button>
          </section>
        </div>
        {!PUBLIC_EDITION && serverModels ? (
          <button type="button" className={`cserver${current?.wire === 'thorp' ? ' on' : ''}`} onClick={() => onPick(SERVER_CONNECTION)}>
            <b>Thorp’s own models</b>
            <span>{serverModels} on this dashboard’s server, run through MLX, with Thorp’s tools</span>
            <span className="cmodelgo">{current?.wire === 'thorp' ? 'in use' : 'use →'}</span>
          </button>
        ) : null}
        {recents.length ? (
          <div className="crecent">
            <span className="cdim">recently used</span>
            {recents.map((c) => (
              <span key={connKey(c)} className="crecentchip">
                <button type="button" onClick={() => onPick(c)} title={`${c.model} on ${c.label}`}>{c.modelLabel || c.model}<span>{c.label}</span></button>
                <button type="button" className="cx" onClick={() => { forgetRecent(c); bump((n) => n + 1); }} aria-label={`forget ${c.model}`}>×</button>
              </span>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (view === 'local') {
    const rows = [...found, ...(extra ? [extra] : [])];
    return (
      <div className="cconnect" ref={rootRef}>
        {head('On this computer')}
        <div className="cscan">
          <span className="cdim" aria-live="polite">
            {scanning ? 'looking…' : anyFound ? `asked ${LOCAL_SERVERS.length} usual servers` : 'listening: start a server and it appears here'}
          </span>
          <button type="button" className="consolbtn" onClick={() => { tries.current = 0; void scan(); }} disabled={scanning}>check again</button>
        </div>
        {rows.filter((p) => p.state === 'found').map((p) => (
          <section key={p.base} className="cserverblock">
            <h3><i className="cdot ok" /> {p.label || p.server.label} <span className="cdim">{p.base.replace(/^https?:\/\//, '')}</span></h3>
            <ModelList models={p.models} onPick={(m) => onPick(localConnection(p, m))} current={current?.base === `${p.base}/v1` ? current.model : undefined} />
          </section>
        ))}
        {[...problems, ...(extra && extra.state !== 'found' && extra.state !== 'down' ? [extra] : [])].map((p) => {
          const fix = p.server.cors(origin);
          return (
            <section key={`${p.base}:${p.state}`} className="cserverblock warn">
              <h3><i className={`cdot ${dotOf(p)}`} /> {p.server.label} <span className="cdim">{p.base.replace(/^https?:\/\//, '')}</span></h3>
              {p.state === 'cors' ? (
                <>
                  <p>{p.server.label} is running, but it won’t answer this page ({origin}) yet. Browsers ask a server’s permission first (CORS); one setting gives it:</p>
                  <Copy text={fix.line} />
                  {fix.then ? <p className="cdim">{fix.then}</p> : null}
                </>
              ) : (
                <>
                  <p>{p.server.label} is running, but has no models yet. Fetch one (a few GB, once):</p>
                  {p.server.pull ? <Copy text={p.server.pull} /> : null}
                  <p className="cdim">It appears here on its own when the download finishes.</p>
                </>
              )}
            </section>
          );
        })}
        {!anyFound && !problems.length && lna === 'denied' ? (
          <section className="cserverblock warn">
            <h3><i className="cdot bad" /> Your browser is not letting this page reach your computer</h3>
            <p>This page is served from {new URL(origin).host}, so your browser asks before it may talk to servers on your own machine, and that permission is off for this site. Until it is on, a running Ollama looks the same as none.</p>
            <ol className="clist">
              <li>Click the icon at the left of the address bar, then <b>Site settings</b>.</li>
              <li>Set <b>Local network access</b> to <b>Allow</b>, and come back to this tab.</li>
              <li>Press <b>check again</b>.</li>
            </ol>
          </section>
        ) : null}
        {!anyFound && !problems.length && lna !== 'denied' ? (
          <section className="cempty">
            <h3>Nothing is running on this computer yet</h3>
            <p>The quickest start is Ollama: about two minutes, and it needs no account.</p>
            <ol>
              <li>Install it from <a href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com/download</a> and open it.</li>
              <li>Fetch a small model in a terminal: <Copy text="ollama pull qwen3:4b" /></li>
              <li>That’s all: this page is listening and lists it the moment it is there.</li>
            </ol>
            <p className="cdim">Already use something else? LM Studio, llama.cpp, an MLX server, vLLM and Jan are asked too, on their usual ports, and any other address can be added below.</p>
          </section>
        ) : null}
        {!onThisMachine && lna !== 'denied' ? (
          <p className="cnote">This page is not served from your computer, so your browser may ask to let it reach devices on your local network: allow it. Safari can refuse such requests from a secure page; Chrome, Edge and Firefox allow them.</p>
        ) : null}
        <form
          className="caddress"
          onSubmit={(e) => {
            e.preventDefault();
            if (!address.trim()) return;
            setAddressBusy(true);
            void probeAddress(address).then((p) => { setExtra(p); setAddressBusy(false); }).catch(() => setAddressBusy(false));
          }}
        >
          <label htmlFor="caddr" className="cdim">another address</label>
          <input id="caddr" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="localhost:5000 or http://192.168.1.20:11434" spellCheck={false} />
          <button type="submit" className="consolbtn" disabled={!address.trim() || addressBusy}>{addressBusy ? '…' : 'ask it'}</button>
        </form>
        {extra && extra.state === 'down' ? <p className="cerr">Nothing answered at {extra.base}. Is the server running, and listening on that address?</p> : null}
        {down.length && lna !== 'denied' ? (
          <details className="cdown">
            <summary>not running here: {down.map((p) => `${p.server.label} (:${p.server.port})`).join(', ')}</summary>
            {down.map((p) => (
              <div key={p.server.id} className="cdownrow">
                <b>{p.server.label}</b>
                <span className="cdim">start it with</span>
                <Copy text={p.server.start} />
                <a href={p.server.install} target="_blank" rel="noreferrer">get it ↗</a>
              </div>
            ))}
          </details>
        ) : null}
      </div>
    );
  }

  // ---- cloud
  const base_ = baseOf(provider);
  return (
    <div className="cconnect" ref={rootRef}>
      {head('A cloud model')}
      <div className="cproviders" role="radiogroup" aria-label="provider">
        {CLOUD_PROVIDERS.map((p) => (
          <button key={p.id} type="button" role="radio" aria-checked={p.id === pid} className={`cprov${p.id === pid ? ' on' : ''}`} onClick={() => { setPid(p.id); setHint(''); }}>
            <b>{p.label}</b><span>{p.blurb}</span>
          </button>
        ))}
      </div>
      {hint ? <p className="cnote">{hint}</p> : null}
      <form className="ckeyform" onSubmit={(e) => { e.preventDefault(); void check(provider, key || kept); }}>
        {provider.id === 'custom' ? (
          <label className="cfield">
            <span>base URL</span>
            <input value={base} onChange={(e) => { setBase(e.target.value); setCloudModels(null); }} placeholder="https://api.groq.com/openai/v1" spellCheck={false} autoComplete="off" />
          </label>
        ) : null}
        <label className="cfield">
          <span>{provider.id === 'custom' ? 'API key' : `${provider.label} API key`}</span>
          <input
            type="password"
            value={key}
            onChange={(e) => setKeyDraft(e.target.value)}
            onPaste={(e) => { const t = e.clipboardData.getData('text'); if (t) { e.preventDefault(); setKeyDraft(t.trim()); onPaste(t.trim()); } }}
            placeholder={kept ? `a key is kept in this browser (•••• ${kept.slice(-4)}): press check, or paste another` : provider.keyHint}
            autoComplete="off"
            spellCheck={false}
            aria-describedby="ckeyprivacy"
          />
        </label>
        <div className="ckeyrow">
          <label className="cremember">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            remember it in this browser
          </label>
          {provider.keyUrl ? <a href={provider.keyUrl} target="_blank" rel="noreferrer">get your {provider.label} key ↗</a> : null}
          {kept ? <button type="button" className="clink" onClick={() => { forgetKey(provider.id, base_); setCloudModels(null); setKeyDraft(''); setHint(`the ${provider.label} key is forgotten in this browser`); }}>forget the kept key</button> : null}
          <button type="submit" className="consolbtn primary" disabled={checking || (!key.trim() && !kept && !provider.keyOptional) || (provider.id === 'custom' && !base.trim())}>
            {checking ? 'checking…' : 'check key'}
          </button>
        </div>
        <p id="ckeyprivacy" className="cprivacy">
          <i className="cdot lock" />
          Your key goes from this browser straight to {provider.id === 'custom' ? 'that endpoint' : provider.label}, in each request’s own header.
          Thorp’s server never receives it and never logs it. {remember ? 'It is kept in this browser’s local storage until you forget it here.' : 'It is held for this tab only and forgotten when the tab closes.'}
        </p>
      </form>
      {cloudErr ? <p className="cerr">{cloudErr}</p> : null}
      {cloudModels ? (
        <section className="cserverblock">
          <h3><i className="cdot ok" /> the key works: {cloudModels.length} model{cloudModels.length === 1 ? '' : 's'} on {provider.id === 'custom' ? base_.replace(/^https?:\/\//, '') : provider.label}</h3>
          <ModelList models={cloudModels} onPick={(m) => onPick(cloudConnection(provider, m, base_))} current={current?.provider === provider.id ? current.model : undefined} />
        </section>
      ) : null}
      {!cloudModels && !cloudErr && !kept && provider.id !== 'custom' ? (
        <p className="cdim cafter">Paste the key and it is checked at once with one free call that lists your models; nothing is sent to a model until you ask it something.</p>
      ) : null}
      {keyRemembered(provider.id, base_) && !remember ? <p className="cnote">The kept key stays in local storage until you press “forget the kept key”.</p> : null}
    </div>
  );
}
