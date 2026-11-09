// The fitout's selection cards (UI.md "Fitouts"), extracted (and typed) from the view monolith: the counts
// bar and the declared-rules chips. Pure: each takes its data and returns an HTML string.

import { big, esc } from '../../lib/format';
import { pillCls } from '../../lib/ui';
import { shipHash } from '../router';
import { statusPill } from './helpers';

// A shelf's trigram scatter (variety against repetition, the Pareto frontier marked), as a small SVG.
export const triScatter = (t: any): string => {
  if (!t || !t.books || !t.books.length) return `<span class="s">${t && t.computing ? 'measuring…' : t ? 'unmeasured' : ''}</span>`;
  const W = 120;
  const H = 64;
  const xs = t.books.map((b: any) => b.variety);
  const ys = t.books.map((b: any) => b.repeat_rate);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const y0 = 0;
  const y1 = Math.max(...ys, 0.01);
  const front = new Set(t.frontier || []);
  const px = (v: number): number => 4 + (W - 8) * (x1 > x0 ? (v - x0) / (x1 - x0) : 0.5);
  const py = (v: number): number => H - 4 - (H - 8) * (v - y0) / (y1 - y0);
  return `<svg class="triscatter" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="variety against repetition">
    <line x1="4" y1="${H - 4}" x2="${W - 4}" y2="${H - 4}" class="tsaxis"/><line x1="4" y1="4" x2="4" y2="${H - 4}" class="tsaxis"/>
    ${t.books.map((b: any) => `<circle cx="${px(b.variety).toFixed(1)}" cy="${py(b.repeat_rate).toFixed(1)}" r="${front.has(b.id) ? 2.8 : 1.6}" class="${front.has(b.id) ? 'tsf' : 'tsb'}"><title>${esc(b.id)}: repetition ${(100 * b.repeat_rate).toFixed(1)}%, variety ${(100 * b.variety).toFixed(0)}%${front.has(b.id) ? ' (frontier)' : ''}</title></circle>`).join('')}
  </svg>`;
};

export const selCounts = (
  title: string,
  note: string,
  m: Record<string, { share: number; books: number; words: number }> | null | undefined,
  order?: (a: string, b: string) => number,
): string => {
  const ks = Object.keys(m || {});
  if (!ks.length) return '';
  if (order) ks.sort(order);
  const max = Math.max(...ks.map((k) => m![k].share), 0.001);
  return `<div class="selcount"><div class="k">${esc(title)} <span class="s">${esc(note)}</span></div>${ks.map((k) => `<div class="selrow"><span class="selkey" title="${esc(k)}">${esc(k)}</span><span class="selbar"><i style="width:${((100 * m![k].share) / max).toFixed(1)}%"></i></span><span class="selnum">${(100 * m![k].share).toFixed(1)}% <span class="s">${m![k].books} books · ${big(m![k].words)} words</span></span></div>`).join('')}</div>`;
};

export const selDeclared = (c: any): string => {
  if (!c) return '<div class="s">its library is listed by hand: no weights or filters are declared, so the counts below are of the books as listed</div>';
  const chip = (a: string, b: string): string => `<span class="selchip"><span class="s">${esc(a)}</span> ${esc(b)}</span>`;
  const inc = (n: string, v: any): string => (v.include.length || v.exclude.length) ? chip(n, [v.include.length ? 'only ' + v.include.join(', ') : '', v.exclude.length ? 'not ' + v.exclude.join(', ') : ''].filter(Boolean).join('; ')) : '';
  const p = c.period || {};
  return [
    chip('languages', Object.entries(c.languages || {}).map(([k, v]) => `${k} ${v}`).join(', ')),
    c.as_of ? chip('library as of', c.as_of) : '',
    c.ogden && c.ogden.min != null ? chip('Ogden-ness', `at least ${Math.round(100 * c.ogden.min)}%${c.ogden.scored_by ? ' (scored by ' + c.ogden.scored_by.join(', ') + ')' : ''}`) : '',
    (p.start != null || p.end != null) ? chip('period', `${p.start ?? '…'} to ${p.end ?? '…'}; undated ${p.undated}d`) : chip('period', 'any (the gate: no name dead after 1955)'),
    inc('kinds', c.kinds), inc('voices', c.voices), inc('sources', c.sources), inc('shelves', c.shelves),
    ...Object.entries(c.weights || {}).map(([k, v]) => chip('weights by ' + k, Object.entries(v as Record<string, unknown>).map(([a, b]) => `${a} ${b}`).join(', '))),
    c.dedupe ? chip('one copy a title', 'keep ' + (c.dedupe.keep || 'ogden')) : '',
    ...(c.carry || []).map((l: string) => chip('carries', l)),
    ...(c.strike || []).map((x: any) => chip('strikes', `${x.title || x.book} (${x.why || ''})`)),
    ...(c.append || []).map((x: any) => chip('appends', `${x.list} (${x.why || ''})`)),
    c.words ? chip('budget', big(c.words) + ' words') : '',
  ].filter(Boolean).join(' ');
};

