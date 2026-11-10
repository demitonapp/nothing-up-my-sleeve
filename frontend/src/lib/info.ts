// The metric-info popover (the ⓘ beside a metric heading, UI.md "Info popover"). Extracted (and typed) from
// the view monolith: the HELP table, the `info()` chip and the popover placement, plus the metric-name map
// that ties a scoreboard row to its help entry.

import { esc } from './format';
import { hoverCardCls } from './ui';

export type HelpEntry = [name: string, better: string, about: string];

export const HELP: Record<string, HelpEntry> = {
  nevermore: ['Nevermore score', 'Higher (0.3 or more is a Nevermore)', "The strongest head's attention from a repeated word to the word that followed it last time; measured on random pieces repeated twice (the standard test) and on a real passage repeated twice. A head attending evenly would score about 0.003."],
  copygain: ['Copy gain', 'Higher', 'How much easier the second copy is to predict than the first, in nats per token. Only a model that copies can gain.'],
  bpb: ['Bits per byte on English held-out books', 'Lower', 'How many bits the model needs, on average, to guess each byte of books it never saw. Fewer bits means better bets on unseen text. It is the headline score every rung shares.'],
  word_inside: ['Bits per byte inside a word', 'Lower', 'Letters after the first one in a word. Once a word has begun, how surely does the model know how it goes on? This is spelling.'],
  word_start: ['Bits per byte at a word start', 'Lower', 'The first letter of each word: which word comes next. That depends on grammar and meaning more than spelling, so expect it to stay high at 9m.'],
  punct: ['Bits per byte on punctuation', 'Lower', 'Commas, full stops, quotation marks, dashes. How well the model knows where punctuation goes.'],
  space: ['Bits per byte on spaces', 'Lower', 'Knowing where a word ends. A spelling skill as much as a layout one.'],
  newline: ['Bits per byte on line breaks', 'Lower', 'Paragraph and verse layout: where lines end.'],
  nonword_rate: ['Non-words', 'Lower, down to the books\' own rate', 'Share of the words the model writes that never appear anywhere on its library: invented spellings. The books\' own rate (ref) is the floor, because real text also holds words the library lacks. Reaching ref means it spells like a book.'],
  zipf: ['Zipf slope', 'Closer to the books', 'How fast word frequency falls with rank (the 10th commonest word is about a tenth as common as the 1st). Below the books: words used too evenly, as in noise. Above: too much repetition of a few common words. Real English sits near 1.'],
  heaps: ['Heaps slope', 'Closer to the books', 'How fast new words keep appearing as text goes on. Above the books usually means inventing words; below means a small, repetitive vocabulary.'],
  word_len: ['Mean word length', 'Closer to the books', 'Average letters per word. Real text prefers short common words (brevity law); a model that writes long strings of letters scores high here.'],
  punct_per_100w: ['Punctuation per 100 words', 'Closer to the books', 'How much punctuation it uses at all. Too much is a common early failure: commas and quote marks sprayed everywhere.'],
  unbalanced_per_kw: ['Unbalanced brackets and quotes per 1,000 words', 'Lower, down to the books\' own rate', 'Brackets and curly quotes closed without being opened, or left open. The books have a few because the excerpts are cut mid-passage; that is the floor.'],
  cap_after_stop: ['Capital after a full stop', 'Higher, up to the books', 'Share of sentence ends followed by a capital letter. Books score about 0.9 (abbreviations such as "Mr." account for the rest).'],
  word_len_js: ['Word-length divergence', 'Lower (0 is identical)', 'Jensen–Shannon divergence, in bits, between the model\'s mix of word lengths and the books\'. 0 means the same shape.'],
  punct_js: ['Punctuation-mix divergence', 'Lower (0 is identical)', 'Divergence between which punctuation marks the model uses and which the books use: the right marks in the right proportions.'],
  traits: ['Traits as they emerge', 'Earlier and stronger', 'Can a probe read fiction, verse or first person off the model\'s hidden state, at which layer, from which step? Shown on the Traits tab for each voyage.'],
  ft: ['The Forgotten Tomes score', 'Lower', 'Bits per byte on 16 period books released on Gutenberg after Qwen 3.8 appeared, so no Qwen model can have trained on them. The same number for Nothing up my sleeve and for Qwen, whatever their tokenisers: the yardstick for the order-of-magnitude gate.'],
  rank: ['Rank agreement with 9m', 'Higher (1 is perfect)', 'Spearman correlation between the order 9m puts the libraries in and the order 1m puts them in. At 0.8 or above the proxy is trusted to explore those kinds of questions.'],
  modelref: ['model / ref', 'Model close to ref', 'Each law is measured on text the model writes (left) and on excerpts of the held-out books (ref, right), at the same length. The target is the books\' own value.'],
};

export const info = (k: string): string => {
  const h = HELP[k];
  return h ? `<span class="info" tabindex="0">ⓘ<span class="pop ${hoverCardCls}"><b>${esc(h[0])}</b><br>Better: <b>${esc(h[1])}</b><br>${esc(h[2])}</span></span>` : '';
};

// popovers sit in scrolling tables, so they are placed against the window, kept on screen
export function placePop(el: HTMLElement): void {
  const pop = el.querySelector('.pop') as HTMLElement | null;
  if (!pop) return;
  const r = el.getBoundingClientRect();
  const w = 280;
  pop.style.left = Math.max(8, Math.min(r.left - 8, window.innerWidth - w - 8)) + 'px';
  pop.style.top = (r.bottom + 6) + 'px';
}

// one set of listeners for every ⓘ on the page
window.addEventListener('scroll', () => document.querySelectorAll('.info.open').forEach((x) => x.classList.remove('open')), true);
(['mouseover', 'focusin'] as const).forEach((ev) => document.addEventListener(ev, (e) => {
  const el = (e.target as HTMLElement | null)?.closest?.('.info') as HTMLElement | null;
  if (el) placePop(el);
}));
document.addEventListener('click', (e) => {
  const el = (e.target as HTMLElement | null)?.closest?.('.info') as HTMLElement | null;
  if (el) placePop(el);
  document.querySelectorAll('.info.open').forEach((x) => { if (x !== el) x.classList.remove('open'); });
  if (el) el.classList.toggle('open');
});

// a scoreboard row's name -> the HELP key behind its ⓘ
export const METRIC_KEY: Record<string, string> = {
  'inside a word': 'word_inside', 'word start': 'word_start', 'punctuation': 'punct', 'layout': 'space', 'non-words': 'nonword_rate',
  'Zipf and Heaps': 'zipf', 'word length, punctuation mix': 'word_len_js', 'balance and capitals': 'cap_after_stop', 'traits as they emerge': 'traits',
  'Forgotten Tomes score': 'ft', 'rank agreement with 9m': 'rank',
};
