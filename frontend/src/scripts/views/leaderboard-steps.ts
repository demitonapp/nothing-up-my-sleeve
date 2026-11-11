// The extra small board (UI.md "Leaderboard", 11 November): under 1B nothing chains, so the board is
// read by the steps to chaining (thorp/steps.py), not ranked by a chaining lift that is noise here.
// Typed renderers, as leaderboard-main.ts: the steps table, each ship beside the outside model ten
// times its size, the readings against size, and ARC-AGI-2 for the band with prompted and trained
// readings kept apart.

import { esc, fmtParams, signed } from '../../lib/format';
import { emptyCls, pillCls } from '../../lib/ui';
import { shipHash } from '../router';
import { makerLink, minicards } from './leaderboard';
import { bandOf, sizeOf, type SizeBand } from './bands';

type Html = { head: string; body: string; lead: string };

const inBand = (rows: any[], band: SizeBand): any[] => (rows || []).filter((r) => bandOf(sizeOf(r)) === band);
const isOurs = (r: any): boolean => r.kind === 'thorp';

const nameCell = (r: any): string => isOurs(r)
  ? `<a href="/leaderboard/thorp/${encodeURIComponent(r.ship_key)}"><b>${esc(r.name)}</b></a><div class="s">${r.ship_key ? `<a href="${shipHash(r.ship_key)}">${esc(r.ship || '')}</a>` : esc(r.ship || '')}${r.sailings ? ` · ${r.sailings} sailing${r.sailings === 1 ? '' : 's'}` : ''}</div>`
  : `<a href="/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a><div class="s">${makerLink(r.model || r.name)}</div>`;

/** A step's reading: green with a tick where the step is held, plain where it is not, and "not read"
 *  where it was never measured (a step not read is not a step failed). */
const stepCell = (held: boolean | null | undefined, text: string, title: string): string =>
  held == null ? `<span class="s" title="${esc(title)}">not read</span>`
    : `<span class="tc${held ? ' lit' : ''}" title="${esc(title)}">${text}${held ? ' ✓' : ''}</span>`;

/** The chaining tests a row performed, by name, from the payload's own per-test readings. */
const performedOf = (lb: any, r: any): string[] => {
  const tests = isOurs(r)
    ? ((lb.ships || []).find((x: any) => x.ship_key === r.ship_key) || {}).tests
    : ((lb.reference || []).find((x: any) => x.model === r.model) || {}).tests;
  return Object.values(tests || {}).filter((t: any) => t.performed).map((t: any) => String(t.name));
};

