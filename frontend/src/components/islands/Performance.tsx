// The server tab's chart (/settings/server): the dash server's own CPU and memory, sampled every twenty
// seconds by thorp.dash.perf (data/dash/perf.jsonl) and read back as one point per bucket for the last
// hour, day or week. ECharts is imported inside the effect: the page is server-rendered, and nothing that
// touches `document` may be imported at module load (UI.md, "Navigation" and the discoveries island's rule).

import { useEffect, useRef } from 'react';
import { useApi } from '@/lib/useApi';
import { cardCls, emptyCls, toggleCls } from '@/lib/ui';

export type PerfRange = '1h' | '24h' | '7d';

interface Point { t: number; cpu: number | null; rss: number | null }
interface Perf {
  error?: string; range: string; step: number; from: number; to: number;
  points: Point[];
  now: Point | null;
  first: number | null;
  stats: { count: number; cpu_mean: number | null; cpu_peak: number | null; rss_mean: number | null; rss_peak: number | null };
  kept_days: number; step_sampled: number; pid: number;
}

const RANGES: { key: PerfRange; label: string; about: string }[] = [
  { key: '1h', label: 'the last hour', about: 'a minute a point' },
  { key: '24h', label: 'the last day', about: 'five minutes a point' },
  { key: '7d', label: 'the last week', about: 'half an hour a point' },
];

const mb = (v: number | null | undefined): string => (v == null ? '–' : `${Math.round(v / 2 ** 20).toLocaleString()} MB`);
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

  useEffect(() => {
    if (!d || d.error || d.range !== range || !d.stats.count || !el.current) return;
    const node = el.current;
    let live = true;
    void (async () => {
      const { echartsPlot } = await import('@/lib/echarts');
      if (!live) return;
      const tok = (n: string): string => getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim();
      const C = { text: tok('text'), muted: tok('muted'), line: tok('line'), accent: tok('accent'), blue: tok('blue') };
      const peakMb = Math.max(0, ...d.points.map((p) => (p.rss ?? 0) / 2 ** 20));
      // below a gigabyte the right axis reads in MB, above it in GB: 2,210 MB is a size no one thinks in
      const mem = (v: number): string => (peakMb >= 1024
        ? `${(v / 1024).toFixed(v >= 10240 ? 0 : 1)} GB`
        : `${Math.round(v)} MB`);
      await echartsPlot(node, {
        animation: false,
        grid: { left: 52, right: peakMb >= 1024 ? 62 : 66, top: 34, bottom: 28 },
        legend: { top: 0, left: 0, textStyle: { color: C.muted, fontSize: 11 }, data: ['CPU %', 'memory'] },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(18,18,18,.94)', borderColor: C.line, textStyle: { color: C.text, fontSize: 11 },
          axisPointer: { type: 'line', lineStyle: { color: C.muted } },
          // ECharts' own time header is a full ISO stamp; this one reads as the axis does
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params : [params];
            if (!p.length) return '';
            const head = clock(p[0].value[0]);
            return [head, ...p.map((x: any) => `${x.marker} ${x.seriesName}: <b>${x.seriesName === 'CPU %' ? pc(x.value[1]) : mem(x.value[1])}</b>`)].join('<br>');
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
            type: 'value', min: 0,
            axisLabel: { color: C.muted, fontSize: 10, formatter: (v: number) => mem(v) },
            splitLine: { show: false },
            axisLine: { show: false }, axisTick: { show: false },
          },
        ],
        series: [
          {
            name: 'CPU %', type: 'line', data: d.points.map((p) => [p.t * 1000, p.cpu]),
            showSymbol: true, symbolSize: 3, symbol: 'circle', connectNulls: false,
            lineStyle: { color: C.accent, width: 1.4 }, itemStyle: { color: C.accent },
            areaStyle: { color: C.accent, opacity: 0.13 },
            tooltip: { valueFormatter: (v: number | null) => (v == null ? '–' : `${Number(v).toFixed(v < 10 ? 1 : 0)}%`) },
          },
          {
            name: 'memory', type: 'line', yAxisIndex: 1,
            data: d.points.map((p) => [p.t * 1000, p.rss == null ? null : +(p.rss / 2 ** 20).toFixed(0)]),
            showSymbol: true, symbolSize: 3, symbol: 'circle', connectNulls: false,
            lineStyle: { color: C.blue, width: 1.4 }, itemStyle: { color: C.blue },
            tooltip: { valueFormatter: (v: number | null) => (v == null ? '–' : mem(Number(v))) },
          },
        ],
      } as Record<string, unknown>);
    })();
    return () => { live = false; };
  }, [d, range]);

  const r = RANGES.find((x) => x.key === range) ?? RANGES[1];
  const empty = Boolean(d) && !d!.stats.count;

  return (
    <section className={cardCls(false, 'panel')}>
      <h2>Performance <span className="note">the dash server's own CPU and memory, sampled every {(d?.step_sampled ?? 20).toFixed(0)} s and kept {(d?.kept_days ?? 8)} days. A break in the line is a time the server was not running</span></h2>
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
      {error && !d ? <div className={emptyCls()}>the server's performance could not be read: {error}. A server started before this chart was added has no /api/settings/perf: restart <code>thorp dash</code>.</div>
        : !d ? <div className={emptyCls()}>reading the server's performance…</div>
        : empty ? <div className={emptyCls()}>no samples yet: the chart begins with the server ({d.step_sampled} s a sample, kept {d.kept_days} days), so {r.label} fills in as it runs.</div>
        : (
          <>
            <div className="strip mt">
              <Stat k="CPU now" v={pc(d.now?.cpu)} s={ago(d.now?.t)} />
              <Stat k={`CPU, ${r.label}`} v={pc(d.stats.cpu_mean)} s={`peak ${pc(d.stats.cpu_peak)}`} />
              <Stat k="memory now" v={mb(d.now?.rss)} s="resident, this process" />
              <Stat k={`memory, ${r.label}`} v={mb(d.stats.rss_mean)} s={`peak ${mb(d.stats.rss_peak)}`} />
              <Stat k="samples" v={d.stats.count.toLocaleString()} s={`first ${ago(d.first)}`} />
            </div>
            <div ref={el} className="chart mt" role="img" aria-label={`the dash server: CPU and memory, ${r.label}`} />
          </>
        )}
      <p className="note mt">A sample is this process alone (pid {d?.pid ?? '–'}): a voyage trains in its own process, so this is what the dashboard costs, not what it is watching. CPU is the process's own time over the interval as a share of one core, so a page that many threads serve at once can read above 100%. The samples live in <code>data/dash/perf.jsonl</code> and outlive a restart.</p>
    </section>
  );
}
