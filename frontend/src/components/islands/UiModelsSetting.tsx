// The site's two models in Settings, and the notice where one is missing (13 November, Justin: "needs to show in each place
// where no model is configured, then the configuration should be in settings but to read about those models should be in the
// models section"). lib/uiModels.ts says what the models are; this sets them up.
//
//   ChatModelLine   what answers the chat terminal, and the way to the console's connect page
//   TranslatorLine  what translates the site: this site's server, or a model on the visitor's own box, found here by asking
//                   the usual local servers from this browser (lib/providers.ts), with the recommended model first
//   NoModelNotice   the short note a place shows when its model is not set up: what it would use, where to set it up, and why

import { useEffect, useState } from 'react';
import '@/styles/ui-models.css';
import {
  LOCAL_SERVERS, loadConnection, localConnection, pageOrigin, probeLocal, type Connection, type ModelInfo, type Probe,
} from '@/lib/providers';
import * as UI from '@/lib/uiModels';
import {
  MODELS_SECTION, TRANSLATOR_EVENT, loadTranslator, openChatConnect, saveTranslator, uiModel, type UiRole,
} from '@/lib/uiModels';

function useTranslatorBox(): Connection | null {
  const [box, setBox] = useState<Connection | null>(null);
  useEffect(() => {
    setBox(loadTranslator());
    const on = (e: Event) => setBox((e as CustomEvent<Connection | null>).detail);
    window.addEventListener(TRANSLATOR_EVENT, on);
    return () => window.removeEventListener(TRANSLATOR_EVENT, on);
  }, []);
  return box;
}

function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <span className="uimcode">
      <code>{text}</code>
      <button type="button" onClick={() => { void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1400); }).catch(() => {}); }} aria-label={`copy: ${text}`}>
        {done ? 'copied' : 'copy'}
      </button>
    </span>
  );
}

/** What answers the chat terminal. The connection itself is the console's; this names it and opens the console's own
 *  connect page, where local and cloud models are found. */
export function ChatModelLine({ onOpen }: { onOpen?: () => void }) {
  const [conn, setConn] = useState<Connection | null | undefined>(undefined);
  useEffect(() => {
    setConn(loadConnection());
    const on = () => setConn(loadConnection());
    window.addEventListener('storage', on);
    window.addEventListener('focus', on);
    return () => { window.removeEventListener('storage', on); window.removeEventListener('focus', on); };
  }, []);
  const m = uiModel('chat');
  const now = !conn ? null : conn.wire === 'thorp' ? 'Thorp’s own models, on this site’s server' : `${conn.modelLabel || conn.model} · ${conn.label}${conn.where === 'local' ? ', on your computer' : ', with your key'}`;
  return (
    <div className="uimline" data-no-translate>
      <span className="uimrole">Chat, reasoning and tools</span>
      <span className="uimnow">{now || <span className="uimmissing">no model set up</span>}</span>
      {!now || !m.match.test(conn?.model || '') ? <span className="uimhint">built for {m.name}</span> : null}
      <span className="uimacts">
        <button type="button" className="uimbtn" onClick={() => { openChatConnect(); onOpen?.(); }}>{now ? 'switch' : 'connect your box'}</button>
        <a href={MODELS_SECTION} onClick={() => onOpen?.()}>why {m.name} →</a>
      </span>
    </div>
  );
}

/** What translates the site, and the way to put it on the visitor's own box. */
export function TranslatorLine({ serverReady, onOpen }: { serverReady: boolean | null; onOpen?: () => void }) {
  const box = useTranslatorBox();
  const [picking, setPicking] = useState(false);
  const m = uiModel('translation');
  const now = box ? `${box.modelLabel || box.model} · ${box.label}, on your computer` : serverReady ? `${m.name}, on this site’s server` : null;
  return (
    <div className="uimline" data-no-translate>
      <span className="uimrole">Translation</span>
      <span className="uimnow">{now || <span className="uimmissing">no translator set up</span>}</span>
      {box && !m.match.test(box.model) ? <span className="uimhint">built for {m.name}</span> : null}
      <span className="uimacts">
        <button type="button" className="uimbtn" onClick={() => setPicking((v) => !v)} aria-expanded={picking}>{box ? 'switch' : 'connect your box'}</button>
        {box ? <button type="button" className="uimbtn ghost" onClick={() => saveTranslator(null)}>use this site’s server</button> : null}
        <a href={MODELS_SECTION} onClick={() => onOpen?.()}>why {m.name} →</a>
      </span>
      {picking ? <BoxPicker role="translation" current={box} onPick={(c) => { saveTranslator(c); setPicking(false); }} /> : null}
    </div>
  );
}