/** The steps table: every model of the band, ranked by the steps it holds. */
export function stepsHtml(lb: any, band: SizeBand): Html {
  const st = lb.steps || {}, order: any[] = st.order || [], nTests = (lb.tests || []).length || 4;
  const rows = inBand(lb.table, band).filter((r) => r.steps).sort((a, b) => a.step_rank - b.step_rank || (b.params ?? 0) - (a.params ?? 0));
  const about = (k: string): string => (order.find((o) => o.key === k) || {}).about || '';
  const head = `<tr><th>#</th><th>model</th><th>parameters</th><th title="how many of the four steps the model holds; a model chains only with the chaining gain and a chaining test together">steps held</th>
    <th title="${esc(about('cards'))}">the four cards <span class="s">P♣ N♠ M♦ C♥</span></th>
    <th title="${esc(about('one_hop'))}">one hop<div class="s">at ${st.one_hop_mark ?? 0.1}</div></th>
    <th title="${esc(about('gain'))}">chaining gain<div class="s">above ${st.gain_noise ?? 0.05}</div></th>
    <th title="${esc(about('test'))}">chaining tests<div class="s">one of ${nTests}</div></th>
    <th title="the mean lift on the four chaining tests: under 1B it is inside the noise, so it ranks nothing here">chaining lift <span class="s">noise</span></th></tr>`;
  const body = rows.map((r) => {
    const s = r.steps, h = s.held || {}, gain = (r.logic || {}).gain, share = (r.logic || {}).score;
    const rank = r.step_tied ? `<span title="tied: the same steps held and one-hop lifts in the same step of the noise">=${r.step_rank}</span>` : r.step_rank;
    const done = performedOf(lb, r);
    return `<tr class="lb-${isOurs(r) ? 'thorp' : 'outside'}"><td>${rank}</td><td>${nameCell(r)}</td><td>${fmtParams(r.params)}</td>
      <td><b>${s.count}</b> of ${order.length || 4}${s.chains ? ` <span class="${pillCls('good')}" title="through the door: a chaining gain above the noise and a chaining test performed">chains</span>` : ''}</td>
      <td class="cards">${r.cards ? minicards(r.cards) : '<span class="miniset"><span class="s">unreadable</span></span>'} ${stepCell(h.cards, `${r.cards_held ?? '–'} of 4`, about('cards'))}</td>
      <td>${stepCell(h.one_hop, signed(r.one_hop), about('one_hop'))}</td>
      <td>${stepCell(h.gain, `${signed(gain)}${share != null ? ` <i>${Math.round(100 * share)}%</i>` : ''}`, `${about('gain')}${share != null ? `; ${Math.round(100 * share)}% of the deck's items right` : ''}`)}</td>
      <td>${stepCell(h.test, `${r.passed ?? 0} of ${nTests}`, done.length ? `performed: ${done.join(', ')}` : 'none of the four performed')}</td>
      <td class="noise">${r.chaining_lift != null ? signed(r.chaining_lift) : '–'}</td></tr>`;
  }).join('') || `<tr><td colspan="9" class="${emptyCls(true)}">no model of this size has been read yet</td></tr>`;

  const through = rows.filter((r) => r.steps.chains), all = rows.filter((r) => (r.passed ?? 0) >= nTests && r.steps.chains);
  const ours = rows.filter(isOurs), best = ours[0];
  const lead = [
    `<div class="sqp"><b class="${through.length ? 'good' : 's'}">${through.length} of ${rows.length}</b><span>through the door: a chaining gain above the noise and a chaining test performed${through.length ? ` — ${through.map((r) => `${esc(r.name)} (${r.passed} of ${nTests})`).join(', ')}` : ''}</span></div>`,
    `<div class="sqp"><b class="${all.length ? 'good' : 's'}">${all.length}</b><span>perform all ${nTests} chaining tests: ${all.length ? all.map((r) => esc(r.name)).join(', ') : 'no model of this size chains two facts yet'}</span></div>`,
    best ? `<div class="sqp"><b>${best.steps.count} of ${order.length || 4}</b><span>steps held by our furthest ship, ${esc(best.name)}, ranked ${best.step_tied ? '=' : ''}${best.step_rank} of ${rows.length}</span></div>` : '',
  ].join('');
  return { head, body, lead };
}

const VERDICT: Record<string, [string, string]> = { ahead: ['good', 'ahead'], tie: ['s', 'tie'], behind: ['bad', 'behind'] };
const MEASURES: [string, string, (v: any) => string][] = [
  ['steps', 'steps held', (v) => (v == null ? '–' : String(v))],
  ['cards', 'the four cards', (v) => (v == null ? '–' : `${v} of 4`)],
  ['one_hop', 'one hop', (v) => signed(v)],
  ['gain', 'chaining gain', (v) => signed(v)],
];

/** Each of our ships beside the outside model nearest ten times its size: the project's claim, as a
 *  table. A reading inside its noise is a tie; a ship matches when it is behind on nothing read. */
