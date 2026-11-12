// The breadcrumb trail under the header, on every page (12 November, Justin: "can we have breadcrumbs
// throughout the UI for ease of navigation"). The trail is lib/crumbs.ts's; this island only draws it,
// first from the server's address (no flash on load) and then from the live one, because an island may
// push a new address without a page load (the layout's script announces it as `thorp:navigate`).

import { useEffect, useState } from 'react';
import { crumbsFor } from '@/lib/crumbs';

const livePath = (): string =>
  location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname;

export default function Breadcrumbs({ initialPath = '/' }: { initialPath?: string }) {
  const [path, setPath] = useState(initialPath);
  useEffect(() => {
    const read = (): void => setPath(livePath());
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
    <nav className="trail" aria-label="Breadcrumb">
      <ol>
        {trail.map((c, i) => {
          const last = i === trail.length - 1;
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
