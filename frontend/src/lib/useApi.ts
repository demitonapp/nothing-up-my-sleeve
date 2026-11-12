// The React islands' shared data hook (9 November, the island work): one typed poll, one request in
// flight at a time (a slow endpoint never piles up), and the header's "updated" stamp. The islands
// replace the dashboard.ts monolith panel by panel; this is the piece every one of them needs.

import { useEffect, useState } from 'react';

/** The route the page is on. A path is the address; only an old hash route (`#/discoveries/stars`) is
 *  read as one, the way the old router did. A plain fragment (`#mastercharter`, `#param-ship-layers`)
 *  is an anchor on the page, not an address: reading it as the route hid the page under a bare island
 *  (12 November, the charter's goal links). */
export const routePath = (): string => (location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname);

export function setUpdated(): void {
  const el = document.getElementById('updated');
  if (el) el.textContent = 'updated ' + new Date().toLocaleTimeString();
}

/** The route, read after mount: the islands are server-rendered too, where `location` does not
 *  exist. The first render on both sides is the loading state, so hydration never mismatches. */
export function useRoute(): string {
  const [route, setRoute] = useState('/');
  useEffect(() => {
    setRoute(routePath());
  }, []);
  return route;
}

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Fetch `url` now, then again every `everyMs`; the next request starts only after the last one
 *  settles, so a 30 s endpoint is not hammered by a 5 s refresh. Pass null to skip the fetch, or
 *  `enabled = false` when this island is not the page on screen (the shells mount several islands). */
export function useApi<T>(url: string | null, everyMs = 5000, enabled = true): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!enabled || !url) {
      setLoading(false);
      return;
    }
    let live = true;
    let timer: number | undefined;
    const load = async () => {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const json = (await res.json()) as T;
        if (!live) return;
        setData(json);
        setError(null);
      } catch (e) {
        if (live) setError(String((e as Error)?.message ?? e));
      } finally {
        if (live) {
          setLoading(false);
          setUpdated();
          if (everyMs > 0) timer = window.setTimeout(load, everyMs);
        }
      }
    };
    load();
    return () => {
      live = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [url, everyMs, enabled]);

  return { data, error, loading };
}

/** A section wrapper: the page's one section is active by itself, since the old router is not here
 *  to toggle `.section.active` any more. */
export const sectionProps = (id: string) => ({ className: 'section active', id });
