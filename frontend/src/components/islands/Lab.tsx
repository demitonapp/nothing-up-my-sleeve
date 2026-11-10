// One lab (#/leaderboard/lab/<key>; /api/lab): the maker of a family of outside models, its models,
// and its five best and five worst readings on the rungs of the four chains. A typed client island;
// it reads the lab key from the route.

import { cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { fmtParams, signed } from '@/lib/format';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';

interface LabModel { model: string; label: string; params: number | null; competitor?: boolean; ladder?: boolean }
interface LabRow {
  model: string; label: string; test?: string; name: string; chain: string; rung?: string | null;
  lift: number | null; score: number | null; performed?: boolean;
  field_median: number | null; field_n: number; beats: number; standing: number;
}
interface LabData {
  key: string; name: string; url?: string | null; readings: number;
  models: LabModel[]; best: LabRow[]; worst: LabRow[]; labs: { key: string; name: string }[];
}

export default function Lab() {
  const route = useRoute();
  const key = decodeURIComponent((route.split('/')[3] || '').trim());
  const { data: d, error } = useApi<LabData>(key ? `/api/lab?lab=${encodeURIComponent(key)}` : null, 60000);

  return (
    <div {...sectionProps('lab')}>
      <h1>
        <a className={crumbCls('back')} href="/leaderboard">← leaderboard</a>{' '}
        <span>{d?.name || key || 'lab'}</span>{' '}
        <span className="q">
          {(d?.labs || []).filter((x) => x.key !== d?.key).map((x, i) => (
            <span key={x.key}>{i ? ' · ' : ''}<a href={`/leaderboard/lab/${x.key}`}>{x.name}</a></span>
          ))}
        </span>
      </h1>
      {error ? <div className={emptyCls()}>the lab could not be read: {error}</div>
        : !d ? <div className={emptyCls()}>reading the lab…</div>
        : (
          <>
            <section className={cardCls(false, 'panel')}>
              <div className="rungover">
                <div>
                  <div className="k">lab</div>
                  <div><b>{d.name}</b>{d.url ? <div className="s"><a href={d.url} target="_blank" rel="noopener">{d.url.replace(/^https?:\/\//, '')}</a></div> : null}</div>
                </div>
                <div>
                  <div className="k">its models</div>
                  <div>
                    {d.models.length ? d.models.map((m) => (
                      <div key={m.model}>
                        <a href={`/leaderboard/competitor/${encodeURIComponent(m.model)}`}>{m.label}</a>{' '}
                        <span className="s">{fmtParams(m.params ?? null)}</span>
                        {m.competitor ? <> <span className={pillCls('blue')}>2–4B</span></> : null}
                        {m.ladder ? <> <span className={pillCls('')}>ladder</span></> : null}
                      </div>
                    )) : '–'}
                  </div>
                </div>
                <div>
                  <div className="k">readings</div>
                  <div><b>{d.readings}</b><div className="s">every rung of the four chains, for each of its models</div></div>
                </div>
              </div>
            </section>
            <LabTable id="labbest" title="Its best" note="the five readings where its models most beat the other labs' models on the same test" rows={d.best} />
            <section className={cardCls(false, 'panel')}>
              <h2>Its worst <span className="note">the five readings where its models most trail the other labs' models on the same test</span></h2>
              <div className="scroll"><LabTableInner id="labworst" rows={d.worst} /></div>
              <p className="note mt">Every rung of the four chains (the chain grades, s4.outside_readings), read for each of the lab's models. A reading's standing is its lift less the median of the other labs' models on that test, over their spread (σ, the standard deviation), so a test where every model lifts 2.0 does not crowd out one where the field lifts 0.1. "Beats" counts the other labs' models it lifts higher than. ✓ performed: lift 0.1 and two in three right.</p>
            </section>
          </>
        )}
    </div>
  );
}

function LabTable({ id, title, note, rows }: { id: string; title: string; note: string; rows: LabRow[] }) {
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>{title} <span className="note">{note}</span></h2>
      <div className="scroll"><LabTableInner id={id} rows={rows} /></div>
    </section>
  );
}

function LabTableInner({ id, rows }: { id: string; rows: LabRow[] }) {
  return (
    <table id={id} data-nosort>
      <thead><tr><th>#</th><th>model</th><th>test</th><th>rung</th><th>lift</th><th title="the median lift of the other labs' models on this test">field median</th><th title="the other labs' models it lifts higher than">beats</th><th title="lift less the field median, over the field's spread">standing</th><th>share right</th><th></th></tr></thead>
      <tbody>
        {rows.length ? rows.map((r, i) => (
          <tr key={`${r.model}-${r.test || r.name}-${i}`}>
            <td>{i + 1}</td>
            <td><a href={`/leaderboard/competitor/${encodeURIComponent(r.model)}`}><b>{r.label}</b></a></td>
            <td>{r.name}<div className="s">{r.chain}</div></td>
            <td className="s">{r.rung || ''}</td>
            <td className="num">{signed(r.lift)}</td>
            <td className="num s">{signed(r.field_median)}</td>
            <td className="num s">{r.beats} of {r.field_n}</td>
            <td className="num"><span className={pillCls(r.standing >= 0 ? 'good' : 'bad')}>{r.standing >= 0 ? '+' : ''}{r.standing.toFixed(2)}σ</span></td>
            <td className="num">{r.score == null ? '–' : Math.round(100 * r.score) + '%'}</td>
            <td>{r.performed ? '✓' : ''}</td>
          </tr>
        )) : <tr><td colSpan={10} className="s">not enough readings yet</td></tr>}
      </tbody>
    </table>
  );
}
