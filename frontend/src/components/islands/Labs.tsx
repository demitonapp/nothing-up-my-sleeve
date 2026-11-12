// Masaq' Reach, the trading orbital (12 November, Justin: "when clicking masaq reach on the orbitals page
// it opens the url with labs. the url should be .../masaq/ and then show labs in one sub tab and models in
// another sub tab with cards representing the size"). One island, the Reach's views under /masaq:
//   /masaq/            the labs, filterable by country, purpose and weights, open weights first
//   /masaq/research    the research houses: universities, collectives and national infrastructure
//   /masaq/models      four size cards; /masaq/models/<band> the models in that band
// A house opens its own page (/masaq/<country>/<key>), where it says what it is, what it is for and lists
// its ships. /labs and /labs/ships stay as aliases.

import { useState } from 'react';
import { artSrc } from '@/scripts/views/helpers';
import { foreignShipsHtml, sizeBandCardsHtml } from '@/scripts/views/harbours';
import { BAND, type SizeBand } from '@/scripts/views/bands';
import { cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import SectionNav from '../SectionNav';
import { TabNav } from '../TabNav';
import EmbeddingOntology from './EmbeddingOntology';

interface House {
  rank: number;
  key: string;
  name: string;
  short: string;
  site: string;
  country: string;
  country_name: string;
  hq: string;
  founded: string;
  blurb: string;
  open: boolean;
  focus: string;
  category: string;
  kind: string;
  flagship: string[];
  art: string;
  readings: number;
  models_read: number;
  read: string[];
}

interface NextHouse {
  key: string;
  name: string;
  short: string;
  readings: number;
  models_read: number;
}

interface LabsData {
  as_of: string;
  as_of_label: string;
  houses: House[];
  next: NextHouse[];
}

const plural = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`;

const PURPOSES: { key: string; label: string }[] = [
  { key: 'frontier', label: 'Frontier' },
  { key: 'open fleet', label: 'Open fleet' },
  { key: 'enterprise', label: 'Enterprise' },
  { key: 'agents', label: 'Agents' },
  { key: 'research', label: 'Research labs' },
];

const COUNTRY_SHORT: Record<string, string> = { us: 'US', cn: 'China', fr: 'France', ca: 'Canada', ae: 'UAE', gb: 'UK', au: 'Australia', za: 'South Africa', br: 'Brazil' };

/** One house's plate: rank, name, flag, what it makes, and what the Reach has read of it. Every house has
 *  its own page now, so the card is one door and the page carries the readings link. */
function labCard(h: House) {
  const read = h.readings > 0;
  return (
    <a
      key={h.key}
      className={cardCls(true, 'card labcard')}
      href={`/orbitals/masaq/${encodeURIComponent(h.country)}/${encodeURIComponent(h.key)}`}
      title={`${h.short}: ${h.flagship.join(', ') || h.kind || 'the house'}`}
    >
      {h.art ? (
        <img
          className="cardart ship"
          src={artSrc(h.art)}
          alt=""
          loading="lazy"
          onError={(e) => e.currentTarget.remove()}
        />
      ) : null}
      <div className="labhead">
        <span className="labrank">{String(h.rank).padStart(2, '0')}</span>
        <span className="labname">{h.short}</span>
        {h.country ? (
          <img
            className="flag"
            src={`/flags/${encodeURIComponent(h.country)}.svg`}
            alt={h.country_name}
            title={h.country_name}
            loading="lazy"
          />
        ) : null}
      </div>
      <div className="labmakes">
        {h.flagship.length ? h.flagship.join(' · ') : 'the house'} <span className="s">· {h.focus}</span>
      </div>
      <div className="lababout">{h.blurb}</div>
      <div className="labfoot">
        <span>{[h.kind, h.hq, h.founded ? `since ${h.founded}` : ''].filter(Boolean).join(' · ')}</span>
        <span className={pillCls(read ? 'accent' : '')}>{read ? plural(h.readings, 'reading', 'readings') : 'not yet read'}</span>
      </div>
      <div className="labfoot">
        <span>{read ? `${plural(h.models_read, 'model', 'models')} in the Reach` : 'no ship in the Reach yet'}</span>
        <span>its page →</span>
      </div>
    </a>
  );
}

export default function Labs() {
  const route = useRoute();
  const path = (route.split('?')[0].replace(/^#/, '') || '/').replace(/\/+$/, '') || '/';
  const parts = path.split('/').filter(Boolean);
  // The canonical orbital address is /orbitals/masaq (12 November, Justin: "clicking masaq card in
  // /orbitals ... should open /orbitals/masaq"); /masaq and /labs stay as aliases.
  const inOrbitals = parts[0] === 'orbitals' && parts[1] === 'masaq';
  const isMasaq = inOrbitals || parts[0] === 'masaq';
  const isAlias = parts[0] === 'labs';
  const ours = isMasaq || isAlias;
  const modelsView = (inOrbitals && parts[2] === 'models')
    || (!inOrbitals && isMasaq && parts[1] === 'models')
    || (isAlias && parts[1] === 'ships');
  // the research houses: universities, collectives and national infrastructure, beside the labs
  const researchView = (inOrbitals && parts[2] === 'research')
    || (!inOrbitals && isMasaq && parts[1] === 'research')
    || (isAlias && parts[1] === 'research');
  // the embeddings ontology (12 November, Justin: "add an embedding tab here /orbitals/masaq")
  const embeddingsView = (inOrbitals && parts[2] === 'embeddings') || (!inOrbitals && isMasaq && parts[1] === 'embeddings');
  const detail = (inOrbitals && parts[2] && !['models', 'labs', 'embeddings', 'research'].includes(parts[2]) && parts[3])
    || (!inOrbitals && parts[0] === 'masaq' && parts[1] && !['models', 'labs', 'embeddings', 'research'].includes(parts[1]) && parts[2])
    || (isAlias && parts[1] && parts[1] !== 'ships' && parts[1] !== 'research');
  const bandSeg = inOrbitals ? parts[3] : parts[2];
  const band = modelsView && bandSeg && BAND(bandSeg) ? (bandSeg as SizeBand) : null;

  // the Labs view's filters: one country, one purpose and one weights choice at a time, each a button
  const [country, setCountry] = useState('');
  const [purpose, setPurpose] = useState('');
  const [weights, setWeights] = useState('');
  const [kind, setKind] = useState('');

  const { data, error } = useApi<LabsData>('/api/labs', 60000, ours && !modelsView && !embeddingsView && !detail);
  const ladder = useApi<any>('/api/ladder', 15000, ours && modelsView);

  // a house's own page is LabPage's; the grid and the ships view are this island's
  if (!ours || detail) return null;

  const houses = data?.houses || [];
  const viewHouses = houses.filter((h) => (researchView ? h.category === 'research' : h.category !== 'research'));
  const shown = viewHouses.filter(
    (h) => (!country || h.country === country)
      && (!purpose || h.focus === purpose)
      && (!weights || (weights === 'open') === h.open)
      && (!kind || h.kind === kind),
  );
  const open = shown.filter((h) => h.open);
  const closed = shown.filter((h) => !h.open);
  const countries = [...new Map(viewHouses.map((h) => [h.country, h])).values()];
  const kinds = [...new Set(viewHouses.map((h) => h.kind).filter(Boolean))];
  const info = band ? BAND(band) : null;

  const chip = (on: boolean): string => pillCls(on ? 'accent' : '');

  return (
    <div {...sectionProps('labs')}>
      <SectionNav />
      <h1>
        <a className={crumbCls('back')} href="/orbitals">← orbitals</a>{' '}
        Masaq' Reach{' '}
        <span className="q">
          the trading orbital: the labs and research houses that build the outside ships, and every one of their
          ships read on our decks
        </span>
      </h1>
      <TabNav
        id="masaqnav"
        ariaLabel="Masaq' Reach views"
        items={[
          { key: 'labs', label: 'Labs', href: '/orbitals/masaq', active: !modelsView && !embeddingsView && !researchView },
          { key: 'research', label: 'Research', href: '/orbitals/masaq/research', active: researchView },
          { key: 'models', label: 'Models', href: '/orbitals/masaq/models', active: modelsView },
          { key: 'embeddings', label: 'Embeddings', href: '/orbitals/masaq/embeddings', active: embeddingsView },
          // the Reach's discoveries (12 November): its own page, the head kinds research has named and the census
          { key: 'discoveries', label: 'Discoveries', href: '/orbitals/masaq/discoveries', active: false },
        ]}
      />

      {embeddingsView ? (
        <EmbeddingOntology />
      ) : modelsView ? (
        ladder.error ? (
          <div className={emptyCls()}>the Reach's ships could not be read: {ladder.error}</div>
        ) : !ladder.data ? (
          <div className={emptyCls()}>reading the Reach's ships…</div>
        ) : (
          <>
            <p className="note labnote">
              {info
                ? `The models of ${info.name.toLowerCase()} in the Reach, biggest first: ${info.range}.`
                : 'Every outside model in the Reach, in four cards by size: extra small, small, medium and large. Open a band to see the models in it.'}{' '}
              <a href="/orbitals/masaq">the houses that built them →</a>
            </p>
            <div className="cards" dangerouslySetInnerHTML={{ __html: band ? foreignShipsHtml(ladder.data, band) : sizeBandCardsHtml(ladder.data) }} />
          </>
        )
      ) : error ? (
        <div className={emptyCls()}>
          the houses could not be read: {error} (restart <span className="mono">thorp dash</span> if this server
          predates them)
        </div>
      ) : !data ? (
        <div className={emptyCls()}>reading the houses…</div>
      ) : (
        <>
          <div className="labfilters" role="group" aria-label="filter the houses">
            <span className="k">country</span>
            <button type="button" className={chip(!country)} onClick={() => setCountry('')}>All</button>
            {countries.map((c) => (
              <button
                key={c.country}
                type="button"
                className={chip(country === c.country)}
                title={c.country_name}
                onClick={() => setCountry(country === c.country ? '' : c.country)}
              >
                <img className="flag" src={`/flags/${encodeURIComponent(c.country)}.svg`} alt="" loading="lazy" />
                {COUNTRY_SHORT[c.country] || c.country_name}
              </button>
            ))}
            {!researchView ? (
              <>
                <span className="k">purpose</span>
                <button type="button" className={chip(!purpose)} onClick={() => setPurpose('')}>All</button>
                {PURPOSES.map((p) => (
                  <button
                    key={p.key}
                    type="button"
                    className={chip(purpose === p.key)}
                    onClick={() => setPurpose(purpose === p.key ? '' : p.key)}
                  >{p.label}</button>
                ))}
              </>
            ) : null}
            {researchView ? (
              <>
                <span className="k">kind</span>
                <button type="button" className={chip(!kind)} onClick={() => setKind('')}>All</button>
                {kinds.map((k) => (
                  <button
                    key={k}
                    type="button"
                    className={chip(kind === k)}
                    onClick={() => setKind(kind === k ? '' : k)}
                  >{k}</button>
                ))}
              </>
            ) : (
              <>
                <span className="k">weights</span>
                <button type="button" className={chip(!weights)} onClick={() => setWeights('')}>All</button>
                <button type="button" className={chip(weights === 'open')} onClick={() => setWeights(weights === 'open' ? '' : 'open')}>Open</button>
                <button type="button" className={chip(weights === 'closed')} onClick={() => setWeights(weights === 'closed' ? '' : 'closed')}>Closed</button>
              </>
            )}
            <span className="s">{shown.length} of {viewHouses.length} houses</span>
          </div>
          <p className="note labnote">
            {researchView
              ? `The research houses: universities, collectives and national infrastructure that build the datasets, benchmarks and models the labs draw on. The country and kind filters narrow the list; a house opens its own page.`
              : `The default order puts the open yards first, the closed ones after; the country and purpose filters narrow the list without changing that order. A house opens its own page, with what it is, what it is for and every one of its ships. The order inside a group is the reach of its releases on ${data.as_of_label}, a reading rather than a score.`}
          </p>
          {researchView ? (
            shown.length ? <div className="labgrid">{shown.map(labCard)}</div> : null
          ) : (
            <>
              {open.length ? (
                <>
                  <h2 className="band labgroup">Open weights <span className="q">{open.length} houses that publish their weights</span></h2>
                  <div className="labgrid">{open.map(labCard)}</div>
                </>
              ) : null}
              {closed.length ? (
                <>
                  <h2 className="band labgroup">Closed weights <span className="q">{closed.length} houses that keep their weights</span></h2>
                  <div className="labgrid">{closed.map(labCard)}</div>
                </>
              ) : null}
            </>
          )}
          {!shown.length ? <div className={emptyCls()}>{researchView ? 'no house matches this country and kind.' : 'no house matches this country, purpose and weight.'}</div> : null}
          {data.next.length ? (
            <section className={cardCls(false, 'panel labnext')}>
              <h2>
                Also in the Reach{' '}
                <span className="note">the houses whose models the leaderboard keeps beside the ones above</span>
              </h2>
              <p>
                {data.next.map((x, i) => (
                  <span key={x.key}>
                    {i ? ' · ' : ''}
                    <a href={`/leaderboard/lab/${encodeURIComponent(x.key)}`}>{x.short || x.name}</a>
                    {x.readings ? <span className="s"> ({plural(x.readings, 'reading', 'readings')})</span> : null}
                  </span>
                ))}
                <span className="s"> · </span>
                <a href="/orbitals/masaq/models">every model in the Reach →</a>
              </p>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