/** The models a box on this computer serves, the recommended one first; or, when nothing answers, how to start one. */
function BoxPicker({ role, current, onPick }: { role: UiRole; current: Connection | null; onPick: (c: Connection) => void }) {
  const m = uiModel(role);
  const [probes, setProbes] = useState<Probe[] | null>(null);
  const scan = async () => { setProbes(null); setProbes(await Promise.all(LOCAL_SERVERS.map((s) => probeLocal(s)))); };
  useEffect(() => { void scan(); }, []);
  if (!probes) return <div className="uimpick"><span className="uimdim">asking the usual local servers on this computer…</span></div>;
  const found = probes.filter((p) => p.state === 'found');
  const rows: { p: Probe; x: ModelInfo; best: boolean }[] = found
    .flatMap((p) => p.models.map((x) => ({ p, x, best: m.match.test(x.id) })))
    .sort((a, b) => Number(b.best) - Number(a.best));
  const refusing = probes.filter((p) => p.state === 'cors');
  return (
    <div className="uimpick">
      {rows.length ? (
        <>
          <div className="uimlist" role="list">
            {rows.slice(0, 12).map(({ p, x, best }) => {
              const c = localConnection(p, x);
              const on = current?.base === c.base && current?.model === c.model;
              return (
                <button key={`${p.server.id}:${x.id}`} type="button" role="listitem" className={`uimmodel${on ? ' on' : ''}`} onClick={() => onPick(c)}>
                  <span>{x.id}</span>
                  <span className="uimdim">{p.label || p.server.label}{best ? ` · ${m.name}, recommended` : ''}</span>
                </button>
              );
            })}
          </div>
          {!rows.some((r) => r.best) ? <p className="uimdim">{m.name} is not on your box yet. To add it to Ollama:</p> : null}
          {!rows.some((r) => r.best) ? <Copy text={m.ollama} /> : null}
        </>
      ) : (
        <>
          <p className="uimdim">Nothing answered on this computer. Start Ollama (or LM Studio, llama.cpp, Jan) and pull {m.name}:</p>
          <Copy text={m.ollama} />
          {m.caveat ? <p className="uimdim">{m.caveat}</p> : null}
        </>
      )}
      {refusing.map((p) => (
        <p key={p.server.id} className="uimdim">{p.server.label} is running but refuses this page. Let it in with: <Copy text={p.server.cors(pageOrigin()).line} /></p>
      ))}
      <button type="button" className="uimbtn ghost" onClick={() => void scan()}>look again</button>
    </div>
  );
}

/** The note a place shows when its model is not set up. */
export function NoModelNotice({ role, onSetUp }: { role: UiRole; onSetUp?: () => void }) {
  const m = uiModel(role);
  return (
    <div className="uimnotice" data-no-translate>
      <b>{role === 'chat' ? 'No chat model is set up.' : 'No translator is set up.'}</b>{' '}
      This site is built for <b>{m.name}</b> ({m.maker}, {m.size.split(',')[0]}), which you can run on your own computer.{' '}
      <span className="uimacts">
        {onSetUp ? <button type="button" className="uimbtn" onClick={onSetUp}>set it up</button> : null}
        <a href={MODELS_SECTION}>why we chose it →</a>
      </span>
    </div>
  );
}

/** The Models section's cards for the site's own two models (/orbitals/masaq/models#ui-models): what each does here, why
 *  we chose it, and how to run it on your own box; setting it up is Settings'. */
export function UiModelsSection() {
  const { UI_MODELS } = UI;
  return (
    <section className="uimodels" id="ui-models" aria-label="the models that run this site">
      <h2 className="band labgroup">The models that run this site <span className="q">two jobs, one model each: chosen by us, runnable on your own computer</span></h2>
      <p>
        Every other model in the Reach is one we read. These two are the ones the site itself works with: one answers in the
        chat terminal, the other translates the site. Either can run on your own computer instead of ours: set it up in
        Settings (the cog, top right).
      </p>
      <div className="uimgrid">
        {UI_MODELS.map((m) => (
          <article key={m.key} className="uimcard">
            <span className="uimrole">{m.role === 'chat' ? 'Chat, reasoning and tools' : 'Translation'}</span>
            <h3>{m.name}<span>{m.maker}</span></h3>
            <dl>
              <div><dt>What it does here</dt><dd>{m.does}</dd></div>
              <div><dt>Why we chose it</dt><dd>{m.why}</dd></div>
              <div><dt>Its size and licence</dt><dd>{m.size} · {m.licence}</dd></div>
              <div>
                <dt>On your own computer</dt>
                <dd>
                  With Ollama: <Copy text={m.ollama} />
                  {m.caveat ? <span className="uimdim" style={{ display: 'block', marginTop: 4 }}>{m.caveat}</span> : null}
                </dd>
              </div>
            </dl>
            <span className="uimacts">
              <button type="button" className="uimbtn" onClick={() => (m.role === 'chat' ? openChatConnect() : document.getElementById('settingscog')?.click())}>set it up</button>
              <a href={m.page} target="_blank" rel="noopener">the model’s card ↗</a>
              <a href={m.gguf} target="_blank" rel="noopener">its GGUF build ↗</a>
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
