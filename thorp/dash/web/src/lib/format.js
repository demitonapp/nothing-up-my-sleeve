// small formatters shared by every panel
export const fmt = (v, d = 3) => v == null || isNaN(v) ? '–' : Number(v).toFixed(d);
export const big = v => v == null ? '–' : v >= 1e9 ? (v / 1e9).toFixed(2) + 'B' : v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : String(Math.round(v));
export const fmtBytes = v => !v ? '–' : v >= 1e9 ? (v / 1e9).toFixed(2) + ' GB' : v >= 1e6 ? (v / 1e6).toFixed(1) + ' MB' : (v / 1e3).toFixed(0) + ' KB';
export const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
export const get = async u => (await fetch(u)).json();
export const log10 = v => v > 0 ? Math.log10(v) : null;
export const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
