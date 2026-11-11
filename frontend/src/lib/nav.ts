// The one place the site's navigation is defined: the five ways in (the header), the tabs each
// section shows under it, and the rule for which one is active. The header, every island and the
// static pages read this file, so a section's tabs cannot drift from page to page (UI.md,
// "Navigation"). Pure logic only: no DOM, no React.

export type MainKey = 'places' | 'expeditions' | 'discoveries' | 'leaderboard' | 'library';

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
    key: 'places', label: 'Places', href: '/harbours',
    title: 'the places: Demiton\'s orbital and the trading orbital, where every other lab and its ships reside',
    match: ['/harbours', '/harbors', '/ships', '/sizes', '/classes', '/rung', '/foreign', '/shipyard', '/labs'],
  },
  {
    key: 'expeditions', label: 'Expeditions', href: '/expeditions',
    title: 'the expeditions: what each standard went out to find, and the VSM (the five systems)',
    match: ['/expeditions', '/voyages', '/vsm', '/governance'],
  },
  { key: 'discoveries', label: 'Discoveries', href: '/discoveries', title: '', match: ['/discoveries'] },
  { key: 'leaderboard', label: 'Leaderboard', href: '/leaderboard', title: '', match: ['/leaderboard'] },
  { key: 'library', label: 'Library', href: '/library', title: '', match: ['/library', '/shelves'] },
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

/** The header tab a path belongs to. Pages outside the five ways in (a bet, a chat) stay on Places,
 *  where they are reached from. */
export function mainTabFor(path: string): MainKey {
  const p = navPath(path);
  if (at(p, '/expeditions') || at(p, '/voyages') || at(p, '/vsm') || at(p, '/governance')) return 'expeditions';
  if (at(p, '/discoveries')) return 'discoveries';
  if (at(p, '/leaderboard')) return 'leaderboard';
  if (at(p, '/library') || at(p, '/shelves')) return 'library';
  return 'places';
}

const placesSection = (p: string): SectionNav => {
  // The shipyard is not a way in of its own (12 November, Justin: "the shipyard is only within demiton's
  // orbital"): it is a page under Demiton, reached from /harbours/demiton's yards, and /shipyard keeps
  // Orbitals lit. The old harbour shipbuilder addresses are Demiton's too.
  const labs = at(p, '/labs');
  return {
    key: 'places',
    label: 'Places',
    items: [
      { key: 'harbours', label: 'Orbitals', href: '/harbours', active: !labs },
      // the houses that build the outside ships: the labs page (12 November, Justin)
      { key: 'labs', label: 'Labs', href: '/labs', active: labs },
    ],
  };
};

const expeditionSub = (p: string): string => {
  if (at(p, '/vsm') || at(p, '/governance')) return 'vsm';
  if (at(p, '/expeditions/queue') || at(p, '/voyages/queue')) return 'queue';
  if (at(p, '/expeditions/plans') || at(p, '/expeditions/expeditions') || at(p, '/voyages/plans') || at(p, '/voyages/expeditions')) return 'plans';
  if (p === '/expeditions' || p === '/voyages') return 'overview';
  // a voyage keeps the Plans tab lit: it is one of the plans
  if (at(p, '/expeditions') || at(p, '/voyages')) return 'plans';
  return 'overview';
};

const expeditionsSection = (p: string): SectionNav => {
  const sub = expeditionSub(p);
  return {
    key: 'expeditions',
    label: 'Expeditions',
    items: [
      // the old Overview (the SOP cards) is gone: the plans page is the Overview now, and /expeditions
      // and /expeditions/plans are the same page (11 November, Justin)
      { key: 'overview', label: 'Overview', href: '/expeditions', active: sub === 'overview' || sub === 'plans' },
      { key: 'queue', label: 'Queue', href: '/expeditions/queue', active: sub === 'queue' },
      {
        key: 'vsm', label: 'VSM', href: '/vsm', active: sub === 'vsm',
        title: 'the VSM: the five systems (S1 operations, S2 coordination, S3 control with the gate and the audit, S4 intelligence, S5 policy)',
      },
    ],
  };
};

// the overview doors: a domain is read on the overview, a trick and its chain on the skills ladder
const DISCOVERY_DOMAINS = new Set(['physics', 'maths', 'mathematics', 'reasoning', 'philosophy']);

const discoverySub = (p: string): string => {
  const rest = p.replace(/^\/discoveries\/?/, '').split('/')[0];
  if (rest === 'tests' || rest === 'two-facts') return 'tests';
  if (rest === 'stars' || rest === 'cards' || rest === 'tells') return 'stars';
  if (rest === 'skills' || rest === 'registry' || rest === 'quantum' || rest === 'traits' || rest === 'chains') return 'skills';
  if (!rest || DISCOVERY_DOMAINS.has(rest)) return 'overview';
  return 'skills'; // a trick of the trade
};

const discoveriesSection = (p: string): SectionNav => {
  const sub = discoverySub(p);
  return {
    key: 'discoveries',
    label: 'Discoveries',
    items: [
      { key: 'overview', label: 'Overview', href: '/discoveries', active: sub === 'overview' },
      { key: 'stars', label: 'Stars', href: '/discoveries/stars', active: sub === 'stars' },
      { key: 'skills', label: 'Skills', href: '/discoveries/skills', active: sub === 'skills' },
      { key: 'tests', label: 'Tests', href: '/discoveries/tests', active: sub === 'tests' },
    ],
  };
};

/**
 * The tabs a page shows under the header, or null when the section is one page (Leaderboard,
 * Library) and has nothing to switch between. The same function serves the islands and the static
 * pages, so a page cannot forget its section's row.
 */
export function sectionNavFor(path: string): SectionNav | null {
  const p = navPath(path);
  if (p === '/' || at(p, '/shipyard') || at(p, '/harbours') || at(p, '/harbors') || at(p, '/ships')
    || at(p, '/sizes') || at(p, '/classes') || at(p, '/rung') || at(p, '/foreign') || at(p, '/labs')) return placesSection(p);
  if (at(p, '/expeditions') || at(p, '/voyages') || at(p, '/vsm') || at(p, '/governance')) return expeditionsSection(p);
  if (at(p, '/discoveries')) return discoveriesSection(p);
  return null;
}
