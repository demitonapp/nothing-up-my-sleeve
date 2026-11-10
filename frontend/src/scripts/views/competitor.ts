// One competitor (or a Thorp ship version): its chaining result, logic deck, cards and every rung
// (UI.md "Leaderboard"). Typed HTML fragments for the island; the charts are drawn by the island after
// render, because ECharts needs the browser.

import { CARD_FACE, deckHand } from '../../lib/deck';
import { esc, fmt, fmtParams, signed } from '../../lib/format';
import { cardCls, emptyCls, pillCls } from '../../lib/ui';
import { cardBadge, shortAbout } from './helpers';

type Payload = any;
const LOGIC_VARIANTS: [string, string][] = [['lift_one_hop', 'one hop'], ['lift_both', 'two hops (both premises)'], ['lift_three_hop', 'three hops'], ['lift_first', 'first premise only'], ['lift_second', 'second premise only'], ['lift_swapped', 'premises swapped'], ['lift_padded', 'a third fact added']];
const DECK: [string, string][] = [['previous_word', 'Previous-word'], ['nevermore', 'Nevermore (induction)'], ['mover', 'Mover'], ['comparator', 'Comparator'], ['bridge', 'Bridge']];

const classLink = (preset: string, name?: string): string => (preset ? `<a href="/harbours">${esc(preset)}${name ? ` · ${esc(name)}` : ''}</a>` : '–');
const makerOf = (m: string): string => (m || '').split('/')[0] || '';

export interface CompetitorHtml {
  title: string;
  pills: string;
  over: string;
  sum: string;
  tests: string;
  cards: string;
  variants: { key: string; label: string; value: number }[];
  relations: { key: string; value: number }[];
  bridge: { curve: number[]; lit: boolean; threshold: number | null } | null;
  rungsHead: string;
  rungsBody: string;
}

