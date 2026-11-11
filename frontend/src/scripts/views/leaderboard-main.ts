// The Leaderboard's main board (UI.md "Leaderboard"), as typed renderers: the ranked chaining
// table, the approaching board, the every-ship table, and Smoking Qwen's head/backtest/chart. The
// competitor and lab sub-views are separate pages for now.

import { esc, fmtParams, signed } from '../../lib/format';
import { emptyCls, pillCls } from '../../lib/ui';
import { fitReachAt, polyfit, polyval } from '../../lib/analysis';
import { modelHash, shipHash } from '../router';
import { chainingCell, logicCell, testCell, makerOf, makerLink, minicards } from './leaderboard';
import { causeCell } from './helpers';

const CAUSE_NOTE = "the logic deck's chaining gain on its cause-and-effect items (when X, then Y; Y makes Z): eight items, so a strong reading counts and a small one is noise; the mark, 0.1, dotted";

type Rung = { preset: string; name: string; total: number };
const classLink = (rungs: Rung[], preset: string): string => {
  const r = rungs.find((x) => x.preset === preset);
  return r ? `<a href="${modelHash(r)}">${esc(r.preset)} · ${esc(r.name)}</a>` : esc(preset || '–');
};
const classRankOf = (rungs: Rung[]) => (p: string): number => {
  const i = rungs.findIndex((r) => r.preset === p);
  return i < 0 ? 99 : i;
};

export function runsHtml(lb: any, want: string, rungs: Rung[]): { head: string; body: string; count: string } {
  const thr = lb.threshold ?? 0.1, tests = lb.tests || [];
  const rank = classRankOf(rungs);
  const rows = (lb.ships || []).filter((r: any) => !want || r.preset === want).sort((a: any, b: any) => (b.chaining_lift ?? -9) - (a.chaining_lift ?? -9));
  const head = `<tr><th>ship</th><th>class</th><th>voyages</th><th>chaining lift</th><th>chaining gain <span class="s">logic deck</span></th><th>passed</th>${tests.map((t: any) => `<th>${esc(t.name)}</th>`).join('')}</tr>`;
  const body = rows.map((r: any) => `<tr><td>${r.ship_key ? `<a href="${shipHash(r.ship_key)}">${esc(r.ship || r.run)}</a>` : esc(r.ship || r.run)}</td><td data-sort="${rank(r.preset)}">${classLink(rungs, r.preset)}</td>
    <td data-sort="${r.sailings ?? 1}">${r.sailings ?? 1}</td><td data-sort="${r.chaining_lift ?? -9}">${chainingCell(r.chaining_lift, thr)}</td><td data-sort="${r.logic && r.logic.gain != null ? r.logic.gain : -9}">${logicCell(r.logic, 'thorp')}</td><td data-sort="${r.passed ?? 0}">${r.passed ?? 0} of ${tests.length}</td>
    ${tests.map((t: any) => `<td>${testCell((r.tests || {})[t.key])}</td>`).join('')}</tr>`).join('')
    || `<tr><td colspan="${6 + tests.length}" class="${emptyCls(true)}">no ships with chaining readings in this size</td></tr>`;
  return { head, body, count: `${rows.length} ship${rows.length === 1 ? '' : 's'}` };
}

