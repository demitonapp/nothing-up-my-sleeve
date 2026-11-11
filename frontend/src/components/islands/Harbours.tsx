// Harbours (UI.md "Harbours"), as a client island: the home page's harbour cards and one harbour's
// ships (with the ship builder on its own address). The island owns the poll and the current score
// under each card; the dense cards live in views/harbours.ts and the builder in views/shipbuilder.ts.

import { useEffect, useRef, useState } from 'react';
import { crumbCls, emptyCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import SectionNav from '../SectionNav';
import { candidateCardsHtml, classScoreHtml, harbourAbout, harbourCardsHtml, harbourKey, harbourRoute, harbourShipsHtml, harbourTitle, isOldHarbour, shipyardCardsHtml } from '@/scripts/views/harbours';
import { applyHarbourFlips, wireHarbourFlip } from '@/scripts/views/harbourflip';
import { BAND } from '@/scripts/views/bands';
import { mountShipbuilder } from '@/scripts/views/shipbuilder';

/** Every address this island answers: the home page, the harbours, and their ships/builder pages. */
export const isHarboursPage = (path: string): boolean => {
  const p = path.split('?')[0].replace(/^#/, '');
  return p === '' || p === '/' || /^\/harbours?(\/|$)/.test(p) || p === '/ships' || p === '/classes' || p === '/sizes' || p === '/rung' || p === '/shipyard' || p.startsWith('/shipyard/');
};

export default function Harbours() {
  const route = useRoute();
  const [path, setPath] = useState('/');

  useEffect(() => { setPath(route); }, [route]);
  const mine = isHarboursPage(path);
  const ladder = useApi<any>('/api/ladder', 15000, mine);
  const cardsRef = useRef<HTMLDivElement>(null);
  const builderRef = useRef<HTMLDivElement>(null);
  const scoreAsked = useRef<Record<string, number>>({});
  const candCache = useRef<any[] | null>(null);
  const builderFor = useRef<string | null>(null);

  // on the document, not the cards' container: the island drops its markup off the harbours' addresses
  useEffect(() => wireHarbourFlip(document.documentElement), []);

  useEffect(() => {
    const read = (): void => setPath(location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname);
    read();
    const onPop = (): void => read();
    window.addEventListener('popstate', onPop);
    window.addEventListener('hashchange', onPop);
    return () => { window.removeEventListener('popstate', onPop); window.removeEventListener('hashchange', onPop); };
  }, []);

  const home = !harbourRoute(path).harbour;
  const { harbour, sub, section, band } = harbourRoute(path);
  // an old harbour address (phaleron, piraeus, zayton) forwards to its Orbital, keeping the sub-path
  useEffect(() => {
    const m = /^\/harbours?\/([^/]+)(\/[^?#]*)?/.exec(path.split('?')[0].replace(/^#/, ''));
    const asGiven = m ? decodeURIComponent(m[1]) : '';
    if (asGiven && isOldHarbour(asGiven)) {
      const rest = m && m[2] ? m[2] : '';
      history.replaceState(null, '', `/harbours/${harbourKey(asGiven)}${rest}`);
    }
  }, [path]);
  const bandInfo = BAND(band);
  const shipyardLanding = !section && (path.split('?')[0].replace(/^#/, '') === '/shipyard' || path.split('?')[0].replace(/^#/, '') === '/shipyard/');
  const data = ladder.data;
  const hs = (data && data.harbours) || [];
  const h = harbour ? hs.find((x: any) => x.key === harbour) || null : null;
  const hasBuilder = !!(h && h.ship_builder) && sub === 'shipbuilder' && !shipyardLanding;

  useEffect(() => {
    if (!mine || !cardsRef.current || !builderRef.current) return;
    const cards = cardsRef.current, builder = builderRef.current;
    if (shipyardLanding) {
      builderFor.current = null;
      builder.hidden = true;
      builder.innerHTML = '';
      builder.dataset.built = '';
      cards.hidden = false;
      cards.className = 'harbours shipyardgrid';
      cards.innerHTML = shipyardCardsHtml();
      return;
    }
    if (!data) return;
    if (hasBuilder && h) {
      cards.hidden = true;
      builder.hidden = false;
      const key = h.key + ':' + (section || '');
      if (builderFor.current !== key) {
        builderFor.current = key;
        builder.innerHTML = '';
        void mountShipbuilder(builder, h, section || undefined);
      }
      return;
    }
    builderFor.current = null;
    builder.hidden = true;
    builder.innerHTML = '';
    builder.dataset.built = '';
    cards.hidden = false;
    cards.className = harbour ? (h && h.foreign && !band ? 'cards bandcards' : 'cards') : 'harbours';
    if (!data.rungs) {
      cards.innerHTML = `<div class="${emptyCls()}">the ships could not be read. Restart <span class="mono">thorp dash</span> if it was just changed.</div>`;
      return;
    }
    if (!harbour) {
      // the poll rewrites the cards, so a turned card is painted back from the kept flip state
      cards.innerHTML = harbourCardsHtml(data);
      applyHarbourFlips(cards);
    } else if (!h) {
      cards.innerHTML = `<div class="${emptyCls()}">no harbour called ${harbour}</div>`;
    } else {
      cards.innerHTML = harbourShipsHtml(data, harbour, band);
      // a band also shows the models we know in it but have not read yet (the leaderboard's candidates),
      // so a pulled model is visible before its reading lands; the read ships stay first
      if (h.foreign && band) {
        const put = (cands: any[]): void => {
          const html = candidateCardsHtml(cands, band, data.foreign || []);
          if (html) cards.insertAdjacentHTML('beforeend', html);
        };
        if (candCache.current) put(candCache.current);
        else
          fetch('/api/leaderboard')
            .then((r) => r.json())
            .then((j) => {
              candCache.current = Object.values(j.candidates || {}).flat() as any[];
              if (harbourRoute(location.pathname).band === band) put(candCache.current!);
            })
            .catch(() => {});
      }
    }
    // the current version's scores (the leaderboard's best of the size; /api/class_score), filled as they arrive
    cards.querySelectorAll<HTMLElement>('[data-cscore]').forEach((el) => {
      const preset = el.dataset.cscore!;
      const now = Date.now();
      if (scoreAsked.current[preset] && now - scoreAsked.current[preset] < 60000) return;
      scoreAsked.current[preset] = now;
      fetch('/api/class_score?preset=' + encodeURIComponent(preset))
        .then((r) => r.json())
        .then((s) => {
          const out = classScoreHtml(s, preset);
          const at = cards.querySelector<HTMLElement>(`[data-cscore="${CSS.escape(preset)}"]`);
          if (at) { at.innerHTML = out.html; if (out.title) at.title = out.title; }
        })
        .catch(() => { scoreAsked.current[preset] = 0; });
    });
  }, [mine, data, harbour, hasBuilder, h, shipyardLanding, section]);

  if (!mine) return null;
  const shipyard = path.split('?')[0].replace(/^#/, '').startsWith('/shipyard');
  const sectionName = section === 'training' ? 'Training' : section === 'fitting' ? 'Fitting Out' : section === 'charting' ? 'Charting' : null;
  const title = sectionName || (shipyard ? 'Shipyard' : harbourTitle(data, harbour) + (bandInfo ? ` · ${bandInfo.name}` : ''));
  const about = sectionName === 'Training' ? 'the SOPing parties our models train on: the content, the fade, and the content by heart'
    : sectionName === 'Fitting Out' ? 'the embeddings, the training content and the scaffolding heads a ship is built from'
    : sectionName === 'Charting' ? 'sorting out the charts the voyage is planned on: the route, the stars, and the suits'
    : shipyard ? 'where a ship is drawn before it is built: the SOP it reads, the stages it must build, and the standard it is held to'
    : bandInfo ? `${bandInfo.range}: the outside models in this band, read on our decks` : harbourAbout(data, harbour);
  return (
    <div {...sectionProps('sizes')}>
      <SectionNav />
      {home || (shipyard && !sectionName) ? null : (
        <h1>
          {harbour ? <><a className={crumbCls('back')} href={sectionName ? '/shipyard' : bandInfo ? `/harbours/${encodeURIComponent(harbour)}` : '/harbours'}>{sectionName ? '← shipyard' : bandInfo ? `← ${harbourTitle(data, harbour)}` : shipyard ? '← places' : '← harbours'}</a> </> : null}
          {title}{' '}
          <span className="q">{about}</span>
        </h1>
      )}
      <div className="cards" id="rungcards" ref={cardsRef} />
      <div id="shipbuilder" ref={builderRef} hidden />
      {ladder.error ? <div className={emptyCls()}>the ships could not be read: {ladder.error}</div> : null}
    </div>
  );
}
