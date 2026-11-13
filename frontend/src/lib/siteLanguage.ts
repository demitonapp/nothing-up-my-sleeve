// The site's language (13 November, Justin: "add your language in the chat terminal as an option. When you do that, the
// Liberty Machine picks up the language you've chosen and uses tiny aya earth to dynamically translate the entire site").
//
// The English on the page is the record. This puts a view of it into the language the Liberty Machine holds (S5,
// s5.site_language): every text node and the placeholder, title, aria-label and alt attributes are sent, a few at a time,
// to /api/translate (Tiny Aya Earth, kept in s1.translations so a sentence is translated once), and the answer is written
// over the page. The English is remembered beside each node, so choosing English puts every word back. Nothing here writes
// a translation anywhere but the screen and a small browser cache.
//
// A visitor may have the translating done on their own box instead (13 November: lib/uiModels.ts `translateOnBox`): the
// page then asks that model, straight from this browser, and nothing goes to /api/translate.
//
// Left alone: code, the chat transcript (what was said stays what was said), the language picker (each language in its
// own), numbers, identifiers and anything marked translate="no" or data-no-translate.

import { loadTranslator, translateOnBox } from './uiModels';

export interface Language {
  code: string;
  name: string;
  native_name: string;
  rtl: boolean;
  listed: boolean;
  is_source: boolean;
}

export interface LanguageState {
  language: Language & { chosen_by?: string; chosen_at?: string | null };
  languages: Language[];
  translator: { model: string; weights: string | null; ready: boolean; why: string | null; loaded: boolean; glossary?: string[] };
  note: string | null;
}

export interface Progress {
  code: string;
  state: 'idle' | 'working' | 'blocked';
  done: number;
  total: number;
  why?: string;
}

export const LANGUAGE_EVENT = 'thorp:language';
export const PROGRESS_EVENT = 'thorp:translate-progress';

const KEEP_LANG = 'thorp.language';
const CHUNK = 16;
const SKIP =
  'script,style,noscript,code,pre,kbd,samp,textarea,input,select,option,svg,canvas,iframe,[contenteditable="true"],' +
  '[translate="no"],[data-no-translate],.consoletranscript,.consolechat';
const NO_ATTRS = 'script,style,code,pre,svg,[translate="no"],[data-no-translate],.consoletranscript,.consolechat';
const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'] as const;

/** The rule in thorp/translate.py (`worth_translating`), kept in step with it by hand: prose and labels, not identifiers. */
export function worthTranslating(s: string): boolean {
  const t = s.trim();
  if (!t || t.length > 1200 || !/\p{L}{2,}/u.test(t)) return false;
  if (!t.includes(' ')) return /^\p{L}{2,}[.:!?…]?$/u.test(t);
  let letters = 0;
  for (const c of t) if (/\p{L}/u.test(c)) letters++;
  return letters >= 0.4 * t.length;
}

const norm = (s: string) => s.trim().replace(/\s+/g, ' ');

/** A string with its numbers swapped for {0}, {1} ... : "updated 12:20:12" and "updated 12:20:13" are one sentence, asked
 *  for once; the numbers go back in when the translation is written to the page. A number glued to a letter (9m, pg2600)
 *  is a name, not a number, and stays where it is. */
const NUM = /(?<![\p{L}\d_])\d+(?:[.,:/\-]\d+)*(?![\p{L}\d_])/gu;
export function templatise(s: string): [string, string[]] {
  const nums: string[] = [];
  const t = s.replace(NUM, (m) => `{${nums.push(m) - 1}}`);
  return [t, nums];
}

export async function fetchLanguage(): Promise<LanguageState> {
  const r = await fetch('/api/language');
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as LanguageState;
}

/** Put the site into a language (the Liberty Machine records the choice) and tell every listener. */
export async function chooseLanguage(code: string): Promise<LanguageState> {
  const r = await fetch('/api/language', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ code, by: 'Justin' }) });
  const body = await r.json();
  if (!r.ok) throw new Error(body?.error || `${r.status}`);
  try { localStorage.setItem(KEEP_LANG, code); } catch { /* blocked */ }
  window.dispatchEvent(new CustomEvent(LANGUAGE_EVENT, { detail: body }));
  return body as LanguageState;
}

