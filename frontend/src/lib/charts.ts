import { emptyCls } from './ui';
import { echartsPlot, loadEcharts, chartOf } from './echarts';

// The dashboard's chart spec, kept close to the Plotly figures it grew from (10 November: ECharts is
// the engine now). A figure is `data` (traces) plus `layout`; the converter below maps the subset this
// dashboard uses — scatter/line, bar, heatmap, axes, shapes and annotations — to an ECharts option.
// The modules load on demand and only when a chart is in view (see lib/echarts).

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

const titleOf = (t: unknown): string => (typeof t === 'string' ? t : ((t as any)?.text ?? ''));
const dashOf = (d: string | undefined): 'solid' | 'dotted' | 'dashed' => (d === 'dot' ? 'dotted' : d === 'dash' ? 'dashed' : 'solid');
const tick = (f: string | undefined): ((v: number) => string) | undefined => {
  if (!f) return undefined;
  const pct = /^\.(\d)%$/.exec(f);
  if (pct) return (v) => `${(Number(v) * 100).toFixed(+pct[1])}%`;
  const dec = /^\.(\d)f$/.exec(f);
  if (dec) return (v) => Number(v).toFixed(+dec[1]);
  return undefined;
};

const axisOf = (a: any, isX: boolean, categories?: string[]): Record<string, unknown> => {
  const type = a?.type === 'log' ? 'log' : isX && categories ? 'category' : 'value';
  const numeric = type === 'value' || type === 'log';
  return {
    type,
    data: isX && categories ? categories : undefined,
    name: titleOf(a?.title),
    nameLocation: 'middle',
    nameGap: isX ? 26 : 42,
    min: a?.range ? a.range[0] : undefined,
    max: a?.range ? a.range[1] : undefined,
    axisLabel: { color: C.muted, fontSize: a?.tickfont?.size ?? 10, rotate: a?.tickangle ?? 0,
      formatter: tick(a?.tickformat) ?? (numeric ? (v: number) => (Math.abs(v) >= 1000 ? String(Math.round(v)) : Number(v).toFixed(Math.abs(v) < 1 ? 3 : 2)) : undefined) },
    splitLine: { show: a?.showgrid !== false, lineStyle: { color: a?.gridcolor || C.line } },
    axisLine: { show: true, lineStyle: { color: C.line } },
    axisTick: { show: false },
  };
};

