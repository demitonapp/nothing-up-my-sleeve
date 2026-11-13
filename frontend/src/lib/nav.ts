// The one place the site's navigation is defined: the two ways in (the header), the tabs each
// section shows under it, and the rule for which one is active. The header, every island and the
// static pages read this file, so a section's tabs cannot drift from page to page (UI.md,
// "Navigation"). Pure logic only: no DOM, no React.

import { PUBLIC_EDITION } from './edition';

export type MainKey = 'places' | 'expeditions' | 'leaderboard' | 'library';

export interface MainTab {
  key: MainKey;
  label: string;
  href: string;
  title: string;
  /** The path prefixes that open this way in. The header's script uses it when an island pushes a
   *  new address without a page load. */
  match: string[];
}

export interface TabItem {
  key: string;
  label: string;
  href?: string;
  active: boolean;
  title?: string;
  hidden?: boolean;
  data?: Record<string, string>;
}

export interface SectionNav {
  key: MainKey;
  label: string;
  items: TabItem[];
}

export const MAIN_TABS: MainTab[] = [
  {
    key: 'places', label: 'Orbitals', href: '/orbitals',
    // the public edition (lib/edition.ts) has no Demiton, so its tooltip names only the orbitals it keeps
    title: PUBLIC_EDITION
      ? 'the places: Masaq\' Reach, the trading orbital where the labs and their ships reside, and Sleeper Service, the museum orbital'
      : 'the places: Demiton\'s orbital (its berth, shipyard, library and expeditions) and the trading orbital, where every other lab and its ships reside',
    match: ['/orbitals', '/harbours', '/harbors', '/ships', '/sizes', '/classes', '/rung', '/foreign', '/shipyard', '/masaq', '/labs', '/expeditions', '/library', '/shelves', '/discoveries'],
  },
  { key: 'leaderboard', label: 'Leaderboard', href: '/leaderboard', title: '', match: ['/leaderboard'] },
];

/** A path as the router reads it: no query, no leading hash, no trailing slash. */
export const navPath = (path: string): string => {
  let p = String(path || '/').split('?')[0];
  if (p.startsWith('#')) p = p.slice(1);
  if (!p.startsWith('/')) p = '/' + p;
  if (p.length > 1) p = p.replace(/\/+$/, '');
  return p || '/';
};

/** The branch a Library address names: `/library/ogden` opens Ogden, `/library` is the branches'
 *  own page. The old `/shelves` address answers the same way. */
export const libraryBranchOf = (path: string): string | null => {
  const m = /^\/(?:library|shelves)\/([^/]+)$/.exec(navPath(path));
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
};

/** One branch's own address. A branch key is a slug already; encode so a custom key with a space or
 *  a slash still lands on its page. */
export const libraryBranchHref = (key: string): string => `/library/${encodeURIComponent(key)}`;

/** True for the base address itself or anything below it. */
const at = (p: string, base: string): boolean => p === base || p.startsWith(base + '/');

/** The header tab a path belongs to. Pages outside the two ways in (a bet, a chat) stay on Orbitals,
 *  where they are reached from. The Liberty Machine is Demiton's, so it lights Orbitals and is reached
 *  from the orbital's card and crumb (12 November, Justin: "liberty machine link should be removed from
 *  the top right navigation. It's navigable via the demiton orbital"). */
export function mainTabFor(path: string): MainKey {
  const p = navPath(path);
  // Discoveries is not a way in of its own (12 November, Justin): it is a view in each orbital, so Places is lit
  if (at(p, '/leaderboard')) return 'leaderboard';
  // Expedition and Library addresses are Demiton's views now (12 November), so Orbitals is the way in.
  return 'places';
}

const placesSection = (p: string): SectionNav => {
  // The shipyard is not a way in of its own (12 November, Justin: "the shipyard is only within demiton's
  // orbital"): it is a page under Demiton, reached from /harbours/demiton's yards, and /shipyard keeps
  // Orbitals lit. The old harbour shipbuilder addresses are Demiton's too.
  // Orbitals has one way in now (12 November): the two orbitals. The shipyard is inside Demiton, and the
  // labs are inside Masaq' Reach's two views, so neither is a tab of its own.
  return {
    key: 'places',
    label: 'Orbitals',
    items: [
      { key: 'harbours', label: 'Orbitals', href: '/orbitals', active: true },
    ],
  };
};