type Applied = { src: string; tr: string };

export class SiteTranslator {
  private code = 'en';
  private rtl = false;
  private lang: Language | null = null; // its names, for a box's prompt
  private glossary: string[] = []; // the names a translation keeps as written (thorp/translate.py GLOSSARY)
  private memo = new Map<string, string>();
  private text = new Map<Text, Applied>();
  private attr = new Map<Element, Map<string, Applied>>();
  private failed = new Set<string>();
  private observer: MutationObserver | null = null;
  private timer = 0;
  private running = false;
  private again = false;
  private blocked: string | null = null;
  private progress: Progress = { code: 'en', state: 'idle', done: 0, total: 0 };

  start(): void {
    this.observer = new MutationObserver(() => this.soon());
    this.observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
  }

  stop(): void {
    this.observer?.disconnect();
    this.observer = null;
    window.clearTimeout(this.timer);
  }

  /** The names a translation keeps as written, from the site's server. */
  setGlossary(names: string[] | undefined): void { if (names?.length) this.glossary = names; }

  /** The language to show now. English restores the page; another starts translating it. */
  set(code: string, rtl = false, lang?: Language): void {
    if (lang) this.lang = lang;
    if (code === this.code && !this.blocked) { this.soon(); return; }
    this.code = code;
    this.rtl = rtl;
    this.blocked = null;
    this.failed.clear();
    this.memo = this.load(code);
    document.documentElement.lang = code;
    document.documentElement.dir = rtl && code !== 'en' ? 'rtl' : 'ltr';
    if (code === 'en') this.restore();
    this.say({ code, state: 'idle', done: 0, total: 0 });
    this.soon();
  }

  retry(): void {
    this.blocked = null;
    this.failed.clear();
    this.soon();
  }

  private say(p: Progress): void {
    this.progress = p;
    window.dispatchEvent(new CustomEvent(PROGRESS_EVENT, { detail: p }));
  }

  private load(code: string): Map<string, string> {
    try {
      const raw = localStorage.getItem(`thorp.tr.${code}`);
      if (raw) return new Map(Object.entries(JSON.parse(raw) as Record<string, string>));
    } catch { /* blocked or broken */ }
    return new Map();
  }

  private save(): void {
    try {
      const entries = [...this.memo.entries()].slice(-3000);
      localStorage.setItem(`thorp.tr.${this.code}`, JSON.stringify(Object.fromEntries(entries)));
    } catch { /* full or blocked: the server still has them */ }
  }

  /** English back on the page: each node still showing what was written over it is given its own words again (a node
   *  React has since changed is already English and is left). */
  private restore(): void {
    for (const [node, a] of this.text) if (node.isConnected && node.data === a.tr) node.data = a.src;
    for (const [el, m] of this.attr) for (const [name, a] of m) if (el.isConnected && el.getAttribute(name) === a.tr) el.setAttribute(name, a.src);
    this.text.clear();
    this.attr.clear();
  }

