// The breadcrumb trail under the header, on every page (12 November, Justin: "can we have breadcrumbs
// throughout the UI for ease of navigation"). The trail is lib/crumbs.ts's; this island only draws it,
// first from the server's address (no flash on load) and then from the live one, because an island may
// push a new address without a page load (the layout's script announces it as `thorp:navigate`).
//
// A crumb with a menu (Demiton, Masaq' Reach) opens a dropdown of quick ways on when chosen (12 November,
// Justin: "if i select masaq reach then a dropdown should appear with quick options to navigate, same thing
// for demiton's orbital"). The crumb's own page is the menu's first item, so nothing is lost by the crumb
// no longer being a plain link. It closes on Escape, a click outside, or the move a choice makes.

import { Fragment, useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { crumbsFor, type Crumb } from '@/lib/crumbs';
import { navPath } from '@/lib/nav';

const livePath = (): string =>
  location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname;

function MenuCrumb({ c, current, path, open, setOpen }: {
  c: Crumb; current: boolean; path: string; open: boolean; setOpen: (o: boolean) => void;
}) {
  const box = useRef<HTMLLIElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const here = navPath(path);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent): void => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', away);
    // the first item takes the focus, so the keyboard can walk the menu at once
    box.current?.querySelector<HTMLAnchorElement>('.trailmenu a')?.focus();
    return () => document.removeEventListener('mousedown', away);
  }, [open, setOpen]);

  const keys = (e: ReactKeyboardEvent<HTMLElement>): void => {
    const items = [...(box.current?.querySelectorAll<HTMLAnchorElement>('.trailmenu a') || [])];
    const at = items.indexOf(document.activeElement as HTMLAnchorElement);
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      button.current?.focus();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      const next = e.key === 'ArrowDown' ? (at + 1) % items.length : (at - 1 + items.length) % items.length;
      items[next]?.focus();
    }
  };

  return (
    <li ref={box} className="trailhas" onKeyDown={keys}>
      <button
        ref={button}
        type="button"
        className="trailbtn"
        aria-haspopup="true"
        aria-expanded={open}
        aria-current={current ? 'page' : undefined}
        onClick={() => setOpen(!open)}
      >
        {c.label}
        <svg viewBox="0 0 10 6" width="9" height="6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
      </button>
      {open ? (
        <div className="trailmenu" role="menu" aria-label={`${c.label}: quick ways on`}>
          {(c.menu || []).map((m, i) => (
            <Fragment key={m.href + i}>
              {m.group ? <div className="trailgroup">{m.group}</div> : null}
              <a
                role="menuitem"
                href={m.href}
                // no close on click: removing the link mid-click lost the move under Astro's router; the
                // move itself closes the menu (`thorp:navigate`, astro:page-load)
                aria-current={navPath(m.href) === here ? 'page' : undefined}
              >
                <span>{m.label}</span>
                {m.note ? <span className="s">{m.note}</span> : null}
              </a>
            </Fragment>
          ))}
        </div>
      ) : null}
    </li>
  );
}

export default function Breadcrumbs({ initialPath = '/' }: { initialPath?: string }) {
  const [path, setPath] = useState(initialPath);
  const [open, setOpen] = useState<string | null>(null);

  // pinned under the header as the page scrolls (12 November, Justin: "breadcrumbs should be pinned when a
  // user scrolls"): the header is sticky too and its height changes when it wraps on a narrow screen, so the
  // trail reads it and sits just below it (--header-h, used by nav.trail's `top`)
  // A page's own tabs pinned beneath the trail (`.pintabs`, 12 November, Justin: "the tabs for overview and
  // models should also be pinned") sit at --pin-top, the header and the trail together; with no trail on a
  // page, that is the header alone.
  const trailRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const header = document.querySelector('body > header');
    if (!header) return;
    const root = document.documentElement.style;
    const set = (): void => {
      const h = header.getBoundingClientRect().height;
      const t = trailRef.current?.isConnected ? trailRef.current.getBoundingClientRect().height : 0;
      root.setProperty('--header-h', `${h}px`);
      root.setProperty('--pin-top', `${h + t}px`);
    };
    set();
    const ro = new ResizeObserver(set);
    ro.observe(header);
    if (trailRef.current) ro.observe(trailRef.current);
    return () => ro.disconnect();
  }, [path]);
  useEffect(() => {
    const read = (): void => {
      setPath(livePath());
      setOpen(null); // a move closes any menu
    };
    read();
    window.addEventListener('thorp:navigate', read);
    window.addEventListener('popstate', read);
    window.addEventListener('hashchange', read);
    document.addEventListener('astro:page-load', read);
    return () => {
      window.removeEventListener('thorp:navigate', read);
      window.removeEventListener('popstate', read);
      window.removeEventListener('hashchange', read);
      document.removeEventListener('astro:page-load', read);
    };
  }, []);

  const trail = crumbsFor(path);
  // one crumb is the page itself and says nothing the header does not: no trail
  if (trail.length < 2) return null;
  return (
    <nav className="trail" aria-label="Breadcrumb" ref={trailRef}>
      <ol>
        {trail.map((c, i) => {
          const last = i === trail.length - 1;
          if (c.menu?.length) {
            return (
              <MenuCrumb
                key={c.href + i}
                c={c}
                current={last}
                path={path}
                open={open === c.href}
                setOpen={(o) => setOpen(o ? c.href : null)}
              />
            );
          }
          return (
            <li key={c.href + i}>
              {last ? <span aria-current="page">{c.label}</span> : <a href={c.href}>{c.label}</a>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
