// The breadcrumb trail (12 November, Justin: "can we have breadcrumbs throughout the UI for ease of
// navigation"). One function reads an address and says where it sits in the site, from Places down, so
// every page gets the same trail from the layout instead of each island writing its own "← back" link.
// The tree is the site's as it stands today (lib/nav.ts, DemitonTabs): Orbitals holds Demiton and Masaq'
// Reach; Demiton holds the berth, the shipyard, the library, the expeditions (with the queue),
// its classes and every ship; Masaq' Reach holds the labs, the models and the embeddings. Old addresses
// (/harbours, /masaq, /labs, /voyages, /shelves, /governance) sit where their pages now live.
// Pure: no DOM, no React.

import { navPath } from './nav';

export interface Crumb {
  label: string;
  href: string;
  /** Quick ways on from this crumb, shown as a dropdown when it is chosen (12 November, Justin: "if i
   *  select masaq reach then a dropdown should appear with quick options to navigate, same thing for
   *  demiton's orbital"). A `group` starts a new labelled section of the menu. */
  menu?: MenuItem[];
}

export interface MenuItem {
  label: string;
  href: string;
  group?: string;
  note?: string;
}

// Demiton's quick ways on: its views (DemitonTabs), the queue and the VSM inside the expeditions, every
// ship, and its classes smallest first, by their canonical address
const DEMITON_MENU: MenuItem[] = [
  { label: 'Overview', href: '/orbitals/demiton', group: 'The orbital' },
  { label: 'Berth', href: '/orbitals/demiton/berth' },
  { label: 'Shipyard', href: '/shipyard' },
  { label: 'Library', href: '/library' },
  { label: 'Images', href: '/library/images', note: 'in the Library' },
  { label: 'VSM', href: '/vsm', note: 'its own way in' },
  { label: 'Expeditions', href: '/expeditions', group: 'At sea' },
  { label: 'Queue', href: '/expeditions/queue' },
  { label: 'Every ship', href: '/ships' },
  { label: 'The towing tank', href: '/ships/300k', note: '300k', group: 'The classes' },
  { label: 'The measured mile', href: '/ships/1m', note: '1m' },
  { label: 'The sea trial', href: '/ships/9m', note: '9m' },
  { label: 'The coasting run', href: '/ships/21m', note: '21m' },
  { label: 'The paragraph', href: '/ships/50m', note: '50m' },
  { label: 'Invention', href: '/ships/100m', note: '100m' },
  { label: 'The trader', href: '/ships/350m', note: '350m' },
];

// Masaq' Reach's quick ways on: its three views, and the models by size band
const MASAQ_MENU: MenuItem[] = [
  { label: 'Labs', href: '/orbitals/masaq', group: 'The Reach' },
  { label: 'Models', href: '/orbitals/masaq/models' },
  { label: 'Embeddings', href: '/orbitals/masaq/embeddings' },
  { label: 'Extra small', href: '/orbitals/masaq/models/xsmall', group: 'Models by size' },
  { label: 'Small', href: '/orbitals/masaq/models/small' },
  { label: 'Medium', href: '/orbitals/masaq/models/medium' },
  { label: 'Large', href: '/orbitals/masaq/models/large' },
];

// switching between the orbitals (12 November, Justin: "the breadcrumb for orbital also needs to have a
// dropdown so i can quickly switch between orbitals"): the two the Orbitals page holds, ours and the Reach
const ORBITALS_MENU: MenuItem[] = [
  { label: 'Every orbital', href: '/orbitals', group: 'The orbitals' },
  { label: 'Demiton', href: '/orbitals/demiton', note: 'our own' },
  { label: "Masaq' Reach", href: '/orbitals/masaq', note: 'the trading orbital' },
];

const ORBITALS: Crumb = { label: 'Orbitals', href: '/orbitals', menu: ORBITALS_MENU };
const DEMITON: Crumb = { label: 'Demiton', href: '/orbitals/demiton', menu: DEMITON_MENU };
const MASAQ: Crumb = { label: "Masaq' Reach", href: '/orbitals/masaq', menu: MASAQ_MENU };
const EXPEDITIONS: Crumb = { label: 'Expeditions', href: '/expeditions' };
const LIBRARY: Crumb = { label: 'Library', href: '/library' };
const SHIPYARD: Crumb = { label: 'Shipyard', href: '/shipyard' };
const MODELS: Crumb = { label: 'Models', href: '/orbitals/masaq/models' };

