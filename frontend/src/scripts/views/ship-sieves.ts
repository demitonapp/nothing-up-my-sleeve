// The ship page's sieves tab (moved under each ship on 9 November): the sieve cards, the heading sieve
// and the settled table. The push/move heats and the kink panels are the ship's own (views/ship.ts).
// Chart-heavy, so the island imports this module at run time only.

import { get } from '../../lib/format';
import { cardCls, emptyCls } from '../../lib/ui';
import { KINK_FIRM, KINK_MIN, kinksOf, setKinkRule } from '../../lib/analysis';
import { firstReach, groupLabel, groupOf, groupOrder, layerOnly, topKeys, valueAt } from '../../lib/metrics';
import { esc, fmt } from '../../lib/format';
import { sieveHeat } from './sieves';
import type { Metrics } from '../types';

const SETTLE_AT = 0.8;
const SETTLE_RECORDS = 3;

let sieveDef: any = null;

export async function drawShipSieves(m: Metrics, r: any): Promise<void> {
  const cards = document.getElementById('sievecards');
  if (!cards) return;
  if (!sieveDef) {
    try { sieveDef = await get('/api/sieves'); } catch { return; }
    setKinkRule(sieveDef.kink_min_records, sieveDef.kink_firm);
  }
  const kr = document.getElementById('kinkrule');
  if (kr && !kr.textContent) kr.textContent = `${KINK_MIN} records when the two lines remove at least ${Math.round(KINK_FIRM * 100)}% of one line's error`;
  cards.innerHTML = (sieveDef.sieves || []).map((v: any) => `<div class="${cardCls(false, 'card')}"><div class="top"><span class="preset">${esc(v.name)}</span>
    <span class="mono">${esc(v.prefix)}</span></div><div class="ov">${esc(v.about)}</div></div>`).join('');
  const byGroup: Record<string, any> = {};
  for (const [k, v] of Object.entries(kinksOf(m, 'grad_norm/'))) byGroup[groupOf(k, 'grad_norm/')] = v;
  sieveHeat('sieve-heading', m, 'heading/', byGroup, { log: false, diverging: true,
    msg: r && r.status === 'running' && !topKeys(m, 'heading/').length ? 'the heading sieve starts with the next ship to sail; this voyage set out before it was fitted' : 'this voyage has no heading readings: the heading sieve started with ships voyage from 08:00 on 7 November' });
  const layers = layerOnly(m, 'grad_norm/').map((k) => groupOf(k, 'grad_norm/'));
  const lit = (sieveDef.stars || []).flatMap((st: any) => {
    const out: any[] = [], a = firstReach(m, st.metric, st.threshold), b = firstReach(m, st.shared_metric, st.threshold);
    if (a != null) out.push({ name: st.name, step: a, layer: valueAt(m, st.layer, a), how: 'one head' });
    if (b != null) out.push({ name: st.name, step: b, layer: valueAt(m, st.shared_layer, b), how: 'shared' });
    return out;
  });
  const tb = document.querySelector('#settledtable tbody');
  if (tb) tb.innerHTML = layers.length ? [...layers].reverse().map((g) => {
    const sr = (m as any)['heading/' + g], i = groupOrder(g);
    let settled: number | null = null;
    if (sr) for (let j = 0; j + SETTLE_RECORDS <= sr[1].length; j++) if (sr[1].slice(j, j + SETTLE_RECORDS).every((v: number) => v >= SETTLE_AT)) { settled = sr[0][j]; break; }
    const here = lit.filter((x: any) => x.layer != null && Math.round(x.layer) === i);
    const kk = byGroup[g];
    return `<tr><td>${esc(groupLabel(g))}</td><td data-sort="${settled ?? ''}">${sr ? (settled != null ? `step ${settled}` : 'not yet') : '–'}</td>
      <td>${sr ? fmt(sr[1][sr[1].length - 1], 2) : '–'}</td><td data-sort="${kk ? kk.step : ''}">${kk ? `step ${kk.step}${kk.tentative ? ' (tentative)' : ''}` : '–'}</td>
      <td>${here.length ? here.map((x: any) => `${esc(x.name)} at step ${x.step} (${x.how})`).join('; ') : '–'}</td></tr>`;
  }).join('') : `<tr><td colspan="5" class="${emptyCls(true)}">no sieve readings on this voyage yet</td></tr>`;
}