export function smokingHtml(sq: any): { head: string; backtest: string; rule: string } {
  const T = sq.target || {}, th = sq.thorp || {}, rng = sq.range || [], scored = rng.filter((c: any) => c.scored);
  const need = 3, pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(100 * v)}%`);
  const above = (sq.classes_above_noise || []).length;
  const pLin = sq.p_range_linear ?? (th.linear || {}).p_at_or_above_target, pBend = sq.p_range_bending ?? (th.bending || {}).p_at_or_above_target;
  const head = sq.forecastable
    ? `<div class="sqp"><b class="${pLin >= 0.9 ? 'good' : ''}">${pct(pLin)}</b><span>on the straight line (conservative), the least over the range</span></div>
       <div class="sqp"><b class="${pBend >= 0.9 ? 'accent' : ''}">${pct(pBend)}</b><span>on the bending curve (probable), the least over the range</span></div>`
    : `<div class="sqp"><b class="s">not yet forecastable</b><span>${above} of ${need} classes above the noise (a chaining lift over ${sq.noise ?? 0.03}); a curve through noise extrapolates nothing, so the curves below are drawn but no probability is claimed</span></div>`;
  const claimed = sq.forecastable && pLin >= 0.9, probable = sq.forecastable && !claimed && pBend >= 0.9;
  const head2 = `<div class="sqp"><b>${claimed ? `<span class="${pillCls('good')}">claimed</span>` : probable ? `<span class="${pillCls('accent')}">probable</span>` : `<span class="${pillCls('')}">not claimed</span>`}</b><span>${rng.length ? `${scored.length} of ${rng.length} competitors scored${sq.hardest ? `; the hardest, ${esc(sq.hardest)}` : ''}, each to be matched at a tenth its size` : `target: ${esc(T.model ? T.model.split('/').pop() : '')} at ${signed(T.chaining_lift)}, a Nothing up my sleeve of ${fmtParams(sq.smoke_at)}`}</span></div>`;
  const fmtBand = (f: any) => (f ? `${signed(f.predicted)} <span class="s">(${signed(f.band[0])} to ${signed(f.band[1])})</span>` : '–');
  const backtest = (sq.backtest || []).map((b: any) => `<div class="sqbt"><div><b>${esc(b.test)}</b> · actual ${signed(b.actual)}</div>
    ${['linear', 'bending'].filter((k) => b[k]).map((k) => `<div class="sqbk ${b[k].inside_band ? 'good' : 'bad'}">${k === 'linear' ? 'straight' : 'bending'}: ${fmtBand(b[k])} · ${b[k].inside_band ? 'inside the band' : b[k].predicted < b.actual ? 'missed (too low)' : 'missed (too high)'}</div>`).join('')}</div>`).join('') || '<div class="s">no backtest yet</div>';
  return { head: head + head2, backtest, rule: 'Claimed when forecastable (three classes above the noise) and P ≥ 0.9 on the straight line for every competitor in the range; "probable" when only the bending curve reaches 0.9.' };
}

export function boardHtml(lb: any, sq: any, rungs: Rung[], showFc: boolean, showPy: boolean, sizeClass = 'small'): { head: string; body: string; approach: string; thr: string; note: string } {
  const thr = lb.threshold ?? 0.1, tests = lb.tests || [];
  const rankOf = classRankOf(rungs);
  const pts = ((sq.thorp || {}).points || []).filter((p: any) => p.params && p.chaining_lift != null);
  const xs = pts.map((p: any) => Math.log10(p.params)), ys = pts.map((p: any) => p.chaining_lift), top = xs.length ? Math.max(...xs) : 6;
  const fits = { straight: pts.length >= 2 ? polyfit(xs, ys, 1) : null, bending: pts.length >= 3 ? polyfit(xs, ys, 2) : null };
  const trusted = !!sq.forecastable;
  const note = !pts.length ? '' : trusted ? 'forecasts trusted: three classes above the noise'
    : `<span class="accent">forecasts not yet trusted</span>: ${(sq.classes_above_noise || []).length} of 3 classes above the noise`;
  const range: Record<string, any> = Object.fromEntries((sq.range || []).map((c: any) => [c.model, c]));
  const testsOf = (r: any) => r.kind === 'thorp'
    ? ((lb.ships || []).find((x: any) => x.ship_key === r.ship_key) || (lb.board || []).map((b: any) => b.best).find((b: any) => b && b.ship_key === r.ship_key) || {}).tests
    : ((lb.reference || []).find((x: any) => x.model === r.model) || {}).tests;
  const asRow = (r: any): any => {
    if (r.kind === 'thorp') {
      const best = (lb.board || []).map((b: any) => b.best).find((b: any) => b && b.ship_key === r.ship_key) || {};
      const preset = best.preset || (r.ship_key || '').split(':')[0], rr = rungs.find((x) => x.preset === preset);
      return { kind: 'thorp', cls: preset, ship: { ...best, name: r.name, ship: r.ship || best.ship, ship_key: r.ship_key, sailings: r.sailings ?? best.sailings }, params: r.params ?? (rr ? rr.total : null),
        lift: r.chaining_lift, passed: r.passed, tests: testsOf(r), logic: r.logic, src: r };
    }
    return { kind: 'outside', model: r.model, name: r.name, maker: makerOf(r.model), competitor: r.kind === 'competitor', params: r.params ?? (range[r.model] || {}).params ?? null,
      lift: r.chaining_lift, passed: r.passed, tests: testsOf(r), logic: r.logic, tenth: range[r.model], src: r };
  };
  const table = (lb.table || []).filter((r: any) => (r.size_class || 'small') === sizeClass);
  const rows = table.filter((r: any) => r.group === 'chaining' && (showPy || r.kind !== 'ladder')).sort((a: any, b: any) => a.rank - b.rank).map(asRow);
  const seen = new Set(table.map((r: any) => r.model).filter(Boolean));
  if (sizeClass === 'small') for (const c of sq.range || []) if (!seen.has(c.model)) rows.push({ kind: 'outside', name: c.label, maker: makerOf(c.model), competitor: true, params: c.params, lift: null, pending: true });
  // the approaching board
  const approachRows = table.filter((r: any) => r.group === 'approaching').sort((a: any, b: any) => a.rank - b.rank).map((r: any) => ({ ...asRow(r), src: r }));
  const approach = approachRows.map((r: any) => {
    const name = r.kind === 'thorp'
      ? `<a href="/leaderboard/thorp/${encodeURIComponent(r.ship.ship_key)}"><b>${esc(r.ship.name)}</b></a><div class="s">${r.ship.ship_key ? `<a href="${shipHash(r.ship.ship_key)}">${esc(r.ship.ship || '')}</a>` : esc(r.ship.ship || '')}${r.ship.sailings ? ` · ${r.ship.sailings} sailing${r.ship.sailings === 1 ? '' : 's'}` : ''}</div>`
      : `<a href="/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a>${r.competitor ? ` <span class="${pillCls('blue')}">2–4B</span>` : ''}<div class="s">${makerLink(r.model || r.name)}</div>`;
    const held = r.src.cards_held;
    const rank = r.src.tied ? `<span title="tied within the noise: one-hop lifts within 0.05 of each other">=${r.src.rank}</span><div class="s tiehint">tied within the noise</div>` : r.src.rank;
    return `<tr class="lb-${r.kind}"><td>${rank}</td><td>${name}</td><td>${fmtParams(r.params)}</td>
      <td>${r.src.cards ? minicards(r.src.cards) : '<span class="miniset"><span class="s">unreadable</span></span>'} <span class="s">${held == null ? '' : `${held} of 4`}</span></td>
      <td>${r.src.one_hop != null ? signed(r.src.one_hop) : '–'}</td>
      <td>${causeCell(r.src.cause_gain)}</td>
      <td class="noise" title="below +0.03 the chaining lift is noise">${r.lift != null ? signed(r.lift) : '–'}</td></tr>`;
  }).join('');
  // forecasts
  let fcNoise = 0;
  if (showFc && sizeClass === 'small' && (fits.straight || fits.bending)) {
    const measured = new Set(table.filter((r: any) => r.kind === 'thorp').map((r: any) => (r.ship_key || '').split(':')[0]));
    const at = rungs.filter((r) => !measured.has(r.preset) && r.total).map((r) => ({ cls: r.preset, params: r.total }));
    if (sq.smoke_at && !at.some((a) => Math.abs(a.params - sq.smoke_at) / sq.smoke_at < 0.1)) at.push({ label: `Nothing up my sleeve ${fmtParams(sq.smoke_at)}`, params: sq.smoke_at, smoke: true } as any);
    for (const a of at) {
      const x = Math.log10(a.params), st = fits.straight ? polyval(fits.straight, x) : null, be = fits.bending ? polyval(fits.bending, x) : null;
      const lift = be ?? st;
      if (lift != null && lift > (lb.noise ?? 0.03)) rows.push({ kind: 'forecast', name: (a as any).label, cls: (a as any).cls, params: a.params, lift, straight: st, bending: be, smoke: (a as any).smoke });
      else fcNoise++;
    }
  }
  const note2 = note + (fcNoise ? ` · ${fcNoise} forecast${fcNoise === 1 ? '' : 's'} still in the noise, so not on this board` : '');
  rows.sort((a: any, b: any) => (b.lift ?? -9) - (a.lift ?? -9) || (b.params ?? 0) - (a.params ?? 0));
  const liftCell = (r: any) => r.pending ? '<span class="s">being scored</span>'
    : r.kind === 'forecast' ? `<span title="bending (probable) ${signed(r.bending)}; straight (conservative) ${signed(r.straight)}"><b>${signed(r.bending)}</b> <span class="s">bending</span><div class="s">${signed(r.straight)} straight</div></span>`
    : chainingCell(r.lift, thr);
  const matchCell = (r: any) => {
    if (r.kind !== 'outside' || !r.competitor) return '';
    const tenth = (r.tenth && r.tenth.smoke_at) || (r.params ? r.params / 10 : null);
    let out = `<div><b>${fmtParams(tenth)}</b> <span class="s">a tenth its size</span></div>`;
    const c = r.tenth;
    if (c && c.scored) out += ['bending', 'linear'].filter((k) => c[k]).map((k) => `<div title="5–95% ${signed(c[k].band[0])} to ${signed(c[k].band[1])}"><span class="s">${k === 'linear' ? 'straight' : k}</span> ${signed(c[k].predicted)}${c[k].p_at_or_above_target != null ? ` · <b>P ${Math.round(100 * c[k].p_at_or_above_target)}%</b>` : ''}</div>`).join('');
    if (r.lift != null && (fits.bending || fits.straight)) {
      const reach = (k: 'straight' | 'bending') => (fits[k] ? fitReachAt(fits[k], r.lift, top) : undefined);
      out += `<div class="s">fits reach it at: ${['bending', 'straight'].filter((k) => fits[k as 'straight' | 'bending']).map((k) => `${k} ${reach(k as 'straight' | 'bending') == null ? 'never' : fmtParams(reach(k as 'straight' | 'bending'))}`).join(' · ')}</div>`;
    }
    return out;
  };
  let rank = 0;
  const head = `<tr><th>#</th><th>model</th><th>parameters</th><th>chaining lift</th><th title="the logic deck's chaining gain: the lift with both premises less the better single premise, on invented words and counterfactual premises; the proof that a pass is chaining, not knowing or one premise">chaining gain<div class="s">logic deck</div></th><th title="${CAUSE_NOTE}">cause and effect<div class="s">chaining gain</div></th><th>passed</th>${tests.map((t: any) => `<th class="tcol">${esc(t.name.replace(/^The /, ''))}</th>`).join('')}<th>Nothing up my sleeve must match it at</th></tr>`
  const body = rows.map((r: any) => {
      const ranked = r.kind !== 'forecast' && !r.pending; if (ranked) rank++;
      const name = r.kind === 'thorp' ? `<a href="/leaderboard/thorp/${encodeURIComponent(r.ship.ship_key)}"><b>${esc(r.ship.name || `Nothing up my sleeve ${r.cls}`)}</b></a><div class="s">${r.ship.ship_key ? `<a href="${shipHash(r.ship.ship_key)}">${esc(r.ship.ship)}</a>` : esc(r.ship.ship || '')} · ${r.ship.sailings ?? 1} sailing${(r.ship.sailings ?? 1) === 1 ? '' : 's'}</div>`
        : r.kind === 'forecast' ? `${r.cls ? classLink(rungs, r.cls) : `<b>${esc(r.name)}</b>`} <span class="${pillCls('accent')}">forecast</span>${r.smoke ? '<div class="s">a tenth of Qwen3 4B</div>' : ''}`
        : `${r.model && !r.pending ? `<a href="/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.name)}</b></a>` : `<b>${esc(r.name)}</b>`}${r.competitor ? ` <span class="${pillCls('blue')}" title="a 2–4B competitor: Nothing up my sleeve must match it at a tenth its size">2–4B</span>` : ''}<div class="s">${makerLink(r.model || r.name)}</div>`;
      return `<tr class="lb-${r.kind}${r.kind === 'forecast' && !trusted ? ' untrusted' : ''}${r.pending ? ' pending' : ''}"><td>${ranked ? rank : ''}</td><td>${name}</td><td>${fmtParams(r.params)}</td>
        <td>${liftCell(r)}</td><td>${logicCell(r.logic, r.kind)}</td><td>${r.kind === 'forecast' ? '' : causeCell(r.src && r.src.cause_gain)}</td><td>${r.passed != null ? `${r.passed} of ${tests.length}` : ''}</td>${tests.map((t: any) => `<td class="tcol">${r.tests ? testCell(r.tests[t.key]) : ''}</td>`).join('')}<td>${matchCell(r)}</td></tr>`;
    }).join('') || `<tr><td colspan="${8 + tests.length}" class="${emptyCls(true)}">no readings yet</td></tr>`;
  return { head, body, approach, thr: String(thr), note: note2 };
}


