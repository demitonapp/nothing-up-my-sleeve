// A branch's configuration: the JSON of choices the branch's controls edit (thorp/library_configs.py). The
// branch is the purpose; a configuration is a saved JSON, not a version. The sliders compose the books on the
// server (the same selection.compose a fitout reads), so the count under them is the real count, not a guess.

import { useEffect, useMemo, useState } from 'react';
import { big } from '@/lib/format';
import { btnCls, emptyCls, fieldCls, rangeCls, selectCls } from '@/lib/ui';

export interface ConfigChoices {
  size?: { words?: number | null; max_book_words?: number | null };
  books?: {
    mode?: 'select' | 'list' | 'all'; list?: string | null; rank?: 'ogden' | 'id' | 'hash';
    dedupe?: 'title' | 'none'; order?: 'id' | 'carried-first';
    carry?: string[]; not_in?: string[]; strike?: unknown[];
    filters?: Record<string, { include?: string[]; exclude?: string[] }>;
  };
  control_tokens?: { wrap?: 'none' | 'bos-eos'; turns?: 'plain' | 'marked' };
  language?: Record<string, number>;
  content_makeup?: { kind?: Record<string, number>; voice?: Record<string, number>; source?: Record<string, number> };
  /** the kinds of knowledge the ship sails with, as shares of the words; empty is the branch as it falls */
  knowledge?: Record<string, number>;
  date?: { start?: number | null; end?: number | null; undated?: 'include' | 'exclude' };
  ogden?: { min?: number | null };
}

export interface SavedConfig {
  key: string;
  branch_key?: string;
  name: string;
  about?: string;
  choices: ConfigChoices;
  config_hash?: string;
  created_at?: string;
}

interface Book {
  [i: number]: unknown;
}

interface Preview {
  summary?: {
    books?: number; words?: number; appended_share?: number;
    by_language?: Record<string, { books: number; words: number; share: number }>;
    by_kind?: Record<string, { books: number; words: number; share: number }>;
    by_voice?: Record<string, { books: number; words: number; share: number }>;
    by_knowledge?: Record<string, { books: number; words: number; share: number }>;
    by_period?: Record<string, { books: number; words: number; share: number }>;
  };
  config_hash?: string;
  books?: string[];
}

const KINDS = ['novel', 'stories', 'poem', 'play', 'essay', 'sermon', 'dialogue', 'textbook', 'history',
  'biography', 'travel', 'philosophy', 'religion', 'science', 'reference', 'periodical', 'practical', 'other'];

// The four kinds of knowledge, in the house order (thorp/library_facts.py KNOWLEDGE; the rule that gives a book
// its kind of knowledge lives there, and the preview says what a configuration holds of each).
const KNOWLEDGE: [string, string][] = [
  ['general knowledge', 'novels, stories, poems, plays, essays, reference: everything that is not one of the other three'],
  ['metaphysics', 'philosophy, religion, sermons and dialogues'],
  ['empirical knowledge', 'science, history, biography, travel, practical books and periodicals'],
  ['logic and maths', 'a title that names logic, reasoning, mathematics, geometry, algebra, number or proportion'],
];

const LANGS: Record<string, string> = {
  en: 'English', la: 'Latin', grc: 'Ancient Greek', sux: 'Sumerian', akk: 'Akkadian', egy: 'Egyptian',
  ar: 'Arabic', he: 'Hebrew', fr: 'French', de: 'German', it: 'Italian', es: 'Spanish', ru: 'Russian',
  sa: 'Sanskrit', ang: 'Old English', enm: 'Middle English', non: 'Old Norse', got: 'Gothic', syr: 'Syriac',
  nl: 'Dutch', pt: 'Portuguese', sv: 'Swedish', da: 'Danish', el: 'Greek', tr: 'Turkish', fa: 'Persian',
  zh: 'Chinese', ja: 'Japanese',
};

