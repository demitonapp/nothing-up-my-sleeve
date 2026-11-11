// The server tab's chart (/settings/server): the machine's GPU and memory beside this server's own CPU and
// memory, sampled every twenty seconds by thorp.dash.perf (data/dash/perf.jsonl) and read back as one point
// per bucket for the last hour, day or week. ECharts is imported inside the effect: the page is
// server-rendered, and nothing that touches `document` may be imported at module load (UI.md, "Navigation"
// and the discoveries island's rule).

import { useEffect, useRef } from 'react';
import { useApi } from '@/lib/useApi';
import { cardCls, emptyCls, toggleCls } from '@/lib/ui';

export type PerfRange = '1h' | '24h' | '7d';

interface Point { t: number; cpu: number | null; rss: number | null; gcpu: number | null; mem: number | null }
interface Perf {
  error?: string; range: string; step: number; from: number; to: number;
  points: Point[];
  now: (Point & { gmem?: number | null; gpu_cores?: number | null }) | null;
  first: number | null;
  stats: Record<string, number | null>;
  mem_total: number | null;
  gpu_cores: number | null;
  kept_days: number; step_sampled: number; pid: number;
}

const RANGES: { key: PerfRange; label: string; about: string }[] = [
  { key: '1h', label: 'the last hour', about: 'a minute a point' },
  { key: '24h', label: 'the last day', about: 'five minutes a point' },
  { key: '7d', label: 'the last week', about: 'half an hour a point' },
];

