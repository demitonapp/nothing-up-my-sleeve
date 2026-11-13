// The models that run this site's own interface (13 November, Justin: "a section on what models we use to run the UI. So
// language model for translation, the 8B Ling model for chat, reasoning and tools ... and then allow someone to connect them
// to their box running locally"; then: "needs to show in each place where no model is configured, then the configuration
// should be in settings but to read about those models should be in the models section with those models highlighted with
// why we chose them and what they do in the app"; translation and chat both may run on the visitor's box).
//
// Two jobs, one model each. What they are, why they were chosen and how to run them is said once, here: the Models
// section (/orbitals/masaq/models#ui-models) reads it, Settings reads it, and every place with no model says it.
//
// The chat's own connection is the console's (lib/providers.ts). The translator's is kept here: a model on the visitor's
// box that the page asks straight from this browser, as the chat does, instead of this site's server. Nothing about it
// is sent to the site's server.

import { chatStream, type Connection } from './providers';

export type UiRole = 'chat' | 'translation';

export interface UiModel {
  key: string;
  role: UiRole;
  name: string;
  maker: string;
  size: string;
  licence: string;
  page: string; // the model's card
  gguf: string; // the maker's own GGUF build, for a box
  ollama: string; // the one line that pulls it into Ollama
  does: string; // what it does in the app
  why: string; // why we chose it
  caveat?: string; // what to know before running it
  match: RegExp; // a model on a box that is this one, by its id
}

export const UI_MODELS: UiModel[] = [
  {
    key: 'ling-3-0-tiny',
    role: 'chat',
    name: 'Ling 3.0 Tiny',
    maker: 'InclusionAI',
    size: '7.9B parameters, 1.3B active (a mixture of experts)',
    licence: 'MIT',
    page: 'https://huggingface.co/inclusionAI/Ling-3.0-tiny',
    gguf: 'https://huggingface.co/inclusionAI/Ling-3.0-tiny-GGUF',
    ollama: 'ollama pull hf.co/inclusionAI/Ling-3.0-tiny-GGUF:Q4_K_M',
    does: 'Answers in the chat terminal: it reasons before it replies, and calls the site’s tools to read the fleet, the queue, the Liberty Machine and the leaderboard rather than guess at them.',
    why: 'It reasons and calls tools, and only 1.3B of its 7.9B parameters work on each word, so it answers quickly on a laptop. When we tried it on the site’s own questions (the fleet, the Liberty Machine, the next charter, Kipling) it chose the right tool every time, and its makers’ published scores stand beside the other medium models on our leaderboard.',
    caveat: 'Its architecture is new: it needs a recent llama.cpp, LM Studio or Ollama. If yours will not load it, update it, or use any model that calls tools.',
    match: /ling/i,
  },
  {
    key: 'tiny-aya-earth',
    role: 'translation',
    name: 'Tiny Aya Earth',
    maker: 'Cohere Labs',
    size: '3.35B parameters',
    licence: 'CC-BY-NC 4.0 (non-commercial)',
    page: 'https://huggingface.co/CohereLabs/tiny-aya-earth',
    gguf: 'https://huggingface.co/CohereLabs/tiny-aya-earth-GGUF',
    ollama: 'ollama pull hf.co/CohereLabs/tiny-aya-earth-GGUF:Q4_K_M',
    does: 'Puts the whole site into the language you choose, a sentence at a time, as it reaches the screen. The English stays the record underneath; choosing English puts every word back.',
    why: 'It is small enough to run beside everything else, it names 67 languages on its card, and the Earth variant is the one Cohere tuned for African and West Asian languages, where the big models are weakest. It is told to keep the site’s names and numbers as written.',
    caveat: 'Cohere gates its weights: accept the licence on the model’s page with your Hugging Face account before pulling it.',
    match: /aya/i,
  },
];

export const uiModel = (role: UiRole): UiModel => UI_MODELS.find((m) => m.role === role)!;
export const MODELS_SECTION = '/orbitals/masaq/models#ui-models';

// ---------------------------------------------------------------- the translator on the visitor's box

const TRANSLATOR = 'thorp.translate.connection.v1';
export const TRANSLATOR_EVENT = 'thorp:translator-connection';

export function loadTranslator(): Connection | null {
  try {
    const v = JSON.parse(window.localStorage.getItem(TRANSLATOR) || 'null');
    return v && typeof v.provider === 'string' && typeof v.model === 'string' ? (v as Connection) : null;
  } catch {
    return null;
  }
}

