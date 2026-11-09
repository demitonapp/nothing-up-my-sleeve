// Metric keys and their grouping: `<prefix>/layer_3`, `<prefix>/layer_3/attn`, `<prefix>/tok`, `<prefix>/pos`.
// Extracted (and typed) from the view monolith; every renderer that groups metric series by layer uses these.

export const groupOf = (k: string, prefix: string): string => k.slice(prefix.length);
export const groupOrder = (g: string): number =>
  g === 'tok' ? -2 : g === 'pos' ? -1 : +(g.split('/')[0].split('_').pop() ?? '0');
export const groupLabel = (g: string): string =>
  g.startsWith('layer_') ? 'layer ' + (g.split('/')[0].split('_').pop() ?? '') : g === 'tok' ? 'token emb' : g === 'pos' ? 'position emb' : g;
export const topKeys = (m: Record<string, unknown>, prefix: string): string[] =>
  Object.keys(m).filter((k) => k.startsWith(prefix) && !groupOf(k, prefix).includes('/')).sort((a, b) => groupOrder(groupOf(a, prefix)) - groupOrder(groupOf(b, prefix)));
export const layerOnly = (m: Record<string, unknown>, prefix: string): string[] =>
  topKeys(m, prefix).filter((k) => groupOf(k, prefix).startsWith('layer_'));

// Two reads on a [steps, values] series (UI.md "Sieves"): the first step a value reaches a threshold, and the
// value at one step. Both return null when the series or the reading is absent.
export const firstReach = (m: Record<string, number[][]>, metric: string | null | undefined, thr: number): number | null => {
  const sr = metric ? m[metric] : null;
  if (!sr) return null;
  const i = sr[1].findIndex((v) => v >= thr);
  return i < 0 ? null : sr[0][i];
};

export const valueAt = (m: Record<string, number[][]>, metric: string | null | undefined, step: number): number | null => {
  const sr = metric ? m[metric] : null;
  if (!sr) return null;
  const i = sr[0].indexOf(step);
  return i < 0 ? null : sr[1][i];
};