const pct = (v: number | undefined): number => Math.round((v ?? 0) * 1000) / 10;

/** One dimension of the content makeup: sliders whose shares are normalised to 1 when one of them moves. */
function ShareSliders({ label, note, values, counts, onSet }: {
  label: string; note: string; values: Record<string, number> | undefined;
  counts: Record<string, number>; onSet: (key: string, share: number) => void;
}) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const keys = [...new Set([...Object.keys(counts), ...Object.keys(values || {})])]
    .sort((a, b) => (counts[b] || 0) - (counts[a] || 0) || a.localeCompare(b));
  if (!keys.length) return null;
  return (
    <div className="cfgblock">
      <div className="k">{label} <span className="s">{note}</span></div>
      <div className="cfgsliders">
        {keys.map((k) => {
          const share = values?.[k] ?? (counts[k] || 0) / total;
          return (
            <label key={k} className="cfgslider">
              <span>{k} <span className="s">{counts[k] || 0}</span></span>
              <input
                className={rangeCls('cfgrange')} type="range" min={0} max={100} step={1} value={Math.round(pct(share))}
                onChange={(e) => onSet(k, +e.target.value / 100)}
              />
              <b>{Math.round(pct(share))}%</b>
            </label>
          );
        })}
      </div>
    </div>
  );
}

