// The ship builder (UI.md "Ship builder"; #/harbours/phaleron/shipbuilder): who signs the supplies,
// and the SOP's variables in two legs (training and parts) with their subtabs. A controller on the
// harbour island: it owns its own DOM, wires its controls once, and survives the ladder's poll.

import { big, esc, get, postJSON } from '../../lib/format';
import { checkCls, emptyCls, fieldCls, pillCls } from '../../lib/ui';
import { artImg } from './helpers';

type Payload = any;

const LIB_SUMMARY: Record<string, any> = {};
let shipbuilderPhase = 'pretraining', shipbuilderActive = 'training';

const SOP_CATS = [
  { key: 'library', name: 'Library', keys: ['content', 'readings'],
    note: 'what the ship reads: the content (recipe, cleaning, passes, order, refusals, tokeniser) and the readings it is judged by' },
  { key: 'depth', name: 'Star chart', keys: ['cards', 'pinning', 'chart'],
    note: 'depth is how the stars are followed: the cards, the pinning table (which card sits in which layer for each size), and the ten-point star chart' },
  { key: 'training', name: 'Training', keys: ['content', 'readings', 'cards', 'pinning', 'chart', 'phases', 'post'],
    note: 'what the ship does: what it reads and what it must build, the phases it sails, and the post-training stage' },
  { key: 'scoring', name: 'Scoring', keys: [],
    note: 'how the ships score: the ladder\'s chaining against Qwen3 4B, and each ship rated on the four suits' },
  { key: 'parts', name: 'Parts', keys: ['parameters', 'sizes', 'embeddings'],
    note: 'what the ship is made of: the shape and the training physics, and the embedding table every token starts in' },
];
const SOP_TABS = [
  { key: 'library', name: 'Library' },
  { key: 'training', name: 'Training', sub: [['content', 'Content'], ['process', 'Process']] },
  { key: 'parts', name: 'Parts', sub: [['physical', 'Physical'], ['embeddings', 'Embeddings']] },
  { key: 'scoring', name: 'Scoring' },
];
const SOP_EDIT = new Set(['library', 'training', 'parts']);

export const shipbuilderKey = (harbour: string | null): boolean => harbour === 'phaleron';

/** Mount the ship builder into `el` for one harbour. Reuses itself when the same harbour is already
 *  built (the island calls this after every poll), and is cleared by the ships view. */