/** A Plotly-shaped figure as an ECharts option. */
export function toOption(data: any[], lay: any = {}): Record<string, unknown> {
  const traces = data || [];
  const catX = traces.some((t) => Array.isArray(t.x) && t.x.some((x: any) => typeof x === 'string'));
  const horiz = traces.some((t) => t.type === 'bar' && t.orientation === 'h');
  const ycats = horiz ? [...new Set(traces.flatMap((t) => (Array.isArray(t.y) ? t.y : [])))] as string[] : undefined;
  const categories = catX
    ? [...new Set(traces.flatMap((t) => (Array.isArray(t.x) ? t.x.filter((x: any) => typeof x === 'string') : [])))] as string[]
    : undefined;
  const marks: any[] = [];
  const areas: any[] = [];
  for (const s of lay.shapes || []) {
    if (s.type === 'line' && s.y0 != null && s.y1 != null && s.y0 === s.y1) {
      marks.push({ yAxis: s.y0, lineStyle: { color: s.line?.color || C.line, type: dashOf(s.line?.dash), width: s.line?.width ?? 1 }, label: { show: false } });
    } else if (s.type === 'rect' && s.x0 != null && s.x1 != null) {
      areas.push([{ xAxis: s.x0 }, { xAxis: s.x1 }]);
    }
  }
  for (const a of lay.annotations || []) {
    if (a.y == null || a.text == null || a.yref === 'paper') continue;
    marks.push({
      yAxis: a.y, lineStyle: { opacity: 0, width: 0 },
      label: { show: true, formatter: String(a.text), position: 'insideEndTop', color: a.font?.color || C.muted, fontSize: a.font?.size ?? 10 },
    });
  }

  const series = traces.map((t, i) => {
    const color = t.line?.color || (typeof t.marker?.color === 'string' ? t.marker.color : PALETTE[i % PALETTE.length]);
    const base: any = { name: t.name || `series ${i + 1}`, yAxisIndex: t.yaxis === 'y2' ? 1 : 0, itemStyle: { color } };
    if (t.type === 'heatmap') {
      const xs = (t.x || []).map(String), ys = (t.y || []).map(String);
      const z: number[][] = t.z || [];
      const points = z.flatMap((row, yi) => row.map((v, xi) => [xi, yi, v]));
      return {
        ...base, type: 'heatmap', data: points,
        xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: undefined },
        markLine: i === 0 ? { silent: true, symbol: 'none', data: marks } : undefined,
        markArea: i === 0 && areas.length ? { silent: true, itemStyle: { color: 'rgba(120,120,120,.10)' }, data: areas } : undefined,
        _heat: { xs, ys },
      };
    }
    if (t.type === 'bar') {
      const raw = t.orientation === 'h' ? (t.x || []) : catX ? t.y : (t.y || []).map((v: any, j: number) => [t.x?.[j], v]);
      const colors = Array.isArray(t.marker?.color) ? t.marker.color : null;
      const texts = Array.isArray(t.text) ? t.text : null;
      const points = raw.map((v: any, j: number) => {
        if (!colors && !texts) return v;
        return { value: v, ...(colors ? { itemStyle: { color: colors[j] } } : {}), ...(texts ? { name: String(texts[j]) } : {}) };
      });
      return {
        ...base, type: 'bar', data: points, barMaxWidth: 22,
        label: texts ? { show: true, position: t.orientation === 'h' ? 'right' : 'top', formatter: '{b}', color: C.muted, fontSize: 9 } : undefined,
        itemStyle: { color: colors ? undefined : color },
        ...(t.orientation === 'h' ? { xAxisIndex: 0, yAxisIndex: 0 } : {}),
        markLine: i === 0 ? { silent: true, symbol: 'none', data: marks } : undefined,
        markArea: i === 0 && areas.length ? { silent: true, itemStyle: { color: 'rgba(120,120,120,.10)' }, data: areas } : undefined,
      };
    }
    const mode = t.mode || 'markers';
    const isLine = mode.includes('lines');
    const points = (t.y || []).map((y: any, j: number) => {
      const v = catX ? y : [t.x?.[j], y];
      return t.text?.[j] != null ? { value: v, name: String(t.text[j]) } : v;
    });
    return {
      ...base, type: isLine ? 'line' : 'scatter', data: points,
      showSymbol: mode.includes('markers'),
      symbolSize: t.marker?.size ?? 4,
      step: t.line?.shape === 'hv' ? 'end' : undefined,
      lineStyle: { color, width: t.line?.width ?? 1.5, type: dashOf(t.line?.dash) },
      itemStyle: { color, opacity: t.marker?.opacity ?? 1 },
      areaStyle: t.fill ? { opacity: 0.15 } : undefined,
      connectNulls: false,
      markLine: i === 0 ? { silent: true, symbol: 'none', data: marks } : undefined,
      markArea: i === 0 && areas.length ? { silent: true, itemStyle: { color: 'rgba(120,120,120,.10)' }, data: areas } : undefined,
    };
  });

  const withLine = traces.some((t) => t.type !== 'bar' && t.type !== 'heatmap' && (t.mode || '').includes('lines'));
  const heat = series.find((s: any) => s._heat);
  const heatZ = heat ? (traces.find((t) => t.type === 'heatmap')?.z || []).flat() : [];
  const y2 = lay.yaxis2 && Object.keys(lay.yaxis2).length
    ? { ...axisOf(lay.yaxis2, false), position: 'right', splitLine: { show: false } } : null;
  const hx = series.find((s: any) => s._heat)?._heat;
  const xa = axisOf(lay.xaxis, true, catX ? categories : undefined);
  const ya = axisOf(lay.yaxis, false);
  if (horiz) { xa.type = 'value'; xa.data = undefined; ya.type = 'category'; ya.data = ycats as any; ya.axisLabel = { ...(ya.axisLabel as object), formatter: undefined }; }
  if (hx) { xa.type = 'category'; xa.data = hx.xs as any; ya.type = 'category'; ya.data = hx.ys as any; ya.axisLabel = { ...(ya.axisLabel as object), formatter: undefined }; }
  const margin = lay.margin || {};
  return {
    animation: false,
    color: series.map((s: any) => s.itemStyle?.color).filter(Boolean),
    grid: { left: margin.l ?? 50, right: margin.r ?? 20, top: margin.t ?? 24, bottom: margin.b ?? 38, containLabel: false },
    legend: { show: lay.showlegend !== false && series.length <= 40, type: 'scroll', top: 0, left: 0, right: 0,
      textStyle: { color: C.muted, fontSize: lay.legend?.font?.size ?? 10 }, data: series.map((s: any) => s.name) },
    tooltip: {
      trigger: withLine || traces.some((t) => t.type === 'bar') ? 'axis' : 'item',
      backgroundColor: 'rgba(18,18,18,.94)', borderColor: C.line, textStyle: { color: C.text, fontSize: 11 },
      formatter: (p: any) => {
        const a = Array.isArray(p) ? p : [p];
        const head = a[0]?.axisValueLabel ?? a[0]?.name ?? '';
        return [head, ...a.map((x: any) => {
          const name = x.data?.name ?? x.name;
          const v = typeof x.value === 'number' ? x.value : (Array.isArray(x.value) ? (x.seriesType === 'heatmap' ? x.value[2] : x.value[1]) : x.value);
          const label = name && name !== x.seriesName ? ` · ${name}` : '';
          return `${x.marker || ''}${x.seriesName}${label}: <b>${v}</b>`;
        })].join('<br>');
      },
    },
    xAxis: xa,
    yAxis: y2 ? [ya, y2] : ya,
    visualMap: heat && heatZ.length ? { show: false, min: Math.min(...heatZ), max: Math.max(...heatZ), inRange: { color: [C.track, C.blue, C.accent] } } : undefined,
    graphic: (lay.annotations || []).filter((a: any) => (a.y == null || a.yref === 'paper') && a.text != null).map((a: any) => ({
      type: 'text', left: `${(((a.x ?? 1) as number) * 100)}%`, top: `${((1 - ((a.y ?? 0) as number)) * 100)}%`,
      style: { text: String(a.text), fill: a.font?.color || C.muted, fontSize: a.font?.size ?? 10 }, silent: true,
    })),
    series: series.map((s: any) => { if (s._heat) { delete s._heat; } return s; }),
  };
}

