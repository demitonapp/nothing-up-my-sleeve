// The book's page (13 November, Justin: the latest epub is something a visitor "can download, email to their
// kindle or read"). /book offers the three; /book/read is the reader, which reads the same epub the page offers
// for download (lib/epub.ts), one page of the book at a time, with Quentin Luck's footnotes opening at the foot
// of the screen as they do on a Kindle. The place a visitor reached is kept in their browser and nowhere else.

import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Download, Send, X } from 'lucide-react';
import '@/styles/first-cards.css';
import { btnCls, crumbCls, emptyCls, selectCls } from '@/lib/ui';
import { sectionProps } from '@/lib/useApi';
import { openEpub, type Epub, type EpubPage } from '@/lib/epub';
import { BOOK, bookPlace, longDate, megabytes, setBookPlace } from '@/lib/firstCards';
import KindleDialog from '../KindleDialog';

const isReader = (path: string): boolean => /^\/book\/read\/?$/.test(path.split('?')[0]);
const isBook = (path: string): boolean => /^\/book(\/read)?\/?$/.test(path.split('?')[0]);

function Landing() {
  const [kindle, setKindle] = useState(false);
  const [place, setPlace] = useState<string | null>(null);
  useEffect(() => { setPlace(bookPlace()); }, []);
  return (
    <div {...sectionProps('book')}>
      <h1>The book <span className="q">what this fleet is for and how it is built, written as it happens</span></h1>
      <div className="bookhero">
        <img className="bookcover" src={BOOK.cover} alt={`The cover of ${BOOK.title}: a card table`} width={300} height={400} />
        <div className="bookwords">
          <div className="bookeyebrow">{BOOK.version} · {longDate(BOOK.published)} · {megabytes(BOOK.bytes)}</div>
          <h2 className="booktitle">{BOOK.title}</h2>
          <p className="bookstand">{BOOK.standfirst}</p>
          <p className="bookby">{BOOK.byline}</p>
          <div className="bookacts">
            <a className={btnCls('default')} href={place ? `/book/read?p=${encodeURIComponent(place)}` : '/book/read'}><BookOpen aria-hidden="true" />{place ? 'Carry on reading' : 'Read it here'}</a>
            <a className={btnCls('outline')} href={BOOK.file} download={BOOK.downloadName}><Download aria-hidden="true" />Download the epub</a>
            <button type="button" className={btnCls('outline')} onClick={() => setKindle(true)}><Send aria-hidden="true" />Send to my Kindle</button>
          </div>
          <p className="booknote">
            The book is unfinished and says so: each version answers the notes made on the last, and the chapters not yet written are marked. Read it here, or take the file, which is the same one.
          </p>
        </div>
      </div>
      <KindleDialog open={kindle} onOpenChange={setKindle} />
    </div>
  );
}

