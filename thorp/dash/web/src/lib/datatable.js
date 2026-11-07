// ---- DataTable: the one sortable table every table on the page uses. Click a header to sort by it,
// again to reverse, a third time for the order it was drawn in. It attaches to every <table> by
// itself (opt out with data-nosort), and keeps each table's sort while the page redraws it every
// 5 s. A cell may carry data-sort="…" to sort by something other than its text. Rows that are not
// data (a single colspan cell: "no runs yet", "12 of 40 books") stay at the bottom.
// Every table, sortable or not, also takes shadcn's Table classes here (UI.md, "shadcn"), so the
// markup that builds tables never has to name them.
import { tableCls } from './ui';
const DataTable = (() => {
  const state = new Map();  // table key -> { col, dir }
  const UNIT = { k: 1e3, K: 1e3, M: 1e6, B: 1e9, G: 1e9, T: 1e12, KB: 1e3, MB: 1e6, GB: 1e9, TB: 1e12, '%': 1 };
  const NUM = /^([+\-−]?\d*\.?\d+(?:e[+\-]?\d+)?)\s*(KB|MB|GB|TB|[kKMBGT%])?$/;
  // cell text without the ⓘ popovers, which carry a paragraph of help text
  const text = n => n.nodeType === 3 ? n.nodeValue : n.classList && n.classList.contains('info') ? '' : [...n.childNodes].map(text).join('');
  const headers = table => [...table.querySelectorAll('thead th')];
  const key = table => {
    const host = table.id || (table.closest('[id]') || {}).id || '';
    return host + '|' + headers(table).map(th => text(th).trim()).join('|');
  };
  const value = td => {
    if (!td) return null;
    const s = (td.dataset.sort ?? text(td)).trim().replace(/,/g, '');
    if (!s || s === '–' || s === '-' || s === '—') return null;
    const m = s.match(NUM);
    return m ? parseFloat(m[1].replace('−', '-')) * (UNIT[m[2]] || 1) : s.toLowerCase();
  };
  const isData = (tr, n) => tr.cells.length === n && ![...tr.cells].some(td => td.colSpan > 1);
  function apply(table) {
    const body = table.tBodies[0], ths = headers(table);
    if (!body || !ths.length) return;
    const rows = [...body.rows];
    const link = table.classList.contains('clickable');
    rows.forEach((tr, i) => {
      if (tr.dataset.dti === undefined) tr.dataset.dti = i;
      if (link && isData(tr, ths.length) && !tr.hasAttribute('tabindex')) tr.tabIndex = 0;
    });
    const st = state.get(key(table)) || { col: -1, dir: 0 };
    ths.forEach((th, i) => {
      th.classList.add('dt-sortable');
      th.classList.toggle('dt-asc', i === st.col && st.dir === 1);
      th.classList.toggle('dt-desc', i === st.col && st.dir === -1);
    });
    const data = rows.filter(tr => isData(tr, ths.length)), rest = rows.filter(tr => !isData(tr, ths.length));
    const byOrder = (a, b) => a.dataset.dti - b.dataset.dti;
    data.sort(st.dir === 0 ? byOrder : (a, b) => {
      const x = value(a.cells[st.col]), y = value(b.cells[st.col]);
      if (x === null || y === null) return x === y ? byOrder(a, b) : x === null ? 1 : -1;  // blanks last either way
      if (typeof x !== typeof y) return (typeof x === 'number' ? -1 : 1) * st.dir;
      return (x < y ? -1 : x > y ? 1 : byOrder(a, b) * st.dir) * st.dir;
    });
    const want = [...data, ...rest];
    if (want.some((tr, i) => rows[i] !== tr)) body.append(...want);
  }
  // the Table look: once per element, marked so a redraw only styles what is new
  const STYLE = [['', 'table'], ['thead', 'head'], ['tbody', 'body'], ['tr', 'row'], ['th', 'th'], ['td', 'td']];
  function style(table) {
    STYLE.forEach(([sel, k]) => (sel ? table.querySelectorAll(sel) : [table]).forEach(el => {
      if (el.dataset.slot) return;
      el.dataset.slot = k === 'th' ? 'table-head' : k === 'td' ? 'table-cell' : k === 'head' ? 'table-header' : k === 'body' ? 'table-body' : k === 'row' ? 'table-row' : 'table';
      el.classList.add(...tableCls[k].split(' '));
    }));
  }
  function scan(root) {
    const tables = root.tagName === 'TABLE' ? [root] : [...root.querySelectorAll('table')];
    tables.forEach(style);
    tables.filter(t => !t.hasAttribute('data-nosort')).forEach(apply);
  }
  const obs = new MutationObserver(muts => {
    const hit = new Set();
    muts.forEach(m => {
      const t = m.target.closest && m.target.closest('table');  // also a table drawn with data-nosort, for its look
      if (t) hit.add(t); else m.addedNodes.forEach(n => n.nodeType === 1 && (n.tagName === 'TABLE' ? hit.add(n) : n.querySelectorAll('table').forEach(x => hit.add(x))));
    });
    hit.forEach(t => { if (!t.isConnected) return; style(t); if (!t.hasAttribute('data-nosort')) apply(t); });
    obs.takeRecords();  // our own reordering is not a redraw
  });
  document.addEventListener('click', e => {
    const th = e.target.closest('thead th');
    if (!th || e.target.closest('.info')) return;
    const table = th.closest('table');
    if (table.hasAttribute('data-nosort')) return;
    const k = key(table), col = headers(table).indexOf(th), st = state.get(k) || { col: -1, dir: 0 };
    const dir = st.col !== col ? 1 : st.dir === 1 ? -1 : st.dir === -1 ? 0 : 1;
    state.set(k, { col, dir });
    apply(table); obs.takeRecords();
  });
  // a clickable table's rows open on Enter or Space, as they do on a click
  document.addEventListener('keydown', e => {
    const tr = e.target.closest && e.target.closest('table.clickable tbody tr[tabindex]');
    if (tr && e.target === tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); tr.click(); }
  });
  function start() { scan(document.body); obs.observe(document.body, { childList: true, subtree: true }); }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  return { refresh: scan };
})();

export { DataTable };
