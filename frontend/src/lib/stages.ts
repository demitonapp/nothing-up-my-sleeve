// ---- Stages: a run's training read in named stages, in order, under one learning-rate schedule
// (spec data.stages; the ledger's 'stages' artifact: [{index, name, recipe, passes, first_step,
// last_step, tokens}]; UI.md, "Stages"). A run without stages is one stage, reading, and draws none.
// Every chart whose x-axis is the training step gets the stages as bands, labelled by name; a chart
// of several runs gets them only when those runs share the same stages, so a band never misleads.
import { get } from './format';
import { applyBands } from './charts';

interface Stage {
  name: string;
  first_step: number;
  last_step: number;
}

const cache = new Map<string, { at: number; stages: Stage[] }>(); // run id or name -> { at, stages }
export async function stagesFor(ids: string[]): Promise<Record<string, Stage[]>> {
  const want = ids.filter((id) => !(cache.has(id) && Date.now() - cache.get(id)!.at < 30000));
  if (want.length) {
    try {
      const d = await get('/api/stages?runs=' + encodeURIComponent(want.join(',')));
      for (const id of want) cache.set(id, { at: Date.now(), stages: d[id] || [] });
    } catch { /* stages are an overlay; without them the charts stand as they are */ }
  }
  return Object.fromEntries(ids.map((id) => [id, cache.get(id)?.stages ?? []]));
}
// the stages several runs share, or null when they differ or none has any
export function common(byRun: Record<string, Stage[]>): Stage[] | null {
  const lists = Object.values(byRun).filter((s): s is Stage[] => !!s && s.length > 0);
  if (!lists.length) return null;
  const key = (s: Stage[]): string => JSON.stringify(s.map((x) => [x.name, x.first_step, x.last_step]));
  return lists.every((s) => key(s) === key(lists[0])) ? lists[0] : null;
}
// lay the stages over every step chart inside a part of the page
export function band(scope: string | Element, stages: Stage[] | null): void {
  applyBands(scope, stages);
}
// the stage a step falls in
export const stageAt = (stages: Stage[] | null | undefined, step: number): Stage | null =>
  (stages || []).find((s) => step >= s.first_step && step <= s.last_step) || null;