function Reader() {
  const [book, setBook] = useState<Epub | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [at, setAt] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [size, setSize] = useState(18);
  const stage = useRef<HTMLDivElement>(null);
  const noteRef = useRef<HTMLDivElement>(null);
  const jump = useRef<string | null>(null);

  useEffect(() => {
    let closed = false;
    let opened: Epub | null = null;
    openEpub(BOOK.file)
      .then((b) => {
        if (closed) { b.close(); return; }
        opened = b;
        const asked = new URLSearchParams(location.search).get('p');
        const start = [asked, bookPlace()].find((h) => h && b.pages.some((p) => p.href === h)) || b.pages[0]?.href || null;
        setBook(b);
        setAt(start);
      })
      .catch((e: unknown) => { if (!closed) setError(e instanceof Error ? e.message : String(e)); });
    return () => { closed = true; opened?.close(); };
  }, []);

  const go = useCallback((href: string, anchor: string | null = null): void => {
    jump.current = anchor;
    setNote(null);
    setAt(href);
    history.replaceState(null, '', `/book/read?p=${encodeURIComponent(href)}`);
    setBookPlace(href);
  }, []);

  // draw the page that was asked for
  useEffect(() => {
    if (!book || !at || !stage.current) return;
    let stale = false;
    const el = stage.current;
    book.page(at)
      .then((nodes) => {
        if (stale) return;
        el.replaceChildren(nodes);
        setBookPlace(at);
        for (const a of el.querySelectorAll<HTMLAnchorElement>('a[href^="http"]')) { a.target = '_blank'; a.rel = 'noreferrer'; }
        const target = jump.current ? el.querySelector<HTMLElement>(`[id="${CSS.escape(jump.current)}"]`) : null;
        jump.current = null;
        if (target) target.scrollIntoView({ block: 'start' }); else window.scrollTo({ top: 0 });
      })
      .catch((e: unknown) => { if (!stale) setError(e instanceof Error ? e.message : String(e)); });
    return () => { stale = true; };
  }, [book, at]);

  // links inside the book: a footnote opens at the foot of the screen, another page of the book is turned to
  const onClick = (e: React.MouseEvent<HTMLDivElement>): void => {
    const a = (e.target as Element).closest('a');
    const href = a?.getAttribute('href');
    if (!a || !href || /^[a-z][a-z0-9+.-]*:/i.test(href)) return;
    e.preventDefault();
    const [file, anchor] = href.split('#');
    if (!file && anchor) {
      const aside = stage.current?.querySelector<HTMLElement>(`aside[id="${CSS.escape(anchor)}"]`);
      if (aside) { setNote(aside.innerHTML); return; }
      stage.current?.querySelector<HTMLElement>(`[id="${CSS.escape(anchor)}"]`)?.scrollIntoView({ block: 'start' });
      return;
    }
    if (book?.pages.some((p) => p.href === file)) go(file, anchor || null);
  };

  useEffect(() => { if (note && noteRef.current) noteRef.current.focus(); }, [note]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => { if (e.key === 'Escape') setNote(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const pages: EpubPage[] = book?.pages || [];
  const i = pages.findIndex((p) => p.href === at);
  const prev = i > 0 ? pages[i - 1] : null;
  const next = i >= 0 && i < pages.length - 1 ? pages[i + 1] : null;

  return (
    <div {...sectionProps('bookread')}>
      <h1><a className={crumbCls('back')} href="/book">The book</a> {BOOK.title} <span className="q">{BOOK.version}</span></h1>
      <div className="readbar">
        <a className={btnCls('ghost')} href="/book"><ArrowLeft aria-hidden="true" />The book</a>
        <label className="readwhere">
          <span className="sr-only">Page of the book</span>
          <select className={selectCls('max-w-full')} value={at || ''} onChange={(e) => go(e.target.value)} disabled={!pages.length}>
            {pages.map((p) => <option key={p.href} value={p.href}>{p.title}</option>)}
          </select>
        </label>
        <span className="readtools">
          <button type="button" className={btnCls('ghost')} onClick={() => setSize((s) => Math.max(14, s - 1))} aria-label="Smaller text">A&minus;</button>
          <button type="button" className={btnCls('ghost')} onClick={() => setSize((s) => Math.min(26, s + 1))} aria-label="Larger text">A+</button>
          <a className={btnCls('ghost')} href={BOOK.file} download={BOOK.downloadName} title="Download the epub" aria-label="Download the epub"><Download aria-hidden="true" /></a>
        </span>
      </div>
      {error ? (
        <div className={emptyCls()}>The book could not be opened here: {error}. <a href={BOOK.file} download={BOOK.downloadName}>Download the epub</a> and read it in any e-reader.</div>
      ) : (
        <article className="readpage" style={{ fontSize: `${size}px` }} aria-busy={!book}>
          {!book ? <p className="readwait">Opening the book…</p> : null}
          {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- the links inside are the controls; this only routes them */}
          <div className="readstage" ref={stage} onClick={onClick} />
        </article>
      )}
      {book && !error ? (
        <nav className="readturn" aria-label="Turn the page">
          {prev ? <button type="button" className={btnCls('outline')} onClick={() => go(prev.href)}><ArrowLeft aria-hidden="true" />{prev.title}</button> : <span />}
          <span className="readcount">{i + 1} of {pages.length}</span>
          {next ? <button type="button" className={btnCls('outline')} onClick={() => go(next.href)}>{next.title}<ArrowRight aria-hidden="true" /></button> : <span />}
        </nav>
      ) : null}
      {note ? (
        <div className="readnote" role="dialog" aria-label="Footnote" tabIndex={-1} ref={noteRef}>
          <button type="button" className="readnoteclose" onClick={() => setNote(null)} aria-label="Close the footnote"><X aria-hidden="true" /></button>
          {/* the footnote's own markup, from the epub this site built and serves */}
          <div className="readnotebody" dangerouslySetInnerHTML={{ __html: note }} />
        </div>
      ) : null}
    </div>
  );
}

export default function Book() {
  const [path, setPath] = useState<string | null>(null);
  useEffect(() => {
    const read = (): void => setPath(location.pathname);
    read();
    window.addEventListener('popstate', read);
    return () => window.removeEventListener('popstate', read);
  }, []);
  if (path === null || !isBook(path)) return null;
  return isReader(path) ? <Reader /> : <Landing />;
}
