// The Library (UI.md "Shelves"), as a typed client island: the library's branches and faceted
// browser, then every list of books Nothing up my sleeve reads, keeps or drafts, with the detail drawer and the
// reader. Converted from dashboard.ts (loadShelves / drawShelves / drawShelfDetail / loadBrowse /
// drawBrowse / drawSelection).

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import BranchConfig, { type ConfigChoices, type SavedConfig } from './BranchConfig';
import { TabNav } from '../TabNav';
import { big, periodOf } from '@/lib/format';
import { libraryBranchHref, libraryBranchOf } from '@/lib/nav';
import { cardCls, emptyCls, fieldCls, pillCls, selectCls } from '@/lib/ui';
import { familyBar } from '@/scripts/views/helpers';
import { selCounts, selDeclared } from '@/scripts/views/fitouts';
import { sectionProps, useApi } from '@/lib/useApi';
import HeldOut from '../HeldOut';

/** Open a book in the reader. The import is deferred: `lib/reader.ts` wires the reader's DOM at
 *  module load, which would touch `document` during Astro's server render. */
const openInReader = async (id: string): Promise<void> => {
  const { openBook } = await import('@/lib/reader');
  await openBook(id);
};

/** A left click follows the branch without a page load (the address still changes); a modified click
 *  keeps the browser's own behaviour, so a branch can be opened in a new tab. */
const plainClick = (e: ReactMouseEvent<HTMLAnchorElement>, run: () => void): void => {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
  e.preventDefault();
  run();
};

type Dim = 'kind' | 'language' | 'voice' | 'source' | 'period' | 'collection';

interface Variation {
  key: string;
  name: string;
  about?: string;
  draft?: boolean;
  derived_from?: string | null;
  kind?: string;
  spec?: unknown;
  list?: string;
  fitouts?: string[];
  sizes?: string[];
  books: number[];
}
interface Branch {
  key: string;
  name: string;
  purpose: string;
  variations: Variation[];
  sizes?: string[];
  attributes?: string[];
  default_choices?: ConfigChoices;
  configurations?: SavedConfig[];
}
interface Size { preset: string; name: string }
interface Collection { path: string; name: string; kind: string; about?: string; books: number }
interface BrowseData {
  branches: Branch[];
  branches_stored: boolean;
  sizes: Size[];
  books: Book[];
  fields: string[];
  collections: Collection[];
  kinds: Record<string, string>;
  voices: Record<string, string>;
  year: Record<string, unknown>;
  fingerprint: string;
  selection_keys: string[];
}
// [id, title, author, language, source, kind, voice, year, year_basis, ogden, words, collections, kind_rule, voice_rule]
type Book = [string, string, string, string, string, string, string, number | null, string, number | null, number, number[], string, string];
interface ShelfUse { run: string; role: string; status?: string }
interface Shelf {
  name: string; path: string; kind: string; about?: string; books: number; rows: number;
  tokens_est: number; families: Record<string, number> | null; runs: number; queued: number; uses: ShelfUse[];
}
interface LibraryData { shelves: Shelf[] | null; computing?: boolean; error?: string | null }

interface KnownBook { book_id?: string; title: string; author: string; family?: string }

const SHELF_KINDS: [string, string, string][] = [
  ['training', 'Training libraries', 'what the ships read'],
  ['deck', 'Decks', 'the books the ships are scored on, never read'],
  ['probe', 'Probes', 'small lists the instruments read'],
  ['other', 'Other', 'lists kept for a purpose of their own'],
  ['draft', 'Drafts', 'lists being drawn up, not yet used'],
];
const BDIMS: [Dim, string, string][] = [
  ['kind', 'Kind', 'what the book is: the first rule that matches (hover for the rule)'],
  ['period', 'Date', "the writer's year: published, else birth + 40, else death - 25 (hover a card)"],
  ['language', 'Language', 'the language of the text'],
  ['collection', 'Collection', 'the named shelves and decks a book belongs to; a book may be in several'],
  ['voice', 'Voice', 'who speaks: read from the credit, so the Church is undercounted'],
  ['source', 'Source', 'the collection the text was fetched from'],
];

const blankFilters = () => ({
  kind: new Set<string>(), language: new Set<string>(), voice: new Set<string>(),
  source: new Set<string>(), period: new Set<string>(), collection: new Set<string>(),
  start: '', end: '', ogden: '', sort: 'words' as 'words' | 'year' | 'title' | 'ogden', more: 200,
});
type Filters = ReturnType<typeof blankFilters>;

const cut = (s: string | null | undefined, n = 160): string => {
  const v = String(s ?? '');
  return v.length > n ? v.slice(0, n - 1) + '…' : v;
};
const bSum = (bs: Book[]) => ({ n: bs.length, w: bs.reduce((a, b) => a + b[10], 0) });
const bVals = (b: Book, dim: Dim, br: BrowseData): string[] =>
  dim === 'kind' ? [b[5]] : dim === 'language' ? [b[3]] : dim === 'voice' ? [b[6]] : dim === 'source' ? [b[4]]
    : dim === 'period' ? [periodOf(b[7])] : b[11].length ? b[11].map((i) => br.collections[i].name) : [];

