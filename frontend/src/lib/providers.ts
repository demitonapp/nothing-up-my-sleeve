// Where the chat console's model lives (13 November, Justin: "the chat terminal would need to be able to be
// linked to their local models somehow … world class, so needs support for both local and cloud models and to
// plug them in as easy as possible").
//
// A connection is one of three kinds:
//   local  — a model server on the visitor's own machine (Ollama, LM Studio, llama.cpp, an MLX server, vLLM,
//            Jan), found by asking each one's usual port from this browser;
//   cloud  — a provider the visitor holds a key for (Anthropic, OpenAI, Google, OpenRouter, or any
//            OpenAI-compatible endpoint by base URL);
//   server — Thorp's own models, run by `thorp dash` on its Mac through MLX (the private edition only).
//
// Local and cloud are spoken to straight from this browser, never through Thorp's server, over two wires:
// OpenAI-compatible chat completions (everyone but Anthropic) and Anthropic Messages. Both stream. A key is
// kept in this browser (localStorage when "remember" is ticked, sessionStorage otherwise) and is sent only to
// the provider it belongs to, in the request's own headers. Nothing here writes a key to Thorp's server.

export type Where = 'local' | 'cloud' | 'server';
export type Wire = 'openai' | 'anthropic' | 'thorp';

export interface Connection {
  provider: string; // 'ollama', 'lmstudio', 'llamacpp', 'vllm', 'jan', 'local', 'anthropic', 'openai', 'google', 'openrouter', 'custom', 'thorp'
  label: string; // the provider as the console names it: "Ollama", "Anthropic"
  where: Where;
  wire: Wire;
  base: string; // the API's base: `http://localhost:11434/v1`, `https://api.anthropic.com/v1`
  model: string; // the model's id as the provider takes it
  modelLabel?: string;
  context?: number | null; // the model's window, where the provider says it
  keyed?: boolean; // a key is needed (and kept in this browser)
}

export interface ModelInfo { id: string; label?: string; context?: number | null; note?: string; created?: number }

// ---------------------------------------------------------------- the edition

/** The public edition (lib/edition.ts): no Thorp server models to offer, and nothing of a chat sent to Thorp's server. */
export { PUBLIC_EDITION } from './edition';

/** Thorp's own models, run by `thorp dash` through MLX: chosen within by the console's lab and model lists. */
export const SERVER_CONNECTION: Connection = { provider: 'thorp', label: 'Thorp', where: 'server', wire: 'thorp', base: '/api/chat', model: '' };

// ---------------------------------------------------------------- what this browser keeps

const CONN = 'thorp.chat.connection.v1';
const RECENT = 'thorp.chat.connections.v1';
const KEYS = 'thorp.chat.keys.v1';

const readJson = <T,>(store: Storage | undefined, slot: string, fallback: T): T => {
  try {
    const v = JSON.parse(store?.getItem(slot) || 'null');
    return v == null ? fallback : (v as T);
  } catch {
    return fallback;
  }
};
const local = (): Storage | undefined => { try { return window.localStorage; } catch { return undefined; } };
const session = (): Storage | undefined => { try { return window.sessionStorage; } catch { return undefined; } };

/** The key a connection's thread is filed under in the conversation store. */
export const connKey = (c: Pick<Connection, 'provider' | 'model'>): string => `conn:${c.provider}:${c.model}`;

/** undefined: this browser has never chosen; null: it chose and then disconnected. */
export function loadConnection(): Connection | null | undefined {
  let raw: string | null = null;
  try { raw = local()?.getItem(CONN) ?? null; } catch { /* blocked */ }
  if (raw == null) return undefined;
  const v = readJson<Connection | null>(local(), CONN, null);
  return v && typeof v.provider === 'string' ? v : null;
}
export function saveConnection(c: Connection | null): void {
  try { local()?.setItem(CONN, JSON.stringify(c)); } catch { /* blocked */ }
  if (c) rememberRecent(c);
}
export function recentConnections(): Connection[] {
  const v = readJson<Connection[]>(local(), RECENT, []);
  return Array.isArray(v) ? v.filter((c) => c && typeof c.provider === 'string' && typeof c.model === 'string') : [];
}
function rememberRecent(c: Connection): void {
  if (c.wire === 'thorp') return;
  const rest = recentConnections().filter((x) => connKey(x) !== connKey(c));
  try { local()?.setItem(RECENT, JSON.stringify([c, ...rest].slice(0, 8))); } catch { /* blocked */ }
}
export function forgetRecent(c: Connection): void {
  try { local()?.setItem(RECENT, JSON.stringify(recentConnections().filter((x) => connKey(x) !== connKey(c)))); } catch { /* blocked */ }
}

