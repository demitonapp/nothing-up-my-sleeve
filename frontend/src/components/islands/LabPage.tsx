// One house in Masaq' Reach (12 November, Justin: "each lab will have their own page with a description of
// them, their purpose and all their ships"). It answers /labs/<key>; the API is thorp/labs.py payload, the
// same profile the Labs grid draws, plus the foreign registry's fleet for this house.

import { artSrc } from '@/scripts/views/helpers';
import { big } from '@/lib/format';
import { btnCls, cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import LabModels from './LabModels';
import { TabNav } from '../TabNav';

interface FleetShip {
  key: string;
  model: string;
  label: string;
  params: number | null;
  read: boolean;
  chained: boolean;
}

interface LabData {
  key: string;
  name: string;
  short: string;
  site: string;
  country: string;
  country_name: string;
  hq: string;
  founded: string;
  blurb: string;
  description: string;
  purpose: string;
  flagship: string[];
  art: string;
  open: boolean;
  focus: string;
  funding: {
    government: number; private: number; kind: string; note: string; basis: string;
    rounds: { date: string; round: string; amount: string; valuation: string; investors: string }[];
  };
  fleet: FleetShip[];
  readings: number;
}

/** One ship of the house in the Reach, with the two actions a model needs (12 November, Justin: "we should
 *  be able to click on their models and add it to the chat terminal and run experiments on it"): chat hands
 *  the model to the console by name, experiments opens its tests and readings on the competitor page. */

/** The funding split: a bar and the numbers, with what the two sides are and the basis. It is an estimate
 *  from public reporting, said so on the page, not an audited cap table. */
function Funding({ f }: { f?: LabData['funding'] }) {
  const fund = f || { government: 0, private: 100, kind: 'private', note: '', basis: '', rounds: [] };
  const gov = Math.max(0, Math.min(100, fund.government));
  const priv = Math.max(0, Math.min(100, fund.private));
  return (
    <>
      <h2 className="mt">Its funding</h2>
      <div className="fundbar" role="img" aria-label={`government ${gov}%, private ${priv}%`}>
        <i className="gov" style={{ width: `${gov}%` }} />
        <i className="priv" style={{ width: `${priv}%` }} />
      </div>
      <div className="fundlegend">
        <span>Government {gov}%</span>
        <span>Private {priv}%</span>
        <span className="s">{fund.kind}</span>
      </div>
      <h3>Funding rounds</h3>
      {(fund.rounds || []).length ? (
        <div className="scroll">
          <table className="fundrounds">
            <thead><tr><th>date</th><th>round</th><th>raised</th><th>valuation</th><th>lead investors</th></tr></thead>
            <tbody>
              {(fund.rounds || []).map((r, i) => (
                <tr key={`${r.date}-${r.round}-${i}`}>
                  <td className="mono">{r.date}</td>
                  <td>{r.round}</td>
                  <td className="num">{r.amount || '—'}</td>
                  <td className="num">{r.valuation || '—'}</td>
                  <td className="s">{r.investors || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="note">No disclosed funding rounds.</p>}
      {fund.note ? <p className="note">{fund.note}</p> : null}
      {fund.basis ? <p className="note">{fund.basis}</p> : null}
    </>
  );
}

function shipCard(s: FleetShip) {
  // the console keys a model by its harbour key (phi-4-mini-3-8b-instruct), not the Hub id; the
  // competitor page keys by the Hub id, so the two actions use the different names they need
  const chatKey = s.key;
  const model = s.model || s.key;
  return (
    <div key={s.key} className={cardCls(false, 'card classcard labship')}>
      <img className="cardart ship" src={artSrc(s.key)} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} />
      <div className="top"><span className="preset">{s.params ? big(s.params) : '–'}</span><span className="nm">{s.label}</span></div>
      <div className="foot">
        <span>{s.read ? 'read on our decks' : 'not read yet'}</span>
        <span className={pillCls(s.chained ? 'good' : '')}>{s.chained ? 'chain-graded' : 'foreign'}</span>
      </div>
      <div className="labshipactions">
        <button
          type="button"
          className={btnCls('outline')}
          title={`add ${s.label} to the chat console`}
          onClick={() => window.dispatchEvent(new CustomEvent('thorp:chat', { detail: { model: chatKey } }))}
        >chat</button>
        <a
          className={btnCls('ghost')}
          href={`/leaderboard/competitor/${encodeURIComponent(model)}`}
          title={`open ${s.label}'s tests and readings`}
        >experiments →</a>
        <a className={btnCls('ghost')} href={`/foreign/${encodeURIComponent(s.key)}`}>readings →</a>
      </div>
    </div>
  );
}

export default function LabPage() {
  const route = useRoute();
  const path = (route.split('?')[0].replace(/^#/, '') || '/').replace(/\/+$/, '') || '/';
  const parts = path.split('/').filter(Boolean);
  // A house's address is /masaq/<country>/<key> (12 November, Justin: "/labs/arcee ... will move to
  // /masaq/us/arcee"); the old /labs/<key> stays as an alias.
  const inOrbitals = parts[0] === 'orbitals' && parts[1] === 'masaq';
  const keyIndex = inOrbitals ? 3 : parts[0] === 'masaq' ? 2 : parts[0] === 'labs' ? 1 : -1;
  const key = keyIndex >= 0 && parts[keyIndex] && !['models', 'labs', 'ships'].includes(parts[keyIndex])
    ? decodeURIComponent(parts[keyIndex]) : '';
  const tab = parts[parts.length - 1] === 'models' ? 'models' : 'overview';
  const base = keyIndex >= 0 && key ? '/' + parts.slice(0, keyIndex + 1).join('/') : '';
  const { data: d, error } = useApi<LabData>(key ? `/api/lab?lab=${encodeURIComponent(key)}` : null, 60000);

  if (!key) return null;
  const fleet = d?.fleet || [];

  return (
    <div {...sectionProps('lab-house')}>
      <h1>
        <a className={crumbCls('back')} href="/orbitals/masaq">← the labs</a>{' '}
        {d?.country ? (
          <img className="flag" src={`/flags/${encodeURIComponent(d.country)}.svg`} alt={d.country_name} title={d.country_name} />
        ) : null}{' '}
        {d?.short || key}{' '}
        <span className="q">{d?.blurb || 'a house in Masaq’ Reach'}</span>
      </h1>
      <TabNav
        id="labnav"
        ariaLabel="the house's views"
        items={[
          { key: 'overview', label: 'Overview', href: base, active: tab === 'overview' },
          { key: 'models', label: 'Models', href: `${base}/models`, active: tab === 'models' },
        ]}
      />
      {error ? (
        <div className={emptyCls()}>this house could not be read: {error}</div>
      ) : !d ? (
        <div className={emptyCls()}>reading the house…</div>
      ) : (
        <>
          {tab === 'overview' ? (
            <>
          <div className="labprofile">
            {d.art ? <img className="labhero" src={artSrc(d.art)} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} /> : null}
            <section className={cardCls(false, 'panel')}>
              <h2>The house <span className="note">{d.country_name} · {d.hq} · since {d.founded}</span></h2>
              <p>{d.description || d.blurb}</p>
              <h2 className="mt">Its purpose</h2>
              <p>{d.purpose || 'to build and publish the models the Reach reads.'}</p>
              <Funding f={d.funding} />
              <div className="labmeta">
                <span className={pillCls(d.open ? 'good' : '')}>{d.open ? 'open weights' : 'closed weights'}</span>
                <span className={pillCls('')}>{d.focus}</span>
                <a href={d.site} target="_blank" rel="noopener">the house’s own door ↗</a>
                {d.readings ? <a href={`/leaderboard/lab/${encodeURIComponent(d.key)}`}>its readings in the Reach →</a> : <span className="s">no chain readings yet</span>}
              </div>
            </section>
          </div>
          <section className={cardCls(false, 'panel')}>
            <h2>
              Its ships{' '}
              <span className="note">
                every ship of this house the Reach knows, read or not: {fleet.length} in the Reach
              </span>
            </h2>
            {fleet.length ? (
              <div className="cards">{fleet.map(shipCard)}</div>
            ) : (
              <p className="note">
                No ship of this house is in the Reach yet; the fleet it has shipped is below, and its page fills
                as the Reach pulls one.
              </p>
            )}
            <h2 className="mt">
              The fleet it has shipped{' '}
              <span className="note">the models it had shipped by 12 November 2026</span>
            </h2>
            <div className="labflagship">
              {d.flagship.length ? d.flagship.map((x) => <span key={x} className={pillCls('accent')}>{x}</span>) : <span className="s">no model named yet</span>}
            </div>
            <p className="labmeta">
              <a href="/orbitals/masaq/models">every model in the Reach →</a>{' '}
              <span className="s">or</span>{' '}
              <a href="/orbitals/masaq">back to the houses →</a>
            </p>
          </section>
            </>
          ) : (
            <LabModels lab={d.key} ships={fleet} />
          )}
        </>
      )}
    </div>
  );
}
