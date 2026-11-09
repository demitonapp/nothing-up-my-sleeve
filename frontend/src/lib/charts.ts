import { emptyCls } from './ui';
import Plotly from 'plotly.js-dist-min';

// the charts read the page's colour tokens (UI.md), so a colour is defined once, in the CSS
export const tok = (n: string): string => getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim();
export const C = { text: tok('text'), muted: tok('muted'), line: tok('line'), accent: tok('accent'), blue: tok('blue'),
            good: tok('good'), bad: tok('bad'), track: tok('track'), c5: tok('c5') };
export const PALETTE: string[] = [C.blue, C.accent, C.good, C.bad, ...[5, 6, 7, 8, 9, 10, 11, 12].map((i) => tok('c' + i))];
export const layout = (extra: Record<string, unknown> = {}): Record<string, unknown> => Object.assign({
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: { color: C.text, size: 11 }, margin: { l: 50, r: 50, t: 10, b: 36 },
  xaxis: { gridcolor: C.line, zerolinecolor: C.line },
  yaxis: { gridcolor: C.line, zerolinecolor: C.line },
  legend: { orientation: 'h', y: -0.18, font: { size: 10 } }, hovermode: 'closest',
}, extra);
export const cfg = { displayModeBar: false, responsive: true };
export const empty = (id: string, msg = 'no data yet'): void => {
  Plotly.purge(id);
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="${emptyCls()}">${msg}</div>`;
};
export const plot = (id: string, data: unknown, lay: Record<string, unknown>): void => {
  const el = document.getElementById(id);
  if (el && el.querySelector('.empty')) el.innerHTML = '';
  Plotly.react(id, data, lay, cfg);
};

export { Plotly };
