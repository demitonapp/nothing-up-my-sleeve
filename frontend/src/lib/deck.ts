// ---- The deck: the cards a model holds, drawn as a player's hand (UI.md, "The deck"). The stars that do a trick are
// playing cards (previous-word, Nevermore, mover, comparator, bridge). A card the model has lit is in its hand, face up
// and fanned; a card it hasn't is still in the deck, set aside face down beside the hand, with how close it came. A card
// that couldn't be read is set aside too, marked so. The readings sit in a table under the table-top.
import { esc } from './format';

// each card's corner: a rank-like letter and a suit, so a hand reads at a glance
interface CardFace {
  rank: string;
  suit: string;
  short: string;
}
export const CARD_FACE: Record<string, CardFace> = {
  previous_word: { rank: 'P', suit: '♣', short: 'Previous word' },
  nevermore: { rank: 'N', suit: '♠', short: 'Nevermore' },
  mover: { rank: 'M', suit: '♦', short: 'Mover' },
  comparator: { rank: 'C', suit: '♥', short: 'Comparator' },
  bridge: { rank: 'B', suit: '♠', short: 'Bridge' },
};

interface DeckCard {
  key: string;
  name?: string;
  held: boolean;
  state: 'lit' | 'unlit' | 'unread' | 'unreadable';
  near?: number | null; // 0..1 of the mark, for a card not held
  note?: string; // one line under a set-aside card
  about?: string; // what the card does, a sentence or two
  href?: string; // where the back of the card links
  untrusted?: boolean; // the card judge doesn't trust the reading
}

// every suit is printed in ink: colour on a card means something here (green lit, amber not trusted), so the
// suits don't borrow red from real playing cards
const RED = new Set<string>();
// the cards turned over, kept here so the page's 5 s redraw leaves them as the reader left them
const TURNED = new Set<string>();

export function deckHand(cards: DeckCard[], opts: { empty?: string } = {}): string {
  const held = cards.filter((c) => c.held);
  const aside = cards.filter((c) => !c.held);
  const n = held.length;
  const face = (c: DeckCard): CardFace => CARD_FACE[c.key] || { rank: (c.name || '?')[0], suit: '♠', short: c.name || '?' };
  const corner = (f: CardFace, cls: string): string => `<span class="pc2-corner ${cls}${RED.has(f.suit) ? ' red' : ''}"><b>${esc(f.rank)}</b><i>${f.suit}</i></span>`;
  const why = (c: DeckCard): string => c.state === 'unreadable' ? 'unreadable' : c.state === 'unread' ? 'not read yet' : c.state === 'lit' ? 'lit: in the hand'
    : c.near != null ? `${Math.round(100 * Math.max(0, Math.min(1, c.near)))}% of the way` : 'not lit';
  // the back of a card: what it does, how it stands, and the way to the stars
  const rear = (c: DeckCard): string => {
    const f = face(c);
    return `<span class="pc2-rear">${corner(f, 'tl')}
      <b class="pc2-rt">${esc(f.short)}</b><span class="pc2-about">${esc(c.about || 'what this card does is read with the stars')}</span>
      <span class="pc2-why">${esc(why(c))}${c.untrusted ? ' · the card judge does not trust this reading yet' : ''}</span>
      <a class="pc2-more" href="${esc(c.href || '/orbitals/demiton/discoveries/stars')}">the stars →</a></span>`;
  };
  // a card that turns: the box keeps its place in the fan, its inside turns over
  const turner = (c: DeckCard, cls: string, style: string, front: string): string => {
    const on = TURNED.has(c.key);
    const f = face(c);
    return `<div class="pc2 flip ${cls}${on ? ' flipped' : ''}${c.untrusted ? ' untrusted' : ''}" style="${style}" data-card="${esc(c.key)}"
      role="button" tabindex="0" aria-pressed="${on}" aria-label="${esc(f.short)}: turn over for what it does" title="${esc(c.name || '')}: click to turn over">
      <span class="pc2-turn"><span class="pc2-face">${c.untrusted ? '<span class="pc2-stamp">not trusted</span>' : ''}${front}</span>${rear(c)}</span></div>`;
  };
  const up = (c: DeckCard, i: number): string => {
    const f = face(c);
    return turner(c, '', `--i:${i};--n:${n}`, `${corner(f, 'tl')}${corner(f, 'br')}
      <span class="pc2-art"><img src="/art/${encodeURIComponent(c.key)}.png" alt="" loading="lazy" onerror="this.remove()"></span>
      <span class="pc2-name">${esc(f.short)}</span>`);
  };
  const down = (c: DeckCard, i: number): string => {
    const f = face(c);
    return `<div class="pc2-aside" style="--j:${i}">
      ${turner(c, `back${c.state === 'unreadable' || c.state === 'unread' ? ' void' : ''}`, '', `<span class="pc2-backmark">${f.suit}</span>
        ${c.near != null && c.state === 'unlit' ? `<span class="pc2-near" style="--near:${(100 * Math.max(0, Math.min(1, c.near))).toFixed(0)}%"></span>` : ''}`)}
      <div class="pc2-label"><b>${esc(f.short)}</b><span>${esc(why(c))}</span>${c.note ? `<span>${esc(c.note)}</span>` : ''}</div></div>`;
  };
  return `<div class="deckzone">
    <div class="handzone"><div class="zlabel">in hand <b>${n} of ${cards.length}</b></div>
      ${n ? `<div class="fanhand" style="--n:${n}">${held.map(up).join('')}</div>` : `<div class="fanhand empty-hand"><span>an empty hand: ${esc(opts.empty || 'no card lit yet')}</span></div>`}</div>
    <div class="asidezone"><div class="zlabel">still in the deck <b>${aside.length}</b></div>
      <div class="asidepile">${aside.map(down).join('') || '<span class="s">none: the whole hand is drawn</span>'}</div></div>
  </div>`;
}

// turning a card over: one listener for every hand on the page; a link on a card's back still goes where it says
function turn(card: HTMLElement): void {
  const key = card.dataset.card;
  if (key == null) return;
  const on = card.classList.toggle('flipped');
  card.setAttribute('aria-pressed', String(on));
  if (on) TURNED.add(key); else TURNED.delete(key);
}
// the listeners are browser-only: the views are imported by server-rendered islands too
if (typeof document !== 'undefined') {
  document.addEventListener('click', (e) => {
    const target = e.target as HTMLElement | null;
    const card = target?.closest('.pc2.flip');
    if (card && !target?.closest('a')) turn(card as HTMLElement);
  });
  document.addEventListener('keydown', (e) => {
    const target = e.target as HTMLElement | null;
    if ((e.key === 'Enter' || e.key === ' ') && target?.matches('.pc2.flip')) { e.preventDefault(); turn(target); }
  });
}
