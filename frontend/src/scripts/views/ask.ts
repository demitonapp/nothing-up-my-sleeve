// The Ask tab's pure helpers, extracted (and typed) from the view monolith: the rudimentary questions the
// ship answers, how its ten guesses read as a "looking for", where a hoped-for word ranks, and the choice
// between two rivals on a logic chain.

import { esc } from '../../lib/format';
import { btnCls } from '../../lib/ui';

export interface AskQuestion {
  text: string;
  hope: string;
  about: string;
}

// the rudimentary questions each carry the answer we would hope for, so "run all" reads as a test
export const ASK_QUESTIONS: AskQuestion[] = [
  { text: 'Once upon a', hope: 'time', about: 'a stock phrase' },
  { text: 'The cat sat on the', hope: 'mat', about: 'a nursery line' },
  { text: 'One, two, three, four,', hope: 'five', about: 'counting' },
  { text: 'Monday, Tuesday,', hope: 'Wednesday', about: 'a sequence' },
  { text: 'The opposite of hot is', hope: 'cold', about: 'an opposite' },
  { text: 'Quoth the Raven, Nevermore. Quoth the Raven,', hope: 'Nevermore', about: 'copying back (the Nevermore card)' },
  { text: 'Mary had a little lamb, its fleece was white as', hope: 'snow', about: 'a verse it may have read' },
  { text: 'If it rains, the ground gets wet. It rained, so the ground is', hope: 'wet', about: 'cause and effect' },
  { text: 'The man went to the baker to buy some', hope: 'bread', about: 'common sense' },
  { text: 'Q: What colour is the sky?\nA: The sky is', hope: 'blue', about: 'a question' },
];

// which of the two a ship chose on a logic chain: the premises' answer ranked above the rival among its ten
// guesses, or the rival above it, or neither in its ten
export const chose = (rank: number | null | undefined, rrank: number | null | undefined): string =>
  rank && (!rrank || rank < rrank) ? 'the premises' : rrank && (!rank || rrank < rank) ? 'the rival' : 'neither';

// what a ship is looking for after a line: its ten guesses' probability summed by part of speech (the server
// tags each guess as the shapes evaluator does), the fine tags with Ogden's coarse tier beside
export const COARSE_WORD: Record<string, string> = { THING: 'a thing', QUALITY: 'a quality', OPERATION: 'an operation', MARK: 'a mark' };

export function lookingFor(g: any): string {
  if (!g || !g.looking_for || !g.looking_for.length) return '';
  const fine = g.looking_for.filter((t: any) => t.share >= 0.02).slice(0, 5).map((t: any) => `<span class="postag" title="${esc(t.about || '')}"><b>${esc(t.tag)}</b> ${Math.round(100 * t.share)}%</span>`).join(' ');
  const coarse = (g.looking_for_coarse || []).filter((t: any) => t.share >= 0.02).map((t: any) => `${esc(COARSE_WORD[t.tag] || t.tag)} ${Math.round(100 * t.share)}%`).join(' · ');
  return `<div class="lookingfor">it is looking for: ${fine}${coarse ? ` <span class="s">· in Ogden's terms, ${coarse}</span>` : ''}</div>`;
}

// where the hoped-for word is among the guesses (a whole word; a piece may start it)
export const hopeRank = (gs: any[], hope: string): number | null => {
  const h = hope.toLowerCase();
  const i = gs.findIndex((g) => {
    const w = (g.word || '').trim().toLowerCase().replace(/[^a-z' ]/g, '');
    if (!w) return false;
    if (g.piece === true) return h === w || (w.length >= 2 && h.startsWith(w));
    return w === h || w.split(' ')[0] === h;
  });
  return i < 0 ? null : i + 1;
};

export const showPiece = (s: string): string => (s === '\n' ? '⏎' : s.replace(/ /g, '·'));

// a chapter's source button, opening the cited section of De Morgan's book in the reader
export const mathsSource = (c: any): string =>
  c.source && c.source.section ? `<button type="button" class="${btnCls('ghost', 'srcbtn')}" data-mbook="${esc(c.source.book)}" data-at="${c.source.at ?? 0}" title="open De Morgan's ${esc(c.source.section)} in the reader">De Morgan: ${esc(c.source.section.replace(/^Book I, /, ''))} ↗</button>` : '';
