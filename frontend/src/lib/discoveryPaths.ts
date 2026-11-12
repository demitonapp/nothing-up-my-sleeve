// Discoveries live in the two orbitals (12 November, Justin: "they should be rather moved to discoveries from demiton
// in the demiton orbital and then the discoveries applicable to the labs and research in the masaq orbital").
//
// - Demiton's discoveries: what our own fleet found. The overview (the doors, the questions, the sieve, the jobs),
//   the skills (the ladder, the route, the chains, every trick), the tests and our stars (lit by size, our ships
//   against Qwen3 4B, the bridge, the sixteen cards). The trick, chain, traits and door pages sit under it. The
//   shipyard's Charting section (/shipyard/charting) is the same page, as Justin asked on 10 November.
// - Masaq' Reach's discoveries: what is known of the outside models and the research field. The head kinds attention
//   research has named (the star chart), the census's clusters beyond the sixteen cards, and the Qwen 4B mapping
//   still to be sorted. Qwen3 4B's own head census and persona vectors are on its model page in the Reach.
//
// The old /discoveries addresses still answer: each is sent to its new home by `newHome`, so the links already out
// in the world (and in the ledger's essays) keep working.

export const DEMITON_DISCOVERIES = '/orbitals/demiton/discoveries';
/** The Reach's old discoveries address: it forwards to HEAD_KINDS (13 November, Justin: "discoveries should be moved
 *  to the demiton orbital", then "remove it" from Masaq' Reach: the head kinds, the cards beyond the sixteen and the
 *  Qwen mapping are Demiton's discoveries now). */
export const MASAQ_DISCOVERIES = '/orbitals/masaq/discoveries';
/** The head kinds research has named, the census's cards beyond the sixteen and the Qwen 4B mapping, under Demiton's. */
export const HEAD_KINDS = `${DEMITON_DISCOVERIES}/head-kinds`;
/** Qwen3 4B's page in the Reach, where its head census and persona vectors are read. */
export const QWEN4B_PAGE = '/foreign/qwen3-4b';

/** Masaq' Reach's discoveries tabs: the head kinds (the default), the cards beyond the sixteen, the Qwen 4B mapping. */
export const MASAQ_SUBS = ['kinds', 'cards', 'unsorted'] as const;
export type MasaqSub = (typeof MASAQ_SUBS)[number];

/** Every trick and chain page a static build must know of (the island reads the path; this is only the list). */
export const TRICK_KEYS = ['copying', 'spelling', 'successor', 'kin_test', 'pedigree_test', 'fire_test', 'workshop_test', 'counting_test',
  'period_test', 'breeders_test', 'smiths_test', 'gap_test', 'nature_test', 'mill_test', 'between_test', 'malthus_test',
  'rumford_test', 'triads_test', 'again_test', 'refrain_test', 'seasons_test', 'pigeonhole_test', 'lucretius_test',
  'recurrence_test', 'logic_test', 'crowns_test', 'origin_test', 'energy_test', 'mendeleev_gaps', 'geometry_test'];
export const CHAIN_KEYS = ['origin_test', 'energy_test', 'mendeleev_gaps', 'recurrence_test'];
/** The paths under a discoveries base, for getStaticPaths: the tabs, the old aliases, the doors, every trick and chain. */
export const DISCOVERY_PATHS = ['overview', 'two-facts', 'physics', 'maths', 'reasoning', 'philosophy', 'mathematics', 'skills',
  'quantum-tests', 'tests', 'quantum', 'registry', 'stars', 'cards', 'traits', 'head-kinds', 'head-kinds/cards', 'head-kinds/unsorted', ...TRICK_KEYS, ...CHAIN_KEYS.map((k) => `chains/${k}`)];

/** The Stars tabs that left Demiton for the Reach, and where each went. */
const STARS_TAB_HOME: Record<string, string> = {
  census: `${QWEN4B_PAGE}#heads`,
  personas: `${QWEN4B_PAGE}#personas`,
  beyond: `${HEAD_KINDS}/cards`,
  unsorted: `${HEAD_KINDS}/unsorted`,
};

/** Where an old discoveries address lives now, or null when the address is already at home. Reads `/discoveries/...`
 *  (the old top-level page), and a Stars tab that moved to the Reach under any base (`?tab=census`, ...). The query is
 *  kept, except a moved tab's own. */
export function newHome(address: string): string | null {
  const [pathPart, query = ''] = String(address || '').split('?');
  const path = pathPart.replace(/\/+$/, '') || '/';
  const q = new URLSearchParams(query);
  const tab = q.get('tab');
  // the Reach's old discoveries address: the same three tabs, now Demiton's
  if (path === MASAQ_DISCOVERIES || path.startsWith(`${MASAQ_DISCOVERIES}/`)) return `${HEAD_KINDS}${path.slice(MASAQ_DISCOVERIES.length)}${query ? `?${query}` : ''}`;
  const isStars = /\/(stars|cards|tells)$/.test(path);
  if (isStars && tab && STARS_TAB_HOME[tab]) return STARS_TAB_HOME[tab];
  if (path !== '/discoveries' && !path.startsWith('/discoveries/')) return null;
  const rest = path.slice('/discoveries'.length); // '' or '/x/y'
  const search = q.toString() ? `?${q.toString()}` : '';
  if (rest === '' || rest === '/overview') return `${DEMITON_DISCOVERIES}${search}`;
  if (rest === '/two-facts') return `${DEMITON_DISCOVERIES}/tests?test=chaining`;
  if (rest === '/registry' || rest === '/quantum') return `${DEMITON_DISCOVERIES}/skills`;
  if (rest === '/quantum-tests') return `${DEMITON_DISCOVERIES}/tests${search}`;
  if (rest === '/cards') return `${DEMITON_DISCOVERIES}/stars?tab=cards`;
  if (rest === '/mathematics') return `${DEMITON_DISCOVERIES}/maths`;
  return `${DEMITON_DISCOVERIES}${rest}${search}`;
}
