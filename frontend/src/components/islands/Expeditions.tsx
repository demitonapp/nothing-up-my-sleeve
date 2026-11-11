// The Expeditions page (UI.md "Expeditions"), as a typed client island: the queue landing (the waters
// plan, the queue at a glance, every voyage), the expedition cards, one expedition and its five tabs,
// and the table. It replaces dashboard.ts on this page; the dense markup lives in
// scripts/views/expeditions.ts and the charts are imported inside effects only, because the island is
// server-rendered and ECharts touches `document` when it loads.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent as ReactMouseEvent, ReactNode } from 'react';
import { btnCls, cardCls, checkCls, crumbCls, emptyCls, fieldCls, hoverCardCls, pillCls, rangeCls, selectCls, toggleCls } from '@/lib/ui';
import { routePath, useApi, useRoute } from '@/lib/useApi';
import { esc, fmt } from '@/lib/format';
import { starHeadline } from '@/scripts/views/helpers';
import SectionNav from '../SectionNav';
import { TabNav } from '../TabNav';
import Launch from './Launch';
import type { LaunchPayload } from './Launch';
import {
  censusHtml, deckHtml, expeditionCardsHtml, expeditionName, expeditionOutcomes, expeditionTableHtml, expPill, firstLightFindings, fitHtml, fleetShipsHtml, runsTableHtml,
  inductionVerdict, leversRowsHtml, outcomesRowsHtml, parseExpeditionRoute, pinsStripHtml, queueLanesHtml, queueRowsHtml, readingsTable,
  skyStateOf, sopCardsHtml, tableLogHtml, tableReadingsHtml, planHtml,
} from '@/scripts/views/expeditions';
import type { Expedition, Observation, SeriesMap, SkyViewState, TableExchange } from '@/scripts/views/expeditions';

/** The expeditions' priority (11 November, Justin: "under goals ... choose their priority across all
 *  the expeditions ... the coordinator can schedule accordingly"): the whole list in rank order, moved
 *  up and down and saved. Saving writes the order and stably sorts the pending spec lines to it, so the
 *  coordinator, which takes the first line, sails the highest-priority expedition's earliest voyage. */
type GoalRow = {
  key: string; expedition?: string; name: string; goal?: number | null; goal_text?: string;
  status?: string; priority: number;
};

/** Priority by goal (11 November, Justin: "it should be a table that is filterable and sortable. For
 *  example I only want to be able to plan current expeditions goals"): the rows are the goals across
 *  every expedition, filtered by status/expedition/text and sortable by any column, while the priority
 *  itself is the # cell — a number, 1 first — so sorting the view never changes the plan. */
function PriorityPanel({ rows, highlight }: { rows: GoalRow[]; highlight?: string }) {
  const [order, setOrder] = useState(rows);
  const [msg, setMsg] = useState('');
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('running');
  const [exp, setExp] = useState('');
  const [q, setQ] = useState('');
  const [sort, setSort] = useState<{ key: 'priority' | 'goal' | 'expedition' | 'status'; dir: 1 | -1 }>({ key: 'priority', dir: 1 });
  useEffect(() => { setOrder(rows); setMsg(''); }, [rows]);

  const place = (key: string, n: number): void => {
    const from = order.findIndex((r) => r.key === key);
    if (from < 0) return;
    const to = Math.max(0, Math.min(order.length - 1, n - 1));
    const next = order.slice();
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    setOrder(next);
    setMsg('');
  };
  const sortBy = (key: 'priority' | 'goal' | 'expedition' | 'status'): void =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));
  const arrow = (key: string): string => (sort.key === key ? (sort.dir === 1 ? ' ↑' : ' ↓') : '');

  const expeditions = Array.from(new Map(order.map((r) => [r.expedition || r.name, r.name])).entries());
  const shown = order
    .map((r, i) => ({ r, rank: i + 1 }))
    .filter(({ r }) => {
      const st = r.status || '';
      if (status !== 'all' && st !== status) return false;
      if (exp && (r.expedition || r.name) !== exp) return false;
      if (q && !`${r.goal_text || ''} ${r.name}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      if (sort.key === 'priority') return (a.rank - b.rank) * sort.dir;
      const va = sort.key === 'goal' ? (a.r.goal_text || a.r.name) : sort.key === 'expedition' ? a.r.name : a.r.status || '';
      const vb = sort.key === 'goal' ? (b.r.goal_text || b.r.name) : sort.key === 'expedition' ? b.r.name : b.r.status || '';
      return String(va).localeCompare(String(vb)) * sort.dir;
    });

  const save = async (): Promise<void> => {
    setSaving(true);
    setMsg('saving…');
    try {
      const r = await fetch('/api/expedition_priority', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ order: order.map((x) => x.key) }),
      });
      if (!r.ok) throw new Error(await r.text());
      await r.json();
      setMsg('saved: the queue is reordered and the coordinator takes the first line');
    } catch (e) {
      setMsg(`could not save: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={cardCls(false, 'panel')} id="voyagepriority">
      <h2>Priority <span className="note">the goals across every expedition, in the order the coordinator should take them: first is highest, and a goal of one expedition may sit between two goals of another. The # cell is the priority (1 first); filtering or sorting the view never changes it. Saving reorders the pending spec lines — a spec joins a goal by naming it (<code>goal: 4</code> in its YAML), a line with no goal sits with its expedition's first, and cmd/wait lines stay where they are</span></h2>
      <div className="handtools priofilters">
        <label className="note">show{' '}
          <select className={selectCls('')} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="running">running (current)</option>
            <option value="planned">planned</option>
            <option value="paused">paused</option>
            <option value="all">all</option>
          </select>
        </label>
        <label className="note">expedition{' '}
          <select className={selectCls('')} value={exp} onChange={(e) => setExp(e.target.value)}>
            <option value="">all</option>
            {expeditions.map(([key, name]) => <option key={key} value={key}>{name}</option>)}
          </select>
        </label>
        <label className="note">search{' '}
          <input className={fieldCls('')} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="goal or expedition" style={{ width: 200 }} />
        </label>
        <span className="note">{shown.length} of {order.length} goals</span>
      </div>
      <div className="scroll priolist">
        <table data-nosort>
          <thead><tr>
            <th className="sortable" onClick={() => sortBy('priority')} title="the priority; 1 sails first">#{arrow('priority')}</th>
            <th className="sortable" onClick={() => sortBy('goal')}>goal{arrow('goal')}</th>
            <th className="sortable" onClick={() => sortBy('expedition')}>expedition{arrow('expedition')}</th>
            <th className="sortable" onClick={() => sortBy('status')}>status{arrow('status')}</th>
            <th>move</th>
          </tr></thead>
          <tbody>
            {shown.map(({ r, rank }) => (
              <tr key={r.key} className={r.key === highlight ? 'sel' : ''}>
                <td className="num">
                  <input className="prioinput" type="number" min={1} max={order.length} value={rank}
                    onChange={(e) => place(r.key, Number(e.target.value) || rank)} title="priority: 1 sails first" />
                </td>
                <td>
                  <b>{r.goal_text || r.name}</b>
                  {r.goal ? <span className="s"> · goal {r.goal}</span> : null}
                </td>
                <td className="s">{r.name}</td>
                <td className="s">{r.status || ''}</td>
                <td>
                  <button type="button" className={btnCls('outline', '')} onClick={() => place(r.key, rank - 1)} disabled={rank === 1} title="move up">↑</button>{' '}
                  <button type="button" className={btnCls('outline', '')} onClick={() => place(r.key, rank + 1)} disabled={rank === order.length} title="move down">↓</button>
                </td>
              </tr>
            ))}
            {shown.length ? null : <tr><td colSpan={5} className={emptyCls(true)}>no goals match this filter</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="handtools mt">
        <button type="button" className={btnCls('default', '')} onClick={save} disabled={saving}>{saving ? 'saving…' : 'Save priority'}</button>
        <span className="note">{msg}</span>
      </div>
    </section>
  );
}

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
// the queue's row identity: the name, plus the spec or start that tells two attempts apart
const queueKey = (r: any): string => `${r?.name || ''}|${r?.spec || r?.started || ''}`;

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

/** A label/value row on a voyage card: the at-sea card's .armrow, reused in the queue's modal. */
function VRow({ k, children }: { k: string; children: ReactNode }) {
  return <div className="armrow"><span className="k">{k}</span><span>{children}</span></div>;
}

function VSection({ title, wide, children }: { title: string; wide?: boolean; children: ReactNode }) {
  return <section className={`qvsec${wide ? ' wide' : ''}`}><h3>{title}</h3>{children}</section>;
}

/** Opening and closing a queue card: the dialog shown modal, Escape and the backdrop close it, and focus goes
 *  back to the row that opened it. */
function useQueueDialog(onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    opener.current = document.activeElement as HTMLElement | null;
    if (!el.open) el.showModal();
    const cancel = (e: Event): void => { e.preventDefault(); closeRef.current(); };
    el.addEventListener('cancel', cancel);
    return () => {
      el.removeEventListener('cancel', cancel);
      if (el.open) el.close();
      opener.current?.focus?.();
    };
  }, []);
  return ref;
}

