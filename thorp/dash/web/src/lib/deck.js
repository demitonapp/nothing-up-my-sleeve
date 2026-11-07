// ---- The deck: the cards a model holds, drawn as a player's hand (UI.md, "The deck"). The stars that do a trick are
// playing cards (previous-word, Nevermore, mover, comparator, bridge). A card the model has lit is in its hand, face up
// and fanned; a card it hasn't is still in the deck, set aside face down beside the hand, with how close it came. A card
// that couldn't be read is set aside too, marked so. The readings sit in a table under the table-top.
import { esc } from './format.js';

// each card's corner: a rank-like letter and a suit, so a hand reads at a glance
export const CARD_FACE = {
  previous_word: { rank: 'P', suit: '♣', short: 'Previous word' },
  nevermore: { rank: 'N', suit: '♠', short: 'Nevermore' },
  mover: { rank: 'M', suit: '♦', short: 'Mover' },
  comparator: { rank: 'C', suit: '♥', short: 'Comparator' },
  bridge: { rank: 'B', suit: '♠', short: 'Bridge' },
};
// every suit is printed in ink: colour on a card means something here (green lit, amber not trusted), so the
// suits don't borrow red from real playing cards
const RED = new Set();

// cards: [{ key, name, held, state ('lit'|'unlit'|'unread'|'unreadable'), near (0..1 of the mark, for a card not held),
//           note (one line under a set-aside card), about (what the card does, a sentence or two), href (where the
//           back of the card links), untrusted (the card judge doesn't trust the reading) }]
// Every card turns over on a click (or Enter / Space) to what it does: its back is the description, the front the
// art. The cards turned over are kept here, so the page's 5 s redraw leaves them as the reader left them.
const TURNED = new Set();
export function deckHand(cards, opts = {}) {
  const held = cards.filter(c => c.held), aside = cards.filter(c => !c.held), n = held.length;
  const face = c => CARD_FACE[c.key] || { rank: (c.name || '?')[0], suit: '♠', short: c.name };
  const corner = (f, cls) => `<span class="pc2-corner ${cls}${RED.has(f.suit) ? ' red' : ''}"><b>${esc(f.rank)}</b><i>${f.suit}</i></span>`;
  const why = c => c.state === 'unreadable' ? 'unreadable' : c.state === 'unread' ? 'not read yet' : c.state === 'lit' ? 'lit: in the hand'
    : c.near != null ? `${Math.round(100 * Math.max(0, Math.min(1, c.near)))}% of the way` : 'not lit';
  // the back of a card: what it does, how it stands, and the way to the stars
  const rear = c => { const f = face(c); return `<span class="pc2-rear">${corner(f, 'tl')}
      <b class="pc2-rt">${esc(f.short)}</b><span class="pc2-about">${esc(c.about || 'what this card does is read with the stars')}</span>
      <span class="pc2-why">${esc(why(c))}${c.untrusted ? ' · the card judge does not trust this reading yet' : ''}</span>
      <a class="pc2-more" href="${esc(c.href || '#/discoveries/stars')}">the stars →</a></span>`; };
  // a card that turns: the box keeps its place in the fan, its inside turns over
  const turner = (c, cls, style, front) => {
    const on = TURNED.has(c.key), f = face(c);
    return `<div class="pc2 flip ${cls}${on ? ' flipped' : ''}${c.untrusted ? ' untrusted' : ''}" style="${style}" data-card="${esc(c.key)}"
      role="button" tabindex="0" aria-pressed="${on}" aria-label="${esc(f.short)}: turn over for what it does" title="${esc(c.name)}: click to turn over">
      <span class="pc2-turn"><span class="pc2-face">${c.untrusted ? '<span class="pc2-stamp">not trusted</span>' : ''}${front}</span>${rear(c)}</span></div>`;
  };
  const up = (c, i) => {
    const f = face(c);
    return turner(c, '', `--i:${i};--n:${n}`, `${corner(f, 'tl')}${corner(f, 'br')}
      <span class="pc2-art"><img src="art/${encodeURIComponent(c.key)}.png" alt="" loading="lazy" onerror="this.remove()"></span>
      <span class="pc2-name">${esc(f.short)}</span>`);
  };
  const down = (c, i) => {
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
function turn(card) {
  const on = card.classList.toggle('flipped');
  card.setAttribute('aria-pressed', String(on));
  if (on) TURNED.add(card.dataset.card); else TURNED.delete(card.dataset.card);
}
document.addEventListener('click', e => {
  const card = e.target.closest && e.target.closest('.pc2.flip');
  if (card && !e.target.closest('a')) turn(card);
});
document.addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('.pc2.flip')) { e.preventDefault(); turn(e.target); }
});