export function tenTimesHtml(lb: any, band: SizeBand): Html {
  const st = lb.steps || {};
  const rows = inBand(lb.ten_times, band);
  const head = `<tr><th>our ship</th><th>parameters</th><th>the outside model ten times its size</th>${MEASURES.map(([, n]) => `<th>${n}<div class="s">ours · theirs</div></th>`).join('')}<th>the result</th></tr>`;
  const measure = (m: any, f: (v: any) => string): string => {
    if (!m || m.verdict == null) return '<span class="s">not read</span>';
    const [cls, word] = VERDICT[m.verdict];
    return `${f(m.ours)} <span class="s">·</span> ${f(m.theirs)}<div class="${cls}">${word}</div>`;
  };
  const body = rows.map((r) => {
    const ref = r.reference;
    if (!ref) return `<tr class="lb-thorp"><td>${nameCell({ ...r, kind: 'thorp' })}</td><td>${fmtParams(r.params)}</td><td colspan="${MEASURES.length + 2}" class="s">no outside model has been read near ten times its size (${fmtParams(10 * r.params)})</td></tr>`;
    const ms = r.measures || {};
    const on = (v: string): string[] => MEASURES.filter(([k]) => (ms[k] || {}).verdict === v).map(([, n]) => n);
    const ahead = on('ahead'), behind = on('behind');
    const result = r.matched
      ? `<span class="${pillCls('good')}">matches</span>${ahead.length ? `<div class="s">ahead on ${esc(ahead.join(', '))}</div>` : '<div class="s">a tie on every measure</div>'}`
      : `<span class="${pillCls('')}">not yet</span><div class="s">behind on ${esc(behind.join(', '))}${ahead.length ? `; ahead on ${esc(ahead.join(', '))}` : ''}</div>`;
    return `<tr class="lb-thorp"><td>${nameCell({ ...r, kind: 'thorp' })}</td><td>${fmtParams(r.params)}</td>
      <td><a href="/leaderboard/competitor/${encodeURIComponent(ref.model)}"><b>${esc(ref.name)}</b></a><div class="s">${fmtParams(ref.params)} · ${Number(ref.times).toFixed(1)}× its size</div></td>
      ${MEASURES.map(([k, , f]) => `<td>${measure(ms[k], f)}</td>`).join('')}<td>${result}</td></tr>`;
  }).join('') || `<tr><td colspan="${MEASURES.length + 4}" class="${emptyCls(true)}">no ship of this size has been read yet</td></tr>`;
  const paired = rows.filter((r) => r.reference), matched = paired.filter((r) => r.matched);
  const hopAhead = paired.filter((r) => (r.measures?.one_hop || {}).verdict === 'ahead').length;
  const lead = `<div class="sqp"><b class="${matched.length ? 'good' : 's'}">${matched.length} of ${paired.length}</b><span>ships match the outside model ten times their size: behind on nothing read${matched.length ? ` — ${matched.map((r) => esc(r.name)).join(', ')}` : ''}</span></div>
    <div class="sqp"><b>${hopAhead} of ${paired.length}</b><span>are ahead of it on one hop, by more than the noise (${st.one_hop_noise ?? 0.05})</span></div>`;
  return { head, body, lead };
}

/** AI2 ARC for one band: the board the extra small class is ranked by (11 November, Justin: "have the
 *  leaderboard for ARC easy and challenge be the primary leaderboard here").
 *
 *  ARC-Easy is the anchor, because that is the split with a gradient under 1B; ARC-Challenge is read
 *  beside it and sits at its 25% floor for everything older than the 2025 small models, which is a
 *  reading too. Ranked by Easy, biggest first; a model whose reading is missing is listed below the
 *  line, never ranked. Both columns are the number of questions the model got right and how many it
 *  had, so a 2,299-question reading can never pass for a 2,376-question one. */