// keys are filed by provider and base, so two OpenAI-compatible endpoints keep two keys
const keySlot = (provider: string, base: string): string => `${provider}|${base.replace(/\/+$/, '')}`;
export function getKey(provider: string, base: string): string {
  const k = keySlot(provider, base);
  return readJson<Record<string, string>>(session(), KEYS, {})[k] || readJson<Record<string, string>>(local(), KEYS, {})[k] || '';
}
export function keyRemembered(provider: string, base: string): boolean {
  return !!readJson<Record<string, string>>(local(), KEYS, {})[keySlot(provider, base)];
}
export function setKey(provider: string, base: string, key: string, remember: boolean): void {
  const k = keySlot(provider, base);
  for (const [store, keep] of [[local(), remember], [session(), !remember]] as const) {
    if (!store) continue;
    const all = readJson<Record<string, string>>(store, KEYS, {});
    if (keep && key) all[k] = key;
    else delete all[k];
    try { store.setItem(KEYS, JSON.stringify(all)); } catch { /* blocked */ }
  }
}
export function forgetKey(provider: string, base: string): void { setKey(provider, base, '', false); setKey(provider, base, '', true); }

// ---------------------------------------------------------------- local servers

export interface LocalServer {
  id: string;
  label: string;
  port: number;
  native?: 'ollama'; // asked by its own API (/api/tags), chatted with over its /v1
  start: string; // how to start it
  install: string; // where to get it
  pull?: string; // the command that fetches a first model
  cors: (origin: string) => { line: string; then?: string }; // the one setting that lets this page in
}

export const LOCAL_SERVERS: LocalServer[] = [
  {
    id: 'ollama', label: 'Ollama', port: 11434, native: 'ollama',
    start: 'ollama serve', install: 'https://ollama.com/download', pull: 'ollama pull qwen3:4b',
    cors: (origin) => ({
      line: `launchctl setenv OLLAMA_ORIGINS "${origin}"`,
      then: `then quit and reopen the Ollama app. On Linux or in a terminal: OLLAMA_ORIGINS="${origin}" ollama serve; on Windows: setx OLLAMA_ORIGINS "${origin}" and restart Ollama.`,
    }),
  },
  {
    id: 'lmstudio', label: 'LM Studio', port: 1234,
    start: 'lms server start', install: 'https://lmstudio.ai', pull: 'lms get qwen3-4b',
    cors: () => ({ line: 'lms server start --cors', then: 'or, in LM Studio: Developer → Server settings → Enable CORS.' }),
  },
  {
    id: 'llamacpp', label: 'llama.cpp or MLX server', port: 8080,
    start: 'llama-server -hf ggml-org/Qwen3-4B-GGUF   (or: mlx_lm.server --model mlx-community/Qwen3-4B-4bit)',
    install: 'https://github.com/ggml-org/llama.cpp',
    cors: () => ({ line: 'llama-server answers any origin by default', then: 'if a proxy sits in front of it, have the proxy send Access-Control-Allow-Origin.' }),
  },
  {
    id: 'vllm', label: 'vLLM', port: 8000,
    start: 'vllm serve Qwen/Qwen3-4B', install: 'https://docs.vllm.ai',
    cors: (origin) => ({ line: `vllm serve <model> --allowed-origins '["${origin}"]'` }),
  },
  {
    id: 'jan', label: 'Jan', port: 1337,
    start: 'open Jan → Settings → Local API Server → Start', install: 'https://jan.ai',
    cors: (origin) => ({ line: `Jan → Settings → Local API Server → CORS: on, trusted hosts: ${new URL(origin).host}` }),
  },
];

export type ProbeState = 'checking' | 'found' | 'empty' | 'cors' | 'down';
export interface Probe { server: LocalServer; base: string; state: ProbeState; models: ModelInfo[]; detail?: string; label?: string }

const withTimeout = async (url: string, init: RequestInit = {}, ms = 2500): Promise<Response> => {
  const ctl = new AbortController();
  const t = window.setTimeout(() => ctl.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: ctl.signal });
  } finally {
    window.clearTimeout(t);
  }
};

