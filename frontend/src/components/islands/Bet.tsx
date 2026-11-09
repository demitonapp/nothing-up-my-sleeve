// The $100 bet (UI.md "The $100 bet"), as a client island: it fetches /api/bet and renders the whole
// panel itself, so the /bet page needs no shared script. Read-only. The helpers are the ones the view
// monolith used, typed here.

import { useEffect, useState } from 'react';
import { big } from '@/lib/format';
import { pillCls } from '@/lib/ui';

const betUsd = (v: number | null | undefined, d = 0): string => (v == null ? '–' : '$' + Number(v).toFixed(d));
const betDur = (h: number | null | undefined): string =>
  h == null ? '–' : h < 1 ? Math.max(1, Math.round(h * 60)) + ' min' : h < 48 ? (h < 10 ? h.toFixed(1) : Math.round(h)) + ' h' : (h / 24).toFixed(h / 24 < 10 ? 1 : 0) + ' days';
const betParams = (n: number): string => (n >= 1e6 ? (n / 1e6).toFixed(n < 1e7 ? 1 : 0) + 'M' : (n / 1e3).toFixed(0) + 'k');

type BetData = any;

function Stat({ k, v, s }: { k: string; v: string; s?: string }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className="s">{s}</div>
    </div>
  );
}

export default function Bet() {
  const [data, setData] = useState<BetData | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    fetch('/api/bet')
      .then((r) => r.json())
      .then(setData)
      .catch(() => setErr(true));
  }, []);

  if (err || (data && !data.budget)) {
    return (
      <div className="section" id="bet">
        <h1>$100 <span className="q">the bet: a ladder of model sizes, each rung proved on this Mac, makes a 350m trained for $100 on a rented H100 bet the right way on quantum physics</span></h1>
        <p>The bet&apos;s numbers come from /api/bet, which this server does not have yet: restart <span className="mono">thorp dash</span> to load them.</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="section" id="bet">
        <h1>$100 <span className="q">the bet: a ladder of model sizes, each rung proved on this Mac, makes a 350m trained for $100 on a rented H100 bet the right way on quantum physics</span></h1>
        <div className="s">reading the bet…</div>
      </div>
    );
  }

  const d = data;
  const b = d.budget;
  const rate = b.rate || [];
  const runs = b.runs_for_budget || {};
  const last = (d.ladder || [])[(d.ladder || []).length - 1] || {};
  const st = d.story || {};
  const q = d.quantum || {};

  return (
    <div className="section" id="bet">
      <h1>$100 <span className="q">the bet: a ladder of model sizes, each rung proved on this Mac, makes a 350m trained for $100 on a rented H100 bet the right way on quantum physics</span></h1>
      <section className="panel">
        <h2>The bet <span className="note">Justin&apos;s words, and what $100 buys on one rented H100</span></h2>
        <div id="betclaim">
          <blockquote className="betsaid">
            “{d.said}”<span className="who">Justin, {String(d.said_at || '').replace('2026-11-07 ', '7 November, ')}</span>
          </blockquote>
          <div className="strip">
            <Stat k="budget" v={betUsd(b.budget)} s="one H100, rented by the hour" />
            <Stat k="one 350m run" v={`${betDur(b.run_hours.mid)} · ${betUsd(b.run_cost.mid)}`} s={`${(b.tokens / 1e9).toFixed(1)}B tokens; ${betUsd(b.run_cost.low)} to ${betUsd(b.run_cost.high)} across the band`} />
            <Stat k="the plan" v={betUsd(b.total.mid)} s={`${b.total_hours.toFixed(0)} H100-hours: two seeds and the ablation`} />
            <Stat k="runs $100 buys" v={String(runs.mid ?? '–')} s={`${runs.high ?? '–'} to ${runs.low ?? '–'} across the band`} />
            <Stat k="gates passed" v={`${d.gates_passed} of ${(d.gates || []).length}`} s="before the $100 is spent" />
          </div>
          <p className="note mt">
            {d.claim} The band runs from ${Number(rate[0]).toFixed(2)} an hour at the fastest speed to ${Number(rate[2]).toFixed(2)} at the slowest; the middle is ${Number(rate[1]).toFixed(2)} at {b.tflops[1]} TFLOPS achieved, an estimate from published training runs.
          </p>
        </div>
      </section>
      <section className="panel">
        <h2>On the Orient pier <span className="note">the bet as Quentin Luck tells it to the bergies and car guards</span></h2>
        <div className="betstory">
          {(st.paragraphs || []).map((p: string, i: number) => <p key={i}>{p}</p>)}
        </div>
      </section>
      <section className="panel">
        <h2>The theory <span className="note">why a ladder makes the trader cheap enough to bet on</span></h2>
        <ul className="betlist">
          {(d.theory || []).map((t: any, i: number) => <li key={i}><b>{t.lead}</b> <span>{t.text}</span></li>)}
        </ul>
      </section>
      <section className="panel">
        <h2>The ladder <span className="note">each size&apos;s goal, what it reads, how long it takes on this Mac and what it would cost rented; the journey from 300k to 50m is what the bet is modelled against</span></h2>
        <div className="scroll">
          <table data-nosort>
            <thead><tr><th>class</th><th>parameters</th><th>goal</th><th>reads</th><th title="training steps only, on the Mac mini M6">this Mac</th><th title="one H100 at the middle rate">rented H100</th><th>state</th></tr></thead>
            <tbody>
              {(d.ladder || []).map((r: any) => {
                const reads = r.shelf === 'ogden' ? <>Ogden v0.1, four passes<div className="s">{big(r.tokens)} tokens</div></> : <>{r.shelf}<div className="s">{big(r.tokens)} tokens, twenty a parameter</div></>;
                const h100 = r.h100_hours != null ? `${betDur(r.h100_hours)} · ${betUsd(r.h100_cost, r.h100_cost < 10 ? 2 : 0)}` : <span className="s">not needed</span>;
                const og = r.ogden;
                const isBet = r.preset === last.preset;
                const state = og ? (<>{og.running ? <span className={pillCls('blue')}>at sea</span> : null} <span className={pillCls(og.finished >= 2 ? 'good' : '')}>{og.finished} of 2 sailed</span></>) : <span className={pillCls(isBet ? 'accent' : '')}>{isBet ? 'the bet' : 'to come'}</span>;
                return (
                  <tr key={r.preset}>
                    <td><b>{r.preset}</b><div className="s">{r.name}</div></td>
                    <td>{betParams(r.params)}</td>
                    <td><b>{r.goal}</b><div className="s">{r.test}</div></td>
                    <td>{reads}</td>
                    <td>{betDur(r.mac_hours)}<div className="s">{r.mac_kind}</div></td>
                    <td>{h100}</td>
                    <td>{state}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="note mt">Parameters on Ogden&apos;s 2,048-piece tokeniser with rotary positions. Times on this Mac ({d.mac}) are measured from the ledger where the size has sailed and estimated otherwise; the H100&apos;s are estimates. 300k to 21m read Ogden for the shapes of the world; from the 50m up each size reads English printed before its test&apos;s cutoff, so its bet is made before the world made it.</p>
      </section>
      <div className="row">
        <section className="panel">
          <h2>The quantum bet <span className="note">the discrete atom, written to the discovery tests&apos; rule</span></h2>
          <dl className="betq">
            <dt>The idea, cutoff {q.cutoff}</dt><dd>{q.idea}</dd>
            <dt>Found independently by</dt><dd>{(q.found_by || []).map((f: any) => <div key={f.who}><b>{f.who}</b> ({f.year}): {f.what}</div>)}</dd>
            <dt>The rivals</dt><dd><ul>{(q.rivals || []).map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></dd>
            <dt>On the shelf before {q.cutoff}</dt><dd><ul>{(q.precursors || []).map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></dd>
            <dt>The ablation</dt><dd>{q.ablation}</dd>
            <dt>The pass rule</dt><dd>{q.pass_rule}</dd>
          </dl>
          <p className="mt"><span className={pillCls('accent')}>{q.status || 'draft'}</span></p>
        </section>
        <section className="panel">
          <h2>The chain to the discrete atom <span className="note">one rung per size, each resting on the one below</span></h2>
          <div className="scroll">
            <table data-nosort>
              <thead><tr><th>size</th><th>rung</th><th>what it asks</th></tr></thead>
              <tbody>{(q.chain || []).map((c: any) => <tr key={c.preset}><td><b>{c.preset}</b></td><td>{c.name}</td><td>{c.about}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      </div>
      <section className="panel">
        <h2>Where the $100 goes <span className="note">one H100 sitting: the 350m at twenty tokens a parameter, two seeds and the precursor ablation, as the pass rule asks</span></h2>
        <div className="scroll">
          <table data-nosort>
            <thead><tr><th>step</th><th>H100-hours</th><th>at ${Number(rate[1]).toFixed(2)} an hour</th></tr></thead>
            <tbody>
              {(b.items || []).map((it: any) => <tr key={it.step}><td>{it.run ? <b>{it.step}</b> : it.step}</td><td>{it.hours.toFixed(1)}</td><td>{betUsd(it.cost, it.cost < 10 ? 2 : 0)}</td></tr>)}
              <tr><td colSpan={3}><b>{b.total_hours.toFixed(1)} H100-hours, {betUsd(b.total.mid)}</b> of the ${b.budget}: {b.fits ? `${betUsd(b.budget - b.total.mid)} to spare` : 'over budget'}</td></tr>
            </tbody>
          </table>
        </div>
        <p className="note mt">Each run is the 350m ({betParams(b.params)} parameters) reading {(b.tokens / 1e9).toFixed(2)}B tokens, about {(b.flops_per_token / 1e9).toFixed(2)} GFLOP a token. Across the band the plan costs {betUsd(b.total.low)} to {betUsd(b.total.high)}; at the dear end $100 buys {runs.high} run{runs.high === 1 ? '' : 's'} and the rest wait. The PyTorch port and the 1910 shelf are not in the $100: they are work, not H100-hours.</p>
      </section>
      <div className="row">
        <section className="panel">
          <h2>Gates before the H100 <span className="note">what must be true before the $100 is spent</span></h2>
          <ul className="betlist">{(d.gates || []).map((g: string, i: number) => <li key={i}>{g}</li>)}</ul>
        </section>
        <section className="panel">
          <h2>What could break it <span className="note">the bet&apos;s known risks</span></h2>
          <ul className="betlist">{(d.risks || []).map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
        </section>
      </div>
    </div>
  );
}
