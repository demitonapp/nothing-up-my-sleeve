// The leaderboard's cell renderers and their constants, extracted (and typed) from the view monolith.
// Pure: each returns an HTML string from its arguments and touches no module state or DOM.

import { CARD_FACE } from '../../lib/deck';
import { esc, fmt, signed } from '../../lib/format';
import { shipHash } from '../router';

// the labs, as thorp/labs.py LABS: a model's family, its maker, and the lab page's key (#/leaderboard/lab/<key>)
export const MAKER: [RegExp, string, string, string][] = [
  [/qwen/i, 'Qwen', 'Alibaba', 'alibaba'],
  [/llama/i, 'Llama', 'Meta', 'meta'],
  [/phi/i, 'Phi', 'Microsoft', 'microsoft'],
  [/pythia/i, 'Pythia', 'EleutherAI', 'eleutherai'],
  [/gemma/i, 'Gemma', 'Google', 'google'],
  [/smollm/i, 'SmolLM', 'Hugging Face', 'huggingface'],
];
export const makerOf = (m: string): string => (MAKER.find(([re]) => re.test(m)) || [null, '', ''])[2]!;
export const makerLink = (m: string): string => {
  const x = MAKER.find(([re]) => re.test(m || ''));
  return x ? `<a href="/leaderboard/lab/${x[3]}" title="${esc(x[2])}: its models' best and worst">${esc(x[2])}</a>` : '';
};

export const CHAIN_LABEL: Record<string, string> = {
  origin_test: 'the Origin',
  energy_test: 'energy',
  mendeleev_gaps: "Mendeleev's gaps",
  recurrence_test: 'the eternal return',
};
export const CHAIN_SHORT: Record<string, string> = {
  origin_test: 'Origin',
  energy_test: 'energy',
  mendeleev_gaps: 'Mendeleev',
  recurrence_test: 'return',
};
export const RUNG_CLASS = ['pan', 'augustus', 'speller', 'stylist', '50m'];

// The four necessary cards (the deck's mark): previous-word, Nevermore, mover, comparator.
export const NEEDED: [string, string][] = [['previous_word', 'Previous-word'], ['nevermore', 'Nevermore'], ['mover', 'Mover'], ['comparator', 'Comparator']];

// The mini set of the four necessary cards, lit where the composition has them.
export const minicards = (c: Record<string, boolean>): string =>
  `<span class="miniset">${NEEDED.map(([k, n]) => {
    const f = CARD_FACE[k] || {};
    return `<span class="minicard${c[k] ? ' on' : ''}" title="${esc(n)}: ${c[k] ? 'lit' : 'not lit'}"><b>${f.rank || ''}</b><i>${f.suit || ''}</i></span>`;
  }).join('')}</span>`;

export const climbBar = (c: number | null, max = 5): string => {
  if (c == null) return '<span class="s">–</span>';
  const pct = Math.max(0, Math.min(100, (100 * c) / max));
  return `<div class="climb" title="climb ${fmt(c, 2)} of ${max}"><div class="cfill" style="width:${pct}%"></div>${Array.from({ length: max - 1 }, (_, i) => `<i style="left:${(100 * (i + 1)) / max}%"></i>`).join('')}<b>${fmt(c, 2)}</b></div>`;
};

export const chainingCell = (v: number | null, thr: number): string => {
  if (v == null) return '<span class="s">not read</span>';
  return `<span class="${v >= thr ? 'good' : Math.abs(v) <= 0.03 ? 's' : ''}" title="${v >= thr ? 'at the mark' : Math.abs(v) <= 0.03 ? 'within the noise (about 0.03 of zero)' : 'below the mark'}">${signed(v)}</span>`;
};

export const chainStrip = (chains: Record<string, { rungs: number; partial?: number; next?: string }> | null | undefined): string => {
  if (!chains) return '';
  return `<div class="cstrip">${Object.entries(chains)
    .map(([k, c]) => `<div class="csr" title="${esc(CHAIN_LABEL[k] || k)}: ${c.rungs} rung${c.rungs === 1 ? '' : 's'} performed${c.next ? `, next ${esc(c.next.replace(/_test$/, ''))} at ${Math.round(100 * (c.partial ?? 0))}% of its mark` : ', all five'}"><span>${esc(CHAIN_SHORT[k] || k)}</span>${RUNG_CLASS.map((r, i) => `<em class="${i < c.rungs ? 'on' : ''}">${i === c.rungs && c.partial ? `<u style="width:${Math.round(100 * c.partial)}%"></u>` : ''}</em>`).join('')}</div>`)
    .join('')}</div>`;
};

export const runLink = (x: { run?: string }): string => (x.run ? `<a href="${shipHash(x.run)}">${esc(x.run)}</a>` : '–');

export const logicCell = (l: { gain?: number | null; score?: number | null; performed?: boolean } | null, kind: string): string => {
  if (kind === 'forecast') return '';
  if (!l || l.gain == null) return '<span class="s">not read yet</span>';
  return `<span class="tc${l.performed ? ' lit' : ''}" title="chaining gain ${signed(l.gain)}${l.score != null ? `, ${Math.round(100 * l.score)}% of items right` : ''}${l.performed ? ', performed' : ''}">${signed(l.gain)} <i>${l.score != null ? Math.round(100 * l.score) + '%' : ''}</i>${l.performed ? ' ✓' : ''}</span>`;
};

export const testCell = (t: { name?: string; lift?: number | null; score?: number | null; performed?: boolean } | null): string => {
  if (!t || t.lift == null) return '<span class="s">–</span>';
  return `<span class="tc${t.performed ? ' lit' : ''}" title="${esc(t.name || '')}: lift ${signed(t.lift)}, ${t.score != null ? Math.round(100 * t.score) + '% of pairs right' : ''}${t.performed ? ', performed' : ''}">${signed(t.lift)} <i>${t.score != null ? Math.round(100 * t.score) + '%' : ''}</i>${t.performed ? ' ✓' : ''}</span>`;
};
