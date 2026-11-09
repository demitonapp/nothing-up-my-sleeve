// The panel layer (9 November): the two things every view in this dashboard needs and none of them owned — a boundary
// that turns a thrown drawer into a message in place of the panel, and the one star-chart spec that had been copied
// three times. See ships/plans/ui-audit-2026-11-09.md for why.
import { Plotly, C, layout, cfg } from './charts';

/** Run a drawer, and if it throws, write *why* into the panel it was drawing into.
 *
 * A blank tab reads as "no data" when the truth is a broken drawer; this is the difference. Returns whatever the
 * drawer returned, or undefined when it failed. Use it on every async drawer the router calls.
 */
export function guarded(fn: (...args: any[]) => any, ...args: any[]): any {
  try {
    const r = fn(...args);
    if (r && typeof r.catch === 'function') {
      return r.catch((e: unknown) => boundary(fn.name, e));
    }
    return r;
  } catch (e) {
    boundary(fn.name, e);
  }
}

function boundary(name: string, e: unknown): void {
  const err = e as { message?: string; stack?: string };
  const msg = `${name} failed: ${String(err?.message ?? e)}`;
  console.error(`[panel] ${msg}`, e);
  // tell the harness, not just the console: data/runs/ui-errors.log (9 November)
  try {
    fetch(`/api/client_log?msg=${encodeURIComponent(msg + '\n' + (err?.stack ?? ''))}`);
  } catch { /* offline */ }
  const host = document.getElementById('rung') || document.body;
  if (!host) return;
  const bar = document.createElement('div');
  bar.className = 'fbmsg bad panel-error';
  bar.textContent = msg;
  bar.title = String(err?.stack ?? '');
  host.prepend(bar);
}

interface StarPoint {
  n: number;
  role: string;
  qwen: number | null;
  ours: number | null;
}

/** The star chart, as two lines: the model that chains against this ship, each point as reading ÷ its mark.
 *
 * This spec was copied into `starJourney`, `sizeJourney` and `sopchart` on 9 November with three sets of margins;
 * it lives here once now. `points` are `{n, role, qwen, ours}` from /api/star_points.
 */
export function starChart(
  elOrId: string | HTMLElement,
  points: StarPoint[],
  { label = 'this ship', height = 340, legend = true, ticks = 10 }: { label?: string; height?: number; legend?: boolean; ticks?: number } = {},
): void {
  const el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId;
  if (!el) return;
  const ps = (points || []).filter((p) => p.qwen != null || p.ours != null);
  if (!ps.length) {
    el.innerHTML = '<div class="s">no chart reading yet</div>';
    return;
  }
  el.innerHTML = '';
  Plotly.react(
    el,
    [
      {
        x: ps.map((p) => `${p.n}. ${p.role}`),
        y: ps.map((p) => p.qwen),
        mode: 'lines+markers',
        name: 'Qwen3 4B (chains)',
        line: { color: C.accent, width: 2 },
        marker: { size: 6 },
        hovertemplate: '%{x}<br>Qwen3 4B: %{y:.2f}× the mark<extra></extra>',
      },
      {
        x: ps.map((p) => `${p.n}. ${p.role}`),
        y: ps.map((p) => p.ours),
        mode: 'lines+markers',
        name: label,
        line: { color: C.good || '#5aa07a', width: 2, dash: 'dot' },
        marker: { size: 6 },
        hovertemplate: `%{x}<br>${label}: %{y:.2f}× the mark<extra></extra>`,
      },
    ],
    {
      ...layout({}),
      height,
      margin: { l: 56, r: 16, t: 26, b: 105 },
      xaxis: { tickangle: -35, tickfont: { size: ticks }, gridcolor: C.line },
      yaxis: { title: "reading ÷ the point's mark", gridcolor: C.line },
      // the tick labels are long and rotated: the legend goes above the plot, not into their row
      legend: { orientation: 'h', x: 0, xanchor: 'left', y: 1.02, yanchor: 'bottom', font: { size: 10 } },
      showlegend: legend,
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: C.line, dash: 'dot' } }],
    },
    cfg,
  );
}
