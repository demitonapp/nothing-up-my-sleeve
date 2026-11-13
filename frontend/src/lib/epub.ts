// Reading an epub in the browser (13 November, Justin: the latest epub is something a visitor "can download,
// email to their kindle or read"). The book page reads the very file it offers for download, so the copy read
// and the copy downloaded cannot differ, and nothing is unpacked at build time.
//
// An epub is a zip. This reads the zip's directory, inflates an entry when it is asked for (the browser's own
// DecompressionStream; no library), and knows the two things about an epub the reader needs: the order of its
// pages (the nav document) and how to turn a page's pictures into addresses the browser can show.
// No DOM is touched here except DOMParser, so the island owns everything that is drawn.

interface Entry { method: number; size: number; start: number; }

export interface EpubPage { href: string; title: string; }

export interface Epub {
  pages: EpubPage[];
  /** One page's body as nodes ready to be put in the document: pictures point at blob addresses. */
  page(href: string): Promise<DocumentFragment>;
  /** Free the picture addresses made so far. */
  close(): void;
}

const u16 = (v: DataView, o: number): number => v.getUint16(o, true);
const u32 = (v: DataView, o: number): number => v.getUint32(o, true);

/** The zip's central directory: every entry's name, how it is packed and where its bytes start. */
function directory(buf: ArrayBuffer): Map<string, Entry> {
  const v = new DataView(buf);
  let end = buf.byteLength - 22;
  while (end >= 0 && u32(v, end) !== 0x06054b50) end--;
  if (end < 0) throw new Error('not a zip: no end-of-directory record');
  const count = u16(v, end + 10);
  let at = u32(v, end + 16);
  const names = new TextDecoder();
  const out = new Map<string, Entry>();
  for (let i = 0; i < count; i++) {
    if (u32(v, at) !== 0x02014b50) throw new Error('not a zip: bad directory entry');
    const method = u16(v, at + 10), size = u32(v, at + 20);
    const nameLen = u16(v, at + 28), extraLen = u16(v, at + 30), commentLen = u16(v, at + 32);
    const local = u32(v, at + 42);
    const name = names.decode(new Uint8Array(buf, at + 46, nameLen));
    // the bytes sit after the entry's own local header, whose name and extra lengths may differ from the directory's
    const start = local + 30 + u16(v, local + 26) + u16(v, local + 28);
    out.set(name, { method, size, start });
    at += 46 + nameLen + extraLen + commentLen;
  }
  return out;
}

async function bytesOf(buf: ArrayBuffer, e: Entry): Promise<Uint8Array<ArrayBuffer>> {
  const packed = new Uint8Array(buf, e.start, e.size);
  if (e.method === 0) return packed;
  if (e.method !== 8) throw new Error(`zip entry packed with method ${e.method}, which this reader does not read`);
  if (typeof DecompressionStream === 'undefined') throw new Error('this browser cannot unpack the book here; download it instead');
  const stream = new Blob([packed]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

const MIME: Record<string, string> = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', svg: 'image/svg+xml', webp: 'image/webp' };

/** Open an epub from its address. Throws with a sentence a visitor can read if it cannot be opened. */
export async function openEpub(url: string): Promise<Epub> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`the book could not be fetched (${res.status})`);
  const buf = await res.arrayBuffer();
  const dir = directory(buf);
  const text = async (name: string): Promise<string> => {
    const e = dir.get(name);
    if (!e) throw new Error(`the book has no ${name}`);
    return new TextDecoder().decode(await bytesOf(buf, e));
  };
  // every page of this book lives in OEBPS, beside its pictures folder (build_epub.py)
  const ROOT = 'OEBPS/';
  const parse = (xml: string): Document => new DOMParser().parseFromString(xml, 'application/xhtml+xml');
  const nav = parse(await text(ROOT + 'nav.xhtml'));
  const pages: EpubPage[] = [...nav.querySelectorAll('nav ol > li > a')]
    .map((a) => ({ href: a.getAttribute('href') || '', title: (a.textContent || '').trim() }))
    .filter((p) => /^c\d+\.xhtml$/.test(p.href));
  const made: string[] = [];
  const pictures = new Map<string, string>();
  const picture = async (src: string): Promise<string> => {
    const name = ROOT + src.replace(/^\.\//, '');
    const had = pictures.get(name);
    if (had) return had;
    const e = dir.get(name);
    if (!e) return '';
    const ext = (name.split('.').pop() || '').toLowerCase();
    const address = URL.createObjectURL(new Blob([await bytesOf(buf, e)], { type: MIME[ext] || 'application/octet-stream' }));
    made.push(address);
    pictures.set(name, address);
    return address;
  };
  return {
    pages,
    async page(href: string): Promise<DocumentFragment> {
      const doc = parse(await text(ROOT + href));
      const body = doc.querySelector('body');
      if (!body || doc.querySelector('parsererror')) throw new Error('this page of the book could not be read');
      for (const img of [...body.querySelectorAll('img')]) {
        const address = await picture(img.getAttribute('src') || '');
        if (address) img.setAttribute('src', address); else img.remove();
      }
      const out = document.createDocumentFragment();
      for (const node of [...body.childNodes]) out.appendChild(document.importNode(node, true));
      return out;
    },
    close(): void { for (const a of made) URL.revokeObjectURL(a); made.length = 0; pictures.clear(); },
  };
}