export function saveTranslator(c: Connection | null): void {
  try {
    if (c) window.localStorage.setItem(TRANSLATOR, JSON.stringify(c));
    else window.localStorage.removeItem(TRANSLATOR);
  } catch { /* blocked: it lasts this page only */ }
  window.dispatchEvent(new CustomEvent(TRANSLATOR_EVENT, { detail: c }));
}

/** Open the chat terminal on its connect page (the console listens: ChatConsole's `thorp:chat`). */
export const openChatConnect = (): void => { window.dispatchEvent(new CustomEvent('thorp:chat', { detail: { connect: true } })); };

// The prompt and the tidying are thorp/translate.py's (`prompt`, `tidy`, `faithful`), kept in step with it by hand, so a
// sentence translated on a box reads as one translated on the site's server.

export interface TargetLanguage { code: string; name: string; native_name: string }

const PLACEHOLDER = /\{\d+\}/g;
const placeholders = (s: string): string[] => (s.match(PLACEHOLDER) || []).sort();

function prompt(lang: TargetLanguage, source: string, glossary: string[], insist = false): string {
  const name = lang.native_name === lang.name ? lang.name : `${lang.name} (${lang.native_name})`;
  const label = source.split(/\s+/).length <= 3 && !/[.!?]$/.test(source.trim());
  const names = glossary.filter((g) => source.includes(g));
  const ph = placeholders(source);
  return (
    `Translate the text below from English into ${name}. `
    + 'It is from the dashboard of a research project that trains small language models; it uses sailing words '
    + '(ship, keel, voyage, fleet, fitout, charter, harbour) in their ordinary sense. '
    + (label ? 'It is a short label on a button, tab or heading: translate it as a label (a noun or a short phrase, not an instruction). ' : '')
    + (names.length ? `Keep these names exactly as written: ${names.join(', ')}. ` : '')
    + (ph.length ? 'Keep every placeholder such as {0} exactly as written, once each. ' : '')
    + (insist ? `These must appear in your answer exactly as written: ${[...names, ...ph].map((n) => `'${n}'`).join(', ')}. ` : '')
    + 'Keep numbers, code, file names, URLs and punctuation as they are. '
    + 'Reply with the translation only: no notes, no quotation marks, no explanation.\n\n'
    + source
  );
}

function tidy(source: string, out: string): string | null {
  let got = (out || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim();
  if (!source.includes('**')) got = got.replace(/\*\*/g, '');
  for (const mark of ['<|END_OF_TURN_TOKEN|>', '<|CHATBOT_TOKEN|>', '<|END_RESPONSE|>', '<|START_RESPONSE|>']) got = got.split(mark).join('');
  got = got.trim();
  if (got.length >= 2 && '"“«'.includes(got[0]) && '"”»'.includes(got[got.length - 1]) && !'"“«'.includes(source[0] || '')) got = got.slice(1, -1).trim();
  if (!got || got.length > 6 * source.length + 60) return null;
  const letters = /[\p{L}]/u;
  if (letters.test(source.replace(PLACEHOLDER, '')) && !letters.test(got.replace(PLACEHOLDER, ''))) return null;
  return got;
}

const faithful = (source: string, out: string, glossary: string[]): boolean =>
  glossary.filter((g) => source.includes(g)).every((n) => out.includes(n)) && placeholders(out).join() === placeholders(source).join();

const budget = (source: string): number => Math.max(48, Math.min(768, source.length + 32));

/** Translate English strings on the visitor's box, each asked alone (one cannot leak into the next), two at a time.
 *  The same shape /api/translate answers: what it could, and what it could not. A box that does not answer throws. */
export async function translateOnBox(c: Connection, lang: TargetLanguage, sources: string[], glossary: string[]): Promise<{ translations: Record<string, string>; missed: string[] }> {
  const translations: Record<string, string> = {};
  const missed: string[] = [];
  const one = async (source: string): Promise<void> => {
    for (const insist of [false, true]) {
      const r = await chatStream(c, [{ role: 'user', content: prompt(lang, source, glossary, insist) }], { maxTokens: budget(source), temperature: 0 }, () => {});
      const got = tidy(source, r.answer);
      if (got && faithful(source, got, glossary)) { translations[source] = got; return; }
    }
    missed.push(source);
  };
  const queue = [...sources];
  await Promise.all([0, 1].map(async () => { for (let s = queue.shift(); s !== undefined; s = queue.shift()) await one(s); }));
  return { translations, missed };
}
