import { esc, get } from './format.js';

// ---- the reader: a book read the way a Kindle Paperwhite shows one, after the Atlas essay reader.
// The whole stripped text is fetched once and cut into parts at paragraph breaks; each part is laid out
// as pages (CSS columns, one per page) and turning past its last page opens the next part. Arrow keys,
// Page Up/Down, Space, or a click on the left or right third of the page turn it. "Scroll" reads a
// part as one long page instead. Text size, the mode and where you stopped in each book are kept.
const RD = {
  SIZES: [15, 17, 19, 21, 24], GAP: 56, PART: 60000, CPM: 1300,  // characters read a minute, for "min left"
  book: null, parts: [], part: 0, page: 0, pages: 1, pageW: 0,
  size: (() => { const v = rget('thorp.read.size'), n = v === null ? NaN : +v; return Number.isInteger(n) && n >= 0 && n < 5 ? n : 2; })(),
  mode: rget('thorp.read.mode') === 'scroll' ? 'scroll' : 'page',
};
function rget(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function rset(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

// Gutenberg text is hard-wrapped: lines inside a paragraph join with a space; a block of short lines
// (verse, a title page, a table of contents) keeps its lines; a short line in capitals is a heading.
function rParas(text) {
  return text.split(/\n[ \t]*\n+/).map(b => b.replace(/^\n+|\s+$/g, '')).filter(b => b.trim()).map(b => {
    const lines = b.split('\n'), longest = Math.max(...lines.map(l => l.trim().length));
    if (lines.length <= 2 && longest < 60 && /[A-Z]/.test(b) && b === b.toUpperCase()) return `<p class="h">${esc(b.trim())}</p>`;
    if (lines.length > 1 && (longest < 56 || lines.filter(l => /^\s{2,}/.test(l)).length > lines.length / 2)) return `<p class="v">${esc(b)}</p>`;
    return `<p>${esc(lines.map(l => l.trim()).join(' '))}</p>`;
  }).join('');
}
function rSplit(text) {
  const parts = [];
  for (let s = 0; s < text.length;) {
    let e = Math.min(text.length, s + RD.PART);
    if (e < text.length) { const b = text.indexOf('\n\n', e); e = b < 0 ? text.length : b + 2; }
    parts.push({ start: s, end: e });
    s = e;
  }
  return parts.length ? parts : [{ start: 0, end: 0 }];
}
const rEl = id => document.getElementById(id);

// a waypoint's write-up (server.py api_essay: the evaluator's own docstring), read like a book
export async function openEssay(name) {
  rEl('rtitle').textContent = 'loading…';
  openReader();
  const d = await get('/api/essay?name=' + encodeURIComponent(name));
  RD.book = d; RD.parts = rSplit(d.text);
  const at = +rget('thorp.read.at:' + d.book_id) || 0;
  RD.part = Math.max(0, RD.parts.findIndex(p => at < p.end));
  rEl('rtitle').textContent = d.title;
  rRender(at);
}
export async function openBook(id) {
  rEl('rtitle').textContent = 'loading…';
  openReader();
  // the server hands out at most 100k characters at a time
  const url = o => `/api/book?id=${encodeURIComponent(id)}&offset=${o}&length=100000`;
  const d = await get(url(0));
  while (d.text.length < d.chars) { const more = await get(url(d.text.length)); if (!more.text) break; d.text += more.text; }
  RD.book = d; RD.parts = rSplit(d.text);
  const at = +rget('thorp.read.at:' + id) || 0;
  RD.part = Math.max(0, RD.parts.findIndex(p => at < p.end));
  rEl('rtitle').textContent = d.title;
  rRender(at);
}
// lay out the current part; `at` is a character offset in the book to open at (null: the part's first page, -1: its last)
function rRender(at = null) {
  const d = RD.book, p = RD.parts[RD.part], stage = rEl('rstage');
  const title = RD.part === 0 ? `<div class="title"><h1>${esc(d.title)}</h1><div class="by">${esc(d.author || '')}${d.author ? ' · ' : ''}${esc(d.book_id)}</div><hr></div>` : '';
  const more = RD.part < RD.parts.length - 1 ? '' : '<p class="more">— the end —</p>';
  const text = `<div class="rtext" style="font-size:${RD.SIZES[RD.size]}px">${title}${rParas(d.text.slice(p.start, p.end))}${more}</div>`;
  const cs = getComputedStyle(stage);
  const w = stage.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  const h = stage.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  RD.pageW = Math.max(0, Math.min(w, 660));
  if (RD.mode === 'page') {
    stage.innerHTML = `<div class="rpage" style="width:${RD.pageW}px;height:${h}px"><div id="rcols" style="height:${h}px;width:${RD.pageW}px;column-width:${RD.pageW}px;column-gap:${RD.GAP}px;column-fill:auto">${text}</div></div>`;
    RD.pages = Math.max(1, Math.ceil((rEl('rcols').scrollWidth + RD.GAP - 1) / (RD.pageW + RD.GAP)));
    // one characters-per-page figure for the whole book at this size and width, so page numbers do not jump between parts
    const key = RD.book.book_id + '|' + RD.size + '|' + RD.pageW + '|' + h;
    if (RD.cppKey !== key && (p.end - p.start > RD.PART / 2 || RD.parts.length === 1)) { RD.cpp = (p.end - p.start) / RD.pages; RD.cppKey = key; }
    RD.page = at === -1 ? RD.pages - 1 : at == null ? 0 : Math.min(RD.pages - 1, Math.round((at - p.start) / Math.max(1, p.end - p.start) * RD.pages));
  } else {
    stage.innerHTML = `<div class="rscroll" id="rscroll">${text}</div>`;
    const sc = rEl('rscroll'); RD.pages = 1; RD.page = 0;
    const max = sc.scrollHeight - sc.clientHeight;
    sc.scrollTop = at === -1 ? max : at == null ? 0 : (at - p.start) / Math.max(1, p.end - p.start) * max;
    sc.onscroll = () => rFoot();
  }
  rEl('rmode').textContent = RD.mode === 'page' ? 'Scroll' : 'Pages';
  rEl('rsmaller').disabled = RD.size === 0; rEl('rlarger').disabled = RD.size === RD.SIZES.length - 1;
  rShow();
}
function rShow() {
  const c = rEl('rcols');
  if (c) c.style.transform = `translateX(${-RD.page * (RD.pageW + RD.GAP)}px)`;
  rFoot();
}
// where the reader is, as a character offset into the book
function rAt() {
  const p = RD.parts[RD.part], len = p.end - p.start, sc = rEl('rscroll');
  const f = RD.mode === 'page' ? RD.page / RD.pages : sc && sc.scrollHeight > sc.clientHeight ? sc.scrollTop / (sc.scrollHeight - sc.clientHeight) : 0;
  return Math.round(p.start + f * len);
}
function rFoot() {
  const d = RD.book, at = rAt(), p = RD.parts[RD.part];
  rset('thorp.read.at:' + d.book_id, at);
  const done = d.chars ? at / d.chars : 0;
  const perPage = Math.max(1, RD.cppKey && RD.cppKey.startsWith(d.book_id + '|') ? RD.cpp : (p.end - p.start) / RD.pages);
  const where = RD.mode === 'page' ? `Page ${Math.floor(at / perPage) + 1} of ${Math.max(1, Math.ceil(d.chars / perPage))}` : `Part ${RD.part + 1} of ${RD.parts.length}`;
  rEl('rpos').textContent = `${where}  ·  ${Math.round(done * 100)}%`;
  const mins = Math.max(0, (d.chars - at) / RD.CPM);
  rEl('rleft').textContent = mins >= 90 ? `${(mins / 60).toFixed(1)} h left in book` : `${Math.max(1, Math.round(mins))} min left in book`;
}
function rTurn(by) {
  if (RD.mode === 'page' && RD.page + by >= 0 && RD.page + by < RD.pages) { RD.page += by; return rShow(); }
  if (RD.mode === 'scroll') {
    const sc = rEl('rscroll'), max = sc.scrollHeight - sc.clientHeight;
    if ((by > 0 && sc.scrollTop < max - 2) || (by < 0 && sc.scrollTop > 2)) return sc.scrollBy({ top: by * sc.clientHeight * 0.9 });
  }
  const next = RD.part + by;
  if (next < 0 || next >= RD.parts.length) return;
  RD.part = next; rRender(by > 0 ? null : -1);
}
// a Dialog: focus moves in when it opens and back to what opened it when it closes
let rFrom = null;
function openReader() {
  const el = rEl('reader');
  if (el.hidden) rFrom = document.activeElement;
  el.hidden = false;
  rEl('rclose').focus();
}
const closeReader = () => { rEl('reader').hidden = true; if (rFrom && rFrom.isConnected) rFrom.focus(); rFrom = null; };
rEl('rclose').onclick = closeReader;
rEl('rsmaller').onclick = () => { const at = rAt(); RD.size--; rset('thorp.read.size', RD.size); rRender(at); };
rEl('rlarger').onclick = () => { const at = rAt(); RD.size++; rset('thorp.read.size', RD.size); rRender(at); };
rEl('rmode').onclick = () => { const at = rAt(); RD.mode = RD.mode === 'page' ? 'scroll' : 'page'; rset('thorp.read.mode', RD.mode); rRender(at); };
rEl('rstage').addEventListener('click', e => {
  if (RD.mode !== 'page' || e.target.closest('a') || !window.getSelection().isCollapsed) return;
  const b = rEl('rstage').getBoundingClientRect(), x = (e.clientX - b.left) / b.width;
  if (x > 0.7) rTurn(1); else if (x < 0.3) rTurn(-1);
});
window.addEventListener('resize', () => { if (!rEl('reader').hidden && RD.book) rRender(rAt()); });
document.addEventListener('keydown', e => {
  if (rEl('reader').hidden || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === 'Escape') return closeReader();
  if (e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && !e.shiftKey)) { e.preventDefault(); rTurn(1); }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || (e.key === ' ' && e.shiftKey)) { e.preventDefault(); rTurn(-1); }
});
// any book row on a model page opens the reader: the Forgotten Tomes (Scoring) and the shelves (Training)
document.addEventListener('click', e => {
  const tr = e.target.closest('#tomestable tr[data-book], #shelftable tr[data-book]');
  if (tr && !e.target.closest('.info')) openBook(tr.dataset.book);
});
