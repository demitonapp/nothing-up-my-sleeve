// ---- Journey: one sailing read as the data's journey up through its layers (UI.md, "Journey").
// The base is the soundings (fleet.SOUNDINGS, the evaluator `soundings`): the stack is drawn bottom
// to top, embeddings, then each layer split into its attention half and its feed-forward half, then
// the output. Beside each depth is the guess the model would make if it stopped there (bits per
// byte) and how much that layer lowered it. Out of each half comes an arrow sized by how hard it
// writes into the stream and tilted by which way: straight up is along the stream (turn 0), level
// is across it (turn 1, something new), down is against it (turn 2, pushing back).
// Modules the viewer switches on draw per layer: the three sieves (push, move, heading) for each
// half, the stars lit in that layer, and the layer's push kink, all at the step chosen.
// A sailing that received heads from another (opts.transplant: the Magician's Apprentice) has the
// receiving attention half outlined and labelled, and the embeddings marked if positions came too.
import { emptyCls } from './ui';
import { esc } from './format.js';

const ROW = 74, BOX_W = 112, GAP = 10, LEFT = 118, TOP = 34, BASE = 40;

// a series [steps, values] read at a step: the last value at or before it
export function at(sr, step) {
  if (!sr) return null;
  let v = null;
  for (let i = 0; i < sr[0].length && sr[0][i] <= step; i++) v = sr[1][i];
  return v;
}
// the number of layers a sailing's soundings (or sieves) describe
export function layersOf(m) {
  let n = 0;
  for (const k of Object.keys(m)) {
    // the guesses (soundings/layer_k/bpb) run one past the last layer, so they don't count layers
    const g = k.match(/^(?:soundings\/layer_(\d+)\/(?:attn|mlp)_|(?:grad_norm|update_ratio|heading)\/layer_(\d+))/);
    if (g) n = Math.max(n, +(g[1] ?? g[2]) + 1);
  }
  return n;
}
// every step a sailing has soundings at
export function soundingSteps(m) {
  const s = new Set();
  for (const k of Object.keys(m)) if (k.startsWith('soundings/')) m[k][0].forEach(x => s.add(x));
  return [...s].sort((a, b) => a - b);
}
const turnColour = t => t == null ? 'var(--muted)' : t < 0.5 ? 'var(--good)' : t <= 1.5 ? 'var(--blue)' : 'var(--bad)';
const turnWord = t => t == null ? '' : t < 0.5 ? 'along' : t <= 1.5 ? 'across' : 'against';
const f2 = v => v == null ? '–' : (Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));

function arrow(cx, cy, write, turn) {
  if (write == null) return '';
  const len = 8 + 34 * Math.min(1, Math.sqrt(Math.max(0, write) / 4));
  const a = (turn ?? 0) * Math.PI / 2;  // 0 up, π/2 right (across), π down (against)
  const x2 = cx + len * Math.sin(a), y2 = cy - len * Math.cos(a), col = turnColour(turn);
  const h = 5, ax = Math.atan2(y2 - cy, x2 - cx);
  const p1 = `${x2 - h * Math.cos(ax - 0.5)},${y2 - h * Math.sin(ax - 0.5)}`, p2 = `${x2 - h * Math.cos(ax + 0.5)},${y2 - h * Math.sin(ax + 0.5)}`;
  return `<g><title>writes ${f2(write)}, turn ${f2(turn)} (${turnWord(turn)})</title><line x1="${cx}" y1="${cy}" x2="${x2}" y2="${y2}" stroke="${col}" stroke-width="2.2"/>
    <polygon points="${x2},${y2} ${p1} ${p2}" fill="${col}"/></g>`;
}