/** The candidates to approach in a size class with no chaining reading yet: five targets, most
 *  likely first, with the reason each is likely and the evidence held so far. A candidate is not
 *  ranked on a chaining lift it does not have; its logic-deck reading, where one exists, is shown
 *  beside. */
export function candidatesHtml(cands: any[], sizeClass: string): { head: string; body: string; count: string } {
  const label = sizeClass === 'medium' ? 'medium' : 'large';
  const head = '<tr><th>#</th><th>candidate</th><th>parameters</th><th>why it is likely</th><th>the evidence so far</th><th>status</th></tr>';
  const body = (cands || []).map((c: any) => {
    const params = `${fmtParams(c.params)}${c.active ? `<div class="s">${fmtParams(c.active)} active</div>` : ''}`;
    const arc = c.arc ? `ARC-AGI-2 <b>${Number(c.arc.score).toFixed(1)}</b> <span class="s">pass@2</span><div class="s">${esc(c.arc.source)}</div>` : '';
    const logic = c.logic
      ? `logic deck <b>${signed(c.logic.gain)}</b> gain, ${signed(c.logic.one_hop)} one-hop<div class="s">${Math.round(100 * c.logic.score)}% of items right</div>`
      : '';
    const evidence = [arc, logic].filter(Boolean).join('<div class="s">·</div>') || '<span class="s">not read yet</span>';
    const link = c.source ? ` · <a href="${esc(c.source)}" target="_blank" rel="noopener">model card</a>` : '';
    return `<tr class="lb-candidate"><td>${c.rank}</td>
      <td><b>${esc(c.label)}</b><div class="s">${esc(c.lab)}${link}</div></td>
      <td>${params}</td><td class="candwhy">${esc(c.why)}</td><td>${evidence}</td>
      <td><span class="${pillCls('accent')}">candidate</span>${c.note ? `<div class="s">${esc(c.note)}</div>` : ''}</td></tr>`;
  }).join('') || `<tr><td colspan="6" class="${emptyCls(true)}">no ${esc(label)} candidates</td></tr>`;
  return { head, body, count: `${(cands || []).length} candidate${(cands || []).length === 1 ? '' : 's'}` };
}

