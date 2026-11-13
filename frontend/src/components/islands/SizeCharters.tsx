// A size's Charters tab (14 November; Justin, of /ships/300k: "the ui ... needs to have a tab for charters. For the 300k
// these are our first two charters ..."; "this UI also needs to reflect the 300k along all the relevant benchmarks"; then
// "we should consolidate the charters so there's one charter. Base with 4 variants and the rigged one is just a variant on
// the base").
//
// Three parts, all from /api/class_charters (thorp/charters.py, the rows of s1.charters, s1.charter_variants,
// s1.size_findings and s1.size_benchmarks): the size's one charter with its variants (the base ones, then the rigged ones
// under their label and their own bar), where the size stands on each benchmark, and what its voyages have shown topic by
// topic. Readings are the ledger's, read live; nothing here is typed in.

import { alertCls, cardCls, emptyCls, pillCls, tableCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

type Reading = { name: string; run_id: string | null; status: string; value: number | null };
type Setting = { name: string; value: string };
type Variant = {
  key: string; name: string; role: 'control' | 'arm'; settings: Setting[]; spec: string | null;
  why: string; expect: string; state: string; voyages: Reading[];
  rigged: boolean; label: string | null; metric: string; better: 'lower' | 'higher'; bar: string | null;
  kind: 'base' | 'experiment' | 'rigged'; proves: string[];
};
type Charter = {
  key: string; name: string; aim: string; bar: string;
  metric: string; better: 'lower' | 'higher'; words: string; variants: Variant[];
};
type Field = { key: string; name: string; group: string; value: string | null; locked: boolean; drifted: boolean; goals: string[] };
type Finding = {
  key: string; topic: string; status: 'measured' | 'not measured' | 'open'; finding: string; detail: string;
  metric: string | null; next: string | null; readings: Reading[];
};
type Benchmark = {
  key: string; name: string; metric: string; better: 'lower' | 'higher'; unit: string; about: string;
  bar_model: string | null; bar_value: number | null; bar_basis: string; best: number | null; best_run: string | null; read_by: number;
};
type Payload = { size: string; charters: Charter[]; findings: Finding[]; benchmarks: Benchmark[]; base_fields: Field[] };

// a share (accuracy, prompts right) reads as a percentage; bits and nats to three places
const isShare = (metric: string | null): boolean => !!metric && /accuracy|prompt_strict|instruction_strict/.test(metric);
const fmt = (v: number | null | undefined, metric: string | null): string => {
  if (v == null) return '–';
  if (isShare(metric)) return `${(100 * v).toFixed(1)}%`;
  return (metric || '').includes('gain') ? `${v >= 0 ? '+' : ''}${v.toFixed(3)}` : v.toFixed(3);
};

const STATE_TONE: Record<string, string> = { home: 'good', 'at sea': 'running', queued: 'blue', laid: 'accent', designed: '' };
const STATUS_TONE: Record<string, string> = { measured: 'good', open: 'accent', 'not measured': '' };
const STATUS_WORDS: Record<string, string> = {
  measured: 'a reading answers it', open: 'readings point one way, not settled', 'not measured': 'nothing has read it yet',
};

function Readings({ rows, metric }: { rows: Reading[]; metric: string | null }) {
  if (!rows.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-1.5">
      {rows.map((r) => (
        <span key={r.name} className={pillCls(r.status === 'home' ? '' : 'accent')} title={r.status === 'home' ? `${r.name}, home` : `${r.name}: ${r.status}`}>
          <span className="mono">{r.name}</span>{metric ? <b className="ml-1.5">{fmt(r.value, metric)}</b> : null}
        </span>
      ))}
    </div>
  );
}

function VariantCard({ v, control, fields }: { v: Variant; control: Variant | null; fields: Record<string, Field> }) {
  const changes = control && v.kind === 'experiment';
  return (
    <div className={cardCls(false, 'gap-1.5')}>
      <div className="flex flex-wrap items-center gap-1.5">
        <b>{v.name}</b>
        {v.role === 'control' ? <span className={pillCls('solid')}>control</span> : null}
        {v.rigged ? <span className={pillCls('bad')} title={v.label || ''}>rigged</span> : null}
        <span className={pillCls(STATE_TONE[v.state] ?? '')} title={v.spec ? `fitout ${v.spec}` : 'no fitout written yet'}>{v.state}</span>
      </div>
      <div className="s">{v.why}</div>
      {v.proves.length ? (
        <div className="flex flex-wrap items-center gap-1 mt-1">
          <span className="note">proves</span>
          {v.proves.map((k) => {
            const f = fields[k];
            return <span key={k} className={pillCls(f?.locked ? 'good' : '')} title={f ? `${f.group}: ${f.value ?? '–'} on the base, ${f.locked ? 'locked' : 'open'}` : k}>{f ? f.name : k}{f ? (f.locked ? ' · locked' : ' · open') : ''}</span>;
          })}
        </div>
      ) : null}
      <div className="note mt-1">{changes ? `as the base, but:` : v.rigged ? 'by any means:' : 'the recipe:'}</div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-0.5 text-sm m-0">
        {v.settings.map((s) => (
          <div key={s.name} className="contents"><dt className="text-muted-foreground">{s.name}</dt><dd className="m-0">{s.value}</dd></div>
        ))}
      </dl>
      <div className="s mt-1"><span className="text-muted-foreground">expect:</span> {v.expect}</div>
      {v.voyages.length
        ? <Readings rows={v.voyages} metric={v.metric} />
        : <div className="note">{v.spec ? `fitout ${v.spec}, not home yet` : 'not yet a fitout: designed only'}</div>}
    </div>
  );
}

const GRID = { gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 300px), 1fr))' };

