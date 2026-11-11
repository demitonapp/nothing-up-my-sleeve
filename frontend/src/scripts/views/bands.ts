// The three size bands the Market Harbour and the leaderboard share (11 November, Justin: "small 300k -
// 4B ... a medium band for 4 - 32B and then large is anything above 32B"): one definition, so the two
// pages cannot disagree about where a model sits. A model at exactly 4B is small and one at exactly 32B
// is medium, the way the bands were spoken; above 32B is large.

import { cardCls } from '../../lib/ui';

export type SizeBand = 'xsmall' | 'small' | 'medium' | 'large';

export interface Band {
  key: SizeBand;
  name: string;
  range: string;
  about: string;
  art: string;
}

export const BANDS: Band[] = [
  {
    key: 'xsmall',
    name: 'Extra small',
    range: 'under 1B',
    about: 'the small end: under a billion parameters, where our own fleet sits and the smallest outside models are read',
    art: 'band-xsmall',
  },
  {
    key: 'small',
    name: 'Small',
    range: '1B – 4B',
    about: 'the four-billion line: the models where chaining has been read, and the size our fleet grows toward',
    art: 'band-small',
  },
  {
    key: 'medium',
    name: 'Medium',
    range: '4B – 32B',
    about: 'the middle of the field: 4 to 32 billion parameters, a size above every ship we have built',
    art: 'band-medium',
  },
  {
    key: 'large',
    name: 'Large',
    range: 'above 32B',
    about: 'the deep end: above 32 billion parameters, the class nothing read here has reached yet',
    art: 'band-large',
  },
];

export const BAND = (key: string | null | undefined): Band | undefined => BANDS.find((b) => b.key === key);

/** A model's band by its parameter count. Small is the floor (300k is our smallest ship); anything at
 *  or under 4B is small, at or under 32B is medium, and above 32B is large. */
export const bandOf = (params: number | null | undefined): SizeBand => {
  if (params == null || !Number.isFinite(Number(params))) return 'small';
  const p = Number(params);
  if (p > 32e9) return 'large';
  if (p > 4e9) return 'medium';
  if (p >= 1e9) return 'small';
  return 'xsmall';
};

/** A model's size: its published count, or the size in its name when the registry has none (Maincoder-1B,
 *  Qwen3.5-0.8B), so a model with a reading is never dropped from the bands. */
export const sizeOf = (x: any): number | null => {
  if (x && x.params != null && Number.isFinite(Number(x.params))) return Number(x.params);
  if (x && x.total != null && Number.isFinite(Number(x.total))) return Number(x.total);
  const m = /(\d+(?:\.\d+)?)\s*([bmk])\b/i.exec(String((x && (x.label || x.name)) || ''));
  if (!m) return null;
  const n = parseFloat(m[1]);
  const unit = m[2].toLowerCase();
  return n * (unit === 'b' ? 1e9 : unit === 'm' ? 1e6 : 1e3);
};

export interface BandCardOptions {
  /** The address the card opens; omit for a card that is chosen in place (the leaderboard). */
  href?: string;
  /** Marks the band the page is showing. */
  active?: boolean;
  /** The middle of the card: what is in the band, as HTML. */
  body: string;
  /** One or two foot lines, each [left, right]. */
  feet?: [string, string][];
  /** The last foot's right-hand call to action. */
  cta?: string;
}

/** One band card, the same card on both pages: its fal image, name and range, what sits in the band, and
 *  the way in. A card with no href carries `data-band` for the page to choose it in place. */
export function bandCardHtml(b: Band, o: BandCardOptions): string {
  const tag = o.href ? 'a' : 'div';
  const attrs = o.href ? `href="${o.href}"` : 'role="button" tabindex="0"';
  const feet = (o.feet || []).map(([l, r]) => `<div class="foot"><span>${l}</span><span>${r}</span></div>`).join('');
  const cta = o.cta ? `<div class="foot"><span></span><span>${o.cta}</span></div>` : '';
  return `<${tag} class="${cardCls(!!o.href, 'card bandcard')}${o.active ? ' active' : ''}" ${attrs} data-band="${b.key}">
    <img class="cardart ship" src="/art/${b.art}.png" alt="" loading="lazy" onerror="this.remove()">
    <div class="top"><span class="preset">${b.name}</span><span class="nm">${b.range}</span></div>
    <div class="job">${b.about}</div>
    <div class="ov">${o.body}</div>
    ${feet}${cta}
  </${tag}>`;
}