/** The canonical intelligence ranking: the published ARC-AGI-2 scores (pass@2 on the 120-task
 *  evaluation set), and Nothing up my sleeve's own reading once the Kipling ARC arm has one. It is a
 *  separate panel because ARC percentages and chaining lift are different scales, not two columns of
 *  one table. */
export function reasoningHtml(r: any): { head: string; body: string; count: string } {
  const head = '<tr><th>model</th><th>ARC-AGI-2 <span class="s">pass@2</span></th><th>the reading</th></tr>';
  const published = (r?.published || []).map((x: any) => `<tr class="lb-outside"><td><b>${esc(x.label)}</b><div class="s">${esc(x.model)}</div></td>
    <td><b>${Number(x.score).toFixed(1)}</b></td><td class="s">${esc(x.source)} · ${esc(x.date)}${x.url ? ` · <a href="${esc(x.url)}" target="_blank" rel="noopener">leaderboard</a>` : ''}</td></tr>`).join('');
  const measured = (r?.measured || []).map((x: any) => `<tr class="lb-candidate"><td><b>${esc(x.label)}</b><div class="s">${esc(x.model)}</div></td>
    <td><b>${Number(x.score).toFixed(1)}</b><div class="s">${x.tasks || 0} tasks${x.cell_accuracy != null ? ` · ${Math.round(100 * x.cell_accuracy)}% cells` : ''}</div></td><td class="s">${esc(x.source)}${x.mode ? ` · ${esc(x.mode)}` : ''}</td></tr>`).join('');
  const earlier = measured ? `<tr class="lb-group"><td colspan="3" class="s">our readings — pilots, not published scores</td></tr>${measured}` : '';
  const thorp = r?.thorp
    ? `<tr class="lb-thorp"><td><b>Nothing up my sleeve</b><div class="s">${esc(r.thorp.ship || r.thorp.run || '')}</div></td><td><b>${Number(r.thorp.score).toFixed(1)}</b></td><td class="s">${esc(r.thorp.note || 'our own reading')}</td></tr>`
    : `<tr class="lb-thorp"><td><b>Nothing up my sleeve</b><div class="s">no ARC-AGI-2 reading yet</div></td><td><span class="s">not yet run</span></td><td class="s">the Kipling ARC arm is the first attempt; <b>scripts/score_arc.py</b> scores an outside model today</td></tr>`;
  return { head, body: published + earlier + thorp, count: `${(r?.published || []).length} published` };
}