const STEP_WHAT: Record<string, string> = { investigation: 'investigation', reading: 'reading', upkeep: 'upkeep', step: 'step' };
const qvMin = (m: number): string => (m < 1 ? 'under a minute' : m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1)} h`);

/** One step in the queue (an investigation, a reading, the coordinator's upkeep, any other command), opened as a
 *  card like a voyage's (12 November, Justin: "investigations need to have a modal similar to voyages and same
 *  thing for these items"): what it does and why, the goal it serves, when it runs and for how long, its
 *  deadline, and the command itself. The data is the row's `detail` from /api/queue. */
function QueueStepDialog({ row, onClose }: { row: any; onClose: () => void }) {
  const ref = useQueueDialog(onClose);
  const d = row?.detail || {};
  const inv = d.investigation || null;
  const rd = d.reading || null;
  const serves = row?.serves || null;
  const atSea = row?.status === 'at sea';
  const when = atSea
    ? row?.started ? `since ${new Date(row.started).toLocaleString()}` : 'at sea'
    : row?.starts_in_min != null
      ? `${row.at_least ? '≥ ' : '≈ '}${new Date(Date.now() + Number(row.starts_in_min) * 60000).toLocaleString()}`
      : 'no time yet';
  const length = row?.est_min == null ? 'no time of its own yet'
    : `${row.est_is_max ? 'up to ' : 'about '}${qvMin(Number(row.est_min))}${row.est_source ? ` · ${row.est_source}` : ''}`;
  const settings = rd?.settings ? Object.entries(rd.settings as Record<string, string>) : [];
  const what = rd
    ? rd.of === 'our ship'
      ? `${String(rd.evaluators || 'its evaluators').replace('ifeval', 'IFEval')} read on our ship ${rd.ship || rd.run_id}, at its last checkpoint. It trains nothing; the reading is written to the ship's own record.`
      : `${row.name.split(':')[0]} read on an outside model, ${rd.model}, so our ships can be set beside it on the leaderboard. It trains nothing.`
    : row?.what === 'upkeep'
      ? 'The coordinator restarts itself between two lines, so it runs the code on disk rather than the code it was started with. Whatever is at sea is adopted by the new coordinator and keeps going.'
      : null;
  return (
    <dialog ref={ref} className="qv-dialog" aria-labelledby="qstitle" onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="qvwrap" onClick={(e) => e.stopPropagation()}>
        <header className="qvhead">
          <div className="qvheadmain">
            <h2 className="qvtitle" id="qstitle">{row.name}</h2>
            <p className="qvsub">
              {inv?.ship || STEP_WHAT[row.what] || 'step'}
              {serves ? <> · <a href={`/expeditions/${serves.expedition}`}>{serves.expedition_name || serves.expedition}</a></> : null}
            </p>
          </div>
          <div className="qvbadges">
            <span className={pillCls(atSea ? 'running' : '')}>{row.status || 'queued'}</span>
            <span className={pillCls('')}>{STEP_WHAT[row.what] || 'step'}</span>
            {row.goal_id ? <span className={pillCls('accent')}>{row.goal_id}</span> : null}
          </div>
        </header>
        <button type="button" className="qvclose" onClick={onClose} aria-label="Close">×</button>
        <div className="qvgrid">
          <VSection title="What it does" wide>
            {inv?.question ? <p className="qvtext">{inv.question}</p> : what ? <p className="qvtext">{what}</p> : <p className="s">A command between voyages.</p>}
          </VSection>

          <VSection title="The line">
            <VRow k="queue">{row.n != null ? `#${row.n}` : atSea ? 'at sea now' : '–'}</VRow>
            <VRow k="lane">{row.lane || '–'}</VRow>
            <VRow k="starts">{when}</VRow>
            <VRow k="takes">{length}</VRow>
            {atSea && row.elapsed_min != null ? <VRow k="so far">{qvMin(Number(row.elapsed_min))}{row.left_min != null ? <span className="s"> · about {qvMin(Number(row.left_min))} left</span> : null}</VRow> : null}
            <VRow k="deadline">{d.deadline ? <>{d.deadline}<span className="s"> · stopped if it runs longer, and the queue goes on</span></> : <span className="s">none</span>}</VRow>
          </VSection>

          <VSection title="The goal it serves">
            {serves ? <>
              <VRow k="goal">{serves.id}</VRow>
              <VRow k="what"><b>{serves.text}</b></VRow>
              <VRow k="expedition"><a href={`/expeditions/${serves.expedition}`}>{serves.expedition_name || serves.expedition}</a></VRow>
              <VRow k="state">{serves.status}</VRow>
            </> : row.what === 'upkeep'
              ? <p className="s">The queue's own upkeep: it serves no expedition.</p>
              : <p className="s">No goal yet: every line serves one (thorp queue goal LINE --goal EXPEDITION:N).</p>}
          </VSection>

          {inv ? <VSection title="The investigation" wide>
            <VRow k="name"><span className="mono">{inv.name}</span></VRow>
            {inv.subject ? <VRow k="subject"><span className="mono">{inv.subject}</span></VRow> : null}
            <VRow k="runs"><span className="mono">python {inv.run}</span></VRow>
            {(inv.readings || []).length ? <VRow k="writes"><ul className="qvlist">{inv.readings.map((x: string) => <li key={x} className="mono">{x}</li>)}</ul></VRow> : null}
            <VRow k="estimate">{inv.estimate || '–'}{inv.timeout ? <span className="s"> · deadline {inv.timeout}</span> : null}</VRow>
            <VRow k="last run">{inv.last && inv.last.status
              ? <>{inv.last.status}{inv.last.wall_minutes != null ? <span className="s"> · {qvMin(Number(inv.last.wall_minutes))}</span> : null}{inv.last.finished ? <span className="s"> · {new Date(inv.last.finished).toLocaleString()}</span> : null}</>
              : <span className="s">never run</span>}</VRow>
          </VSection> : null}

          {rd ? <VSection title="The reading" wide>
            {rd.of === 'our ship' ? <>
              <VRow k="ship">{rd.ship || '–'}<span className="s mono"> · {rd.run_id}</span></VRow>
              <VRow k="evaluators">{rd.evaluators || '–'}</VRow>
              {settings.map(([k, v]) => <VRow k={k.replace(/^THORP_/, '').replace(/_/g, ' ').toLowerCase()} key={k}>{v}</VRow>)}
            </> : <>
              <VRow k="model"><span className="mono">{rd.model}</span></VRow>
              <VRow k="script"><span className="mono">{rd.script}</span></VRow>
              {rd.options ? <VRow k="options"><span className="mono">{rd.options}</span></VRow> : null}
            </>}
          </VSection> : null}

          <VSection title="The command" wide>
            <pre className="qvcmd">{d.command || row.cmd}</pre>
          </VSection>
        </div>
        <div className="qvfoot">
          {serves ? <a className={btnCls('outline', '')} href={`/expeditions/${serves.expedition}/plan`}>the expedition's plan →</a> : null}
          <span className="s">Queue line: <span className="mono">{row.line || row.cmd}</span></span>
        </div>
      </div>
    </dialog>
  );
}