export async function mountShipbuilder(
  el: HTMLElement, h: Payload, section?: 'training' | 'fitting' | 'charting', embedded = false, version?: string | null,
): Promise<void> {
  if (!h || !h.key || h.key !== 'phaleron' || !h.ship_builder) { el.innerHTML = ''; return; }
  if (el.dataset.built === h.key && el.querySelector('.hmpanel')) return;
  el.dataset.built = h.key;
  el.innerHTML = `<div class="s">reading the ship builder…</div>`;
  let d: Payload;
  try { d = await get('/api/shipbuilder?harbour=' + encodeURIComponent(h.key)); } catch (e) {
    el.innerHTML = `<div class="${emptyCls()}">the ship builder could not be read: ${esc(String((e as Error).message || e))} (restart <span class="mono">thorp dash</span> if this server predates the panel)</div>`;
    el.dataset.built = '';
    return;
  }
  const s = d.sop || {}, vs = s.versions || [], std = s.standards || {}, cur = s.current;
  const hh = (d.harbour as Payload) || h;
  const opts = vs.map((v: string) => `<option value="${esc(v)}"${v === cur ? ' selected' : ''}>v${esc(v)}${v === cur ? ' · in force' : ''}</option>`).join('');
  const SECTION_NAME: Record<string, string> = { training: 'Training', fitting: 'Fitting Out', charting: 'Charting' };
  // the trail up: the shipyard sits beside the harbours, not under one, so it is harbours > shipyard > section
  const crumb = embedded ? '' : `<div class="bcrumb"><a class="crumb" href="/harbours">harbours</a> <a class="crumb" href="/shipyard">shipyard</a> <b>${esc(section ? (SECTION_NAME[section] || section) : 'shipbuilder')}</b></div>`;
  el.innerHTML = `<section class="hmpanel">
    ${crumb}
    <figure class="sbbanner">${artImg('shipyard', 'shipbuilderart')}<figcaption><b>The shipyard</b> <span>· the SOP: what the ship reads, what it must build, and what it is made of</span></figcaption></figure>
    <h2>Shipyard <span class="s">${esc(hh.ship_builder || 'unnamed')} signs the supplies: the two legs' stages, and the SOP variables below that carry them</span></h2>
    <div class="phasenav" id="phasenav" role="tablist"></div>
    <div class="phasebody" id="phasebody"></div>
    <div class="hmgrid">
      <div class="hmfacts">
        <div><span class="k">Harbour</span> <b>${esc(hh.name)}</b></div>
        <div><span class="k">Depth</span> ${hh.depth ? big(hh.depth) + ' parameters' : 'no bottom'}</div>
        <div><span class="k">Lane</span> ${esc(hh.lane === 'mac' ? 'the Mac lane (MLX)' : 'the Vast lane (torch on CUDA)')}</div>
        <div><span class="k">Ship builder</span> ${esc(hh.ship_builder || '–')}</div>
        <label class="k" for="hmversion">SOP version</label>
        <select class="sel" id="hmversion">${opts}</select>
        <div class="hmvars">The standard in tabs: <b>Library</b> (what it reads), <b>Star chart</b> (how the stars are followed), <b>Physical</b> (the model and its training). Saving writes a <b>new</b> version; the current one stays in force until a voyage names it.</div>
        <div class="hmvars" id="hmabout"></div>
      </div>
      <div class="hmedit">
        <div class="fbrow"><label class="s" for="hmadopted">adopted</label><input type="text" class="${fieldCls('w-full')}" id="hmadopted" value="${esc('defined at ' + hh.name + ' by ' + (hh.ship_builder || 'the ship builder'))}"></div>
        <div class="atsea" id="hmatsea" hidden></div>
        <div class="sopnav" id="sopnav" role="tablist"></div>
        <div class="sopnav subsop" id="sopsub" role="tablist"></div>
        <div class="sopnote" id="sopnote"></div>
        <div class="hmform">
          <div class="hmrow" id="hmchoices">
            <label class="hmfield"><span class="k">embedding</span><select class="sel" id="hmembed" title="the locked embedding version this standard chooses"></select></label>
            <div class="hmfield grow"><span class="k">sizes to sail</span><span id="hmsizes" class="hmsizes"></span></div>
          </div>
          <div class="hmrow" id="hmbranchrow" hidden>
            <label class="hmfield"><span class="k">branch</span><select class="sel" id="hmbranch" title="the branch the plan reads"></select></label>
            <label class="hmfield"><span class="k">variation</span><select class="sel" id="hmvariation" title="the variation of that branch"></select></label>
            <span class="hmhint">the branch and variation the plan reads; then the makeup taken out of it</span>
          </div>
          <div class="hmrow hmfilters" id="hmfilters" hidden>
          <label class="hmfield"><span class="k">years</span><span class="hmyears"><input id="hmyearfrom" class="${fieldCls('w-20')}" type="number" min="1000" max="2100" placeholder="from"> <i>–</i> <input id="hmyearto" class="${fieldCls('w-20')}" type="number" min="1000" max="2100" placeholder="to"></span></label>
          <label class="hmfield"><span class="k">language</span><select class="sel" id="hmlang" multiple size="4"></select></label>
          <label class="hmfield"><span class="k">kind</span><select class="sel" id="hmkind" multiple size="4"></select></label>
          <label class="hmfield"><span class="k">source</span><select class="sel" id="hmsource" multiple size="4"></select></label>
          <label class="hmfield"><span class="k">voice</span><select class="sel" id="hmvoice" multiple size="4"></select></label>
        </div>
        <div id="soplib" class="libsum" hidden></div>
        <div id="sopstage" class="depthsum" hidden></div>
        <div id="sopphases" class="depthsum" hidden></div>
        <div id="sopshape" class="libsum" hidden></div>
        <div id="sopembed" class="libsum" hidden></div>
        <div id="sopladder" class="libsum" hidden></div>
        <div id="sopsuits" class="libsum" hidden></div>
        <div id="sopdepth" class="depthsum" hidden></div>
        <textarea id="hmsop" spellcheck="false" aria-label="the SOP variables in this tab"></textarea>
        <div class="fbactions"><button id="hmsave">Save as a new SOP version</button><span id="hmmsg" class="fbmsg"></span></div>
      </div>
    </div></section>`;
  const ta = document.getElementById('hmsop') as HTMLTextAreaElement;
  const sel = document.getElementById('hmversion') as HTMLSelectElement;
  // an expedition has one standard: open on it rather than on whatever is in force (9 November)
  if (version && std[version]) sel.value = version;
  const msg = document.getElementById('hmmsg') as HTMLElement;
  // a lane may have several seats now: say which ships are at sea, not just that one is
  const atsea = document.getElementById('hmatsea') as HTMLElement | null;
  const paintAtSea = async (): Promise<void> => {
    if (!atsea) return;
    try {
      const r = await fetch('/api/lanes');
      const d = await r.json();
      const seats: any[] = d.seats || [];
      if (!seats.length) {
        atsea.hidden = true;
        return;
      }
      atsea.hidden = false;
      atsea.innerHTML = `<span class="k">At sea</span> ${seats
        .map((x) => `<span class="seat"><b>${x.name}</b>${x.since ? ` <span class="s">since ${String(x.since).slice(11, 16)}</span>` : ''}</span>`)
        .join('')}<span class="s">${seats.length} of ${d.mac_seats || 1} Mac seats · ${d.vast_seats || 1} on Vast</span>`;
    } catch {
      atsea.hidden = true;
    }
  };
  void paintAtSea();
  const atSeaTimer = setInterval(paintAtSea, 20000);
  const branchSel = document.getElementById('hmbranch') as HTMLSelectElement | null;
  const variationSel = document.getElementById('hmvariation') as HTMLSelectElement | null;
  const yearFrom = document.getElementById('hmyearfrom') as HTMLInputElement | null;
  const yearTo = document.getElementById('hmyearto') as HTMLInputElement | null;
  const langSel = document.getElementById('hmlang') as HTMLSelectElement | null;
  const kindSel = document.getElementById('hmkind') as HTMLSelectElement | null;
  const sourceSel = document.getElementById('hmsource') as HTMLSelectElement | null;
  const voiceSel = document.getElementById('hmvoice') as HTMLSelectElement | null;
  let browse: Payload | null = null;
  // SOP versions with a voyage at sea are locked: a version carrying a ship out cannot be changed
  // (the API refuses it too, so this is the visible half of one rule).
  const locked: Record<string, string> = ((d.sop || {}) as any).locked || {};
  const only = section === 'fitting' ? 'parts' : section === 'charting' ? 'scoring' : section === 'training' ? 'training' : null;
  if (only) {
    // a section page is only its section: the builder's heading and the two-leg phase chrome are
    // navigation/context for the whole SOP, not for Training, Fitting Out or Charting alone.
    el.querySelector<HTMLElement>('h2')?.remove();
    el.querySelector<HTMLElement>('.sbbanner')?.remove();
    if (only !== 'training') {  // Training's two legs are its primary tabs (9 November)
      document.getElementById('phasenav')?.remove();
      document.getElementById('phasebody')?.remove();
    }
    // the builder's own facts (harbour, depth, lane, ship builder, the SOP version and its about) and
    // the adopted line belong to the whole standard, not to one section: hidden here, kept in the DOM
    // so the version selector the rest of the code reads is still there (9 November, Justin: "remove this")
    const facts = el.querySelector<HTMLElement>('.hmfacts');
    if (facts) {
      // keep the SOP version selector — the page is useless without a way to switch standard — and
      // drop the harbour/depth/lane/ship-builder rows and the prose around it
      for (const node of Array.from(facts.children) as HTMLElement[]) {
        const isSelector = node.id === 'hmversion' || node.getAttribute('for') === 'hmversion';
        if (!isSelector) node.style.display = 'none';
      }
    }
    const adopted = document.getElementById('hmadopted');
    const adoptedRow = adopted ? (adopted.closest('.fbrow') as HTMLElement | null) : null;
    if (adoptedRow) adoptedRow.style.display = 'none';
  }
  const initial = only || shipbuilderActive || 'training';
  shipbuilderActive = initial;
  let draft: Payload = {}, active = initial, cats = SOP_CATS, phase = shipbuilderPhase;
  let shipbuilderSub = 'content';
  const journey = d.journey || null;

  const drawPhase = (): void => {
    const nav = document.getElementById('phasenav'), body = document.getElementById('phasebody');
    if (!nav || !body) return;
    const tabs: [string, string, string][] = [['pretraining', 'Pretraining', 'outbound'], ['posttraining', 'Posttraining', 'return']];
    nav.innerHTML = tabs.map(([k, name, leg]) => `<button type="button" class="phasebtn${phase === k ? ' active' : ''}" data-phase="${k}" role="tab" aria-selected="${phase === k}">${name} <span class="s">${leg}</span></button>`).join('');
    nav.querySelectorAll<HTMLElement>('.phasebtn').forEach((b) => { b.onclick = () => { phase = b.dataset.phase!; shipbuilderPhase = phase; drawPhase(); showTab(active); }; });
    if (!journey) { body.innerHTML = '<div class="s">no journey is recorded for this harbour yet</div>'; return; }
    const leg = journey[phase] || {}, stages = leg.stage || [];
    const post = phase === 'posttraining' ? postOf() : null;
    body.innerHTML = `<div class="phasehead"><span class="k">${phase}</span> <span class="s">${esc(leg.leg || '')}</span></div>
      <div class="s">${phase === 'posttraining'
        ? post ? `${stages.length} stage${stages.length === 1 ? '' : 's'} · ${esc(post.name || 'posttraining')}; the Star chart and Physical attributes are shared.` : 'Posttraining is not in this SOP: Library, Stages and Phases are empty. The Star chart and Physical attributes are shared.'
        : `${stages.length} stage${stages.length === 1 ? '' : 's'} · the tabs below apply to this leg; physical stays shared.`}</div>`;
  };
  const catOf = (key: string): Payload => cats.find((c) => c.key === key) || cats[0];
  const readDraft = (): boolean => {
    if (!SOP_EDIT.has(active)) return true;
    const c = catOf(active); let got: Payload;
    try { got = JSON.parse(ta.value); } catch (e) { msg.className = 'fbmsg bad'; msg.textContent = 'not JSON: ' + (e as Error).message; return false; }
    if (!got || typeof got !== 'object' || Array.isArray(got)) { msg.className = 'fbmsg bad'; msg.textContent = 'this tab is a JSON object'; return false; }
    for (const k of c.keys) { if (k in got) draft[k] = got[k]; else delete draft[k]; }
    return true;
  };
  const showTab = (key: string): void => {
    active = key; shipbuilderActive = key;
    const branchRow = document.getElementById('hmbranchrow');
    const filterRow = document.getElementById('hmfilters');
    const onLib = key === 'library' || key === 'training';
    if (branchRow) branchRow.hidden = !onLib || !browse;
    if (filterRow) filterRow.hidden = !onLib || !browse;
    if (onLib && browse) renderSelection();
    const c = catOf(key);
    const editor = SOP_EDIT.has(key);
    document.querySelectorAll<HTMLElement>('#sopnav .sopbtn').forEach((b) => { const on = b.dataset.sop === key; b.classList.toggle('active', on); b.setAttribute('aria-selected', String(on)); });
    const sub = (SOP_TABS.find((t) => t.key === key) || {}).sub || [];
    if (sub.length && !sub.some(([k]) => k === shipbuilderSub)) shipbuilderSub = sub[0][0];
    const note = key === 'training' ? (shipbuilderSub === 'process'
        ? 'the stages of this leg, in order, with their tokens and cards, and the probe site: the dynamic schedule that tests whether the heads respond'
        : 'what the ship reads on this leg and the embedding table every token starts in')
      : key === 'scoring' ? 'how the ships score: the ladder against Qwen3 4B, and each ship on the four suits — copying, position, comparing, carrying'
      : key === 'parts' ? (shipbuilderSub === 'embeddings'
        ? 'the embedding table every token starts in: vocabulary x width, tied to the output'
        : 'the physical attributes are shared by both legs: one model, one set of parameters and sizes')
      : c.note;
    const noteEl = document.getElementById('sopnote');
    if (noteEl) noteEl.textContent = note;
    if (editor) ta.value = JSON.stringify(Object.fromEntries(c.keys.filter((k: string) => k in draft).map((k: string) => [k, draft[k]])), null, 1);
    ta.hidden = !editor;
    const lockName = locked[sel.value] || '';
    ta.disabled = !!lockName;
    const save = document.getElementById('hmsave'); if (save) save.hidden = !editor || !!lockName;
    const lockMsg = document.getElementById('hmmsg');
    if (lockMsg && lockName) {
      lockMsg.className = 'fbmsg bad';
      lockMsg.textContent = `v${sel.value} is locked: ${lockName} is at sea on it. It unlocks when that ship docks.`;
    } else if (lockMsg && lockMsg.classList.contains('bad') && / is locked: /.test(lockMsg.textContent || '')) {
      lockMsg.className = 'fbmsg'; lockMsg.textContent = '';
    }
    // Training is two tabs under two legs (9 November): Content is what it reads and the table it
    // starts in; Process is the stages it sails (the fade) and the probe site (the dynamic schedule).
    const training = key === 'training';
    const content = training && shipbuilderSub === 'content';
    const process = training && shipbuilderSub === 'process';
    void drawLibSummary(key === 'library' || content ? stageLibrary() : '');
    drawStarChart(process);
    drawStages(process);
    void drawPhases(process);
    drawPhysical(key === 'parts' && shipbuilderSub === 'physical');
    drawEmbeddings(content || (key === 'parts' && shipbuilderSub === 'embeddings'));
    void drawLadderChaining(key === 'scoring');
    void drawSuits(key === 'scoring');
    const subnav = document.getElementById('sopsub');
    if (subnav) {
      subnav.hidden = !sub.length;
      subnav.innerHTML = sub.map(([k, n]) => `<button type="button" class="sopbtn sub${k === shipbuilderSub ? ' active' : ''}" data-sub="${esc(k)}" role="tab" aria-selected="${k === shipbuilderSub}">${esc(n)}</button>`).join('');
      subnav.querySelectorAll<HTMLElement>('.sopbtn').forEach((b) => { b.onclick = () => {
        shipbuilderSub = b.dataset.sub!;
        showTab(key);  // the leg is the phase nav; Content and Process only switch the panels
      }; });
    }
  };
  const drawSuits = async (on: boolean): Promise<void> => {
    const box = document.getElementById('sopsuits'); if (!box) return;
    box.hidden = !on; if (!on) return;
    let d2: Payload; try { d2 = await get('/api/suit_ratings'); } catch { return; }
    const rows = (d2.ships || []).map((x: any) => {
      const cell = (v: number | null) => v == null ? '<span class="s">–</span>' : `<b>${v.toFixed(2)}</b>`;
      const label = x.run && x.run.startsWith('deck-') ? `<span class="mono">${esc(x.size)}</span> <span class="s">foreign</span>` : `<span class="mono">${esc(x.size)}</span>`;
      return `<tr><td>${label}</td><td>${cell(x.copying)}</td><td>${cell(x.position)}</td><td>${cell(x.comparing)}</td><td>${cell(x.carrying)}</td></tr>`;
    }).join('');
    box.innerHTML = `<div class="k">The four suits <span class="s">how good each ship is at each suit: the mean of its four cards, each card divided by its mark. 1.00 means every card in that suit is lit; the foreign ships are read on the same deck</span></div>
      <div class="scroll"><table class="selbooks"><thead><tr><th>ship</th><th>copying</th><th>position</th><th>comparing</th><th>carrying</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };
  const drawLadderChaining = async (on: boolean): Promise<void> => {
    const box = document.getElementById('sopladder'); if (!box) return;
    box.hidden = !on; if (!on) return;
    const version = (sel && sel.value) || (d.sop && d.sop.current) || '';
    let r: Payload; try { r = await get(`/api/ladder_chaining?sop=${encodeURIComponent(version)}`); } catch { return; }
    const rows = (r.sizes || []).map((x: any) => {
      const ch = x.chaining == null ? '–' : x.chaining.toFixed(3);
      const gap = x.gap == null ? '' : `${x.gap > 0 ? '+' : ''}${x.gap.toFixed(3)}`;
      const pill = x.status === 'running' ? 'running' : x.status === 'finished' ? '' : 'bad';
      return `<tr><td class="mono">${esc(x.size)}</td><td>${x.status === 'not sailed' ? '<span class="s">not yet</span>' : `<span class="${pillCls(pill)}">${esc(x.status)}</span>`}</td><td><b>${ch}</b></td><td>${(r.qwen || 0.538).toFixed(3)}</td><td>${gap}</td></tr>`;
    }).join('');
    box.innerHTML = `<div class="k">The ladder against Qwen3 4B <span class="s">every rung on v${esc(version)}, its chaining lift at its last step, and the distance to the model that chains (0.538). A rung fills in as it finishes</span></div>
      <div class="scroll"><table class="selbooks"><thead><tr><th>size</th><th>status</th><th>chaining</th><th>qwen</th><th>gap</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };
  const drawPhysical = (on: boolean): void => {
    const box = document.getElementById('sopshape'); if (!box) return;
    box.hidden = !on; if (!on) return;
    const shapes = d.shapes || {};
    const order = ['300k', '1m', '9m', '21m', '50m', '100m', '350m'];
    const thorpKeys = [...order.filter((k) => shapes[k]), ...Object.keys(shapes).filter((k) => !order.includes(k) && shapes[k].thorp).sort()];
    const foreignKeys = Object.keys(shapes).filter((k) => !shapes[k].thorp).sort();
    const keys = [...thorpKeys, ...foreignKeys];
    box.innerHTML = `<div class="k">The shapes of the ladder <span class="s">depth and width for each class: the deep ladder of 9 November puts the width into layers, so the copy cards can sit in the second half of the model</span></div>
      <div class="scroll"><table class="selbooks"><thead><tr><th>class</th><th>layers</th><th>width</th><th>heads</th><th>head dim</th></tr></thead><tbody>${
        keys.map((k) => { const sh = shapes[k]; const hd = sh.heads ? (sh.width / sh.heads) : null;
          const name = sh.thorp ? `<span class="mono">${esc(k)}</span>` : `<span class="mono">${esc(sh.lab || k)}</span> <span class="s">foreign${sh.params ? ' · ' + big(sh.params) : ''}</span>`;
          return `<tr><td>${name}</td><td>${sh.layers}</td><td>${sh.width}</td><td>${sh.heads}</td><td>${hd == null ? '–' : Math.round(hd * 10) / 10}</td></tr>`; }).join('')
      }</tbody></table></div>`;
  };
  const SHIP_NAMES: Record<string, string> = { '300k': 'Pan', '1m': 'Augustus', '9m': 'The speller', '21m': 'The stylist', '50m': 'Paragraph', '100m': 'Invention', '350m': 'Trader' };
  const drawEmbeddings = (on: boolean): void => {
    const box = document.getElementById('sopembed'); if (!box) return;
    box.hidden = !on; if (!on) return;
    const emb = d.embeddings || {};
    const order = ['300k', '1m', '9m', '21m', '50m', '100m', '350m'];
    const keys = [...order.filter((k) => emb[k]), ...Object.keys(emb).filter((k) => !order.includes(k) && !emb[k].thorp).sort()];
    const embs = (d.sop && ((d.sop.standards || {})[sel.value] || {}).embeddings) || {};
    const vers = embs.versions || {}, chosen = embs.chosen;
    const verRows = Object.entries(vers).map(([k, v]: [string, any]) =>
      `<tr><td class="mono">${esc(k)}</td><td>${v.vocab}</td><td>${k === chosen ? '<b>chosen by this standard</b>' : '<span class="s">available</span>'}</td><td class="s">${esc(v.note || '')}</td></tr>`).join('');
    const ctlClasses = ((d.control || {}).classes || []) as any[];
    const ctlSel = ((draft.embeddings || {}) as any).control || {};
    const ctlChosen = new Set<string>(ctlSel.classes || []);
    const ctlSome = Array.isArray(ctlSel.ships);
    const ctlShips = ctlSome ? (ctlSel.ships as string[]) : [];
    const shipKeys = keys.filter((k) => emb[k] && emb[k].thorp);
    const ctlHtml = ctlClasses.length ? `
      <div class="k mt">Control tokens <span class="s">the classes this expedition's ships carry (9 November). The names follow the open-source &lt;|...|&gt; convention; boundary is the model's own SentencePiece specials, the rest are user-defined pieces</span></div>
      <div class="ctlclasses">${ctlClasses.map((c) => `<label class="ctlclass"><input type="checkbox" class="${checkCls()}" data-ctlclass="${esc(c.key)}"${ctlChosen.has(c.key) ? ' checked' : ''}> <b>${esc(c.name)}</b> <span class="s">${c.is_special ? 'model specials: ' : ''}${(c.tokens || []).map((t: any) => esc(t.symbol)).join(' ')}</span></label>`).join('')}</div>
      <div class="fbrow"><label class="note" for="hmctlscope">apply to</label>
        <select class="sel" id="hmctlscope"><option value="all"${ctlSome ? '' : ' selected'}>all ships</option><option value="some"${ctlSome ? ' selected' : ''}>some ships</option></select>
        <select class="sel" id="hmctlships" multiple size="7"${ctlSome ? '' : ' disabled'}>${shipKeys.map((k) => `<option value="${esc(k)}"${ctlShips.includes(k) ? ' selected' : ''}>${esc(SHIP_NAMES[k] || k)} (${esc(k)})</option>`).join('')}</select>
        <span class="s">recorded on this SOP version; each selected ship's tokeniser declares the chosen symbols</span></div>
      <div class="s" id="hmctlresolved"></div>` : '';
    box.innerHTML = `<div class="k">The embedding versions <span class="s">three locked sets of pieces the SOP may choose between (9 November): a version is never edited, only added, and readings from different versions are never compared — the tokeniser sets the bits-per-byte scale</span></div>
      <div class="scroll"><table class="selbooks"><thead><tr><th>version</th><th>pieces</th><th></th><th>what it is for</th></tr></thead><tbody>${verRows}</tbody></table></div>
      <div class="k mt">The embedding <span class="s">the lookup table every token starts in: vocabulary × width. It is the same table at every phase, so it sits with the model's physics, not with a phase</span></div>
      <div class="scroll"><table class="selbooks"><thead><tr><th>class</th><th>vocab</th><th>width</th><th>embedding params</th><th>of the ship</th></tr></thead><tbody>${
        keys.map((k) => { const e = emb[k];
          const name = e.thorp ? `<span class="mono">${esc(k)}</span>` : `<span class="mono">${esc(e.lab || k)}</span> <span class="s">foreign</span>`;
          return `<tr><td>${name}</td><td>${big(e.vocab)}</td><td>${e.width}</td><td>${big(e.params)}</td><td>${(e.share * 100).toFixed(1)}%</td></tr>`; }).join('')
      }</tbody></table></div>
      <div class="s" style="margin-top:6px">the table is tied: the same matrix reads a token and predicts the next, so a wider table is both a bigger first layer and a bigger last one</div>${ctlHtml}`;
    if (ctlClasses.length) {
      const scopeEl = document.getElementById('hmctlscope') as HTMLSelectElement | null;
      const shipsEl = document.getElementById('hmctlships') as HTMLSelectElement | null;
      const resolved = document.getElementById('hmctlresolved');
      const sync = (): void => {
        const classes = [...box.querySelectorAll<HTMLInputElement>('[data-ctlclass]:checked')].map((x) => x.dataset.ctlclass!);
        const ships = scopeEl && scopeEl.value === 'some' ? [...(shipsEl ? shipsEl.selectedOptions : [])].map((o) => o.value) : 'all';
        draft.embeddings = { ...(draft.embeddings || {}) };
        (draft.embeddings as Payload).control = { classes, ships };
        if (active === 'parts') {
          const c = catOf('parts');
          ta.value = JSON.stringify(Object.fromEntries(c.keys.filter((k: string) => k in draft).map((k: string) => [k, draft[k]])), null, 1);
        }
        const picked = ctlClasses.filter((c) => classes.includes(c.key));
        const all = picked.flatMap((c) => c.tokens || []);
        const specials = picked.filter((c) => c.is_special).flatMap((c) => (c.tokens || []).map((t: any) => t.symbol));
        const symbols = picked.filter((c) => !c.is_special).flatMap((c) => (c.tokens || []).map((t: any) => t.symbol));
        if (resolved) {
          resolved.innerHTML = classes.length
            ? `${all.length} tokens: ${all.map((t: any) => esc(t.symbol)).join(' ')} · ${symbols.length ? `the tokeniser declares ${symbols.length}: ${symbols.map((x: string) => esc(x)).join(' ')}` : 'no user-defined control symbols'}${specials.length ? ` · plus the model specials ${specials.map((x: string) => esc(x)).join(' ')}` : ''}${Array.isArray(ships) && !ships.length ? ' · no ships selected' : ''}`
            : 'no control tokens selected';
        }
      };
      box.querySelectorAll<HTMLInputElement>('[data-ctlclass]').forEach((el) => el.addEventListener('change', sync));
      if (scopeEl) scopeEl.onchange = () => { if (shipsEl) shipsEl.disabled = scopeEl.value === 'all'; sync(); };
      if (shipsEl) shipsEl.onchange = sync;
      sync();
    }
  };
  const postOf = (): Payload => { const st = std[sel.value] || {}; return st.posttraining || st.post || null; };
  const postStages = (): any[] => { const p = postOf(); return p ? (p.stages || (p.stage ? [p.stage] : [])) : []; };
  const postStage = (): Payload => postStages()[0] || {};
  const stageLibrary = (): string => {
    if (phase === 'posttraining') { const st = postStage(); return st.library || st.recipe || ''; }
    const c = (draft.content || {}) as Payload;
    const fromStandard = c.recipe || c.library || '';
    if (fromStandard) return fromStandard;
    return (((journey && journey[phase] || {}).stage || [])[0] || {}).library || '';
  };
  const drawLibSummary = async (path: string): Promise<void> => {
    if (browse) { renderSelection(); return; }
    const box = document.getElementById('soplib'); if (!box) return;
    box.hidden = active !== 'library' && active !== 'training';
    if (active !== 'library' && active !== 'training') return;
    if (phase === 'posttraining' && !postOf()) { box.innerHTML = '<div class="s">posttraining is not in this SOP: Library is empty. The Star chart and Physical attributes are shared.</div>'; return; }
    if (!path) { box.innerHTML = '<div class="s">no library is chosen for this leg yet</div>'; return; }
    box.innerHTML = '<div class="s">reading the shelf…</div>';
    let lib = LIB_SUMMARY[path];
    if (!lib) {
      let timer: number | undefined;
      const timeout = new Promise<never>((_, reject) => {
        timer = window.setTimeout(() => reject(new Error('the shelf is taking too long to read (the server is busy); the stages and phases below are still shown')), 15000);
      });
      try {
        lib = await Promise.race([get('/api/library_summary?path=' + encodeURIComponent(path)), timeout]);
        LIB_SUMMARY[path] = lib;
      } catch (e) {
        box.innerHTML = `<div class="s">the shelf could not be read: ${esc(String((e as Error).message || e))}</div>`;
        return;
      } finally {
        if (timer) window.clearTimeout(timer);
      }
    }
    if (stageLibrary() !== path) return;
    const langs = lib.languages || [], kinds = lib.categories || [];
    const langText = langs.length ? langs.slice(0, 3).map((l: any) => `${esc(l.name)} ${Math.round((l.share || 0) * 100)}%`).join(' · ') : '–';
    const langName = langs.length ? (langs[0].share >= 0.999 ? esc(langs[0].name) : `${esc(langs[0].name)} +${langs.length - 1}`) : '–';
    const mb = (b: number | null) => b == null ? '–' : b >= 1e9 ? (b / 1e9).toFixed(2) + ' GB' : Math.round(b / 1e6) + ' MB';
    const dates = lib.date_range ? `${lib.date_range.from}–${lib.date_range.to}` : '–';
    const og = lib.ogden || {};
    box.innerHTML = `<div class="libhead"><div class="k">The library at a glance <span class="s">${esc(path)} · what this version reads, before its settings</span></div></div>
      <div class="libstats">
        <div class="libstat"><b>${langName}</b><span>language${langs.length > 1 ? ' · ' + langText : ''}</span></div>
        <div class="libstat"><b>${lib.books || lib.rows ? big(lib.books || lib.rows) : '–'}</b><span>${lib.synthetic ? 'passages' : 'books'}${lib.resolved != null && !lib.synthetic ? ' · ' + big(lib.resolved) + ' resolved' : ''}</span></div>
        <div class="libstat"><b>${lib.tokens_est == null ? '–' : big(lib.tokens_est)}</b><span>tokens (estimated)${lib.bytes ? ' · ' + mb(lib.bytes) : ''}</span></div>
        <div class="libstat"><b>${dates}</b><span>date range</span></div>
        <div class="libstat"><b>${og.mean == null ? '–' : og.mean.toFixed(2)}</b><span>Ogdenish mean${og.share_at_bar == null ? '' : ' · ' + Math.round(og.share_at_bar * 100) + '% at ' + og.bar}</span></div>
      </div>
      <div class="libkinds"><span class="k">Kinds of book</span>${kinds.length ? kinds.map((k: any) => `<span class="libkind"><b>${esc(k.category)}</b> ${Math.round((k.share || 0) * 100)}% <span class="s">${big(k.books)}</span></span>`).join('') : lib.synthetic ? '<span class="s">synthetic card-stage passages; there are no book categories to count</span>' : '<span class="s">no categories read for these books</span>'}</div>`;
  };
  const drawStarChart = (on: boolean): void => {
    const box = document.getElementById('sopdepth'); if (!box) return;
    box.hidden = !on; if (!on) return;
    const layers = ((d.chart || {}).depths || {})[sel.value] || [];
    const focus = layers.find((l: any) => l.size === '300k-l28') || layers.find((l: any) => l.size === '300k') || layers[0];
    const points = (d.chart || {}).points || [];
    box.innerHTML = `<div class="depthhead"><div class="k">The star chart <span class="s">depth is how the stars are followed: the model depth the standard includes, and the card placements that reach it</span></div>
        ${focus ? `<div class="depthbig"><b>${focus.layers}</b> layers at <span class="mono">${esc(focus.size)}</span> <span class="s">· ${focus.pinned} cards pinned, deepest at L${focus.deepest_pinned}</span></div>` : '<div class="s">no pinning table in this version</div>'}
        <div class="depthpills">${layers.map((l: any) => `<span class="depthpill"><b>${l.layers}</b> <span class="s">${esc(l.size)}</span></span>`).join('')}</div></div>
      <div class="depthchart"><div class="k">The ten-point star chart <span class="s">the chart we are building towards: ten places chaining might live, what Qwen3 4B's heads say, the deck card each point is read as, and how a four-slot 300k tests it</span></div>
      <div class="scroll"><table class="depthtable"><thead><tr><th>#</th><th>point — the role</th><th>Qwen 4B evidence</th><th>deck card</th><th>how the 300k tests it</th></tr></thead><tbody>
      ${points.map((p: any) => `<tr><td class="mono">${p.n}</td><td><b>${esc(p.role)}</b></td><td>${esc(p.qwen)}</td><td class="mono">${esc(p.card)}</td><td>${esc(p.test)}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  };
  const drawStages = (on: boolean): void => {
    const box = document.getElementById('sopstage'); if (!box) return;
    box.hidden = !on; if (!on) return;
    const post = phase === 'posttraining' ? postOf() : null;
    // the stages of this leg: the standard's own stage first, the journey's plan as the fallback (the
    // journey is a planning record for another ship, and reading only it left Training empty)
    const fromJourney = (((journey || {})[phase] || {}).stage || []) as any[];
    const fromStandard = (() => {
      if (phase === 'posttraining') return postStages();
      const c = (draft.content || {}) as any;
      if (!c.recipe && !c.library) return [];
      return [{ name: c.name || 'content', purpose: 'what the ship reads on this leg',
                library: c.recipe || c.library, passes: c.passes || 1 }];
    })();
    const stages = fromStandard.length ? fromStandard : fromJourney;
    if (phase === 'posttraining' && !post) { box.innerHTML = '<div class="s">posttraining is not in this SOP: Stages is empty. The Star chart and Physical attributes are shared.</div>'; return; }
    box.innerHTML = `<div class="k">Stages of ${phase} <span class="s">the ships and books of this leg</span></div>` +
      (stages.length ? stages.map((st: any) => `<div class="phasestage">
        <div class="psname">${esc(st.name)} <span class="s">${esc(st.purpose || (phase === 'posttraining' ? (postOf() || {}).what : '') || '')}</span></div>
        <div class="psmeta"><span>library <b>${esc(st.library || st.recipe || 'not chosen')}</b></span><span>${st.passes ?? 1} pass${st.passes === 1 ? '' : 'es'}</span><span>${st.tokens ? big(st.tokens) + ' tokens' : 'tokens not set'}</span><span>${(st.cards || []).length} cards</span></div>
        ${(st.cards || []).length ? `<div class="pscards">${st.cards.map((c: any) => `<span class="${pillCls('')}" title="level ${c.level}: ${esc(c.about || '')}">${esc(c.name || c.key)} <span class="s">L${c.level}</span></span>`).join('')}</div>` : '<div class="s">no cards recorded for this stage</div>'}
      </div>`).join('') : '<div class="s">no stages in this leg</div>');
  };
  const drawPhases = async (on: boolean): Promise<void> => {
    const box = document.getElementById('sopphases'); if (!box) return;
    box.hidden = !on; if (!on) return;
    const post = phase === 'posttraining' ? postOf() : null;
    if (phase === 'posttraining' && !post) {
      box.innerHTML = '<div class="s">posttraining is not in this SOP: Phases is empty. The Star chart and Physical attributes are shared.</div>'; return;
    }
    const phases = phase === 'posttraining'
      ? (post.phases || (post.stage ? [{ kind: 'post-training', share: 1, about: post.what || post.about || '', cards: post.cards || post.stage.cards || [] }] : (post.mixture || [])))
      : (draft.phases || []);
    const cards = phase === 'posttraining' ? (post.cards || (post.stage || {}).cards || []) : (draft.cards || []);
    const stage = phase === 'posttraining' ? postStage() : ((((journey || {})[phase] || {}).stage || [])[0] || {});
    const phaseAt = phase;
    const passes = Number(stage.passes) || 1;
    let perPass: number | null = null;
    const stagePath = stage.library || stage.recipe || '';
    if (stagePath) {
      // never block the phases on the shelf summary: its tokens are a nicety, the plan is the point
      const lib = LIB_SUMMARY[stagePath];
      if (lib && lib.tokens_est) perPass = lib.tokens_est;
      else if (!lib) {
        void get('/api/library_summary?path=' + encodeURIComponent(stagePath))
          .then((v) => { LIB_SUMMARY[stagePath] = v; })
          .catch(() => { /* the plan is shown without a token estimate */ });
      }
    }
    if (phase !== phaseAt) return;
    const total = Number(stage.tokens) || (perPass ? perPass * passes : null);
    const totalText = total ? `${big(total)} tokens planned${perPass ? ` (${passes} × ${big(perPass)} per pass)` : ''}` : 'tokens not planned';
    const order = phases.map((p: any, i: number) => `<span><b>${i + 1}</b> ${esc(p.kind || 'phase')} ${Math.round((Number(p.share) || 0) * 100)}%</span>`).join('<span class="s"> → </span>');
    // the dynamic schedule (SOP 0.0.6): pin -> probe -> equilibrium -> release -> boost -> by heart.
    // It is the standard's own data, so a version without a controller simply shows nothing.
    const ctrl: any = phase === 'pretraining' ? (draft.control || null) : null;
    const ctrlHtml = ctrl && ctrl.enabled
      ? `<div class="k">The dynamic schedule <span class="s">the controller runs over ${esc(ctrl.signal || 'the cards')}</span></div>
        <div class="phaseorder">${(ctrl.sequence || []).map((p: any, i: number) => `<span><b>${i + 1}</b> ${esc(p.kind)} ${Math.round((Number(p.share) || 0) * 100)}%</span>`).join('<span class="s"> → </span>')}</div>
        <div class="phaseplan">${(ctrl.sequence || []).map((p: any, i: number) => `<div class="planphase ${p.kind === 'by_heart' ? 'content' : 'scaffold'}">
            <div class="pphead"><b>${i + 1}. ${esc(p.kind)}</b><span>${Math.round((Number(p.share) || 0) * 100)}%${total ? ` · ${big(Math.round(total * (Number(p.share) || 0)))} tokens` : ''}</span></div>
            <div class="s">${esc(p.about || '')}</div>
            <div class="ppmeta">${p.pulses != null ? `pulses ${p.pulses} × ${p.pulse_evals} evals` : ''}${p.target != null ? ` · target ${p.target}× threshold` : ''}${p.delta != null ? ` · delta ${p.delta}` : ''}${p.floor != null ? ` · floor ${p.floor}` : ''}${p.k != null ? ` · top ${p.k} heads by rise` : ''}</div>
          </div>`).join('')}</div>
        <div class="s">Every card is released by ${Math.round((Number(ctrl.deadline) || 0.9) * 100)}% of the voyage, so the last tenth is read by heart.</div>`
      : '';
    // 0.0.6 defines a dynamic schedule; the fixed three-phase plan is what the trainer actually runs
    // today. Both are shown, the defined one first (9 November, Justin: "I'm on kipling and I don't
    // think that's the phase at all. We were going with a probe step").
    const defined = ctrl && ctrl.enabled ? ctrlHtml : '';
    const library = stage.library || stage.recipe || '';
    box.innerHTML = `<div class="k">Phases of ${phase} <span class="s">in order: ${esc(totalText)}</span></div>
      ${defined}
      <div class="k mt">The fixed schedule the trainer runs today <span class="s">what executes on this voyage now; a step of the schedule above lands when the controller does</span></div>
      <div class="phaseorder">${order}</div>
      <div class="phaseplan">${phases.length ? phases.map((p: any, i: number) => {
        const share = Number(p.share) || 0, pct = Math.round(share * 100);
        const tokens = total ? Math.round(total * share) : null;
        const scaffold = p.kind === 'scaffold';
        const pulled = Array.isArray(p.cards) && p.cards.length ? p.cards : (scaffold ? cards : []);
        return `<div class="planphase ${scaffold ? 'scaffold' : 'content'}">
          <div class="pphead"><b>${i + 1}. ${esc(p.kind || 'phase')}</b><span>${pct}%${tokens != null ? ` · ${big(tokens)} tokens` : ''}</span></div>
          <div class="s">${esc(p.about || '')}</div>
          ${library ? `<div class="ppmeta">reads <span class="mono">${esc(library)}</span>${stage.passes ? ` · ${stage.passes} passes` : ''}</div>` : ''}
          ${scaffold ? `<div class="ppmeta">${p.weight != null ? `weight ${p.weight}` : ''}${p.hold != null ? ` · hold ${p.hold}` : ''}${p.fade != null ? ` · fade ${p.fade}` : ''}${p.floor != null ? ` · floor ${p.floor}` : ''}</div>
            <div class="ppcards"><span class="k">cards scaffolded</span>${pulled.length ? pulled.map((c: string) => `<span class="ppcard">${esc(c)}</span>`).join('') : '<span class="s">none listed in this version</span>'}</div>` : '<div class="ppmeta">content: no cards pulled</div>'}
        </div>`;
      }).join('') : '<div class="s">no phases in this version of the SOP</div>'}</div>
      <div class="s">${phases.length} phases, ${Math.round(phases.reduce((a: number, p: any) => a + (Number(p.share) || 0), 0) * 100)}% of the voyage; the scaffold is the only phase that pulls cards.${total ? ' The token split is the stage\'s planned tokens divided by the SOP shares.' : ' Choose the stage library to plan its tokens.'}</div>`;
  };
  const paintChoices = (): void => {
    const es = document.getElementById('hmembed') as HTMLSelectElement | null, ss = document.getElementById('hmsizes');
    if (!es || !ss) return;
    const curStd = std[sel.value] || {};
    const fallback = ((std[curStd && curStd.supersedes ? curStd.supersedes : '0.0.5'] || {}).embeddings) || {};
    const vers = ((curStd.embeddings || {}).versions) || fallback.versions || {};
    const chosen = (curStd.embeddings || {}).chosen || fallback.chosen || '';
    es.innerHTML = Object.entries(vers).map(([k, v]: [string, any]) => `<option value="${esc(k)}"${k === chosen ? ' selected' : ''}>${esc(k)} · ${v.vocab} pieces</option>`).join('') || `<option value="">${esc(chosen || 'none')}</option>`;
    es.onchange = () => { draft.embeddings = { ...(draft.embeddings || {}), chosen: es.value }; };
    const sizes = ['300k', '1m', '9m', '21m', '50m', '100m', '350m'];
    const on = new Set(curStd.sizes_to_sail || sizes);
    ss.innerHTML = sizes.map((k) => `<label class="s"><input type="checkbox" class="${checkCls()}" data-size="${k}"${on.has(k) ? ' checked' : ''}> ${k}</label>`).join('');
    ss.querySelectorAll<HTMLInputElement>('input[data-size]').forEach((b) => { b.onchange = () => {
      draft.sizes_to_sail = [...ss.querySelectorAll<HTMLInputElement>('input[data-size]:checked')].map((x) => x.dataset.size);
    }; });
  };
  const load = (v: string): void => {
    draft = { ...(std[v] || {}) };
    if (browse) applyDraftSelection();
    cats = SOP_CATS;
    paintChoices();
    const about = document.getElementById('hmabout'); if (about) about.textContent = String((std[v] || {}).about || '');
    if (!SOP_TABS.some((c) => c.key === active)) active = 'library';
    const nav = document.getElementById('sopnav')!;
    nav.innerHTML = (only ? SOP_TABS.filter((c) => c.key === only) : SOP_TABS).map((c) => `<button type="button" class="sopbtn${c.key === active ? ' active' : ''}" data-sop="${esc(c.key)}" role="tab" aria-selected="${c.key === active}">${esc(c.name)}</button>`).join('');
    nav.hidden = !!only;
    nav.querySelectorAll<HTMLElement>('.sopbtn').forEach((b) => { b.onclick = () => { if (!readDraft()) return; showTab(b.dataset.sop!); }; });
    showTab(active);
    drawPhase();
  };
  // ---- the branch editor: a branch and variation, then the makeup taken out of them. The browse is
  // the library's own facts (12k books) and can take a few seconds to compute; the editor waits for it.
  const LANGS: Record<string, string> = { en: 'English', la: 'Latin', grc: 'Ancient Greek', sux: 'Sumerian', akk: 'Akkadian', egy: 'Egyptian', ar: 'Arabic', he: 'Hebrew', fr: 'French', de: 'German', it: 'Italian', es: 'Spanish', ru: 'Russian', sa: 'Sanskrit', ang: 'Old English', enm: 'Middle English', non: 'Old Norse', got: 'Gothic', syr: 'Syriac', nl: 'Dutch', pt: 'Portuguese', sv: 'Swedish', da: 'Danish', el: 'Greek', tr: 'Turkish', fa: 'Persian', zh: 'Chinese', ja: 'Japanese' };
  const multi = (el: HTMLSelectElement | null): string[] => el ? [...el.selectedOptions].map((o) => o.value) : [];
  const currentBranch = (): Payload | null => (browse && (browse.branches || []).find((b: Payload) => b.key === branchSel?.value)) || null;
  const currentVariation = (): Payload | null => {
    const b = currentBranch(); if (!b) return null;
    return (b.variations || []).find((v: Payload) => v.key === variationSel?.value) || (b.variations || [])[0] || null;
  };
  const selectedBooks = (): any[] => {
    const v = currentVariation(); if (!browse || !v) return [];
    const all = browse.books || [];
    const from = yearFrom?.value ? Number(yearFrom.value) : null;
    const to = yearTo?.value ? Number(yearTo.value) : null;
    const langs = new Set(multi(langSel)), kinds = new Set(multi(kindSel)), sources = new Set(multi(sourceSel)), voices = new Set(multi(voiceSel));
    return (v.books || []).map((i: number) => all[i]).filter((b: any) => {
      if (!b) return false;
      const y = Number(b[7]);
      if (from != null && (!Number.isFinite(y) || y < from)) return false;
      if (to != null && (!Number.isFinite(y) || y > to)) return false;
      if (langs.size && !langs.has(b[3])) return false;
      if (kinds.size && !kinds.has(b[5])) return false;
      if (sources.size && !sources.has(b[4])) return false;
      if (voices.size && !voices.has(b[6])) return false;
      return true;
    });
  };
  const catOfBook = (b: any): string => {
    const title = String(b[1] || '');
    if (/\b(logic|reason|mathemat|arithmetic|geometry|geometr|algebra|calculus|euclid|number|proportion)\b/i.test(title)) return 'logic and maths';
    const kind = String(b[5] || '');
    if (['philosophy', 'religion', 'sermon', 'dialogue'].includes(kind)) return 'metaphysics';
    if (['science', 'history', 'biography', 'travel', 'practical', 'periodical'].includes(kind)) return 'empirical knowledge';
    return 'general knowledge';
  };
  const fillMulti = (el: HTMLSelectElement | null, values: string[], label: (v: string) => string): void => {
    if (!el) return;
    const keep = new Set(multi(el));
    const counts = new Map<string, number>();
    for (const v of values) counts.set(v, (counts.get(v) || 0) + 1);
    el.innerHTML = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([v, n]) => `<option value="${esc(v)}"${keep.has(v) ? ' selected' : ''}>${esc(label(v))} (${n})</option>`).join('');
  };
  const fillFilters = (v: Payload | null): void => {
    const all = browse ? (browse.books || []) : [];
    const bs = ((v && v.books) || []).map((i: number) => all[i]).filter(Boolean);
    fillMulti(langSel, bs.map((b: any) => String(b[3] || '?')), (x) => LANGS[x] || x);
    fillMulti(kindSel, bs.map((b: any) => String(b[5] || 'other')), (x) => x);
    fillMulti(sourceSel, bs.map((b: any) => String(b[4] || '?')), (x) => x);
    fillMulti(voiceSel, bs.map((b: any) => String(b[6] || '?')), (x) => x);
    const s = (draft.content || {}).selection;
    if (s) {
      if (s.from != null && yearFrom) yearFrom.value = String(s.from);
      if (s.to != null && yearTo) yearTo.value = String(s.to);
      const apply = (el: HTMLSelectElement | null, vals: string[] | undefined): void => {
        if (!el || !vals) return;
        const set = new Set(vals);
        [...el.options].forEach((o) => { o.selected = set.has(o.value); });
      };
      apply(langSel, s.languages); apply(kindSel, s.kinds); apply(sourceSel, s.sources); apply(voiceSel, s.voices);
    }
  };
  const fillVariations = (want?: string): void => {
    const b = currentBranch();
    if (!variationSel) return;
    variationSel.innerHTML = ((b && b.variations) || []).map((v: Payload) => `<option value="${esc(v.key)}">${esc(v.name || v.key)}</option>`).join('');
    if (want && (b?.variations || []).some((v: Payload) => v.key === want)) variationSel.value = want;
    fillFilters(currentVariation());
  };
  const renderSelection = (): void => {
    const box = document.getElementById('soplib'); if (!box) return;
    const onLib = active === 'library' || active === 'training';
    box.hidden = !onLib;
    if (!onLib || !browse) return;
    const bs = selectedBooks();
    const b = currentBranch(), v = currentVariation();
    if (!b || !v) { box.innerHTML = '<div class="s">choose a branch</div>'; return; }
    const n = bs.length || 1;
    const words = bs.reduce((a: number, x: any) => a + (Number(x[10]) || 0), 0);
    const langs = new Map<string, number>(); const kinds = new Map<string, number>(); const cats = new Map<string, number>();
    const years: number[] = []; const ogden: number[] = [];
    for (const x of bs) {
      langs.set(String(x[3] || '?'), (langs.get(String(x[3] || '?')) || 0) + 1);
      kinds.set(String(x[5] || 'other'), (kinds.get(String(x[5] || 'other')) || 0) + 1);
      cats.set(catOfBook(x), (cats.get(catOfBook(x)) || 0) + 1);
      const y = Number(x[7]); if (Number.isFinite(y)) years.push(y);
      const o = Number(x[9]); if (Number.isFinite(o)) ogden.push(o);
    }
    const top = [...langs.entries()].sort((a, b2) => b2[1] - a[1])[0];
    const topName = top ? (LANGS[top[0]] || top[0]) : '–';
    const langsText = [...langs.entries()].sort((a, b2) => b2[1] - a[1]).slice(0, 3).map(([k, c]) => `${esc(LANGS[k] || k)} ${Math.round((c / n) * 100)}%`).join(' · ');
    const range = years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '–';
    const mean = ogden.length ? (ogden.reduce((a, b2) => a + b2, 0) / ogden.length).toFixed(2) : '–';
    const atBar = ogden.length ? Math.round((ogden.filter((o) => o >= 0.68).length / ogden.length) * 100) : null;
    const tokens = Math.round(words * 1.33);
    const mb = Math.round((words * 6) / 1e6);
    box.innerHTML = `<div class="libhead"><div class="k">The library at a glance <span class="s">${esc(b.name || b.key)} · ${esc(v.name || v.key)} · ${esc(String(yearFrom?.value || 'any'))}–${esc(String(yearTo?.value || 'any'))}</span></div></div>
      <div class="libstats">
        <div class="libstat"><b>${esc(topName)}</b><span>language${langs.size > 1 ? ' · ' + langsText : ''}</span></div>
        <div class="libstat"><b>${big(bs.length)}</b><span>books${bs.length ? ' · ' + big(words) + ' words' : ''}</span></div>
        <div class="libstat"><b>${big(tokens)}</b><span>tokens (estimated) · ${mb} MB</span></div>
        <div class="libstat"><b>${range}</b><span>date range</span></div>
        <div class="libstat"><b>${mean}</b><span>Ogdenish mean${atBar == null ? '' : ' · ' + atBar + '% at 0.68'}</span></div>
      </div>
      <div class="libkinds"><span class="k">Kinds of book</span>${[...cats.entries()].sort((a, b2) => b2[1] - a[1]).map(([c, k]) => `<span class="libkind"><b>${esc(c)}</b> ${Math.round((k / n) * 100)}% <span class="s">${big(k)}</span></span>`).join('')}</div>`;
    draft.content = { ...(draft.content || {}) };
    (draft.content as Payload).selection = {
      branch: b.key, variation: v.key,
      from: yearFrom?.value ? Number(yearFrom.value) : null,
      to: yearTo?.value ? Number(yearTo.value) : null,
      languages: multi(langSel), kinds: multi(kindSel), sources: multi(sourceSel), voices: multi(voiceSel),
    };
    if (ta) {
      const c = catOf('training');
      ta.value = JSON.stringify(Object.fromEntries(c.keys.filter((k: string) => k in draft).map((k: string) => [k, draft[k]])), null, 1);
    }
  };
  const applyDraftSelection = (): void => {
    if (!browse) return;
    const s = (draft.content || {}).selection;
    const rec = (draft.content || {}).recipe;
    if (s && s.branch && (browse.branches || []).some((b: Payload) => b.key === s.branch)) {
      if (branchSel) branchSel.value = s.branch;
      fillVariations(s.variation);
      if (yearFrom) yearFrom.value = s.from == null ? '' : String(s.from);
      if (yearTo) yearTo.value = s.to == null ? '' : String(s.to);
    } else if (rec) {
      const b = (browse.branches || []).find((x: Payload) => (x.variations || []).some((v: Payload) => v.list === rec));
      const v = b && (b.variations || []).find((x: Payload) => x.list === rec);
      if (b && branchSel) branchSel.value = b.key;
      fillVariations(v && v.key);
    }
  };
  const setupBrowse = (b: Payload): void => {
    browse = b;
    if (branchSel) branchSel.innerHTML = (b.branches || []).map((x: Payload) => `<option value="${esc(x.key)}">${esc(x.name || x.key)}</option>`).join('');
    applyDraftSelection();
    if (variationSel && !variationSel.options.length) fillVariations();
    const row = document.getElementById('hmbranchrow'); if (row) row.hidden = active !== 'library' && active !== 'training';
    const filters = document.getElementById('hmfilters'); if (filters) filters.hidden = active !== 'library' && active !== 'training';
    renderSelection();
    if (active === 'library' || active === 'training') showTab(active);
  };
  const getBrowse = async (): Promise<void> => {
    try {
      const b = await get('/api/library_browse');
      if (b && b.computing) { window.setTimeout(() => { void getBrowse(); }, 5000); return; }
      if (b && Array.isArray(b.branches)) setupBrowse(b);
    } catch { window.setTimeout(() => { void getBrowse(); }, 5000); }
  };
  if (branchSel) branchSel.onchange = () => { fillVariations(); renderSelection(); };
  if (variationSel) variationSel.onchange = () => { fillFilters(currentVariation()); renderSelection(); };
  for (const el of [yearFrom, yearTo, langSel, kindSel, sourceSel, voiceSel]) {
    if (el) el.addEventListener('change', () => renderSelection());
  }
  void getBrowse();
  if (version && vs.includes(version)) { sel.value = version; sel.dataset.v = version; }
  load(sel.value);
  sel.onchange = () => { if (!readDraft()) { sel.value = sel.dataset.v || sel.value; return; } sel.dataset.v = sel.value; active = only || 'library'; load(sel.value); paintChoices(); };
  sel.dataset.v = sel.value;
  document.getElementById('hmsave')?.addEventListener('click', async () => {
    if (!readDraft()) return;
    msg.className = 'fbmsg'; msg.textContent = 'saving…';
    try {
      const r = await postJSON<any>('/api/shipbuilder/save', { harbour: h.key, standard: draft, from_version: sel.value, adopted: (document.getElementById('hmadopted') as HTMLInputElement).value });
      std[r.version] = r.standard;
      if (r.chart && r.chart.depths) { d.chart = { ...(d.chart || {}), depths: { ...((d.chart || {}).depths || {}), [r.version]: r.chart.depths } }; }
      msg.className = 'fbmsg good'; msg.textContent = 'saved v' + r.version + ' (not in force until a voyage names it)';
      sel.innerHTML = (r.versions || []).map((v: string) => `<option value="${esc(v)}"${v === r.version ? ' selected' : ''}>v${esc(v)}${v === cur ? ' · in force' : ''}</option>`).join('');
      sel.dataset.v = r.version; draft = { ...(r.standard || {}) }; if (browse) applyDraftSelection(); cats = SOP_CATS; active = SOP_TABS.some((c) => c.key === active) ? active : 'library';
      const about = document.getElementById('hmabout'); if (about) about.textContent = String((r.standard || {}).about || '');
      const nav = document.getElementById('sopnav')!;
      nav.innerHTML = (only ? SOP_TABS.filter((c) => c.key === only) : SOP_TABS).map((c) => `<button type="button" class="sopbtn${c.key === active ? ' active' : ''}" data-sop="${esc(c.key)}" role="tab" aria-selected="${c.key === active}">${esc(c.name)}</button>`).join('');
      nav.hidden = !!only;
      nav.querySelectorAll<HTMLElement>('.sopbtn').forEach((b) => { b.onclick = () => { if (!readDraft()) return; showTab(b.dataset.sop!); }; });
      paintChoices();
      showTab(active);
      drawPhase();
    } catch (e) { msg.className = 'fbmsg bad'; msg.textContent = String((e as Error).message || e); }
  });
}
