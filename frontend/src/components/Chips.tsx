// The chips, a page of Demiton's discoveries (13 November, Justin: "a card here ... that focuses purely on chips
// then when clicking it's a page with 5 tabs for chip kinds, time to train, trend lines, bottlenecks, source of
// leaps with the latest information and a summary of all of them"). The summary of all five sits above the tabs on
// every one of them; each tab is an address (/chips, /chips/<tab>) the Discoveries island follows in place. The data
// and its sources are lib/chipResearch.ts.

import { cardCls, crumbCls } from '@/lib/ui';
import { DEMITON_DISCOVERIES as DB } from '@/lib/discoveryPaths';
import { TabNav } from './TabNav';
import {
  CHIP_TABS, FOR_US, GATHERED, KINDS, LAICS_AXES, LEAPS, LEAP_NOTES, PRECISION, READ_MLPERF, ROUNDS, SUMMARY,
  TAB_SOURCES, TRENDS, TREND_NOTES, WALLS, type ChipTab, type Source,
} from '@/lib/chipResearch';

export const CHIPS = `${DB}/chips`;
export const chipHref = (t: ChipTab): string => (t === 'kinds' ? CHIPS : `${CHIPS}/${t}`);
const labelOf = (t: ChipTab): string => CHIP_TABS.find((x) => x.key === t)?.label || t;
const Src = ({ s }: { s: Source }) => (
  s.href.startsWith('/') ? <a href={s.href}>{s.label}</a> : <a href={s.href} target="_blank" rel="noreferrer">{s.label}</a>
);