export function arcAi2Html(lb: any, band: SizeBand): Html {
  const spec = lb.arc_ai2 || {};
  const chance = spec.chance ?? 0.25;
  const read = (spec.rows || []).filter((r: any) => r.params && bandOf(sizeOf(r)) === band && r.easy && r.easy.accuracy != null);
  read.sort((a: any, b: any) => b.easy.accuracy - a.easy.accuracy || (b.challenge?.accuracy ?? 0) - (a.challenge?.accuracy ?? 0) || b.params - a.params);
  // a ship read by `thorp eval` is ranked with the rest; one not read yet stands below the line
  const readShips = new Set(read.filter((r: any) => r.kind === 'thorp').map((r: any) => r.ship_key));
  const unread = inBand(lb.table, band).filter((r) => isOurs(r) && r.params && !readShips.has(r.ship_key));
  const pct = (x: number): string => `${(100 * x).toFixed(1)}%`;
  const splitCell = (s: any, primary: boolean): string => {
    if (!s || s.accuracy == null) return '<span class="s">not read</span>';
    const excess = s.accuracy - chance;
    return `<b>${pct(s.accuracy)}</b>${primary ? ` <span class="s">${excess >= 0 ? '+' : ''}${(100 * excess).toFixed(1)} on chance</span>` : ''}
      <div class="s">${s.questions ?? 0} of ${primary ? 2376 : 1172} read${s.skipped ? ` · ${s.skipped} skipped` : ''}${s.pilot ? ' · pilot' : ''}</div>`;
  };
  const body = read.map((r: any, i: number) => `<tr class="lb-${r.kind === 'thorp' ? 'thorp' : 'outside'}">
      <td>${i + 1}</td>
      <td>${r.kind === 'thorp'
        ? `<a href="/leaderboard/thorp/${encodeURIComponent(r.ship_key || '')}"><b>${esc(r.name)}</b></a><div class="s">ours · ${r.sailings ?? 1} sailing${(r.sailings ?? 1) === 1 ? '' : 's'} averaged</div>`
        : `<a href="/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a><div class="s">${makerLink(r.model)}</div>`}</td>
      <td>${fmtParams(r.params)}</td>
      <td>${splitCell(r.easy, true)}</td>
      <td>${splitCell(r.challenge, false)}</td></tr>`).join('')
    + unread.map((r: any) => `<tr class="lb-thorp unread"><td>–</td>
      <td><a href="/leaderboard/thorp/${encodeURIComponent(r.ship_key || '')}"><b>${esc(r.name)}</b></a></td>
      <td>${fmtParams(r.params)}</td>
      <td colspan="2"><span class="s">not read yet: a ship is read by <code>thorp eval</code> with the arc_ai2 evaluator</span></td></tr>`).join('')
    || `<tr><td colspan="5" class="${emptyCls(true)}">no model of this size has been read on AI2 ARC yet</td></tr>`;
  const best = read[0], over = read.filter((r: any) => r.easy.accuracy > chance);
  const lead = `<div class="sqp"><b class="${best ? 'good' : 's'}">${best ? pct(best.easy.accuracy) : '–'}</b><span>${best ? `${esc(best.name)} on ARC-Easy, the best of ${read.length} read at this size` : 'nothing read at this size yet'}</span></div>
    <div class="sqp"><b>${over.length} of ${read.length}</b><span>are above the ${Math.round(100 * chance)}% floor, so the split discriminates across the whole band</span></div>`;
  const head = '<tr><th>#</th><th>model</th><th>parameters</th><th>ARC-Easy <span class="s">the anchor</span></th><th>ARC-Challenge <span class="s">the floor</span></th></tr>';
  return { head, body, lead };
}

/** ARC-AGI-2 for one band. A model prompted cold and a model trained on ARC tasks are two different
 *  contests, so they are two columns and never one number. */
export function arcBandHtml(reasoning: any, band: SizeBand): { head: string; body: string } {
  const head = '<tr><th>model</th><th>prompted cold <span class="s">pass@2</span></th><th>trained on ARC tasks <span class="s">pass@2</span></th><th>the reading</th></tr>';
  const rows = ((reasoning && reasoning.measured) || []).filter((x: any) => bandOf(sizeOf(x)) === band);
  const grid = (x: any): string => x.format_rate == null ? '' : x.format_rate === 0 ? ' · no grid written' : ` · a grid on ${Math.round(100 * x.format_rate)}%`;
  const outside = rows.map((x: any) => `<tr class="lb-outside"><td><b>${esc(x.label)}</b>${x.thinking ? ` <span class="s">thinking ${esc(x.thinking)}</span>` : ''}<div class="s">${esc(x.model)}</div></td>
    <td><b>${Number(x.score).toFixed(1)}</b><div class="s">${x.tasks || 0} tasks${grid(x)}</div></td><td><span class="s">not trained on them</span></td>
    <td class="s">${esc(x.source)}${x.mode ? ` · ${esc(x.mode)}` : ''}${x.thinking_unfinished ? ` · thinking ran out on ${x.thinking_unfinished}` : ''}</td></tr>`).join('');
  const t = reasoning && reasoning.thorp;
  const ours = `<tr class="lb-thorp"><td><b>Nothing up my sleeve</b><div class="s">${esc(t ? (t.ship || t.run || '') : 'no reading yet')}</div></td>
    <td>${t ? `<b>${Number(t.score).toFixed(1)}</b><div class="s">${t.tasks || 0} tasks</div>` : '<span class="s">not yet run</span>'}</td>
    <td><span class="s">not yet run</span></td><td class="s">${t ? esc(t.note || 'our own reading') : ''}${t ? ' · ' : ''}the Kipling ARC arm is the first ship to be trained on the ARC tasks</td></tr>`;
  return { head, body: outside + ours };
}

export const STEP_METRICS: { key: string; name: string; unit: string }[] = [
  { key: 'one_hop', name: 'one hop', unit: 'one-hop lift' },
  { key: 'gain', name: 'chaining gain', unit: 'chaining gain' },
  { key: 'steps', name: 'steps held', unit: 'steps held' },
  { key: 'lift', name: 'chaining lift', unit: 'chaining lift' },
];

/** One reading against size: our ships as one line and the outside models as another, so "the same
 *  at a tenth the size" is a line sitting to the left of the other. */
export async function drawStepsChart(lb: any, band: SizeBand, metric: string): Promise<void> {
  if (!lb || !document.getElementById('lbstepschart')) return;
  // imported here, not at module load: ECharts needs `self`, which the server render does not have
  const { plot, layout, tok } = await import('../../lib/charts');
  const st = lb.steps || {};
  const value = (r: any): number | null => metric === 'one_hop' ? r.one_hop ?? null
    : metric === 'gain' ? (r.logic || {}).gain ?? null
    : metric === 'steps' ? (r.steps || {}).count ?? null
    : r.chaining_lift ?? null;
  const rows = inBand(lb.table, band).filter((r) => r.params && value(r) != null).sort((a, b) => a.params - b.params);
  const line = (rs: any[], name: string, color: string, dash: string) => ({
    x: rs.map((r) => r.params), y: rs.map((r) => Number(value(r)!.toFixed(3))), text: rs.map((r) => `${r.name} · ${fmtParams(r.params)}`),
    mode: 'lines+markers', name, line: { color, width: 1.6, dash }, marker: { color, size: 8 },
  });
  const traces = [
    line(rows.filter(isOurs), 'Nothing up my sleeve', tok('good'), 'solid'),
    line(rows.filter((r) => !isOurs(r)), 'outside models', tok('muted'), 'dash'),
  ];
  const mark: Record<string, [number, string] | undefined> = {
    one_hop: [st.one_hop_mark ?? 0.1, 'the mark'],
    gain: [st.gain_noise ?? 0.05, 'the noise'],
    lift: [lb.threshold ?? 0.1, 'performed'],
  };
  const m = mark[metric];
  const shapes = m ? [{ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: m[0], y1: m[0], line: { color: tok('accent'), width: 1, dash: 'dot' } }] : [];
  const notes = m ? [{ xref: 'paper', yref: 'y', x: 0, y: m[0], showarrow: false, text: `${m[1]} (${m[0]})`, font: { size: 9, color: tok('accent') } }] : [];
  const unit = (STEP_METRICS.find((x) => x.key === metric) || STEP_METRICS[0]).unit;
  plot('lbstepschart', traces, layout({ xaxis: { type: 'log', title: { text: 'parameters' } }, yaxis: { title: { text: unit }, zeroline: false }, shapes, annotations: notes, height: 340 }));
}

/** IFEval for one band (12 November, Justin: "can you also add a card to xsmall for IFEval"): prompt-level
 *  strict accuracy on the 541 prompts, the instruction-level reading beside it. A voyage whose training
 *  turns held the official prompts carries the word rigged in its row, always: its number says it learned
 *  the checks, not that it follows instructions. No outside model has been read on IFEval here yet. */
export function ifevalHtml(lb: any, band: SizeBand): Html {
  const spec = lb.ifeval || {};
  const total = spec.prompts ?? 541;
  const all = (spec.rows || []).filter((r: any) => r.params && bandOf(r.params) === band);
  const honest = all.filter((r: any) => !r.rigged && r.prompts >= total);
  const rest = all.filter((r: any) => !honest.includes(r));
  const pct = (x: number | null | undefined): string => (x == null ? '–' : `${(100 * x).toFixed(1)}%`);
  const how = (r: any): string => {
    const fmt = r.format === 'chat' ? 'chat template, thinking off' : r.format === 'bare' || !r.format ? 'prompt bare' : `taught turn (${esc(r.format)})`;
    const cap = r.max_new ? ` · cap ${r.max_new}` : '';
    const ended = r.stopped != null ? ` · ended itself ${Math.round(100 * r.stopped)}%` : '';
    return `${fmt}${cap}${ended}`;
  };
  const nameCell = (r: any): string => r.kind === 'thorp'
    ? `${r.ship_key ? `<a href="/leaderboard/thorp/${encodeURIComponent(r.ship_key)}"><b>${esc(r.name)}</b></a>` : `<b>${esc(r.name)}</b>`}${r.rigged ? ` <span class="${pillCls('bad')}">rigged</span>` : ''}<div class="s">ours · ${esc(r.run || '')}</div>`
    : `<a href="/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a><div class="s">${makerLink(r.model)}</div>`;
  const row = (r: any, rank: string): string => `<tr class="lb-${r.kind === 'thorp' ? 'thorp' : 'outside'}${rank === '–' ? ' unread' : ''}">
      <td>${rank}</td>
      <td>${nameCell(r)}</td>
      <td>${fmtParams(r.params)}</td>
      <td><b>${pct(r.prompt_strict)}</b><div class="s">${r.prompts} of ${total} read${r.prompts < total ? ' · subset' : ''}</div></td>
      <td>${pct(r.instruction_strict)}</td>
      <td><span class="s">${how(r)}</span></td></tr>`;
  const head = '<tr><th>#</th><th>model</th><th>parameters</th><th>prompt-level strict <span class="s">the board</span></th><th>instruction-level strict</th><th>how it was asked</th></tr>';
  const body = honest.map((r: any, i: number) => row(r, String(i + 1))).join('') + rest.map((r: any) => row(r, '–')).join('')
    || `<tr><td colspan="6" class="${emptyCls(true)}">no model of this size has been read on IFEval yet</td></tr>`;
  const best = honest[0];
  const rigged = all.filter((r: any) => r.rigged).length;
  const lead = `<div class="sqp"><b class="${best ? 'good' : 's'}">${best ? pct(best.prompt_strict) : '–'}</b><span>${best ? `${esc(best.name)} on prompt-level strict, the best of ${honest.length} read on the ${total}` : `no honest reading on the ${total} yet`}</span></div>
    <div class="sqp"><b>${rigged} of ${all.length}</b><span>readings are rigged, trained on the official prompts, and stand below the line</span></div>`;
  return { head, body, lead };
}
