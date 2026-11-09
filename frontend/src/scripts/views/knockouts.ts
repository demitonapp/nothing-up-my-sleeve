// The knockout deck (UI.md "the deck"): one reference model's four cards silenced, each against three random
// controls, read on the card's own measure. Extracted (and typed) from the view monolith; `knockoutBlock` renders
// the table and `knockoutChart` the grouped bars, both taking the knockout data and the chart id.

import { CARD_FACE } from '../../lib/deck';
import { esc, signed } from '../../lib/format';
import { pillCls } from '../../lib/ui';
import { layout, plot, tok } from '../../lib/charts';

export const KO_CARDS: [string, string][] = [['previous_word', 'Previous-word'], ['nevermore', 'Nevermore'], ['mover', 'Mover'], ['comparator', 'Comparator']];

export const knockoutBlock = (k: any, id: string): string => {
  const base = k.baseline || {};
  const v = k.verdict || {};
  const controls = k.controls || [];
  const drop = (cond: any, measure: string): number | null => (cond && base[measure] != null && cond[measure] != null ? base[measure] - cond[measure] : null);
  const ctrlCause = controls.map((c: any) => drop(c, 'cause_gain'));
  const largest = Math.max(0, ...ctrlCause.filter((x: number | null) => x != null));
  const line = Math.max(0.1, 2 * largest);
  const badges = KO_CARDS.map(([key, name]) => {
    const x = v[key];
    const f = CARD_FACE[key] || {};
    if (!x) return `<span class="kobadge"><b>${f.rank || ''}${f.suit || ''}</b> ${esc(name)} <i>not knocked out</i></span>`;
    return `<span class="kobadge ${x.necessary ? 'need' : ''}" title="${esc(x.measure || 'cause_gain')} dropped ${x.drop != null ? x.drop.toFixed(3) : '–'}; the largest random drop ${x.largest_random_drop != null ? x.largest_random_drop.toFixed(3) : '–'}; chaining lift dropped ${x.chaining_lift_drop != null ? x.chaining_lift_drop.toFixed(3) : '–'}"><b>${f.rank || ''}${f.suit || ''}</b> ${esc(name)} <i>${x.necessary ? 'NECESSARY' : 'not shown'}</i></span>`;
  }).join('');
  const rows = KO_CARDS.filter(([key]) => v[key] || k[key]).map(([key, name]) => {
    const x = v[key] || {};
    const heads = (k.card_heads || {})[key] || [];
    return `<tr><td><b>${esc(name)}</b></td><td class="s">${esc((x.measure || (key === 'comparator' ? 'order_gain' : 'cause_gain')).replace('_', ' '))}</td>
      <td>${x.drop != null ? signed(x.drop) : '–'}</td><td>${x.largest_random_drop != null ? signed(x.largest_random_drop) : '–'}</td><td>${x.chaining_lift_drop != null ? signed(x.chaining_lift_drop) : '–'}</td>
      <td>${x.necessary ? `<span class="${pillCls('good')}">necessary</span>` : `<span class="${pillCls('')}">not shown</span>`}</td>
      <td class="mono kohd">${heads.map((h: [number, number]) => `${h[0]}:${h[1]}`).join(' ')}</td></tr>`;
  }).join('');
  return `<div class="kobadges">${badges}</div>
    <div class="row koro"><div class="chart" id="${id}"></div>
    <div class="scroll"><table class="kotable" data-nosort><thead><tr><th>card</th><th>measure</th><th>lost</th><th>largest random</th><th>chaining lift lost</th><th>verdict</th><th>its ${k.k || 8} heads <span class="s">layer:head</span></th></tr></thead><tbody>${rows}</tbody></table>
    <p class="s">baseline: cause gain ${base.cause_gain != null ? signed(base.cause_gain) : '–'} · order gain ${base.order_gain != null ? signed(base.order_gain) : '–'} · logic gain ${base.logic_gain != null ? signed(base.logic_gain) : '–'} · chaining lift ${base.chaining_lift != null ? signed(base.chaining_lift) : '–'}${k.layers ? ` · ${k.layers} layers × ${k.heads} heads` : ''}</p></div></div>`;
};

export const knockoutChart = (k: any, id: string): void => {
  // grouped per card: the card's own drop and the three random draws' drops, all on that card's own measure
  // (the comparator, order gain; the rest, cause gain), with the card's rule line at max(0.1, 2 × its largest
  // random drop).
  const base = k.baseline || {};
  const v = k.verdict || {};
  const controls = k.controls || [];
  const cards = KO_CARDS.filter(([key]) => v[key]);
  const measureOf = (key: string): string => v[key].measure || (key === 'comparator' ? 'order_gain' : 'cause_gain');
  const lost = (cond: any, m: string): number | null => (cond && base[m] != null && cond[m] != null ? base[m] - cond[m] : null);
  const names = cards.map(([, n]) => n);
  const traces: any[] = [{
    type: 'bar', name: 'its 8 heads silenced', x: names, y: cards.map(([key]) => v[key].drop),
    marker: { color: cards.map(([key]) => (v[key].necessary ? tok('good') : tok('blue'))) },
    text: cards.map(([key, n]) => `${n}: ${measureOf(key).replace('_', ' ')} lost ${v[key].drop != null ? v[key].drop.toFixed(3) : '–'}`),
    textposition: 'none', hovertemplate: '%{text}<extra></extra>',
  }];
  controls.forEach((c: any, i: number) => traces.push({
    type: 'bar', name: `random ${i + 1}`, x: names, y: cards.map(([key]) => lost(c, measureOf(key))),
    marker: { color: tok('muted'), opacity: 0.5 + 0.15 * i },
    text: cards.map(([key]) => `random draw ${i + 1}: ${measureOf(key).replace('_', ' ')} lost ${lost(c, measureOf(key)) != null ? lost(c, measureOf(key))!.toFixed(3) : '–'}`),
    textposition: 'none', hovertemplate: '%{text}<extra></extra>', showlegend: i === 0, legendgroup: 'random',
  }));
  const shapes: any[] = [];
  const notes: any[] = [];
  cards.forEach(([key], i) => {
    const largest = v[key].largest_random_drop ?? Math.max(0, ...controls.map((c: any) => lost(c, measureOf(key)) ?? 0));
    const line = Math.max(0.1, 2 * largest);
    shapes.push({ type: 'line', xref: 'x', yref: 'y', x0: i - 0.45, x1: i + 0.45, y0: line, y1: line, line: { color: tok('accent'), dash: 'dot', width: 1.6 } });
    notes.push({ xref: 'x', yref: 'y', x: i, y: line, yanchor: 'bottom', showarrow: false, text: `${line.toFixed(2)}${measureOf(key) === 'order_gain' ? ' (order)' : ''}`, font: { size: 9, color: tok('accent') } });
  });
  plot(id, traces, layout({ barmode: 'group', height: 300, margin: { l: 50, r: 10, t: 10, b: 40 }, yaxis: { title: { text: 'gain lost when silenced' } },
    legend: { orientation: 'h', y: -0.18 }, shapes, annotations: notes }));
};