/** One voyage in the queue, opened as a card: the same shape the at-sea cards use (embeddings, reads,
 *  attention, pins, schedule, readings), plus the spec's question and its place in the queue. The data is
 *  the row's `detail` from /api/queue; a voyage at sea also carries its latest readings. */
function QueueVoyageDialog({ row, onClose }: { row: any; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    opener.current = document.activeElement as HTMLElement | null;
    if (!el.open) el.showModal();
    const cancel = (e: Event): void => { e.preventDefault(); closeRef.current(); };
    el.addEventListener('cancel', cancel);
    return () => {
      el.removeEventListener('cancel', cancel);
      if (el.open) el.close();
      opener.current?.focus?.();
    };
  }, []);
  const d = row?.detail || {};
  const model = d.model || {};
  const tok = d.tokeniser || {};
  const data = d.data || {};
  const optim = d.optim || {};
  const sc = d.scaffold || {};
  const content = d.content || {};
  const readings = d.readings || null;
  const stages: any[] = Array.isArray(data.stages) ? data.stages : [];
  const symbols: string[] = Array.isArray(tok.symbols) ? tok.symbols : [];
  const refuses: string[] = Array.isArray(data.refuse) ? data.refuse : [];
  const pins: any[] = Array.isArray(sc.heads) ? sc.heads : [];
  const riddles: [string, any][] = Object.entries(sc.riddles || {}) as [string, any][];
  const params = model.params || {};
  const layers = Number(model.layers || 0);
  const num = (v: any, digits = 3): string => (v == null || v === '' ? '–' : Number.isFinite(Number(v)) ? fmt(Number(v), digits) : String(v));
  const int = (v: any): string => (v == null || v === '' ? '–' : Number(v).toLocaleString());
  const pct = (v: any): string => (v == null ? '–' : `${Math.round(Number(v) * 100)}%`);
  const tone = row?.status === 'at sea' ? 'running' : row?.status === 'queued' ? '' : 'accent';
  const when = row?.status === 'at sea'
    ? row?.started ? `since ${new Date(row.started).toLocaleString()}` : 'at sea'
    : row?.starts_in_min != null
      ? `${row.at_least ? '≥ ' : '≈ '}${new Date(Date.now() + Number(row.starts_in_min) * 60000).toLocaleString()}`
      : 'no time yet';
  const estimate = row?.est_min != null ? `${Math.round(Number(row.est_min))} min${row.est_source ? ` · ${row.est_source}` : ''}` : 'no time yet';
  // the learning rate as the voyage runs it: its peak, the warm-up to it, and where the schedule leaves it
  const lrEnd = optim.lr != null && optim.min_lr_ratio != null ? Number((Number(optim.lr) * Number(optim.min_lr_ratio)).toPrecision(3)) : null;
  const lrLine: ReactNode = optim.lr == null ? '–' : <>
    <b>{optim.lr}</b> at its peak
    <span className="s">
      {optim.warmup_steps != null ? ` · ${int(optim.warmup_steps)} warm-up steps` : ''}
      {lrEnd != null ? ` · ${optim.schedule || 'falls'} to ${lrEnd}` : optim.schedule ? ` · ${optim.schedule}` : ''}
    </span>
  </>;
  const rcards: any[] = readings && Array.isArray(readings.cards) ? readings.cards : [];
  const totalSteps = optim.steps ?? (d.schedule || {}).total ?? null;
  const hasScaffold = pins.length > 0 || riddles.length > 0;
  // how far the voyage is and when it should dock, from the steps it has written and its own start
  const started = readings?.started || row?.started || null;
  const step = readings?.step != null ? Number(readings.step) : null;
  const total = totalSteps != null && Number(totalSteps) > 0 ? Number(totalSteps) : null;
  const pctDone = step != null && total ? Math.max(0, Math.min(100, (100 * step) / total)) : null;
  const startMs = started ? new Date(started).getTime() : null;
  const elapsedMin = startMs != null && Number.isFinite(startMs) ? Math.max(0, (Date.now() - startMs) / 60000) : null;
  const paceLeft = step != null && total && step > 0 && elapsedMin != null ? Math.max(0, ((total - step) * elapsedMin) / step) : null;
  const queueLeft = row?.est_min != null && elapsedMin != null ? Math.max(0, Number(row.est_min) - elapsedMin) : null;
  const queueFinish = startMs != null && Number.isFinite(startMs) && row?.est_min != null
    ? new Date(startMs + Number(row.est_min) * 60000) : null;
  const finishAt = paceLeft != null ? new Date(Date.now() + paceLeft * 60000) : queueFinish;
  const leftMin = paceLeft ?? queueLeft;
  const dur = (m: number): string => (m < 1 ? 'under a minute' : m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1)} h`);
  const clockAt = (d: Date): string => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    + (d.toDateString() === new Date().toDateString() ? '' : ` ${d.toLocaleDateString(undefined, { weekday: 'short' })}`);
  // the post-training: what a leg does (its seed, its stages in order, how it is read), and the legs that
  // follow this voyage. A leg puts it straight under the question; a pretraining voyage after what it reads.
  const post = d.post || {};
  const pseed = post.seed || null;
  const legs: any[] = Array.isArray(post.legs) ? post.legs : [];
  const stageLine = (s: any): ReactNode => <>
    <b>{s.name || 'stage'}</b> · <span className="mono">{String(s.recipe || '').split('/').pop() || '–'}</span>
    {' · '}{s.books != null ? `${int(s.books)} books` : 'books not counted'} × {int(s.passes ?? 1)} {Number(s.passes ?? 1) === 1 ? 'pass' : 'passes'}
  </>;
  const postSection = post.leg || legs.length ? (
    <VSection title="The post-training" wide>
      {post.leg && pseed ? <>
        <VRow k="seeded from">
          <b>{pseed.run || '–'}</b>
          {pseed.at_step != null ? ` at step ${int(pseed.at_step)}` : ', its last checkpoint'}
          <span className="s"> · {pseed.status
            ? <>{pseed.status}{pseed.step != null ? `, step ${int(pseed.step)}${pseed.total ? ` of ${int(pseed.total)}` : ''}` : ''}{pseed.bpb != null ? ` · bpb ${num(pseed.bpb)}` : ''}</>
            : 'not sailed yet: this leg cannot start before it docks'}</span>
        </VRow>
        <VRow k="inherits">{pseed.mode}{pseed.mode_words ? <span className="s"> · {pseed.mode_words}</span> : null}</VRow>
        <VRow k="the pull">{post.pull?.off
          ? <>off<span className="s"> · scaffold weight 0{post.pull.pins ? `: the seed's ${post.pull.pins} pin${post.pull.pins === 1 ? '' : 's'}${post.pull.riddles ? ` and ${post.pull.riddles} riddle${post.pull.riddles === 1 ? '' : 's'}` : ''} are named but nothing is taught` : ''}</span></>
          : <>on<span className="s"> · scaffold weight {num(post.pull?.weight, 2)}, on the schedule below</span></>}</VRow>
        <VRow k="turns">{post.turns
          ? <>{post.turns.format}{post.turns.shape ? <> · <span className="mono">{post.turns.shape}</span></> : null}</>
          : <span className="s">no turn format: it reads its lists as plain books</span>}</VRow>
        <VRow k="learning rate">{post.lr ?? '–'}{pseed.lr != null ? <span className="s"> · the seed's peak was {pseed.lr}</span> : null}</VRow>
        <div className="qvsubhead">what it does, in order</div>
        <ol className="qvlist qvsteps">{(post.stages || []).map((s: any, i: number) => <li key={i}>{stageLine(s)}</li>)}</ol>
        <div className="qvsubhead">how it is read</div>
        <VRow k="when">{post.read?.when || '–'}{(post.read?.sets || []).length ? <span className="s"> · on <span className="mono">{(post.read.sets as string[]).map((x) => x.split('/').pop()).join(', ')}</span></span> : null}</VRow>
        {(post.read?.evaluators || []).map((e: any) => {
          const opts = Object.entries(e.options || {}).map(([k, v]) => `${k} ${v}`).join(' · ');
          const all = e.seen && e.seen.of > 0 && e.seen.n >= e.seen.of;
          return <VRow k={e.name} key={e.name}>
            {e.what || <span className="s">no description</span>}
            {opts ? <span className="s"> · {opts}</span> : null}
            {e.seen && e.seen.n > 0 ? <div className="qvseen">
              {int(e.seen.n)} of the {int(e.seen.of)} {e.seen.set === 'the official prompts' ? 'official prompts' : <>prompts in <span className="mono">{e.seen.set}</span></>} are in this leg's own training turns{all ? ': none is held out' : ''}.
            </div> : null}
          </VRow>;
        })}
      </> : null}
      {legs.length ? <>
        <div className="qvsubhead">{post.leg ? 'the legs after this one' : 'the legs seeded from this voyage'}</div>
        {legs.map((l: any) => <VRow k={l.mode || 'leg'} key={l.name}>
          <b>{l.name}</b>{l.ship ? <span className="s"> · {l.ship}</span> : null}
          <ol className="qvlist qvsteps">{(l.stages || []).map((s: any, i: number) => <li key={i}>{stageLine(s)}</li>)}</ol>
          <span className="s">
            {l.turns ? `turns ${l.turns} · ` : ''}learning rate {l.lr ?? '–'}
            {(l.evaluators || []).length ? ` · read by ${(l.evaluators as string[]).join(', ')}` : ''}
          </span>
        </VRow>)}
      </> : null}
    </VSection>
  ) : null;
  return (
    <dialog ref={ref} className="qv-dialog" aria-labelledby="qvtitle"
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="qvwrap" onClick={(e) => e.stopPropagation()}>
        <header className="qvhead">
          <div className="qvheadmain">
            <h2 className="qvtitle" id="qvtitle">{row.name}</h2>
            <p className="qvsub">
              {row.ship || '–'}
              {row.expedition ? <> · <a href={`/expeditions/${row.expedition}`}>{row.expedition_name || row.expedition}</a></> : null}
            </p>
          </div>
          <div className="qvbadges">
            <span className={pillCls(tone)}>{row.status || 'queued'}</span>
            {row.sop ? <span className={pillCls('accent')}>SOP v{row.sop}</span> : null}
            {row.preset ? <span className={pillCls('')}>{row.preset}</span> : null}
            {row.seed != null ? <span className={pillCls('')}>seed {row.seed}</span> : null}
          </div>
        </header>
        <button type="button" className="qvclose" onClick={onClose} aria-label="Close">×</button>
          {row.missing ? <div className="qvmissing">The queue names this voyage but its spec file is missing: <span className="mono">{row.spec || '–'}</span></div> : null}
          <div className="qvgrid">
            <VSection title="The question" wide>
              {row.goal ? <p className="qvtext">{row.goal}</p> : <p className="s">The spec states no question.</p>}
              {row.experiment ? <p className="qvtext qvexp"><span className="k">experiment</span> {row.experiment}</p> : null}
            </VSection>

            {post.leg ? postSection : null}

            <VSection title="The run">
              <VRow k="expedition">{row.expedition ? <a href={`/expeditions/${row.expedition}`}>{row.expedition_name || row.expedition}</a> : '–'}</VRow>
              <VRow k="ship">{row.ship || '–'}</VRow>
              <VRow k="SOP">{row.sop ? `v${row.sop}` : '–'}</VRow>
              <VRow k="class">{model.preset || row.preset || '–'}</VRow>
              <VRow k="seed">{row.seed ?? '–'}</VRow>
              <VRow k="learning rate">{lrLine}</VRow>
              {row.fitout?.key ? <VRow k="fitout">{row.fitout.name || row.fitout.key}{row.fitout.variation ? ` · ${row.fitout.variation}` : ''}{row.fitout.stage ? ` · ${row.fitout.stage}` : ''}</VRow> : null}
              <VRow k="spec"><span className="mono">{row.spec || '–'}</span></VRow>
              <VRow k="queue">{row.n != null ? `#${row.n}` : row.status === 'at sea' ? 'at sea now' : '–'}</VRow>
              <VRow k="lane">{row.lane || (row.status === 'at sea' ? 'sailing' : '–')}</VRow>
              <VRow k="starts">{when}</VRow>
              <VRow k="about">{estimate}</VRow>
            </VSection>

            <VSection title="The ship">
              <VRow k="layers">{model.layers ?? '–'}</VRow>
              <VRow k="query heads">{model.heads ?? '–'}</VRow>
              <VRow k="KV heads">{model.kv_heads ? model.kv_heads : 'one per query head'}</VRow>
              <VRow k="width">{model.width ?? '–'}</VRow>
              <VRow k="context">{model.context ? `${int(model.context)} pieces` : '–'}</VRow>
              <VRow k="positions">{model.positions || '–'}</VRow>
              <VRow k="parameters">{params.total != null ? int(params.total) : '–'}</VRow>
              <VRow k="non-embedding">{params.non_embedding != null ? int(params.non_embedding) : '–'}</VRow>
              <VRow k="embedding">{params.embedding != null ? int(params.embedding) : '–'}</VRow>
            </VSection>

            <VSection title="The tokeniser">
              <VRow k="pieces">{tok.kind || '–'} · {tok.vocab != null ? `${int(tok.vocab)} pieces` : '–'}</VRow>
              <VRow k="byte fallback">{tok.byte_fallback ? 'yes' : 'no'}</VRow>
              <VRow k="trained on"><span className="mono">{tok.train_on || '–'}</span></VRow>
              <VRow k="control symbols">{symbols.length ? symbols.map((s) => <span className="sym" key={s}>{s}</span>) : <span className="s">none declared</span>}</VRow>
            </VSection>

            <VSection title="What it reads">
              <VRow k="recipe"><span className="mono">{data.recipe || '–'}</span></VRow>
              <VRow k="passes">{data.passes ?? '–'} {data.passes === 1 ? 'pass' : 'passes'}</VRow>
              <VRow k="clean">{data.clean || 'raw'}</VRow>
              {data.order ? <VRow k="order">{data.order}</VRow> : null}
              {content && (content.version || content.books != null) ? (
                <VRow k="content">
                  {content.version ? <b>{String(content.version).replace(/^ogden-/, 'Ogden ')}</b> : '–'}
                  {content.books != null ? ` · ${int(content.books)} books` : ''}
                  {content.marked ? ` · ${int(content.marked)} with turns marked` : ''}
                  {content.transform ? ` · ${content.transform}` : ''}
                  {content.stamped ? '' : ' · no stamped transform'}
                </VRow>
              ) : null}
              {stages.length ? <VRow k="stages"><ul className="qvlist">{stages.map((s: any, i: number) => (
                <li key={i}><b>{s.name || 'stage'}</b> · <span className="mono">{String(s.recipe || '').split('/').pop() || '–'}</span> · {s.books ?? '?'} books × {s.passes ?? '?'}</li>
              ))}</ul></VRow> : null}
              {refuses.length ? <VRow k="refuses"><ul className="qvlist">{refuses.map((x) => <li key={x} className="mono">{x}</li>)}</ul></VRow> : null}
              {data.opt_in ? <VRow k="opt-in"><span className="qvtext">{data.opt_in}</span></VRow> : null}
            </VSection>

            {post.leg ? null : postSection}

            <VSection title="The scaffold" wide>
              {hasScaffold ? <>
                <VRow k="weight">{sc.weight != null ? Number(sc.weight).toFixed(2) : '–'}</VRow>
                <VRow k="hold">{pct(sc.hold)}</VRow>
                <VRow k="fade">{pct(sc.fade)}</VRow>
                <VRow k="release">{sc.release == null ? 'none' : pct(sc.release)}</VRow>
                <VRow k="pins">{pins.length} head pin{pins.length === 1 ? '' : 's'}{riddles.length ? ` · ${riddles.length} riddle${riddles.length === 1 ? '' : 's'}` : ''}</VRow>
                <div className="qvsubhead">where they sit</div>
                <div className="pinstrip" dangerouslySetInnerHTML={{ __html: pinsStripHtml(pins, layers) }} />
                {riddles.length ? <>
                  <div className="qvsubhead">riddles</div>
                  {riddles.map(([name, r]) => <VRow k={name} key={name}>layer {r.layer} · head {r.head} · {r.items} items · pool {r.pool}</VRow>)}
                </> : null}
                <div className="qvsubhead">the schedule</div>
                <div dangerouslySetInnerHTML={{ __html: scheduleLine(d.schedule) }} />
              </> : <p className="s">No scaffold: every head is left to the corpus, so the loss and the cards it forms are the measurement.</p>}
            </VSection>

            <VSection title="The training">
              <VRow k="optimiser">{optim.name || '–'}</VRow>
              <VRow k="learning rate">{lrLine}</VRow>
              <VRow k="warm-up">{optim.warmup_steps != null ? `${int(optim.warmup_steps)} steps` : '–'}</VRow>
              <VRow k="batch">{optim.batch_tokens != null ? `${int(optim.batch_tokens)} tokens` : '–'}</VRow>
              <VRow k="schedule">{optim.schedule || '–'}{optim.min_lr_ratio != null ? ` · min ${pct(optim.min_lr_ratio)}` : ''}</VRow>
              <VRow k="grad clip">{optim.grad_clip ?? '–'}</VRow>
              <VRow k="precision">{optim.precision || '–'}</VRow>
              <VRow k="steps">{totalSteps != null ? int(totalSteps) : 'known once it sails'}</VRow>
            </VSection>

            <VSection title="Its readings" wide>
              {readings ? <>
                <VRow k="progress">
                  <div className="qvprogress">
                    {pctDone != null && total != null && step != null ? <progress className="qvbar" max={total} value={step} aria-label="voyage progress" /> : null}
                    <b>{pctDone != null ? `${pctDone.toFixed(1)}%` : '–'}</b>
                    <span className="s">{step != null ? `step ${int(step)}${total != null ? ` of ${int(total)}` : ''}` : 'not started'}</span>
                  </div>
                </VRow>
                <VRow k="finish">
                  {finishAt ? <><b>{clockAt(finishAt)}</b>{leftMin != null ? <span className="s"> · about {dur(leftMin)} left{paceLeft != null ? ' at this pace' : ''}</span> : null}</> : <span className="s">no estimate yet</span>}
                </VRow>
                {queueFinish && finishAt && paceLeft != null && queueLeft != null && Math.abs(queueFinish.getTime() - finishAt.getTime()) > 5 * 60000
                  ? <VRow k="queue est."><span className="s">{clockAt(queueFinish)} · about {dur(queueLeft)} left by the queue's estimate</span></VRow>
                  : null}
                <VRow k="loss">{num(readings.loss)}</VRow>
                <VRow k="bpb">{num(readings.bpb)}</VRow>
                <VRow k="chaining">{readings.chaining == null ? '–' : `${readings.chaining > 0 ? '+' : ''}${num(readings.chaining)}`}</VRow>
                <VRow k="tokens read">{readings.tokens_seen != null ? int(readings.tokens_seen) : '–'}</VRow>
                <VRow k="started">{readings.started ? new Date(readings.started).toLocaleString() : '–'}</VRow>
                <VRow k="shapes">parts of speech {num((readings.shapes || {}).upos)} · keyed words {num((readings.shapes || {}).keyed)}</VRow>
                {rcards.length ? <>
                  <div className="qvsubhead">the cards</div>
                  <div className="qvcards">{rcards.map((c: any, i: number) => {
                    const lit = c.now != null && c.mark != null && c.now >= c.mark;
                    return <span key={`${c.card}-${c.layer}-${c.head}-${i}`} className={`cardlight${lit ? ' lit' : ''}`}
                      title={`${c.card} at layer ${c.layer}, head ${c.head}: now ${num(c.now, 2)} against its mark ${num(c.mark, 2)}`}>
                      <b>{c.card}</b> <i>L{c.layer} H{c.head}</i> {num(c.now, 2)}/{num(c.mark, 2)}
                    </span>;
                  })}</div>
                </> : null}
              </> : <p className="s">No readings yet: a queued voyage writes its readings once it sails.</p>}
            </VSection>
          </div>
          <div className="qvfoot">
            {row.expedition ? <a className={btnCls('outline', '')} href={`/expeditions/${row.expedition}/plan`}>the expedition's plan →</a> : null}
            <span className="s">Spec: <span className="mono">{row.spec || '–'}</span></span>
          </div>
        </div>
    </dialog>
  );
}

