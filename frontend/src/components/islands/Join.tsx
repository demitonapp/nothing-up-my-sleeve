// Joining (13 November, Justin: a card "kinda like a join a faction card whereby people can help with Nothing up
// my sleeve's mission", and then the four: "Investor, Researcher, GPU provider, Corpus provider"). Four sides a
// visitor can take, each saying what it brings and why it matters, and two ways to start that need nobody's
// leave: running a model on your own machine, and building with us.
//
// The public site has no server, so joining is a note the visitor writes on the project's public repository
// (lib/firstCards.ts, joinHref). The side they took is remembered in their browser, to mark the card; nothing
// about them is kept by the site.

import { useEffect, useState } from 'react';
import { Coins, Cpu, FlaskConical, GitBranch, Library, Terminal } from 'lucide-react';
import '@/styles/first-cards.css';
import { btnCls, cardCls } from '@/lib/ui';
import { sectionProps } from '@/lib/useApi';
import { FACTIONS, MISSION, REPO, joinHref, setSide, side, type FactionKey } from '@/lib/firstCards';

export const FACTION_ICON = { investor: Coins, researcher: FlaskConical, gpu: Cpu, corpus: Library } as const;

export default function Join() {
  const [mine, setMine] = useState<FactionKey | null>(null);
  useEffect(() => { setMine(side()); }, []);
  const take = (k: FactionKey | null): void => { setSide(k); setMine(k); };

  return (
    <div {...sectionProps('join')}>
      <h1>Join <span className="q">four sides to take, and two ways to start today</span></h1>
      <p className="joinlead">{MISSION}</p>

      <div className="factions">
        {FACTIONS.map((f) => {
          const Icon = FACTION_ICON[f.key];
          const taken = mine === f.key;
          return (
            <section key={f.key} id={f.key} className={cardCls(false, `faction${taken ? ' taken' : ''}`)} aria-labelledby={`faction-${f.key}`}>
              <div className="factionhead">
                <span className="factionmark" aria-hidden="true"><Icon /></span>
                <h2 id={`faction-${f.key}`}>{f.name}</h2>
                {taken ? <span className="factionyours">your side</span> : null}
              </div>
              <p className="factionbrings">{f.brings}</p>
              <p className="factionabout">{f.about}</p>
              <div className="factionacts">
                <a className={btnCls(taken ? 'outline' : 'default')} href={joinHref(f)} target="_blank" rel="noreferrer" onClick={() => take(f.key)}>
                  {taken ? 'Write another note' : `Join as ${f.as}`}
                </a>
                {taken ? <button type="button" className={btnCls('ghost')} onClick={() => take(null)}>Leave</button> : null}
              </div>
            </section>
          );
        })}
      </div>
      <p className="joinnote">
        Joining opens a note on the project's public repository, with the title filled in; you write the rest, and it is public. This site keeps nothing about you: the side you took is remembered in this browser only, to mark the card.
      </p>

      <h2 className="joinsub">Or start today</h2>
      <div className="starts">
        <button type="button" className={cardCls(true, 'card start')} onClick={() => window.dispatchEvent(new CustomEvent('thorp:chat', { detail: { model: '' } }))}>
          <span className="factionmark" aria-hidden="true"><Terminal /></span>
          <b>Run a model on your own machine</b>
          <span>Open the console and connect a model running on your computer. It is found from your browser, and what you say to it stays between the two of you.</span>
        </button>
        <a className={cardCls(true, 'card start')} href={REPO} target="_blank" rel="noreferrer">
          <span className="factionmark" aria-hidden="true"><GitBranch /></span>
          <b>Build with us</b>
          <span>The code, the record of every decision and the book are in one public repository. Read it, run it, send a change.</span>
        </a>
      </div>
    </div>
  );
}
