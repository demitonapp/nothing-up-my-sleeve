// The field's discoveries on two axes, and Demiton's discoveries folded under them (13 November, Justin: "a card for
// the two axis and then when clicking in we have cards for the level below them", then "this page should only have
// the 2 axis cards with a fal image and then all the other content should be folded into it at a lower level").
//
// The landing is the two axis cards. An axis page shows its categories as cards. A category page shows our own
// sections placed there (the jobs, the stars, the head kinds, the traits, the skills ladder and its four doors, the
// tests, chaining two facts), then the field's discoveries. The data is lib/fieldMap.ts. Links are plain addresses
// under Demiton's discoveries, which the Discoveries island follows in place.

import { crumbCls, emptyCls, pillCls, cardCls } from '@/lib/ui';
import { DEMITON_DISCOVERIES as DB } from '@/lib/discoveryPaths';
import { AXES, axisBySlug, discoveriesIn, oursIn, slugOf, type MapAxis, type OurWork } from '@/lib/fieldMap';

const axisHref = (a: MapAxis): string => `${DB}/${a.slug}`;
const otherAxis = (a: MapAxis): MapAxis => AXES.find((x) => x.key !== a.key) as MapAxis;
// each axis's plate (backend/thorp/dash/art/generate_art.py: discoveries-kind-of-claim, discoveries-object-of-study)
const artOf = (a: MapAxis): string => `/art/discoveries-${a.slug}.png`;

/** The landing: the two axis cards, each with its plate and its categories. */
export function AxisDoors() {
  return (
    <div className="discdoors">
      {AXES.map((a) => (
        <a className="discdoor" href={axisHref(a)} key={a.key}>
          <img src={artOf(a)} alt="" loading="lazy" style={{ height: 300 }} />
          <div className="db">
            <span className="dk">Axis {a.n} · {a.categories.length} categories</span>
            <b>{a.name}</b>
            <p>{a.question} {a.about}</p>
            <p>{a.categories.map((c) => <span className={pillCls('')} key={c.key} style={{ marginRight: 4, display: 'inline-block', marginTop: 4 }}>{c.name}</span>)}</p>
          </div>
        </a>
      ))}
    </div>
  );
}

/** Our own sections in a category, as door cards (the four doors keep their plates). */
function OursCards({ ours }: { ours: OurWork[] }) {
  return (
    <div className="discdoors">
      {ours.map((o) => (
        <a className="discdoor" href={o.href} key={o.key}>
          {o.image ? <img src={o.image} alt="" loading="lazy" /> : null}
          <div className="db">
            <span className="dk">from our fleet</span>
            <b>{o.title}</b>
            <p>{o.about}</p>
          </div>
        </a>
      ))}
    </div>
  );
}

/** An axis (its categories as cards) or one category of it (our sections there, then the field's discoveries). */
export function FieldMapView({ slug, cat }: { slug: string; cat: string | null }) {
  const axis = axisBySlug(slug);
  if (!axis) return <div className={emptyCls()}>no such axis: {slug}</div>;
  const category = cat ? axis.categories.find((c) => slugOf(c) === cat || c.key === cat) || null : null;
  const other = otherAxis(axis);

  if (cat && !category) {
    return (
      <>
        <h1><a className={crumbCls('back')} href={axisHref(axis)}>← {axis.name.toLowerCase()}</a> Not found</h1>
        <div className={emptyCls()}>{axis.name} has no category {cat}</div>
      </>
    );
  }

  if (category) {
    const found = discoveriesIn(axis, category.key);
    const ours = oursIn(axis, category.key);
    return (
      <>
        <h1>
          <a className={crumbCls('back')} href={axisHref(axis)}>← {axis.name.toLowerCase()}</a>{' '}
          {category.name}{' '}
          <span className="q">{category.question} {category.about}</span>
        </h1>
        {ours.length ? (
          <section className={cardCls(false, 'panel')}>
            <h2>From our fleet <span className="note">what Nothing up my sleeve has found here: open one for its readings</span></h2>
            <OursCards ours={ours} />
          </section>
        ) : null}
        <section className={cardCls(false, 'panel')}>
          <h2>{found.length} discover{found.length === 1 ? 'y' : 'ies'} in the field <span className="note">each with its source; the tag is where it sits on the other axis ({other.name.toLowerCase()}), and a link marks where Nothing up my sleeve measures the same thing</span></h2>
          {found.length ? (
            <div className="domainskills">
              {found.map((d) => {
                const otherKey = axis.key === 'kind' ? d.object : d.kind;
                const otherCat = other.categories.find((c) => c.key === otherKey);
                return (
                  <div className={`skill${d.thorp ? ' measured' : ''}`} key={d.key} id={d.key}>
                    <b>{d.title}</b>
                    <span>{d.finding}</span>
                    <em>
                      {d.source} · <a href={`${axisHref(other)}/${otherCat ? slugOf(otherCat) : otherKey}`}>{otherCat?.name || otherKey}</a>
                      {d.thorp ? <> · in Nothing up my sleeve: <a href={d.thorp.href}>{d.thorp.label}</a></> : null}
                    </em>
                  </div>
                );
              })}
            </div>
          ) : <div className={emptyCls()}>nothing is placed here yet</div>}
        </section>
      </>
    );
  }

  return (
    <>
      <h1>
        <a className={crumbCls('back')} href={DB}>← discoveries</a>{' '}
        {axis.name}{' '}
        <span className="q">{axis.question} {axis.about}</span>
      </h1>
      <div className="discdoors">
        {axis.categories.map((c) => {
          const found = discoveriesIn(axis, c.key);
          const ours = oursIn(axis, c.key);
          return (
            <a className="discdoor" href={`${axisHref(axis)}/${slugOf(c)}`} key={c.key}>
              <div className="db">
                <span className="dk">{found.length} in the field{ours.length ? ` · ${ours.length} of ours` : ''}</span>
                <b>{c.name}</b>
                <p>{c.question} {c.about}</p>
                {ours.length ? <p><b style={{ display: 'inline', fontSize: 'inherit' }}>Ours:</b> {ours.map((o) => o.title).join(' · ')}</p> : null}
                <p>{found.slice(0, 4).map((d) => d.title).join(' · ')}{found.length > 4 ? ' …' : ''}</p>
              </div>
            </a>
          );
        })}
      </div>
      <p className="note">The same discoveries, the other way: <a href={axisHref(other)}>{other.name.toLowerCase()}</a>.</p>
    </>
  );
}
