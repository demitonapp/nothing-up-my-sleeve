// Labs (12 November, Justin: "a new tab on the homepage for labs with the fal images ... the ten top
// producers of models as of today"): the houses that build the outside ships, each a card in the same
// 16:9 ink as a harbour or a class — its plate, its name, its flag, the models it had shipped by the
// reading day, and what the Reach holds of it. The profiles are thorp/labs.py LABS; the plates are
// LABS in backend/thorp/dash/art/generate_art.py, drawn by fal in the one Risso/Drake/Culture brief.

import { artSrc } from '@/scripts/views/helpers';
import { cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { sectionProps, useApi } from '@/lib/useApi';
import SectionNav from '../SectionNav';

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

/** One house's plate: the rank, the name and flag, what it makes, and what the Reach has read of it. A
 *  house with readings opens its lab page; one without opens its own door, so no card lands on an empty
 *  page while its models are still outside the Reach. */
function labCard(h: House) {
  const read = h.readings > 0;
  const href = read ? `/leaderboard/lab/${encodeURIComponent(h.key)}` : h.site;
  const outward = !read && /^https?:/.test(h.site);
  return (
    <a
      key={h.key}
      className={cardCls(true, 'card labcard')}
      href={href}
      target={outward ? '_blank' : undefined}
      rel={outward ? 'noopener' : undefined}
      title={`${h.short}: ${h.flagship.join(', ') || 'the house'}`}
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
      <div className="labmakes">{h.flagship.length ? h.flagship.join(' · ') : 'the house'}</div>
      <div className="lababout">{h.blurb}</div>
      <div className="labfoot">
        <span>{[h.hq, h.founded ? `since ${h.founded}` : ''].filter(Boolean).join(' · ')}</span>
        <span className={pillCls(read ? 'accent' : '')}>{read ? plural(h.readings, 'reading', 'readings') : 'not yet read'}</span>
      </div>
      <div className="labfoot">
        <span>{read ? `${plural(h.models_read, 'model', 'models')} in the Reach` : 'the house’s own door'}</span>
        <span>{read ? 'readings →' : 'site ↗'}</span>
      </div>
    </a>
  );
}

export default function Labs() {
  const { data, error } = useApi<LabsData>('/api/labs', 60000);

  return (
    <div {...sectionProps('labs')}>
      <SectionNav />
      <h1>
        <a className={crumbCls('back')} href="/harbours">← the orbitals</a>{' '}
        The trading orbital{' '}
        <span className="q">
          Masaq' Reach: where every other lab and its ships reside, and what each house had shipped by{' '}
          {data?.as_of_label || '12 November 2026'}
        </span>
      </h1>
      {error ? (
        <div className={emptyCls()}>
          the houses could not be read: {error} (restart <span className="mono">thorp dash</span> if this server
          predates them)
        </div>
      ) : !data ? (
        <div className={emptyCls()}>reading the houses…</div>
      ) : (
        <>
          <p className="note labnote">
            The Reach's own ships, weighed by size band, are on{' '}
            <a href="/harbours/masaq-reach">the harbour page</a>; the ten houses below built them. Ordered by
            the reach of their releases on {data.as_of_label}, a reading rather than a score: the Reach keeps
            the only scores. A card with readings opens that house's lab page, and one without opens its own
            door. The model names are the ones each house had shipped by that day, not everything it has
            announced.
          </p>
          <div className="labgrid">{data.houses.map(labCard)}</div>
          {data.next.length ? (
            <section className={cardCls(false, 'panel labnext')}>
              <h2>
                Also in the Reach{' '}
                <span className="note">
                  the smaller houses whose models the leaderboard already keeps: their ships are read on our
                  decks though they are not among the ten
                </span>
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
                <a href="/harbours/masaq-reach">the Reach’s own harbour →</a>
              </p>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