  private soon(): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.pass(), 150);
  }

  /** Every translatable thing on the page not already in the chosen language, by its English: how to write the answer
   *  back to each place, and how far the nearest of them is from the screen (the ones in view are asked for first). */
  private scan(): Map<string, { writes: Array<(tr: string) => void>; dist: number }> {
    const found = new Map<string, { writes: Array<(tr: string) => void>; dist: number }>();
    if (this.code === 'en') return found;
    const add = (src: string, at: Element | null, put: (tr: string) => void) => {
      const [k, nums] = templatise(norm(src));
      if (!worthTranslating(k)) return;
      const write = (tr: string) => put(nums.length ? tr.replace(/\{(\d+)\}/g, (_, i) => nums[+i] ?? '') : tr);
      const have = this.memo.get(k);
      if (have !== undefined) { write(have); return; }
      if (this.failed.has(k)) return;
      let top = 0;
      if (at) {
        const r = at.getBoundingClientRect();
        top = r.bottom < 0 ? -r.bottom : r.top > window.innerHeight ? r.top - window.innerHeight : 0;
      }
      const got = found.get(k);
      if (got) { got.writes.push(write); got.dist = Math.min(got.dist, top); } else found.set(k, { writes: [write], dist: top });
    };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement && !n.parentElement.closest(SKIP) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    for (let n = walker.nextNode() as Text | null; n; n = walker.nextNode() as Text | null) {
      const node = n;
      const had = this.text.get(node);
      if (had && node.data === had.tr) continue; // ours already
      const src = node.data;
      add(src, node.parentElement, (tr) => {
        if (!node.isConnected) return;
        const lead = src.match(/^\s*/)![0];
        const tail = src.match(/\s*$/)![0];
        const out = lead + tr + tail;
        this.text.set(node, { src, tr: out });
        if (node.data !== out) node.data = out;
      });
    }
    for (const el of document.body.querySelectorAll<HTMLElement>(ATTRS.map((a) => `[${a}]`).join(','))) {
      // an input's own placeholder is wanted; only what it sits inside can rule it out
      if (el.closest(NO_ATTRS)) continue;
      for (const name of ATTRS) {
        const v = el.getAttribute(name);
        if (!v) continue;
        const had = this.attr.get(el)?.get(name);
        if (had && v === had.tr) continue;
        add(v, el, (tr) => {
          if (!el.isConnected) return;
          (this.attr.get(el) ?? this.attr.set(el, new Map()).get(el)!).set(name, { src: v, tr });
          if (el.getAttribute(name) !== tr) el.setAttribute(name, tr);
        });
      }
    }
    return found;
  }

  private async pass(): Promise<void> {
    if (this.code === 'en' || this.blocked) return; // blocked: the pill says why, and "try again" is the way on
    if (this.running) { this.again = true; return; }
    this.running = true;
    const code = this.code;
    try {
      do {
        this.again = false;
        const todo = this.scan(); // writes everything already known as it finds it
        if (!todo.size || this.blocked) break;
        const ordered = [...todo.keys()].sort((a, b) => todo.get(a)!.dist - todo.get(b)!.dist);
        let done = 0;
        this.say({ code, state: 'working', done, total: ordered.length });
        for (let i = 0; i < ordered.length && code === this.code; i += CHUNK) {
          const chunk = ordered.slice(i, i + CHUNK);
          // the visitor's box, when they connected one in Settings; else the site's server
          const box = loadTranslator();
          let body: { translations?: Record<string, string>; missed?: string[]; error?: string };
          if (box) {
            const lang = this.lang?.code === code ? this.lang : { code, name: code, native_name: code };
            body = await translateOnBox(box, lang, chunk, this.glossary);
          } else {
            const r = await fetch('/api/translate', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ code, texts: chunk }) });
            body = await r.json().catch(() => ({}));
            if (code !== this.code) return; // the language changed while this was away: its answer is for the old one
            if (!r.ok) {
              this.blocked = String(body?.error || `${r.status} ${r.statusText}`);
              this.say({ code, state: 'blocked', done, total: ordered.length, why: this.blocked });
              return;
            }
          }
          if (code !== this.code) return;
          for (const [src, tr] of Object.entries(body.translations || {})) this.memo.set(src, tr);
          for (const m of body.missed || []) this.failed.add(m);
          done += chunk.length;
          this.scan(); // writes the new ones, and anything React has put on the page since
          this.save();
          this.say({ code, state: 'working', done, total: ordered.length });
        }
      } while (this.again && code === this.code);
    } catch (e) {
      if (code !== this.code) return;
      this.blocked = String((e as Error)?.message ?? e);
      this.say({ code, state: 'blocked', done: 0, total: 0, why: this.blocked });
      return;
    } finally {
      this.running = false;
    }
    if (code === this.code && !this.blocked) this.say({ code, state: 'idle', done: this.progress.total, total: this.progress.total });
  }
}
