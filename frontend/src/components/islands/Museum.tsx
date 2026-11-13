// Sleeper Service, the museum Orbital (13 November, Justin: "This UNESCO's Memory of the World register deserves it's own
// Orbital", "it's a museum orbital and must reflect that", "Yes, build it"). UNESCO's Memory of the World register
// hung as a museum: you walk it rather than filter it.
//
//   /orbitals/sleeper-service                    the entrance hall: the wings now open, the exhibitions, the floor plan
//   /orbitals/sleeper-service/wings/<key>        a wing: its wall text and its exhibits, each a label
//   /orbitals/sleeper-service/exhibits/<key>     one exhibit's label, its lenders and the wings it hangs in
//   /orbitals/sleeper-service/lenders            the Lenders room: who holds each exhibit
//
// The floor plan runs by era, and the threshold is drawn across it at 1930, the period fleet's cutoff: the wing
// past it is sealed. Exhibits carry no pictures (the objects are their lenders'); the wings and rooms carry the
// plates. The rows are thorp/museum.py's, from s4.museum_*; every address is pre-rendered from data/museum.json.

import { useEffect, useState } from 'react';
import { cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi, routePath } from '@/lib/useApi';
import { artSrc, flagImg } from '@/scripts/views/helpers';

export const MEMORY = '/orbitals/sleeper-service';
// named for the Sleeper Service, the General Systems Vehicle of Banks' Excession that turned its vast spaces into
// tableaux, scenes of the past held perfectly still (13 November, Justin chose it: "the name has to banks culture
// series inspired")

interface Wing {
  key: string; kind: 'era' | 'country' | 'theme'; name: string; blurb: string; description: string;
  year_from: number | null; year_to: number | null; sealed: boolean; country: string; exhibits: string[];
}
interface Lender { key: string; name: string; city: string; country: string; country_name: string; kind: string; site: string; about: string; exhibits: string[] }
interface Exhibit {
  key: string; title: string; register: string; inscribed: number | null; year_from: number; year_to: number | null;
  dates: string; medium: string; languages: string[]; countries: string[]; lenders: string[]; themes: string[];
  label: string; significance: string; conservation: string; access: string; note: string;
  sources: { label: string; href: string }[]; wings: string[]; era: string | null; sealed: boolean;
}
interface MuseumData { name: string; source: string; threshold: number | null; wings: Wing[]; exhibits: Exhibit[]; lenders: Lender[] }

const wingHref = (k: string): string => `${MEMORY}/wings/${k}`;
const exhibitHref = (k: string): string => `${MEMORY}/exhibits/${k}`;
const plate = (k: string): string => artSrc(`sleeper-service-wing-${k}`);
const years = (w: Wing): string => (w.year_from == null ? '' : `${w.year_from < 0 ? `${-w.year_from} BCE` : w.year_from}–${w.year_to ?? 'today'}`);
const REGISTER: Record<string, string> = { international: 'International Register', 'asia-pacific': 'Asia-Pacific Register', australian: 'Australian Register' };

/** A wing as a door: its plate, its kind and its exhibits. */
function WingDoor({ w, big = false }: { w: Wing; big?: boolean }) {
  const kind = w.kind === 'era' ? (w.sealed ? 'sealed · beyond the threshold' : years(w)) : w.kind === 'country' ? 'a country wing' : 'an exhibition';
  return (
    <a className={`discdoor${w.sealed ? ' sealedwing' : ''}`} href={wingHref(w.key)}>
      <img src={plate(w.key)} alt="" loading="lazy" style={big ? { height: 300 } : undefined} onError={(e) => { e.currentTarget.style.display = 'none'; }} />
      <div className="db">
        <span className="dk">{kind} · {w.exhibits.length ? `${w.exhibits.length} ${w.exhibits.length === 1 ? 'exhibit' : 'exhibits'}` : 'not yet hung'}</span>
        <b>{w.name}</b>
        <p>{w.blurb}</p>
      </div>
    </a>
  );
}

