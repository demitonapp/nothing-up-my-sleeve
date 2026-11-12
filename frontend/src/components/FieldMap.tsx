// The field's discoveries on two axes, drawn inside Demiton's discoveries (13 November, Justin: "a card for the two
// axis and then when clicking in we have cards for the level below them"). The overview shows the two axis cards; an
// axis page shows its categories as cards; a category page shows its discoveries. The data is lib/fieldMap.ts. Links
// are plain addresses under Demiton's discoveries, which the Discoveries island follows in place.

import { cardCls, crumbCls, emptyCls, pillCls } from '@/lib/ui';
import { DEMITON_DISCOVERIES as DB } from '@/lib/discoveryPaths';
import { AXES, axisBySlug, discoveriesIn, slugOf, type MapAxis } from '@/lib/fieldMap';

const axisHref = (a: MapAxis): string => `${DB}/${a.slug}`;
const otherAxis = (a: MapAxis): MapAxis => AXES.find((x) => x.key !== a.key) as MapAxis;

/** The two axis cards, for the top of the overview. */
export function AxisDoors() {
  return (
    <section className={cardCls(false, 'panel')}>
      <h2>The field, on two axes <span className="note">every discovery about language models placed twice: by the kind of claim it makes, and by what it is about. Open an axis for its categories, then a category for its discoveries</span></h2>
      <div className="discdoors">
        {AXES.map((a) => (
          <a className="discdoor" href={axisHref(a)} key={a.key}>
            <div className="db">
              <span className="dk">Axis {a.n} · {a.categories.length} categories</span>
              <b>{a.name}</b>
              <p>{a.question} {a.about}</p>
              <p>{a.categories.map((c) => <span className={pillCls('')} key={c.key} style={{ marginRight: 4, display: 'inline-block', marginTop: 4 }}>{c.name}</span>)}</p>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}

/** An axis (its categories as cards) or one category of it (its discoveries as cards). */
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
    return (
      <>
        <h1>
          <a className={crumbCls('back')} href={axisHref(axis)}>← {axis.name.toLowerCase()}</a>{' '}
          {category.name}{' '}
          <span className="q">{category.question} {category.about}</span>
        </h1>
        <section className={cardCls(false, 'panel')}>
          <h2>{found.length} discover{found.length === 1 ? 'y' : 'ies'} <span className="note">each with its source; the tag is where it sits on the other axis ({other.name.toLowerCase()}), and a link marks where Nothing up my sleeve measures the same thing</span></h2>
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
          const measured = found.filter((d) => d.thorp).length;
          return (
            <a className="discdoor" href={`${axisHref(axis)}/${slugOf(c)}`} key={c.key}>
              <div className="db">
                <span className="dk">{found.length} discover{found.length === 1 ? 'y' : 'ies'}{measured ? ` · ${measured} measured here` : ''}</span>
                <b>{c.name}</b>
                <p>{c.question} {c.about}</p>
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