// a class's address by its slug or its size (router.ts CLASS_RENAMES): the trail names it the same way
const CLASS: Record<string, string> = {
  '300k': 'The towing tank', 'towing-tank': 'The towing tank', seedling: 'The towing tank', keel: 'The towing tank',
  pan: 'The towing tank', faces: 'The towing tank',
  '1m': 'The measured mile', 'measured-mile': 'The measured mile', pilot: 'The measured mile', augustus: 'The measured mile',
  '9m': 'The sea trial', 'sea-trial': 'The sea trial', speller: 'The sea trial',
  '21m': 'The coasting run', 'coasting-run': 'The coasting run', stylist: 'The coasting run',
  '50m': 'The paragraph', paragraph: 'The paragraph',
  '100m': 'Invention', invention: 'Invention',
  '350m': 'The trader', trader: 'The trader',
};
const SIZE_OF: Record<string, string> = {
  'towing-tank': '300k', 'measured-mile': '1m', 'sea-trial': '9m', 'coasting-run': '21m', paragraph: '50m', invention: '100m', trader: '350m',
};
const BAND: Record<string, string> = { xsmall: 'Extra small', small: 'Small', medium: 'Medium', large: 'Large' };
const COUNTRY: Record<string, string> = { us: 'US', cn: 'China', fr: 'France', ca: 'Canada', ae: 'UAE', gb: 'UK' };
// a house by its key, as the Reach writes it; any other key is title-cased
const HOUSE: Record<string, string> = {
  openai: 'OpenAI', xai: 'xAI', zai: 'Z.ai', antgroup: 'Ant Group', deepseek: 'DeepSeek', minimax: 'MiniMax',
  stepfun: 'StepFun', bytedance: 'ByteDance', thinkingmachines: 'Thinking Machines', tii: 'TII', nvidia: 'NVIDIA',
};
const WORDS: Record<string, string> = {
  vsm: 'VSM', s1: 'S1 Operations', s2: 'S2 Coordination', s3: 'S3 Control', s4: 'S4 Intelligence', s5: 'S5 Policy', sops: 'SOPs', ifeval: 'IFEval', arc: 'ARC',
  'at-sea': 'At sea', 'quantum-tests': 'Quantum tests', 'two-facts': 'Two facts', mtsp: 'MTSP',
};

const decode = (s: string): string => {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
};

/** A segment as a reader names it: a known word, else its words with the first capitalised. A run id or a
 *  model name (it has an @, a dot or a digit beside a letter) is kept exactly as written. */
export const labelOf = (seg: string): string => {
  const s = decode(seg);
  if (WORDS[s]) return WORDS[s];
  if (/[@.]/.test(s) || /\d[a-z]|[a-z]\d/i.test(s)) return s;
  const w = s.replace(/[-_]+/g, ' ').trim();
  return w ? w[0].toUpperCase() + w.slice(1) : s;
};

const houseLabel = (key: string): string => HOUSE[key] || labelOf(key);
const classLabel = (slug: string): string => {
  const name = CLASS[slug];
  const size = SIZE_OF[slug] || (CLASS[slug] && /^\d/.test(slug) ? slug : '');
  return name ? (size ? `${name} ${size}` : name) : labelOf(slug);
};

/** The trail for an address, outermost first; the last crumb is the page itself. Empty for the home page
 *  and for an address the tree does not know (better no trail than a wrong one). */
