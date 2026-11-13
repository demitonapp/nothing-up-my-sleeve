// Masaq' Reach, the trading orbital (12 November, Justin: "when clicking masaq reach on the orbitals page
// it opens the url with labs. the url should be .../masaq/ and then show labs in one sub tab and models in
// another sub tab with cards representing the size"). One island, the Reach's views under /masaq:
//   /orbitals/masaq        the Reach's landing of four cards (its Discoveries moved to Demiton's, 13 November)
//   /orbitals/masaq/labs   the labs, filterable by country, purpose and weights, open weights first
//   /orbitals/masaq/research  the research houses: universities, collectives and national infrastructure
//   /orbitals/masaq/models    four size cards; /models/<band> the models in that band
// /masaq and /labs stay as aliases of the Labs view.
// A house opens its own page (/masaq/<country>/<key>), where it says what it is, what it is for and lists
// its ships. /labs and /labs/ships stay as aliases.

import { useState } from 'react';
import { artSrc } from '@/scripts/views/helpers';
import { foreignCountryHtml, foreignShipsHtml, masaqCardsHtml, sizeBandCardsHtml, type Approach } from '@/scripts/views/harbours';
import { BAND, type SizeBand } from '@/scripts/views/bands';
import { cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import SectionNav from '../SectionNav';
import { TabNav } from '../TabNav';
import EmbeddingOntology from './EmbeddingOntology';
import countryNotes from '@/data/country-notes.json';
import '@/styles/country-note.css';

// one entry a country (13 November, Justin: "a two paragraph bill bryson comment on how that country
// approaches language models"): the text is data in frontend/src/data/country-notes.json
const COUNTRY_NOTES = countryNotes as unknown as Record<string, { paragraphs: string[] } | undefined>;

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
  // /orbitals/masaq is the Reach's landing of five cards (12 November); the Labs view is /labs
  const landing = inOrbitals && parts.length === 2;
  const modelsView = (inOrbitals && parts[2] === 'models')
    || (!inOrbitals && isMasaq && parts[1] === 'models')
    || (isAlias && parts[1] === 'ships');
  // the research houses: universities, collectives and national infrastructure, beside the labs
  const researchView = (inOrbitals && parts[2] === 'research')
    || (!inOrbitals && isMasaq && parts[1] === 'research')
    || (isAlias && parts[1] === 'research');
  // the embeddings ontology (12 November, Justin: "add an embedding tab here /orbitals/masaq")
  const embeddingsView = (inOrbitals && parts[2] === 'embeddings') || (!inOrbitals && isMasaq && parts[1] === 'embeddings');
  // A country's pages (13 November, Justin: "cards for each country with a fal image and then the url will be
  // /orbitals/masaq/us/labs and /orbitals/masaq/us/research"): /orbitals/masaq/<cc>/labs, /research and /models;
  // /orbitals/masaq/<cc> alone is its Labs. /orbitals/masaq/labs is the landing of the country cards.
  const RESERVED = ['models', 'labs', 'embeddings', 'research', 'discoveries'];
  const CVIEWS = ['labs', 'research', 'models'];
  const cc = inOrbitals && parts[2] && !RESERVED.includes(parts[2]) && /^[a-z]{2}$/.test(parts[2]) ? parts[2] : '';
  const cview = cc && (parts.length === 3 ? 'labs' : parts.length === 4 && CVIEWS.includes(parts[3]) ? parts[3] : '');
  const countryView = !!cview;
  const detail = (inOrbitals && parts[2] && !RESERVED.includes(parts[2]) && parts[3] && !countryView)
    || (!inOrbitals && parts[0] === 'masaq' && parts[1] && !['models', 'labs', 'embeddings', 'research'].includes(parts[1]) && parts[2])
    || (isAlias && parts[1] && parts[1] !== 'ships' && parts[1] !== 'research');
  const bandSeg = inOrbitals ? parts[3] : parts[2];
  const band = modelsView && bandSeg && BAND(bandSeg) ? (bandSeg as SizeBand) : null;

  // the Labs view's filters: one country, one purpose and one weights choice at a time, each a button
  const [country, setCountry] = useState('');
  const [purpose, setPurpose] = useState('');
  const [weights, setWeights] = useState('');
  const [kind, setKind] = useState('');

  const labsLanding = ours && !landing && !modelsView && !researchView && !embeddingsView && !detail && !countryView;
  const { data, error } = useApi<LabsData>('/api/labs', 60000, ours && !modelsView && !embeddingsView && !detail && !landing);
  // the country cards and pages need the ladder too: each country's models are under it
  const ladder = useApi<any>('/api/ladder', 15000, ours && (modelsView || labsLanding || countryView));
  // the goals that take a model up (s4.model_approaches in Postgres): a model's card shows an existing approach on it
  const approaches = useApi<{ models: Approach[] }>('/api/model-approaches', 60000, ours && (modelsView || countryView));

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
  const countries = [...new Map(viewHouses.map((h) => [h.country, h])).values()];
  const kinds = [...new Set(viewHouses.map((h) => h.kind).filter(Boolean))];
  const info = band ? BAND(band) : null;

  const chip = (on: boolean): string => pillCls(on ? 'accent' : '');

  // The Labs view is by country (13 November, Justin: "cards for each of the countries and then under each
  // country show their labs and the research", then "models should also go under the countries"): a card
  // a country, and under it that country's labs, research houses and outside models. The purpose and
  // weights filters narrow the labs (and so their models); research has neither, so it waits while one is on.
  const groups = (() => {
    const m = new Map<string, { country: string; name: string; labs: House[]; research: House[]; rank: number }>();
    for (const h of houses) {
      if (!m.has(h.country)) m.set(h.country, { country: h.country, name: h.country_name, labs: [], research: [], rank: 9999 });
      const g = m.get(h.country)!;
      (h.category === 'research' ? g.research : g.labs).push(h);
      g.rank = Math.min(g.rank, h.category === 'research' ? 5000 + h.rank : h.rank);
    }
    return [...m.values()].sort((a, b) => a.rank - b.rank);
  })();
  // the ladder keys EleutherAI's models `eleuther`; its house is `eleutherai`
  const labCountry: Record<string, string> = { ...Object.fromEntries(houses.map((h) => [h.key, h.country])), eleuther: houses.find((h) => h.key === 'eleutherai')?.country || '' };
  const modelsOf = (c: string) => (ladder.data ? foreignCountryHtml(ladder.data, c, labCountry, null, approaches.data?.models || []) : null);
  const cg = cc ? groups.find((g) => g.country === cc) || null : null;
  const cLabs = cg ? cg.labs.filter((h) => (!purpose || h.focus === purpose) && (!weights || (weights === 'open') === h.open)).sort((a, b) => Number(b.open) - Number(a.open) || a.rank - b.rank) : [];
  const cResearch = cg ? [...cg.research].sort((a, b) => a.rank - b.rank) : [];
  const cModels = cc ? modelsOf(cc) : null;
  const cOpen = cLabs.filter((h) => h.open);
  const cClosed = cLabs.filter((h) => !h.open);

  return (
    <div {...sectionProps('labs')}>
      <SectionNav />
      <h1>
        {countryView ? (
          <>
            <a className={crumbCls('back')} href="/orbitals/masaq/labs">← countries</a>{' '}
            <img className="flag" src={`/flags/${encodeURIComponent(cc)}.svg`} alt="" /> {cg?.name || COUNTRY_SHORT[cc] || cc}{' '}
            <span className="q">{cview === 'labs' ? 'the labs of this country, open weights first' : cview === 'research' ? 'the research houses of this country: universities, collectives and national infrastructure' : 'the outside models its labs make, biggest first: not ours to build, read on our decks'}</span>
          </>
        ) : (<>
        <a className={crumbCls('back')} href="/orbitals">← orbitals</a>{' '}
        Masaq' Reach{' '}
        <span className="q">
          {landing
            ? 'the trading orbital: the labs and research houses that build the outside ships, and every one of their ships read on our decks'
            : researchView
              ? 'the research houses: universities, collectives and national infrastructure, and the datasets and benchmarks they build'
              : modelsView
                ? 'every outside model in the Reach, in four cards by size: extra small, small, medium and large'
                : embeddingsView
                  ? "the embeddings ontology: what a model's vectors hold, and how the Reach reads them"
                  : 'the countries: open one for its labs, its research houses and the outside models they make'}
        </span>
        </>)}
      </h1>

      {landing ? (
        <div dangerouslySetInnerHTML={{ __html: masaqCardsHtml() }} />
      ) : embeddingsView ? (
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
              <a href="/orbitals/masaq/labs">the houses that built them →</a>
            </p>
            <div className="cards" dangerouslySetInnerHTML={{ __html: band ? foreignShipsHtml(ladder.data, band, approaches.data?.models || []) : sizeBandCardsHtml(ladder.data) }} />
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
          {labsLanding ? (
            <>
              <p className="note labnote">A card a country, in the order of its best house. Open one for its labs, its research houses and the outside models its labs make. {data.as_of_label}.</p>
              <div className="harbours shipyardgrid demitonyard five" role="group" aria-label="the countries">
                {groups.map((g, i) => {
                  const m = modelsOf(g.country);
                  return (
                    <a key={g.country} className={cardCls(true, 'card harbourcard shipyardcard')} href={`/orbitals/masaq/${encodeURIComponent(g.country)}/labs`}>
                      <img className="cardart ship" src={artSrc(`masaq-country-${g.country}`)} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} />
                      <div className="yardplate">
                        <span className="yardnum">{String(i + 1).padStart(2, '0')}</span>
                        <span className="yardrule" aria-hidden="true" />
                        <span className="nm"><img className="flag" src={`/flags/${encodeURIComponent(g.country)}.svg`} alt="" loading="lazy" /> {g.name}</span>
                        <span className="job">{plural(g.labs.length, 'lab', 'labs')} · {plural(g.research.length, 'research house', 'research houses')}{m ? ` · ${plural(m.count, 'model', 'models')}` : ''}</span>
                        <span className="yardopen">open {g.name.toLowerCase()} →</span>
                      </div>
                    </a>
                  );
                })}
              </div>
            </>
          ) : countryView ? (
            !cg ? <div className={emptyCls()}>no country is called {cc} in the Reach.</div> : (
              <>
                {COUNTRY_NOTES[cc]?.paragraphs?.length ? (
                  <div className="countrynote" id="countrynote">
                    {COUNTRY_NOTES[cc]!.paragraphs.map((p, i) => <p key={i}>{p}</p>)}
                  </div>
                ) : null}
                <TabNav
                  id="countrynav"
                  ariaLabel={`${cg.name}'s pages`}
                  items={[
                    { key: 'labs', label: `Labs · ${cg.labs.length}`, href: `/orbitals/masaq/${cc}/labs`, active: cview === 'labs' },
                    { key: 'research', label: `Research · ${cg.research.length}`, href: `/orbitals/masaq/${cc}/research`, active: cview === 'research' },
                    { key: 'models', label: `Models · ${cModels?.count ?? '…'}`, href: `/orbitals/masaq/${cc}/models`, active: cview === 'models' },
                  ]}
                />
                {cview === 'labs' ? (
                  <>
                    <div className="labfilters" role="group" aria-label="filter the labs">
                      <span className="k">purpose</span>
                      <button type="button" className={chip(!purpose)} onClick={() => setPurpose('')}>All</button>
                      {PURPOSES.filter((p) => p.key !== 'research').map((p) => (
                        <button key={p.key} type="button" className={chip(purpose === p.key)} onClick={() => setPurpose(purpose === p.key ? '' : p.key)}>{p.label}</button>
                      ))}
                      <span className="k">weights</span>
                      <button type="button" className={chip(!weights)} onClick={() => setWeights('')}>All</button>
                      <button type="button" className={chip(weights === 'open')} onClick={() => setWeights(weights === 'open' ? '' : 'open')}>Open</button>
                      <button type="button" className={chip(weights === 'closed')} onClick={() => setWeights(weights === 'closed' ? '' : 'closed')}>Closed</button>
                      <span className="s">{cLabs.length} of {cg.labs.length} labs</span>
                    </div>
                    {cOpen.length ? (
                      <>
                        <h2 className="band labgroup">Open weights <span className="q">{cOpen.length} {cOpen.length === 1 ? 'house that publishes' : 'houses that publish'} its weights</span></h2>
                        <div className="labgrid">{cOpen.map(labCard)}</div>
                      </>
                    ) : null}
                    {cClosed.length ? (
                      <>
                        <h2 className="band labgroup">Closed weights <span className="q">{cClosed.length} {cClosed.length === 1 ? 'house that keeps' : 'houses that keep'} its weights</span></h2>
                        <div className="labgrid">{cClosed.map(labCard)}</div>
                      </>
                    ) : null}
                    {!cLabs.length ? <div className={emptyCls()}>no lab of {cg.name} matches this purpose and weight.</div> : null}
                  </>
                ) : cview === 'research' ? (
                  cResearch.length ? <div className="labgrid">{cResearch.map(labCard)}</div> : <div className={emptyCls()}>no research house of {cg.name} is in the Reach yet.</div>
                ) : ladder.error ? (
                  <div className={emptyCls()}>the Reach's models could not be read: {ladder.error}</div>
                ) : !cModels ? (
                  <div className={emptyCls()}>reading the Reach's models…</div>
                ) : cModels.count ? (
                  <div className="cards" dangerouslySetInnerHTML={{ __html: cModels.html }} />
                ) : <div className={emptyCls()}>no outside model of {cg.name} has been read in the Reach yet.</div>}
              </>
            )
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
                <span className="k">kind</span>
                <button type="button" className={chip(!kind)} onClick={() => setKind('')}>All</button>
                {kinds.map((k) => (
                  <button key={k} type="button" className={chip(kind === k)} onClick={() => setKind(kind === k ? '' : k)}>{k}</button>
                ))}
                <span className="s">{shown.length} of {viewHouses.length} houses</span>
              </div>
              <p className="note labnote">The research houses: universities, collectives and national infrastructure that build the datasets, benchmarks and models the labs draw on. The country and kind filters narrow the list; a house opens its own page. The Labs view sets them under their countries.</p>
              {shown.length ? <div className="labgrid">{shown.map(labCard)}</div> : <div className={emptyCls()}>no house matches this country and kind.</div>}
            </>
          )}
          {labsLanding && data.next.length ? (
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