/** An exhibit's label, as a museum hangs it beside the object: title, dates and medium, our text, the credit line. */
function Placard({ e, m, full = false }: { e: Exhibit; m: MuseumData; full?: boolean }) {
  const lenders = e.lenders.map((k) => m.lenders.find((x) => x.key === k)).filter(Boolean) as Lender[];
  const closed = e.access === 'closed at the community’s request' || e.access === 'closed';
  return (
    <article className={`placard${e.sealed ? ' sealed' : ''}`} id={e.key}>
      <h3>{full ? e.title : <a href={exhibitHref(e.key)}>{e.title}</a>}</h3>
      <div className="pmeta">{e.dates} · {e.medium}{e.languages.length ? ` · ${e.languages.join(', ')}` : ''}</div>
      {closed ? <p className="s">Not on display, at the community's request.</p> : (
        <>
          <p>{e.label}</p>
          <p className="pwhy">{e.significance}</p>
        </>
      )}
      <div className="pcredit">Lent by {lenders.map((x, i) => (
        <span key={x.key}>{i ? (i === lenders.length - 1 ? ' and ' : ', ') : ''}<a href={`${MEMORY}/lenders#${x.key}`}>{x.name}</a>{x.city ? `, ${x.city}` : ''}</span>
      ))}</div>
      <div className="ppills">
        <span className={pillCls('')}>{REGISTER[e.register] || e.register}{e.inscribed ? ` · ${e.inscribed}` : ''}</span>
        <span className={pillCls(e.conservation === 'digitised' ? 'good' : '')} title="conservation: whether it can be read, or only seen">{e.conservation || 'not yet checked'}</span>
        <span className={pillCls(e.access === 'open' ? '' : 'accent')} title="access">{e.access === 'open' ? 'open access' : e.access}</span>
        {e.sealed ? <span className={pillCls('accent')}>sealed wing</span> : null}
      </div>
      {e.note ? <p className="pnote">{e.note}</p> : null}
      {full ? (
        <>
          <p className="pnote">Hangs in {e.wings.map((k, i) => {
            const w = m.wings.find((x) => x.key === k);
            return w ? <span key={k}>{i ? ', ' : ''}<a href={wingHref(k)}>{w.name}</a></span> : null;
          })}.</p>
          <p className="pnote">Sources: {e.sources.map((s, i) => <span key={s.href}>{i ? '; ' : ''}<a href={s.href} target="_blank" rel="noreferrer">{s.label}</a></span>)}</p>
        </>
      ) : null}
    </article>
  );
}

/** The floor plan: every era wing in order, with the threshold drawn between the last open wing and the sealed one. */
function FloorPlan({ m }: { m: MuseumData }) {
  const eras = m.wings.filter((w) => w.kind === 'era');
  return (
    <div className="floorplan" role="list" aria-label="the floor plan, by era">
      {eras.map((w) => (
        <div role="listitem" key={w.key} style={{ display: 'contents' }}>
          {w.sealed ? <div className="threshold" title={`the threshold: ${m.threshold}`}><span>{m.threshold}</span></div> : null}
          <a className={`room${w.sealed ? ' sealed' : ''}${w.exhibits.length ? '' : ' empty'}`} href={wingHref(w.key)}>
            <b>{w.name}</b>
            <span className="s">{years(w)}</span>
            <span className="s">{w.exhibits.length ? `${w.exhibits.length} hung` : 'not yet hung'}</span>
          </a>
        </div>
      ))}
    </div>
  );
}

function Hall({ m }: { m: MuseumData }) {
  const country = m.wings.filter((w) => w.kind === 'country');
  const themes = m.wings.filter((w) => w.kind === 'theme');
  return (
    <>
      <h1>
        <a className={crumbCls('back')} href="/orbitals">← Orbitals</a>{' '}
        {m.name}{' '}
        <span className="q">the museum Orbital: the documents the world agreed to keep ({m.source}), hung by era, with the threshold drawn across the floor at {m.threshold}. Every label is ours; every object is on loan from the library or archive that holds it</span>
      </h1>
      <section className={cardCls(false, 'panel museumhall')}>
        <img className="hallplate" src={artSrc('sleeper-service-hall')} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
        <div>
          <h2>The entrance hall <span className="note">{m.exhibits.length} exhibits hung, from {m.lenders.length} lenders</span></h2>
          <p>Walk the floor plan from the Ancient Hall to the Sealed Wing. The rooms before {m.threshold} hold what a period ship may know; the Sealed Wing holds what it must not. When the guided tour is built, every ship will walk these rooms and be asked about each exhibit: a room it recognises before the threshold is knowledge, one it recognises beyond it is a leak.</p>
          <p className="note">Open now: the Australian Wing, two exhibitions and the Lenders room. Still to come: the rest of the International Register's 570 inscriptions, hung by era, and the guided tour.</p>
        </div>
      </section>
      <h2 className="mt">Now open</h2>
      <div className="discdoors">
        {country.map((w) => <WingDoor w={w} key={w.key} big />)}
        <a className="discdoor" href={`${MEMORY}/lenders`}>
          <img src={artSrc('sleeper-service-lenders')} alt="" loading="lazy" style={{ height: 300 }} onError={(e) => { e.currentTarget.style.display = 'none'; }} />
          <div className="db">
            <span className="dk">a room · {m.lenders.length} lenders</span>
            <b>The Lenders room</b>
            <p>The libraries, archives and museums that hold the exhibits, and what each one lends.</p>
          </div>
        </a>
      </div>
      <h2 className="mt">The exhibitions <span className="note">curated routes through the wings</span></h2>
      <div className="discdoors">{themes.map((w) => <WingDoor w={w} key={w.key} />)}</div>
      <h2 className="mt">The floor plan <span className="note">every wing by era; the threshold at {m.threshold}</span></h2>
      <FloorPlan m={m} />
    </>
  );
}

