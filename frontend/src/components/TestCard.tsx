// One test's card (12 November, Justin: "cards for each test ... with fal images the user must click and
// then they flip over with the leaderboard, but the card must have a picture that represents the test in
// our style and a link and description to the test"). The face is the plate, the test's name, what it reads
// and where it is published; a click turns it over, and the turned card takes the whole row for its board.
//
// Lifted out of StepsBoard.tsx (12 November) so a band's test cards and the extra small band's are one
// component. A test without art of its own gets a plate: its group's short mark, set on the same 16:9
// black the images sit on, so the row never shows an empty frame.

import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { hiddenHere } from '@/lib/edition';

export function TestCard({ id, open = null, setOpen, href, art, plate, name, tag, about, ours, published, pros, cons, link, stat, children }: {
  id: string; open?: string | null; setOpen?: (v: string | null) => void; art?: string; plate?: string;
  name: string; tag: string; about: string; link: { href: string; label: string }; stat?: string;
  /** A leaderboard category's two lists (lib/testCategories.ts): what we measure, and the published tests beside it. */
  ours?: string; published?: string;
  /** What the test is good for and where it misleads (lib/testCatalog.ts), on the face of the card. */
  pros?: string[]; cons?: string[];
  /** A card that opens a page instead of turning over (the landing's categories, 13 November). */
  href?: string;
  children?: ReactNode;
}) {
  // a plate that is not made yet (or fails to load) falls back to the text plate, never an empty frame
  const [broken, setBroken] = useState(false);
  const showArt = !!art && !broken;
  // the plate can fail before this component hydrates, so its error event is missed: look again once mounted
  const img = useRef<HTMLImageElement | null>(null);
  useEffect(() => {
    const el = img.current;
    if (el && el.complete && el.naturalWidth === 0) setBroken(true);
  }, [art]);
  const on = !href && open === id;
  const turn = () => { if (href) window.location.assign(href); else setOpen?.(on ? null : id); };
  return (
    <div className={`tflip${on ? ' on' : ''}`} id={`test-${id}`}>
      <div className="tflip-inner">
        <div
          className="tface tfront"
          role="button"
          tabIndex={on ? -1 : 0}
          aria-pressed={href ? undefined : on}
          aria-label={href ? `Open ${name}` : `Turn the ${name} card over for its board`}
          onClick={turn}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); turn(); } }}
        >
          <div className={`tart${showArt ? '' : ' noplate'}`}>
            {showArt
              ? <img ref={img} src={art} alt="" onError={() => setBroken(true)} />
              : <span className="tplate" aria-hidden="true">{plate || name}</span>}
            {showArt && <span className="ttag">{tag}</span>}
          </div>
          <div className="tcap">
            <div className="tname">{name}</div>
            <p className="tabout">{about}</p>
            {ours != null && <p className="tabout"><b>Our measured tests</b> · {ours}</p>}
            {published != null && <p className="tabout"><b>Published tests</b> · {published}</p>}
            {pros && pros.length ? <div className="tpc tpros"><b>Pros</b><ul>{pros.map((x) => <li key={x}>{x}</li>)}</ul></div> : null}
            {cons && cons.length ? <div className="tpc tcons"><b>Cons</b><ul>{cons.map((x) => <li key={x}>{x}</li>)}</ul></div> : null}
            {stat && <div className="tstat sqhead" dangerouslySetInnerHTML={{ __html: stat.split('</div>')[0] + '</div>' }} />}
            <div className="tfoot">
              {/* the public edition (lib/edition.ts) has no Demiton: a link into it is left off, the card keeps its turn */}
              {hiddenHere(link.href) ? <span /> : <a href={link.href} target={link.href.startsWith('http') ? '_blank' : undefined} rel="noreferrer" onClick={(e) => e.stopPropagation()}>{link.label} ↗</a>}
              <span className="tturn" aria-hidden="true">{href ? 'open →' : '⟲ the board'}</span>
            </div>
          </div>
        </div>
        {href ? null : (
          <div className="tface tback" aria-hidden={!on}>
            <button type="button" className="hflipbtn tbackbtn" onClick={turn} aria-label={`Turn the ${name} card back`}><span className="hflipicon" aria-hidden="true">⟲</span><span>the card</span></button>
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
