// small formatters shared by every panel
export const fmt = (v: number | null | undefined, d = 3): string =>
  v == null || Number.isNaN(v) ? '–' : Number(v).toFixed(d);
export const big = (v: number | null | undefined): string =>
  v == null ? '–' : v >= 1e9 ? (v / 1e9).toFixed(2) + 'B' : v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : String(Math.round(v));
export const fmtBytes = (v: number | null | undefined): string =>
  !v ? '–' : v >= 1e9 ? (v / 1e9).toFixed(2) + ' GB' : v >= 1e6 ? (v / 1e6).toFixed(1) + ' MB' : (v / 1e3).toFixed(0) + ' KB';
const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;' };
export const esc = (s: unknown): string => String(s).replace(/[&<>]/g, (c) => ESC[c]);
// A failed request throws instead of returning the error JSON as the panel's data: otherwise a 500
// reads as "no voyage of this size", no data, and the viewer is told something false (10 November).
// A 200 body that carries `error` (the fitouts, the cleaning audit: still computing) is left to the panel.
export const get = async <T = any>(u: string): Promise<T> => {
  const res = await fetch(u);
  const d = (await res.json().catch(() => null)) as any;
  if (!res.ok) throw new Error((d && d.error) || `${res.status} ${res.statusText}`);
  return d as T;
};
export const postJSON = async <T = any>(url: string, body: unknown): Promise<T> => {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const d = await res.json().catch(() => ({}));
  if (!res.ok || d.error) throw new Error(d.error || res.statusText);
  return d;
};
export const log10 = (v: number): number | null => (v > 0 ? Math.log10(v) : null);
export const mean = (a: number[]): number | null => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
// a signed value with its sign always shown: "+0.42", "−0.10" (as the leaderboard and the chains read it)
export const signed = (v: number | null | undefined, d = 2): string => (v == null ? '–' : `${v >= 0 ? '+' : ''}${fmt(v, d)}`);
// a model size in parameters: "9m", "1.2B", "350M", "0.6B"
export const fmtParams = (n: number | null | undefined): string =>
  n == null ? '–' : n >= 1e12 ? `${(n / 1e12).toFixed(n >= 1e13 ? 0 : 1)}T`
    : n >= 1e9 ? `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B`
    : n >= 1e6 ? `${Math.round(n / 1e6)}M`
    : `${Math.round(n / 1e3)}k`;
// a model's short name from its Hugging Face path: "Qwen/Qwen3-0.6B" -> "Qwen3 0.6B"
export const shortModel = (m: string | null | undefined): string =>
  (m || '').split('/').pop()!.replace(/-(\d+)bit$/, ' $1-bit').replace('Qwen3-', 'Qwen3 ');
// a book's year as a fifty-year period label: 1891 -> "1850–1899", before 1500 -> "before 1500"
export const periodOf = (y: number | null | undefined): string =>
  y == null ? 'undated' : y < 1500 ? 'before 1500' : `${Math.floor(y / 50) * 50}–${Math.floor(y / 50) * 50 + 49}`;
