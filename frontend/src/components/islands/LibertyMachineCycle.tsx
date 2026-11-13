// The queue's planning cycle on the Liberty Machine page (UI.md "Liberty Machine"; thorp/viable/s3_control/cycle.py, /api/liberty-machine/cycle).
// Every twelve hours the five systems take one turn, each doing its own part: S3* closes the books, S4
// refreshes what was measured, S5 sets the envelope, S3 plans, S2 sails it, S1 measures. The strip of six
// steps sits on every system tab with that tab's steps marked; below it, the tab's own part in full: the
// audit and the plan on S3, the measurements and the judge on S4, the ceilings on S5, the schedule on S2,
// what a hire records on S1. Read-only: a turn is taken by the schedule or `thorp cycle run`.

import type { ReactNode } from 'react';
import { alertCls, cardCls, emptyCls, pillCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

type Sys = 'S1' | 'S2' | 'S3' | 'S4' | 'S5';
type Any = Record<string, any>;

const money = (v: number | null | undefined): string => (v == null ? '–' : `$${Number(v).toFixed(2)}`);
const hours = (v: number | null | undefined): string => (v == null ? '–' : `${Number(v).toFixed(1)} h`);
const mins = (v: number | null | undefined): string => (v == null ? '–' : `${Math.round(Number(v))} min`);
const pct = (v: number | null | undefined): string => (v == null ? '–' : `${Math.round(100 * Number(v))}%`);
const when = (iso: string | null | undefined): string => {
  if (!iso) return '–';
  const d = new Date(iso);
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};
/** A step belongs to a tab when its system is the tab's; the audit (S3*) sits on the S3 tab. */
const onTab = (system: string, tab: Sys): boolean => system.replace('*', '') === tab;

function Stat({ k, v, s, tone }: { k: string; v: ReactNode; s?: ReactNode; tone?: 'warn' | 'ok' }) {
  return (
    <div className={`govstat${tone ? ` ${tone}` : ''}`}>
      <b>{v}</b>
      <span>{k}{s ? <> · {s}</> : null}</span>
    </div>
  );
}

/** What each step can say in one line, from the last turn and from what is true now. */
function stepFact(n: number, d: Any): string {
  const last: Any | null = d.last;
  const plan: Any = last?.plan || {};
  const env: Any = last?.envelope || {};
  if (n === 1) {
    if (!last) return 'no turn taken yet';
    const f = (last.audit?.findings || []).length;
    return f ? `${f} finding${f === 1 ? '' : 's'} last turn` : 'nothing out of line last turn';
  }
  if (n === 2) {
    const fl: Any = d.failures || {};
    return fl.hires ? `${fl.failed} of ${fl.hires} fit-outs failed; judge ${d.judge?.name || 'not chosen'}` : 'no hire measured yet';
  }
  if (n === 3) return last ? `${money(env.cycle_allowance)} this cycle, ${env.max_instances} ship${env.max_instances === 1 ? '' : 's'}` : '–';
  if (n === 4) return last ? `${(plan.abroad || []).length} abroad on ${plan.ships} ship${plan.ships === 1 ? '' : 's'}, ${plan.stay ?? '–'} here` : '–';
  if (n === 5) return last ? (plan.lane_enabled ? 'the Vast lane is open' : 'the Vast lane is closed') : '–';
  const own = (d.classes || []).filter((c: Any) => String(c.source || '').startsWith('measured') && !String(c.source).includes('reconstructed')).length;
  return own ? `${own} class${own === 1 ? '' : 'es'} timed by the charter itself` : 'no hire timed by the charter yet';
}

function Steps({ d, tab }: { d: Any; tab: Sys }) {
  return (
    <ol className="cyclesteps">
      {(d.steps || []).map((s: Any) => (
        <li key={s.n} className={onTab(s.system, tab) ? 'here' : ''} title={s.what}>
          <div className="cyclestephead"><span className={pillCls(onTab(s.system, tab) ? 'accent' : '')}>{s.system}</span> <b>{s.n}. {s.title}</b></div>
          <div className="s">{stepFact(s.n, d)}</div>
        </li>
      ))}
    </ol>
  );
}

function Proposals({ rows, to }: { rows: Any[]; to?: string[] }) {
  const mine = to ? rows.filter((p) => to.includes(p.to)) : rows;
  if (!mine.length) return null;
  return (
    <div className={alertCls('open')}>
      <b>Proposed, not done</b> <span className="s">the plan would do these if allowed; Justin signs</span>
      <ul className="govlints">
        {mine.map((p, i) => <li key={i}><span className={pillCls('')}>{p.to}</span> <b>{p.what}</b>: {p.why}</li>)}
      </ul>
    </div>
  );
}

/** S3: the audit of the last cycle, and the plan for the next. */
function Control({ d }: { d: Any }) {
  const last: Any | null = d.last;
  if (!last) return <div className={emptyCls()}>no turn of the cycle has been taken yet: <code>thorp cycle run</code></div>;
  const plan: Any = last.plan || {}, audit: Any = last.audit || {};
  const hires: Any[] = audit.hires || [], clock: Any[] = audit.clock || [];
  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>S3* closed the books <span className="note">the last cycle&apos;s plan against what happened, read from the records and not from the planner: each hire&apos;s quote against its bill, and the queue&apos;s clock against the Mac</span></h2>
        {(audit.findings || []).length ? (
          <ul className="govlints">{audit.findings.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
        ) : <div className="s">Nothing out of line: no hire over its quote, no voyage more than a quarter over the queue&apos;s clock.</div>}
        {hires.length ? (
          <div className="scroll mt">
            <table data-nosort>
              <thead><tr><th scope="col">hire</th><th scope="col">quoted</th><th scope="col">took</th><th scope="col">set-up and home</th><th scope="col">billed</th><th scope="col">ended</th></tr></thead>
              <tbody>
                {hires.map((h) => (
                  <tr key={h.instance}>
                    <td><b>{h.name || `instance ${h.instance}`}</b><div className="s">{h.gpu} · instance {h.instance}</div></td>
                    <td className="num">{hours(h.quote_hours)}<div className="s">{money(h.quote)}</div></td>
                    <td className={`num${h.hours_ratio > 1.25 ? ' over' : ''}`}>{hours(h.hours)}{h.hours_ratio ? <div className="s">{Number(h.hours_ratio).toFixed(1)} times the quote</div> : null}</td>
                    <td className="num">{mins(h.overhead_min)}{h.setup_assumed_min ? <div className="s">planned at {mins(h.setup_assumed_min)}</div> : null}</td>
                    <td className="num">{money(h.cost)}</td>
                    <td>{h.sailed ? <span className={pillCls('good')}>sailed</span> : <span className={pillCls('bad')}>never sailed</span>}<div className="s">{h.why || h.status || '–'}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {clock.length ? <p className="note mt">The queue&apos;s clock: {clock.length} voyage{clock.length === 1 ? '' : 's'} finished here in the window; planned against taken, {clock.map((c) => `${c.name} ${mins(c.planned_min)} / ${mins(c.took_min)}`).slice(0, 6).join(' · ')}.</p> : null}
        <p className="note mt">Window: {when(new Date(audit.since * 1000).toISOString())} to {when(new Date(audit.until * 1000).toISOString())}. Spent {money(audit.spend)}, of it {money(audit.wasted)} on hires that never sailed.</p>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>The plan for the next {last.hours} hours <span className="note">the same queue planned for one ship to four. A ship costs the same beside another as after it, but every hire pays its own set-up; the Mac is free, so it is the critical path. The fleet marked is the smallest that brings the queue home soonest within the terms</span></h2>
        <div className="govstats">
          <Stat k="lines queued" v={plan.queued ?? '–'} />
          <Stat k="all on this Mac" v={hours(plan.mac_only_h)} />
          <Stat k="voyages abroad" v={(plan.abroad || []).length} s={`${plan.ships} ship${plan.ships === 1 ? '' : 's'}`} />
          <Stat k="held by the allowance" v={plan.held_by_allowance ?? 0} tone={plan.held_by_allowance ? 'warn' : undefined} />
        </div>
        <div className="scroll mt">
          <table id="cyclefleets" data-nosort>
            <thead><tr><th scope="col">fleet</th><th scope="col">voyages abroad</th><th scope="col">quotes</th><th scope="col">this Mac home in</th><th scope="col">the ships home in</th><th scope="col">the next ship costs</th><th scope="col"></th></tr></thead>
            <tbody>
              {(plan.options || []).map((r: Any) => (
                <tr key={r.ships} className={r.ships === plan.ships ? 'now' : ''}>
                  <td><b>{r.ships} ship{r.ships === 1 ? '' : 's'}</b></td>
                  <td className="num">{r.abroad}</td>
                  <td className="num">{money(r.cost)}</td>
                  <td className="num">{hours(r.mac_done_h)}</td>
                  <td className="num">{hours(r.ships_done_h)}</td>
                  <td className="num">{r.dollars_per_hour_saved != null ? `${money(r.dollars_per_hour_saved)} an hour saved` : r.ships === 1 ? '–' : <span className="s">no sooner home</span>}</td>
                  <td>{r.ships === plan.ships ? <span className={pillCls('accent')}>chosen</span> : r.within_terms ? null : <span className={pillCls('')}>beyond the terms</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(plan.abroad || []).length ? (
          <div className="scroll mt">
            <table data-nosort>
              <thead><tr><th scope="col">called foreign</th><th scope="col">on</th><th scope="col">quote</th><th scope="col">home in</th><th scope="col">why</th></tr></thead>
              <tbody>
                {plan.abroad.map((c: Any) => (
                  <tr key={c.name}><td><b>{c.name}</b></td><td>{c.gpu}</td><td className="num">{money(c.cost)}</td><td className="num">{hours(c.home_min != null ? c.home_min / 60 : null)}</td><td className="s">{c.reason}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="s mt">Nothing is called foreign: no eligible voyage comes home sooner abroad by the margin, inside the allowance.</div>}
        {!plan.lane_enabled ? <p className="note mt">The Vast lane is closed, so the plan is what the lane would carry if it were open: nothing sails abroad until it is.</p> : null}
        <Proposals rows={last.proposals || []} />
        <p className="note mt">Taken {when(last.at)} ({last.how}). The purser re-plans inside this every five minutes; this is the record the next turn&apos;s audit reads.</p>
      </section>
    </>
  );
}

/** S4: what was measured (code), and what the judge said (a model). */
function Intelligence({ d }: { d: Any }) {
  const classes: Any[] = d.classes || [], fl: Any = d.failures || {};
  const judge: Any | null = d.judge, canRun: [boolean, string] = d.judge_can_run || [false, ''];
  const judgments: Any[] = d.judgments || [], toJudge: Any[] = (d.to_judge || []).filter((c: Any) => !c.judged);
  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>What a hire really takes <span className="note">measured, not assumed: each class&apos;s set-up and home from its last hires that sailed, and how often its fit-outs died first. The planner uses these in place of S5&apos;s constant ({mins(d.constant_min)}). Lower is better throughout</span></h2>
        <div className="govstats">
          <Stat k="hires measured" v={fl.hires ?? '–'} />
          <Stat k="fit-outs that never sailed" v={fl.failed ?? '–'} s={pct(fl.rate)} tone={fl.failed ? 'warn' : undefined} />
          <Stat k="lost to them" v={mins(fl.wasted_min)} s={money(fl.wasted_cost)} />
        </div>
        <div className="scroll mt">
          <table data-nosort>
            <thead><tr><th scope="col">GPU class</th><th scope="col">set-up</th><th scope="col">home</th><th scope="col">overhead a hire</th><th scope="col">fit-outs failed</th><th scope="col">where the figure comes from</th></tr></thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.gpu}>
                  <td><b>{c.gpu}</b><div className="s">{c.sailed} sailed</div></td>
                  <td className="num">{mins(c.setup_min)}</td>
                  <td className="num">{c.home_min ? mins(c.home_min) : <span className="s">in the set-up</span>}</td>
                  <td className={`num${c.overhead_min > 1.25 * d.constant_min ? ' over' : ''}`}><b>{mins(c.overhead_min)}</b></td>
                  <td className="num">{c.hires ? `${c.failed} of ${c.hires}` : '–'}{c.hires ? <div className="s">{pct(c.failure_rate)}</div> : null}</td>
                  <td className="s">{c.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note mt">Since 12 November every hire writes where its time went on its release (provision, ssh, code, data, manifest, environment, training, home, and the megabytes carried). Older hires are reconstructed from the charter&apos;s log or the run&apos;s own clock, and carried 9 GB where a voyage now carries under 1 GB, so their set-up errs long until a new hire sails.</p>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>The judge <span className="note">S5&apos;s chosen model, asked only what a number cannot say: why a fit-out died. It reads the hire&apos;s timing and the end of its log, and proposes; nothing acts on what it says. Where a person had already written the cause down, that is shown beside the verdict and was not shown to the judge</span></h2>
        {judge ? (
          <div className="govstats">
            <Stat k="judge" v={judge.name} s={`chosen ${when(judge.set_at)}`} />
            <Stat k="may run now" v={canRun[0] ? 'yes' : 'no'} s={canRun[0] ? 'the harbour is small enough' : canRun[1]} tone={canRun[0] ? 'ok' : 'warn'} />
            <Stat k="fit-outs to judge" v={toJudge.filter((c) => c.readable).length} s={`${toJudge.filter((c) => !c.readable).length} with no log kept`} />
          </div>
        ) : <div className={emptyCls()}>no judge is chosen: <code>thorp schedule judge</code></div>}
        {judgments.length ? (
          <div className="scroll mt">
            <table data-nosort>
              <thead><tr><th scope="col">hire</th><th scope="col">the judge said</th><th scope="col">fault</th><th scope="col">a person had said</th><th scope="col">asked</th></tr></thead>
              <tbody>
                {judgments.map((j) => (
                  <tr key={j.id}>
                    <td><b>{j.verdict?.name || `instance ${j.subject}`}</b><div className="s">{j.verdict?.gpu} · instance {j.subject} · {mins(j.verdict?.minutes)}</div></td>
                    <td>{j.outcome === 'ok' ? <>{j.verdict?.cause}<div className="s">{j.verdict?.do}</div></> : <span className={pillCls('bad')}>{j.outcome}</span>}</td>
                    <td>{j.outcome === 'ok' ? <>{j.verdict?.fault}<div className="s">in {j.verdict?.step} · {j.verdict?.confidence} confidence</div></> : '–'}</td>
                    <td className="s">{j.known || '–'}</td>
                    <td className="s">{when(j.at)}<div>{j.judge} · {j.seconds != null ? `${Math.round(j.seconds)} s` : '–'}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="s mt">The judge has not been asked yet. {toJudge.filter((c) => c.readable).length} failed fit-out{toJudge.filter((c) => c.readable).length === 1 ? ' has' : 's have'} a log it can read; the next turn of the cycle asks it when the harbour allows.</div>}
        {toJudge.length ? <p className="note mt">Waiting: {toJudge.map((c) => `${c.name} (${c.gpu}, ${mins(c.minutes)}${c.readable ? '' : ', no log kept'})`).join(' · ')}.</p> : null}
        {judge ? <p className="note mt">Runs on this Mac as <code>{(judge.command || []).join(' ')}</code>, the prompt on stdin. It takes about 16 GB, so it waits while anything larger than a 1m is at sea here.</p> : null}
      </section>
    </>
  );
}

/** S5: the ceilings the plan is held to. */
function Policy({ d }: { d: Any }) {
  const last: Any | null = d.last;
  const env: Any | null = last?.envelope || null;
  if (!env) return <div className={emptyCls()}>no turn of the cycle has been taken yet: <code>thorp cycle run</code></div>;
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The envelope <span className="note">the ceilings the plan is held to. The week&apos;s budget is released a cycle at a time: what is left, over the cycles left, and what one cycle does not spend the next may. A hire counts against the allowance at its quote times the overrun, so the ceiling holds if every ship comes home at its deadline</span></h2>
      <div className="govstats">
        <Stat k="left of the week" v={money(env.week_left)} s={`of ${money(env.weekly_budget)}`} />
        <Stat k="left of this cycle's share" v={money(env.cycle_allowance)} s={`${money(env.cycle_share)} share, ${money(env.cycle_spent)} spent, ${money(env.cycle_held)} held · ${env.cycles_left} cycle${env.cycles_left === 1 ? '' : 's'} left`} />
        <Stat k="of quotes it carries" v={money(env.spendable)} s={`counted at ${env.overrun} times`} />
        <Stat k="one voyage" v={money(env.voyage_budget)} />
        <Stat k="ships at once" v={env.max_instances} />
        <Stat k="the Vast lane" v={env.lane_enabled ? 'open' : 'closed'} tone={env.lane_enabled ? 'ok' : 'warn'} />
      </div>
      <p className="note mt">A cycle is {env.cycle_hours} hours (<code>cycle_hours</code>). The purser is <b>{env.purser}</b>; a voyage sails abroad only when it is home at least {env.margin_hours} h and {pct(env.margin_fraction)} of its wait sooner. Expeditions allowed abroad: {(env.foreign_expeditions || []).join(', ') || 'none'}. Terms are changed by Justin with <code>thorp charter terms</code>, not from here.</p>
      <Proposals rows={last?.proposals || []} to={['S5']} />
    </section>
  );
}

/** S2: the schedule that takes the turn, and what the coordinator was told. */
function Coordination({ d }: { d: Any }) {
  const job: Any | null = d.job, last: Any | null = d.last;
  const lints: string[] = last?.plan?.lints || [];
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The turn on the schedule <span className="note">the cycle is a job on Thorp&apos;s own schedule (s2.schedule_jobs), not a task in another tool. The coordinator then runs the lanes; it chooses nothing</span></h2>
      <div className="govstats">
        <Stat k="the job" v={job ? (job.enabled ? 'on' : 'off') : 'not scheduled'} s={job ? `cron ${job.when}` : `thorp cycle schedule`} tone={job?.enabled ? 'ok' : 'warn'} />
        <Stat k="next turn" v={job?.next ? when(job.next) : '–'} />
        <Stat k="last firing" v={job?.last ? job.last.outcome : '–'} s={job?.last ? when(job.last.due) : 'never fired'} />
        <Stat k="the schedule's tick" v={d.ticking === true ? 'running' : d.ticking === false ? 'not loaded' : '–'} tone={d.ticking === true ? 'ok' : 'warn'} />
      </div>
      {d.ticking === false ? <div className={alertCls('no')}>The schedule&apos;s tick (<code>io.thorp.schedule</code>) is not loaded in launchd, so no job fires. Until it is, a turn is taken by hand with <code>thorp cycle run</code>.</div> : null}
      {lints.length ? <div className={alertCls('no')}><ul className="govlints">{lints.map((l, i) => <li key={i}>{l}</li>)}</ul></div> : null}
      <Proposals rows={last?.proposals || []} to={['S2']} />
      <p className="note mt"><b>Not built yet:</b> {(d.not_built || []).join(' ')}</p>
    </section>
  );
}

/** S1: what a hire now writes down. */
function Operations({ d }: { d: Any }) {
  const classes: Any[] = d.classes || [];
  const own = classes.filter((c) => String(c.source || '').startsWith('measured') && !String(c.source).includes('reconstructed'));
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>What a hire writes down <span className="note">every chartered voyage times its own steps and writes them on its release in the spend log: provision, ssh, code, data, manifest, environment, training and home, with the megabytes each transfer carried. That record is what S4 plans on at the next turn</span></h2>
      <div className="govstats">
        <Stat k="classes timed by the charter itself" v={own.length} s={`of ${classes.length}`} tone={own.length ? 'ok' : 'warn'} />
        <Stat k="hires on record" v={d.failures?.hires ?? '–'} />
      </div>
      <p className="note mt">{own.length ? '' : 'No hire has sailed since the record began, so every figure is still reconstructed from the charter’s log. '}Each hire, step by step, is on <a href="/settings/server">Settings → Server → Vast</a>.</p>
    </section>
  );
}

export function LibertyMachineCycle({ tab }: { tab: Sys }) {
  const { data, error } = useApi<Any>('/api/liberty-machine/cycle', 30000);
  if (error && !data) return <section className={cardCls(false, 'panel')}><h2>The queue&apos;s cycle</h2><div className={emptyCls()}>the cycle could not be read: {error}</div></section>;
  if (!data) return <section className={cardCls(false, 'panel')}><h2>The queue&apos;s cycle</h2><div className={emptyCls()}>reading the cycle…</div></section>;
  const last: Any | null = data.last;
  return (
    <div id="libertymachinecycle">
      <section className={cardCls(false, 'panel')}>
        <h2>The queue&apos;s cycle <span className="note">every {data.cycle_hours} hours the five systems take one turn at the queue, each doing only its own part, to bring it home soonest inside the cost ceilings. This tab&apos;s part is marked; hover a step for what it does</span></h2>
        <Steps d={data} tab={tab} />
        <p className="note mt">Last turn {last ? `${when(last.at)} (${last.how})` : 'not taken yet'} · next {data.job?.next && data.ticking ? when(data.job.next) : data.job?.enabled ? `due ${when(data.job.next)}, but the schedule's tick is not loaded` : 'not scheduled'} · judge {data.judge?.name || 'not chosen'}.</p>
      </section>
      {tab === 'S1' ? <Operations d={data} /> : null}
      {tab === 'S2' ? <Coordination d={data} /> : null}
      {tab === 'S3' ? <Control d={data} /> : null}
      {tab === 'S4' ? <Intelligence d={data} /> : null}
      {/* S5's standing proposals are in its feedback now (S5Feedback.tsx, under Decide), at the top of the page */}
      {tab === 'S5' ? <Policy d={data} /> : null}
    </div>
  );
}
