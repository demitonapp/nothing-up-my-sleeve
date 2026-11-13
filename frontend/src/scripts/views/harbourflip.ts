// The harbour cards' flip (11 November, Justin: "the cards to harbours to flip so each harbour has 5 images").
// The island rewrites the cards' HTML on every poll, so the state lives here, not in the DOM: which cards are
// turned over and which of the five views each shows. `applyHarbourFlips` repaints that state onto freshly
// written cards; `wireHarbourFlip` is one delegated listener on the cards' container.

import { DEMITON, DEMITON_VIEWS, HARBOUR_VIEWS, SLEEPER_KEY, SLEEPER_VIEWS } from './harbours';

/** A card's five views: Demiton's own list, Sleeper Service's (13 November: its card flipped to nothing until it
 *  was named here), or its harbour's. */
const viewsOf = (key: string) => (key === DEMITON.key ? DEMITON_VIEWS : key === SLEEPER_KEY ? SLEEPER_VIEWS : HARBOUR_VIEWS[key]);

interface FlipState { on: boolean; view: number }
const state = new Map<string, FlipState>();
const get = (key: string): FlipState => {
  let s = state.get(key);
  if (!s) { s = { on: false, view: 0 }; state.set(key, s); }
  return s;
};

const load = (img: HTMLImageElement | null): void => {
  if (img && img.dataset.src && img.getAttribute('src') !== img.dataset.src) img.src = img.dataset.src;
};

/** Paint one card from its kept state: turned or not, which view, which images are fetched. */
function paint(card: HTMLElement): void {
  const key = card.dataset.harbour || '';
  const views = viewsOf(key);
  if (!views) return;
  const s = get(key);
  const front = card.querySelector<HTMLElement>('.hfront');
  const back = card.querySelector<HTMLElement>('.hback');
  const btn = card.querySelector<HTMLButtonElement>('[data-hflip]');
  if (!front || !back || !btn) return;
  card.classList.toggle('on', s.on);
  front.toggleAttribute('inert', s.on);
  back.toggleAttribute('inert', !s.on);
  btn.setAttribute('aria-pressed', String(s.on));
  const name = (card.querySelector('.nm')?.textContent || key).trim();
  btn.setAttribute('aria-label', s.on ? `Flip ${name} back` : `Flip ${name} to see five views`);
  const text = btn.querySelector('.hfliptext');
  if (text) text.textContent = s.on ? 'back' : '5 views';
  if (s.on) back.querySelectorAll<HTMLImageElement>('img[data-src]').forEach(load);
  const v = views[s.view] || views[0];
  const shot = back.querySelector<HTMLImageElement>('.hshot');
  if (shot && shot.dataset.src !== artUrlOf(back, s.view)) {
    shot.dataset.src = artUrlOf(back, s.view);
    shot.style.animation = 'none'; // replay the fade-in for the new view
    void shot.offsetWidth;
    shot.style.animation = '';
    if (s.on) load(shot);
  }
  if (shot) shot.alt = v.label;
  const lab = back.querySelector('.hcaplabel');
  const note = back.querySelector('.hcapnote');
  if (lab) lab.textContent = v.label;
  if (note) note.textContent = v.note;
  back.querySelectorAll<HTMLButtonElement>('.hthumb').forEach((t, i) => {
    t.classList.toggle('on', i === s.view);
    t.setAttribute('aria-pressed', String(i === s.view));
  });
}

/** The URL of view `i`'s image, read from its thumbnail (which carries the same file as the large view). */
const artUrlOf = (back: HTMLElement, i: number): string =>
  back.querySelectorAll<HTMLImageElement>('.hthumb img')[i]?.dataset.src || '';

/** Repaint every harbour card under `root` from the kept state: called after each write of the cards. */
export function applyHarbourFlips(root: HTMLElement): void {
  // new nodes have no earlier style to transition from, so a turned card comes back turned, not re-flipping
  root.querySelectorAll<HTMLElement>('.hflip').forEach(paint);
}

/** Wire the flip button, the five thumbnails and the arrow keys on `root`. Returns the remover. */
export function wireHarbourFlip(root: HTMLElement): () => void {
  const onClick = (e: MouseEvent): void => {
    const t = e.target as HTMLElement | null;
    if (!t) return;
    const card = t.closest<HTMLElement>('.hflip');
    if (!card) return;
    const key = card.dataset.harbour || '';
    if (t.closest('[data-hflip]')) {
      e.preventDefault();
      const s = get(key);
      s.on = !s.on;
      paint(card);
      return;
    }
    const thumb = t.closest<HTMLElement>('[data-hview]');
    if (thumb) {
      e.preventDefault();
      get(key).view = Number(thumb.dataset.hview) || 0;
      paint(card);
    }
  };
  const onKey = (e: KeyboardEvent): void => {
    const t = e.target as HTMLElement | null;
    const card = t && t.closest<HTMLElement>('.hflip');
    if (!card) return;
    const key = card.dataset.harbour || '';
    const s = get(key);
    if (e.key === 'Escape' && s.on) { s.on = false; paint(card); card.querySelector<HTMLElement>('[data-hflip]')?.focus(); return; }
    if (!s.on || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft')) return;
    const n = (viewsOf(key) || []).length;
    if (!n) return;
    e.preventDefault();
    s.view = (s.view + (e.key === 'ArrowRight' ? 1 : n - 1)) % n;
    paint(card);
    card.querySelectorAll<HTMLElement>('.hthumb')[s.view]?.focus();
  };
  root.addEventListener('click', onClick);
  root.addEventListener('keydown', onKey);
  return () => { root.removeEventListener('click', onClick); root.removeEventListener('keydown', onKey); };
}
