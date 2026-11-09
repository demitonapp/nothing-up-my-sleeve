// The analysis helpers behind the ship-page panels: the exponential moving average, the kink fit (a
// two-line fit to (step, log10 norm)), the stat block, and the small numeric helpers. Extracted (and
// typed) from the view monolith; pure, except the kink rule thresholds, which loadSieves sets.

import { groupLabel, groupOf, layerOnly, topKeys } from './metrics';

// the kink rule is fleet.py's (KINK_MIN_RECORDS, KINK_FIRM), read from /api/sieves when it loads
export let KINK_MIN = 10;
export let KINK_FIRM = 0.25;
export const setKinkRule = (min: number, firm: number): void => { KINK_MIN = min; KINK_FIRM = firm; };

export const ema = (xs: number[], span: number): number[] => {
  const a = 2 / (span + 1);
  let m: number | null = null;
  return xs.map((x) => (m = m == null ? x : a * x + (1 - a) * m));
};

export interface Fit {
  a: number;
  b: number;
  sse: number;
}

export const linfit = (x: number[], y: number[]): Fit => {
  const n = x.length;
  let sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (let i = 0; i < n; i++) { sx += x[i]; sy += y[i]; sxx += x[i] * x[i]; sxy += x[i] * y[i]; }
  const d = n * sxx - sx * sx;
  const b = d ? (n * sxy - sx * sy) / d : 0;
  const a = (sy - b * sx) / n;
  let sse = 0;
  for (let i = 0; i < n; i++) { const r = y[i] - (a + b * x[i]); sse += r * r; }
  return { a, b, sse };
};

export interface Kink {
  step: number;
  before: number;
  after: number;
  kind: string;
  strength: number;
  tentative: boolean;
  L: Fit;
  R: Fit;
  k: number;
  xs: number[];
}

// the kink: a two-line fit to (step, log10 norm); the break is where the layer changes regime
export const kink = (xs: number[], ys: number[]): Kink | null => {
  const n = xs.length;
  if (n < 6) return null;
  const one = linfit(xs, ys);
  let best: { k: number; sse: number; L: Fit; R: Fit } | null = null;
  for (let k = 3; k <= n - 3; k++) {
    const L = linfit(xs.slice(0, k), ys.slice(0, k));
    const R = linfit(xs.slice(k), ys.slice(k));
    const sse = L.sse + R.sse;
    if (!best || sse < best.sse) best = { k, sse, L, R };
  }
  const b = best!;
  const strength = one.sse > 0 ? 1 - b.sse / one.sse : 0;
  const before = b.L.b * 100;
  const after = b.R.b * 100;
  // which way the push went at the break: by the signs of the two slopes
  const kind = Math.abs(after - before) < 0.02 ? 'bent'
    : before < 0 && after >= 0 ? 'turned up' : before > 0 && after <= 0 ? 'turned down'
    : before < 0 ? (after > before ? 'flattened' : 'steepened') : (after > before ? 'steepened' : 'eased');
  return { step: xs[b.k], before, after, kind, strength, tentative: n < KINK_MIN || strength < KINK_FIRM, L: b.L, R: b.R, k: b.k, xs };
};

// the fit starts where warmup ends (the learning-rate peak): the ramp before it is the schedule's
// shape, not the layer's, and a hump defeats a two-line fit
export const warmEnd = (m: { lr?: number[][] }): number => {
  if (!m.lr) return 0;
  const [x, v] = m.lr;
  let b = 0;
  v.forEach((lr, i) => { if (lr > v[b]) b = i; });
  return x[b];
};

export const kinksOf = (m: Record<string, number[][]>, prefix: string): Record<string, Kink> => {
  const out: Record<string, Kink> = {};
  const from = warmEnd(m);
  for (const k of topKeys(m, prefix)) {
    const [x, v] = m[k];
    const pts = x.map((s, i) => [s, v[i]] as [number, number]).filter((p) => p[1] > 0 && p[0] >= from);
    const kk = kink(pts.map((p) => p[0]), pts.map((p) => Math.log10(p[1])));
    if (kk) out[k] = kk;
  }
  return out;
};

export const stat = (k: string, v: string, s = ''): string => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;

export const kinkSummary = (m: Record<string, number[][]>, kinks: Record<string, Kink>): [string, string] => {
  const prefix = 'grad_norm/';
  const keys = layerOnly(m, prefix);
  if (!keys.length) return ['no records yet', ''];
  const firm = keys.filter((k) => kinks[k] && !kinks[k].tentative);
  const tent = keys.filter((k) => kinks[k] && kinks[k].tentative);
  if (!firm.length) return [tent.length ? `${tent.length} tentative, none firm` : 'none yet', `${keys.length} layers, ${m[keys[0]][0].length} records`];
  const say = (k: string): string => `${groupLabel(groupOf(k, prefix)).replace('layer ', 'L')} ${kinks[k].kind} @ ${kinks[k].step}`;
  const earliest = firm.slice().sort((a, b) => kinks[a].step - kinks[b].step)[0];
  return [firm.map(say).join(' · '), `${firm.length} firm, ${tent.length} tentative; earliest ${say(earliest)}`];
};

export const interp = (xs: number[], ys: number[], x: number): number | null => {
  if (!xs.length || x < xs[0] || x > xs[xs.length - 1]) return null;
  for (let i = 1; i < xs.length; i++) if (xs[i] >= x) { const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1] || 1); return ys[i - 1] + t * (ys[i] - ys[i - 1]); }
  return ys[ys.length - 1];
};

export const meanOf = (a: number[]): number | null => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
export const rangeOf = (a: number[]): number | null => (a.length > 1 ? Math.max(...a) - Math.min(...a) : null);

// Least-squares polynomial fit: coefficients highest power first (numpy.polyfit's order), solved by the normal
// equations and Gauss–Jordan. And where that polynomial first reaches `y` in log10-parameter space.
export const polyfit = (xs: number[], ys: number[], deg: number): number[] => {
  const n = deg + 1;
  const A: number[][] = Array.from({ length: n }, () => Array(n + 1).fill(0));
  xs.forEach((x, i) => {
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) A[r][c] += x ** (2 * deg - r - c);
      A[r][n] += ys[i] * x ** (deg - r);
    }
  });
  for (let i = 0; i < n; i++) {
    let m = i;
    for (let r = i + 1; r < n; r++) if (Math.abs(A[r][i]) > Math.abs(A[m][i])) m = r;
    [A[i], A[m]] = [A[m], A[i]];
    for (let r = 0; r < n; r++) {
      if (r !== i) {
        const f = A[r][i] / A[i][i];
        for (let c = i; c <= n; c++) A[r][c] -= f * A[i][c];
      }
    }
  }
  return A.map((row, i) => row[n] / row[i]);
};

export const polyval = (co: number[], x: number): number => co.reduce((a, c) => a * x + c, 0);

export const fitReachAt = (co: number[] | null, y: number, from: number): number | null => {
  if (!co) return null;
  for (let x = from; x <= 14; x += 0.005) if (polyval(co, x) >= y) return 10 ** x;
  return null;
};
