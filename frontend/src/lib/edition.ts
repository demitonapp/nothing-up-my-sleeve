// The two editions (13 November, Justin: "we'll need to start preparing the UI for a public launch, so a public
// version would exclude all Demiton Orbital stuff for now and the settings"). One codebase builds both:
//
//   pnpm --dir frontend build                      the private dashboard, into backend/thorp/dash/static
//   PUBLIC_EDITION=1 pnpm --dir frontend build     the public site, into frontend/dist-public
//
// The public site keeps Masaq' Reach, Sleeper Service and the leaderboard. It leaves out Demiton and everything
// behind it (its views, berths, shipyard, library, expeditions and queue, the Liberty Machine, the discoveries,
// every ship of our fleet, the bet) and the settings. This file is the one list of what is left out: the build
// drops those pages (astro.config.mjs, the public-edition integration), and the header, the breadcrumbs, the ⌘K
// palette and the orbital cards drop their links to them. Pure: no DOM, no React.

/** True when this build is the public site. astro.config.mjs defines it from the PUBLIC_EDITION env var ('1' or
 *  unset), so the server render and the islands read the same value. */
export const PUBLIC_EDITION: boolean = import.meta.env.PUBLIC_EDITION === '1';

/** Every address the public site leaves out: a prefix covers itself and everything below it. Old aliases are
 *  listed too, since each one forwards into Demiton or the settings. */
export const PRIVATE_PREFIXES: readonly string[] = [
  // Demiton, our own orbital, and its two berths (at their orbital addresses and the old harbour ones)
  '/orbitals/demiton',
  '/orbitals/schimint',
  '/orbitals/vavatch-end',
  '/harbours/demiton',
  '/harbours/schimint',
  '/harbours/vavatch-end',
  '/harbours/phaleron',
  '/harbours/piraeus',
  // the Reach's old discoveries address forwards into Demiton's (lib/discoveryPaths.ts)
  '/orbitals/masaq/discoveries',
  // Demiton's views at their own addresses: the shipyard (and the berth), the library, the expeditions and queue
  '/shipyard',
  '/library',
  '/shelves',
  '/expeditions',
  '/voyages',
  // our fleet: every ship and class, and the old class addresses that forward to them
  '/ships',
  '/sizes',
  '/classes',
  '/rung',
  // the Liberty Machine's old flat addresses (astro.config.mjs redirects them into Demiton)
  '/liberty-machine',
  '/vsm',
  '/governance',
  // the old Discoveries addresses, which forward into Demiton's
  '/discoveries',
  // the $100 bet: our fleet's own numbers
  '/bet',
  // the settings: the disk, the store, the server, the switches, the keys
  '/settings',
];

const clean = (path: string): string => {
  let p = String(path || '/').split(/[?#]/)[0];
  if (!p.startsWith('/')) p = '/' + p;
  if (p.length > 1) p = p.replace(/\/+$/, '');
  return p || '/';
};

/** True for an address the public site leaves out, in either edition (the build and the dev server ask it). */
export const isPrivatePath = (path: string): boolean => {
  const p = clean(path);
  return PRIVATE_PREFIXES.some((base) => p === base || p.startsWith(base + '/'));
};

/** True for an address this build does not have: always false in the private dashboard. */
export const hiddenHere = (path: string): boolean => PUBLIC_EDITION && isPrivatePath(path);