/** A fetch that failed: was the server down, or up and refusing this page (CORS)? An opaque no-cors request
 *  resolves whenever something answers on the port, so it tells the two apart. */
async function corsOrDown(url: string): Promise<'cors' | 'down'> {
  try {
    await withTimeout(url, { mode: 'no-cors' }, 2000);
    return 'cors';
  } catch {
    return 'down';
  }
}

const notChat = /(embed|bge-|minilm|rerank|whisper|tts|clip)/i;

// a server that lists a whole model cache (mlx_lm.server does) would offer base checkpoints first: the models
// that answer go to the top, the ones that only continue prose to the bottom (the order is otherwise kept)
const baseCheckpoint = /(\bbase\b|-base|-pt\b|-pt-|pythia|phi-2$|gemma-2-2b$|flux|dflash)/i;
const answerFirst = (models: ModelInfo[]): ModelInfo[] =>
  [...models].sort((a, b) => Number(baseCheckpoint.test(a.id)) - Number(baseCheckpoint.test(b.id)));

/** Ask one local server what it serves. `base` is its origin, e.g. http://localhost:11434. */
export async function probeLocal(server: LocalServer, origin?: string): Promise<Probe> {
  const base = (origin || `http://localhost:${server.port}`).replace(/\/+$/, '');
  const url = server.native === 'ollama' ? `${base}/api/tags` : `${base}/v1/models`;
  try {
    const r = await withTimeout(url);
    if (!r.ok) return { server, base, state: 'down', models: [], detail: `answered ${r.status} at ${url}` };
    const d = await r.json();
    let models: ModelInfo[];
    let label: string | undefined;
    if (server.native === 'ollama') {
      models = (d.models || [])
        .filter((m: { name?: string; details?: { family?: string } }) => m.name && !notChat.test(m.name) && !/bert/i.test(m.details?.family || ''))
        .map((m: { name: string; size?: number; details?: { parameter_size?: string; quantization_level?: string } }) => ({
          id: m.name,
          note: [m.details?.parameter_size, m.details?.quantization_level, m.size ? `${(m.size / 1e9).toFixed(1)} GB` : ''].filter(Boolean).join(' · '),
        }));
    } else {
      const rows = (d.data || d.models || []) as { id?: string; owned_by?: string; meta?: { n_ctx_train?: number } }[];
      models = rows.filter((m) => m.id && !notChat.test(m.id)).map((m) => ({ id: String(m.id), context: m.meta?.n_ctx_train ?? null, note: m.owned_by && m.owned_by !== 'organization_owner' ? m.owned_by : '' }));
      const owner = rows.find((m) => m.owned_by)?.owned_by || '';
      if (server.id === 'llamacpp') label = /llama/i.test(owner) ? 'llama.cpp server' : rows.some((m) => /mlx/i.test(String(m.id))) ? 'MLX server' : 'OpenAI-compatible server';
    }
    return { server, base, state: models.length ? 'found' : 'empty', models: answerFirst(models), label };
  } catch {
    return { server, base, state: await corsOrDown(url), models: [] };
  }
}

