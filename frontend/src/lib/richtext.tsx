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
const TABLE = new Set(['table', 'thead', 'tbody', 'tr', 'th', 'td']);
const BLOCK = new Set(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li', 'br', 'hr', ...TABLE]);
const ALLOWED = new Set([
  ...BLOCK,
  'strong', 'b', 'em', 'i', 'code', 'span', 'div',
]);
const VOID = new Set(['br', 'hr']);
// a block that already carries block-level structure is not wrapped in a <p> again
const BLOCKISH = /<(?:h[1-4]|p|div|ul|ol|pre|blockquote|li|hr|table)\b/i;

type El = { tag: string; kids: Node[] };
type Node = string | El;

// a table's separator row: `|---|:---:|---|`, the pipes at the ends optional, at least one dash a cell
const TABLE_RULE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$|^\s*\|\s*:?-+:?\s*\|\s*$/;
const isRow = (line: string): boolean => /^\s*\|.*\|\s*$/.test(line) || (line.includes('|') && line.trim().split('|').length > 2);
const cells = (line: string): string[] => {
  let s = line.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|') && !s.endsWith('\\|')) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
};

/** GitHub tables (12 November, Justin: "can you fix the markdown table rendering"): a header row, a
 *  separator of dashes, then body rows, folded into the whitelist's own table tags. A model's table arrived
 *  as rows of pipes. Alignment colons are read and dropped (no attribute survives the whitelist); a row
 *  shorter than the header is padded, a longer one keeps its extra cells. */
function foldTables(src: string): string {
  const lines = src.split('\n');
  const out: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (isRow(lines[i]) && i + 1 < lines.length && TABLE_RULE.test(lines[i + 1])) {
      const head = cells(lines[i]);
      const body: string[][] = [];
      let j = i + 2;
      while (j < lines.length && isRow(lines[j]) && !TABLE_RULE.test(lines[j])) body.push(cells(lines[j++]));
      const row = (cs: string[], tag: 'th' | 'td'): string => {
        const padded = cs.length < head.length ? [...cs, ...Array(head.length - cs.length).fill('')] : cs;
        return `<tr>${padded.map((c) => `<${tag}>${c}</${tag}>`).join('')}</tr>`;
      };
      out.push(`<table><thead>${row(head, 'th')}</thead><tbody>${body.map((r) => row(r, 'td')).join('')}</tbody></table>`);
      i = j - 1;
      continue;
    }
    out.push(lines[i]);
  }
  return out.join('\n');
}

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
  // tables first, so a row's pipes are never read as anything else; then a `---` line is a rule, before the
  // lists, so it is never read as a bullet
  return foldLists(foldTables(src).replace(/^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$/gm, '<hr>'))
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
    if (VOID.has(tag) || /\/>$/.test(m[0])) {
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

/** How much a node says, in characters: what tells a cell of prose from a cell holding a number or a name. */
const textLen = (n: Node): number => (typeof n === 'string' ? n.trim().length : n.kids.reduce((a, k) => a + textLen(k), 0));
// a cell this long is a sentence, and keeps a readable measure however many columns stand beside it
const LONG_CELL = 40;

function renderEl(el: El, key: string): ReactNode {
  // a list's whitespace between items is layout, not content: it must not become a <br>
  // (and a table's whitespace between rows and cells, which React would warn about inside <tr>)
  const inList = el.tag === 'ul' || el.tag === 'ol' || el.tag === 'li' || (TABLE.has(el.tag) && el.tag !== 'th' && el.tag !== 'td');
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
    case 'hr': return <hr className="rt-hr" key={key} />;
    // A table is as wide as what it holds (12 November, Justin: "the markdown table needs to size
    // dynamically"): each column takes its content, a word is never split, a cell of prose is marked so
    // it keeps a readable width, and only a table too wide for the room scrolls, inside its own frame.
    case 'table': return <div className="rt-tablewrap" key={key}><table className="rt-table">{kids}</table></div>;
    case 'thead': return <thead key={key}>{kids}</thead>;
    case 'tbody': return <tbody key={key}>{kids}</tbody>;
    case 'tr': return <tr key={key}>{kids}</tr>;
    case 'th': return <th key={key}>{kids}</th>;
    case 'td': return <td key={key} data-long={textLen(el) > LONG_CELL ? '' : undefined}>{kids}</td>;
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