export default function BranchConfig({ branchKey, branchName, books, attributes, defaults, configurations, totalWords, lists }: {
  branchKey: string; branchName: string; books: Book[]; attributes: string[]; defaults: ConfigChoices;
  configurations: SavedConfig[]; totalWords: number; lists: { key: string; name: string; list: string }[];
}) {
  const has = (k: string): boolean => attributes.includes(k);
  const [choices, setChoices] = useState<ConfigChoices>(defaults || {});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [name, setName] = useState('');
  const [about, setAbout] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [extra, setExtra] = useState<SavedConfig[]>([]);
  const [liveConfigs, setLiveConfigs] = useState<SavedConfig[]>([]);
  const [jsonOpen, setJsonOpen] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState('');

  // a branch's editor starts on its defaults; a new branch is a new set of choices, not an edit of the last one
  useEffect(() => {
    setChoices(defaults || {});
    setPreview(null);
    setPreviewError(null);
    setMessage('');
    setName('');
    setAbout('');
    setExtra([]);
    setJsonOpen(false);
  }, [branchKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  // saved configurations are read live, not from the branch payload's warm copy: a save shows on reload
  useEffect(() => {
    let live = true;
    fetch('/api/library_configs?branch=' + encodeURIComponent(branchKey))
      .then((r) => r.json())
      .then((d: { configurations?: SavedConfig[] }) => { if (live) setLiveConfigs(d.configurations || []); })
      .catch(() => { if (live) setLiveConfigs([]); });
    return () => { live = false; };
  }, [branchKey]);

  // the live count: the server composes the choices exactly as a fitout would
  useEffect(() => {
    let live = true;
    let retry: number | undefined;
    const load = async (attempt = 0): Promise<void> => {
      try {
        const res = await fetch('/api/library_config/preview', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ branch: branchKey, choices }),
        });
        const d = (await res.json()) as Preview & { computing?: boolean; error?: string };
        if (!live) return;
        if (d.computing && attempt < 30) {
          retry = window.setTimeout(() => { void load(attempt + 1); }, 500);
          return;
        }
        if (!res.ok || d.error) {
          setPreviewError(d.error || `${res.status} ${res.statusText}`);
          setPreview(null);
          setPreviewing(false);
          return;
        }
        setPreview(d);
        setPreviewError(null);
        setPreviewing(false);
      } catch (e) {
        if (live) {
          setPreviewError(String((e as Error)?.message ?? e));
          setPreview(null);
          setPreviewing(false);
        }
      }
    };
    setPreviewing(true);
    const debounce = window.setTimeout(() => { void load(); }, 250);
    return () => {
      live = false;
      window.clearTimeout(debounce);
      if (retry) window.clearTimeout(retry);
    };
  }, [branchKey, choices]);

  useEffect(() => {
    if (!jsonOpen) setJsonText(JSON.stringify({ branch: branchKey, choices }, null, 1));
  }, [branchKey, choices, jsonOpen]);

  const bookStats = useMemo(() => {
    const lang: Record<string, number> = {};
    const kind: Record<string, number> = {};
    const voice: Record<string, number> = {};
    const source: Record<string, number> = {};
    for (const b of books as unknown as unknown[][]) {
      for (const [acc, i] of [[lang, 3], [kind, 5], [voice, 6], [source, 4]] as [Record<string, number>, number][]) {
        const k = String(b[i] ?? '?');
        acc[k] = (acc[k] || 0) + 1;
      }
    }
    return { lang, kind, voice, source };
  }, [books]);

  // until a share is set, a kind of knowledge stands where the configuration's own books put it (the preview),
  // so the four sliders open on what the ship would sail with and a move starts from there
  const knowledgeOwn = (k: string): number => preview?.summary?.by_knowledge?.[k]?.share ?? 0;
  const knowledgeSet = Object.keys(choices.knowledge || {}).length > 0;
  const knowledgeShare = (k: string): number => (knowledgeSet ? choices.knowledge?.[k] ?? 0 : knowledgeOwn(k));

  // move one kind of knowledge: the other three keep their proportion and the four sum to the whole
  const setKnowledge = (key: string, share: number): void => {
    setChoices((prev) => {
      const set = Object.keys(prev.knowledge || {}).length > 0;
      const others = KNOWLEDGE.map(([k]) => k).filter((k) => k !== key);
      const was = Object.fromEntries(others.map((k) => [k, set ? prev.knowledge?.[k] ?? 0 : knowledgeOwn(k)]));
      const rest = Object.values(was).reduce((a, b) => a + b, 0);
      const left = Math.max(0, 1 - share);
      const next: Record<string, number> = {};
      if (share > 0) next[key] = share;
      for (const k of others) {
        const v = rest > 0 ? (was[k] / rest) * left : left / others.length;
        if (v > 0) next[k] = Math.round(v * 10000) / 10000;
      }
      return { ...prev, knowledge: next };
    });
  };

  const s = preview?.summary;
  const top = (m: Record<string, { share: number }> | undefined, n = 3): string =>
    Object.entries(m || {}).sort((a, b) => b[1].share - a[1].share).slice(0, n)
      .map(([k, v]) => `${LANGS[k] || k} ${Math.round(v.share * 100)}%`).join(' · ');

  const sizeMax = Math.max(1_000_000, Math.ceil((totalWords || 0) / 1_000_000) * 1_000_000);
  const sizeWords = choices.size?.words ?? null;
  const sizeValue = sizeWords ?? sizeMax;

  const setSize = (n: number): void => {
    setChoices((prev) => ({ ...prev, size: { ...(prev.size || {}), words: n >= sizeMax ? null : n } }));
  };

  const setLang = (code: string, share: number): void => {
    setChoices((prev) => {
      const next = { ...(prev.language || {}) };
      if (share <= 0) delete next[code]; else next[code] = share;
      if (!Object.keys(next).length) next.en = 1;
      return { ...prev, language: next };
    });
  };

  const setMakeup = (dim: 'kind' | 'voice' | 'source', key: string, share: number): void => {
    setChoices((prev) => {
      const counts = dim === 'kind' ? bookStats.kind : dim === 'voice' ? bookStats.voice : bookStats.source;
      const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
      const current: Record<string, number> = {};
      for (const k of new Set([...Object.keys(counts), ...Object.keys((prev.content_makeup || {})[dim] || {})])) {
        current[k] = ((prev.content_makeup || {})[dim] || {})[k] ?? (counts[k] || 0) / total;
      }
      current[key] = share;
      const sum = Object.values(current).reduce((a, b) => a + b, 0);
      const next = sum > 0 ? Object.fromEntries(Object.entries(current).map(([k, v]) => [k, v / sum])) : {};
      return { ...prev, content_makeup: { ...(prev.content_makeup || {}), [dim]: next } };
    });
  };

  const setBook = (patch: Record<string, unknown>): void => {
    setChoices((prev) => ({ ...prev, books: { ...(prev.books || {}), ...patch } }));
  };

  const applyJson = (): void => {
    try {
      const parsed = JSON.parse(jsonText) as { choices?: ConfigChoices } & ConfigChoices;
      const next = (parsed.choices || parsed) as ConfigChoices;
      setChoices(next);
      setJsonError('');
      setJsonOpen(false);
    } catch (e) {
      setJsonError(String((e as Error)?.message ?? e));
    }
  };

  const copyJson = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(JSON.stringify({ branch: branchKey, choices }, null, 1));
      setMessage('the JSON is on the clipboard');
    } catch {
      setMessage('the browser would not copy; select it from the box below');
    }
  };

  const save = async (): Promise<void> => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/library_config/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch: branchKey, name, about, choices }),
      });
      const d = (await res.json()) as SavedConfig & { error?: string };
      if (!res.ok || d.error) throw new Error(d.error || `${res.status} ${res.statusText}`);
      setExtra((prev) => [d, ...prev.filter((x) => x.key !== d.key)]);
      setMessage(`saved “${d.name}” · ${String(d.config_hash || '').slice(0, 12)}`);
      setName('');
      setAbout('');
    } catch (e) {
      setMessage(String((e as Error)?.message ?? e));
    } finally {
      setSaving(false);
    }
  };

  const load = (c: SavedConfig): void => {
    setChoices(c.choices);
    setName(c.name || '');
    setAbout(c.about || '');
    setMessage(`loaded “${c.name}” as a draft; saving it again keeps its identity if the choices have not changed`);
  };

  const del = async (c: SavedConfig): Promise<void> => {
    if (!window.confirm(`Delete the configuration “${c.name}”?`)) return;
    try {
      const res = await fetch('/api/library_config/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: c.key }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setExtra((prev) => prev.filter((x) => x.key !== c.key));
      setLiveConfigs((prev) => prev.filter((x) => x.key !== c.key));
      setMessage(`deleted “${c.name}”`);
    } catch (e) {
      setMessage(String((e as Error)?.message ?? e));
    }
  };

  const saved = [...extra, ...liveConfigs, ...(configurations || [])].filter(
    (c, i, all) => all.findIndex((x) => x.key === c.key) === i,
  );

  return (
    <div className="cfgpanel">
      <div className="k">The branch's choices <span className="s">a JSON of choices, not a version: move a control, save it under a name, and the JSON is the configuration. Sailed lists stay below, locked.</span></div>
      <div className="cfggrid">
        {has('size') ? (
          <div className="cfgblock">
            <div className="k">Size <span className="s">words the configuration draws; the whole branch at the top</span></div>
            <div className="cfgslider">
              <span><b>{big(sizeValue)}</b> of {big(sizeMax)} words</span>
              <input className={rangeCls('cfgwide')} type="range" min={0} max={sizeMax} step={1_000_000} value={sizeValue} onChange={(e) => setSize(+e.target.value)} />
              <b>{sizeWords == null ? 'whole branch' : Math.round((100 * sizeWords) / sizeMax) + '%'}</b>
            </div>
          </div>
        ) : null}

        {has('ogden') ? (
          <div className="cfgblock">
            <div className="k">Ogden-ness <span className="s">the share of ordinary words at or above this bar; 0 is no bar</span></div>
            <div className="cfgslider">
              <span><b>{choices.ogden?.min == null ? 'no bar' : Math.round(choices.ogden.min * 100) + '%'}</b></span>
              <input className={rangeCls('cfgwide')} type="range" min={0} max={100} step={1} value={choices.ogden?.min == null ? 0 : Math.round(choices.ogden.min * 100)} onChange={(e) => {
                const v = +e.target.value;
                setChoices((prev) => ({ ...prev, ogden: { min: v <= 0 ? null : v / 100 } }));
              }} />
              <b>≥ {choices.ogden?.min == null ? 'any' : Math.round(choices.ogden.min * 100) + '%'}</b>
            </div>
          </div>
        ) : null}

        {has('date') ? (
          <div className="cfgblock">
            <div className="k">Date <span className="s">the writer's year; undated books are left out unless included</span></div>
            <div className="handtools cfgdate">
              <label className="note">from <input className={fieldCls('cfgnum')} type="number" placeholder="year" value={choices.date?.start ?? ''} onChange={(e) => setChoices((prev) => ({ ...prev, date: { ...(prev.date || {}), start: e.target.value === '' ? null : +e.target.value } }))} /></label>
              <label className="note">to <input className={fieldCls('cfgnum')} type="number" placeholder="year" value={choices.date?.end ?? ''} onChange={(e) => setChoices((prev) => ({ ...prev, date: { ...(prev.date || {}), end: e.target.value === '' ? null : +e.target.value } }))} /></label>
              <select className={selectCls('cfgundated')} value={choices.date?.undated || 'exclude'} onChange={(e) => setChoices((prev) => ({ ...prev, date: { ...(prev.date || {}), undated: e.target.value as 'include' | 'exclude' } }))}>
                <option value="exclude">undated left out</option>
                <option value="include">undated included</option>
              </select>
            </div>
          </div>
        ) : null}

        {has('books') ? (
          <div className="cfgblock">
            <div className="k">Books <span className="s">how the configuration finds them, and whether a title is kept once</span></div>
            <div className="handtools">
              <select className={selectCls('')} value={choices.books?.mode || 'select'} onChange={(e) => setBook({ mode: e.target.value })}>
                <option value="select">select from the library</option>
                <option value="list">an exact list</option>
                <option value="all">the whole library</option>
              </select>
              {choices.books?.mode === 'list' ? (
                <select className={selectCls('')} value={choices.books?.list || ''} onChange={(e) => setBook({ list: e.target.value || null })}>
                  <option value="">choose a list</option>
                  {lists.map((l) => <option key={l.key} value={l.list}>{l.name}</option>)}
                </select>
              ) : null}
              {choices.books?.mode === 'select' ? (
                <>
                  <select className={selectCls('')} value={choices.books?.rank || 'ogden'} onChange={(e) => setBook({ rank: e.target.value })}>
                    <option value="ogden">rank by Ogden-ness</option>
                    <option value="id">rank by id</option>
                    <option value="hash">rank by hash (seeded)</option>
                  </select>
                  <select className={selectCls('')} value={choices.books?.dedupe || 'title'} onChange={(e) => setBook({ dedupe: e.target.value })}>
                    <option value="title">one copy a title</option>
                    <option value="none">keep every copy</option>
                  </select>
                </>
              ) : null}
            </div>
            {choices.books?.filters && Object.entries(choices.books.filters).some(([, f]) => (f.include || []).length || (f.exclude || []).length) ? (
              <div className="s">
                starting filters: {Object.entries(choices.books.filters).filter(([, f]) => (f.include || []).length || (f.exclude || []).length)
                  .map(([dim, f]) => `${dim}${(f.include || []).length ? ' include ' + (f.include || []).join(', ') : ''}${(f.exclude || []).length ? ' exclude ' + (f.exclude || []).join(', ') : ''}`).join(' · ')}
              </div>
            ) : null}
          </div>
        ) : null}

        {has('control_tokens') ? (
          <div className="cfgblock">
            <div className="k">Control tokens <span className="s">how the text would be marked after the books are chosen; this does not change which books</span></div>
            <div className="handtools">
              <label className="note">wrap <select className={selectCls('')} value={choices.control_tokens?.wrap || 'none'} onChange={(e) => setChoices((prev) => ({ ...prev, control_tokens: { ...(prev.control_tokens || {}), wrap: e.target.value as 'none' | 'bos-eos' } }))}>
                <option value="none">none</option>
                <option value="bos-eos">&lt;bos&gt; … &lt;eos&gt;</option>
              </select></label>
              <label className="note">turns <select className={selectCls('')} value={choices.control_tokens?.turns || 'plain'} onChange={(e) => setChoices((prev) => ({ ...prev, control_tokens: { ...(prev.control_tokens || {}), turns: e.target.value as 'plain' | 'marked' } }))}>
                <option value="plain">plain words</option>
                <option value="marked">&lt;question&gt;/&lt;answer&gt;/&lt;end&gt;</option>
              </select></label>
            </div>
          </div>
        ) : null}
      </div>

      {has('language') ? (
        <div className="cfgblock">
          <div className="k">Language <span className="s">shares of the words; a language at zero is not read</span></div>
          <div className="cfgsliders">
            {[...new Set([...Object.keys(bookStats.lang), ...Object.keys(choices.language || {})])]
              .sort((a, b) => (bookStats.lang[b] || 0) - (bookStats.lang[a] || 0)).slice(0, 14).map((code) => (
                <label key={code} className="cfgslider">
                  <span>{LANGS[code] || code} <span className="s">{bookStats.lang[code] || 0}</span></span>
                  <input className={rangeCls('cfgrange')} type="range" min={0} max={100} step={1} value={Math.round(pct(choices.language?.[code]))} onChange={(e) => setLang(code, +e.target.value / 100)} />
                  <b>{Math.round(pct(choices.language?.[code]))}%</b>
                </label>
              ))}
          </div>
        </div>
      ) : null}

      {has('knowledge') ? (
        <div className="cfgblock">
          <div className="k">Knowledge <span className="s">the kinds of knowledge the ship sails with, each a share of the words. Left alone, the books fall as they fall; move one and the other three keep their proportion. With a size set these are the shares the composer fills, best-ranked books first, and the content makeup's own shares are not also held.</span></div>
          <div className="cfgsliders">
            {KNOWLEDGE.map(([k, about]) => {
              const asked = knowledgeShare(k);
              const held = s?.by_knowledge ? s.by_knowledge[k] || { books: 0, words: 0, share: 0 } : null;
              const short = knowledgeSet && held != null && held.share < asked - 0.02;
              return (
                <label key={k} className="cfgslider cfgknow" title={about}>
                  <span>{k}</span>
                  <input className={rangeCls('cfgrange')} type="range" min={0} max={100} step={1} value={Math.round(asked * 100)}
                    onChange={(e) => setKnowledge(k, +e.target.value / 100)} aria-label={`${k}, share of the words`} />
                  <b>{Math.round(asked * 100)}%</b>
                  <span className={short ? 'bad' : 's'}>
                    {held == null ? (previewing ? 'composing…' : '')
                      : `holds ${Math.round(held.share * 1000) / 10}% · ${big(held.books)} books, ${big(held.words)} words${short ? ': too few books of this kind pass the other choices' : ''}`}
                  </span>
                </label>
              );
            })}
          </div>
          <div className="handtools">
            <button type="button" className={btnCls('ghost')} disabled={!knowledgeSet}
              onClick={() => setChoices((prev) => ({ ...prev, knowledge: {} }))}>as the books fall</button>
            <span className="note">{knowledgeSet ? 'the JSON carries these shares' : 'no shares set: the percentages are what the other choices compose'}</span>
          </div>
        </div>
      ) : null}

      {has('content_makeup') ? (
        <>
          <ShareSliders label="Content makeup: kinds" note="the branch's own shares until you move one; then the JSON carries the weights, and the others keep their proportion"
            values={choices.content_makeup?.kind} counts={bookStats.kind} onSet={(k, v) => setMakeup('kind', k, v)} />
          <ShareSliders label="Content makeup: voices" note="who speaks; the same rule as the kinds" values={choices.content_makeup?.voice} counts={bookStats.voice} onSet={(k, v) => setMakeup('voice', k, v)} />
        </>
      ) : null}

      <div className="cfgbrief">
        {previewError ? <span className="bad">the configuration could not be composed: {previewError}</span>
          : !s ? <span>{previewing ? 'composing the branch…' : 'reading the configuration…'}</span>
          : (
            <>
              <b>{big(s.books || 0)}</b> books · <b>{big(s.words || 0)}</b> words
              {s.by_language ? <span> · {top(s.by_language)}</span> : null}
              {s.by_kind ? <span> · {top(s.by_kind, 3)}</span> : null}
              {s.by_period ? <span> · {top(s.by_period, 2)}</span> : null}
              {s.appended_share ? <span className="s"> · {Math.round(s.appended_share * 100)}% appended</span> : null}
            </>
          )}
      </div>

      <div className="cfgsave">
        <input className={fieldCls('cfgname')} type="text" placeholder="name this configuration" value={name} onChange={(e) => setName(e.target.value)} aria-label="configuration name" />
        <input className={fieldCls('cfgname cfgabout')} type="text" placeholder="what it is for (optional)" value={about} onChange={(e) => setAbout(e.target.value)} aria-label="configuration note" />
        <button type="button" className={btnCls('default')} onClick={() => { void save(); }} disabled={saving || !(s?.books)}>{saving ? 'saving…' : 'Save configuration'}</button>
        <button type="button" className={btnCls('outline')} onClick={() => { void copyJson(); }}>Copy JSON</button>
        <button type="button" className={btnCls('ghost')} onClick={() => { setJsonOpen(!jsonOpen); setJsonError(''); }}>{jsonOpen ? 'close JSON' : 'edit JSON'}</button>
        {message ? <span className="note">{message}</span> : null}
      </div>

      {jsonOpen ? (
        <div className="cfgjson">
          <textarea className={fieldCls('cfgedit')} value={jsonText} onChange={(e) => setJsonText(e.target.value)} spellCheck={false} aria-label="the JSON of choices" />
          <div className="handtools">
            <button type="button" className={btnCls('default')} onClick={applyJson}>Apply JSON</button>
            <span className="note">{jsonError ? <span className="bad">{jsonError}</span> : 'the same JSON the server validates and saves'}</span>
          </div>
        </div>
      ) : null}

      <details className="cfgpeek">
        <summary>This configuration as JSON <span className="s">the object the save sends</span></summary>
        <pre className="bspec">{JSON.stringify({ branch: branchKey, choices }, null, 1)}</pre>
      </details>

      <div className="k mt">Saved configurations <span className="s">each is a named JSON; loading one makes a draft, saving it again keeps its identity if the choices are the same</span></div>
      {saved.length ? (
        <div className="cfgcards">
          {saved.map((c) => (
            <div key={c.key} className="cfgcard">
              <div className="cfgname"><b>{c.name}</b> {c.config_hash ? <span className="mono s">{c.config_hash.slice(0, 12)}</span> : null}</div>
              {c.about ? <div className="s">{c.about}</div> : null}
              {c.created_at ? <div className="s">{String(c.created_at).slice(0, 16).replace('T', ' ')}</div> : null}
              <details><summary>the JSON of choices</summary><pre className="bspec">{JSON.stringify(c.choices, null, 1)}</pre></details>
              <div className="handtools">
                <button type="button" className={btnCls('outline')} onClick={() => load(c)}>Load</button>
                <button type="button" className={btnCls('ghost')} onClick={() => { void del(c); }}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      ) : <div className={emptyCls()}>no saved configurations yet: the first one is {branchName}'s JSON of choices</div>}
    </div>
  );
}
