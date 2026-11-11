// The one expedition, on the Expeditions landing (12 November, Justin: the open expeditions "are all
// preparation for the expedition ... once we have all the final knowledge ... we will then launch the
// fleet"): its phases, the fleet it launches, the master charter the fleet sails under (the voyage card's
// own parameters, signed off row by row as preparation settles them) and every goal's part in the launch.
// The data is /api/launch (thorp/launch.py); a signature is a POST to /api/charter/sign, which answers
// with the page's payload again, so the row reads signed without waiting for the next poll.

import { useState } from 'react';
import { btnCls, cardCls, pillCls } from '@/lib/ui';

type GoalRef = { goal_id: string; text: string; status: string; expedition?: string | null; words?: string; evidence?: string };
type Signed = { values: Record<string, string | null>; by: string; note: string; at: string | null };
type ParamRow = {
  key: string; name: string; leg: boolean; values: Record<string, string | null>; goals: GoalRef[];
  state: 'signed' | 'drifted' | 'ready' | 'waiting'; signed: Signed | null;
};
type Rehearsal = { name: string; sop: string; state: string; ft: number | null };
type Cell = { ship: string | null; state: string; why?: string; spec?: boolean; rehearsals: Rehearsal[]; rehearsal_count?: number };
type Part = {
  goal_id: string; expedition: string; expedition_name?: string; text: string; status: string;
  part: string; why: string; params: string[]; words: string; evidence: string;
};
export type LaunchPayload = {
  version: string; name: string; frozen: boolean; draft: string; store: boolean;
  phases: { key: string; name: string; state: 'done' | 'active' | 'ahead'; note: string }[];
  readiness: { params: number; signed: number; drifted: number; ready: number; waiting: number; blocking: number; ships: number; home: number };
  fleet: { class: string; voyages: number; mean_minutes: number | null; base: Cell; instruct: Cell }[];
  charter: { columns: { class: string; base: string | null; leg: string | null }[]; groups: { key: string; name: string; params: ParamRow[] }[] };
  parts: Part[]; part_words: Record<string, string>; parts_proposed: boolean;
  preparations: Record<string, { kind: string; decides: string[]; blocking: number; parts: Record<string, number> }>;
};