/** The tabs a page shows under the header, or null when the section is one page (Leaderboard,
 *  Library) and has nothing to switch between. The same function serves the islands and the static
 *  pages, so a page cannot forget its section's row. The Liberty Machine and the Expeditions return
 *  null: their crumb's menu is the navigation (12 November). */
export function sectionNavFor(path: string): SectionNav | null {
  const p = navPath(path);
  if (p === '/' || at(p, '/shipyard') || at(p, '/orbitals') || at(p, '/harbours') || at(p, '/harbors') || at(p, '/ships')
    || at(p, '/sizes') || at(p, '/classes') || at(p, '/rung') || at(p, '/foreign') || at(p, '/labs')) return placesSection(p);
  if (at(p, '/orbitals/demiton/liberty-machine') || at(p, '/governance') || at(p, '/vsm')) return null;
  if (at(p, '/expeditions') || at(p, '/voyages')) return null;
  return null;
}

/** The Liberty Machine's own pages: the overview (the five cards) and one page a system. The old addresses answer:
 *  /orbitals/demiton/liberty-machine/control is S3's, /orbitals/demiton/liberty-machine/acquisition S1's, and /governance the Liberty Machine's. */
export const LIBERTY_MACHINE_SYSTEMS: { key: 's1' | 's2' | 's3' | 's4' | 's5'; label: string; name: string }[] = [
  { key: 's1', label: 'S1', name: 'Operations' },
  { key: 's2', label: 'S2', name: 'Coordination' },
  { key: 's3', label: 'S3', name: 'Control' },
  { key: 's4', label: 'S4', name: 'Intelligence' },
  { key: 's5', label: 'S5', name: 'Policy' },
];

/** The systems whose address is a word, not their S-number: S1 is Operations (12 November, Justin: "this url ...
 *  should not be s1 but rather ... operations") and S5 is Policy (13 November, Justin chose /policy for the page that
 *  leads with feedback). S2 to S4 keep their number. */
export const LIBERTY_MACHINE_SLUG: Partial<Record<'s1' | 's2' | 's3' | 's4' | 's5', string>> = { s1: 'operations', s5: 'policy' };

/** One system's address. */
export const libertyMachineHref = (key: string): string =>
  `/orbitals/demiton/liberty-machine/${LIBERTY_MACHINE_SLUG[key as 's1'] || key}`;

/** The system a segment after the machine names: its word (operations, policy), an old alias (acquisition is
 *  S1's, control S3's) or its S-number; null for none. */
export const libertyMachineKeyOf = (seg: string): 's1' | 's2' | 's3' | 's4' | 's5' | null => {
  if (seg === 'operations' || seg === 'acquisition') return 's1';
  if (seg === 'control') return 's3';
  if (seg === 'policy') return 's5';
  if (/^s[1-5]$/.test(seg)) return seg as 's1' | 's2' | 's3' | 's4' | 's5';
  return null;
};

export const libertyMachineSystemOf = (path: string): 's1' | 's2' | 's3' | 's4' | 's5' | null => {
  // both addresses are read: /liberty-machine (12 November, Justin's own) and the Demiton alias
  // /orbitals/demiton/liberty-machine. The segment after the machine names the system, so a prefix
  // can be added or moved without a regular expression that a replacement can break.
  let p = navPath(path);
  for (const prefix of ['/governance', '/vsm', '/orbitals/demiton/liberty-machine']) {
    if (p === prefix || p.startsWith(prefix + '/')) {
      p = '/liberty-machine' + p.slice(prefix.length);
      break;
    }
  }
  const parts = p.split('/').filter(Boolean);
  if (parts[0] !== 'liberty-machine') return null;
  return libertyMachineKeyOf(parts[1] || '');
};

