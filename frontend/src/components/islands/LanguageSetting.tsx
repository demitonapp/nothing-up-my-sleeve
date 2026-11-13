// The chat terminal's language option (13 November, Justin: "add your language in the chat terminal as an option"). One row
// in the settings pane: pick a language and the Liberty Machine records it (S5, s5.site_language) and the whole site is put
// into it by Tiny Aya Earth (SiteTranslatorIsland, on every page). Each language is shown in its own, so it can be found
// by someone who cannot read the page it is on. English is the way back.

import { useEffect, useState } from 'react';
import { LANGUAGE_EVENT, chooseLanguage, fetchLanguage, type LanguageState } from '../../lib/siteLanguage';
import { TranslatorLine } from './UiModelsSetting';

export default function LanguageSetting() {
  const [s, setS] = useState<LanguageState | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    fetchLanguage().then((v) => live && setS(v)).catch((e) => live && setErr(String(e?.message ?? e)));
    const on = (e: Event) => setS((e as CustomEvent<LanguageState>).detail);
    window.addEventListener(LANGUAGE_EVENT, on);
    return () => { live = false; window.removeEventListener(LANGUAGE_EVENT, on); };
  }, []);

  const pick = async (code: string) => {
    setBusy(true);
    setErr('');
    try { await chooseLanguage(code); } catch (e) { setErr(String((e as Error)?.message ?? e)); } finally { setBusy(false); }
  };

  const now = s?.language;
  const ready = s?.translator.ready;
  return (
    <>
    <div className="consolesetrow" data-no-translate>
      <span className="consolesetname">language</span>
      <span className="consolesetline">
        <select
          value={now?.code ?? 'en'}
          onChange={(e) => void pick(e.target.value)}
          aria-label="language"
          title="the language the whole site is shown in: English stays the record, the rest is translated on the way to the screen by Tiny Aya Earth"
          disabled={!s || busy}
          lang={now?.code}
        >
          {!s ? <option value="en">reading the languages…</option> : null}
          {s?.languages.map((l) => (
            <option key={l.code} value={l.code}>
              {l.native_name === l.name ? l.name : `${l.native_name} · ${l.name}`}{l.listed ? '' : ' (not on the model’s list)'}
            </option>
          ))}
        </select>
      </span>
      {now && !now.is_source ? (
        <span className="consolesetwhy">
          {ready
            ? `the site is shown in ${now.name}, translated by Tiny Aya Earth and kept so each sentence is translated once; English stays the record`
            : s?.translator.why}
        </span>
      ) : null}
      {s?.note ? <span className="consolesetwhy">{s.note}</span> : null}
      {err ? <span className="consolesetwhy">{err}</span> : null}
    </div>
    {/* what translates the site: this site's server, or the visitor's own box (13 November) */}
    <div className="consolesetrow"><TranslatorLine serverReady={s ? s.translator.ready : null} /></div>
    </>
  );
}
