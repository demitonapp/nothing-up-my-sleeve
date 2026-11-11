// Small shared helpers used by several views, extracted (and typed) from the view monolith. All are pure:
// they format a value or a small badge, and touch no module state or DOM.

import { esc, fmt, signed } from '../../lib/format';
import { pillCls } from '../../lib/ui';

export const MOVE_LABEL: Record<string, string> = { appears: 'appears', vanishes: 'vanishes', earlier: 'earlier', later: 'later', same: 'same' };

export const fmtTok = (t: number | null | undefined): string =>
  t == null ? '' : t >= 1e6 ? `${Math.round(t / 1e6)}M` : `${Math.round(t / 1e3)}k`;

export const fallText = (f: any): string =>
  !f ? '<span class="s">not sailed</span>' : !f.charted ? '<span class="s">uncharted</span>'
    : f.played ? `played at ${fmtTok(f.tokens)} tokens${f.layer != null ? `, layer ${f.layer}` : ''}` : '<span class="s">not played</span>';

export const hms = (s: number | null | undefined): string =>
  s == null ? '–' : s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min` : `${Math.round(s / 60)} min`;

export const TRAIT_LABEL: Record<string, string> = { fiction: 'fiction', verse: 'verse', first_person: 'first person' };

export const firstAt = (sr: { step: number[]; value: any[] } | null | undefined, ok: (v: any) => boolean): number | null | undefined => {
  if (!sr) return undefined;
  const i = sr.value.findIndex(ok);
  return i < 0 ? null : sr.step[i];
};

export const lastOf = (sr: { value: any[] } | null | undefined): any | null => (sr && sr.value.length ? sr.value[sr.value.length - 1] : null);

export const statusPill = (st: string | null | undefined): string =>
  `<span class="${pillCls({ running: 'blue', done: 'good', paused: 'accent' }[st as string] || '')}">${esc(st || '')}</span>`;

export const STAR_LABEL: Record<string, string> = { previous_word: 'the Previous Word', duplicate_word: 'the Duplicate Word', nevermore: 'Nevermore' };

// a library's language families as a stacked bar, each family a colour assigned in first-seen order (UI.md "Library").
const FAMILY_TOK = ['blue', 'accent', 'good', 'bad', 'c5', 'c6', 'c7', 'c8', 'c9', 'c10'];
const familyColour = (() => {
  const seen: Record<string, string> = {};
  return (f: string): string => seen[f] || (seen[f] = `var(--${FAMILY_TOK[Object.keys(seen).length % FAMILY_TOK.length]})`);
})();
export const familyBar = (fam: Record<string, number> | null | undefined): string => {
  const n = Object.values(fam || {}).reduce((a, b) => a + b, 0);
  if (!n) return '<span class="s">–</span>';
  const entries = Object.entries(fam as Record<string, number>);
  return `<div class="fbar" title="${esc(entries.map(([f, k]) => `${f} ${k}`).join(' · '))}">${entries.map(([f, k]) => `<span style="width:${(100 * k) / n}%;background:${familyColour(f)}"></span>`).join('')}</div>`;
};

// A card's badge on the leaderboard (verdicts from s4.outside_readings): necessary, marker, or neither.
export const cardBadge = (verdicts: Record<string, any> | null | undefined, key: string): string => {
  const v = (verdicts || {})[key];
  if (!v) return '';
  const tip = `played by ${v.chainers_lit} of the models that chain two facts; dark in ${v.non_chainers_dark} that don't`;
  if (v.valid === false) return `<span class="vbadge warn" title="${esc(tip)}: the reading is not trusted yet">not trusted</span>`;
  if (v.marker) return `<span class="vbadge marker" title="${esc(tip)}: only the chainers play it">marker</span>`;
  if (v.necessary) return `<span class="vbadge need" title="${esc(tip)}: every chainer plays it, so a ship must draw it">necessary card</span>`;
  return `<span class="vbadge" title="${esc(tip)}">neither necessary nor a marker</span>`;
};

// The art (thorp/dash/art/): one image per size of ship and one per playing card; an image that isn't there removes itself.
export const ART_CARDS = new Set(['previous_word', 'nevermore', 'mover', 'comparator', 'bridge']);
// The art is regenerated in place, and a browser will happily serve the plate it already has: the version
// takes the query string so a regeneration is seen on the next load. Bump it when the art is regenerated
// (python -m thorp.dash.art.generate_art), and every plate is fetched again once.
export const ART_V = '2026-11-11-theme';
export const artImg = (key: string | null | undefined, cls = 'cardart'): string =>
  key ? `<img class="${cls}" src="/art/${encodeURIComponent(key)}.png?v=${ART_V}" alt="" loading="lazy" onerror="this.remove()">` : '';
export const cardArt = (key: string): string => (ART_CARDS.has(key) ? artImg(key, 'cardart face') : '');
export const flagImg = (flag: string | null | undefined, name?: string, cls = 'flag'): string => {
  if (!flag) return '';
  const label = name || flag;
  return `<img class="${cls}" src="/flags/${encodeURIComponent(flag)}.svg" alt="${esc(label)}" title="${esc(label)}" loading="lazy">`;
};

