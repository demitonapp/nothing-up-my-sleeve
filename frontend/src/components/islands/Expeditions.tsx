// The Expeditions page (UI.md "Expeditions"), as a typed client island: the queue landing (the waters
// plan, the queue at a glance, every voyage), the expedition cards, one expedition and its five tabs,
// and the table. It replaces dashboard.ts on this page; the dense markup lives in
// scripts/views/expeditions.ts and the charts are imported inside effects only, because the island is
// server-rendered and ECharts touches `document` when it loads.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, MouseEvent as ReactMouseEvent } from 'react';
import { btnCls, cardCls, checkCls, crumbCls, emptyCls, fieldCls, hoverCardCls, rangeCls, selectCls, tabCls, tabsCls, toggleCls } from '@/lib/ui';
import { routePath, useApi, useRoute } from '@/lib/useApi';
import { esc } from '@/lib/format';
import { starHeadline } from '@/scripts/views/helpers';
import {
  censusHtml, deckHtml, expeditionCardsHtml, expeditionName, expeditionOutcomes, expeditionTableHtml, expPill, firstLightFindings, fitHtml, fleetShipsHtml, runsTableHtml,
  inductionVerdict, leversRowsHtml, outcomesRowsHtml, parseExpeditionRoute, queueRowsHtml, readingsTable,
  skyStateOf, sopCardsHtml, tableLogHtml, tableReadingsHtml, planHtml,
} from '@/scripts/views/expeditions';
import type { Expedition, Observation, SeriesMap, SkyViewState, TableExchange } from '@/scripts/views/expeditions';

/** The route, read after mount (as useRoute) and kept current through pushState and popstate. */
function usePath(): [string, (p: string) => void] {
  const route = useRoute();
  const [path, setPath] = useState(route);
  useEffect(() => { setPath(route); }, [route]);
  useEffect(() => {
    const onPop = (): void => setPath(routePath());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  const go = useCallback((p: string) => { history.pushState(null, '', p); setPath(p); }, []);
  return [path, go];
}

const EMPTY = (msg: string): string => `<div class="${emptyCls()}">${msg}</div>`;
// a panel that does not belong to this expedition: the card's flex would otherwise win over [hidden]
const hideStyle = (hide: boolean): { display?: string } | undefined => (hide ? { display: 'none' } : undefined);
const journeyOptsKey = (v: Expedition | null): string => (v ? v.key + '|' + v.runs.filter((r) => !r.set_aside).map((r) => r.run_id).join(',') : '');

/** Compare two SOP versions ("0.0.6" against "0.0.10") as numbers, not as strings. */
const sopVersionCmp = (a: string, b: string): number => {
  const x = String(a || '0').split('.').map((n) => Number(n) || 0);
  const y = String(b || '0').split('.').map((n) => Number(n) || 0);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] || 0) - (y[i] || 0);
    if (d) return d;
  }
  return 0;
};


/** The plan: one column a queued spec, one row a parameter, a row marked where the columns differ. */
const planTableHtml = (d: any): string => {
  const q = (d && d.queue) || [];
  if (!q.length) return '<div class="s">nothing is queued for this expedition yet</div>';
  const fmt = (n: any): string => (typeof n === 'number' ? n.toLocaleString() : n == null ? '–' : String(n));
  const kv = (r: any): string => `${r.kv_heads || r.heads}/${r.heads} KV`;
  const rows: [string, (r: any) => string, string, string?][] = [
    ['ship', (r) => esc(r.ship || '–'), 'the label the run is recorded under'],
    ['class', (r) => esc(r.preset || '–'), 'the size preset: its layer count, width and learning rate'],
    ['attention', kv, 'query heads / KV heads. Fewer KV heads than queries is grouped-query attention: each key and value is shared by a group of queries'],
    ['layers', (r) => fmt(r.layers), 'how many transformer blocks deep the model is'],
    ['query heads', (r) => fmt(r.heads), 'how many attention heads per layer carry the queries'],
    ['parameters', (r) => fmt(r.params?.total), 'every learned weight: embeddings, attention and MLP, summed'],
    ['non-embedding', (r) => fmt(r.params?.non_embedding), 'the weights that do the computing, without the token table'],
    ['learning rate', (r) => fmt(r.lr), 'the peak step size, reached at the end of warm-up'],
    ['warm-up', (r) => fmt(r.warmup), 'steps over which the learning rate climbs to its peak'],
    ['batch tokens', (r) => fmt(r.batch_tokens), 'how many tokens one step reads'],
    ['passes', (r) => fmt(r.passes), 'how many times the corpus is read'],
    ['books', (r) => esc(r.books || '–'), 'the corpus list the voyage reads'],
    ['pinned', (r) => (r.pinned || []).join(', ') || '–', 'the cards the scaffold pulls, in head order: these are taught, not left to the corpus'],
    ['tokeniser', (r) => `${fmtOr(r.tokeniser?.kind)} · ${fmtOr(r.tokeniser?.vocab)} pieces`, 'how text is cut into pieces: the piece count sets the embedding table, which is most of a small model\'s parameters'],
    ['control tokens', (r) => ((r.tokeniser?.symbols || []) as string[]).length
        ? (r.tokeniser.symbols as string[]).map((x) => `<span class="sym">${esc(x)}</span>`).join('')
        : '<span class="s">none declared</span>',
      'single pieces for structure rather than content. A declared token the corpus never uses receives no gradient: it must appear in the text, not only in the table.',
      `<div class="symdoc"><div class="k">the ten, and what each marks</div><dl>${TOKEN_DOCS.map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join('')}</dl></div>`],
    ['trained on', (r) => `<span class="mono s">${esc(r.tokeniser?.train_on || '–')}</span>`, 'the corpus the tokeniser itself was fitted on, which fixes the pieces before training starts'],
  ];
  const head = `<tr><th>parameter</th>${q.map((r: any) => `<th>${esc(r.name)}</th>`).join('')}</tr>`;
  const body = rows.map(([label, f, why, extra]) => {
    const vals = q.map(f);
    const differs = new Set(vals).size > 1;
    const body = extra && extra.includes('<') && label === 'control tokens'
      ? extra
      : esc(why);
    return `<tr class="${differs ? 'plandiff' : ''}"><td class="s"><span class="plabel">${esc(label)}</span><details class="hint"><summary>?</summary><div class="hintbody">${body}</div></details></td>${vals.map((v: string) => `<td>${v}</td>`).join('')}</tr>`;
  }).join('');
  return `<div class="scroll"><table id="plantable"><thead>${head}</thead><tbody>${body}</tbody></table></div>
    <div class="s">Rows marked are where the arms differ; identical rows are what makes the comparison a test. Click a <b>?</b> for what the parameter means.</div>`;
};

/** The ⓘ beside the at-sea card's tokeniser line: which alternatives to test, and why (9 November). */
const TOKENISER_HELP = `<span class="info" tabindex="0">ⓘ<span class="pop ${hoverCardCls}"><b>Tokenisers to test</b><br>
<b>SPM Unigram 2048</b> — same SentencePiece framework and byte fallback; a probabilistic segmentation often gives a
better likelihood at a 2048-piece vocabulary. The cheapest meaningful A/B: the same 592 Ogden books, the same vocab,
the same clean, held-out BPB and tokens/book.<br>
<b>SPM BPE 4096</b> — finer tokens, cheaper to read a page; worth testing on the 9m and up, where the doubled embedding
is a few per cent (21m 3.5% → 7%, 50m 1.5% → 3%). On the 300k it is 31% → 62%, which is a different model, not a
tokeniser swap.<br>
<b>Byte-level BPE 2048</b> — the open-source standard (GPT/Llama 3/Qwen); at 2048 its 256 byte pieces plus regex
pre-tokenisation leave little for Ogden-English merges, so expect no win — one control run is enough to prove it.<br>
<b>SPM BPE 1024</b> — frees about 16% of the 300k's budget and is worth a look only at that end of the ladder; it is
coarser, and its BPB/chaining are not comparable with the 2048/4096 runs.<br>
<b>Not</b> WordPiece (UNK, lossy normalisation), character-level (too long) or word-level (OOV).<br>
<b>Measure</b>: held-out BPB, tokens/book, byte-fallback rate and embedding parameters, then the same model and seed on
the cards. Record the tokeniser id: it changes the BPB scale, so cross-tokeniser chaining comparisons are unsafe.</span></span>`;

/** The ⓘ beside the at-sea card's attention line: heads, KV heads, layers, and why these settings. */
const ATTENTION_HELP = `<span class="info" tabindex="0">ⓘ<span class="pop ${hoverCardCls}"><b>Heads, KV and layers</b><br>
<b>Heads</b> — each layer splits its width into parallel attention heads; one head is one relation the model can learn
(copy the previous word, attend to a delimiter, carry a comparison). They are the unit the star chart pins, so too few
heads leaves the cards nowhere to sit, and too many makes each head too narrow to hold a circuit. The presets keep the
head width in the 20–64 band: 300k 48/2 = 24, 21m 192/8 = 24, 350m 1024/16 = 64.<br>
<b>KV</b> — the key/value heads. Equal to the query heads is ordinary multi-head attention; fewer is grouped-query
attention, where several query heads share one K/V head. Fewer KV heads shrink the KV cache and the attention memory
and speed up decoding, at the cost of less diversity in keys and values. The <b>300k@v0.0.6-gqa</b> arm is the 2:1
test — 2 query heads, 1 KV head — to see whether the cards survive at the smallest scale.<br>
<b>Layers</b> — depth: each layer composes the last, so more layers buy more sequential relations and more slots in
the star chart. Depth is traded against width at a fixed budget: the 50m is deep and narrow (36 layers × 304), the
100m wide and shallow (12 × 768). The 300k has 6 layers because that is all its budget allows; the 21m has 24 to
hold the chained cards.<br>
<b>Why these settings</b> — the SOP's shape table: heads divide the width, the head width stays in the 20–64 band,
depth scales with the parameter target, and the 1-KV arm is the one deliberate departure (GQA at 300k) testing the
memory/speed trade without losing the cards. The numbers on the card are this run's actual values.</span></span>`;

