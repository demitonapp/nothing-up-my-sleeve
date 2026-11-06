import Plotly from 'plotly.js-dist-min';

// the charts read the page's colour tokens (UI.md), so a colour is defined once, in the CSS
export const tok = n => getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim();
export const C = { text: tok('text'), muted: tok('muted'), line: tok('line'), accent: tok('accent'), blue: tok('blue'),
            good: tok('good'), bad: tok('bad'), track: tok('track'), c5: tok('c5') };
export const PALETTE = [C.blue, C.accent, C.good, C.bad, ...[5, 6, 7, 8, 9, 10, 11, 12].map(i => tok('c' + i))];
export const layout = (extra = {}) => Object.assign({
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: { color: C.text, size: 11 }, margin: { l: 50, r: 50, t: 10, b: 36 },
  xaxis: { gridcolor: C.line, zerolinecolor: C.line },
  yaxis: { gridcolor: C.line, zerolinecolor: C.line },
  legend: { orientation: 'h', y: -0.18, font: { size: 10 } }, hovermode: 'closest',
}, extra);
export const cfg = { displayModeBar: false, responsive: true };
export const empty = (id, msg = 'no data yet') => { Plotly.purge(id); document.getElementById(id).innerHTML = `<div class="empty">${msg}</div>`; };
export const plot = (id, data, lay) => { const el = document.getElementById(id); if (el.querySelector('.empty')) el.innerHTML = ''; Plotly.react(id, data, lay, cfg); };

export { Plotly };