export function competitorHtml(d: Payload, stars: Payload[]): CompetitorHtml {
  const chainingTests = d.chains.map((c: any) => c.rungs.find((r: any) => /chains two facts/i.test(r.rung || ''))).filter(Boolean);
  const read = chainingTests.filter((t: any) => t.lift != null), mean = read.length ? read.reduce((a: number, t: any) => a + t.lift, 0) / read.length : null;
  const passed = chainingTests.filter((t: any) => t.performed).length, t = d.tenth;
  const title = d.label || d.model || 'competitor';
  const pills = d.thorp ? `<span class="${pillCls('good')}">Thorp</span>${d.current ? '' : ` <span class="${pillCls('')}">not the current version</span>`}`
    : `${d.competitor ? `<span class="${pillCls('blue')}">2–4B competitor</span> ` : ''}${d.ladder ? `<span class="${pillCls('')}">reference ladder</span>` : ''}`;
  const over = d.thorp
    ? [
      ['class', classLink(d.ship && d.ship.preset || '')],
      ['parameters', fmtParams(d.params)],
      ['the ship', `${d.ship && d.ship.ship_key ? `<a href="/ships/${encodeURIComponent(d.ship.ship_key)}">${esc(d.ship.ship || d.ship.ship_key)}</a>` : esc(d.ship && d.ship.ship || '')}<div class="s">${d.ship && d.ship.sailings || 0} sailing${(d.ship && d.ship.sailings) === 1 ? '' : 's'}, every reading the mean of their latest</div>`],
      ['the voyages', (d.ship && d.ship.runs || []).map((r: string) => `<a href="/ships/${encodeURIComponent(r)}">${esc(r)}</a>`).join(', ') || '–'],
      ['version', `${d.version ? `<b>v${d.version}</b>, crowned ${esc(String(d.crowned || '').replace('T', ' '))}` : 'not crowned'}${(d.history || []).length ? `<div class="s">${d.history.map((h: any) => `v${h.v} ${esc(h.ship)} (${signed(h.chaining_lift)}, ${esc(String(h.crowned || '').replace('T', ' '))})`).join(' → ')}</div>` : ''}<div class="s">a new version is crowned only when a ship beats the last by more than the noise (0.03)</div>`],
    ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('')
    : [
      ['made by', makerOf(d.model) || '–'],
      ['parameters', fmtParams(d.params)],
      ['checkpoint', `<span class="mono">${esc(d.model)}</span>`],
      ['Thorp must match it at', d.competitor && d.params ? `<b>${fmtParams(t && t.smoke_at || d.params / 10)}</b> <span class="s">a tenth its size</span>${t && t.scored ? ['bending', 'linear'].filter((k) => t[k]).map((k) => `<div class="s">${k === 'linear' ? 'straight' : k} forecast there ${signed(t[k].predicted)}${t[k].p_at_or_above_target != null ? ` · P ${Math.round(100 * t[k].p_at_or_above_target)}%` : ''}</div>`).join('') : ''}` : '<span class="s">not a competitor: a reference model that grades the chains</span>'],
    ].map(([k, v]) => `<div><div class="k">${k}</div><div>${v}</div></div>`).join('');
  const L = d.logic;
  const sum = !d.scored ? `<div class="${emptyCls()}">not scored yet: the competitors are being scored now, a few minutes each</div>`
    : `<div class="tfs"><b>${mean == null ? '–' : signed(mean)}</b><span>chaining lift (mean of the four)</span></div>
       <div class="tfs"><b>${passed} of ${chainingTests.length}</b><span>chaining tests performed</span></div>
       <div class="tfs"><b class="${L && L.performed ? 'good' : ''}">${L && L.gain != null ? signed(L.gain) : 'not read'}</b><span>chaining gain on the logic deck${L && L.score != null ? `, ${Math.round(100 * L.score)}% of items right` : ''}${L && L.items_n ? `, ${L.items_n} items` : ''}${L && L.performed ? ' ✓' : ''}</span></div>`;
  const tests = chainingTests.map((x: any, i: number) => `<tr><td><a href="/discoveries/${esc(x.key)}"><b>${esc(x.name)}</b></a></td><td><a href="/discoveries/chains/${esc(d.chains[i].key)}">${esc(d.chains[i].name)}</a></td>
    <td class="${x.performed ? 'good' : ''}">${x.lift != null ? signed(x.lift) : '–'}</td><td>${x.score != null ? Math.round(100 * x.score) + '%' : '–'}</td><td>${x.performed ? '✓' : ''}</td></tr>`).join('');
  const variants = L ? LOGIC_VARIANTS.filter(([k]) => L[k] != null).map(([k, label]) => ({ key: k, label, value: L[k] })) : [];
  const relations = L ? Object.keys(L).filter((k) => k.startsWith('gain_')).map((k) => ({ key: k.slice(5), value: L[k] })) : [];
  // the cards: the hand it holds (lit, fanned) and what is still in the deck (set aside face down), then the readings
  const C = d.cards, read2 = !C || C.attention_readable !== false;
  const thrOf = (key: string) => (stars.find((s) => s.key === key) || {}).threshold;
  const hand = DECK.map(([key, name]) => {
    const x = C && C[key], thr = thrOf(key);
    const state = !C ? 'unread' : key !== 'bridge' && !read2 ? 'unreadable' : !x ? 'unread' : (x.lit || x.lit_shared) ? 'lit' : (x.max == null && key === 'bridge') ? 'unreadable' : 'unlit';
    const best = x ? Math.max(x.max ?? -Infinity, x.shared ?? -Infinity) : null;
    const star = stars.find((s) => s.key === key);
    return { key, name, held: state === 'lit', state, near: thr && best != null && isFinite(best) ? best / thr : null, x, thr, untrusted: false, about: star && shortAbout(star.about), href: '/discoveries/stars' };
  });
  const rowOf = (c: any) => {
    const x = c.x || {}, v = cardBadge(d.card_verdicts, c.key);
    const read = c.state === 'unread' ? '<span class="s">not read yet</span>' : c.state === 'unreadable' ? '<span class="s">unreadable</span>'
      : c.key === 'bridge' ? `best ${x.max != null ? fmt(x.max) + ' nats' : '<i>unreadable</i>'}${x.best_layer != null ? ` at layer ${x.best_layer}${x.layers ? ` of ${x.layers}` : ''}` : ''}`
      : `one head ${x.max != null ? fmt(x.max) : '–'}${x.shared != null ? ` · shared ${fmt(x.shared)}${x.shared_layer != null ? ` (layer ${x.shared_layer})` : ''}` : ''}${'copy_gain' in x ? ` · copy gain ${x.copy_gain != null ? fmt(x.copy_gain) + ' nats/token' : '<i>unreadable</i>'}` : ''}`;
    const f = CARD_FACE[c.key] || {};
    return `<tr class="${c.held ? 'held' : ''}"><td><span class="suitmark">${f.rank || ''}${f.suit || ''}</span> <b>${esc(c.name)}</b></td><td>${c.held ? `<span class="${pillCls('good')}">in hand</span>` : `<span class="${pillCls('')}">${{ unlit: 'in the deck', unread: 'not read', unreadable: 'unreadable' }[c.state as 'unlit' | 'unread' | 'unreadable']}</span>`}</td>
      <td>${read}</td><td>${c.thr != null ? c.thr : '–'}</td><td>${v}</td></tr>`;
  };
  const B = C && C.bridge;
  const bridge = B && B.curve && B.curve.length ? { curve: B.curve as number[], lit: !!B.lit, threshold: thrOf('bridge') ?? null } : null;
  const cards = deckHand(hand as any, { empty: !C ? 'its cards are being read' : 'no card lit yet' })
    + `<div class="scroll"><table class="decktable" data-nosort><thead><tr><th>card</th><th></th><th>its reading</th><th>the mark</th><th>the judge</th></tr></thead><tbody>${hand.map(rowOf).join('')}</tbody></table></div>`
    + (bridge ? '<div class="k mt">the bridge over layers <span class="s">nats at the answer\'s position; the mark dotted</span></div><div class="chart cpbridge" id="cpbridge"></div>' : '');
  const width = Math.max(...d.chains.map((c: any) => c.rungs.length - 1));
  const rungsHead = `<tr><th>chain</th>${d.chains[0].rungs.slice(0, width).map((r: any) => `<th>${esc(r.rung || '')}</th>`).join('')}</tr>`;
  const rungsBody = d.chains.map((c: any) => `<tr><td><a href="/discoveries/chains/${esc(c.key)}"><b>${esc(c.name)}</b></a></td>${c.rungs.slice(0, width).map((r: any) => `<td><a href="/discoveries/${esc(r.key)}">${esc(r.name)}</a><div class="${r.performed ? 'good' : 's'}">${r.lift != null ? `${signed(r.lift)} · ${r.score != null ? Math.round(100 * r.score) + '%' : ''}${r.performed ? ' ✓' : ''}` : 'not read'}</div></td>`).join('')}</tr>`).join('');
  return { title, pills, over, sum, tests, cards, variants, relations, bridge, rungsHead, rungsBody };
}

export async function drawCompetitorCharts(html: CompetitorHtml, thorp: boolean): Promise<void> {
  const { plot, layout, tok } = await import('../../lib/charts');
  const vs = html.variants;
  if (vs.length) plot('cpvariants', [{ type: 'bar', orientation: 'h', y: vs.map((v) => v.label), x: vs.map((v) => v.value),
    marker: { color: vs.map((v) => v.key === 'lift_both' ? tok('accent') : /one_hop|three_hop/.test(v.key) ? tok('blue') : tok('muted')) },
    hovertemplate: '%{y}: %{x:.3f}<extra></extra>' }],
    layout({ height: 260, margin: { l: 170, r: 10, t: 10, b: 30 }, yaxis: { autorange: 'reversed' }, xaxis: { title: { text: 'mean lift' }, zeroline: true } }));
  else if (document.getElementById('cpvariants')) plot('cpvariants', [], layout({ height: 260, annotations: [{ text: 'the logic deck is not read on this model yet', showarrow: false, xref: 'paper', yref: 'paper', x: 0.5, y: 0.5 }] }));
  const rel = html.relations;
  if (rel.length) plot('cprelations', [{ type: 'bar', x: rel.map((r) => r.key === 'cause' ? 'cause and effect' : r.key), y: rel.map((r) => r.value),
    marker: { color: rel.map((r) => r.value >= 0.1 ? tok('good') : r.value >= 0 ? tok('blue') : tok('bad')), line: { color: rel.map((r) => r.key === 'cause' ? tok('accent') : 'rgba(0,0,0,0)'), width: rel.map((r) => r.key === 'cause' ? 3 : 0) } },
    hovertemplate: '%{x}: %{y:.3f}<extra></extra>' }],
    layout({ height: 260, margin: { l: 50, r: 10, t: 10, b: 40 }, yaxis: { title: { text: 'chaining gain' } }, shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0.1, y1: 0.1, line: { color: tok('accent'), dash: 'dot', width: 1 } }] }));
  if (html.bridge && document.getElementById('cpbridge')) {
    const b = html.bridge;
    plot('cpbridge', [{ x: b.curve.map((_, i) => i), y: b.curve, mode: 'lines+markers', line: { color: b.lit ? tok('good') : tok('blue'), width: 1.6 }, hovertemplate: 'layer %{x}: %{y:.2f}<extra></extra>' }],
      layout({ height: 160, margin: { l: 40, r: 10, t: 6, b: 30 }, showlegend: false, xaxis: { title: { text: 'layer' }, dtick: Math.max(1, Math.round(b.curve.length / 8)) }, shapes: b.threshold != null ? [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: b.threshold, y1: b.threshold, line: { color: tok('accent'), dash: 'dot', width: 1 } }] : [] }));
  }
}