/** The ten control tokens, in the order the tokeniser declares them. */
const TOKEN_DOCS: [string, string][] = [
  ['<bos>', 'beginning of sequence: the document starts here, so nothing precedes it'],
  ['<eos>', 'end of sequence: the document is over, and generation stops'],
  ['<pad>', 'padding: fills a batch to a common length, and is masked out'],
  ['<unk>', 'unknown: a piece with no entry in the vocabulary (rare with byte fallback)'],
  ['<sep>', 'separator: divides sections or turns without ending the sequence'],
  ['<premise>', 'opens the statement a conclusion rests on'],
  ['<conclusion>', 'opens the step that follows from the premise'],
  ['<question>', 'opens a question'],
  ['<answer>', 'opens the answer to it'],
  ['<end>', 'closes the turn (the answer), as distinct from <eos>, which closes the document'],
];

const fmtOr = (v: any): string => (v == null || v === '' ? '–' : esc(String(v)));


/** The arms at sea: control first, then each lever with its step, loss and difference from the control. */
const armsTableHtml = (d: any): string => {
  const arms = (d && d.arms) || [];
  if (!arms.length) return '<div class="s">nothing of this expedition is at sea</div>';
  const control = arms.find((a: any) => !/-/.test(String(a.name).split('@')[1] || '')) || arms[0];
  const fmt = (n: any, digits = 2): string => (n == null ? '–' : Number(n).toFixed(digits));
  const rows = arms.map((a: any) => {
    const lever = String(a.name).split('@')[1] || '';
    const isControl = a === control;
    const dl = a.loss != null && control.loss != null ? a.loss - control.loss : null;
    return `<tr class="${isControl ? 'armcontrol' : ''}">
      <td><b>${esc(a.name)}</b></td>
      <td class="s">${esc(a.preset || '')}${a.kv_heads ? ` · ${a.kv_heads} KV` : ''}${a.pins ? ` · ${a.pins} pins` : ''}</td>
      <td>${a.step ?? '–'}</td>
      <td>${fmt(a.loss, 3)}</td>
      <td>${fmt(a.bpb, 3)}</td>
      <td>${dl == null ? '–' : (dl > 0 ? '+' : '') + fmt(dl, 3)}</td>
      <td>${a.chaining == null ? '–' : (a.chaining > 0 ? '+' : '') + fmt(a.chaining, 3)}</td>
    </tr>`;
  }).join('');
  return `<div class="scroll"><table id="armstable"><thead><tr>
      <th>arm</th><th>shape</th><th>step</th><th>loss</th><th>bpb</th><th>Δ loss vs control</th><th>chaining</th>
    </tr></thead><tbody>${rows}</tbody></table></div>
    <div class="s">The control is the arm with no suffix; a negative Δ is better. bpb and chaining appear when the first reading lands.</div>`;
};


/** Where each arm's pins sit: one strip per arm, a cell per layer, the cards that layer teaches. */
const pinsHtml = (d: any): string => {
  const arms = (d && d.arms) || [];
  if (!arms.length) return '<div class="s">nothing at sea</div>';
  const lanes = arms.map((a: any) => {
    const layers = a.layers || 0;
    const heads = a.heads_per_layer || 0;
    const by: Record<number, string[]> = {};
    (a.pinned || []).forEach((h: any) => { (by[h.layer] || (by[h.layer] = [])).push(h.card); });
    const cells = Array.from({ length: layers }, (_, L) => {
      const cards = by[L] || [];
      return `<span class="pincell${cards.length ? ' used' : ''}" title="layer ${L}: ${cards.length ? esc(cards.join(', ')) : 'free'}">${cards.length ? cards.map((c: string) => `<i>${esc(c)}</i>`).join('') : ''}<b>L${L}</b></span>`;
    }).join('');
    return `<div class="pinrow"><span class="pinname">${esc(a.name)}</span><span class="pinstrip">${cells}</span>
      <span class="s">${(a.pinned || []).length} of ${layers * heads} slots${(a.riddles || []).length ? ` · riddle ${esc((a.riddles || []).join(', '))}` : ''}</span></div>`;
  }).join('');
  return `<div class="pins">${lanes}</div><div class="s">A cell is one layer; each card in it is a head the scaffold teaches. Layers with nothing in them are left to the corpus.</div>`;
};


/** One card an arm: its embedding makeup, its corpus, its attention, its pins, and its readings against
 *  the control — everything about that voyage in one place, live (9 November). */
