// ---- Stages: a run's training read in named stages, in order, under one learning-rate schedule
// (spec data.stages; the ledger's 'stages' artifact: [{index, name, recipe, passes, first_step,
// last_step, tokens}]; UI.md, "Stages"). A run without stages is one stage, reading, and draws none.
// Every chart whose x-axis is the training step gets the stages as bands, labelled by name; a chart
// of several runs gets them only when those runs share the same stages, so a band never misleads.
import { get, esc } from './format.js';
import { Plotly, tok } from './charts.js';

const cache = new Map();  // run id or name -> { at, stages }
export async function stagesFor(ids) {
  const want = ids.filter(id => id && !(cache.has(id) && Date.now() - cache.get(id).at < 30000));
  if (want.length) {
    try {
      const d = await get('/api/stages?runs=' + encodeURIComponent(want.join(',')));
      for (const id of want) cache.set(id, { at: Date.now(), stages: d[id] || [] });
    } catch (e) { /* stages are an overlay; without them the charts stand as they are */ }
  }
  return Object.fromEntries(ids.map(id => [id, (cache.get(id) || {}).stages || []]));
}
// the stages several runs share, or null when they differ or none has any
export function common(byRun) {
  const lists = Object.values(byRun).filter(s => s && s.length);
  if (!lists.length) return null;
  const key = s => JSON.stringify(s.map(x => [x.name, x.first_step, x.last_step]));
  return lists.every(s => key(s) === key(lists[0])) ? lists[0] : null;
}
const isStepChart = el => {
  const t = el.layout && el.layout.xaxis && el.layout.xaxis.title;
  return /step/.test(typeof t === 'string' ? t : (t && t.text) || '');
};
// lay the stages over every step chart inside a part of the page
export function band(scope, stages) {
  const root = typeof scope === 'string' ? document.querySelector(scope) : scope;
  if (!root) return;
  root.querySelectorAll('.js-plotly-plot').forEach(el => {
    if (!el.layout || !isStepChart(el)) return;
    const shapes = (el.layout.shapes || []).filter(s => s.name !== 'stage');
    const notes = (el.layout.annotations || []).filter(a => a.name !== 'stage');
    if (stages && stages.length) {
      stages.forEach((s, i) => {
        shapes.push({ name: 'stage', type: 'rect', xref: 'x', yref: 'paper', x0: s.first_step, x1: s.last_step, y0: 0, y1: 1, layer: 'below',
          line: { width: 0 }, fillcolor: i % 2 ? 'rgba(227,179,65,0.06)' : 'rgba(88,166,255,0.05)' });
        if (i) shapes.push({ name: 'stage', type: 'line', xref: 'x', yref: 'paper', x0: s.first_step, x1: s.first_step, y0: 0, y1: 1, line: { color: tok('muted'), width: 1, dash: 'dot' } });
        notes.push({ name: 'stage', xref: 'x', yref: 'paper', x: (s.first_step + s.last_step) / 2, y: 1, yanchor: 'bottom', showarrow: false,
          text: esc(s.name), font: { size: 10, color: tok('muted') } });
      });
    }
    Plotly.relayout(el, { shapes, annotations: notes });
  });
}
// the stage a step falls in
export const stageAt = (stages, step) => (stages || []).find(s => step >= s.first_step && step <= s.last_step) || null;