function bPass(b: Book, f: Filters, br: BrowseData, skip?: Dim): boolean {
  for (const dim of ['kind', 'language', 'voice', 'source', 'period', 'collection'] as Dim[]) {
    if (dim === skip || !f[dim].size) continue;
    if (!bVals(b, dim, br).some((v) => f[dim].has(v))) return false;
  }
  if (skip !== 'period') {
    const s = f.start === '' ? null : +f.start;
    const e = f.end === '' ? null : +f.end;
    if (s != null || e != null) {
      if (b[7] == null || (s != null && b[7] < s) || (e != null && b[7] > e)) return false;
    }
  }
  if (f.ogden !== '' && !(b[9] != null && b[9] >= +f.ogden / 100)) return false;
  return true;
}

const FamilyBar = ({ fam }: { fam: Record<string, number> | null }) => (
  <span dangerouslySetInnerHTML={{ __html: familyBar(fam) }} />
);

export default function Library({ initialPath = '/library' }: { initialPath?: string }) {
  const browse = useApi<BrowseData>('/api/library_browse', 30000);
  const library = useApi<LibraryData>('/api/library', 5000);

  // One address a branch: /library is the branches' page, /library/<key> is a branch's own page.
  // The path is read after mount (the island is server-rendered too) and kept current through
  // pushState and the browser's back/forward.
  const [path, setPath] = useState(initialPath);
  useEffect(() => {
    const read = (): void => setPath(location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname);
    read();
    window.addEventListener('popstate', read);
    window.addEventListener('hashchange', read);
    return () => { window.removeEventListener('popstate', read); window.removeEventListener('hashchange', read); };
  }, []);
  const go = useCallback((next: string) => {
    history.pushState(null, '', next);
    setPath(next);
  }, []);
  // Two sections (12 November, Justin: "under library ... two sections books and then images which will
  // be where we start to collect images"): /library is Books, /library/images is Images. 'images' is
  // taken out of the branch addresses, so no branch can be called that.
  const imagesView = /^\/(?:library|shelves)\/images\/?$/.test(path.split(/[?#]/)[0]);
  // the third section (13 November): every held-out set, at /library/held-out; 'held-out' is no branch's address
  const heldView = /^\/(?:library|shelves)\/held-out\/?$/.test(path.split(/[?#]/)[0]);
  const branchKey = imagesView || heldView ? null : libraryBranchOf(path);

  return (
    <div {...sectionProps('shelves')}>
      <h1>Library <span className="q">{heldView
        ? 'everything a ship is scored on and never trains on: the held-out questions, the decks of books and the field’s own tests'
        : imagesView
        ? 'the images Nothing up my sleeve will read: where they come from, the rule they pass, and what is gathered so far'
        : 'every list of books Nothing up my sleeve reads from, is scored on or is drafting: how many books are fetched, about how many tokens they hold, their language families, and the voyages that read them'}</span></h1>
      <TabNav
        id="librarynav"
        ariaLabel="Library sections"
        items={[
          { key: 'books', label: 'Books', href: '/library', active: !imagesView && !heldView },
          { key: 'images', label: 'Images', href: '/library/images', active: imagesView },
          { key: 'held-out', label: 'Held out', href: '/library/held-out', active: heldView },
        ]}
      />
      {heldView ? <HeldOut /> : imagesView ? <Images /> : <Books browse={browse} library={library} branchKey={branchKey} go={go} />}
    </div>
  );
}

function Books({ browse, library, branchKey, go }: {
  browse: { data: BrowseData | null; error: string | null };
  library: { data: LibraryData | null; error: string | null };
  branchKey: string | null;
  go: (p: string) => void;
}) {
  return (
    <>
      <section className={cardCls(false, 'panel')} id="browsepanel">
        <h2>The library <span className="note">it starts with branches, each a purpose its books are gathered for (Ogden, the decks, the content experiment...). Open a branch to compose a JSON of choices and save it under a name; the lists it has already sailed stay beneath it, locked</span></h2>
        <div id="browse">
          {(() => {
            const b = browse.data as any;
            const ready = !!b && Array.isArray(b.branches) && Array.isArray(b.books) && Array.isArray(b.sizes) && Array.isArray(b.collections);
            const why = browse.error || (b && b.error);
            if (why) return <div className={emptyCls()}>the library could not be read: {why}</div>;
            if (!ready) return <div className={emptyCls()}>{b && b.computing ? 'reading the library (a few seconds)…' : 'reading the library…'}</div>;
            return <Browser br={b} branchKey={branchKey} go={go} />;
          })()}
        </div>
      </section>
      <Shelves data={library.data} error={library.error} />
    </>
  );
}

/** Where image sources stand. Nothing is gathered yet: this is the shelf the first intake will fill. */
const IMAGE_SOURCES: { name: string; what: string; rule: string; state: string }[] = [
  { name: 'Gutenberg illustrations', what: 'the plates and figures in the HTML editions of illustrated books', rule: 'English text, a credited illustrator, every named person dead by 1955, 200px a side', state: 'pilot' },
  { name: 'Internet Archive page scans', what: 'page images of the scanned books, the source of the scanned branch’s text', rule: 'the same period and death rule as the text; one image a page', state: 'not started' },
  { name: 'Wikimedia Commons', what: 'public-domain prints, maps, diagrams and photographs before 1930', rule: 'a dated, public-domain licence tag; the creator dead by 1955', state: 'not started' },
  { name: 'Library of Congress, British Library', what: 'digitised period prints, plates and periodicals', rule: 'marked no known restrictions, dated before 1930', state: 'not started' },
];

interface GatheredImage {
  id: string; book: number; title: string; illustrators: string[]; caption: string; alt: string;
  width: number; height: number; page: string; url: string;
}
interface ImagesData {
  images: number; books: number; bytes: number; rule: string;
  by_book: { book: number; title: string; illustrators: string[]; images: number }[];
  items: GatheredImage[];
}

function Images() {
  const { data, error } = useApi<ImagesData>('/api/images', 30000);
  const [book, setBook] = useState<number | null>(null);
  const items = (data?.items || []).filter((i) => book == null || i.book === book);
  const first = (t: string) => t.split('\n')[0];
  return (
    <>
      <section className={cardCls(false, 'panel')} id="imagespanel">
        <h2>Images <span className="note">the second shelf of the Library, where the images start to be collected</span></h2>
        <p className="foaim">
          Images come under the same rules as the books: every maker dead by 1955, held with where they came
          from and who made them. The first source is the illustrations in Gutenberg&rsquo;s HTML editions,
          gathered with <span className="mono">thorp images gather</span>. They are the start of a training shelf
          for a Nothing up my sleeve image model, and a multimodal embedder (see{' '}
          <a href="/orbitals/masaq/embeddings#emb-multimodal">the embeddings ontology</a>) can place them in the
          same space as the text.
        </p>
        {error ? (
          <div className={emptyCls()}>the images could not be read: {error} (restart <span className="mono">thorp dash</span> if this server predates them)</div>
        ) : !data ? (
          <div className={emptyCls()}>reading the images…</div>
        ) : !data.images ? (
          <div className={emptyCls()}>no images in the library yet: <span className="mono">thorp images gather --illustrator Doré</span></div>
        ) : (
          <>
            <div className="bsummary">
              <b>{data.images.toLocaleString()}</b> images from <b>{data.books}</b> books · {(data.bytes / 1e6).toFixed(1)} MB
              {book != null ? <button type="button" className="selchip bclear" onClick={() => setBook(null)}>every book ×</button> : null}
            </div>
            <div className="s">{data.rule}</div>
            <div className="bcards mt">
              {data.by_book.map((b) => (
                <button key={b.book} type="button" className={`bcard${book === b.book ? ' on' : ''}`} title={first(b.title)} onClick={() => setBook(book === b.book ? null : b.book)}>
                  <span className="bname">{cut(first(b.title), 40)}</span>
                  <span className="bnum">{b.images}<span className="s"> · {b.illustrators.join(', ')}</span></span>
                </button>
              ))}
            </div>
            <div className="imggrid mt">
              {items.map((i) => (
                <figure key={i.id} className="imgcard">
                  <a href={`/api/image?id=${i.id}`} target="_blank" rel="noreferrer">
                    <img src={`/api/image?id=${i.id}`} alt={i.alt || i.caption} loading="lazy" width={i.width} height={i.height} />
                  </a>
                  <figcaption>
                    {i.caption || i.alt ? <span>{cut(i.caption || i.alt, 120)}</span> : null}
                    <span className="s">{i.illustrators.join(', ')} · {cut(first(i.title), 40)} · {i.width}×{i.height}</span>
                  </figcaption>
                </figure>
              ))}
            </div>
          </>
        )}
      </section>
      <section className={cardCls(false, 'panel')}>
        <h2>Where they will come from <span className="note">the sources in mind, each with its rule; none has an intake yet</span></h2>
        <div className="scroll">
          <table className="shelftable">
            <thead><tr><th>source</th><th>what</th><th>rule</th><th>state</th></tr></thead>
            <tbody>
              {IMAGE_SOURCES.map((s) => (
                <tr key={s.name}>
                  <td><b>{s.name}</b></td>
                  <td>{s.what}</td>
                  <td className="s">{s.rule}</td>
                  <td><span className={pillCls('')}>{s.state}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Shelves({ data, error }: { data: LibraryData | null; error: string | null }) {
  const [kind, setKind] = useState('');
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const shelves = data?.shelves || null;
  const rows = (shelves || []).filter((x) => (!kind || x.kind === kind) && (!q || `${x.name} ${x.path} ${x.about || ''}`.toLowerCase().includes(q.toLowerCase())));
  const kinds = SHELF_KINDS.filter(([k]) => (shelves || []).some((x) => x.kind === k));
  const known = SHELF_KINDS.map((k) => k[0]);
  const groups: [string, string, string][] = [...SHELF_KINDS, ...[...new Set(rows.map((x) => x.kind))].filter((k) => !known.includes(k)).map((k) => [k, k, ''] as [string, string, string])];

  return (
    <>
      <div className="handtools" data-filters>
        <label className="note" htmlFor="shelfkind">show</label>
        <select className={selectCls('')} id="shelfkind" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">every kind</option>
          {kinds.map(([k, name]) => <option key={k} value={k}>{name.toLowerCase()}</option>)}
        </select>
        <input className={fieldCls('')} id="shelfsearch" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="find a library" aria-label="find a library" />
        <span className="note" id="shelfcount">{shelves ? `${rows.length} librar${rows.length === 1 ? 'y' : 'ies'}` : ''}</span>
      </div>
      <div id="shelfgroups">
        {error ? <div className={emptyCls()}>the libraries could not be read: {error}</div>
          : !shelves ? <div className={emptyCls()}>{data?.error ? `the libraries could not be read: ${data.error}` : 'reading the libraries (a few seconds)…'}</div>
          : rows.length === 0 ? <div className={emptyCls()}>no library matches</div>
          : groups.map(([k, title, note]) => {
            const g = rows.filter((x) => x.kind === k);
            if (!g.length) return null;
            const table = <ShelfTable shelves={g} open={open} onOpen={(p) => setOpen(open === p ? null : p)} />;
            const head = <>{title} <span className="note">{g.length} · {note}</span></>;
            return k === 'draft' && !q && kind !== 'draft'
              ? <section key={k} className={cardCls(false, 'panel')}><details open={g.some((x) => x.path === open)}><summary><h2>{head}</h2></summary>{table}</details></section>
              : <section key={k} className={cardCls(false, 'panel')}><h2>{head}</h2>{table}</section>;
          })}
      </div>
    </>
  );
}

function ShelfTable({ shelves, open, onOpen }: { shelves: Shelf[]; open: string | null; onOpen: (p: string) => void }) {
  return (
    <div className="scroll">
      <table className="shelftable clickable">
        <thead><tr><th>library</th><th>books</th><th>~tokens</th><th>families</th><th>read by</th></tr></thead>
        <tbody>
          {shelves.map((x) => (
            <ShelfRow key={x.path} x={x} open={open === x.path} onOpen={onOpen} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ShelfRow({ x, open, onOpen }: { x: Shelf; open: boolean; onOpen: (p: string) => void }) {
  return (
    <>
      <tr data-shelf={x.path} className={open ? 'open' : undefined} onClick={(e) => { if (!(e.target as HTMLElement).closest('a')) onOpen(x.path); }}>
        <td><b>{x.name}</b> <span className="mono s">{x.path}</span>{x.about ? <div className="s">{x.about}</div> : null}</td>
        <td data-sort={x.books}>{x.books}{x.books < x.rows ? <span className="s"> of {x.rows}</span> : null}</td>
        <td data-sort={x.tokens_est}>{big(x.tokens_est)}</td>
        <td><FamilyBar fam={x.families} /></td>
        <td data-sort={x.runs + x.queued}>
          {[x.runs ? `read by ${x.runs} run${x.runs === 1 ? '' : 's'}` : '', x.queued ? `${x.queued} queued` : ''].filter(Boolean).join(' · ') || <span className="s">no voyage yet</span>}
        </td>
      </tr>
      {open ? <tr className="shelfdetail"><td colSpan={5}><ShelfDetail x={x} /></td></tr> : null}
    </>
  );
}

function ShelfDetail({ x }: { x: Shelf }) {
  const cache = useRef(new Map<string, KnownBook[] | null>());
  const [books, setBooks] = useState<KnownBook[] | null | undefined>(cache.current.get(x.path));
  useEffect(() => {
    if (cache.current.has(x.path)) { setBooks(cache.current.get(x.path)); return; }
    let live = true;
    fetch('/api/library_books?path=' + encodeURIComponent(x.path))
      .then((r) => r.json())
      .then((d: KnownBook[]) => { cache.current.set(x.path, d); if (live) setBooks(d); })
      .catch(() => { cache.current.set(x.path, null); if (live) setBooks(null); });
    return () => { live = false; };
  }, [x.path]);

  const roleOrder = (r: string) => ['reads', 'reads first', 'tokeniser', 'scored on', 'refuses'].indexOf(r);
  const uses = [...x.uses].sort((a, b) => (a.status === 'queued' ? 1 : 0) - (b.status === 'queued' ? 1 : 0) || roleOrder(a.role) - roleOrder(b.role) || a.run.localeCompare(b.run));

  return (
    <>
      <div className="k">used by</div>
      {uses.length ? (
        <div className="shelfuses">
          {uses.map((u) => (
            <span key={u.run + u.role} className={`use${u.status === 'queued' ? ' queued' : ''}`}>
              {u.status === 'queued' ? u.run : <a href={`/ships/${encodeURIComponent(u.run)}`}>{u.run}</a>} <i>{u.role}</i>{u.status === 'queued' ? <i> queued</i> : null}
            </span>
          ))}
        </div>
      ) : <div className="s">no voyage reads it yet</div>}
      <div className="k mt">the books</div>
      {books === undefined ? <div id="shelfbooks" className="s">reading the list…</div>
        : books === null ? <div className="s">the list could not be read</div>
        : books.length === 0 ? <div className="s">the list is empty</div>
        : (
          <div className="shelfbooks">
            {books.map((b) => b.book_id ? (
              <button key={b.book_id} type="button" className={['bookbtn', 'outline'].join(' ')} data-book={b.book_id} title="open in the reader" onClick={() => { void openInReader(b.book_id!); }}>
                {b.title}<span>{b.author}{b.family ? ` · ${b.family}` : ''}</span>
              </button>
            ) : (
              <span key={b.title} className="bookbtn off" title="not fetched yet">{b.title}<span>{b.author} · not fetched</span></span>
            ))}
          </div>
        )}
    </>
  );
}

function Browser({ br, branchKey, go }: { br: BrowseData; branchKey: string | null; go: (p: string) => void }) {
  const [vars, setVars] = useState<Set<string>>(new Set());
  const [sizes, setSizes] = useState<Set<string>>(new Set());
  const [f, setF] = useState<Filters>(blankFilters);
  const branch = branchKey ? (br.branches || []).find((b) => b.key === branchKey) || null : null;

  useEffect(() => {
    // a new branch (or the branches' own page) resets the facet filters and the variation picks
    setF(blankFilters());
    setVars(new Set());
  }, [branchKey]);

  if (!branchKey) {
    return (
      <Branches br={br} sizes={sizes} setSizes={setSizes} onOpen={(k) => go(libraryBranchHref(k))} />
    );
  }
  if (!branch) {
    return <MissingBranch branchKey={branchKey} go={go} />;
  }
  return (
    <BranchView
      br={br} branch={branch} vars={vars} sizes={sizes} f={f}
      setVars={setVars} setF={setF}
      onBack={() => go('/library')}
    />
  );
}

/** A branch address the payload does not name: a typo, or a branch saved in the store after this
 *  build. It says so and offers the branches rather than pretending the address is /library. */
function MissingBranch({ branchKey, go }: { branchKey: string; go: (p: string) => void }) {
  return (
    <>
      <div className="bcrumb">
        <a className="selchip" href="/library" onClick={(e) => plainClick(e, () => go('/library'))}>Library</a>
        <span className="s">›</span> <b>{branchKey}</b>
      </div>
      <div className={emptyCls()}>
        no branch is called “{branchKey}”. <a href="/library" onClick={(e) => plainClick(e, () => go('/library'))}>see every branch</a>
      </div>
    </>
  );
}

function Branches({ br, sizes, setSizes, onOpen }: { br: BrowseData; sizes: Set<string>; setSizes: (s: Set<string>) => void; onOpen: (k: string) => void }) {
  const toggle = (p: string) => { const n = new Set(sizes); n.has(p) ? n.delete(p) : n.add(p); setSizes(n); };
  const sizeName = (p: string) => ((br.sizes || []).find((s) => s.preset === p) || { name: p }).name;
  return (
    <>
      <div className="k">Branches <span className="s">a branch is a purpose the books are gathered for; open one to compose a configuration and explore what is in it</span></div>
      <div className="bhand">
        <span className="k">Ships that work it</span>{' '}
        {(br.sizes || []).map((s) => (
          <button key={s.preset} type="button" className={`selchip bsize${sizes.has(s.preset) ? ' on' : ''}`} data-size={s.preset} title={s.preset} onClick={() => toggle(s.preset)}>{s.name}</button>
        ))}
        {sizes.size ? <button type="button" className="selchip bclear-size" onClick={() => setSizes(new Set())}>clear ×</button> : null}{' '}
        <span className="s">{sizes.size ? 'the branches that size cannot work on are dimmed' : 'the size that has read a branch of the library; pick one or more to filter'}</span>
      </div>
      <div className="bbranches">
        {(br.branches || []).map((b) => {
          const vars = b.variations || [];
          const ix = [...new Set(vars.flatMap((v) => v.books))];
          const t = bSum(ix.map((i) => br.books[i]));
          const sz = (b.sizes || []).map(sizeName).join(', ') || 'no size has read it yet';
          const worked = !sizes.size || (b.sizes || []).some((p) => sizes.has(p));
          return (
            <a
              key={b.key} className={`bbranch${worked ? '' : ' none'}`} href={libraryBranchHref(b.key)} data-branch={b.key}
              onClick={(e) => plainClick(e, () => onOpen(b.key))}
            >
              <span className="bbname">{b.name}</span>
              <span className="bbpurpose">{b.purpose}</span>
              <span className="bbnum"><b>{vars.length}</b> sailed · <b>{t.n.toLocaleString()}</b> books · {big(t.w)} words</span>
              <span className="bbnum s bbwork">ships: {sz}</span>
              <span className="bbvars">
                {vars.slice(0, 6).map((v) => <span key={v.key} className="selchip">{v.name}</span>)}{' '}
                {vars.length > 6 ? <span className="s">+{vars.length - 6} more</span> : null}
              </span>
            </a>
          );
        })}
      </div>
      {br.branches_stored ? null : <div className="s mt">these are the default branches, not yet stored: <span className="mono">thorp select branches</span> writes them to Postgres, where they can be changed</div>}
      <div className="s mt">Library facts {br.fingerprint}: {br.books.length.toLocaleString()} books in all, derived texts included. A branch's ships are the sizes that have read its variations' lists (its voyages on the ledger); a variation that has never sailed has none, and a branch of selections has none until one is read.</div>
    </>
  );
}

function BranchView({ br, branch, vars, sizes, f, setVars, setF, onBack }: {
  br: BrowseData; branch: Branch; vars: Set<string>; sizes: Set<string>; f: Filters;
  setVars: (s: Set<string>) => void; setF: (fn: Filters | ((p: Filters) => Filters)) => void; onBack: () => void;
}) {
  const sizeName = (p: string) => ((br.sizes || []).find((s) => s.preset === p) || { name: p }).name;
  const byKey = useMemo(() => Object.fromEntries(branch.variations.map((v) => [v.key, v])), [branch]);
  const touched = useRef(false);
  useEffect(() => { touched.current = false; }, [branch.key]);

  const toggleVar = (key: string) => {
    const n = new Set(vars); n.has(key) ? n.delete(key) : n.add(key);
    setVars(n);
    setF((p) => ({ ...blankFilters(), sort: p.sort }));
  };

  // the branch's whole shelf: what the configuration editor draws on, independent of the old list picked below
  const branchBooks = useMemo(() => {
    const ix = new Set(branch.variations.flatMap((v) => v.books));
    return [...ix].sort((a, b) => a - b).map((i) => br.books[i]);
  }, [branch, br.books]);
  const branchWords = useMemo(() => bSum(branchBooks).w, [branchBooks]);
  const lists = useMemo(() => branch.variations.filter((v) => v.list).map((v) => ({ key: v.key, name: v.name, list: v.list! })), [branch]);
  const scope = useMemo(() => {
    const vs = branch.variations.filter((v) => !vars.size || vars.has(v.key));
    const ix = new Set(vs.flatMap((v) => v.books));
    return [...ix].sort((a, b) => a - b).map((i) => br.books[i]);
  }, [branch, vars, br]);

  const now = scope.filter((b) => bPass(b, f, br));
  const tot = bSum(scope);
  const cur = bSum(now);
  const periodOrder = (k: string) => (k === 'undated' ? 9999 : k === 'before 1500' ? 0 : parseInt(k));
  const order: Partial<Record<Dim, string[]>> = { kind: Object.keys(br.kinds), voice: Object.keys(br.voices) };

  const facets = BDIMS.map(([dim, label, note]) => {
    const c: Record<string, { n: number; w: number }> = {};
    for (const b of scope) if (bPass(b, f, br, dim)) for (const v of bVals(b, dim, br)) { const x = c[v] || (c[v] = { n: 0, w: 0 }); x.n++; x.w += b[10]; }
    if (dim === 'collection') for (const col of br.collections) c[col.name] = c[col.name] || { n: 0, w: 0 };
    for (const v of f[dim]) c[v] = c[v] || { n: 0, w: 0 };
    let ks = Object.keys(c);
    ks = dim === 'period' ? ks.sort((a, b) => periodOrder(a) - periodOrder(b))
      : dim === 'collection' ? ks.sort((a, b) => c[b].n - c[a].n)
      : order[dim] ? ks.sort((a, b) => order[dim]!.indexOf(a) - order[dim]!.indexOf(b))
      : ks.sort((a, b) => c[b].w - c[a].w);
    const max = Math.max(...ks.map((k) => c[k].w), 1);
    const tip = (k: string) => dim === 'kind' ? br.kinds[k] : dim === 'voice' ? br.voices[k] : dim === 'collection' ? (br.collections.find((x) => x.name === k) || {}).about : dim === 'period' ? (k === 'undated' ? 'no writer years in the catalogue' : '') : '';
    return (
      <div key={dim} className="bfacet" data-dim={dim}>
        <div className="k">{label} <span className="s">{note}</span></div>
        <div className="bcards">
          {ks.map((k) => (
            <button key={k} type="button" className={`bcard${f[dim].has(k) ? ' on' : ''}${c[k].n ? '' : ' none'}`} data-dim={dim} data-val={k} title={tip(k) || ''}
              onClick={() => { const n = new Set(f[dim]); n.has(k) ? n.delete(k) : n.add(k); setF({ ...f, [dim]: n, more: 200 }); }}>
              <span className="bname">{k}</span>
              <span className="bnum">{c[k].n}<span className="s"> · {big(c[k].w)}</span></span>
              <span className="bbar"><i style={{ width: `${(100 * c[k].w / max).toFixed(0)}%` }} /></span>
            </button>
          ))}
        </div>
        {dim === 'period' ? (
          <div className="bshow">
            <label className="s">from <input className="bnum-in" type="number" placeholder="year" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value, more: 200 })} /></label>{' '}
            <label className="s">to <input className="bnum-in" type="number" placeholder="year" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value, more: 200 })} /></label>{' '}
            <span className="s">undated books fall outside any bounds</span>
          </div>
        ) : null}
        {dim === 'source' ? (
          <div className="bshow">
            <label className="s">Ogden-ness at least <input className="bnum-in" type="number" min={0} max={100} placeholder="%" value={f.ogden} onChange={(e) => setF({ ...f, ogden: e.target.value, more: 200 })} />%</label>{' '}
            <span className="s">unscored books fall short of a bar</span>
          </div>
        ) : null}
      </div>
    );
  });

  const chips = BDIMS.flatMap(([dim, label]) => [...f[dim]].map((v) => (
    <button key={dim + v} type="button" className="selchip bchip" onClick={() => { const n = new Set(f[dim]); n.delete(v); setF({ ...f, [dim]: n, more: 200 }); }}>{label}: {v} ×</button>
  )));
  if (f.start !== '' || f.end !== '') chips.push(<button key="years" type="button" className="selchip bchip" onClick={() => setF({ ...f, start: '', end: '', more: 200 })}>years {f.start || '…'} to {f.end || '…'} ×</button>);
  if (f.ogden !== '') chips.push(<button key="ogden" type="button" className="selchip bchip" onClick={() => setF({ ...f, ogden: '', more: 200 })}>Ogden-ness ≥ {f.ogden}% ×</button>);

  const sort = f.sort;
  const rows = now.slice().sort(sort === 'year' ? (a, b) => (a[7] ?? 9999) - (b[7] ?? 9999) : sort === 'title' ? (a, b) => a[1].localeCompare(b[1]) : sort === 'ogden' ? (a, b) => (b[9] ?? -1) - (a[9] ?? -1) : (a, b) => b[10] - a[10]);

  const spec = {
    languages: Object.fromEntries([...(f.language.size ? f.language : new Set(now.map((b) => b[3])))].sort().map((l) => [l, +(bSum(now.filter((b) => b[3] === l)).w / (cur.w || 1)).toFixed(3)])),
    ...(f.ogden !== '' ? { ogden: { min: +f.ogden / 100 } } : {}),
    ...((f.start !== '' || f.end !== '') ? { period: { start: f.start === '' ? null : +f.start, end: f.end === '' ? null : +f.end, undated: 'exclude' } } : {}),
    ...(f.kind.size ? { kinds: { include: [...f.kind] } } : {}),
    ...(f.voice.size ? { voices: { include: [...f.voice] } } : {}),
    ...(f.source.size ? { sources: { include: [...f.source] } } : {}),
  };

  const one = vars.size === 1 ? branch.variations.find((v) => vars.has(v.key)) || null : null;
  const delta = (v: Variation) => {
    const p = v.derived_from ? byKey[v.derived_from] : null;
    if (!p) return null;
    const a = new Set(p.books), b = new Set(v.books);
    return <span className="s">from {p.name}: +{v.books.filter((i) => !a.has(i)).length} −{p.books.filter((i) => !b.has(i)).length}</span>;
  };

  return (
    <>
      <div className="bcrumb">
        <a className="selchip" href="/library" onClick={(e) => plainClick(e, onBack)}>Library</a> <span className="s">›</span> <b>{branch.name}</b>
      </div>
      <p className="foaim">{branch.purpose}</p>
      <BranchConfig
        branchKey={branch.key}
        branchName={branch.name}
        books={branchBooks}
        attributes={branch.attributes || []}
        defaults={branch.default_choices || {}}
        configurations={branch.configurations || []}
        totalWords={branchWords}
        lists={lists}
      />
      <div className="k mt">Sailed configurations <span className="s">the named lists this branch has already sailed, locked: pick one or more to look at just those, or none for all of them together{sizes.size ? `; dimmed: not read at ${[...sizes].map(sizeName).join(' or ')}` : ''}</span></div>
      <div className="bcards bvars">
        {branch.variations.map((v) => {
          const t = bSum(v.books.map((i) => br.books[i]));
          const worked = !sizes.size || (v.sizes || []).some((p) => sizes.has(p));
          const sz = (v.sizes || []).map(sizeName).join(', ') || 'not sailed yet';
          return (
            <button key={v.key} type="button" className={`bcard bvar${vars.has(v.key) ? ' on' : ''}${worked ? '' : ' none'}`} title={v.about || ''} onClick={() => toggleVar(v.key)}>
              <span className="bname">{v.name}<span className="s"> locked</span>{v.draft ? <span className="s"> draft</span> : null}</span>
              <span className="bnum">{t.n.toLocaleString()}<span className="s"> books · {big(t.w)}</span></span>
              <span className="s">{v.kind === 'selection' ? 'a selection, not a list' : v.kind === 'all' ? 'the whole library' : v.list}</span>
              <span className="s">ships: {sz}</span>
              {delta(v)}
            </button>
          );
        })}
      </div>
      <div className="k mt">What is in the sailed {vars.size ? [...vars].map((k) => byKey[k].name).join(' + ') : 'branch'}</div>
      <div className="bsummary"><b>{cur.n.toLocaleString()}</b> of {tot.n.toLocaleString()} books · <b>{big(cur.w)}</b> of {big(tot.w)} words{chips.length ? <button type="button" className="selchip bclear" onClick={() => setF(blankFilters())}>clear all</button> : null}</div>
      <div className="selchips">{chips}</div>
      <div className="bfacets">{facets}</div>
      <div className="k mt">The books in this sailed view <span className="s">sorted by <select className={selectCls('')} value={sort} onChange={(e) => setF({ ...f, sort: e.target.value as Filters['sort'], more: 200 })}><option value="words">length</option><option value="year">year</option><option value="title">title</option><option value="ogden">Ogden-ness</option></select> · hover a kind or voice for the rule that placed it</span></div>
      <div className="scroll">
        <table className="selbooks">
          <thead><tr><th>book</th><th>writer</th><th>lang</th><th>year</th><th>kind</th><th>voice</th><th>source</th><th>Ogden</th><th>words</th><th>collections</th></tr></thead>
          <tbody>
            {rows.slice(0, f.more).map((b) => (
              <tr key={b[0]}>
                <td title={b[1]}><a href="#" onClick={(e) => { e.preventDefault(); void openInReader(b[0]); }}>{cut(b[1], 56)}</a> <span className="s mono">{b[0]}</span></td>
                <td>{cut(b[2], 26)}</td><td>{b[3]}</td>
                <td title={b[8]}>{b[7] ?? '–'} <span className="s">{b[8]}</span></td>
                <td title={b[12]}>{b[5]}</td><td title={b[13]}>{b[6]}</td><td>{b[4]}</td>
                <td>{b[9] == null ? '–' : Math.round(100 * b[9]) + '%'}</td>
                <td>{big(b[10])}</td>
                <td className="s">{cut(b[11].map((i) => br.collections[i].name).join(', '), 60)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > f.more ? <button type="button" className="selchip bmore" onClick={() => setF({ ...f, more: f.more + 200 })}>show 200 more ({rows.length - f.more} left)</button> : null}
      <details className="mt">
        <summary>This sailed view as a fitout's selection <span className="s">the same filters as declared weights and filters (thorp/selection.py); the shares are this view's, to be set by hand</span></summary>
        <pre className="bspec">{JSON.stringify(spec, null, 1)}</pre>
      </details>
      <div className="s mt">Library facts {br.fingerprint}; the year is an estimate (no catalogue we hold gives a publication date), the kind and voice are read from subjects, bookshelves and credits; each carries its rule.</div>
      {one && one.fitouts && one.fitouts.length ? <Selection fitout={one.fitouts[0]} /> : null}
    </>
  );
}

function Selection({ fitout }: { fitout: string }) {
  const { data, error } = useApi<SelectionData | null>(`/api/selection?fitout=${encodeURIComponent(fitout)}`, 0);
  if (error) return <div className={emptyCls()}>the selection could not be read: {error}</div>;
  if (!data) return <div className={emptyCls()}>reading the selection…</div>;
  const rules = data.rules || {};
  return (
    <div className="mt">
      <div className="k">Selection <span className="s">the fitout's books as declared weights and filters (thorp/selection.py), over the library's facts ({data.facts.books} books, build {data.facts.fingerprint || 'not stored'})</span></div>
      {data.stages.map((st) => {
        const c = st.composition;
        return (
          <div key={st.ordinal} className="selstage">
            <div className="k">Stage {st.ordinal}: {st.name} <span className="s">{st.books} books, {big(st.words)} words by the library's count ({st.found} found in the facts), {st.passes || 1} pass{(st.passes || 1) === 1 ? '' : 'es'}</span></div>
            <div className="selchips" dangerouslySetInnerHTML={{ __html: selDeclared(st.compose) }} />
            {c ? (
              <>
                <div className="k mt">The rules, in order <span className="s">books left after each; composed {String(c.composed_at).slice(0, 16).replace('T', ' ')} from facts {c.facts_fingerprint}, selection {c.spec_hash}, list {c.list_path} (sha1 {String(c.list_sha1).slice(0, 10)})</span></div>
                <table className="selfunnel"><tbody>{(c.funnel || []).map(([rule, n, what]) => <tr key={rule}><td className="num">{n}</td><td><b>{rule}</b> <span className="s">{what}</span></td></tr>)}</tbody></table>
                <div className="selchecks">
                  {(c.prechecks || []).map((k) => <span key={k.name} className={pillCls(k.passed ? 'green' : 'red')} title={JSON.stringify(k.evidence)}>{k.passed ? 'pass' : 'FAIL'} {k.name}</span>)}
                  {c.diff ? <span className={pillCls(c.diff.same_books ? 'green' : 'amber')}>{c.against}: {c.diff.same_books ? 'the same books' : `${c.diff.only_composed.length} only composed, ${c.diff.only_list.length} only listed`}{c.diff.same_order ? ', same order' : ''}</span> : null}
                </div>
                {(c.notes || []).map((n) => <div key={n} className="s">note: {n}</div>)}
              </>
            ) : st.compose ? <div className="s mt">declared, not composed yet: <span className="mono">thorp select compose</span></div> : null}
            <div className="selgrid">
              <div dangerouslySetInnerHTML={{ __html: selCounts('By language', 'share of the words', st.by_language) }} />
              <div dangerouslySetInnerHTML={{ __html: selCounts('By kind', 'share of the words; a kind is the first rule that matches (below)', st.by_kind) }} />
              <div dangerouslySetInnerHTML={{ __html: selCounts('By voice', 'who speaks: the Church, the press, a body, Nothing up my sleeve itself, any other writer', st.by_voice) }} />
              <div dangerouslySetInnerHTML={{ __html: selCounts('By source', 'the collection the text came from', st.by_source) }} />
              <div dangerouslySetInnerHTML={{ __html: selCounts('By period', "the writer's year (floruit); undated has none", st.by_period) }} />
              <div dangerouslySetInnerHTML={{ __html: selCounts('How the year was found', 'published: recorded when fetched; floruit: birth + 40; late: death - 25', st.by_year_basis) }} />
            </div>
          </div>
        );
      })}
      <details className="mt"><summary>What the words mean: kind, voice and the year</summary>
        <div className="selrules">
          <div><div className="k">Kinds <span className="s">one to a book, the first rule that matches</span></div><ul>{Object.entries(rules.kinds || {}).map(([k, v]) => <li key={k}><b>{k}</b> {v as string}</li>)}</ul></div>
          <div><div className="k">Voices <span className="s">read from the catalogue's credit and subjects</span></div><ul>{Object.entries(rules.voices || {}).map(([k, v]) => <li key={k}><b>{k}</b> {v as string}</li>)}</ul></div>
        </div>
      </details>
    </div>
  );
}

interface SelectionStage {
  ordinal: number; name: string; books: number; words: number; found: number; passes?: number;
  compose: unknown; by_language: Record<string, { share: number; books: number; words: number }>;
  by_kind: Record<string, { share: number; books: number; words: number }>;
  by_voice: Record<string, { share: number; books: number; words: number }>;
  by_source: Record<string, { share: number; books: number; words: number }>;
  by_period: Record<string, { share: number; books: number; words: number }>;
  by_year_basis: Record<string, { share: number; books: number; words: number }>;
  composition: {
    composed_at: string; facts_fingerprint: string; spec_hash: string; list_path: string; list_sha1: string;
    funnel?: [string, number, string][]; prechecks?: { name: string; passed: boolean; evidence: unknown }[];
    diff?: { same_books: boolean; same_order: boolean; only_composed: unknown[]; only_list: unknown[] } | null;
    against?: string; notes?: string[];
  } | null;
}
interface SelectionData {
  stages: SelectionStage[];
  rules: { kinds?: Record<string, string>; voices?: Record<string, string>; year?: Record<string, number> };
  facts: { books: number; fingerprint?: string };
}
