// The chat's answer, formatted (11 November, Justin: "can you add formatting"): a small model emits the
// tags it was trained on — gemma-3-270m answers a question with `<h1><strong>Current Situation</strong></h1>`
// — and those tags were reaching the page as text.
//
// This is a whitelist renderer, never `dangerouslySetInnerHTML`: the answer is the model's own text, and a
// model trained on the web can write a `<script>` as easily as a heading. Only the tags below are built,
// every attribute is dropped (no `onerror`, no `href`, no `style`), an unknown tag loses its tag and keeps
// its words, and everything else stays text. Markdown that other chats' models write — `# heading`,
// `**bold**`, `code` — is folded in before the tags are read, so one renderer serves both.

import type { ReactNode } from 'react';

const HEADINGS: Record<string, number> = { h1: 1, h2: 2, h3: 3, h4: 4 };
const BLOCK = new Set(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li', 'br']);
const ALLOWED = new Set([
  ...BLOCK,
  'strong', 'b', 'em', 'i', 'code', 'span', 'div',
]);

type El = { tag: string; kids: Node[] };
type Node = string | El;

/** Markdown a model writes instead of tags, folded into the same whitelist before it is read. */
/** `- item` and `* item` runs become one list; folded first, so a bullet is never read as *italic*. */
function foldLists(src: string): string {
  const out: string[] = [];
  let items: string[] = [];
  const flush = (): void => {
    if (items.length) out.push(`<ul>${items.join('')}</ul>`);
    items = [];
  };
  for (const line of src.split('\n')) {
    const item = /^\s*[-*]\s+(.*)$/.exec(line);
    if (item) items.push(`<li>${item[1]}</li>`);
    else {
      flush();
      out.push(line);
    }
  }
  flush();
  return out.join('\n');
}

function foldMarkdown(src: string): string {
  return foldLists(src)
    .replace(/^[ \t]*#{1,4}[ \t]+(.+?)[ \t]*$/gm, (_, t: string) => `<h4>${t}</h4>`)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>');
}

/** The whitelist tree: tags outside it are dropped and their text kept; attributes never survive. */
function tokenize(src: string): Node[] {
  const root: El = { tag: '#root', kids: [] };
  const stack: El[] = [root];
  const push = (t: string): void => {
    if (t) stack[stack.length - 1].kids.push(t);
  };
  const re = /<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) {
    push(src.slice(last, m.index));
    last = re.lastIndex;
    const tag = m[1].toLowerCase();
    if (!ALLOWED.has(tag)) continue; // the tag goes, its words stay
    if (m[0].startsWith('</')) {
      const at = stack.map((e) => e.tag).lastIndexOf(tag);
      if (at > 0) stack.length = at; // close the nearest matching open, and anything inside it
      continue;
    }
    if (tag === 'br' || /\/>$/.test(m[0])) {
      stack[stack.length - 1].kids.push({ tag, kids: [] });
      continue;
    }
    const el: El = { tag, kids: [] };
    stack[stack.length - 1].kids.push(el);
    stack.push(el);
  }
  push(src.slice(last));
  return root.kids;
}

/** Inline markdown that survives the tree walk: **bold**, *italic*, `code`, and the line breaks. */
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*([^*]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let n = 0;
  const plain = (s: string): void => {
    const parts = s.split(/\n+/); // a run of newlines is one break, never a stack of them
    parts.forEach((p, i) => {
      if (i) out.push(<br key={`${key}.b${n++}`} />);
      if (p) out.push(p);
    });
  };
  while ((m = re.exec(text))) {
    plain(text.slice(last, m.index));
    last = re.lastIndex;
    if (m[2] !== undefined) out.push(<strong key={`${key}.s${n++}`}>{m[2]}</strong>);
    else if (m[3] !== undefined) out.push(<em key={`${key}.e${n++}`}>{m[3]}</em>);
    else if (m[4] !== undefined) out.push(<code className="mono" key={`${key}.c${n++}`}>{m[4]}</code>);
  }
  plain(text.slice(last));
  return out;
}

function renderNodes(nodes: Node[], key: string): ReactNode[] {
  return nodes.map((node, i) => {
    const k = `${key}.${i}`;
    if (typeof node === 'string') return <span key={k}>{inline(node, k)}</span>;
    return renderEl(node, k);
  });
}

function renderEl(el: El, key: string): ReactNode {
  // a list's whitespace between items is layout, not content: it must not become a <br>
  const inList = el.tag === 'ul' || el.tag === 'ol' || el.tag === 'li';
  const kids = renderNodes(
    inList ? el.kids.filter((k) => typeof k !== 'string' || k.trim() !== '') : el.kids,
    key,
  );
  const level = HEADINGS[el.tag];
  if (level) {
    // never a real <h1>: the page has one, and a chat bubble is not the document's structure
    return (
      <div key={key} style={{ fontWeight: 600, fontSize: level === 1 ? '1.05em' : '1em', margin: '8px 0 4px' }}>
        {kids}
      </div>
    );
  }
  switch (el.tag) {
    case 'strong': return <strong key={key}>{kids}</strong>;
    case 'b': return <b key={key}>{kids}</b>;
    case 'em': return <em key={key}>{kids}</em>;
    case 'i': return <i key={key}>{kids}</i>;
    case 'code': return <code className="mono" key={key}>{kids}</code>;
    case 'pre': return <pre key={key} style={{ margin: '6px 0', whiteSpace: 'pre-wrap' }}>{kids}</pre>;
    case 'br': return <br key={key} />;
    case 'p': case 'div': case 'span': return <span key={key}>{kids}</span>;
    case 'blockquote': return <blockquote key={key} style={{ margin: '6px 0', paddingLeft: 10, borderLeft: '2px solid var(--line)' }}>{kids}</blockquote>;
    case 'ul': return <ul key={key} style={{ margin: '6px 0', paddingLeft: 18 }}>{kids}</ul>;
    case 'ol': return <ol key={key} style={{ margin: '6px 0', paddingLeft: 18 }}>{kids}</ol>;
    case 'li': return <li key={key}>{kids}</li>;
    default: return <span key={key}>{kids}</span>;
  }
}

/** The answer as the page shows it: the whitelist's tags built, everything else left as words. */
export default function RichText({ text }: { text: string }) {
  return <>{renderNodes(tokenize(foldMarkdown(text || '')), 'r')}</>;
}
