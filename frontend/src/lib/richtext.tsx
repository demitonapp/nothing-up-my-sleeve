// The chat's answer, formatted (11 November, Justin: "can you add formatting"): a small model emits the
// tags it was trained on — gemma-3-270m answers a question with `<h1><strong>Current Situation</strong></h1>`
// — and those tags were reaching the page as text.
//
// This is a whitelist renderer, never `dangerouslySetInnerHTML`: the answer is the model's own text, and a
// model trained on the web can write a `<script>` as easily as a heading. Only the tags below are built,
// every attribute is dropped (no `onerror`, no `href`, no `style`), an unknown tag loses its tag and keeps
// its words, and everything else stays text. Markdown that other chats' models write — `# heading`,
// `**bold**`, `code` — is folded in before the tags are read, so one renderer serves both.
//
// The answer is read as blocks (12 November): a blank line is a paragraph, a run of `- ` lines is a list,
// and a heading is a heading. Everything used to be laid out as one run of inline spans, so a model that
// wrote four paragraphs had them arrive as one wall of text at whatever width the window happened to be.

import { Fragment, type ReactNode } from 'react';

const HEADINGS: Record<string, number> = { h1: 1, h2: 2, h3: 3, h4: 4 };
const BLOCK = new Set(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li', 'br']);
const ALLOWED = new Set([
  ...BLOCK,
  'strong', 'b', 'em', 'i', 'code', 'span', 'div',
]);
// a block that already carries block-level structure is not wrapped in a <p> again
const BLOCKISH = /<(?:h[1-4]|p|div|ul|ol|pre|blockquote|li)\b/i;

type El = { tag: string; kids: Node[] };
type Node = string | El;

/** `- item` and `* item` runs become one list, numbered lines an ordered one; folded first, so a bullet
 *  is never read as *italic*. */
function foldLists(src: string): string {
  const out: string[] = [];
  let items: string[] = [];
  let kind: 'ul' | 'ol' | null = null;
  const flush = (): void => {
    if (items.length && kind) out.push(`<${kind}>${items.join('')}</${kind}>`);
    items = [];
    kind = null;
  };
  for (const line of src.split('\n')) {
    const ul = /^\s*[-*]\s+(.*)$/.exec(line);
    const ol = ul ? null : /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const nextKind = ul ? 'ul' : ol ? 'ol' : null;
    if (nextKind) {
      if (kind && kind !== nextKind) flush();
      kind = nextKind;
      items.push(`<li>${(ul || ol)![1]}</li>`);
    } else {
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
    else if (m[4] !== undefined) out.push(<code className="rt-code" key={`${key}.c${n++}`}>{m[4]}</code>);
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
    return <div key={key} className="rt-h" data-l={level}>{kids}</div>;
  }
  switch (el.tag) {
    case 'strong': return <strong key={key}>{kids}</strong>;
    case 'b': return <b key={key}>{kids}</b>;
    case 'em': return <em key={key}>{kids}</em>;
    case 'i': return <i key={key}>{kids}</i>;
    case 'code': return <code className="rt-code" key={key}>{kids}</code>;
    case 'pre': return <pre className="rt-pre" key={key}>{kids}</pre>;
    case 'br': return <br key={key} />;
    case 'p': case 'div': case 'span': return <span key={key}>{kids}</span>;
    case 'blockquote': return <blockquote className="rt-bq" key={key}>{kids}</blockquote>;
    case 'ul': return <ul className="rt-list" key={key}>{kids}</ul>;
    case 'ol': return <ol className="rt-list" key={key}>{kids}</ol>;
    case 'li': return <li key={key}>{kids}</li>;
    default: return <span key={key}>{kids}</span>;
  }
}

/** The answer as the page shows it: the whitelist's tags built, everything else left as words. */
export default function RichText({ text }: { text: string }) {
  const src = (text || '').replace(/\r\n?/g, '\n').trim();
  if (!src) return null;
  // a blank line is the model's own paragraph break: keep it as one on the page
  const blocks = src.split(/\n[ \t]*\n\s*/);
  return (
    <>
      {blocks.map((block, i) => {
        const raw = block.trim();
        if (!raw) return null;
        const folded = foldMarkdown(raw);
        const key = `r${i}`;
        const nodes = renderNodes(tokenize(folded), key);
        return BLOCKISH.test(folded)
          ? <Fragment key={key}>{nodes}</Fragment>
          : <p className="rt-p" key={key}>{nodes}</p>;
      })}
    </>
  );
}
