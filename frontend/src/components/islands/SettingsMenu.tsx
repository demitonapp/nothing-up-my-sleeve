// The settings cog, top right, as a pop-down (13 November, Justin: "the settings cog in the top right should pop down so
// people can quick select their language and see the site change in realtime or click more settings to go the full
// settings page"). It is the same choice the chat terminal's Settings makes (lib/siteLanguage.ts: the Liberty Machine holds
// it, Tiny Aya Earth translates), so picking here changes the page under the menu while it stays open, and the pill at the
// bottom left (SiteTranslator) shows how far it has got. "More settings" is the old cog's link, /settings.

import { useEffect, useRef, useState } from 'react';
import { LANGUAGE_EVENT, chooseLanguage, fetchLanguage, type LanguageState } from '../../lib/siteLanguage';
import { logOut, useLogin } from '../../lib/login';
import { ChatModelLine, NoModelNotice, TranslatorLine } from './UiModelsSetting';
import { loadTranslator } from '../../lib/uiModels';

const COG =
  'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z';

export default function SettingsMenu({ atSettings = false }: { atSettings?: boolean }) {
  const [open, setOpen] = useState(false);
  const [s, setS] = useState<LanguageState | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [at, setAt] = useState({ top: 0, right: 0 });
  const login = useLogin();
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    fetchLanguage().then((v) => live && setS(v)).catch((e) => live && setErr(String(e?.message ?? e)));
    const on = (e: Event) => setS((e as CustomEvent<LanguageState>).detail);
    window.addEventListener(LANGUAGE_EVENT, on);
    return () => { live = false; window.removeEventListener(LANGUAGE_EVENT, on); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const place = () => {
      const r = btn.current?.getBoundingClientRect();
      if (r) setAt({ top: r.bottom + 8, right: Math.max(8, window.innerWidth - r.right) });
    };
    place();
    const away = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!menu.current?.contains(t) && !btn.current?.contains(t)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); btn.current?.focus(); } };
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', key);
    window.addEventListener('resize', place);
    return () => {
      document.removeEventListener('mousedown', away);
      document.removeEventListener('keydown', key);
      window.removeEventListener('resize', place);
    };
  }, [open]);

  const pick = async (code: string) => {
    setBusy(true);
    setErr('');
    try { await chooseLanguage(code); } catch (e) { setErr(String((e as Error)?.message ?? e)); } finally { setBusy(false); }
  };

  const now = s?.language;
  return (
    <>
      <button
        ref={btn}
        className="cog"
        id="settingscog"
        type="button"
        title="settings: the language, and the full settings page"
        aria-label="Settings"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-current={atSettings ? 'page' : undefined}
        onClick={() => setOpen((v) => !v)}
        style={{ background: 'none', border: 0, cursor: 'pointer', font: 'inherit' }}
      >
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d={COG} />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </button>
      {open ? (
        <div
          ref={menu}
          role="dialog"
          aria-label="Settings"
          style={{
            position: 'fixed', top: at.top, right: at.right, zIndex: 500, width: 'min(340px, calc(100vw - 16px))', maxHeight: 'calc(100vh - 80px)', overflowY: 'auto',
            background: 'var(--panel, #161b22)', color: 'var(--text, #e6edf3)', border: '1px solid var(--line, #2a313c)',
            borderRadius: 8, boxShadow: '0 8px 28px rgba(0,0,0,.45)', padding: 12, display: 'grid', gap: 8, fontSize: 13,
          }}
        >
          <label style={{ display: 'grid', gap: 5 }} data-no-translate-label>
            <span style={{ color: 'var(--muted, #8b949e)', fontSize: 11, letterSpacing: '.06em', textTransform: 'uppercase' }}>Language</span>
            <select
              data-no-translate
              value={now?.code ?? 'en'}
              onChange={(e) => void pick(e.target.value)}
              disabled={!s || busy}
              lang={now?.code}
              aria-label="Language"
              style={{ width: '100%', background: 'var(--bg, #0e1116)', color: 'inherit', border: '1px solid var(--line, #2a313c)', borderRadius: 6, padding: '6px 8px', font: 'inherit' }}
            >
              {!s ? <option value="en">{err ? 'unavailable' : 'reading the languages…'}</option> : null}
              {s?.languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.native_name === l.name ? l.name : `${l.native_name} · ${l.name}`}{l.listed ? '' : ' *'}
                </option>
              ))}
            </select>
          </label>
          {now && !now.is_source && !s?.translator.ready && !loadTranslator() ? <NoModelNotice role="translation" /> : null}
          {s?.note ? <span style={{ color: 'var(--muted, #8b949e)', fontSize: 12 }}>{s.note}</span> : null}
          {err && s ? <span style={{ color: 'var(--bad, #f85149)', fontSize: 12 }}>{err}</span> : null}
          {/* the site's two models (13 November): what runs the chat and the translating, and the way to the visitor's own box */}
          <hr style={{ border: 0, borderTop: '1px solid var(--line, #2a313c)', margin: '2px 0' }} />
          <span style={{ color: 'var(--muted, #8b949e)', fontSize: 11, letterSpacing: '.06em', textTransform: 'uppercase' }}>Models</span>
          <ChatModelLine onOpen={() => setOpen(false)} />
          <TranslatorLine serverReady={s ? s.translator.ready : null} onOpen={() => setOpen(false)} />
          <hr style={{ border: 0, borderTop: '1px solid var(--line, #2a313c)', margin: '2px 0' }} />
          <a href="/settings" onClick={() => setOpen(false)} style={{ color: 'var(--accent, #e3b341)', textDecoration: 'none' }}>More settings →</a>
          {/* the dashboard's login (lib/login.ts): what opens the expeditions and the Liberty Machine */}
          {login?.logged_in ? (
            <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8, color: 'var(--muted, #8b949e)', fontSize: 12 }}>
              <span>Logged in as {login.username}</span>
              <button type="button" onClick={() => { void logOut(); setOpen(false); }} style={{ background: 'none', border: 0, padding: 0, color: 'var(--accent, #e3b341)', font: 'inherit', cursor: 'pointer' }}>Log out</button>
            </span>
          ) : login ? (
            <a href={`/login?next=${encodeURIComponent(location.pathname)}`} onClick={() => setOpen(false)} style={{ color: 'var(--accent, #e3b341)', textDecoration: 'none' }}>Log in →</a>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