const armCardsHtml = (d: any): string => {
  const arms = (d && d.arms) || [];
  if (!arms.length) return '<div class="s">nothing of this expedition is at sea</div>';
  const control = arms.find((a: any) => !/-/.test(String(a.name).split('@')[1] || '')) || arms[0];
  const fmt = (n: any, digits = 3): string => (n == null ? '–' : Number(n).toFixed(digits));
  const cards = arms.map((a: any) => {
    const t = a.tokeniser || {};
    const dl = a.loss != null && control.loss != null ? a.loss - control.loss : null;
    const isControl = a === control;
    const sym = (t.symbols || []) as string[];
    const layers = a.layers || 0, heads = a.heads_per_layer || 0;
    const by: Record<number, string[]> = {};
    (a.pinned || []).forEach((h: any) => { (by[h.layer] || (by[h.layer] = [])).push(h.card); });
    const strip = Array.from({ length: layers }, (_, L) => {
      const cs = by[L] || [];
      return `<span class="pincell${cs.length ? ' used' : ''}" title="layer ${L}: ${cs.length ? esc(cs.join(', ')) : 'free'}">${cs.map((c: string) => `<i>${esc(c)}</i>`).join('')}<b>L${L}</b></span>`;
    }).join('');
    const role = isControl ? 'control' : (String(a.name).split('@')[1] || '').replace(/^v[0-9.]+-?/, '') || 'arm';
    const total = a.schedule?.total;
    const pct = total && a.step ? Math.round((a.step / total) * 100) : null;
    return `<article class="armcard${isControl ? ' armcontrol' : ''}" data-deck-run="${esc(a.run_id || '')}" title="show this voyage in the observation deck">
      <header><b>${esc(a.name)}</b><span class="pill">${esc(role)}</span></header>
      <div class="armprogress">${a.step != null ? `step ${a.step.toLocaleString()}${total ? ` of ${total.toLocaleString()}` : ''}${pct != null ? ` · ${pct}% complete` : ''}` : 'not started'}</div>
      <div class="armrow"><span class="k">embeddings${TOKENISER_HELP}</span><span>${esc(t.kind || '')} · ${t.vocab ?? '–'} pieces${sym.length ? ` · ${sym.map((x: string) => `<span class="sym">${esc(x)}</span>`).join('')}` : ''}</span></div>
      <div class="armrow"><span class="k">reads</span><span>${(() => {
        const c = a.content || {};
        const name = c.version ? esc(String(c.version).replace(/^ogden-/, 'Ogden ')) : esc(a.recipe || '–');
        const bits = [name, a.passes ? `×${a.passes}` : '', esc(a.clean || 'raw')].filter(Boolean).join(' · ');
        const why = c.stamped
          ? `${c.books ?? '?'} books${c.marked ? `, ${c.marked} with turns marked` : ''} · transform: ${c.transform}${c.about ? ` — ${c.about}` : ''}`
          : `${c.books ?? '?'} books · no stamped transform (read through the cleaner \`${a.clean || 'raw'}\`)`;
        return `<span class="s">${bits}</span> <details class="hint"><summary>?</summary><div class="hintbody">${esc(why)}</div></details>`;
      })()}</span></div>
      <div class="armrow"><span class="k">attention${ATTENTION_HELP}</span><span>${heads} heads${a.kv_heads ? ` · ${a.kv_heads} KV` : ''} · ${layers} layers</span></div>
      <div class="armrow"><span class="k">pins</span><span class="pinstrip">${strip}</span></div>
      <div class="armrow"><span class="k">schedule</span><span>${scheduleLine(a.schedule)}</span></div>
      <div class="armrow"><span class="k">readings</span><span>loss ${fmt(a.loss)}${dl != null ? ` (${dl > 0 ? '+' : ''}${fmt(dl)})` : ''} · bpb ${fmt(a.bpb)}${a.chaining != null ? ` · chaining ${a.chaining > 0 ? '+' : ''}${fmt(a.chaining)}` : ''}</span></div>
      <div class="armrow"><span class="k">shapes</span><span>parts of speech ${fmt(a.shapes?.upos, 3)} · keyed words ${fmt(a.shapes?.keyed, 3)}</span></div>
      <div class="armrow"><span class="k">cards</span><span class="cardreadings">${(() => {
        const cs = a.cards_summary || {};
        if (!cs.total) return '<span class="s">nothing pinned</span>';
        const pair = (e: any): string => `${e.lit}/${e.n}`;
        const stages = Object.entries(cs.by_stage || {}).map(([k, e]: [string, any]) => `${esc(k)} ${pair(e)}`).join(' · ');
        const suits = Object.entries(cs.by_suit || {}).map(([k, e]: [string, any]) => `${esc(k)} ${pair(e)}`).join(' · ');
        const names = (a.cards || []).map((c: any) => `${c.card} ${c.now != null && c.mark != null && c.now >= c.mark ? '✓' : '·'} ${fmt(c.now, 2)}/${fmt(c.mark, 2)}`);
        return `<span class="holding">${stages}${suits ? ` <span class="s">| ${suits}</span>` : ''}</span>
          <span class="s">${cs.lit} of ${cs.total} lit</span>
          <details class="hint"><summary>?</summary><div class="hintbody"><b>${cs.total} heads pinned</b><br>${names.map((x: string) => esc(x)).join('<br>')}</div></details>`;
      })()}</span></div>
    </article>`;
  }).join('');
  return `<div class="armcards">${cards}</div>
    <div class="s">Each card is one voyage as it stands: what its pieces are, what it reads, how its attention is grouped, which heads are taught and where. Δ is against the control; a negative loss difference is better.</div>`;
};


/** The schedule a voyage runs, as a bar broken into its stages, with a marker where the ship is now. */
const scheduleLine = (sc: any): string => {
  if (!sc || sc.stage == null) return '<span class="s">–</span>';
  const fmt = (n: any, digits = 2): string => (n == null ? '–' : Number(n).toFixed(digits));
  const total = sc.total || null;
  const pct = (x: any): number => Math.max(0, Math.min(1, Number(x)));
  const at = (x: any): string => (total ? `step ${Math.round(pct(x) * total).toLocaleString()}` : `${Math.round(pct(x) * 100)}%`);
  const hold = sc.hold != null ? pct(sc.hold) : 0;
  const fade = sc.fade != null ? pct(sc.fade) : 1;
  const rel = sc.release != null ? pct(sc.release) : null;
  type Ph = { cls: string; name: string; from: number; to: number; about: string };
  const phases: Ph[] = [];
  if (hold > 0) phases.push({ cls: 'hold', name: 'hold', from: 0, to: hold,
    about: 'the pin at full weight: the scaffold teaches its heads and they read it' });
  if (rel != null) {
    phases.push({ cls: 'release', name: 'release', from: hold, to: rel,
      about: 'the pull handed to the weights: from here the scaffold is off and the cards must stand alone' });
    phases.push({ cls: 'content', name: 'content', from: rel, to: 1,
      about: 'by heart: no pull at all, the model reading its corpus with nothing taught' });
  } else if (fade > hold) {
    phases.push({ cls: 'fade', name: 'fade', from: hold, to: fade,
      about: 'the pull easing out: the scaffold weakens step by step, so a card that only read because of the pin starts to show it' });
    phases.push({ cls: 'content', name: 'content', from: fade, to: 1,
      about: 'by heart: no pull at all, the model reading its corpus with nothing taught' });
  }
  const segs = phases.map((ph) => `<span class="seg ${ph.cls}" style="width:${Math.max(0.5, (ph.to - ph.from) * 100)}%" title="${esc(`${ph.name} — ${at(ph.from)} to ${at(ph.to)}. ${ph.about}`)}"><b>${esc(ph.name)}</b></span>`).join('');
  // per-card schedules (10 November): a voyage can release some cards and fade others; the top-level bar
  // shows the scaffold's schedule, these show what each group of cards actually runs
  const groups = Array.isArray(sc.groups) && sc.groups.length > 1 ? sc.groups : [];
  const gbars = groups.map((g: any) => {
    const gh = g.hold != null ? pct(g.hold) : 0;
    const gr = g.kind === 'release' ? pct(g.share) : null;
    const gf = g.kind === 'release' ? gh : Math.max(gh, g.fade != null ? pct(g.fade) : 1);
    const parts: string[] = [];
    if (gh > 0) parts.push(`<span class="seg hold" style="width:${gh * 100}%"></span>`);
    if (gr != null) {
      parts.push(`<span class="seg release" style="width:${Math.max(0.8, (gr - gh) * 100)}%"></span>`);
      parts.push(`<span class="seg content" style="width:${Math.max(0.5, (1 - gr) * 100)}%"></span>`);
    } else {
      parts.push(`<span class="seg fade" style="width:${Math.max(0.5, (gf - gh) * 100)}%"></span>`);
      if (gf < 1) parts.push(`<span class="seg content" style="width:${(1 - gf) * 100}%"></span>`);
    }
    const n = g.pins ?? (g.cards || []).length;
    const label = g.kind === 'release'
      ? `released at ${Math.round(pct(g.share) * 100)}% (${at(g.share)})`
      : `fade to ${Math.round(pct(g.share) * 100)}% (${at(g.share)})`;
    return `<div class="g" title="${esc((g.cards || []).join(', '))}"><span class="s">${n} pin${n === 1 ? '' : 's'}</span><div class="schedbar">${parts.join('')}</div><span class="s">${esc(label)}</span></div>`;
  }).join('');
  // the phase names are written in the bar itself (9 November): no separate key
  const now = sc.step && total ? Math.min(100, (Number(sc.step) / Number(total)) * 100) : null;
  const w = sc.weight == null ? null : Number(sc.weight);
  const detail = (sc.phases_detail || []).map((ph: any) => {
    const kept = (ph.cards || []).map((c: any) => `${esc(c.card)} ${c.kept == null ? '–' : `${Math.round(c.kept)}%`}`).join(' · ');
    const loss = ph.loss_start != null || ph.loss_end != null ? `loss ${fmt(ph.loss_start, 3)} → ${fmt(ph.loss_end, 3)}` : '';
    return `<tr><td><b>${esc(ph.name)}</b></td><td class="s">${ph.from.toLocaleString()}–${ph.to.toLocaleString()}</td><td class="s">${loss}</td><td class="s">${kept || '–'}</td></tr>`;
  }).join('');
  return `<details class="sched">
    <summary><div class="schedbar">${segs}${now != null ? `<i class="marker" style="left:${now}%"></i>` : ''}</div>
      <div class="schedcap"><b class="stagechip">${esc(sc.stage)}</b> <span class="s">${w != null ? `weight ${w.toFixed(2)}` : ''}${total && sc.step ? ` · step ${Number(sc.step).toLocaleString()} of ${Number(total).toLocaleString()}` : ''}</span> <span class="s openhint">expand for each phase</span></div>
      ${gbars ? `<div class="schedgroups">${gbars}</div>` : ''}
    </summary>
    <div class="scheddetail"><table><thead><tr><th>phase</th><th>steps</th><th>loss across it</th><th>cards kept</th></tr></thead><tbody>${detail || '<tr><td colspan="4" class="s">no readings yet</td></tr>'}</tbody></table>
      <div class="s">Kept is the card's reading at the phase's end as a share of its reading at the start: how much of it survived that phase. A hold or fade that holds reads near 100%; one that doesn't shows which card fell.</div></div>
  </details>`;
};
export default function Expeditions() {
  const [path, go] = usePath();
  const route = parseExpeditionRoute(path);
  const isOverview = route.kind === 'overview';
  const isQueue = route.kind === 'queue';
  const isList = route.kind === 'list';
  const isVoyage = route.kind === 'voyage';
  const isTable = route.kind === 'table';
  const onPage = isQueue || isList || isVoyage || isTable;

  // one route for the whole page, one poll for the expeditions (the cards and one expedition both read it)
  const expsApi = useApi<Expedition[]>(onPage ? '/api/expeditions' : null, 60000);
  const ladderApi = useApi<any>(onPage ? '/api/ladder' : null, 300000);
  // the overview tab needs this payload too, or it sits on 'reading the expeditions…' for ever
  const ovApi = useApi<any>(isOverview || isQueue || isList || isVoyage ? '/api/expeditions/overview' : null, 15000);
  const queueApi = useApi<any>(isQueue ? '/api/queue' : null, 15000);
  const exps = expsApi.data || [];
  const rungs = useMemo(() => (Array.isArray(ladderApi.data?.rungs) ? ladderApi.data.rungs : []), [ladderApi.data]);
  const states = useMemo(() => Object.fromEntries((ovApi.data?.expeditions || []).map((e: any) => [e.key, e.status])) as Record<string, string>, [ovApi.data]);
  // The standards split in two: the one in play (at sea, and anything newer than it) is the Overview's
  // subject; the ones whose voyages are home sit with every expedition on Plans (10 November, Justin:
  // "move ogden from here to the plans tab").
  const [liveSops, pastSops] = useMemo(() => {
    const all: any[] = (ovApi.data?.sops || []) as any[];
    if (!all.length) return [[], []] as [any[], any[]];
    const atSea = all.filter((e) => Number(e.at_sea) > 0);
    const floor = (atSea.length ? atSea : all).map((e) => String(e.version)).sort(sopVersionCmp).pop() as string;
    const live = all.filter((e) => Number(e.at_sea) > 0 || sopVersionCmp(String(e.version), floor) >= 0);
    const past = all.filter((e) => !live.includes(e)).sort((a, b) => sopVersionCmp(String(b.version), String(a.version)));
    return [live, past] as [any[], any[]];
  }, [ovApi.data]);
  const v = isVoyage && route.key ? exps.find((x) => x.key === route.key) || null : null;

  const detailApi = useApi<any>(isVoyage && route.key ? `/api/expedition?key=${encodeURIComponent(route.key)}` : null, 60000);
  const obsApi = useApi<Observation>(isVoyage && route.key ? `/api/observation?expedition=${encodeURIComponent(route.key)}` : null, 10000);
  const koApi = useApi<any>(isVoyage && v?.key === 'knockout' ? '/api/knockout' : null, 120000);
  const censusApi = useApi<any>(isVoyage && v?.key === 'card_census' ? '/api/census' : null, 60000);

  // its readings (Findings): every voyage on each measure the expedition is judged by
  const outs = useMemo(() => (v ? expeditionOutcomes(v) : []), [v]);
  const readingsRuns = useMemo(() => (v ? v.runs.filter((r) => !r.set_aside && r.name).slice(-40).map((r) => r.name) : []), [v]);
  const readingsUrl = isVoyage && v && outs.length && readingsRuns.length
    ? `/api/series?runs=${encodeURIComponent(readingsRuns.join(','))}&metrics=${encodeURIComponent(outs.map((o) => o.metric).join(','))}`
    : null;
  const readingsApi = useApi<SeriesMap>(readingsUrl, 60000);

  // the induction head's three charts
  const indRuns = useMemo(() => (v && v.key === 'induction' ? v.runs.filter((r) => r.name).map((r) => r.name) : []), [v]);
  const indUrl = indRuns.length
    ? `/api/series?runs=${encodeURIComponent(indRuns.join(','))}&metrics=${encodeURIComponent('nevermore/natural_max_score,stars/previous_word/max_score,nevermore/natural_copy_gain')}`
    : null;
  const indApi = useApi<SeriesMap>(isVoyage && v?.key === 'induction' ? indUrl : null, 60000);

  // the climb (two_facts)
  const climbRuns = useMemo(() => (v && v.key === 'two_facts' ? v.runs.filter((r) => r.run_id).map((r) => r.run_id) : []), [v]);
  const climbApi = useApi<any>(climbRuns.length ? `/api/climb?runs=${encodeURIComponent(climbRuns.join(','))}` : null, 60000);
  const internalApi = useApi<any>(isVoyage && v?.key === 'two_facts' ? '/api/leaderboard/internal' : null, 300000);

  // the Inside tab applies only when one of its voyages recorded soundings; shown while unknown
  const soundingRuns = useMemo(() => (v ? v.runs.filter((r) => !r.set_aside).map((r) => r.name).slice(-40) : []), [v]);
  const soundingUrl = isVoyage && soundingRuns.length
    ? `/api/series?runs=${encodeURIComponent(soundingRuns.join(','))}&metrics=${encodeURIComponent('soundings/layer_0/bpb')}`
    : null;
  const soundingsApi = useApi<SeriesMap>(soundingUrl, 600000);
  const insideOk = !isVoyage ? true : !soundingRuns.length ? false : !soundingsApi.data ? true : Object.values(soundingsApi.data).some((m) => Object.keys(m).length > 0);

  const tabOk = useMemo<Record<string, boolean>>(() => {
    if (!v) return {} as Record<string, boolean>;
    const st = states[v.key] || '';
    return {
      overview: true, findings: true,
      'at-sea': ['at sea', 'under way', 'paused', 'awaiting orders'].includes(st) || (!st && v.status === 'running') || v.runs.some((r) => r.status === 'running'),
      fleet: !!(v.runs.length || (v.ships || []).length),
      inside: insideOk,
    };
  }, [v, states, insideOk]);
  const expTab = isVoyage && tabOk[route.tab] === false ? 'overview' : route.tab;
  // the plan: every launch still queued for this expedition, with what makes its arms differ
  const planApi = useApi<any>(isVoyage && expTab === 'plan' && route.key ? '/api/expedition_plan?key=' + encodeURIComponent(route.key) : null, 60000);
  // the voyages at sea, side by side, as they run (9 November)
  const seaApi = useApi<any>(isVoyage && expTab === 'at-sea' && route.key ? '/api/at_sea?expedition=' + encodeURIComponent(route.key) : null, 20000);
  useEffect(() => {
    if (isVoyage && route.key && tabOk[route.tab] === false) history.replaceState(null, '', `/expeditions/${route.key}`);
  }, [isVoyage, route.key, route.tab, tabOk]);

  // the queue's subtab survives a trip to the cards and back
  const [qview, setQview] = useState<'glance' | 'every'>(route.qview);
  useEffect(() => { if (isQueue) setQview(route.qview); }, [isQueue, route.qview]);

  // ---- the table's state (the #table section)
  const tableKey = isTable ? route.key || 'table_talk' : null;
  const tableExp = tableKey ? exps.find((x) => x.key === tableKey) || null : null;
  const runsApi = useApi<any[]>(isTable ? '/api/runs' : null, 60000);
  const [tableRun, setTableRun] = useState<string | null>(null);
  const [tableLog, setTableLog] = useState<TableExchange[]>([]);
  const [tablePending, setTablePending] = useState<string | null>(null);
  const [tableStatus, setTableStatus] = useState('');
  const [tableReadings, setTableReadings] = useState('ask something to see them');
  const [tableQ, setTableQ] = useState('');
  const [tableTemp, setTableTemp] = useState(0.8);
  const [tableMax, setTableMax] = useState('200');
  const [tableSeed, setTableSeed] = useState('');
  const [tableBusy, setTableBusy] = useState(false);
  const [tableLocked, setTableLocked] = useState(false);

  const tableOptions = useMemo(() => {
    const own = tableExp ? tableExp.runs.filter((r) => r.status === 'finished' || r.status === 'running') : [];
    const others = (runsApi.data || []).filter((r: any) => r.status === 'finished' && r.name && !r.name.startsWith('smoke') && !own.some((o) => o.run_id === r.run_id)).reverse();
    const label = (r: any): string => `${r.ship || r.name} · ${r.name}${r.preset ? ` (${r.preset})` : ''}`;
    return { own, others, label };
  }, [tableExp, runsApi.data]);
  const tableOptionValues = useMemo(() => [...tableOptions.own.map((r) => r.name), ...tableOptions.others.map((r: any) => r.name)], [tableOptions]);

  useEffect(() => {
    if (!isTable) return;
    if (!tableRun || !tableOptionValues.includes(tableRun)) setTableRun(tableOptionValues[0] ?? null);
  }, [isTable, tableRun, tableOptionValues]);

  useEffect(() => {
    if (!isTable || !tableRun) { setTableLog([]); return; }
    let live = true;
    (async () => {
      try {
        const r = await fetch('/api/table/transcript?run=' + encodeURIComponent(tableRun));
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || r.statusText);
        if (!live) return;
        setTableLog((Array.isArray(d) ? d : []).map((x: any) => ({ q: x.question, a: x.answer, meta: x })));
        setTableStatus('');
        setTableLocked(false);
      } catch (e) {
        if (!live) return;
        setTableLog([]);
        const notBuilt = /not built yet/.test(String((e as Error).message));
        setTableStatus(notBuilt ? "The table isn't open yet: the ship's side (thorp.table) is still being built. The page is ready for it." : 'could not load the transcript: ' + (e as Error).message);
        setTableLocked(notBuilt);
      }
    })();
    return () => { live = false; };
  }, [isTable, tableRun]);

  useEffect(() => {
    const el = document.getElementById('tablelog');
    if (el) el.scrollTop = el.scrollHeight;
  }, [tableLog, tablePending]);

  const askTable = async (): Promise<void> => {
    const question = tableQ.trim();
    if (tableBusy || !question || !tableRun) return;
    setTableBusy(true); setTableQ(''); setTablePending(question); setTableStatus('');
    const seed = tableSeed.trim();
    const temperature = tableTemp;
    try {
      const r = await fetch('/api/table/reply', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run: tableRun, question, history: tableLog.slice(-8).map((x) => ({ q: x.q, a: x.a })), temperature, max_tokens: +tableMax, seed: seed === '' ? null : seed }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || r.statusText);
      setTableLog((prev) => [...prev, { q: question, a: d.answer, meta: { ...d, temperature, seed: seed === '' ? null : seed } }]);
      setTableReadings(tableReadingsHtml(d.readings));
      if (d.prompt_tokens != null) setTableStatus(`the ship read ${d.prompt_tokens} tokens of the conversation (step ${d.step ?? '–'})`);
    } catch (e) {
      setTableStatus(/not built yet/.test(String((e as Error).message)) ? "The table isn't open yet: the ship's side (thorp.table) is still being built." : 'no answer: ' + (e as Error).message);
      setTableQ(question);
    } finally {
      setTableBusy(false); setTablePending(null);
    }
  };

  // ---- the deck's play state (one find at a time, or one reading at a time) and its tabs
  const [sky, setSky] = useState<Record<string, SkyViewState>>({});
  const skyRef = useRef<Record<string, SkyViewState>>({});
  useEffect(() => { skyRef.current = sky; }, [sky]);
  const [playing, setPlaying] = useState<{ run: string; kind: 'sky' | 'nv' } | null>(null);
  // the one voyage the observation deck shows (clicking a voyage or a chip picks it)
  const [deckRun, setDeckRun] = useState<string | null>(null);
  const obs = obsApi.data;
  useEffect(() => { setDeckRun(null); }, [route.key]);
  useEffect(() => {
    if (deckRun && obs && !(obs.at_sea || []).some((r) => r.run_id === deckRun)) setDeckRun(null);
  }, [obs, deckRun]);
  useEffect(() => {
    if (!playing || !obs) return;
    const run = (obs.at_sea || []).find((r) => r.run_id === playing.run);
    const n = playing.kind === 'sky' ? ((run?.finds || []) as any[]).length : ((((run?.heads || {}) as any).steps || []) as any[]).length;
    if (!n) { setPlaying(null); return; }
    const timer = window.setInterval(() => {
      const st = skyStateOf(skyRef.current[playing.run]);
      if (playing.kind === 'sky') {
        const next = st.k == null ? 0 : st.k + 1;
        if (next >= n) { setPlaying(null); setSky((p) => ({ ...p, [playing.run]: { ...st, k: null } })); return; }
        setSky((p) => ({ ...p, [playing.run]: { ...st, k: next } }));
      } else {
        const next = st.i == null ? 0 : st.i + 1;
        if (next >= n - 1) { setPlaying(null); setSky((p) => ({ ...p, [playing.run]: { ...st, i: null } })); return; }
        setSky((p) => ({ ...p, [playing.run]: { ...st, i: next } }));
      }
    }, playing.kind === 'sky' ? 900 : 700);
    return () => window.clearInterval(timer);
  }, [playing, obs]);
  const patchSky = (rid: string, f: (s: SkyViewState) => SkyViewState): void =>
    setSky((prev) => ({ ...prev, [rid]: f(skyStateOf(prev[rid])) }));

  const onDeckClick = (e: ReactMouseEvent): void => {
    const t = e.target as HTMLElement;
    const pick = t.closest('[data-deck-run]') as HTMLElement | null;
    if (pick && !t.closest('a') && !t.closest('.sky[data-run]') && !t.closest('.obsship')) {
      const rid = pick.dataset.deckRun;
      if (rid) {
        setDeckRun(rid);
        setPlaying(null);
        document.getElementById('obspanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
    }
    const box = t.closest('.sky[data-run]') as HTMLElement | null;
    if (!box) return;
    const rid = box.dataset.run;
    if (!rid) return;
    const run = (obs?.at_sea || []).find((r) => r.run_id === rid);
    const viewTab = t.closest('[data-skyview]') as HTMLElement | null;
    if (viewTab) { setPlaying(null); patchSky(rid, (s) => ({ ...s, view: viewTab.dataset.skyview === 'all' ? 'all' : 'nevermore' })); return; }
    const nvBtn = t.closest('[data-nv]') as HTMLElement | null;
    if (nvBtn) {
      const steps = ((run?.heads || {}) as any).steps || [];
      if (nvBtn.dataset.nv === 'live') { setPlaying(null); patchSky(rid, (s) => ({ ...s, i: null })); return; }
      if (nvBtn.dataset.nv === 'play') {
        if (playing && playing.run === rid && playing.kind === 'nv') { setPlaying(null); return; }
        patchSky(rid, (s) => ({ ...s, i: s.i == null || s.i >= steps.length - 1 ? 0 : s.i }));
        setPlaying({ run: rid, kind: 'nv' });
      }
      return;
    }
    const skyBtn = t.closest('[data-sky], .skychip') as HTMLElement | null;
    if (skyBtn) {
      const finds = (run?.finds || []) as any[];
      if (skyBtn.dataset.sky === 'live') { setPlaying(null); patchSky(rid, (s) => ({ ...s, k: null })); return; }
      if (skyBtn.dataset.k) { setPlaying(null); patchSky(rid, (s) => ({ ...s, k: +skyBtn.dataset.k! })); return; }
      if (skyBtn.dataset.sky === 'play') {
        if (playing && playing.run === rid && playing.kind === 'sky') { setPlaying(null); return; }
        patchSky(rid, (s) => ({ ...s, k: s.k == null || s.k >= finds.length ? 0 : s.k }));
        setPlaying({ run: rid, kind: 'sky' });
      }
    }
  };
  const onDeckInput = (e: FormEvent): void => {
    const t = e.target as HTMLInputElement;
    const box = t.closest('.sky[data-run]') as HTMLElement | null;
    const rid = box?.dataset.run;
    if (!rid) return;
    const run = (obs?.at_sea || []).find((r) => r.run_id === rid);
    const val = +t.value;
    if (t.classList.contains('skyrange')) { setPlaying(null); patchSky(rid, (s) => ({ ...s, k: val >= ((run?.finds || []) as any[]).length ? null : val })); }
    else if (t.classList.contains('nvrange')) { setPlaying(null); patchSky(rid, (s) => ({ ...s, i: val >= (((run?.heads || {}) as any).steps || []).length - 1 ? null : val })); }
    // the redraw replaces the range (as the old skyRedraw did): put the focus back on it
    const cls = t.classList.contains('skyrange') ? '.skyrange' : '.nvrange';
    requestAnimationFrame(() => {
      try { document.querySelector<HTMLInputElement>(`.sky[data-run="${CSS.escape(rid)}"] ${cls}`)?.focus(); } catch { /* an id CSS cannot escape */ }
    });
  };

  // ---- the census rows and the findings instruments
  const [censusOpen, setCensusOpen] = useState<Set<string>>(new Set());
  const census = censusApi.data ? censusHtml(censusApi.data, censusOpen, rungs) : EMPTY('reading the census…');
  const onCensusClick = (e: ReactMouseEvent): void => {
    const tr = (e.target as HTMLElement).closest('tr.cenrow') as HTMLElement | null;
    if (!tr || (e.target as HTMLElement).closest('a')) return;
    const k = tr.dataset.cen; if (!k) return;
    setCensusOpen((prev) => { const n = new Set(prev); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  };
  const [koHtml, setKoHtml] = useState<string | null>(null);
  const [climbWhat, setClimbWhat] = useState('climb');

  // ---- the star shown and the journey's choices
  const [starKey, setStarKey] = useState('');
  const starOptions = useMemo<{ key: string; name: string; lit: boolean }[]>(() => {
    const d = detailApi.data;
    if (!d || !d.stars) return [];
    const lit = (k: string): boolean => (d.runs || []).some((r: any) => r.series[k] && r.series[k].step.length);
    const own: string[] = (d.voyage_stars || []).filter((k: string) => d.stars[k]);
    const keys: string[] = Object.keys(d.stars);
    return (own.length ? own : keys).map((k: string) => ({ key: k, name: d.stars[k].name, lit: lit(k) }));
  }, [detailApi.data]);
  useEffect(() => {
    if (!starOptions.length || starOptions.some((o: { key: string }) => o.key === starKey)) return;
    setStarKey((starOptions.find((o: { lit: boolean }) => o.lit) || starOptions[0]).key);
  }, [starOptions, starKey]);

  const journeyRuns = useMemo(() => (v ? v.runs.filter((r) => !r.set_aside) : []), [v]);
  const optsKey = journeyOptsKey(v);
  const [ja, setJa] = useState<string | null>(null);
  const [jb, setJb] = useState<string | null>(null);
  const [jidx, setJidx] = useState<number | null>(null);
  const [jmods, setJmods] = useState<Set<string>>(new Set(['stars', 'kink']));
  const lastOpts = useRef('');
  const detailReady = !isVoyage || detailApi.data != null || detailApi.error != null;
  // useApi keeps the last payload while a new URL loads: make sure it is this expedition's series
  const detailMatches = !v || !detailApi.data || !v.runs.length || v.runs.some((r) => (detailApi.data.runs || []).some((x: any) => x.run_id === r.run_id));
  useEffect(() => {
    if (!v || !detailReady || !detailMatches || lastOpts.current === optsKey) return;
    lastOpts.current = optsKey;
    const runs = v.runs.filter((r) => !r.set_aside);
    if (!runs.length) { setJa(null); setJb(null); return; }
    const d = detailApi.data;
    const tpOf = (id: string): any => d && ((d.runs || []).find((x: any) => x.run_id === id) || {}).transplant;
    const roleOf = (id: string): any => d && ((d.runs || []).find((x: any) => x.run_id === id) || {}).role;
    const reverse = [...runs].reverse();
    const recv = reverse.find((r) => tpOf(r.run_id) || roleOf(r.run_id) === 'student');
    const a = (recv || reverse.find((r) => r.status === 'running') || runs[runs.length - 1]).run_id;
    let b: string | null = null;
    if (recv) {
      const seed = (recv.name.match(/-s(\d+)$/) || [])[1];
      const want = /lineage/.test(recv.name) ? /lineage-ctl/ : /control/;
      const ctl = runs.find((r) => r.run_id !== recv.run_id && !tpOf(r.run_id) && want.test(r.name) && (!seed || r.name.endsWith('-s' + seed)));
      b = ctl ? ctl.run_id : null;
    }
    setJa(a); setJb(b); setJidx(null);
  }, [v, detailReady, detailMatches, optsKey, detailApi.data]);
  useEffect(() => { setJa(null); setJb(null); setJidx(null); lastOpts.current = ''; }, [route.key]);

  // ---- Training and Fitting Out are the SOP's build sections, mounted only while their tab is open.
  // The shipbuilder is Phaleron's; it is fetched and rendered into the expedition's own tab.
  useEffect(() => {
    if (!v || (expTab !== 'training' && expTab !== 'fitting')) return;
    const activeId = expTab === 'training' ? 'exptraining' : 'expfitting';
    // The shipbuilder uses document ids inside its panel; only one panel may be mounted at a time, or
    // the Training and Fitting Out panels write into each other's boxes. Clear the other one first.
    for (const id of ['exptraining', 'expfitting']) {
      if (id === activeId) continue;
      const other = document.getElementById(id);
      if (other) { other.innerHTML = ''; other.dataset.built = ''; }
    }
    const el = document.getElementById(activeId);
    if (!el) return;
    let live = true;
    void (async () => {
      const { mountShipbuilder } = await import('@/scripts/views/shipbuilder');
      if (!live) return;
      await mountShipbuilder(el, { key: 'phaleron', name: 'Phaleron', ship_builder: 'the ship builder' } as any, expTab, true, v.sop);
    })();
    return () => { live = false; };
  }, [v, expTab]);

  // ---- the drawings, once the browser has the payload and the tab that shows them
  // the sortable tables and the ⓘ popovers wire themselves when their modules load (browser only)
  useEffect(() => { void import('@/lib/datatable'); void import('@/lib/info'); }, []);
  useEffect(() => {
    if (!isVoyage || !v || expTab !== 'findings' || v.key !== 'book_value') return;
    void import('@/scripts/views/expedition-charts').then((c) => c.drawFit(v));
  }, [isVoyage, v, expTab]);
  useEffect(() => {
    if (!isVoyage || !v || expTab !== 'fleet') return;
    let live = true;
    void import('@/scripts/views/expedition-charts').then((c) => { if (live) { c.drawVoyageFt(v); } });
    return () => { live = false; };
  }, [isVoyage, v, expTab]);
  useEffect(() => {
    if (!isVoyage || !v || expTab !== 'fleet' || !detailApi.data || !starKey) return;
    let live = true;
    void import('@/scripts/views/expedition-charts').then((c) => { if (live) void c.drawVoyageStars(v, detailApi.data, starKey); });
    return () => { live = false; };
  }, [isVoyage, v, expTab, detailApi.data, starKey]);
  useEffect(() => {
    if (!isVoyage || !v || v.key !== 'induction' || expTab !== 'findings') return;
    let live = true;
    void import('@/scripts/views/expedition-charts').then((c) => { if (live) c.drawInductionCharts(v, indApi.data); });
    return () => { live = false; };
  }, [isVoyage, v, expTab, indApi.data]);
  useEffect(() => {
    if (!isVoyage || v?.key !== 'knockout' || expTab !== 'findings' || !koApi.data) { setKoHtml(null); return; }
    let live = true;
    void import('@/scripts/views/expedition-charts').then((c) => { if (live) setKoHtml(c.knockoutHtml(koApi.data)); });
    return () => { live = false; };
  }, [isVoyage, v, expTab, koApi.data]);
  useEffect(() => {
    if (!koHtml || !koApi.data) return;
    let live = true;
    const draw = (): void => {
      if (!live) return;
      if (!document.getElementById('kochart0')) { requestAnimationFrame(draw); return; }
      void import('@/scripts/views/expedition-charts').then((c) => { if (live) c.drawKnockoutCharts(koApi.data); });
    };
    draw();
    return () => { live = false; };
  }, [koHtml, koApi.data]);
  useEffect(() => {
    if (!isVoyage || v?.key !== 'two_facts' || expTab !== 'findings' || !v) return;
    let live = true;
    void import('@/scripts/views/expedition-charts').then((c) => { if (live) c.drawVoyageClimb(v, climbApi.data, internalApi.data, climbWhat, rungs); });
    return () => { live = false; };
  }, [isVoyage, v, expTab, climbApi.data, internalApi.data, climbWhat, rungs]);
  useEffect(() => {
    if (!isVoyage || !v || !ja || !detailApi.data) return;
    let live = true;
    const draw = (): void => {
      if (!live) return;
      if (!document.getElementById('journeyviewA')) { requestAnimationFrame(draw); return; }
      void import('@/scripts/views/expedition-charts').then((c) => {
        if (live) void c.drawJourneyPanel({ v, detail: detailApi.data, a: ja, b: jb, idx: jidx, modules: jmods });
      });
    };
    draw();
    return () => { live = false; };
  }, [isVoyage, v, ja, jb, jidx, jmods, detailApi.data]);

  // a row in the fleet table opens that ship; a book link opens the reader (lazily: its module wires
  // the reader's DOM at load)
  const onBookClick = (e: ReactMouseEvent): void => {
    const t = e.target as HTMLElement;
    const tr = t.closest('#voyageruns tr[data-ship]') as HTMLElement | null;
    if (tr && !t.closest('a') && !t.closest('.info')) { location.href = '/ships/' + encodeURIComponent(tr.dataset.ship || ''); return; }
    const b = t.closest('a[data-book]') as HTMLElement | null;
    if (!b) return;
    e.preventDefault();
    const id = b.dataset.book;
    if (id) void import('@/lib/reader').then((r) => r.openBook(id));
  };

  // ---- a few renderers read the whole payload; compute them once per render
  const fleet = useMemo(() => (v ? fleetShipsHtml(v) : null), [v]);
  const koBody = koHtml !== null ? koHtml
    : !koApi.data ? EMPTY('reading the knockout…')
    : !(koApi.data.results || []).length ? EMPTY('no knockout has finished yet: the first, Qwen 3 4B, takes about an hour')
    : '';
  const reading = useMemo(() => (v ? readingsTable(v, readingsApi.data) : { head: '', body: '' }), [v, readingsApi.data]);
  const fit = useMemo(() => (v ? fitHtml(v) : null), [v]);

  // ---- the shell
  return (
    <div onClick={onBookClick}>
      {/* ------------------------------------------------ the queue and the expeditions */}
      <div className={`section${isOverview || isQueue || isList ? ' active' : ''}`} id="voyages">
        <h1>{isQueue
          ? <>The queue <span className="q">what sails next, in order, as the S2 coordinator takes it from the Mac lane; open a ship to follow its training</span></>
          : isList
          ? <>Plans <span className="q">every expedition: the ships it has sailed, its goal, how it is steered, and what it found</span></>
          : <>Expeditions <span className="q">what each standard went out to find, and how far it has got</span></>}</h1>
        <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="vnav">
          <a className={tabCls('')} data-state={isOverview ? 'active' : 'inactive'} data-vtab="overview" href="/expeditions"
            onClick={(e) => { e.preventDefault(); go('/expeditions'); }}>Overview</a>
          <a className={tabCls('')} data-state={isQueue ? 'active' : 'inactive'} data-vtab="queue" href="/expeditions/queue"
            onClick={(e) => { e.preventDefault(); go('/expeditions/queue'); }}>Queue</a>
          <a className={tabCls('')} data-state={isList ? 'active' : 'inactive'} data-vtab="expeditions" href="/expeditions/plans"
            onClick={(e) => { e.preventDefault(); go('/expeditions/plans'); }}>Plans</a>
          <a className={tabCls('')} data-state="inactive" data-vtab="vsm" href="/vsm"
            title="the VSM: the five systems (S1 operations, S2 coordination, S3 control with the gate and the audit, S4 intelligence, S5 policy)">VSM</a>
        </nav>
        <div className={`vtab${isOverview ? ' active' : ''}`} data-vtab="overview">
          <div id="soppanel" dangerouslySetInnerHTML={{ __html: ovApi.data ? sopCardsHtml({ sops: liveSops }) : EMPTY('reading the expeditions…') }} />
        </div>
        <div className={`vtab${isList ? ' active' : ''}`} data-vtab="expeditions">
          {pastSops.length > 0 && (
            <section className="paststandards">
              <h2 className="band">Earlier standards <span className="q">the standards whose voyages are home: what each went out to find. Every expedition they made is listed below</span></h2>
              <div dangerouslySetInnerHTML={{ __html: sopCardsHtml({ sops: pastSops }) }} />
            </section>
          )}
          <div id="voyagecards" dangerouslySetInnerHTML={{ __html: expsApi.data ? expeditionTableHtml(exps, states, ovApi.data) : EMPTY('reading the expeditions…') }} />
        </div>
        <div className={`vtab${isQueue ? ' active' : ''}`} data-vtab="queue">
          <div className="qview active" data-qview="every">
            <section className={cardCls(false, 'panel')} id="queuepanel">
              <h2>The queue <span className="note">every voyage still to sail, in the order it sails (specs/queue.txt), with its goal: the question its spec asks, or its experiment's where it asks none, and the fitout it was compiled from (its census variation and stage); the starts are the median of like voyages scheduled with the Mac's seats, and ≥ marks a line behind one with no time yet</span></h2>
              <div className="scroll queuescroll"><table id="queuetable" data-nosort>
                <thead><tr><th>#</th><th>voyage</th><th>ship</th><th title="the SOP the voyage is built to: its content, tokeniser, parameters, phases and depth">SOP</th><th title="about when it starts, in your local timezone: the median of like voyages, scheduled with the Mac's seats (two 300k may share; a 1m or 9m holds the lane); ≥ where a voyage ahead has no time yet">starts</th><th title="about when it sails: the median of like voyages, scheduled with the Mac's seats; ≥ where a voyage ahead has no time yet">sails in</th></tr></thead>
                <tbody dangerouslySetInnerHTML={{ __html: queueApi.data ? queueRowsHtml(queueApi.data, rungs) : `<tr><td colspan="6" class="${emptyCls(true)}">reading the queue…</td></tr>` }} />
              </table></div>
            </section>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------ one expedition */}
      <div className={`section${isVoyage ? ' active' : ''}`} id="voyage">
        <h1><a className={crumbCls('back')} href="/expeditions" onClick={(e) => { e.preventDefault(); go('/expeditions/queue'); }}>← expeditions</a>{' '}
          <span id="voyagetitle">{v ? v.name : expsApi.data ? `no expedition called ${route.key}` : 'loading…'}</span>{' '}
          <span id="voyagestatus" dangerouslySetInnerHTML={{ __html: v ? expPill(states[v.key], v) : '' }} />{' '}
          </h1>
        <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="expnav">
          {[
            ['overview', 'Overview'], ['at-sea', 'At sea'], ['findings', 'Findings'], ['fleet', 'Fleet'], ['runs', 'Runs'],
            ['plan', 'Plan'], ['training', 'Training'], ['fitting', 'Fitting Out'], ['inside', 'Inside'],
          ].map(([k, label]) => (
            <a key={k} className={tabCls('')} data-state={expTab === k ? 'active' : 'inactive'} data-etab={k} hidden={tabOk[k] === false}
              href={`/expeditions/${route.key}${k === 'overview' ? '' : '/' + k}`}
              onClick={(e) => { e.preventDefault(); go(`/expeditions/${route.key}${k === 'overview' ? '' : '/' + k}`); }}>{label}</a>
          ))}
        </nav>

        {/* Overview */}
        <div className={`etab${expTab === 'overview' ? ' active' : ''}`} data-etab="overview">
          {/* the goal first (11 November, Justin: "where should i see goals for the expeditions"): it was on
              the cards that open this page and nowhere on the page itself */}
          <section className={cardCls(false, 'panel')} id="voyagegoal" hidden={!v?.goal}>
            <h2>The goal <span className="note">what the expedition went out to find, as it was set (fleet.py)</span></h2>
            {(() => {
              // numbered aims in the text, "(1) ... (2) ...", read as a list under what comes before them
              const parts = String(v?.goal || '').split(/\s*\((\d+)\)\s+/);
              const aims: string[] = [];
              for (let i = 1; i + 1 < parts.length; i += 2) aims.push(parts[i + 1]);
              return (
                <>
                  <p className="goaltext">{parts[0]}</p>
                  {aims.length > 1 ? <ol className="sopgoals goaltext">{aims.map((a, i) => <li key={i}>{a}</li>)}</ol> : aims.length ? <p className="goaltext">(1) {aims[0]}</p> : null}
                </>
              );
            })()}
          </section>
          <section className={cardCls(false, 'panel')} id="voyageplan" hidden={!(v?.plan || []).length}>
            <h2>The launching order <span className="note">the investigations that must be home before a learning ship sails, then the ships themselves</span></h2>
            <ol className="plansteps" dangerouslySetInnerHTML={{ __html: v ? planHtml(v) : '' }} />
          </section>
          <section className={cardCls(false, 'panel')} id="voyagelearned"><h2>What it found</h2>
            <p id="voyagelearnedtext" dangerouslySetInnerHTML={{ __html: v ? (v.learned || starHeadline(v) ? escapeText(v.learned || starHeadline(v)) : '<span class="s">nothing written up yet: what it found is written when it comes home</span>') : '' }} />
            <div id="voyagenextwrap" hidden={!v?.next_steps?.length}><h2 className="mt">Suggested next steps</h2><ol id="voyagenext" className="nextsteps">{(v?.next_steps || []).map((x) => <li key={x}>{x}</li>)}</ol></div></section>
          <section className={cardCls(false, 'panel')} data-voyage="table_talk" style={hideStyle(v?.key !== 'table_talk')}>
            <h2>The table <span className="note">talk with Table Talk's ships, or any finished ship: type a line and read its answer</span></h2>
            <p><a href="/expeditions/table_talk/table">Sit at the table →</a></p>
          </section>
          <div className="row">
            <section className={cardCls(false, 'panel')}><h2>What it measures <span className="note">the outcomes the expedition is judged by</span></h2><div className="scroll"><table id="voyageoutcomes"><thead><tr><th>outcome</th><th>metric</th><th>better is</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: v ? outcomesRowsHtml(v) : '' }} /></table></div></section>
            <section className={cardCls(false, 'panel')}><h2>The levers <span className="note">what the expedition may change between voyages, and within what limits</span></h2><div className="scroll"><table id="voyagelevers"><thead><tr><th>lever</th><th>range or choices</th><th>about</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: v ? leversRowsHtml(v) : '' }} /></table></div></section>
          </div>
        </div>

        {/* Plan: what is queued for this expedition, and what makes its arms differ */}
        <div className={`etab${expTab === 'plan' ? ' active' : ''}`} data-etab="plan">
          <section className={cardCls(false, 'panel')} id="planpanel">
            <h2>The plan <span className="note">every launch still queued for this expedition, in order, and the parameters that make the arms differ: the two 1m ships are the same voyage twice, once with 4 query heads sharing 2 KV heads and once plain</span></h2>
            <div dangerouslySetInnerHTML={{ __html: planTableHtml(planApi.data) }} />
          </section>
        </div>

        {/* At sea: the arm-by-arm read, as it runs */}
        <div className={`etab${expTab === 'at-sea' ? ' active' : ''}`} data-etab="at-sea">
          <section className={cardCls(false, 'panel')} id="armspanel" onClick={onDeckClick}>
            <h2>The arms at sea <span className="note">one card a voyage, live: its embeddings, its corpus, its attention, the heads it teaches and where, and its readings against the control</span></h2>
            <div dangerouslySetInnerHTML={{ __html: seaApi.error ? EMPTY(`the arms could not be read: ${seaApi.error}`) : seaApi.data ? armCardsHtml(seaApi.data) : EMPTY('reading the arms at sea…') }} />
          </section>
        </div>

        {/* At sea: the observation deck */}
        <div className={`etab${expTab === 'at-sea' ? ' active' : ''}`} data-etab="at-sea">
          <section className={cardCls(false, 'panel')} id="obspanel">
            <h2>The observation deck <span className="note">the selected voyage at sea, read live from its log: how far each has come and how long it has left, its loss, its speed, the four necessary cards as they stand, and its star chart: each star and trick lit where the voyage found it, numbered in order, to play back. One voyage sails at a time (S2); when none of this expedition's is at sea, where its next one stands in the queue</span></h2>
            <div id="obsdeck" onClick={onDeckClick} onInput={onDeckInput} dangerouslySetInnerHTML={{ __html: obsApi.error ? EMPTY(`the observation deck could not be read: ${obsApi.error}`) : obsApi.data ? deckHtml(obsApi.data, sky, expeditionName(exps, obsApi.data.elsewhere?.[0]?.expedition), deckRun) : EMPTY('reading the observation deck…') }} />
          </section>
        </div>

        {/* Findings: its own instruments, then every reading */}
        <div className={`etab${expTab === 'findings' ? ' active' : ''}`} data-etab="findings">
          <section className={cardCls(false, 'panel')} data-voyage="induction" style={hideStyle(v?.key !== 'induction')}>
            <h2>The Nevermore over training <span className="note">the trigram engine (frontier books, green) against its random twin (the same libraries and amounts, books chosen at random, grey), two seeds each (seed 1 solid, seed 2 dashed): the Nevermore's natural score at every reading, the mark 0.3 dotted, and the step each voyage first lights it. Success: a 300k lights it on two seeds; repetition did it if the engine lights it and its twin does not (DECISIONS.md, "Discovering the induction head, pre-registered")</span></h2>
            <div className="indverdict" id="indverdict" dangerouslySetInnerHTML={{ __html: v ? inductionVerdict(v, indApi.data) : '' }} />
            <div className="chart tall" id="indnevermore" />
            <div className="row">
              <div><div className="k">Previous-word <span className="s">the head the Nevermore rests on; the mark 0.5</span></div><div className="chart" id="indprev" /></div>
              <div><div className="k">The copy gain <span className="s">the loss drop from a passage's first copy to its second, nats per token; copying performed at 0.5</span></div><div className="chart" id="indcopy" /></div>
            </div>
          </section>
          <section className={cardCls(false, 'panel')} data-voyage="knockout" style={hideStyle(v?.key !== 'knockout')}>
            <h2>The knockout <span className="note">does silencing a card's heads break chaining in a model that chains? Each card's 8 strongest heads silenced, beside three random draws of 8 heads; a bar per card for the gain lost (cause; the comparator, order), the random draws in grey on the same measure, and each card's rule dotted over it (0.1, and twice its largest random drop), and each card's verdict, necessary or not shown. Outside models only (DECISIONS.md, "The knockout, pre-registered")</span></h2>
            <div id="knockouts" dangerouslySetInnerHTML={{ __html: koBody }} />
          </section>
          <section className={cardCls(false, 'panel')} data-voyage="card_census" style={hideStyle(v?.key !== 'card_census')}>
            <h2>The census <span className="note">which of the four necessary cards (previous-word, Nevermore, mover, comparator: the ones every model that chains plays) each size can draw, and its cause-and-effect score, voyage as ablations of the size's own fitout so every variation compares with it. A row per variation (the fitout first), each cell its latest stage's reading (one head or a layer's best two together), green ✓ at the card's mark; cause with its change from the fitout's own. Open a row for its three stages</span></h2>
            <div id="censusgrid" onClick={onCensusClick} dangerouslySetInnerHTML={{ __html: census }} />
          </section>
          <section className={cardCls(false, 'panel')} data-voyage="two_facts" style={hideStyle(v?.key !== 'two_facts')}>
            <h2>The climb over training <span className="note">each voyage's climb toward chaining two facts at every discovery reading (0 to 5: the rungs performed from the bottom of each chain, plus the next rung's share of its mark, the mean of the four chains), one line per voyage, coloured by size; the dotted levels are the reference ladder; the <a href="/leaderboard">leaderboard</a> holds each size's best</span></h2>
            <div className="handtools"><select className={selectCls('')} id="voyageclimbwhat" value={climbWhat} onChange={(e) => setClimbWhat(e.target.value)}>
              <option value="climb">the climb</option><option value="chaining_lift">the chaining lift</option><option value="logic_gain">the chaining gain (logic deck)</option>
            </select></div>
            <div className="chart tall" id="voyageclimb" />
          </section>
          <section className={cardCls(false, 'panel')} data-voyage="book_value" style={hideStyle(v?.key !== 'book_value')}>
            <h2>The fit: what each kind of book is worth <span className="note">the Forgotten Tomes score a pure library of each kind would give, with 90% intervals, lower is better; <b id="fitr2">{fit ? fit.r2 : ''}</b></span></h2>
            <div className="row"><div className="scroll"><table id="fittable"><thead><tr><th>term</th><th>estimate</th><th>90% low</th><th>90% high</th></tr></thead><tbody dangerouslySetInnerHTML={{ __html: fit ? fit.rows : '' }} /></table></div>
              <div className="chart" id="fitchart" /></div>
          </section>
          <section className={cardCls(false, 'panel')} data-voyage="first_light" style={hideStyle(v?.key !== 'first_light')}>
            <h2>What it found <span className="note">the fourteen round-1 voyages, best first: the Forgotten Tomes score on the 16 unseen books, and whether the previous-word and duplicate-word stars lit with one head or shared between a layer's two strongest</span></h2>
            <div dangerouslySetInnerHTML={{ __html: v ? firstLightFindings(v) : '' }} />
          </section>
          <section className={cardCls(false, 'panel')} id="readingspanel">
            <h2>Its readings <span className="note">every voyage of this expedition on each measure it is judged by (What it measures, on Overview): the latest reading, the best in each column marked</span></h2>
            <div className="scroll"><table id="voyagereadings" data-nosort>
              <thead dangerouslySetInnerHTML={{ __html: reading.head }} />
              <tbody dangerouslySetInnerHTML={{ __html: v ? reading.body : `<tr><td class="${emptyCls(true)}">reading…</td></tr>` }} />
            </table></div>
          </section>
        </div>

        {/* Fleet */}
        <div className={`etab${expTab === 'fleet' ? ' active' : ''}`} data-etab="fleet">
          <section className={cardCls(false, 'panel')}><h2>The ships <span className="note">each ship this expedition fitted out, its voyages, its mean Forgotten Tomes score, and for each star how many voyages lit it and the soonest step; open one to see it sail</span></h2>
            <div className="scroll"><table id="voyageruns" className="clickable">
              <thead dangerouslySetInnerHTML={{ __html: fleet ? fleet.head : '' }} />
              <tbody dangerouslySetInnerHTML={{ __html: fleet ? fleet.body : '' }} />
            </table></div></section>
          <div className="row">
            <section className={cardCls(false, 'panel')} id="ftpanel" style={hideStyle(!fleet?.scored)}><h2>The Forgotten Tomes score, voyage by voyage <span className="note">one dot per voyage in the order they sailed, coloured by the expedition's main lever; lower is better</span></h2><div className="chart" id="voyageft" /></section>
            <section className={cardCls(false, 'panel')} id="lightpanel" style={hideStyle(!fleet?.light)}><h2>First light <span className="note">each star's score against step: per voyage, the best single head (solid) and the best layer's two strongest heads together (dashed); the dotted line is the threshold, and the moment a line crosses it is first light, lit or lit shared</span></h2>
              <div className="handtools"><select className={selectCls('')} id="voyagestar" title="the star shown" value={starKey} onChange={(e) => setStarKey(e.target.value)}>
                {starOptions.map((o) => <option key={o.key} value={o.key}>{o.name}</option>)}
              </select></div><div className="chart" id="voyagestars" /></section>
          </div>
        </div>

        {/* Runs: every arm of the expedition, finished or at sea */}
        <div className={`etab${expTab === 'runs' ? ' active' : ''}`} data-etab="runs">
          <section className={cardCls(false, 'panel')}>
            <h2>The runs <span className="note">every voyage of this expedition, finished or at sea: the arm, its ship, its size, its status, its Forgotten Tomes score, the tokens it read and the stars it lit. The finished 300ks are here, not only the arms still at sea</span></h2>
            <div dangerouslySetInnerHTML={{ __html: runsTableHtml(v) }} />
          </section>
        </div>

        {/* Training and Fitting Out: the SOP's two build sections, on the expedition's own page */}
        <div className={`etab${expTab === 'training' ? ' active' : ''}`} data-etab="training"><div id="exptraining" /></div>
        <div className={`etab${expTab === 'fitting' ? ' active' : ''}`} data-etab="fitting"><div id="expfitting" /></div>

        {/* Inside: the journey through the layers */}
        <div className={`etab${expTab === 'inside' ? ' active' : ''}`} data-etab="inside">
          <section className={cardCls(false, 'panel')} id="journeypanel">
            <h2>The journey through the layers <span className="note">one voyage read as the data's journey up its stack, bottom to top: the guess the model would make at each depth (bits per byte, and how much each layer lowered it), and out of each half of each layer an arrow sized by how hard it writes into the stream and tilted by which way, up along it, level across it (something new), down against it. Switch on the modules to read each layer's sieves, stars and kink at the step chosen; put a second voyage beside it to compare</span></h2>
            <div className="handtools">
              <select className={selectCls('')} id="journeyA" title="the voyage" value={ja ?? ''} onChange={(e) => { setJidx(null); setJa(e.target.value || null); }}>
                {[...journeyRuns].reverse().map((r) => <option key={r.run_id} value={r.run_id}>{`${r.ship_name || r.ship || r.name} · ${r.name}`}</option>)}
              </select><label className="note" htmlFor="journeyB">beside</label>
              <select className={selectCls('')} id="journeyB" title="a second voyage to compare" value={jb ?? ''} onChange={(e) => { setJidx(null); setJb(e.target.value || null); }}>
                <option value="">none</option>
                {[...journeyRuns].reverse().map((r) => <option key={r.run_id} value={r.run_id}>{`${r.ship_name || r.ship || r.name} · ${r.name}`}</option>)}
              </select>
              <input className={rangeCls('')} type="range" id="journeystep" min={0} defaultValue={0}
                onChange={(e) => { const n = +e.target.value; setJidx(n >= +(e.target as HTMLInputElement).max ? null : n); }} /><span id="journeylabel" className="note" />
            </div>
            <div className="jstages" id="journeystages" />
            <div className="handtools" id="journeymods">
              <span className="note">modules</span>
              {([['push', 'push'], ['move', 'move'], ['heading', 'heading'], ['stars', 'stars'], ['kink', 'kink']] as [string, string][]).map(([k, label]) => (
                <label key={k}><input className={checkCls('')} type="checkbox" value={k} checked={jmods.has(k)}
                  onChange={(e) => setJmods((prev) => { const n = new Set(prev); if (e.target.checked) n.add(k); else n.delete(k); return n; })} /> {label}</label>
              ))}
            </div>
            <div className="journeys"><div id="journeyviewA" /><div id="journeyviewB" /></div>
          </section>
        </div>
      </div>

      {/* ------------------------------------------------ the table */}
      <div className={`section${isTable ? ' active' : ''}`} id="table">
        <h1><a className={crumbCls('back')} id="tableback" href={`/expeditions/${tableKey || 'table_talk'}`}
          onClick={(e) => { e.preventDefault(); go(`/expeditions/${tableKey || 'table_talk'}`); }}>← expedition</a> The table <span className="q">talk with a ship: your line as Q:, its answer as A:, every exchange kept</span></h1>
        <section className={cardCls(false, 'panel')}>
          <div className="handtools">
            <label className="note" htmlFor="tablerun">ship</label>
            <select className={selectCls('')} id="tablerun" title="the voyage at the table" value={tableRun ?? ''} onChange={(e) => { setTableRun(e.target.value); setTableReadings('ask something to see them'); }}>
              {tableOptions.own.length ? <optgroup label={tableExp ? tableExp.name : tableKey || 'table_talk'}>
                {tableOptions.own.map((r) => <option key={r.name} value={r.name}>{tableOptions.label(r)}</option>)}
              </optgroup> : null}
              <optgroup label="any finished ship">
                {tableOptions.others.map((r: any) => <option key={r.name} value={r.name}>{tableOptions.label(r)}</option>)}
              </optgroup>
            </select>
            <label className="note" htmlFor="tabletemp">temperature</label><input className={rangeCls('')} type="range" id="tabletemp" min={0} max={1.5} step={0.05} value={tableTemp} onChange={(e) => setTableTemp(+e.target.value)} /><b id="tabletempv">{tableTemp.toFixed(2)}</b>
            <label className="note" htmlFor="tablemax">longest answer</label><select className={selectCls('')} id="tablemax" value={tableMax} onChange={(e) => setTableMax(e.target.value)}>
              <option>50</option><option>100</option><option>200</option><option>400</option>
            </select>
            <label className="note" htmlFor="tableseed">seed</label><input className={fieldCls('')} id="tableseed" placeholder="any" size={6} title="the same seed and temperature give the same answer" value={tableSeed} onChange={(e) => setTableSeed(e.target.value)} />
          </div>
          <p className="note" id="tablehint">Low temperature: the ship's surest words. High: braver, stranger. The ship reads the last exchanges as the conversation so far. Ships not trained on the Q:/A: form don't converse yet: they carry on as if reading a book (a contents page, a poem). Table Talk's conversation stage is what teaches them to answer.</p>
        </section>
        <div className="tablegrid">
          <section className={cardCls(false, 'panel')}>
            <div id="tablelog" className="tablelog" dangerouslySetInnerHTML={{ __html: tableLogHtml(tableLog, tablePending) }} />
            <form id="tableform" className="tableform" autoComplete="off" onSubmit={(e) => { e.preventDefault(); void askTable(); }}>
              <b>Q:</b><input className={fieldCls('')} id="tableq" placeholder="say something to the ship" value={tableQ} onChange={(e) => setTableQ(e.target.value)} disabled={tableLocked || !tableRun} />
              <button className={btnCls('outline', '')} id="tableask" type="submit" disabled={tableBusy || tableLocked || !tableRun}>Ask</button>
            </form>
            <div className="note" id="tablestatus">{tableStatus}</div>
          </section>
          <section className={cardCls(false, 'panel')}>
            <h2>The ship's readings <span className="note">its stars and tricks at the checkpoint answering you</span></h2>
            <div id="tablereadings" className="note" dangerouslySetInnerHTML={{ __html: tableReadings }} />
          </section>
        </div>
      </div>
    </div>
  );
}

// `learned` and the star headline are prose, not markup: escape them here, as the old DOM did with textContent
function escapeText(s: string): string {
  return String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string));
}