// One fitout's card (UI.md "Fitouts"): its stages as pretraining and post-training lanes, its runs below.
export const fitoutCard = (f: any): string => {
  const tackOf = (t: any): string => (t ? `${esc(t.kind || 'tack')}${t.alpha != null ? ` ×${t.alpha}` : ''}` : '');
  const lane = (f: any, phase: string, label: string, note: string): string => {
    const st = (f.stages || []).filter((x: any) => x.phase === phase).sort((a: any, b: any) => a.order - b.order);
    if (!st.length) return '';
    const total = st.reduce((a: number, x: any) => a + (x.tokens || 0), 0);
    return `<div class="folane"><div class="folabel">${label} <span class="s">${big(total)} tokens · ${note}</span></div><div class="foblocks">${st.map((x: any, i: number) => `
      <div class="foblock ${phase === 'post-training' ? 'post' : 'pre'}" style="flex-grow:${Math.max(1, x.tokens || 0)}" title="${esc(x.purpose || '')}">
        <div class="fobn"><b>${x.order}. ${esc(x.name)}</b>${i ? '<span class="s"> ← seeded from the stage before</span>'.repeat(phase === 'post-training' ? 1 : 0) : ''}</div>
        <a class="foshelf" data-shelf="${esc(x.shelf)}" href="/library">${esc(x.shelf_name || x.shelf)}</a>
        <div class="s">${x.books} books · ${big(x.tokens_per_pass)} × ${x.passes} = ${big(x.tokens)}</div>
        ${phase === 'post-training' ? `<div class="s">${x.lr != null ? `lr ${x.lr}` : ''}${x.tack ? ` · tack ${tackOf(x.tack)}` : ''}</div>` : ''}
        <div class="fop">${esc(x.purpose || '')}</div></div>`).join('')}</div></div>`;
  };
  return `<div class="fitout">
    <div class="fohead"><span class="${pillCls('')}">${esc(f.preset || '')}</span> <b>${esc(f.name)}</b></div>
    <p class="foaim">${esc(f.aim || '')}</p>
    <div class="s">${[f.positions ? `positions ${esc(f.positions)}` : 'learned positions', f.vocab ? `vocabulary ${big(f.vocab)}` : '', f.tack ? `tack ${tackOf(f.tack)}` : '', f.tokens ? `${big(f.tokens)} tokens in all` : ''].filter(Boolean).join(' · ')}</div>
    ${lane(f, 'pretraining', 'Pretraining', 'its stages in order, one voyage')}
    ${lane(f, 'post-training', 'Post-training', 'each stage seeded from the one before')}
    <div class="foruns"><span class="s">voyages</span> ${(f.runs || []).map((r: any) => `<span class="forun">${r.status && r.status !== 'queued' ? `<a href="${shipHash(r.run)}">${esc(r.run)}</a>` : esc(r.run)} ${statusPill(r.status || 'queued')}</span>`).join('') || '<span class="s">none yet</span>'}</div>
  </div>`;
};