/** The Face scorecard (11 November): the four Faces' abilities, the mark each must reach, Qwen 3 4B
 *  the reference, and the fleet's best of each class. A ✓ is at or above the mark, ≈ within 10% of it;
 *  the cell's title names the run that gave a class's reading. The Mover is its one-hop ability: its
 *  look is a diffuse head in Qwen and the 300k alike, so it is not the card's read. */
export function facesHtml(f: any, rungs: Rung[]): { head: string; body: string } {
  const keys = ['nevermore', 'counter', 'scales', 'mover'];
  const cols: Record<string, string> = { nevermore: 'copy gain', counter: 'sentence-position R²', scales: 'order gain', mover: 'one-hop lift' };
  const marks = f.marks || {};
  const cell = (v: number | undefined, k: string, held: boolean, near: boolean, from?: string) => {
    if (v == null) return '<span class="s">–</span>';
    const m = marks[k];
    const title = `${from ? `the run: ${from}. ` : ''}${held ? 'at or above' : near ? 'within 10% of' : 'below'} the mark (${m})`;
    return `<span class="${held ? 'good' : near ? 'accent' : ''}" title="${esc(title)}">${v.toFixed(3)}${held ? ' ✓' : near ? ' ≈' : ''}</span>`;
  };
  const heldCell = (held: string[], near: string[]) => `${held.length} of ${keys.length}${near.length ? ` <span class="s">${near.length} near</span>` : ''}`;
  const head = `<tr><th>model</th>${keys.map((k) => `<th>${esc(f.names?.[k] || k)}<div class="s">${cols[k]} · ${marks[k]}</div></th>`).join('')}<th>Faces held</th></tr>`;
  const refRows = (f.reference || []).map((r: any) => `<tr class="lb-outside"><td><a href="/leaderboard/competitor/${encodeURIComponent(r.model)}"><b>${esc(r.label)}</b></a> <span class="${pillCls('blue')}">2–4B</span><div class="s">the reference</div></td>
    ${keys.map((k) => `<td>${cell(r.values?.[k], k, (r.held || []).includes(k), (r.near || []).includes(k))}</td>`).join('')}<td>${heldCell(r.held || [], r.near || [])}</td></tr>`).join('');
  const fleetRows = (f.fleet || []).map((r: any) => `<tr class="lb-thorp"><td>${classLink(rungs, r.preset)}<div class="s">best of its ships</div></td>
    ${keys.map((k) => `<td>${cell(r.values?.[k], k, (r.held || []).includes(k), (r.near || []).includes(k), r.from?.[k])}</td>`).join('')}<td>${heldCell(r.held || [], r.near || [])}</td></tr>`).join('');
  const body = refRows + (fleetRows ? `<tr class="lb-group"><td colspan="${keys.length + 2}" class="s">the fleet — each class's best of its ships for that Face</td></tr>${fleetRows}` : '')
    || `<tr><td colspan="${keys.length + 2}" class="${emptyCls(true)}">no Face readings yet</td></tr>`;
  return { head, body };
}

