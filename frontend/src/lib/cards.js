// ---- Cards: a model's attention heads as a hand of playing cards (UI.md, "Cards").
// Thorp beat blackjack by counting cards: remembering what was dealt to bet on what comes next. A
// Nevermore does the same in text, so each head is a card. A card turns face up (♠) when its head
// reaches the Nevermore threshold on either test; until then its face shows through from the bottom
// in proportion to how far it has come (score ÷ threshold), so a head that is forming is visible.
// The big number is the real-prose score, the corner one the random-sequence score.
import { emptyCls } from './ui';
import { esc } from './format.js';

const FULL_MAX = 64;  // up to this many heads the whole hand is laid out by layer; above, the best five

// every head as { layer, head, real, random, top } where top is the better of the two tests
export function heads(hand) {
  const out = [];
  const grid = hand.real || hand.random || [];
  grid.forEach((row, l) => row.forEach((_, h) => {
    const real = hand.real ? hand.real[l][h] : null, random = hand.random ? hand.random[l][h] : null;
    out.push({ layer: l, head: h, real, random, top: Math.max(real ?? 0, random ?? 0) });
  }));
  return out;
}

const fmt2 = v => v == null ? '–' : v.toFixed(2).replace(/^0\./, '.');
const turned = (c, thr) => Math.max(0, Math.min(1, c.top / thr));

function card(c, thr, flipped) {
  const up = c.top >= thr;
  const title = `layer ${c.layer}, head ${c.head}: ${c.real != null ? `real prose ${c.real.toFixed(3)}` : ''}${c.real != null && c.random != null ? ', ' : ''}${c.random != null ? `random ${c.random.toFixed(3)}` : ''}${up ? ' (a Nevermore)' : ''}`;
  return `<div class="pcard${up ? ' up' : ''}${flipped ? ' flip' : ''}" style="--turn:${(turned(c, thr) * 100).toFixed(1)}%" title="${esc(title)}">
    <span class="pc-tl">L${c.layer}<br>H${c.head}</span>
    <span class="pc-mid">${up ? '♠' : ''}<b>${fmt2(c.real ?? c.random)}</b></span>
    <span class="pc-br">${c.real != null && c.random != null ? fmt2(c.random) : ''}</span>
  </div>`;
}

// the hand at one step. `prev` is the hand shown before, so a card that has just turned can flip.
export function renderHand(el, hand, thr, prev = null) {
  const all = heads(hand);
  if (!all.length) { el.innerHTML = `<div class="${emptyCls()}">no per-head scores at this step</div>`; return; }
  const wasUp = new Set(prev ? heads(prev).filter(c => c.top >= thr).map(c => c.layer + '.' + c.head) : []);
  const flipped = c => prev && c.top >= thr && !wasUp.has(c.layer + '.' + c.head);
  const up = all.filter(c => c.top >= thr).length;
  const summary = `<div class="handsum"><b>${up}</b> of ${all.length} heads face up${up ? '' : ' · none has become a Nevermore yet'} · strongest ${(() => { const b = [...all].sort((a, z) => z.top - a.top)[0]; return `layer ${b.layer}, head ${b.head} at ${b.top.toFixed(3)}`; })()}</div>`;
  if (all.length <= FULL_MAX) {
    const layers = [...new Set(all.map(c => c.layer))].sort((a, b) => b - a);  // the top layer first, as a hand is held
    el.innerHTML = summary + layers.map(l => `<div class="handrow"><span class="handlabel">layer ${l}</span>${all.filter(c => c.layer === l).map(c => card(c, thr, flipped(c))).join('')}</div>`).join('');
  } else {
    const best = [...all].sort((a, b) => b.top - a.top).slice(0, 5);
    el.innerHTML = summary + `<div class="handrow fan">${best.map(c => card(c, thr, flipped(c))).join('')}</div>`
      + `<div class="note">the strongest five of ${all.length} heads</div>`;
  }
}

// five tiny cards for a table row: the run's strongest heads at its latest step
export function miniHand(hand, thr) {
  if (!hand) return '–';
  const best = heads(hand).sort((a, b) => b.top - a.top).slice(0, 5);
  return `<span class="minihand" title="the five strongest heads: ${best.map(c => `L${c.layer} H${c.head} ${c.top.toFixed(3)}`).join(', ')}">${
    best.map(c => `<i class="${c.top >= thr ? 'up' : ''}" style="--turn:${(turned(c, thr) * 100).toFixed(1)}%"></i>`).join('')}</span>`;
}