export function crumbsFor(path: string): Crumb[] {
  const p = navPath(path);
  const parts = p.split('/').filter(Boolean);
  const [a, b, c, d] = parts;
  const out: Crumb[] = [];
  const add = (label: string, href: string): void => {
    out.push({ label, href });
  };
  const tail = (from: number, base: string): void => {
    let href = base;
    for (const seg of parts.slice(from)) {
      href += '/' + seg;
      add(labelOf(seg), href);
    }
  };

  if (!a) return [];

  // Masaq' Reach, at its canonical address and its two aliases
  const masaqAt = a === 'orbitals' && b === 'masaq' ? 2 : a === 'masaq' ? 1 : a === 'labs' ? 1 : -1;
  if (masaqAt >= 0) {
    out.push(ORBITALS, MASAQ);
    const [x, y, z] = parts.slice(masaqAt);
    if (!x || x === 'labs') return out;
    if (x === 'models' || x === 'ships') {
      out.push(MODELS);
      if (y && BAND[y]) add(BAND[y], `/orbitals/masaq/models/${y}`);
      return out;
    }
    if (x === 'embeddings') {
      add('Embeddings', '/orbitals/masaq/embeddings');
      return out;
    }
    // a house: /orbitals/masaq/<country>/<key>[/models]
    if (y) {
      add(houseLabel(y), `/orbitals/masaq/${x}/${y}`);
      if (z === 'models') add('Models', `/orbitals/masaq/${x}/${y}/models`);
      return out;
    }
    add(COUNTRY[x] || labelOf(x), `/orbitals/masaq`);
    return out;
  }

  if (a === 'orbitals' || a === 'harbours' || a === 'harbors') {
    out.push(ORBITALS);
    if (!b) return out;
    if (b === 'demiton') {
      out.push(DEMITON);
      if (c === 'berth') add('Berth', '/orbitals/demiton/berth');
      else if (c === 'ships') add('Every ship', '/ships');
      else if (c === 'shipbuilder') out.push(SHIPYARD);
      return out;
    }
    if (b === 'masaq-reach' || b === 'zayton') {
      out.push(MASAQ);
      if (c === 'ships' || (c && BAND[c])) {
        out.push(MODELS);
        const band = BAND[c] ? c : d;
        if (band && BAND[band]) add(BAND[band], `/orbitals/masaq/models/${band}`);
      }
      return out;
    }
    add(labelOf(b), `/orbitals/${b}`);
    tail(2, `/orbitals/${b}`);
    return out;
  }

  if (a === 'shipyard') {
    out.push(ORBITALS, DEMITON, SHIPYARD);
    tail(1, '/shipyard');
    return out;
  }

  if (a === 'library' || a === 'shelves') {
    out.push(ORBITALS, DEMITON, LIBRARY);
    if (b) add(b === 'images' ? 'Images' : labelOf(b), `/library/${b}`);
    return out;
  }

  if (a === 'expeditions' || a === 'voyages') {
    out.push(ORBITALS, DEMITON, EXPEDITIONS);
    if (!b || b === 'plans' || b === 'expeditions') return out;
    if (b === 'queue') {
      add('Queue', '/expeditions/queue');
      if (c) add(labelOf(c), `/expeditions/queue/${c}`);
      return out;
    }
    add(labelOf(b), `/expeditions/${b}`);
    if (c && c !== 'overview') add(labelOf(c), `/expeditions/${b}/${c}`);
    return out;
  }

  // the VSM is a way in of its own (12 November), not a page of Demiton's expeditions
  if (a === 'vsm' || a === 'governance') {
    add('VSM', '/vsm');
    const sys = b === 'control' ? 's3' : b === 'acquisition' ? 's1' : b;
    if (sys) add(labelOf(sys), `/vsm/${sys}`);
    return out;
  }

  if (a === 'sizes' || a === 'classes' || a === 'rung') {
    out.push(ORBITALS, DEMITON);
    if (!b) return out;
    add(classLabel(b), `/sizes/${b}`);
    if (c && c !== 'overview') add(labelOf(c), `/sizes/${b}/${c}`);
    if (c && d) add(labelOf(d), `/sizes/${b}/${c}/${d}`);
    return out;
  }

  if (a === 'ships') {
    out.push(ORBITALS, DEMITON);
    if (!b || b === 'all') {
      add('Every ship', '/ships');
      return out;
    }
    if (CLASS[b]) {
      // a class's page rewrites itself to /ships/<size>/<tab>[/<sub>], so its tabs carry on the trail
      add(classLabel(b), `/ships/${b}`);
      if (c && c !== 'overview') add(labelOf(c), `/ships/${b}/${c}`);
      if (c && d) add(labelOf(d), `/ships/${b}/${c}/${d}`);
      return out;
    }
    add('Every ship', '/ships');
    add(decode(b), `/ships/${b}`);
    if (c) add(labelOf(c), `/ships/${b}/${c}`);
    return out;
  }

  if (a === 'foreign') {
    out.push(ORBITALS, MASAQ, MODELS);
    if (b) add(decode(b), `/foreign/${b}`);
    return out;
  }

  if (a === 'leaderboard') {
    add('Leaderboard', '/leaderboard');
    if (!b) return out;
    if (BAND[b]) {
      add(BAND[b], `/leaderboard/${b}`);
      return out;
    }
    if (b === 'competitor') {
      if (c) add(decode(c), `/leaderboard/competitor/${c}`);
      return out;
    }
    if (b === 'lab') {
      if (c) add(houseLabel(c), `/leaderboard/lab/${c}`);
      return out;
    }
    if (b === 'thorp') {
      add('Our ships', '/leaderboard/thorp');
      return out;
    }
    tail(1, '/leaderboard');
    return out;
  }

  if (a === 'discoveries') {
    add('Discoveries', '/discoveries');
    if (b && b !== 'overview') tail(1, '/discoveries');
    return out;
  }

  if (a === 'settings') {
    add('Settings', '/settings');
    tail(1, '/settings');
    return out;
  }

  if (a === 'bet' || a === 'chat') {
    out.push(ORBITALS);
    add(a === 'bet' ? 'The bet' : 'Chat', `/${a}`);
    return out;
  }

  return [];
}