export default function Expeditions() {
  const [path, go] = usePath();
  const route = parseExpeditionRoute(path);
  const isOverview = route.kind === 'overview';
  const isQueue = route.kind === 'queue';
  const isList = route.kind === 'list';
  const isVoyage = route.kind === 'voyage';
  const isTable = route.kind === 'table';
  const onPage = isOverview || isQueue || isList || isVoyage || isTable;

  // one route for the whole page, one poll for the expeditions (the cards and one expedition both read it)
  const expsApi = useApi<Expedition[]>(onPage ? '/api/expeditions' : null, 60000);
  const ladderApi = useApi<any>(isQueue || isList || isVoyage || isTable ? '/api/ladder' : null, 300000);
  // the overview tab needs this payload too, or it sits on 'reading the expeditions…' for ever
  const ovApi = useApi<any>(isOverview || isQueue || isList || isVoyage ? '/api/expeditions/overview' : null, 15000);
  // the one expedition the open ones prepare: its fleet, its master charter and every goal's part
  // (12 November). A signature answers with the payload again; that copy stands until the next poll.
  const launchApi = useApi<LaunchPayload>(isOverview || isList ? '/api/launch' : null, 30000);
  const [launchSigned, setLaunchSigned] = useState<LaunchPayload | null>(null);
  useEffect(() => { setLaunchSigned(null); }, [launchApi.data]);
  const launch = launchSigned || launchApi.data;
  const queueApi = useApi<any>(isQueue ? '/api/queue' : null, 15000);
  const prioApi = useApi<any>(isQueue ? '/api/expedition_priority' : null, 0);
  // the queue row whose card is open: its identity, so a poll that reorders the queue cannot swap it
  const [queuePick, setQueuePick] = useState<string | null>(null);
  const queueRow = useMemo(() => (queuePick ? (queueApi.data?.rows || []).find((r: any) => queueKey(r) === queuePick) || null : null), [queueApi.data, queuePick]);
  useEffect(() => { if (!isQueue) setQueuePick(null); }, [isQueue]);
  useEffect(() => { if (queuePick && queueApi.data && !queueRow) setQueuePick(null); }, [queuePick, queueApi.data, queueRow]);
  const onQueueClick = (e: ReactMouseEvent): void => {
    const t = e.target as HTMLElement;
    if (t.closest('a,button,summary,.info,input,select,textarea')) return;
    const tr = t.closest('#queuetable tr[data-qi], .qlanes [data-qi]') as HTMLElement | null;
    if (!tr) return;
    const row = (queueApi.data?.rows || [])[Number(tr.dataset.qi)];
    if (row) setQueuePick(queueKey(row));
  };
  const onQueueKey = (e: ReactKeyboardEvent): void => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const t = e.target as HTMLElement;
    if (t.closest('a,button,summary,.info')) return;
    const tr = t.closest('#queuetable tr[data-qi], .qlanes [data-qi]') as HTMLElement | null;
    if (!tr) return;
    e.preventDefault();
    const row = (queueApi.data?.rows || [])[Number(tr.dataset.qi)];
    if (row) setQueuePick(queueKey(row));
  };
  const exps = expsApi.data || [];
  const rungs = useMemo(() => (Array.isArray(ladderApi.data?.rungs) ? ladderApi.data.rungs : []), [ladderApi.data]);
  const states = useMemo(() => Object.fromEntries((ovApi.data?.expeditions || []).map((e: any) => [e.key, e.status])) as Record<string, string>, [ovApi.data]);
  // The standards split in two: the one in play (at sea, and anything newer than it) is the Overview's
  // subject; the ones whose voyages are home sit with every expedition on Plans (10 November, Justin:
  // "move ogden from here to the plans tab").
  const [, pastSops] = useMemo(() => {
    const all: any[] = (ovApi.data?.sops || []) as any[];
    if (!all.length) return [[], []] as [any[], any[]];
    const atSea = all.filter((e) => Number(e.at_sea) > 0);
    const floor = (atSea.length ? atSea : all).map((e) => String(e.version)).sort(sopVersionCmp).pop() as string;
    const live = all.filter((e) => Number(e.at_sea) > 0 || sopVersionCmp(String(e.version), floor) >= 0);
    const past = all.filter((e) => !live.includes(e)).sort((a, b) => sopVersionCmp(String(b.version), String(a.version)));
    return [live, past] as [any[], any[]];
  }, [ovApi.data]);
  // the state enums (S2's view) said plainly under each band's heading
  const stateTally = (list: Expedition[]): string => {
    const n: Record<string, number> = {};
    for (const e of list) {
      const st = states[e.key] || e.status || 'unknown';
      n[st] = (n[st] || 0) + 1;
    }
    return Object.entries(n).map(([st, c]) => `${c} ${st}`).join(' · ');
  };
  // The landing is filtered by status, not by recency: what is still open is the page, and what is
  // retired is folded away at the bottom (Justin, 11 November: "i only want it filtered by open and then
  // retired minimised at the bottom"). Retired is the fleet's own word (`status: done`), which is set
  // only when every goal is settled — so the folded group is the record, not a work list.
  const planGroups = useMemo(() => {
    const open = exps.filter((e) => e.status !== 'done');
    const retired = exps.filter((e) => e.status === 'done');
    // at sea first, then under way, then in port: the same order the coordinator reads
    const rank = (k: string): number => (states[k] === 'at sea' ? 0 : states[k] === 'under way' ? 1 : 2);
    open.sort((a, b) => rank(a.key) - rank(b.key));
    retired.sort((a, b) => a.name.localeCompare(b.name));
    return [
      {
        key: 'open',
        title: 'Preparation',
        note: `${open.length} still settling the charter · ${stateTally(open)}`,
        list: open,
        open: true,
      },
      {
        key: 'retired',
        title: 'Settled preparation',
        note: `${retired.length} closed, every goal settled · open one to read what it learned`,
        list: retired,
        open: false,
      },
    ].filter((g) => g.list.length);
  }, [exps, states]);
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
  const [qview, setQview] = useState<'glance' | 'every'>(route.qview === 'every' ? 'every' : 'glance');
  const [qtab, setQtab] = useState<'queue' | 'planning'>(route.qview === 'planning' ? 'planning' : 'queue');
  useEffect(() => { if (isQueue) setQtab(route.qview === 'planning' ? 'planning' : 'queue'); }, [isQueue, route.qview]);
  useEffect(() => { if (isQueue) setQview(route.qview === 'every' ? 'every' : 'glance'); }, [isQueue, route.qview]);

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
  // The shipbuilder is Schi'mint's; it is fetched and rendered into the expedition's own tab.
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
      await mountShipbuilder(el, { key: 'schimint', name: "Schi'mint", ship_builder: 'the ship builder' } as any, expTab, true, v.sop);
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
      <SectionNav />
      {/* ------------------------------------------------ the queue and the expeditions */}
      <div className={`section${isOverview || isQueue || isList ? ' active' : ''}`} id="voyages">
        <h1>{isQueue
          ? <>The queue <span className="q">what sails next, in order, as the S2 coordinator takes it from the Mac lane; open a ship to follow its training</span></>
          : <>Overview <span className="q">one expedition: the fleet it launches, the master charter it sails under, and the preparation that settles it</span></>}</h1>
        <div className={`vtab${isOverview || isList ? ' active' : ''}`} data-vtab="expeditions">
          {launch ? <Launch data={launch} onChange={setLaunchSigned} /> : launchApi.error ? (
            <div dangerouslySetInnerHTML={{ __html: EMPTY(`the launch could not be read: ${esc(launchApi.error)}`) }} />
          ) : null}
          {expsApi.data ? (
            <>
              {planGroups.map((g) => (
                <details key={g.key} className="expgroup" id={`plans-${g.key}`} open={g.open}>
                  <summary><h2 className="band">{g.title} <span className="q">{g.note}</span></h2></summary>
                  <div dangerouslySetInnerHTML={{ __html: expeditionCardsHtml(g.list, states, ovApi.data, launch?.preparations) }} />
                </details>
              ))}
              {pastSops.length > 0 && (
                <details className="expgroup paststandards" id="paststandards">
                  <summary><h2 className="band">Earlier drafts <span className="q">{pastSops.map((s: any) => `${s.name}${s.expedition_name ? ` · ${s.expedition_name}` : ''}`).join(', ')} — the rework so far: the standards whose voyages are home, and what each went out to find</span></h2></summary>
                  <div dangerouslySetInnerHTML={{ __html: sopCardsHtml({ sops: pastSops }) }} />
                </details>
              )}
              <details className="archive" id="expeditiontableref">
                <summary>The preparations as a table <span className="note">one row each, for scanning the counts and statuses</span></summary>
                <div dangerouslySetInnerHTML={{ __html: expeditionTableHtml(exps, states, ovApi.data) }} />
              </details>
            </>
          ) : (
            <div dangerouslySetInnerHTML={{ __html: EMPTY('reading the expeditions…') }} />
          )}
        </div>
        <div className={`vtab${isQueue ? ' active' : ''}`} data-vtab="queue">
          <TabNav
            id="queuenav"
            ariaLabel="queue sections"
            tablist
            items={[
              { key: 'queue', label: 'Queue', href: '/expeditions/queue', active: qtab === 'queue', onClick: () => go('/expeditions/queue') },
              { key: 'planning', label: 'Planning', href: '/expeditions/queue/planning', active: qtab === 'planning', onClick: () => go('/expeditions/queue/planning') },
            ]}
          />
          {qtab === 'planning' ? (
            prioApi.data
              ? <PriorityPanel rows={prioApi.data.expeditions || []} />
              : <div className={emptyCls()}>reading the priorities…</div>
          ) : (
          <div className="qview active" data-qview="every">
            <section className={cardCls(false, 'panel')} id="queuepanel">
              <h2>The queue <span className="note">every voyage still to sail, in the order it sails (specs/queue.txt), with its goal: the question its spec asks, or its experiment's where it asks none, and the fitout it was compiled from (its census variation and stage); the starts are the median of like voyages scheduled with the Mac's seats, and ≥ marks a line behind one with no time yet. Click a voyage for its card</span></h2>
              {queueApi.data ? <div onClick={onQueueClick} onKeyDown={onQueueKey} dangerouslySetInnerHTML={{ __html: queueLanesHtml(queueApi.data) }} /> : null}
              <div className="scroll queuescroll" onClick={onQueueClick} onKeyDown={onQueueKey}><table id="queuetable" data-nosort>
                <thead><tr><th>#</th><th>voyage</th><th>ship</th><th title="the SOP the voyage is built to: its content, tokeniser, parameters, phases and depth">SOP</th><th title="how far the voyage has come: its training step of the steps its schedule sets; a line that has not sailed reads 0%">% complete</th><th title="about when it starts, in your local timezone: the median of like voyages, scheduled with the Mac's seats (two 300k may share; a 1m or 9m holds the lane); ≥ where a voyage ahead has no time yet">starts</th><th title="about when it sails: the median of like voyages, scheduled with the Mac's seats; ≥ where a voyage ahead has no time yet">sails in</th></tr></thead>
                <tbody dangerouslySetInnerHTML={{ __html: queueApi.data ? queueRowsHtml(queueApi.data, rungs) : `<tr><td colspan="7" class="${emptyCls(true)}">reading the queue…</td></tr>` }} />
              </table></div>
            </section>
          </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------ one expedition */}
      <div className={`section${isVoyage ? ' active' : ''}`} id="voyage">
        <h1><a className={crumbCls('back')} href="/expeditions" onClick={(e) => { e.preventDefault(); go('/expeditions/queue'); }}>← expeditions</a>{' '}
          <span id="voyagetitle">{v ? v.name : expsApi.data ? `no expedition called ${route.key}` : 'loading…'}</span>{' '}
          <span id="voyagestatus" dangerouslySetInnerHTML={{ __html: v ? expPill(states[v.key], v) : '' }} />{' '}
          </h1>
        <TabNav
          id="expnav"
          ariaLabel="expedition sections"
          items={[
            ['overview', 'Overview'], ['at-sea', 'At sea'], ['findings', 'Findings'], ['fleet', 'Fleet'], ['runs', 'Runs'],
            ['plan', 'Plan'], ['training', 'Training'], ['fitting', 'Fitting Out'], ['inside', 'Inside'],
          ].map(([k, label]) => ({
            key: k,
            label,
            href: `/expeditions/${route.key}${k === 'overview' ? '' : '/' + k}`,
            active: expTab === k,
            hidden: tabOk[k] === false,
            data: { 'data-etab': k },
            onClick: () => go(`/expeditions/${route.key}${k === 'overview' ? '' : '/' + k}`),
          }))}
        />

        {/* Overview */}
        <div className={`etab${expTab === 'overview' ? ' active' : ''}`} data-etab="overview">
          {/* the goal first (11 November, Justin: "where should i see goals for the expeditions"): it was on
              the cards that open this page and nowhere on the page itself */}
          <section className={cardCls(false, 'panel')} id="voyagegoal" hidden={!v?.goal}>
            <h2>The goal <span className="note">what the expedition went out to find and why, as it was set (fleet.py)</span></h2>
            {(() => {
              // numbered aims in the text, "(1) ... (2) ...", read as a list under what comes before them;
              // an expedition that lists its goals one by one (fleet.py `goals`) shows them as a table
              // instead, each with why it is wanted
              const parts = String(v?.goal || '').split(/\s*\((\d+)\)\s+/);
              const aims: string[] = [];
              for (let i = 1; i + 1 < parts.length; i += 2) aims.push(parts[i + 1]);
              const goals = v?.goals || [];
              return (
                <>
                  <p className="goaltext">{parts[0]}</p>
                  {goals.length ? (
                    <div className="scroll">
                      <table id="voyagegoals" className="goaltable" data-nosort>
                        <thead><tr><th>#</th><th>goal</th><th>what it is</th><th>why we want it</th></tr></thead>
                        <tbody>
                          {goals.map((g, i) => (
                            <tr key={g.text}>
                              <td className="s">{i + 1}</td>
                              <td><b>{g.text}</b></td>
                              <td className="s">{g.detail || '–'}</td>
                              <td>{g.why || <span className="s">not written down yet</span>}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : aims.length > 1 ? <ol className="sopgoals goaltext">{aims.map((a, i) => <li key={i}>{a}</li>)}</ol> : aims.length ? <p className="goaltext">(1) {aims[0]}</p> : null}
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
      {queueRow ? (queueRow.kind === 'step'
        ? <QueueStepDialog row={queueRow} onClose={() => setQueuePick(null)} />
        : <QueueVoyageDialog row={queueRow} onClose={() => setQueuePick(null)} />) : null}
    </div>
  );
}

// `learned` and the star headline are prose, not markup: escape them here, as the old DOM did with textContent
function escapeText(s: string): string {
  return String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string));
}