function Summary({ tab }: { tab: ChipTab }) {
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The summary <span className="note">what all five say, one line each, gathered {GATHERED}</span></h2>
      <div className="scroll">
        <table className="selbooks">
          <tbody>
            {SUMMARY.map((r) => (
              <tr key={r.tab}>
                <td style={{ whiteSpace: 'nowrap' }}>{r.tab === tab ? <b>{labelOf(r.tab)}</b> : <a href={chipHref(r.tab)}>{labelOf(r.tab)}</a>}</td>
                <td>{r.line}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2 className="mt">What it means for our fleet <span className="note">from our own ledger and the $100 bet</span></h2>
      <ul className="chiplist">{FOR_US.map((l) => <li key={l}>{l}</li>)}</ul>
    </section>
  );
}

function Kinds() {
  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>Six kinds of chip <span className="note">what each is, what it is good and bad at, and whether models are trained on it</span></h2>
        <div className="scroll">
          <table className="selbooks">
            <thead><tr><th>kind</th><th>examples</th><th>how it works</th><th>strong at</th><th>weak at</th><th>trains on it</th></tr></thead>
            <tbody>
              {KINDS.map((k) => (
                <tr key={k.kind}>
                  <td><b>{k.kind}</b></td>
                  <td className="s">{k.examples}</td>
                  <td>{k.how}</td>
                  <td className="s">{k.strong}</td>
                  <td className="s">{k.weak}</td>
                  <td>{k.trains}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className={cardCls(false, 'panel')}>
        <h2>How MIT Lincoln Laboratory sorts them <span className="note">the nearest thing to a published taxonomy: the Lincoln AI Computing Survey, updated yearly since 2019, over 150 chips. It focuses on serving and leaves out training across many machines</span></h2>
        <div className="scroll">
          <table className="selbooks">
            <thead><tr><th>axis</th><th>what it sorts by</th></tr></thead>
            <tbody>{LAICS_AXES.map((a) => <tr key={a.axis}><td><b>{a.axis}</b></td><td className="s">{a.values}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function TimeToTrain() {
  return (
    <>
      {ROUNDS.map((r) => (
        <section className={cardCls(false, 'panel')} key={r.round}>
          <h2>{r.round} <span className="note">{r.when}, the industry’s shared training race: the time for a set model to reach a set quality</span></h2>
          <ul className="chiplist">{r.facts.map((f) => <li key={f}>{f}</li>)}</ul>
        </section>
      ))}
      <section className={cardCls(false, 'panel')}>
        <h2>How to read it <span className="note">what a time-to-train result does and does not say</span></h2>
        <ul className="chiplist">{READ_MLPERF.map((f) => <li key={f}>{f}</li>)}</ul>
      </section>
    </>
  );
}

function Trends() {
  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>The rates <span className="note">how fast each thing about a chip improves, from Epoch AI’s hardware datasets</span></h2>
        <div className="scroll">
          <table className="selbooks">
            <thead><tr><th>what</th><th>doubles every</th><th>10x every</th><th>over</th><th>source</th></tr></thead>
            <tbody>
              {TRENDS.map((t) => (
                <tr key={t.what}>
                  <td><b>{t.what}</b></td>
                  <td>{t.doubles}</td>
                  <td>{t.tenfold || '–'}</td>
                  <td className="s">{t.note}</td>
                  <td className="s"><Src s={t.src} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className={cardCls(false, 'panel')}>
        <h2>Smaller numbers <span className="note">the other lever: doing the sums in fewer bits, against plain FP32 (Epoch’s averages)</span></h2>
        <div className="scroll">
          <table className="selbooks">
            <thead><tr><th>number format</th><th>speed against FP32</th></tr></thead>
            <tbody>{PRECISION.map((p) => <tr key={p.format}><td>{p.format}</td><td className="s">{p.gain}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className={cardCls(false, 'panel')}>
        <h2>Reading the lines</h2>
        <ul className="chiplist">{TREND_NOTES.map((n) => <li key={n}>{n}</li>)}</ul>
      </section>
    </>
  );
}

function Bottlenecks() {
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The walls <span className="note">what actually limits a training step, roughly from the most to the least general</span></h2>
      <div className="scroll">
        <table className="selbooks">
          <thead><tr><th>wall</th><th>what the research finds</th><th>the numbers</th><th>source</th></tr></thead>
          <tbody>
            {WALLS.map((w) => (
              <tr key={w.wall}>
                <td><b>{w.wall}</b></td>
                <td>{w.finding}</td>
                <td className="s">{w.numbers}</td>
                <td className="s">{w.src ? <Src s={w.src} /> : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Leaps() {
  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>Where the jumps came from <span className="note">each leap in results, how big it was, and what drove it</span></h2>
        <div className="scroll">
          <table className="selbooks">
            <thead><tr><th>leap</th><th>how big</th><th>what drove it</th><th>source</th></tr></thead>
            <tbody>
              {LEAPS.map((l) => (
                <tr key={l.leap}>
                  <td><b>{l.leap}</b></td>
                  <td>{l.size}</td>
                  <td className="s">{l.drove}</td>
                  <td className="s"><Src s={l.src} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {LEAP_NOTES.map((n) => (
        <section className={cardCls(false, 'panel')} key={n.title}>
          <h2>{n.title} <span className="note"><Src s={n.src} /></span></h2>
          <p className="chipbody">{n.body}</p>
        </section>
      ))}
    </>
  );
}

export default function Chips({ tab }: { tab: ChipTab }) {
  return (
    <>
      <h1>
        <a className={crumbCls('back')} href={DB}>← discoveries</a>{' '}
        Chips{' '}
        <span className="q">what the research says about the chips models are trained on: the kinds there are, how fast they train, how fast they improve, what holds them back, and how much of the progress in models they explain</span>
      </h1>
      <Summary tab={tab} />
      <TabNav
        id="chipsnav"
        ariaLabel="chips"
        items={CHIP_TABS.map((t) => ({ key: t.key, label: t.label, href: chipHref(t.key), active: t.key === tab }))}
      />
      {tab === 'kinds' ? <Kinds /> : tab === 'time-to-train' ? <TimeToTrain /> : tab === 'trends' ? <Trends /> : tab === 'bottlenecks' ? <Bottlenecks /> : <Leaps />}
      <section className={cardCls(false, 'panel')}>
        <h2>Sources <span className="note">for this tab; vendor figures are the vendor’s own, and the MLPerf rounds are read from vendor and press reports</span></h2>
        <ul className="chiplist">{TAB_SOURCES[tab].map((s) => <li key={s.href}><Src s={s} /></li>)}</ul>
      </section>
    </>
  );
}
