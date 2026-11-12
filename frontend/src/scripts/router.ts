// The dashboard's navigation, extracted from the view monolith (scripts/dashboard.ts) and typed.
// Pure logic only: the hash router, the canonical addresses and the tab constants (UI.md, "Navigation").
// Nothing here touches the DOM or the module state in dashboard.ts, so it can be unit-tested and reused
// by the multi-page split.

export interface Rung {
  name: string;
  preset: string;
  [key: string]: unknown;
}

export const slugOf = (r: { name: string }): string =>
  r.name.toLowerCase().replace(/^the\s+/, '').replace(/[^a-z0-9]+/g, '-');

// classes renamed (old address name -> new; server.py CLASS_RENAMES): either name opens the size,
// and the address is rewritten to the size's current name
export const CLASS_RENAMES: Record<string, string> = {
  seedling: 'towing-tank', keel: 'towing-tank', pan: 'towing-tank', faces: 'towing-tank',
  proxy: 'measured-mile', pilot: 'measured-mile', augustus: 'measured-mile', bettor: 'explorer', summit: 'trader',
  speller: 'sea-trial', stylist: 'coasting-run', // 12 Nov: the 9m is the sea trial, the 21m the coasting run
}; // 11 Nov: the 300k is the towing tank (was Faces, and Pan before it), the 1m the measured mile (was Augustus)
export const CLASS_ALIASES: Record<string, string> = Object.fromEntries(
  Object.entries(CLASS_RENAMES).flatMap(([a, b]) => [[a, b], [b, a]]),
);

export const MTABS = ['overview', 'fleet', 'goals', 'training', 'scoring', 'waypoints', 'sops', 'fitouts', 'bet', 'chat'];
export const STABS = ['betting', 'books', 'languages', 'sieves', 'attention', 'traits', 'chat'];
export const STAB_EL: Record<string, string> = { betting: 'betting', books: 'books', languages: 'languages', sieves: 'sieves', attention: 'attention', traits: 'traits-section', chat: 'chat' };
export const OLD_SHIP: Record<string, string> = { betting: 'betting', books: 'books', languages: 'languages', sieves: 'sieves', attention: 'attention', 'traits-section': 'traits' };
export const SECTION_NAV: Record<string, string> = { sizes: 'ships', rung: 'ships', ship: 'ships', 'runs-section': 'ships', foreign: 'ships', voyages: 'expeditions', voyage: 'expeditions', table: 'expeditions', discoveries: 'discoveries', leaderboard: 'leaderboard', competitor: 'leaderboard', lab: 'leaderboard', governance: 'governance', bet: 'bet', shelves: 'library' };
// an expedition page's tabs (UI.md, "Expeditions"): the same five for every expedition; one that doesn't apply is hidden
export const ETABS = ['overview', 'at-sea', 'findings', 'fleet', 'inside'];
// the Discoveries subtabs: the overview, the skills ladder (with the registry), the tests (with the
// chaining method) and the stars. The old two-facts, registry, quantum and cards addresses still answer.
export const DSUBS = ['overview', 'skills', 'quantum-tests', 'stars'];
// Governance's tabs (UI.md, "Governance"): the five systems, S3 control built out, acquisition one level down
export const GVIEWS = ['control', 'acquisition'];
export const WSUBS = ['expected', 'envelope', 'stars'];
export const SSUBS = ['maths', 'ask', 'language', 'shapes', 'number', 'physics', 'life', 'return', 'logic', 'versus'];
// the Overview's sub-pages: one per relation of the logic deck (2026-11-08)
export const OSUBS = ['order', 'cause', 'membership', 'proportion', 'counterfactual'].map((x) => 'logic-' + x);

export interface Route {
  page: string;
  [key: string]: unknown;
}

// A rung is addressed by its preset (its size, the canonical identifier) or by its class slug (an old
// alias the page resolves and rewrites to the preset); both live on the ships page.
const RUNG_PRESETS = new Set(['300k', '1m', '9m', '21m', '50m', '100m', '350m',
  'towing-tank', 'measured-mile', 'sea-trial', 'coasting-run', 'faces', 'pan', 'augustus', 'speller', 'stylist', 'paragraph', 'invention', 'trader']); // 'faces', 'pan', 'augustus', 'speller' and 'stylist' are old addresses