// A first sentence or two, up to 170 characters (a full stop then a space ends a sentence; 0.3 does not).
export const shortAbout = (t: string | null | undefined): string => {
  if (!t) return '';
  const sents = t.trim().split(/(?<=\.)\s+/);
  let out = '';
  for (const x of sents) {
    if ((out + ' ' + x).length > 170) break;
    out = out ? out + ' ' + x : x;
  }
  return out || sents[0].split(': ')[0].replace(/[.,;]?$/, '.');
};

// The cause-and-effect chaining gain as a cell: the mark at 0.1, dotted, lit when at it.
const CAUSE_NOTE = "the logic deck's chaining gain on its cause-and-effect items (when X, then Y; Y makes Z): eight items, so a strong reading counts and a small one is noise; the mark, 0.1, dotted";
export const causeCell = (v: number | null): string => {
  if (v == null || !isFinite(v)) return '<span class="s">not read</span>';
  const pos = Math.max(-0.2, Math.min(1, v));
  const w = (100 * (pos + 0.2)) / 1.2;
  const mark = (100 * (0.1 + 0.2)) / 1.2;
  const zero = (100 * 0.2) / 1.2;
  return `<span class="cause${v >= 0.1 ? ' lit' : ''}" title="${esc(CAUSE_NOTE)}"><b>${signed(v)}</b><span class="cbar"><i style="left:${Math.min(w, zero)}%;width:${Math.abs(w - zero)}%"></i><u style="left:${mark}%"></u></span></span>`;
};

// The stars a voyage's runs have lit so far (UI.md "Expeditions"/"Voyages"): one line per star, its soonest
// light (one head, or two heads together) or its best score yet.
export const starHeadline = (v: { runs: any[] }): string =>
  Object.values(
    v.runs.reduce((acc: Record<string, any>, r) => {
      (r.stars || []).forEach((x: any) => {
        const a = acc[x.star] || (acc[x.star] = { star: x.star, lit: null, ship: null, shared: null, sship: null, best: null });
        if (x.steps_to_lit != null && (a.lit == null || x.steps_to_lit < a.lit)) { a.lit = x.steps_to_lit; a.ship = r.ship_name || r.ship || r.name; }
        if (x.shared_steps_to_lit != null && (a.shared == null || x.shared_steps_to_lit < a.shared)) { a.shared = x.shared_steps_to_lit; a.sship = r.ship_name || r.ship || r.name; }
        if (x.best != null && (a.best == null || x.best > a.best)) a.best = x.best;
      });
      return acc;
    }, {}),
  )
    .filter((a: any) => a.best != null)
    .map((a: any) => {
      const n = STAR_LABEL[a.star] || a.star;
      return a.lit != null ? `${n} lit at step ${a.lit} (${a.ship})`
        : a.shared != null ? `${n} lit shared at step ${a.shared} (${a.sship}), no single head yet (best ${fmt(a.best)})`
        : `${n} not lit yet, best ${fmt(a.best)}`;
    })
    .join('; ');

// the metre scaffold's phases within pretraining (thorp/train.py optim.scaffold): metre, fade, content, you are here
export function scaffoldBar(sc: any, tokens: number): string {
  if (!sc) return '';
  const total = sc.bands[sc.bands.length - 1].to || 1;
  // a floor (optim.scaffold.floor) holds the pull from the fade's end to the voyage's end: no stretch of language alone
  const floor = sc.floor || 0;
  const about: Record<string, string> = floor
    ? { metre: 'heads pulled to the pattern', fade: `the pull eased from ${sc.weight ?? 1} to ${floor}`, content: `the pull held at ${floor} to the end: held with a light hand?` }
    : { metre: 'heads pulled to the pattern', fade: 'the pull eased away', content: 'language alone: held by heart?' };
  const heads = sc.heads.map((h: any) => `${esc(h.card.replace(/_/g, '-'))} in layer ${h.layer} (head ${h.head})`).join(', ');
  return `<div class="s" style="margin-top:8px">pretraining in phases: the metre scaffold pins ${heads}</div><div class="wstagebar">${sc.bands.map((b: any) => {
    const state = tokens >= b.to ? 'done' : tokens >= b.from ? 'now' : 'later';
    const fill = state === 'done' ? 100 : state === 'now' ? Math.round(100 * (tokens - b.from) / Math.max(b.to - b.from, 1)) : 0;
    return `<div class="wstage" style="flex:${Math.max(100 * (b.to - b.from) / total, 4)}"><div class="wsname"><b>${b.phase}</b> <span class="s">${about[b.phase]}</span></div><div class="wpasses"><div class="wpass ${state}"><i style="width:${fill}%"></i><span>${((b.to - b.from) / 1e6).toFixed(1)}M tokens</span></div></div></div>`;
  }).join('')}</div>`;
}