/** A server at an address the visitor typed: Ollama's API is tried first, then the OpenAI-compatible one. */
export async function probeAddress(address: string): Promise<Probe> {
  let base = address.trim();
  if (!/^https?:\/\//i.test(base)) base = `http://${base}`;
  base = base.replace(/\/+$/, '').replace(/\/v1$/, '');
  const port = Number(new URL(base).port) || 80;
  const known = LOCAL_SERVERS.find((s) => s.port === port);
  const asOllama = await probeLocal({ ...(known || LOCAL_SERVERS[0]), native: 'ollama', label: known?.label || 'Ollama' }, base);
  if (asOllama.state === 'found' || asOllama.state === 'empty') return asOllama;
  const generic: LocalServer = known && !known.native ? known : {
    id: 'local', label: 'OpenAI-compatible server', port, start: '', install: '',
    cors: () => ({ line: 'have the server send Access-Control-Allow-Origin for this page' }),
  };
  const asOpenAi = await probeLocal(generic, base);
  return asOpenAi.state === 'down' && asOllama.state === 'cors' ? asOllama : asOpenAi;
}

export function localConnection(p: Probe, m: ModelInfo): Connection {
  return {
    provider: p.server.id, label: p.label || p.server.label, where: 'local', wire: 'openai',
    base: `${p.base}/v1`, model: m.id, modelLabel: m.label || m.id, context: m.context ?? null,
  };
}

/** Chrome's Local Network Access permission (2025 on): a page served from elsewhere may reach localhost only once
 *  the visitor allows it, and while it is denied every request fails as if nothing were running, the no-cors
 *  one too. 'unknown' where the browser has no such permission (Safari, Firefox) or the page is itself local. */
export async function localNetworkAccess(): Promise<'granted' | 'denied' | 'prompt' | 'unknown'> {
  if (pageIsLocal() || typeof navigator === 'undefined' || !navigator.permissions) return 'unknown';
  for (const name of ['local-network-access', 'loopback-network']) {
    try {
      const p = await navigator.permissions.query({ name } as unknown as PermissionDescriptor);
      return p.state as 'granted' | 'denied' | 'prompt';
    } catch { /* this browser does not know the name */ }
  }
  return 'unknown';
}

/** The page's own origin, for the CORS line; and whether this page is itself on this machine. */
export const pageOrigin = (): string => (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:4321');
export const pageIsLocal = (): boolean => /^(localhost|127\.0\.0\.1|\[::1\]|.+\.localhost)$/.test(typeof window !== 'undefined' ? window.location.hostname : 'localhost');

// ---------------------------------------------------------------- cloud providers

export interface CloudProvider {
  id: string;
  label: string;
  wire: 'openai' | 'anthropic';
  base: string;
  keyUrl?: string;
  keyHint: string;
  blurb: string;
  keyOptional?: boolean;
}

export const CLOUD_PROVIDERS: CloudProvider[] = [
  { id: 'anthropic', label: 'Anthropic', wire: 'anthropic', base: 'https://api.anthropic.com/v1', keyUrl: 'https://console.anthropic.com/settings/keys', keyHint: 'sk-ant-…', blurb: 'Claude' },
  { id: 'openai', label: 'OpenAI', wire: 'openai', base: 'https://api.openai.com/v1', keyUrl: 'https://platform.openai.com/api-keys', keyHint: 'sk-…', blurb: 'GPT and the o-series' },
  { id: 'google', label: 'Google', wire: 'openai', base: 'https://generativelanguage.googleapis.com/v1beta/openai', keyUrl: 'https://aistudio.google.com/apikey', keyHint: 'AIza…', blurb: 'Gemini, with a free tier' },
  { id: 'openrouter', label: 'OpenRouter', wire: 'openai', base: 'https://openrouter.ai/api/v1', keyUrl: 'https://openrouter.ai/keys', keyHint: 'sk-or-…', blurb: 'one key, hundreds of models' },
  { id: 'custom', label: 'Other', wire: 'openai', base: '', keyHint: 'if it needs one', blurb: 'any OpenAI-compatible endpoint', keyOptional: true },
];

/** The provider a pasted key belongs to, by its prefix, so a key pasted under the wrong name still lands. */
export function providerOfKey(key: string): string | null {
  const k = key.trim();
  if (/^sk-ant-/.test(k)) return 'anthropic';
  if (/^sk-or-/.test(k)) return 'openrouter';
  if (/^AIza[0-9A-Za-z_-]{20,}$/.test(k)) return 'google';
  if (/^sk-(proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}$/.test(k)) return 'openai';
  return null;
}

const errorText = async (r: Response): Promise<string> => {
  const raw = await r.text().catch(() => '');
  try {
    const d = JSON.parse(raw);
    const e = Array.isArray(d) ? d[0]?.error : d.error;
    return String(e?.message || e || d.message || raw).slice(0, 300);
  } catch {
    return raw.slice(0, 300);
  }
};

const headersFor = (wire: Wire, provider: string, key: string): Record<string, string> => {
  if (wire === 'anthropic') {
    return {
      'x-api-key': key, 'anthropic-version': '2023-06-01',
      // Anthropic answers a browser only when it is told the key is the visitor's own, in their own browser
      'anthropic-dangerous-direct-browser-access': 'true',
    };
  }
  const h: Record<string, string> = key ? { authorization: `Bearer ${key}` } : {};
  if (provider === 'openrouter') { h['http-referer'] = pageOrigin(); h['x-title'] = 'Thorp'; }
  return h;
};

const host = (url: string): string => { try { return new URL(url).host; } catch { return url; } };

/** One cheap call that proves the key, then the models it reaches. Throws a sentence a visitor can act on. */
export async function checkKey(p: CloudProvider, key: string, base?: string): Promise<ModelInfo[]> {
  const root = (base || p.base).replace(/\/+$/, '');
  if (!root) throw new Error('give the endpoint’s base URL, e.g. https://api.groq.com/openai/v1');
  const h = headersFor(p.wire, p.id, key.trim());
  let r: Response;
  try {
    if (p.id === 'openrouter') {
      // OpenRouter lists its models to anyone, so the key is proved by asking about the key itself
      r = await fetch(`${root}/key`, { headers: h });
      if (r.ok) r = await fetch(`${root}/models`, { headers: h });
    } else {
      r = await fetch(`${root}/models${p.wire === 'anthropic' ? '?limit=1000' : ''}`, { headers: h });
    }
  } catch {
    throw new Error(`could not reach ${host(root)} from this browser: check the address, your connection, or whether it allows browser requests (CORS)`);
  }
  if (!r.ok) {
    const msg = await errorText(r);
    // Google answers a bad key with a 400, the rest with 401 or 403
    if (r.status === 401 || r.status === 403 || (r.status === 400 && /api[ _-]?key/i.test(msg))) throw new Error(`${p.label} refused this key (${r.status}): ${msg}`);
    throw new Error(`${p.label} answered ${r.status}: ${msg}`);
  }
  const d = await r.json();
  return modelsOf(p.id, d);
}

function modelsOf(provider: string, d: any): ModelInfo[] {
  const rows: any[] = d.data || d.models || [];
  if (provider === 'anthropic') {
    return rows.map((m) => ({ id: m.id, label: m.display_name || m.id, created: Date.parse(m.created_at) || 0, context: m.max_input_tokens ?? null }));
  }
  if (provider === 'openrouter') {
    return rows
      .filter((m) => !/(embed|image|audio)/i.test(m.architecture?.modality?.split('->')[1] || ''))
      .map((m) => {
        const inP = Number(m.pricing?.prompt) * 1e6;
        const outP = Number(m.pricing?.completion) * 1e6;
        const price = Number.isFinite(inP) ? (inP === 0 && outP === 0 ? 'free' : `$${inP.toFixed(2)} / $${outP.toFixed(2)} per M`) : '';
        return { id: m.id, label: m.name || m.id, context: m.context_length ?? null, created: (m.created || 0) * 1000, note: price };
      })
      .sort((a, b) => (b.created || 0) - (a.created || 0));
  }
  if (provider === 'google') {
    return rows
      .map((m) => ({ id: String(m.id).replace(/^models\//, ''), label: m.display_name, context: m.input_token_limit ?? null }))
      .filter((m) => /gemini|gemma/i.test(m.id) && !/(embedding|imagen|image|tts|aqa|live|native-audio|veo)/i.test(m.id))
      .sort((a, b) => b.id.localeCompare(a.id, undefined, { numeric: true }));
  }
  if (provider === 'openai') {
    return rows
      .filter((m) => /^(gpt-|o\d|chatgpt)/i.test(m.id) && !/(audio|realtime|tts|transcribe|image|search|embedding|instruct|moderation|dall-e|whisper|codex)/i.test(m.id))
      .map((m) => ({ id: m.id, created: (m.created || 0) * 1000 }))
      .sort((a, b) => (b.created || 0) - (a.created || 0));
  }
  return answerFirst(rows.filter((m) => m.id && !notChat.test(m.id)).map((m) => ({ id: String(m.id), context: m.context_length ?? m.max_model_len ?? null })));
}

export function cloudConnection(p: CloudProvider, m: ModelInfo, base?: string): Connection {
  const root = (base || p.base).replace(/\/+$/, '');
  return {
    provider: p.id, label: p.id === 'custom' ? host(root) : p.label, where: 'cloud', wire: p.wire, base: root,
    model: m.id, modelLabel: m.label || m.id, context: m.context ?? null, keyed: true,
  };
}

/** Is a connection still answering? For a local one, the server; for a cloud one, only that a key is held. */
export async function stillThere(c: Connection): Promise<{ ok: boolean; why?: string }> {
  if (c.wire === 'thorp') return { ok: true };
  if (c.where === 'cloud') return getKey(c.provider, c.base) || c.provider === 'custom' ? { ok: true } : { ok: false, why: `no ${c.label} key in this browser: paste it again` };
  try {
    const r = await withTimeout(`${c.base}/models`, {}, 2500);
    return r.ok ? { ok: true } : { ok: false, why: `${c.label} answered ${r.status}` };
  } catch {
    return { ok: false, why: `${c.label} is not answering at ${host(c.base)}: is it running?` };
  }
}

// ---------------------------------------------------------------- the chat itself

export interface Turn { role: 'user' | 'assistant'; content: string }
export interface ChatOptions { maxTokens: number; temperature?: number; signal?: AbortSignal }
export interface ChatDelta { kind: 'text' | 'reasoning'; text: string }
export interface ChatResult {
  answer: string;
  reasoning: string;
  finish: string;
  promptTokens?: number;
  answerTokens?: number;
  reasoningTokens?: number;
  cachedTokens?: number;
}

/** Read a server-sent-events body a `data:` line at a time. */
async function* sse(r: Response): AsyncGenerator<any> {
  const reader = r.body!.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    for (let nl = buf.indexOf('\n'); nl >= 0; nl = buf.indexOf('\n')) {
      const line = buf.slice(0, nl).replace(/\r$/, '');
      buf = buf.slice(nl + 1);
      if (!line.startsWith('data:')) continue; // event names, comments (OpenRouter's ": PROCESSING"), blanks
      const data = line.slice(5).trim();
      if (!data || data === '[DONE]') continue;
      try { yield JSON.parse(data); } catch { /* a partial or foreign line */ }
    }
  }
}

/** Some local servers write a reasoning model's thinking into the answer between <think> tags. */
function thinkSplitter(emit: (d: ChatDelta) => void): (text: string) => void {
  let mode: 'start' | 'think' | 'text' = 'start';
  let held = '';
  return (text: string) => {
    if (mode === 'text') { emit({ kind: 'text', text }); return; }
    held += text;
    if (mode === 'start') {
      const t = held.trimStart();
      if (!t) return;
      if ('<think>'.startsWith(t) && t.length < 7) return; // could still be the tag
      if (t.startsWith('<think>')) { mode = 'think'; held = t.slice(7); } else { mode = 'text'; emit({ kind: 'text', text: held }); held = ''; return; }
    }
    const end = held.indexOf('</think>');
    if (end >= 0) {
      if (end) emit({ kind: 'reasoning', text: held.slice(0, end) });
      const rest = held.slice(end + 8).replace(/^\s+/, '');
      mode = 'text';
      held = '';
      if (rest) emit({ kind: 'text', text: rest });
    } else if (held.length > 8) {
      emit({ kind: 'reasoning', text: held.slice(0, -8) });
      held = held.slice(-8);
    }
  };
}

/** Chat with any connection from this browser, streaming. Throws on a refusal; resolves with the whole answer. */
export async function chatStream(c: Connection, turns: Turn[], opt: ChatOptions, onDelta: (d: ChatDelta) => void): Promise<ChatResult> {
  const key = c.keyed || c.where === 'cloud' ? getKey(c.provider, c.base) : '';
  if (c.where === 'cloud' && !key && c.provider !== 'custom') throw new Error(`no ${c.label} key in this browser: connect again and paste it`);
  return c.wire === 'anthropic' ? anthropicStream(c, key, turns, opt, onDelta) : openaiStream(c, key, turns, opt, onDelta);
}

async function post(c: Connection, url: string, headers: Record<string, string>, body: unknown, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body), signal });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new Error(c.where === 'local'
      ? `${c.label} did not answer at ${host(url)}: is it still running? (if it is, this page may be blocked by its CORS setting: switch model to see the fix)`
      : `could not reach ${host(url)} from this browser`);
  }
}

async function openaiStream(c: Connection, key: string, turns: Turn[], opt: ChatOptions, onDelta: (d: ChatDelta) => void): Promise<ChatResult> {
  const url = `${c.base}/chat/completions`;
  const headers = headersFor('openai', c.provider, key);
  // OpenAI's newer models take max_completion_tokens and only their own temperature; everyone else max_tokens
  const body: Record<string, unknown> = { model: c.model, messages: turns, stream: true, stream_options: { include_usage: true } };
  if (c.provider === 'openai') body.max_completion_tokens = opt.maxTokens;
  else { body.max_tokens = opt.maxTokens; if (opt.temperature != null) body.temperature = opt.temperature; }
  let r = await post(c, url, headers, body, opt.signal);
  if (r.status === 400 || r.status === 422) {
    // a server that will not take an optional field: ask again with the plainest request
    const first = await errorText(r);
    const plain: Record<string, unknown> = { model: c.model, messages: turns, stream: true };
    if (c.provider === 'openai') plain.max_completion_tokens = opt.maxTokens; else plain.max_tokens = opt.maxTokens;
    r = await post(c, url, headers, plain, opt.signal);
    if (!r.ok) throw new Error(`${c.label} answered ${r.status}: ${(await errorText(r)) || first}`);
  }
  if (r.status === 401 || r.status === 403) throw new Error(`${c.label} refused the key (${r.status}): ${await errorText(r)}`);
  if (!r.ok || !r.body) throw new Error(`${c.label} answered ${r.status}: ${await errorText(r)}`);
  const out: ChatResult = { answer: '', reasoning: '', finish: '' };
  // a server that reports no usage is counted a streamed piece a token, which local servers send
  let pieces = 0;
  let thoughts = 0;
  const emit = (d: ChatDelta): void => {
    if (d.kind === 'reasoning') out.reasoning += d.text; else out.answer += d.text;
    onDelta(d);
  };
  const content = thinkSplitter(emit);
  for await (const ev of sse(r)) {
    if (ev.error) throw new Error(`${c.label}: ${ev.error.message || JSON.stringify(ev.error)}`);
    const ch = ev.choices?.[0];
    const d = ch?.delta || {};
    const think = d.reasoning_content ?? d.reasoning ?? d.thinking;
    if (typeof think === 'string' && think) { thoughts += 1; emit({ kind: 'reasoning', text: think }); }
    if (typeof d.content === 'string' && d.content) { pieces += 1; content(d.content); }
    if (ch?.finish_reason) out.finish = ch.finish_reason;
    if (ev.usage) {
      out.promptTokens = ev.usage.prompt_tokens;
      out.answerTokens = ev.usage.completion_tokens;
      out.reasoningTokens = ev.usage.completion_tokens_details?.reasoning_tokens || undefined;
      out.cachedTokens = ev.usage.prompt_tokens_details?.cached_tokens || undefined;
    }
  }
  content(''); // flush a held fragment
  if (out.answerTokens == null && pieces + thoughts) {
    out.answerTokens = pieces + thoughts;
    if (thoughts) out.reasoningTokens = thoughts;
  }
  return out;
}

async function anthropicStream(c: Connection, key: string, turns: Turn[], opt: ChatOptions, onDelta: (d: ChatDelta) => void): Promise<ChatResult> {
  const r = await post(c, `${c.base}/messages`, headersFor('anthropic', c.provider, key), {
    model: c.model, max_tokens: opt.maxTokens, stream: true,
    messages: turns.map((t) => ({ role: t.role, content: t.content })),
  }, opt.signal);
  if (r.status === 401 || r.status === 403) throw new Error(`${c.label} refused the key (${r.status}): ${await errorText(r)}`);
  if (!r.ok || !r.body) throw new Error(`${c.label} answered ${r.status}: ${await errorText(r)}`);
  const out: ChatResult = { answer: '', reasoning: '', finish: '' };
  for await (const ev of sse(r)) {
    if (ev.type === 'message_start') {
      const u = ev.message?.usage || {};
      out.promptTokens = (u.input_tokens || 0) + (u.cache_read_input_tokens || 0) + (u.cache_creation_input_tokens || 0);
      out.cachedTokens = u.cache_read_input_tokens || undefined;
    } else if (ev.type === 'content_block_delta') {
      if (ev.delta?.type === 'text_delta') { out.answer += ev.delta.text; onDelta({ kind: 'text', text: ev.delta.text }); }
      else if (ev.delta?.type === 'thinking_delta') { out.reasoning += ev.delta.thinking; onDelta({ kind: 'reasoning', text: ev.delta.thinking }); }
    } else if (ev.type === 'message_delta') {
      if (ev.usage?.output_tokens != null) out.answerTokens = ev.usage.output_tokens;
      if (ev.delta?.stop_reason) out.finish = ev.delta.stop_reason === 'max_tokens' ? 'length' : ev.delta.stop_reason;
    } else if (ev.type === 'error') {
      throw new Error(`${c.label}: ${ev.error?.message || 'the stream failed'}`);
    }
  }
  return out;
}