// the three every size gets, in the order they are worked (Justin, 14 November: "base needs to understand the
// transformer, we experiment on the experiment one and then try cheat on the rigged one before we decide what the base gets")
const KINDS: { key: Variant['kind']; title: string; about: string }[] = [
  { key: 'base', title: '1 · Base', about: 'the ship as we understand it: its locked fields are the master charter\'s rows signed for this size' },
  { key: 'experiment', title: '2 · Experiment', about: 'arms that each try to prove a field of the base, read on every point of the scorecard against it' },
  { key: 'rigged', title: '3 · Rigged', about: 'the most the size can score by any means; it decides nothing for the base' },
];

function BaseFields({ fields, arms }: { fields: Field[]; arms: Variant[] }) {
  const locked = fields.filter((f) => f.locked).length;
  const by = (k: string): string[] => arms.filter((a) => a.proves.includes(k)).map((a) => a.name.split(' · ')[0]);
  return (
    <details className="mt-1">
      <summary className="s cursor-pointer">The base's fields: <b>{locked}</b> of {fields.length} locked{fields.some((f) => f.drifted) ? `, ${fields.filter((f) => f.drifted).length} drifted from what was signed` : ''}</summary>
      <div className="scroll">
        <table className={tableCls.table}>
          <thead className={tableCls.head}><tr className={tableCls.row}>
            <th className={tableCls.th}>field</th><th className={tableCls.th}>on the base</th><th className={tableCls.th}></th><th className={tableCls.th}>proved by</th>
          </tr></thead>
          <tbody className={tableCls.body}>
            {fields.map((f) => (
              <tr key={f.key} className={tableCls.row}>
                <td className={tableCls.td}><span className="s text-muted-foreground">{f.group}</span> {f.name}</td>
                <td className={tableCls.td}><span className="s">{f.value ?? '–'}</span></td>
                <td className={tableCls.td}><span className={pillCls(f.locked ? 'good' : f.drifted ? 'bad' : '')}>{f.locked ? 'locked' : f.drifted ? 'drifted' : 'open'}</span></td>
                <td className={tableCls.td}><span className="s">{by(f.key).join(', ') || (f.goals.length ? `waiting on ${f.goals.join(', ')}` : '')}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function CharterCard({ c, fields }: { c: Charter; fields: Field[] }) {
  const control = c.variants.find((v) => v.role === 'control') || null;
  const byKey = Object.fromEntries(fields.map((f) => [f.key, f]));
  const arms = c.variants.filter((v) => v.kind === 'experiment');
  const open = [...new Set(arms.flatMap((a) => a.proves))].filter((k) => !byKey[k]?.locked);
  return (
    <section className={cardCls(false, 'panel')} id={`charter-${c.key}`}>
      <h2>
        {c.name}{' '}
        <span className="note">base, {arms.length} experiment arm{arms.length === 1 ? '' : 's'}, {c.variants.filter((v) => v.rigged).length} rigged · the base is judged on <span className="mono">{c.metric}</span>, {c.better} is better</span>
      </h2>
      <p className="m-0">{c.aim}</p>
      <div className="s"><span className="text-muted-foreground">the bar:</span> {c.bar}</div>
      {c.words ? <div className="s text-muted-foreground"><i>{c.words}</i></div> : null}
      {KINDS.map((k) => {
        const vs = c.variants.filter((v) => v.kind === k.key);
        if (!vs.length) return null;
        const rig = k.key === 'rigged' ? vs[0] : null;
        return (
          <div key={k.key} id={`charter-${c.key}-${k.key}`}>
            <h3 className="mt-4 mb-0">{k.title} <span className="note">{k.about}{rig ? <> · judged on <span className="mono">{rig.metric}</span>, {rig.better} is better</> : null}</span></h3>
            {k.key === 'base' && fields.length ? <BaseFields fields={fields} arms={arms} /> : null}
            {rig?.label ? <div className={alertCls('no')}>{rig.label}</div> : null}
            {rig?.bar ? <div className="s"><span className="text-muted-foreground">the bar:</span> {rig.bar}</div> : null}
            <div className="grid gap-2 mt-1" style={GRID}>
              {vs.map((v) => <VariantCard key={v.key} v={v} control={control} fields={byKey} />)}
            </div>
          </div>
        );
      })}
      <h3 className="mt-4 mb-0">4 · What the base takes <span className="note">decided when the experiment's arms are home, field by field, and signed on the master charter</span></h3>
      <div className="s">{open.length ? <>Open, and proved by the experiment: {open.map((k) => byKey[k]?.name || k).join(', ')}.</> : 'Nothing the experiment proves is still open.'}</div>
    </section>
  );
}

function Benchmarks({ rows, size }: { rows: Benchmark[]; size: string }) {
  return (
    <section className={cardCls(false, 'panel')} id="sizebenchmarks">
      <h2>Where the {size} stands <span className="note">each test the size is judged on: the best reading by any finished voyage of this size (or a variant of its shape), how many voyages were read on it, and the bar beside it with where that bar comes from</span></h2>
      <div className="scroll">
        <table className={tableCls.table}>
          <thead className={tableCls.head}><tr className={tableCls.row}>
            <th className={tableCls.th}>test</th><th className={tableCls.th}>what it reads</th><th className={tableCls.th}>best {size}</th>
            <th className={tableCls.th}>voyages read</th><th className={tableCls.th}>the bar</th><th className={tableCls.th}>where the bar comes from</th>
          </tr></thead>
          <tbody className={tableCls.body}>
            {rows.map((b) => {
              const above = b.best != null && b.bar_value != null ? (b.better === 'lower' ? b.best < b.bar_value : b.best > b.bar_value) : null;
              return (
                <tr key={b.key} className={tableCls.row}>
                  <td className={tableCls.td}><b>{b.name}</b><div className="s">{b.better} is better · {b.unit}</div></td>
                  <td className={tableCls.td}><span className="s">{b.about}</span></td>
                  <td className={tableCls.td}>
                    {b.best == null ? <span className={pillCls('')}>never read</span> : <><b>{fmt(b.best, b.metric)}</b><div className="s mono">{b.best_run}</div></>}
                  </td>
                  <td className={tableCls.td}>{b.read_by}</td>
                  <td className={tableCls.td}>
                    {b.bar_model ? <><b>{fmt(b.bar_value, b.metric)}</b> <span className="s">{b.bar_model}</span></> : '–'}
                    {above == null ? null : <div className="s">{above ? 'past it' : 'short of it'}</div>}
                  </td>
                  <td className={tableCls.td}><span className="s">{b.bar_basis}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="s mt-1">A best reading is the best of every voyage, so it is flattered by the number read: on chaining, one voyage in {rows.find((b) => b.key === 'chaining')?.read_by ?? 'many'} landing past the noise is not chaining.</div>
    </section>
  );
}

function Findings({ rows, size }: { rows: Finding[]; size: string }) {
  return (
    <section className={cardCls(false, 'panel')} id="sizefindings">
      <h2>What the {size} has shown <span className="note">topic by topic, with the voyages behind each and their readings from the ledger; <b>measured</b>: {STATUS_WORDS.measured} · <b>open</b>: {STATUS_WORDS.open} · <b>not measured</b>: {STATUS_WORDS['not measured']}</span></h2>
      <div className="grid gap-3">
        {rows.map((f) => (
          <div key={f.key} className="border-t border-border pt-2 first:border-t-0 first:pt-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <b>{f.topic}</b><span className={pillCls(STATUS_TONE[f.status] ?? '')} title={STATUS_WORDS[f.status]}>{f.status}</span>
            </div>
            <p className="m-0 mt-1">{f.finding}</p>
            <div className="s mt-0.5">{f.detail}</div>
            <Readings rows={f.readings} metric={f.metric} />
            {f.next ? <div className="s mt-1"><span className="text-muted-foreground">next:</span> {f.next}</div> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function SizeCharters({ preset, active }: { preset: string; active: boolean }) {
  const d = useApi<Payload>(preset ? `/api/class_charters?preset=${encodeURIComponent(preset)}` : null, 60000, active && !!preset);
  if (!d.data) {
    return <section className={cardCls(false, 'panel')}><div className={emptyCls()}>{d.error ? `could not read the charters: ${d.error}` : 'reading the charters…'}</div></section>;
  }
  const { charters, findings, benchmarks, size } = d.data;
  return (
    <>
      {charters.length
        ? charters.map((c) => <CharterCard key={c.key} c={c} fields={d.data!.base_fields || []} />)
        : <section className={cardCls(false, 'panel')}><div className={emptyCls()}>no charter is drawn for the {size} yet</div></section>}
      {benchmarks.length ? <Benchmarks rows={benchmarks} size={size} /> : null}
      {findings.length ? <Findings rows={findings} size={size} /> : null}
    </>
  );
}
