// The Scoring tab's "maths" sub-page, extracted (and typed) from the view monolith: the credit line, the chapter
// index, and the per-voyage answer table. Pure: each takes the maths book (mathsData) and the source helper as
// arguments; nothing touches module state or DOM.

import { esc } from '../../lib/format';
import { btnCls, pillCls } from '../../lib/ui';
import { chose, mathsSource } from './ask';

export const mathsCredit = (mathsData: any): string => {
  const b = mathsData.book;
  if (!b) return '';
  return `<div class="mathcredit">After <b>${esc((b.author || '').replace(/^De Morgan, Augustus.*$/, 'Augustus De Morgan'))}</b>, <i>${esc(b.title)}</i> (${esc(b.edition)}): each chapter follows a section of his Book I, Principles of Arithmetic, in his order; the sums are in plain words, not his. <button type="button" class="${btnCls('outline', 'bookbtn')}" data-mbook="${esc(b.id)}" data-at="0">open the book</button>${b.in_ogden ? '' : ' <span class="s">Nothing up my sleeve\'s Ogden ships have not read it (it is in neither Ogden v0.1 nor v0.2): what they know of sums, they learnt elsewhere</span>'}</div>`;
};

export const mathsIndex = (mathsData: any): string =>
  `${mathsCredit(mathsData)}<div class="scroll"><table class="mathstable"><thead><tr><th>chapter</th><th>what it teaches</th><th>a sum from it</th><th>from the book</th></tr></thead><tbody>${mathsData.chapters.map((c: any) => `<tr><td><b>${c.n}. ${esc(c.title)}</b></td><td class="s">${esc(c.about)}</td><td class="mono">${esc(c.sums[0].text)} <b>${esc(c.sums[0].hope)}</b> <span class="s">not</span> <i>${esc(c.sums[0].rival)}</i></td><td>${mathsSource(c)}</td></tr>`).join('')}</tbody></table></div>`;

export const mathsTable = (mathsData: any, run: string, res: any, done: boolean): string => {
  const mark = mathsData.mark || 6;
  let learnt = 0;
  let open = true;
  for (const c of mathsData.chapters) {
    const r = res[c.n];
    if (!r || r.length < c.sums.length) break;
    if (open && r.filter((x: any) => x.ok).length >= mark) learnt = c.n;
    else open = false;
  }
  const total = Object.values(res).flat() as any[];
  const right = total.filter((x: any) => x.ok).length;
  const head = `<div class="ovq">${esc(run)} · <b>${right} of ${total.length}</b> sums right${done ? ` · <b>${learnt ? `learnt up to chapter ${learnt}, ${esc(mathsData.chapters[learnt - 1].title.toLowerCase())}` : 'not yet past chapter 1, counting on'}</b>` : ' · reading…'}</div>`;
  const rows = mathsData.chapters.filter((c: any) => res[c.n]).map((c: any) => {
    const r = res[c.n];
    const n = r.filter((x: any) => x.ok).length;
    const full = r.length === c.sums.length;
    const sums = r.map((x: any) => `<tr class="mathsum"><td></td><td class="mono">${esc(x.q.text)}</td><td>${esc(x.q.hope)} <span class="s">${x.rank ? `guess ${x.rank}` : 'not in ten'}</span></td><td>${esc(x.q.rival)} <span class="s">${x.rrank ? `guess ${x.rrank}` : 'not in ten'}</span></td>
      <td>${x.err ? '<span class="s">failed</span>' : `<span class="${pillCls(x.ok ? 'good' : chose(x.rank, x.rrank) === 'the rival' ? 'bad' : '')}">${x.ok ? 'right' : chose(x.rank, x.rrank) === 'the rival' ? 'the rival' : 'neither'}</span>`}</td>
      <td class="mono s">${(x.top || []).map((g: any) => `${esc(g.word)} ${(100 * g.p).toFixed(0)}%`).join(' · ')}</td></tr>`).join('');
    return `<tr class="mathchap"><td><b>${c.n}. ${esc(c.title)}</b><div>${mathsSource(c)}</div></td><td class="s" colspan="3">${esc(c.about)}</td>
      <td><span class="${pillCls(!full ? '' : n >= mark ? 'good' : 'bad')}">${n} of ${r.length}${full ? (n >= mark ? ' · learnt' : ' · not yet') : ''}</span></td><td><div class="mathbar"><span style="width:${(100 * n) / c.sums.length}%"></span></div></td></tr>${sums}`;
  }).join('');
  return `${mathsCredit(mathsData)}${head}<div class="scroll"><table class="mathstable"><thead><tr><th>chapter</th><th>the sum</th><th>the answer</th><th>the rival</th><th>verdict</th><th>its first three guesses</th></tr></thead><tbody>${rows}</tbody></table></div>`;
};