// m: the sailing's metrics (/api/metrics); step: the step shown; defs: /api/sieves; opts.modules: Set of
// 'push' 'move' 'heading' 'stars' 'kink'; opts.kinks: {layer_i: kink}; opts.title: the sailing's name
export function drawJourney(el, m, step, defs, opts = {}) {
  const L = layersOf(m);
  if (!L) { el.innerHTML = `<div class="${emptyCls()}">${esc(opts.title || 'this sailing')}: no layers on the ledger yet</div>`; return; }
  const mods = opts.modules || new Set(), S = k => m[k];
  const hasSound = Object.keys(m).some(k => k.startsWith('soundings/'));
  const depthY = k => TOP + (L + 1 - k) * ROW;  // depth k = after k layers; 0 is the embeddings
  const W = LEFT + 2 * BOX_W + GAP + 270, H = depthY(0) + BASE + 12;
  const bpb = k => at(S(`soundings/layer_${k}/bpb`), step);
  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" class="journey" role="img" aria-label="${esc(opts.title || '')} through its layers">`;
  // the output on top, the embeddings at the bottom
  const out = bpb(L);
  svg += `<rect x="${LEFT}" y="${TOP - 4}" width="${2 * BOX_W + GAP}" height="26" rx="5" class="j-io"/>
    <text x="${LEFT + BOX_W + GAP / 2}" y="${TOP + 13}" text-anchor="middle" class="j-lbl">the guess: next word</text>`;
  svg += `<rect x="${LEFT}" y="${depthY(0) - 4}" width="${2 * BOX_W + GAP}" height="${BASE - 8}" rx="5" class="j-io"/>
    <text x="${LEFT + BOX_W + GAP / 2}" y="${depthY(0) + 16}" text-anchor="middle" class="j-lbl">embeddings: the words as read</text>`
    + (opts.transplant && (opts.transplant.pos || opts.transplant.tok) ? `<text x="${LEFT + 2 * BOX_W + GAP + 12}" y="${depthY(0) + 16}" class="j-tp">⇄ ${[opts.transplant.tok ? 'token' : '', opts.transplant.pos ? 'position' : ''].filter(Boolean).join(' and ')} embeddings transplanted</text>` : '');
  // the guess at each depth, and the drop from the depth below
  for (let k = 0; k <= L; k++) {
    const v = bpb(k), below = k ? bpb(k - 1) : null, d = v != null && below != null ? v - below : null;
    const y = k === L ? TOP + 13 : depthY(k) + (k === 0 ? 16 : -6);
    svg += `<text x="${LEFT - 10}" y="${y}" text-anchor="end" class="j-bpb"><title>the guess if the model stopped here, bits per byte</title>${v == null ? '' : f2(v)}</text>`;
    if (d != null) svg += `<text x="${LEFT - 10}" y="${y + 13}" text-anchor="end" class="${d <= 0 ? 'j-good' : 'j-bad'}">${d <= 0 ? '−' : '+'}${f2(Math.abs(d))}</text>`;
  }
  // the layers, each an attention half and a feed-forward half
  for (let i = 0; i < L; i++) {
    const y = depthY(i + 1) + 10, h = ROW - 26;
    const halves = [['attn', 'attention', LEFT], ['mlp', 'feed-forward', LEFT + BOX_W + GAP]];
    svg += `<text x="${LEFT - 64}" y="${y + h / 2 + 4}" text-anchor="end" class="j-layer">layer ${i}</text>`;
    // the receiving layer, and any whole layers beneath it that came too (transplant.below)
    const tp = opts.transplant, here = tp && Number(tp.layer) === i, whole = tp && (tp.below || []).map(Number).includes(i);
    for (const [key, name, x] of halves) {
      const w = at(S(`soundings/layer_${i}/${key}_write`), step), t = at(S(`soundings/layer_${i}/${key}_turn`), step);
      svg += `<rect x="${x}" y="${y}" width="${BOX_W}" height="${h}" rx="5" class="j-box${(here && key === 'attn') || whole ? ' j-transplant' : ''}"/>
        <text x="${x + 8}" y="${y + 15}" class="j-lbl">${name}</text>`;
      if (w != null) svg += `<text x="${x + 8}" y="${y + 30}" class="j-sub">writes ${f2(w)} · ${turnWord(t)}</text>`;
      // the sieves on this half
      const bits = [];
      if (mods.has('push')) { const v = at(S(`grad_norm/layer_${i}/${key}`), step); if (v != null) bits.push(`push ${v.toExponential(1)}`); }
      if (mods.has('move')) { const v = at(S(`update_ratio/layer_${i}/${key}`), step); if (v != null) bits.push(`move ${v.toExponential(1)}`); }
      if (mods.has('heading')) { const v = at(S(`heading/layer_${i}/${key}`), step) ?? at(S(`heading/layer_${i}`), step); if (v != null) bits.push(`heading ${f2(v)}`); }
      if (bits.length) svg += `<text x="${x + 8}" y="${y + h - 6}" class="j-mod">${esc(bits.join(' · '))}</text>`;
      svg += arrow(x + BOX_W - 16, y, w, t);
    }
    // the stars lit in this layer by the step shown, and the layer's push kink
    const notes = [];
    if (here) notes.push(`⇄ ${tp.star ? tp.star.replace(/_/g, ' ') + ' ' : ''}heads ${(tp.heads || []).join(', ')} transplanted from ${tp.from_run || 'another run'}${tp.ln ? ', with their layer norms' : ''}${tp.restored_from_log ? ' (restored from the log)' : ''}`);
    if (whole && !here) notes.push(`⇄ the whole layer transplanted from ${tp.from_run || 'another run'}`);
    if (mods.has('stars')) for (const st of defs.stars || []) {
      for (const [metric, layer, how] of [[st.metric, st.layer, 'one head'], [st.shared_metric, st.shared_layer, 'shared']]) {
        const sr = metric && S(metric); if (!sr) continue;
        const j = sr[1].findIndex((v, n) => v >= st.threshold && sr[0][n] <= step); if (j < 0) continue;
        const where = at(S(layer), sr[0][j]);
        if (where != null && Math.round(where) === i) notes.push(`★ ${st.name} lit at ${sr[0][j]} (${how})`);
      }
    }
    if (mods.has('kink')) { const kk = (opts.kinks || {})[`layer_${i}`]; if (kk && kk.step <= step) notes.push(`◆ push kink at ${kk.step}${kk.tentative ? ' (tentative)' : ''}`); }
    notes.slice(0, 3).forEach((n, j) => { svg += `<text x="${LEFT + 2 * BOX_W + GAP + 12}" y="${y + 14 + j * 15}" class="${n.startsWith('★') ? 'j-star' : n.startsWith('⇄') ? 'j-tp' : 'j-mod'}">${esc(n)}</text>`; });
  }
  svg += '</svg>';
  el.innerHTML = `<div class="j-title">${esc(opts.title || '')}${out != null ? ` · guess ${f2(out)} bits per byte` : ''}</div>`
    + (hasSound ? '' : `<div class="note j-none">no soundings on this sailing: they start with the next ship to sail, so its guesses and arrows are empty; the modules still read its sieves</div>`)
    + svg;
}