const STATE_TONE: Record<string, string> = { home: 'good', 'at sea': 'running', laid: 'accent', failed: 'bad', killed: 'bad' };
const GOAL_TONE: Record<string, string> = { done: 'good', partly: 'accent', dropped: '' };
const PART_ORDER = ['decides', 'acceptance', 'delivered', 'carried', 'unassigned'];
const PART_NAME: Record<string, string> = {
  decides: 'Decides the charter', acceptance: 'The bar', delivered: 'Delivered by the fleet', carried: 'Carried to the next', unassigned: 'No part yet',
};
const plural = (n: number, one: string, many = one + 's'): string => `${n} ${n === 1 ? one : many}`;
const day = (at: string | null): string => (at ? new Date(at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '');
const mins = (m: number | null): string => (m == null ? '' : m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1)} h`);

function ShipCell({ c }: { c: Cell }) {
  if (!c.ship) return <td className="fleetcell none"><span className="s">{c.why || '–'}</span></td>;
  return (
    <td className="fleetcell">
      <div className="fleetship"><span className="mono">{c.ship}</span> <span className={pillCls(STATE_TONE[c.state] || '')}>{c.state}</span></div>
      {c.rehearsals.length ? (
        <ul className="rehearsals" title="the voyages of this class at the draft standards: what the fleet's ship has been rehearsed by">
          {c.rehearsals.map((r) => (
            <li key={r.name}>
              <a href={`/ships/${encodeURIComponent(r.name)}`} className="mono">{r.name}</a>{' '}
              <span className={`rstate ${r.state.replace(/\s+/g, '-')}`}>{r.state}</span>
              {r.ft != null ? <span className="s"> · {r.ft.toFixed(3)} bpb</span> : null}
            </li>
          ))}
          {(c.rehearsal_count || 0) > c.rehearsals.length ? <li className="s">and {(c.rehearsal_count || 0) - c.rehearsals.length} earlier</li> : null}
        </ul>
      ) : <div className="s">never rehearsed</div>}
    </td>
  );
}

export default function Launch({ data, onChange }: { data: LaunchPayload; onChange: (d: LaunchPayload) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState('');
  const classes = data.charter.columns.map((c) => c.class);
  const r = data.readiness;

  const sign = async (param: string, on: boolean): Promise<void> => {
    setBusy(param);
    setErr('');
    try {
      const res = await fetch('/api/charter/sign', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ param, sign: on }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j?.error || `${res.status}`);
      onChange(j as LaunchPayload);
    } catch (e) {
      setErr(`the signature was not recorded: ${String((e as Error)?.message ?? e)}`);
    } finally {
      setBusy(null);
    }
  };

  const valueCells = (p: ParamRow) => {
    const shown = classes.map((c) => p.values[c]);
    const have = shown.filter((v) => v != null);
    if (!have.length) return <td colSpan={classes.length} className="s">{p.leg ? 'no return leg written yet' : 'no fitout to read it from'}</td>;
    if (have.length === classes.length && have.every((v) => v === have[0])) {
      return <td colSpan={classes.length} className="same"><b>{have[0]}</b> <span className="s">at every class</span></td>;
    }
    // a value one class holds alone is the row's question: mark it
    const count = (v: string | null): number => shown.filter((x) => x === v).length;
    const most = Math.max(...have.map(count));
    return classes.map((c) => {
      const v = p.values[c];
      const odd = v != null && most > 1 && count(v) < most;
      return <td key={c} className={v == null ? 's' : odd ? 'odd' : ''} title={odd ? 'differs from the other classes' : undefined}>{v ?? '–'}</td>;
    });
  };

  const signCell = (p: ParamRow) => {
    const waitingOn = p.goals.filter((g) => g.status === 'open' || g.status === 'partly').map((g) => g.goal_id).join(', ');
    if (p.state === 'signed' || p.state === 'drifted') {
      const was = Object.entries(p.signed?.values || {}).filter(([, v]) => v != null).map(([c, v]) => `${c}: ${v}`).join(' · ');
      return <>
        <span className={pillCls(p.state === 'signed' ? 'good' : 'bad')} title={p.state === 'drifted' ? `the draft has been reworked since; signed as ${was}` : `signed as ${was}`}>{p.state}</span>
        <span className="s"> {p.signed?.by}{p.signed?.at ? `, ${day(p.signed.at)}` : ''}</span>{' '}
        {p.state === 'drifted' ? <button type="button" className={btnCls('outline')} disabled={busy === p.key} onClick={() => void sign(p.key, true)}>sign again</button> : null}{' '}
        <button type="button" className={btnCls('outline')} disabled={busy === p.key} onClick={() => void sign(p.key, false)}>take back</button>
      </>;
    }
    return <>
      <span className={pillCls(p.state === 'ready' ? 'accent' : '')} title={p.state === 'ready' ? 'nothing in preparation is left to settle it' : `waiting on ${waitingOn}`}>{p.state}</span>{' '}
      <button type="button" className={btnCls('outline')} disabled={busy === p.key} onClick={() => void sign(p.key, true)}
        title={p.state === 'waiting' ? `signs it before ${waitingOn} is settled` : undefined}>{busy === p.key ? 'signing…' : 'sign off'}</button>
    </>;
  };

  return (
    <div className="launch">
      {/* ---- the expedition and where it stands */}
      <section className={cardCls(false, 'panel launchhead')} id="launchhead">
        <div className="launchtitle">
          <div>
            <div className="launchname">{data.name} <span className="launchver">v{data.version}</span></div>
            <div className="s">the one expedition: research, test voyages and rework settle the master charter; once it is signed, the fleet launches</div>
          </div>
          <div className="launchtally">
            <span><b>{r.signed}</b> of {r.params} parameters signed</span>
            <span><b>{r.blocking}</b> deciding {r.blocking === 1 ? 'goal' : 'goals'} open</span>
            <span><b>{r.home}</b> of {r.ships} ships home</span>
          </div>
        </div>
        <ol className="phases">
          {data.phases.map((p) => (
            <li key={p.key} className={`phase ${p.state}`} aria-current={p.state === 'active' ? 'step' : undefined}>
              <span className="phasename">{p.name}</span>
              <span className="phasenote">{p.note}</span>
            </li>
          ))}
        </ol>
        {!data.store ? <div className="s">the store could not be read: the goals' verdicts and the signatures are missing from this reading</div> : null}
      </section>

      {/* ---- the fleet */}
      <section className={cardCls(false, 'panel')} id="launchfleet">
        <h2>The fleet <span className="note">the eight ships of v{data.version}: a base at every class and an instruct ship from the 9m up (a base with the return leg sailed from it). Under each, the voyages that have rehearsed it at the draft standards</span></h2>
        <div className="scroll"><table className="fleettable" data-nosort>
          <thead><tr><th />{data.fleet.map((s) => (
            <th key={s.class}>{s.class}{s.mean_minutes != null ? <span className="s" title={`the mean of ${plural(s.voyages, 'finished voyage')} of this class, every kind`}> · about {mins(s.mean_minutes)} a voyage</span> : null}</th>
          ))}</tr></thead>
          <tbody>
            <tr><th scope="row">base</th>{data.fleet.map((s) => <ShipCell key={s.class} c={s.base} />)}</tr>
            <tr><th scope="row">instruct</th>{data.fleet.map((s) => <ShipCell key={s.class} c={s.instruct} />)}</tr>
          </tbody>
        </table></div>
      </section>

      {/* ---- the master charter */}
      <section className={cardCls(false, 'panel')} id="mastercharter">
        <h2>The master charter <span className="note">the voyage card's parameters, for the whole fleet: each row read from the draft's fitouts (SOP v{data.draft}), class by class, and signed off when preparation has settled it. A signature keeps the values as signed, so a draft reworked afterwards reads drifted. {r.ready} ready to sign, {r.waiting} waiting on a goal{r.drifted ? `, ${r.drifted} drifted` : ''}</span></h2>
        {err ? <div className="bad" role="alert">{err}</div> : null}
        <div className="scroll"><table className="chartertable" data-nosort>
          <thead><tr>
            <th>parameter</th>
            {data.charter.columns.map((c) => (
              <th key={c.class}>{c.class}<div className="s mono" title="the fitout this column is read from; the return leg's rows are read from the leg">{c.base || 'no fitout'}{c.leg ? <><br />{c.leg}</> : null}</div></th>
            ))}
            <th>decided by</th><th>sign-off</th>
          </tr></thead>
          {data.charter.groups.map((g) => (
            <tbody key={g.key}>
              <tr className="chartergroup"><th colSpan={classes.length + 3} scope="colgroup">{g.name} <span className="s">{g.params.filter((p) => p.state === 'signed').length} of {g.params.length} signed</span></th></tr>
              {g.params.map((p) => (
                <tr key={p.key} className={`charterrow ${p.state}`} data-param={p.key}>
                  <th scope="row">{p.name}</th>
                  {valueCells(p)}
                  <td className="decided">{p.goals.length ? p.goals.map((gl) => (
                    <div key={gl.goal_id} title={[gl.text, gl.words, gl.evidence].filter(Boolean).join(' — ')}>
                      <a href={`/expeditions/${gl.expedition || gl.goal_id.split(':')[0]}`}>{gl.goal_id}</a>{' '}
                      <span className={pillCls(GOAL_TONE[gl.status] || '')}>{gl.status}</span>
                    </div>
                  )) : <span className="s">carried from the draft</span>}</td>
                  <td className="signoff">{signCell(p)}</td>
                </tr>
              ))}
            </tbody>
          ))}
        </table></div>
      </section>

      {/* ---- every goal's part */}
      <details className="expgroup" id="launchparts">
        <summary><h2 className="band">Every goal's part in the launch <span className="q">{PART_ORDER.filter((k) => data.parts.some((x) => x.part === k)).map((k) => `${data.parts.filter((x) => x.part === k).length} ${PART_NAME[k].toLowerCase()}`).join(' · ')}{data.parts_proposed ? ' — proposed, not yet signed off' : ''}</span></h2></summary>
        <section className={cardCls(false, 'panel')}>
          <div className="scroll"><table className="partstable" data-nosort>
            <thead><tr><th>part</th><th>goal</th><th>preparation</th><th>state</th><th>why this part</th></tr></thead>
            <tbody>
              {PART_ORDER.flatMap((k) => data.parts.filter((x) => x.part === k).map((x, i) => (
                <tr key={x.goal_id} className={i === 0 ? 'first' : ''}>
                  <td className="partname" title={data.part_words[k] || ''}>{i === 0 ? PART_NAME[k] : ''}</td>
                  <td><b>{x.text}</b> <span className="s mono">{x.goal_id}</span>{x.words ? <div className="s">{x.words}</div> : null}</td>
                  <td><a href={`/expeditions/${x.expedition}`}>{x.expedition_name || x.expedition}</a></td>
                  <td><span className={pillCls(GOAL_TONE[x.status] || '')}>{x.status}</span></td>
                  <td>{x.why || <span className="s">no part given yet</span>}</td>
                </tr>
              )))}
            </tbody>
          </table></div>
        </section>
      </details>
    </div>
  );
}
