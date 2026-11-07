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
//           note (one line under a set-aside card), badge (html), href, untrusted (the card judge doesn't trust the reading) }]
export function deckHand(cards, opts = {}) {
  const held = cards.filter(c => c.held), aside = cards.filter(c => !c.held), n = held.length;
  const face = c => CARD_FACE[c.key] || { rank: (c.name || '?')[0], suit: '♠', short: c.name };
  const corner = (f, cls) => `<span class="pc2-corner ${cls}${RED.has(f.suit) ? ' red' : ''}"><b>${esc(f.rank)}</b><i>${f.suit}</i></span>`;
  const up = (c, i) => {
    const f = face(c);
    const tag = c.href ? 'a' : 'div';
    return `<${tag} class="pc2${c.untrusted ? ' untrusted' : ''}" ${c.href ? `href="${esc(c.href)}"` : ''} style="--i:${i};--n:${n}" title="${esc(c.name)}: lit${c.untrusted ? ', but the card judge does not trust this reading yet' : ''}">${c.untrusted ? '<span class="pc2-stamp">not trusted</span>' : ''}
      ${corner(f, 'tl')}${corner(f, 'br')}
      <span class="pc2-art"><img src="art/${encodeURIComponent(c.key)}.png" alt="" loading="lazy" onerror="this.remove()"></span>
      <span class="pc2-name">${esc(f.short)}</span></${tag}>`;
  };
  const down = (c, i) => {
    const f = face(c);
    const why = c.state === 'unreadable' ? 'unreadable' : c.state === 'unread' ? 'not read yet' : c.near != null ? `${Math.round(100 * Math.max(0, Math.min(1, c.near)))}% of the way` : 'not lit';
    return `<div class="pc2-aside" style="--j:${i}" title="${esc(c.name)}: ${esc(why)}${c.note ? ' · ' + esc(c.note) : ''}">
      <div class="pc2 back${c.state === 'unreadable' || c.state === 'unread' ? ' void' : ''}${c.untrusted ? ' untrusted' : ''}">${c.untrusted ? '<span class="pc2-stamp">not trusted</span>' : ''}<span class="pc2-backmark">${f.suit}</span>
        ${c.near != null && c.state === 'unlit' ? `<span class="pc2-near" style="--near:${(100 * Math.max(0, Math.min(1, c.near))).toFixed(0)}%"></span>` : ''}</div>
      <div class="pc2-label"><b>${esc(f.short)}</b><span>${esc(why)}</span></div></div>`;
  };
  return `<div class="deckzone">
    <div class="handzone"><div class="zlabel">in hand <b>${n} of ${cards.length}</b></div>
      ${n ? `<div class="fanhand" style="--n:${n}">${held.map(up).join('')}</div>` : `<div class="fanhand empty-hand"><span>an empty hand: ${esc(opts.empty || 'no card lit yet')}</span></div>`}</div>
    <div class="asidezone"><div class="zlabel">still in the deck <b>${aside.length}</b></div>
      <div class="asidepile">${aside.map(down).join('') || '<span class="s">none: the whole hand is drawn</span>'}</div></div>
  </div>`;
}
