// The two cards a new visitor meets on the home page (13 November, Justin: "two cards for new users to the site":
// the latest epub, to download, send to a Kindle or read; and a join-a-faction card for people who can help with
// the mission). They stand above the orbitals until the visitor puts them away, which their browser remembers;
// the book and the join page stay reachable from the ⌘K palette either way.

import { useEffect, useState } from 'react';
import { BookOpen, Download, Send, X } from 'lucide-react';
import '@/styles/first-cards.css';
import { btnCls, cardCls } from '@/lib/ui';
import { BOOK, FACTIONS, MISSION, hideWelcome, longDate, side, welcomeHidden, type FactionKey } from '@/lib/firstCards';
import KindleDialog from './KindleDialog';
import { FACTION_ICON } from './islands/Join';

export default function Welcome() {
  // nothing on the server or before the browser has been asked: a returning visitor never sees them flash
  const [shown, setShown] = useState(false);
  const [kindle, setKindle] = useState(false);
  const [mine, setMine] = useState<FactionKey | null>(null);
  useEffect(() => { setShown(!welcomeHidden()); setMine(side()); }, []);
  // the orbital cards below fit themselves to the window on a resize (Harbours.tsx); these cards move them
  useEffect(() => { window.dispatchEvent(new Event('resize')); }, [shown]);
  if (!shown) return null;

  return (
    <section className="welcome" aria-label="New here">
      <div className="welcomehead">
        <h2>New here? <span>Two places to start.</span></h2>
        <button type="button" className="welcomeclose" onClick={() => { hideWelcome(true); setShown(false); }} aria-label="Put these two cards away" title="Put these away"><X aria-hidden="true" /></button>
      </div>
      <div className="welcomecards">
        <article className={cardCls(false, 'welcomecard bookcard')}>
          <a className="welcomeart" href="/book" tabIndex={-1} aria-hidden="true"><img src={BOOK.cover} alt="" loading="lazy" /></a>
          <div className="welcomewords">
            <div className="bookeyebrow">The book · {BOOK.version} · {longDate(BOOK.published)}</div>
            <h3><a href="/book">{BOOK.title}</a></h3>
            <p>{BOOK.standfirst}</p>
            <div className="bookacts">
              <a className={btnCls('default')} href="/book/read"><BookOpen aria-hidden="true" />Read</a>
              <a className={btnCls('outline')} href={BOOK.file} download={BOOK.downloadName}><Download aria-hidden="true" />Download</a>
              <button type="button" className={btnCls('outline')} onClick={() => setKindle(true)}><Send aria-hidden="true" />Send to Kindle</button>
            </div>
          </div>
        </article>

        <article className={cardCls(false, 'welcomecard joincard')}>
          <div className="welcomewords">
            <div className="bookeyebrow">Join</div>
            <h3><a href="/join">Take a side</a></h3>
            <p>{MISSION}</p>
            <ul className="sidelist">
              {FACTIONS.map((f) => {
                const Icon = FACTION_ICON[f.key];
                return (
                  <li key={f.key}>
                    <a className={`sidechip${mine === f.key ? ' taken' : ''}`} href={`/join#${f.key}`}>
                      <Icon aria-hidden="true" />{f.name}{mine === f.key ? <span className="sr-only"> (your side)</span> : null}
                    </a>
                  </li>
                );
              })}
            </ul>
            <div className="bookacts">
              <a className={btnCls('default')} href="/join">Choose how to help</a>
            </div>
          </div>
        </article>
      </div>
      <KindleDialog open={kindle} onOpenChange={setKindle} />
    </section>
  );
}
