// ECharts (10 November): the dashboard's charts are ECharts options now. The modules are imported only
// when a chart is in view, and only the pieces used are registered; extend the lists when a chart needs
// a new type.
let lib: Promise<any> | null = null;

export const loadEcharts = (): Promise<any> => (lib ??= Promise.all([
  import('echarts/core'),
  import('echarts/charts'),
  import('echarts/components'),
  import('echarts/renderers'),
]).then(([core, charts, components, renderers]) => {
  core.use([
    charts.LineChart, charts.BarChart, charts.ScatterChart, charts.HeatmapChart,
    components.GridComponent, components.LegendComponent, components.TooltipComponent,
    components.MarkLineComponent, components.MarkAreaComponent, components.VisualMapComponent,
    components.TitleComponent, components.DataZoomComponent, components.GraphicComponent,
    renderers.CanvasRenderer,
  ]);
  return core;
}));

/** Resolve when the element is in (or near) the viewport: charts load when they are read. */
export const inView = (el: HTMLElement): Promise<void> => new Promise((resolve) => {
  if (typeof IntersectionObserver === 'undefined') return resolve();
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { io.disconnect(); resolve(); }
  }, { rootMargin: '320px' });
  io.observe(el);
});

const charts = new WeakMap<HTMLElement, any>();

export const chartOf = (el: HTMLElement): any => charts.get(el);

/** Draw (or redraw) an ECharts option in a div; the instance is reused and resized with the element. */
export async function echartsPlot(el: HTMLElement, option: Record<string, unknown>): Promise<void> {
  await inView(el);
  const echarts = await loadEcharts();
  let c = charts.get(el);
  if (c && !el.querySelector('canvas')) { try { c.dispose(); } catch { /* already gone */ } charts.delete(el); c = undefined; }
  if (!c) {
    c = echarts.init(el, null, { renderer: 'canvas' });
    charts.set(el, c);
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => c.resize()).observe(el);
  }
  c.setOption(option, { notMerge: true });
}
