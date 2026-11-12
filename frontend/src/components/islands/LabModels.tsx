// A house's Hugging Face table and its test chooser (12 November, Justin: "within a labs details page ...
// list all models that are available on hugging face in a table and then in that table, there should be an
// icon to download the model and add it to the chat terminal and then also to see whether we have scored
// that model against all our tests ... and then to choose which tests to score against it and then it sends
// those investigative items to the bottom of the expeditions queue").
//
// The table is /api/lab_models (thorp.lab_models), the tests are /api/lab_model_tests (s4.tests), the
// download is /api/lab_download (thorp.lab_downloads) and the chosen tests become investigation specs plus
// queue lines through /api/lab_model_queue.

import { useEffect, useMemo, useState } from 'react';
import { big } from '@/lib/format';
import { btnCls, cardCls, emptyCls, fieldCls, pillCls } from '@/lib/ui';

interface DownloadState {
  state: string;
  error?: string | null;
  cached?: boolean;
}

interface HfModel {
  model: string;
  label: string;
  key: string;
  downloads: number | null;
  likes: number | null;
  last_modified: string | null;
  released: string | null;
  pipeline: string;
  variant: string;
  params: number | null;
  size_inferred: boolean;
  mlx: boolean;
  gguf: boolean;
  mac: boolean;
  nvidia: boolean;
  cached: boolean;
  url: string;
  scored: number;
  tests: number;
  download?: DownloadState;
}

interface HfData {
  lab: string;
  orgs: string[];
  models: HfModel[];
  error: string | null;
}

interface TestRow {
  key: string;
  name: string;
  chain: string;
  rung: string;
  evaluator: string;
  metric: string;
  threshold: number | null;
  min_score: number | null;
  scored: boolean;
  lift: number | null;
  score: number | null;
  performed: boolean;
}

interface TestsData {
  model: string;
  tests: TestRow[];
  scored: number;
  download?: DownloadState;
}

const supported = (t: TestRow): boolean => t.evaluator === 'discovery' || t.evaluator === 'logic';
type SortKey = 'model' | 'size' | 'released' | 'downloads' | 'likes' | 'pipeline' | 'tests';
type Sort = { key: SortKey; dir: 1 | -1 };

const COLUMNS: { key: SortKey; label: string; cls?: string }[] = [
  { key: 'model', label: 'model' },
  { key: 'size', label: 'size', cls: 'num' },
  { key: 'released', label: 'released', cls: 'num' },
  { key: 'downloads', label: 'downloads', cls: 'num' },
  { key: 'likes', label: 'likes', cls: 'num' },
  { key: 'pipeline', label: 'pipeline' },
  { key: 'tests', label: 'tests' },
];

const sortValue = (m: HfModel, key: SortKey): string | number | null => {
  switch (key) {
    case 'model': return m.label.toLowerCase();
    case 'size': return m.params;
    case 'released': return m.released ? Date.parse(m.released) : null;
    case 'downloads': return m.downloads;
    case 'likes': return m.likes;
    case 'pipeline': return m.pipeline || '';
    case 'tests': return m.tests ? m.scored / m.tests : 0;
  }
};

const when = (s: string | null): string => {
  if (!s) return '—';
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s.slice(0, 10) : d.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' });
};

