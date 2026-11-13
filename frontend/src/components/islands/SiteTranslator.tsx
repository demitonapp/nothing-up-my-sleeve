// The site's translator, on every page (13 November, Justin: "the Liberty Machine picks up the language you've chosen and uses
// tiny aya earth to dynamically translate the entire site"). It reads the language the Liberty Machine holds
// (/api/language, S5's s5.site_language), has lib/siteLanguage.ts put the page into it, and says what it is doing in a small
// pill at the bottom left: nothing when the page is in English or done, a count while it works, the reason when the
// translator is not here. The page's English is untouched underneath; choosing English puts every word back.

import { useEffect, useRef, useState } from 'react';
import {
  LANGUAGE_EVENT,
  PROGRESS_EVENT,
  SiteTranslator,
  fetchLanguage,
  type Language,
  type LanguageState,
  type Progress,
} from '../../lib/siteLanguage';

const pill: React.CSSProperties = {
  position: 'fixed', left: 14, bottom: 72, zIndex: 400, // above the console's bar along the bottom maxWidth: 'min(420px, calc(100vw - 28px))',
  background: '#161b22', color: '#e6edf3', border: '1px solid #2a313c', borderRadius: 8, padding: '8px 12px',
  font: '12.5px/1.4 system-ui, sans-serif', boxShadow: '0 4px 18px rgba(0,0,0,.35)',
};

export default function SiteTranslatorIsland() {
  const tr = useRef<SiteTranslator | null>(null);
  const [p, setP] = useState<Progress | null>(null);
  const [langs, setLangs] = useState<Language[]>([]);

  useEffect(() => {
    const t = new SiteTranslator();
    tr.current = t;
    t.start();
    let live = true;
    // the language this browser last had is shown at once, so a new page does not flash English; the Liberty Machine
    // then says which it is
    try {
      const had = localStorage.getItem('thorp.language');
      if (had && had !== 'en') t.set(had);
    } catch { /* blocked */ }
    const take = (s: LanguageState) => {
      if (!live) return;
      setLangs(s.languages);
      t.set(s.language.code, s.language.rtl);
    };
    fetchLanguage().then(take).catch(() => { /* no API (a static build): the page stays as it is */ });
    const onLang = (e: Event) => take((e as CustomEvent<LanguageState>).detail);
    const onProg = (e: Event) => setP((e as CustomEvent<Progress>).detail);
    window.addEventListener(LANGUAGE_EVENT, onLang);
    window.addEventListener(PROGRESS_EVENT, onProg);
    return () => {
      live = false;
      t.stop();
      window.removeEventListener(LANGUAGE_EVENT, onLang);
      window.removeEventListener(PROGRESS_EVENT, onProg);
    };
  }, []);

  if (!p || p.code === 'en' || p.state === 'idle') return null;
  const name = langs.find((l) => l.code === p.code)?.native_name || p.code;
  if (p.state === 'blocked') {
    return (
      <div style={pill} role="status" data-no-translate>
        <b>The page is still in English.</b> {p.why}
        <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
          <button type="button" className="consolbtn" onClick={() => tr.current?.retry()}>try again</button>
        </div>
      </div>
    );
  }
  return (
    <div style={pill} role="status" aria-live="polite" data-no-translate>
      Translating into {name} with Tiny Aya Earth… {p.done} of {p.total}
    </div>
  );
}