export async function drawSmokingChart(sq: any): Promise<void> {
  if (!sq || !document.getElementById('sqchart')) return;
  // imported here, not at module load: ECharts needs `self`, which the server render does not have
  const { plot, layout, tok } = await import('../../lib/charts');
  const T = sq.target || {}, th = sq.thorp || {}, pts = th.points || [];
  const lx = Math.log10, traces: any[] = [];
  const xs = pts.map((p: any) => lx(p.params)), ys = pts.map((p: any) => p.chaining_lift);
  const grid = Array.from({ length: 61 }, (_, i) => 5 + i * (lx(sq.smoke_at) - 5) / 60);
  for (const [kind, deg, col, dash] of [['linear', 1, tok('blue'), 'solid'], ['bending', 2, tok('accent'), 'dash']] as const) {
    const f = th[kind]; if (!f || pts.length < deg + 1) continue;
    const co = polyfit(xs, ys, deg);
    traces.push({ x: grid.map((g) => 10 ** g), y: grid.map((g) => polyval(co, g)), mode: 'lines', name: kind === 'linear' ? 'straight line' : 'bending curve', line: { color: col, width: 1.6, dash }, hoverinfo: 'skip' });
    traces.push({ x: [sq.smoke_at], y: [f.predicted], mode: 'markers', name: `${kind === 'linear' ? 'straight' : 'bending'} at 400M`, showlegend: false, marker: { color: col, size: 9, symbol: 'diamond' },
      error_y: { type: 'data', symmetric: false, array: [f.band[1] - f.predicted], arrayminus: [f.predicted - f.band[0]], color: col, thickness: 1.4, width: 6 },
      hovertemplate: `${kind === 'linear' ? 'straight' : 'bending'} at 400M: %{y:.3f}<br>5-95%: ${signed(f.band[0])} to ${signed(f.band[1])}<extra></extra>` });
  }
  traces.push({ x: pts.map((p: any) => p.params), y: ys, mode: 'markers+text', name: 'Nothing up my sleeve (best of each size)', text: pts.map((p: any) => p.name), textposition: 'top center', textfont: { size: 10, color: tok('text') },
    marker: { color: tok('good'), size: 10 }, customdata: pts.map((p: any) => p.run || ''), hovertemplate: '%{text} · %{customdata}<br>%{x:.3s} parameters<br>chaining lift %{y:.3f}<extra></extra>' });
  const comp = (sq.reference || []).filter((r: any) => r.competitor && r.chaining_lift != null);
  if (comp.length) traces.push({ x: comp.map((r: any) => r.params), y: comp.map((r: any) => r.chaining_lift), mode: 'markers+text', name: 'the 2–4B competitors', text: comp.map((r: any) => r.short), textposition: 'middle left', textfont: { size: 9, color: tok('bad') },
    marker: { color: tok('bad'), size: 9, symbol: 'diamond-open' }, hovertemplate: '%{text}<br>%{x:.3s} parameters<br>chaining lift %{y:.3f}<extra></extra>' });
  const ref = (sq.reference || []).filter((r: any) => !r.competitor);
  if (ref.length) traces.push({ x: ref.map((r: any) => r.params), y: ref.map((r: any) => r.chaining_lift), mode: 'markers', name: 'reference ladder (hover for each)', text: ref.map((r: any) => r.short),
    marker: { color: tok('muted'), size: 7, symbol: 'circle-open' }, hovertemplate: '%{text}<br>%{x:.3s} parameters<br>chaining lift %{y:.3f}<extra></extra>' });
  const shapes: any[] = [
    { type: 'line', xref: 'x', yref: 'paper', x0: sq.smoke_at, x1: sq.smoke_at, y0: 0, y1: 1, line: { color: tok('muted'), width: 1, dash: 'dash' } },
    { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: -(sq.noise ?? 0.03), y1: sq.noise ?? 0.03, fillcolor: 'rgba(139,148,158,0.10)', line: { width: 0 }, layer: 'below' },
    { type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: sq.threshold ?? 0.1, y1: sq.threshold ?? 0.1, line: { color: tok('accent'), width: 1, dash: 'dot' } },
  ];
  if (T.chaining_lift != null) shapes.push({ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: T.chaining_lift, y1: T.chaining_lift, line: { color: tok('bad'), width: 1.2 } });
  const notes: any[] = [
    { xref: 'x', yref: 'paper', x: Math.log10(sq.smoke_at), y: 1, yanchor: 'bottom', showarrow: false, text: '400M', font: { size: 10, color: tok('muted') } },
    { xref: 'paper', yref: 'y', x: 0, y: sq.threshold ?? 0.1, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: 'performed (0.1)', font: { size: 9, color: tok('accent') } },
    { xref: 'paper', yref: 'y', x: 0, y: sq.noise ?? 0.03, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: 'noise', font: { size: 9, color: tok('muted') } },
  ];
  if (T.chaining_lift != null) notes.push({ xref: 'paper', yref: 'y', x: 0, y: T.chaining_lift, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: `${esc(T.model ? T.model.split('/').pop() : '')} ${signed(T.chaining_lift)}`, font: { size: 10, color: tok('bad') } });
  plot('sqchart', traces, layout({ xaxis: { type: 'log', title: { text: 'parameters' }, range: [5, 10] }, yaxis: { title: { text: 'chaining lift' }, zeroline: false }, shapes, annotations: notes, height: 400, legend: { orientation: 'h', y: -0.2 } }));
}