export function route(h: string): Route {
  if (h.startsWith('/')) {
    const [a, b, c] = h.slice(1).split('/');
    if ((a === 'sizes' || a === 'classes') && b) { const d = h.slice(1).split('/')[3]; return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'overview', wsub: WSUBS.includes(d) ? d : 'expected', ssub: SSUBS.includes(d) ? d : 'maths', osub: c === 'overview' && OSUBS.includes(d) ? d : null }; }
    if (a === 'models' && b) return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'overview' };
    if (a === 'foreign' && b) return { page: 'foreign', foreign: decodeURIComponent(b) };
    if (a === 'ships' && b === 'all') return { page: 'runs-section' };
    if (a === 'ships' && b && RUNG_PRESETS.has(b)) {
      // a preset is a rung, and a rung lives on the ships page: one address for both
      const d = h.slice(1).split('/')[3];
      return { page: 'rung', rung: b, mtab: MTABS.includes(c) ? c : 'overview', wsub: WSUBS.includes(d) ? d : 'expected',
               ssub: SSUBS.includes(d) ? d : 'maths', osub: c === 'overview' && OSUBS.includes(d) ? d : null };
    }
    if (a === 'ships' && b) {
      const d = h.slice(1).split('/')[3];
      if (STABS.includes(c)) return { page: 'ship', ship: decodeURIComponent(b), sailing: null, stab: c };
      return { page: 'ship', ship: decodeURIComponent(b), sailing: c ? decodeURIComponent(c) : null, stab: STABS.includes(d) ? d : 'betting' };
    }
    if (a === 'harbours' || a === 'harbors') return { page: 'sizes', harbour: b ? decodeURIComponent(b) : null, hsub: c === 'shipbuilder' || c === 'ships' ? c : null };
    if (a === 'ships' || a === 'classes' || a === 'sizes') return { page: 'sizes' };
    if ((a === 'voyages' || a === 'expeditions') && b === 'queue') return { page: 'voyages', vtab: 'queue', qview: c === 'every' ? 'every' : 'glance' };
    if (a === 'voyages' || a === 'expeditions') return { page: 'voyages', vtab: b === 'expeditions' ? 'expeditions' : 'queue', qview: c === 'every' ? 'every' : 'glance' }; // the queue is the landing view (9 November)
    if ((a === 'voyages' || a === 'expeditions') && b && c === 'table') return { page: 'table', voyage: b };
    if ((a === 'voyages' || a === 'expeditions') && b) return { page: 'voyage', voyage: b, etab: ETABS.includes(c) ? c : 'overview' };
    if (a === 'voyages' || a === 'expeditions') return { page: 'voyages', vtab: 'expeditions' };
    if (a === 'discoveries' && b === 'chains' && c) return { page: 'discoveries', dview: 'chain', chain: c };
    // the deprecated tabs' addresses answer at their new home
    if (a === 'discoveries' && b === 'two-facts') return { page: 'discoveries', dview: 'index', dsub: 'quantum-tests' };
    if (a === 'discoveries' && b === 'registry') return { page: 'discoveries', dview: 'index', dsub: 'skills' };
    if (a === 'discoveries' && b === 'quantum') return { page: 'discoveries', dview: 'index', dsub: 'skills' };
    if (a === 'discoveries' && b === 'cards') return { page: 'discoveries', dview: 'index', dsub: 'stars' };
    if (a === 'discoveries' && b === 'tests') return { page: 'discoveries', dview: 'index', dsub: 'quantum-tests' };
    if (a === 'discoveries' && (!b || DSUBS.includes(b))) return { page: 'discoveries', dview: 'index', dsub: b || 'overview' };
    if (a === 'discoveries') return { page: 'discoveries', dview: b === 'traits' ? b : 'trick', trick: b !== 'traits' ? b : null };
    if (a === 'leaderboard' && b === 'thorp' && c) return { page: 'competitor', thorp: decodeURIComponent(c) };
    if (a === 'leaderboard' && b === 'competitor' && c) return { page: 'competitor', model: decodeURIComponent(h.slice(1).split('/').slice(2).join('/')) };
    if (a === 'leaderboard' && b === 'lab' && c) return { page: 'lab', lab: decodeURIComponent(c) };
    if (a === 'leaderboard') return { page: 'leaderboard' };
    if (a === 'governance') return { page: 'governance', gview: GVIEWS.includes(b) ? b : 'systems' };
    if (a === 'bet') return { page: 'bet' };
    if (a === 'shelves' || a === 'library') return { page: 'shelves', shelf: b ? decodeURIComponent(b) : null };
    return { page: 'sizes' };
  }
  if (h.startsWith('rung-')) return { page: 'rung', rung: h.slice(5), mtab: 'overview' };
  if (h in OLD_SHIP) return { page: 'ship', ship: null, stab: OLD_SHIP[h] };
  if (h === 'runs-section') return { page: 'runs-section' };
  if (!h || h === 'sizes' || h === 'rung') return { page: 'sizes' };
  return { page: 'rung', rung: h, mtab: 'overview' }; // an old class link: #proxy
}

export const modelHash = (r: { name: string; preset?: string }, mt = 'overview', sub: string | null = null): string =>
  `/ships/${r.preset || slugOf(r)}${mt === 'overview' && !sub ? '' : '/' + mt}${mt === 'waypoints' && sub && sub !== 'expected' ? '/' + sub : ''}${mt === 'scoring' && sub && sub !== 'maths' ? '/' + sub : ''}${mt === 'overview' && sub ? '/' + sub : ''}`;

export const shipHash = (key: string, sailing: string | null = null, st = 'betting'): string =>
  `/ships/${key}${sailing ? '/' + encodeURIComponent(sailing) : ''}${st === 'betting' ? '' : '/' + st}`;