function WingPage({ m, w }: { m: MuseumData; w: Wing }) {
  const items = w.exhibits.map((k) => m.exhibits.find((e) => e.key === k)).filter(Boolean) as Exhibit[];
  return (
    <>
      <h1>
        <a className={crumbCls('back')} href={MEMORY}>← {m.name}</a>{' '}
        {w.name}{' '}
        <span className="q">{w.kind === 'era' ? years(w) : w.kind === 'country' ? 'a country wing' : 'an exhibition'}: {w.blurb}</span>
      </h1>
      <section className={cardCls(false, `panel museumhall${w.sealed ? ' sealedwing' : ''}`)}>
        <img className="hallplate" src={plate(w.key)} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
        <div>
          <h2>The wall text {w.sealed ? <span className={pillCls('accent')}>sealed: beyond {m.threshold}</span> : null}</h2>
          <p>{w.description}</p>
        </div>
      </section>
      {w.kind === 'era' ? <FloorPlan m={m} /> : null}
      {items.length ? <div className="placards">{items.map((e) => <Placard e={e} m={m} key={e.key} />)}</div>
        : <div className={emptyCls()}>Nothing hangs here yet: this wing opens when the International Register is hung.</div>}
    </>
  );
}

function ExhibitPage({ m, e }: { m: MuseumData; e: Exhibit }) {
  const era = m.wings.find((w) => w.key === e.era);
  return (
    <>
      <h1>
        <a className={crumbCls('back')} href={era ? wingHref(era.key) : MEMORY}>← {era ? era.name : m.name}</a>{' '}
        {e.title}{' '}
        <span className="q">{e.dates} · {e.medium}</span>
      </h1>
      <div className="placards single"><Placard e={e} m={m} full /></div>
    </>
  );
}

function Lenders({ m }: { m: MuseumData }) {
  return (
    <>
      <h1>
        <a className={crumbCls('back')} href={MEMORY}>← {m.name}</a>{' '}
        The Lenders room{' '}
        <span className="q">every exhibit is on loan from the library, archive or museum that holds it; the credit line on each label names them</span>
      </h1>
      <div className="lenders">
        {m.lenders.map((x) => (
          <section className={cardCls(false, 'panel')} id={x.key} key={x.key}>
            <h2>{x.country ? <span dangerouslySetInnerHTML={{ __html: flagImg(x.country, x.country_name) }} /> : null} {x.name} <span className="note">{x.kind} · {x.city}</span></h2>
            <p>{x.about}</p>
            <p className="note">Lends {x.exhibits.map((k, i) => {
              const e = m.exhibits.find((y) => y.key === k);
              return e ? <span key={k}>{i ? '; ' : ''}<a href={exhibitHref(k)}>{e.title}</a></span> : null;
            })}{x.site ? <> · <a href={x.site} target="_blank" rel="noreferrer">its own site</a></> : null}</p>
          </section>
        ))}
      </div>
    </>
  );
}

export default function Museum() {
  const [path, setPath] = useState<string | null>(null);
  useEffect(() => { setPath(routePath()); }, []);
  const on = path != null && (path === MEMORY || path.startsWith(`${MEMORY}/`));
  const { data: m, error } = useApi<MuseumData>(on ? '/api/museum' : null, 300000);
  if (!on) return null;
  const [kind, key] = path.slice(MEMORY.length).split('/').filter(Boolean);
  let body;
  if (error) body = <div className={emptyCls()}>Sleeper Service could not be read: {error}. Restart <span className="mono">thorp dash</span> if it was just changed.</div>;
  else if (!m) body = <div className={emptyCls()}>opening the doors…</div>;
  else if (kind === 'wings' && key) {
    const w = m.wings.find((x) => x.key === key);
    body = w ? <WingPage m={m} w={w} /> : <div className={emptyCls()}>no wing {key}</div>;
  } else if (kind === 'exhibits' && key) {
    const e = m.exhibits.find((x) => x.key === key);
    body = e ? <ExhibitPage m={m} e={e} /> : <div className={emptyCls()}>no exhibit {key}</div>;
  } else if (kind === 'lenders') body = <Lenders m={m} />;
  else body = <Hall m={m} />;
  return <div {...sectionProps('sleeper-service')}>{body}</div>;
}