export const empty = (id: string, msg = 'no data yet'): void => {
  const el = document.getElementById(id);
  if (!el) return;
  const c = chartOf(el);
  if (c) c.clear();
  el.innerHTML = `<div class="${emptyCls()}">${msg}</div>`;
};

const draw = (el: HTMLElement, data: unknown, lay: Record<string, unknown>): void => {
  if (lay.height) el.style.height = `${lay.height}px`;
  void echartsPlot(el, toOption(data as any[], lay)).catch((e) => console.error('chart failed', el.id, e));
};
export const plotEl = (el: HTMLElement | null, data: unknown, lay: Record<string, unknown>): void => { if (el) draw(el, data, lay); };
export const plot = (id: string, data: unknown, lay: Record<string, unknown>): void => { plotEl(document.getElementById(id), data, lay); };

/** The stages as bands over every step chart in a scope (lib/stages): ECharts markAreas on the first series. */
export const applyBands = (scope: string | Element, stages: any[] | null): void => {
  const root = typeof scope === 'string' ? document.querySelector(scope) : scope;
  if (!root) return;
  void (async () => {
    const echarts = await loadEcharts();
    root.querySelectorAll<HTMLElement>('.chart').forEach((el) => {
      let tries = 0;
      const draw = (): void => {
        const c = echarts.getInstanceByDom(el);
        if (!c) { if (tries++ < 25) setTimeout(draw, 200); return; }
        const opt = c.getOption();
        const xn = String(opt?.xAxis?.[0]?.name || '');
        if (!/step/.test(xn)) return;
        const data = (stages || []).map((s: any) => [{ xAxis: s.first_step, name: s.name }, { xAxis: s.last_step }]);
        c.setOption({ series: (opt.series || []).map((_: any, i: number) => (i === 0
          ? { markArea: { silent: true, itemStyle: { color: 'rgba(120,120,120,.08)' }, label: { show: false }, data } }
          : {})) });
      };
      draw();
    });
  })();
};
