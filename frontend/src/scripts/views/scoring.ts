// The Scoring tab's shared definitions, extracted (and typed) from the view monolith: the metric-name maps
// that decide which score is science and which is art, and the two table-row builders.

import { esc } from '../../lib/format';
import { info, METRIC_KEY, HELP } from '../../lib/info';
import { pillCls, emptyCls } from '../../lib/ui';

export const SPLIT_LABEL: Record<string, string> = { word_inside: 'inside a word', word_start: 'word start', punct: 'punctuation', space: 'space', newline: 'newline' };

export const LAW_COLS: [string, string, number][] = [
  ['nonword_rate', 'non-words', 3], ['zipf', 'Zipf', 2], ['heaps', 'Heaps', 2], ['word_len', 'word length', 2],
  ['punct_per_100w', 'punct /100 w', 1], ['unbalanced_per_kw', 'unbalanced /1k w', 1], ['cap_after_stop', 'capital after stop', 2],
  ['word_len_js', 'word-length JS', 3], ['punct_js', 'punct mix JS', 3],
];

// a metric not named here counts as science (UI.md "Scoring"); the art metrics judge the writing, not the bets
export const ART = new Set(['non-words', 'Zipf and Heaps', 'word length, punctuation mix', 'balance and capitals',
  'traits as they emerge', 'minimal pairs', 'register probe', 'the 9m laws']);

export const metricRows = (list: [string, string, string][]): string =>
  list.length ? list.map((m) => `<tr><td><b>${esc(m[0])}</b>${info(METRIC_KEY[m[0]])}</td><td>${esc(m[1])}</td>
    <td>${HELP[METRIC_KEY[m[0]]] ? esc(HELP[METRIC_KEY[m[0]]][1]) : '–'}</td>
    <td><span class="${pillCls(m[2] === 'live' ? ' live' : '')}">${esc(m[2])}</span></td></tr>`).join('')
    : '<tr><td colspan="4" class="${emptyCls(true)}">none for this model yet</td></tr>';

export const runCells = (x: any): string => `<td>${esc(x.ship || '')}</td><td>${esc(x.name)}</td><td>${esc((x.status || '').split(':')[0])}</td>`;
