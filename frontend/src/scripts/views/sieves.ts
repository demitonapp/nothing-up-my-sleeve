// The sieves' shared chart: a per-layer heatmap of one sieve, with each layer's push kink marked
// (UI.md "Sieves"). Extracted (and typed) from the view monolith; pure — it takes its series and kinks
// as arguments and touches no module state.

import { C, empty, layout, plot, tok } from '../../lib/charts';
import { log10 } from '../../lib/format';
import { groupLabel, groupOf, topKeys } from '../../lib/metrics';
import type { Metrics } from '../types';

export const sieveHeat = (
  id: string,
  m: Metrics,
  prefix: string,
  kinksByGroup: Record<string, { step: number; tentative?: boolean }>,
  opts: { log?: boolean; diverging?: boolean; msg?: string } = {},
): void => {
  const { log = true, diverging = false, msg = 'no readings for this sieve on this voyage' } = opts;
  const keys = topKeys(m, prefix);
  if (!keys.length) {
    empty(id, msg);
    return;
  }
  const x = m[keys[0]][0];
  const y = keys.map((k) => groupLabel(groupOf(k, prefix)));
  const z = keys.map((k) => m[k][1].map((v) => (log ? log10(v) : v)));
  const data: unknown[] = [
    {
      type: 'heatmap',
      x,
      y,
      z,
      hovertemplate: `step %{x}<br>%{y}<br>${log ? 'log10 ' : ''}%{z:.2f}<extra></extra>`,
      ...(diverging
        ? { colorscale: [[0, C.bad], [0.5, tok('panel')], [1, C.good]], zmin: -1, zmax: 1, zmid: 0 }
        : { colorscale: 'Viridis' }),
      colorbar: { title: log ? 'log10' : 'cosine', thickness: 10 },
    },
  ];
  const kx: number[] = [];
  const ky: string[] = [];
  const kt: string[] = [];
  keys.forEach((k, i) => {
    const kk = kinksByGroup[groupOf(k, prefix)];
    if (kk) {
      kx.push(kk.step);
      ky.push(y[i]);
      kt.push(`push kink at ${kk.step}${kk.tentative ? ' (tentative)' : ''}`);
    }
  });
  if (kx.length) {
    data.push({
      type: 'scatter',
      x: kx,
      y: ky,
      text: kt,
      mode: 'markers',
      marker: { symbol: 'diamond', size: 9, color: '#fff', line: { color: '#000', width: 1 } },
      hovertemplate: '%{y}<br>%{text}<extra></extra>',
      showlegend: false,
    });
  }
  plot(id, data, layout({ margin: { l: 80, r: 10, t: 10, b: 36 }, xaxis: { title: 'step', gridcolor: C.line } }));
};
