// The server tab's Vast.ai panel (/settings/server): the market's price reads (s4.market_reads), the
// voyages hired (s3.spend_events) and the terms that bound them (s5.charter), one row a GPU chip class.
// The figures are thorp.dash.settings' chip_stats; this file only lays them out (UI.md, "Settings").

import type { ReactNode } from 'react';
import { cardCls, emptyCls, pillCls } from '@/lib/ui';

export interface VastChip {
  gpu: string;
  ceiling: number | null;
  reads: number;
  last_read: string | null;
  price: number | null;
  reliability: number | null;
  min: number | null;
  median: number | null;
  max: number | null;
  hires: number;
  out: number;
  hours: number;
  spent: number;
  rate: number | null;
  rate_preset: string | null;
  rate_at: string | null;
  guess: number | null;
}

export interface Vast {
  error?: string;
  at: string;
  key: boolean;
  seats: number;
  week: { spent: number; budget: number };
  voyage_budget: number;
  out: number;
  chips: VastChip[];
  totals: { reads: number; hires: number; hours: number; spent: number };
}

const money = (v: number | null | undefined, digits = 2): string => (v == null ? '–' : `$${v.toFixed(digits)}`);
const when = (iso: string | null | undefined): string => {
  if (!iso) return '–';
  const d = new Date(iso);
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};
const tokens = (v: number | null | undefined): string => (v == null ? '–' : `${Math.round(v / 1000).toLocaleString()}k/s`);

function Stat({ k, v, s }: { k: string; v: ReactNode; s?: ReactNode }) {
  return <div className="stat"><div className="k">{k}</div><div className="v">{v}</div><div className="s">{s}</div></div>;
}

export function VastPanel({ vast }: { vast: Vast }) {
  const d = vast;
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The market <span className="note">the price reads and the voyages hired, per GPU chip class the charter's terms allow. Read from the store, never the API, so it is as fresh as the last quote or hire; the key is only ever said to be present</span></h2>
      {d.error ? <div className={emptyCls()}>the Vast.ai figures could not be read: {d.error}</div> : (
        <>
          <div className="strip">
            <Stat k="the key" v={d.key ? 'set' : 'not set'} s={d.key ? <a href="/shipyard/constraints">set on the constraints page</a> : 'the charter cannot hire without it'} />
            <Stat k="seats" v={String(d.seats)} s="one instance a seat" />
            <Stat k="the week" v={money(d.week.spent)} s={`of ${money(d.week.budget)} · Monday to Sunday, UTC`} />
            <Stat k="all time" v={money(d.totals.spent)} s={`${d.totals.hires} voyage${d.totals.hires === 1 ? '' : 's'} · ${d.totals.hours} h at sea`} />
            <Stat k="ships out" v={String(d.out)} s="hired, not yet released" />
          </div>
          <div className="scroll mt">
            <table id="vasttable" data-nosort>
              <thead>
                <tr>
                  <th rowSpan={2} scope="col">chip class</th>
                  <th colSpan={3} scope="colgroup" className="grp">the market</th>
                  <th colSpan={4} scope="colgroup" className="grp sep">the voyages</th>
                </tr>
                <tr>
                  <th scope="col">reads</th>
                  <th scope="col">price now</th>
                  <th scope="col">the range <span className="s">min · median · max</span></th>
                  <th scope="col" className="sep">voyages</th>
                  <th scope="col">hours</th>
                  <th scope="col">spent</th>
                  <th scope="col">the last rate</th>
                </tr>
              </thead>
              <tbody>
                {d.chips.map((c) => (
                  <tr key={c.gpu} className={c.out ? 'out' : ''}>
                    <td><b>{c.gpu}</b>{c.ceiling != null ? <div className="s">ceiling {money(c.ceiling)} an hour</div> : null}</td>
                    <td className="num">{c.reads ? <>{c.reads}<div className="s">{when(c.last_read)}</div></> : <span className="s">never read</span>}</td>
                    <td className="num">{money(c.price, 3)}{c.price != null
                      ? <div className="s">rel {c.reliability != null ? c.reliability.toFixed(3) : '–'}</div>
                      : null}</td>
                    <td className="num">{c.min != null ? `${money(c.min, 3)} – ${money(c.max, 3)}` : '–'}{c.min != null ? <div className="s">median {money(c.median, 3)}</div> : null}</td>
                    <td className="num sep">{c.hires || <span className="s">–</span>}{c.out ? <span className={pillCls('accent')}>{c.out} out</span> : null}</td>
                    <td className="num">{c.hours ? `${c.hours.toFixed(1)} h` : '–'}</td>
                    <td className="num">{c.hours || c.spent ? money(c.spent) : '–'}</td>
                    <td className="num">{tokens(c.rate)}{c.rate != null
                      ? <div className="s">{c.rate_preset}{c.rate_at ? ` · ${when(c.rate_at)}` : ''}</div>
                      : <div className="s">{c.guess != null ? `unmeasured: guessed ${c.guess.toFixed(0)} TFLOP/s` : 'unmeasured'}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="note mt">A read is the cheapest offer the last charter quote found for the class, kept whenever a voyage is priced; a voyage is a hire in the spend log, its hours from the hire to the release and its rate the tokens a second that voyage measured. As of {when(d.at)}. The key and the seats are set on <a href="/shipyard/constraints">the shipyard's constraints page</a>.</p>
        </>
      )}
    </section>
  );
}