export default function LabModels({ lab, ships = [] }: { lab: string; ships?: { key: string; model: string; label: string }[] }) {
  const [data, setData] = useState<HfData | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [tests, setTests] = useState<TestsData | null>(null);
  const [testModel, setTestModel] = useState('');
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [queueMsg, setQueueMsg] = useState('');
  const [queueing, setQueueing] = useState(false);
  const [q, setQ] = useState('');
  const [platform, setPlatform] = useState<'' | 'mac' | 'nvidia'>('');
  const [variant, setVariant] = useState('');
  const [sort, setSort] = useState<Sort>({ key: 'downloads', dir: -1 });

  const load = useMemo(() => async (): Promise<void> => {
    try {
      const r = await fetch(`/api/lab_models?lab=${encodeURIComponent(lab)}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      setData((await r.json()) as HfData);
      setError('');
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    }
  }, [lab]);

  useEffect(() => { void load(); }, [load]);

  const downloading = !!data?.models.some((m) => m.download?.state === 'queued' || m.download?.state === 'downloading');
  useEffect(() => {
    if (!downloading) return;
    const id = window.setInterval(() => { void load(); }, 4000);
    return () => window.clearInterval(id);
  }, [downloading, load]);

  const download = async (m: HfModel): Promise<void> => {
    setBusy(m.model);
    try {
      const r = await fetch('/api/lab_download', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ model: m.model, lab, label: m.label, params: m.params }),
      });
      if (!r.ok) throw new Error(await r.text());
      await load();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy('');
    }
  };

  const openTests = async (m: HfModel): Promise<void> => {
    setTestModel(m.model);
    setTests(null);
    setQueueMsg('');
    try {
      const r = await fetch(`/api/lab_model_tests?model=${encodeURIComponent(m.model)}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const d = (await r.json()) as TestsData;
      setTests(d);
      setChosen(new Set(d.tests.filter((t) => supported(t) && !t.scored).map((t) => t.key)));
      window.setTimeout(() => document.getElementById('labtests')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    }
  };

  const queue = async (): Promise<void> => {
    if (!testModel || !chosen.size) return;
    setQueueing(true);
    setQueueMsg('');
    try {
      const r = await fetch('/api/lab_model_queue', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lab, model: testModel, tests: [...chosen] }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.error || `${r.status} ${r.statusText}`);
      setQueueMsg(
        `queued ${d.queued?.length || 0} investigation${d.queued?.length === 1 ? '' : 's'} at the bottom`
        + (d.skipped?.length ? `; ${d.skipped.length} already there` : '')
      );
      void load();
    } catch (e) {
      setQueueMsg(`could not queue: ${(e as Error)?.message ?? e}`);
    } finally {
      setQueueing(false);
    }
  };

  const filtered = useMemo(
    () => (data?.models || []).filter((m) => {
      if (q && !`${m.model} ${m.label}`.toLowerCase().includes(q.toLowerCase())) return false;
      if (platform === 'mac' && !m.mac) return false;
      if (platform === 'nvidia' && !m.nvidia) return false;
      if (variant && m.variant !== variant) return false;
      return true;
    }),
    [data, q, platform, variant],
  );
  const shown = useMemo(() => {
    const dir = sort.dir;
    return [...filtered].sort((a, b) => {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      // a missing value (no safetensors size, no release date, no downloads) sits at the bottom in both
      // directions: it is not the smallest or the oldest, it is unknown
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === 'string' || typeof bv === 'string'
        ? String(av).localeCompare(String(bv))
        : Number(av) - Number(bv);
      return cmp * dir;
    });
  }, [filtered, sort]);
  const sized = useMemo(
    () => (data?.models || []).filter((m): m is HfModel & { params: number } => m.params != null),
    [data],
  );
  const smallest = sized.length ? [...sized].sort((a, b) => a.params - b.params)[0] : null;
  const largest = sized.length ? [...sized].sort((a, b) => b.params - a.params)[0] : null;
  const formats = useMemo(() => ({
    mlx: (data?.models || []).filter((m) => m.mlx).length,
    gguf: (data?.models || []).filter((m) => m.gguf).length,
    nvidia: (data?.models || []).filter((m) => m.nvidia).length,
  }), [data]);
  const sortBy = (key: SortKey): void => {
    setSort((s) => (s.key === key
      ? { key, dir: s.dir === 1 ? -1 : 1 }
      : { key, dir: key === 'model' || key === 'pipeline' ? 1 : -1 }));
  };
  const header = (key: SortKey, label: string, cls?: string) => (
    <th key={key} className={cls} aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="sortbtn" onClick={() => sortBy(key)} title={`sort by ${label}`}>
        {label}<span className={sort.key === key ? 'sortarrow on' : 'sortarrow'} aria-hidden="true">{sort.key === key ? (sort.dir === 1 ? '↑' : '↓') : '↕'}</span>
      </button>
    </th>
  );
  const ready = (m: HfModel): boolean => m.cached || m.download?.state === 'ready';
  const chatOk = (m: HfModel): boolean => ready(m) && !m.gguf && !m.nvidia;
  const state = (m: HfModel): DownloadState => m.download || { state: m.cached ? 'ready' : 'not started', cached: m.cached };

  return (
    <>
      <section className={cardCls(false, 'panel')} id="labhub">
        <h2>
          All its models on Hugging Face{' '}
          <span className="note">
            {data ? `${shown.length} of ${data.models.length} repositories` : 'reading the Hub…'}
            {data?.orgs?.length ? ` from ${data.orgs.join(', ')}` : ''}; download one and it joins the chat terminal
            {lab === 'nvidia' ? ' · NVIDIA’s own families (other houses’ NVFP4 conversions excluded)' : ''}
            {smallest && largest ? ` · size range ${big(smallest.params)}–${big(largest.params)}; smallest ${smallest.label}` : ''}
            {data ? ` · MLX ${formats.mlx} · GGUF ${formats.gguf} · NVIDIA ${formats.nvidia}${formats.mlx === 0 ? ' · no MLX release' : ''}` : ''}
          </span>
        </h2>
        {error ? <p className="note">the Hub list could not be read: {error}</p> : null}
        {data?.error ? <p className="note">{data.error}</p> : null}
        {!data && !error ? <div className={emptyCls()}>reading the house on Hugging Face…</div> : null}
        {data?.models?.length ? (
          <div className="handtools labplatforms">
            <span className="k">kind</span>
            <button type="button" className={pillCls(!variant ? 'accent' : '')} onClick={() => setVariant('')}>All</button>
            {(['base', 'instruct', 'reasoning', 'general', 'other'] as const).map((v) => (
              <button key={v} type="button" className={pillCls(variant === v ? 'accent' : '')} onClick={() => setVariant(variant === v ? '' : v)}>{v}</button>
            ))}
            <span className="k">runs on</span>
            <button type="button" className={pillCls(!platform ? 'accent' : '')} onClick={() => setPlatform('')}>All</button>
            <button type="button" className={pillCls(platform === 'mac' ? 'accent' : '')} onClick={() => setPlatform(platform === 'mac' ? '' : 'mac')}>Mac · MLX / GGUF</button>
            <button type="button" className={pillCls(platform === 'nvidia' ? 'accent' : '')} onClick={() => setPlatform(platform === 'nvidia' ? '' : 'nvidia')}>NVIDIA · NVFP4 / FP8 / CUDA</button>
            <input
              className={fieldCls('')}
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="search the house's models"
              style={{ width: 280 }}
              aria-label="search the Hugging Face models"
            />
            {data.models.length >= 200 ? <span className="s">the first 200 by downloads; search narrows it</span> : null}
          </div>
        ) : null}
        {shown.length ? (
          <div className="scroll modeltablewrap">
            <table className="modeltable">
              <thead>
                <tr>
                  {COLUMNS.map((c) => header(c.key, c.label, c.cls))}<th className="actions">actions</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((m) => (
                  <tr key={m.model} className={ready(m) ? 'cached' : ''}>
                    <td className="modelcell">
                      <a className="modelname" href={m.url} target="_blank" rel="noopener">{m.label}</a>
                      <div className="repo">{m.model}</div>
                      <div className="modelmeta"><span className="tag">{m.variant}</span>{m.mlx ? <span className="tag">mlx</span> : null}{m.gguf ? <span className="tag">gguf</span> : null}{m.nvidia ? <span className="tag">nvidia</span> : null}</div>
                    </td>
                    <td className="num">{m.params ? <b title={m.size_inferred ? 'from the model name; the repository has no safetensors total' : undefined}>{m.size_inferred ? '~' : ''}{big(m.params)}</b> : '—'}</td>
                    <td className="num nowrap">{when(m.released)}</td>
                    <td className="num">{m.downloads == null ? '—' : m.downloads.toLocaleString()}</td>
                    <td className="num">{m.likes == null ? '—' : m.likes.toLocaleString()}</td>
                    <td className="s">{m.pipeline || '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="testcount"
                        title={`see and choose the tests for ${m.label}`}
                        onClick={() => void openTests(m)}
                      >
                        <span>{m.scored}/{m.tests}</span>
                        <span className="testmeter" aria-hidden="true"><i style={{ width: `${m.tests ? (100 * m.scored) / m.tests : 0}%` }} /></span>
                      </button>
                    </td>
                    <td className="actions">
                      <div className="modelactions">
                        {state(m).state === 'downloading' || state(m).state === 'queued' ? (
                          <span className={pillCls('')}>{state(m).state}</span>
                        ) : ready(m) ? (
                          <span className={pillCls('good')}>ready</span>
                        ) : state(m).state === 'failed' ? (
                          <span className={pillCls('bad')} title={state(m).error || ''}>failed</span>
                        ) : null}
                        <button
                          type="button"
                          className={btnCls('outline')}
                          disabled={busy === m.model || ready(m) || state(m).state === 'downloading'}
                          title={ready(m) ? 'its weights are already cached' : 'download the model and add it to the chat terminal'}
                          onClick={() => void download(m)}
                        >{ready(m) ? '✓' : '↓'}</button>
                        <button
                          type="button"
                          className={btnCls('ghost')}
                          disabled={!chatOk(m)}
                          title={chatOk(m) ? 'add it to the chat console' : m.nvidia || m.gguf ? 'the chat console needs an MLX / safetensors checkpoint' : 'download it first'}
                          onClick={() => window.dispatchEvent(new CustomEvent('thorp:chat', { detail: { model: m.key, refresh: true } }))}
                        >chat</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {data?.models?.length && !shown.length ? (
          <div className={emptyCls()}>no model matches this search, kind and platform.</div>
        ) : null}
      </section>

      <section className={cardCls(false, 'panel')} id="labtests">
        <h2>
          Tests <span className="note">choose the tests to score this model on; the queue takes one investigation per test at its bottom</span>
        </h2>
        {!testModel ? (
          <p className="note">Choose a model above, open its tests, and tick the ones to score.</p>
        ) : !tests ? (
          <div className={emptyCls()}>reading the tests for {testModel}…</div>
        ) : (
          <>
            <p className="note">
              <b>{testModel}</b>: {tests.scored} of {tests.tests.length} tests have a reading. Ticked tests are queued;
              tests with their own scorer are shown but not ticked here.
            </p>
            <div className="scroll testtablewrap">
              <table className="testtable">
                <thead><tr><th></th><th>test</th><th>chain</th><th>rung</th><th>evaluator</th><th>reading</th></tr></thead>
                <tbody>
                  {tests.tests.map((t) => (
                    <tr key={t.key} className={!supported(t) ? 'aside' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`score ${t.name}`}
                          checked={chosen.has(t.key)}
                          disabled={!supported(t)}
                          onChange={(e) => {
                            setChosen((prev) => {
                              const next = new Set(prev);
                              if (e.target.checked) next.add(t.key); else next.delete(t.key);
                              return next;
                            });
                          }}
                        />
                      </td>
                      <td><b>{t.name}</b><div className="s mono">{t.key}</div></td>
                      <td className="s">{t.chain || '—'}</td>
                      <td className="s">{t.rung || '—'}</td>
                      <td className="s">{t.evaluator || 'unbuilt'}{supported(t) ? '' : ' · own scorer'}</td>
                      <td>
                        {t.scored ? (
                          <span className={pillCls(t.performed ? 'good' : '')}>
                            lift {t.lift == null ? '—' : t.lift.toFixed(2)}
                            {t.score != null ? ` · ${Math.round(100 * t.score)}%` : ''}
                            {t.performed ? ' ✓' : ''}
                          </span>
                        ) : <span className="s">not scored</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="labmeta">
              <button type="button" className={btnCls('outline')} disabled={queueing || !chosen.size} onClick={() => void queue()}>
                {queueing ? 'queueing…' : `Queue ${chosen.size} investigation${chosen.size === 1 ? '' : 's'}`}
              </button>
              <button
                type="button"
                className={btnCls('ghost')}
                onClick={() => setChosen(new Set(tests.tests.filter((t) => supported(t) && !t.scored).map((t) => t.key)))}
              >Select unscored</button>
              <button type="button" className={btnCls('ghost')} onClick={() => setChosen(new Set())}>Clear</button>
              {queueMsg ? <span className="s">{queueMsg}</span> : null}
            </div>
            {ships.length ? (
              <p className="note">
                The house&apos;s ships already in the Reach: {ships.map((s) => s.label).join(' · ')}
              </p>
            ) : null}
          </>
        )}
      </section>
    </>
  );
}
