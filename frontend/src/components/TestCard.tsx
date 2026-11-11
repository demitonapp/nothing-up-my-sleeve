// One test's card (12 November, Justin: "cards for each test ... with fal images the user must click and
// then they flip over with the leaderboard, but the card must have a picture that represents the test in
// our style and a link and description to the test"). The face is the plate, the test's name, what it reads
// and where it is published; a click turns it over, and the turned card takes the whole row for its board.
//
// Lifted out of StepsBoard.tsx (12 November) so a band's test cards and the extra small band's are one
// component. A test without art of its own gets a plate: its group's short mark, set on the same 16:9
// black the images sit on, so the row never shows an empty frame.

import type { ReactNode } from 'react';

export function TestCard({ id, open, setOpen, art, plate, name, tag, about, link, stat, children }: {
  id: string; open: string | null; setOpen: (v: string | null) => void; art?: string; plate?: string;
  name: string; tag: string; about: string; link: { href: string; label: string }; stat?: string;
  children: ReactNode;
}) {
  const on = open === id;
  const turn = () => setOpen(on ? null : id);
  return (
    <div className={`tflip${on ? ' on' : ''}`} id={`test-${id}`}>
      <div className="tflip-inner">
        <div
          className="tface tfront"
          role="button"
          tabIndex={on ? -1 : 0}
          aria-pressed={on}
          aria-label={`Turn the ${name} card over for its board`}
          onClick={turn}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); turn(); } }}
        >
          <div className={`tart${art ? '' : ' noplate'}`}>
            {art
              ? <img src={art} alt="" loading="lazy" onError={(e) => { (e.currentTarget.parentElement as HTMLElement).style.display = 'none'; }} />
              : <span className="tplate" aria-hidden="true">{plate || name}</span>}
            {art && <span className="ttag">{tag}</span>}
          </div>
          <div className="tcap">
            <div className="tname">{name}</div>
            <p className="tabout">{about}</p>
            {stat && <div className="tstat sqhead" dangerouslySetInnerHTML={{ __html: stat.split('</div>')[0] + '</div>' }} />}
            <div className="tfoot">
              <a href={link.href} target={link.href.startsWith('http') ? '_blank' : undefined} rel="noreferrer" onClick={(e) => e.stopPropagation()}>{link.label} ↗</a>
              <span className="tturn" aria-hidden="true">⟲ the board</span>
            </div>
          </div>
        </div>
        <div className="tface tback" aria-hidden={!on}>
          <button type="button" className="hflipbtn tbackbtn" onClick={turn} aria-label={`Turn the ${name} card back`}><span className="hflipicon" aria-hidden="true">⟲</span><span>the card</span></button>
          {children}
        </div>
      </div>
    </div>
  );
}