const mb = (v: number | null | undefined): string => (v == null ? '–' : `${Math.round(v / 2 ** 20).toLocaleString()} MB`);
const gb = (v: number | null | undefined): string => (v == null ? '–' : `${(v / 2 ** 30).toFixed(v / 2 ** 30 >= 10 ? 1 : 2)} GB`);
const pc = (v: number | null | undefined): string => (v == null ? '–' : `${Number(v).toFixed(Number(v) < 10 ? 1 : 0)}%`);
const clock = (ms: number): string => {
  const t = new Date(ms);
  return `${t.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};
const ago = (t: number | null | undefined): string => {
  if (!t) return '–';
  const s = Math.max(0, Math.round(Date.now() / 1000 - t));
  return s < 90 ? `${s} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`;
};
function Stat({ k, v, s }: { k: string; v: string; s?: string }) {
  return <div className="stat"><div className="k">{k}</div><div className="v">{v}</div><div className="s">{s}</div></div>;
}

export default function Performance({ range, onRange }: { range: PerfRange; onRange: (r: PerfRange) => void }) {
  const { data: d, error } = useApi<Perf>(`/api/settings/perf?range=${range}`, 60000);
  const el = useRef<HTMLDivElement>(null);
  const totalGb = d?.mem_total ? d.mem_total / 2 ** 30 : null;

  useEffect(() => {
    if (!d || d.error || d.range !== range || !d.stats.count || !el.current) return;
    const node = el.current;
    let live = true;
    void (async () => {
      const { echartsPlot } = await import('@/lib/echarts');
      if (!live) return;
      const tok = (n: string): string => getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim();
      const C = { text: tok('text'), muted: tok('muted'), line: tok('line'), accent: tok('accent'), blue: tok('blue'), good: tok('good') };
      const gbOf = (v: number | null): number | null => (v == null ? null : +(v / 2 ** 30).toFixed(2));
      const total = d.mem_total ? +(d.mem_total / 2 ** 30).toFixed(1) : undefined;
      await echartsPlot(node, {
        animation: false,
        grid: { left: 52, right: 62, top: 40, bottom: 28 },
        legend: { top: 0, left: 0, textStyle: { color: C.muted, fontSize: 11 }, data: ['GPU %', 'CPU % (server)', 'memory in use', 'this server'] },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(18,18,18,.94)', borderColor: C.line, textStyle: { color: C.text, fontSize: 11 },
          axisPointer: { type: 'line', lineStyle: { color: C.muted } },
          // ECharts' own time header is a full ISO stamp; this one reads as the axis does
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params : [params];
            if (!p.length) return '';
            const shares = p.map((x: any) => {
              const v = x.value?.[1];
              const isPct = x.seriesName === 'GPU %' || x.seriesName === 'CPU % (server)';
              const share = v == null ? '–' : isPct ? pc(v) : `${Number(v).toFixed(1)} GB`;
              return `${x.marker} ${x.seriesName}: <b>${share}</b>`;
            });
            return [clock(p[0].value[0]), ...shares].join('<br>');
          },
        },
        xAxis: {
          type: 'time',
          axisLine: { lineStyle: { color: C.line } },
          axisTick: { show: false },
          axisLabel: {
            color: C.muted, fontSize: 10, hideOverlap: true,
            // a clock for the hour and the day, a date and a clock for the week: ECharts' own
            // time labels put the bare day number at midnight, which reads as a time
            formatter: (v: number) => {
              const t = new Date(v);
              const clock = t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              return range === '7d'
                ? `${t.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${clock}`
                : clock;
            },
          },
          splitLine: { show: false },
        },
        yAxis: [
          {
            type: 'value', min: 0,
            axisLabel: { color: C.muted, fontSize: 10, formatter: (v: number) => `${Math.round(v)}%` },
            splitLine: { lineStyle: { color: C.line } },
            axisLine: { show: false }, axisTick: { show: false },
          },
          {
            type: 'value', min: 0, max: total, interval: total ? total / 4 : undefined,
            axisLabel: { color: C.muted, fontSize: 10, formatter: (v: number) => `${v} GB` },
            splitLine: { show: false },
            axisLine: { show: false }, axisTick: { show: false },
          },
        ],
        series: [
          {
            name: 'GPU %', type: 'line', data: d.points.map((p) => [p.t * 1000, p.gcpu]),
            showSymbol: true, symbolSize: 3, symbol: 'circle', connectNulls: false,
            lineStyle: { color: C.accent, width: 1.4 }, itemStyle: { color: C.accent },
            areaStyle: { color: C.accent, opacity: 0.16 },
          },
          {
            name: 'CPU % (server)', type: 'line', data: d.points.map((p) => [p.t * 1000, p.cpu]),
            showSymbol: true, symbolSize: 2.5, symbol: 'circle', connectNulls: false,
            lineStyle: { color: C.good, width: 1.2 }, itemStyle: { color: C.good },
          },
          {
            name: 'memory in use', type: 'line', yAxisIndex: 1,
            data: d.points.map((p) => [p.t * 1000, gbOf(p.mem)]),
            showSymbol: false, connectNulls: false,
            lineStyle: { color: C.blue, width: 1.4 }, itemStyle: { color: C.blue },
            areaStyle: { color: C.blue, opacity: 0.08 },
          },
          {
            name: 'this server', type: 'line', yAxisIndex: 1,
            data: d.points.map((p) => [p.t * 1000, gbOf(p.rss)]),
            showSymbol: false, connectNulls: false,
            lineStyle: { color: C.muted, width: 1, type: 'dashed' }, itemStyle: { color: C.muted },
          },
        ],
      } as Record<string, unknown>);
    })();
    return () => { live = false; };
  }, [d, range]);

  const r = RANGES.find((x) => x.key === range) ?? RANGES[1];
  const empty = Boolean(d) && !d!.stats.count;
  const gpuCores = d?.gpu_cores ?? d?.now?.gpu_cores ?? null;

  return (
    <section className={cardCls(false, 'panel')}>
      <h2>Performance <span className="note">the machine's GPU and memory, and this server's own CPU and memory, sampled every {(d?.step_sampled ?? 20).toFixed(0)} s and kept {(d?.kept_days ?? 8)} days. The GPU's memory is inside the machine's (unified); a break in a line is a time the server was not running</span></h2>
      <div className="mt" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 6 }}>
        {RANGES.map((x) => (
          <button
            key={x.key}
            type="button"
            className={toggleCls()}
            data-state={range === x.key ? 'on' : 'off'}
            aria-pressed={range === x.key}
            title={x.about}
            onClick={() => onRange(x.key)}
          >{x.label}</button>
        ))}
        <span className="s">{r.about}</span>
      </div>
      {error && !d ? <div className={emptyCls()}>the performance could not be read: {error}. A server started before this chart was added has no /api/settings/perf: restart <code>thorp dash</code>.</div>
        : !d ? <div className={emptyCls()}>reading the performance…</div>
        : empty ? <div className={emptyCls()}>no samples yet: the chart begins with the server ({d.step_sampled} s a sample, kept {d.kept_days} days), so {r.label} fills in as it runs.</div>
        : (
          <>
            <div className="strip mt">
              <Stat k="GPU now" v={pc(d.now?.gcpu)} s={`${gpuCores ? `${gpuCores} cores` : 'the machine'}${d.now?.gmem ? ` · ${gb(d.now.gmem)} held` : ''}`} />
              <Stat k="CPU now" v={pc(d.now?.cpu)} s={`this server · peak ${pc(d.stats.cpu_peak)}`} />
              <Stat k="memory in use" v={gb(d.now?.mem)} s={`of ${totalGb ? `${totalGb.toFixed(0)} GB` : 'the machine'} · peak ${gb(d.stats.mem_peak)}`} />
              <Stat k="this server" v={mb(d.now?.rss)} s="resident, the dash process" />
              <Stat k="samples" v={Number(d.stats.count).toLocaleString()} s={`first ${ago(d.first)}`} />
            </div>
            <div ref={el} className="chart mt" role="img" aria-label={`the machine and this server: GPU, CPU and memory, ${r.label}`} />
          </>
        )}
      <p className="note mt">A sample is two things. <b>The machine's</b>: the GPU's utilisation and the memory it holds (IOAccelerator), and the memory in use of the {totalGb ? `${totalGb.toFixed(0)} GB` : 'machine'} (vm_stat: wired, anonymous and compressed, what Activity Monitor calls Memory Used). <b>This server's</b>: its own CPU time and resident memory, the dashed line. A voyage trains in its own process on the GPU, so it moves the machine's lines and leaves the server's gigabyte alone; the samples live in <code>data/dash/perf.jsonl</code> and outlive a restart.</p>
    </section>
  );
}
