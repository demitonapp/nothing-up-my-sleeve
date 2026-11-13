// The breadcrumb trail (12 November, Justin: "can we have breadcrumbs throughout the UI for ease of
// navigation"). One function reads an address and says where it sits in the site, from the orbitals down, so
// every page gets the same trail from the layout instead of each island writing its own "← back" link.
// The tree is the site's as it stands today (lib/nav.ts): Orbitals holds Demiton and Masaq'
// Reach; Demiton holds the berth, the shipyard, the library, the expeditions (with the queue), the
// Liberty Machine, its classes and every ship; Masaq' Reach holds the labs, the models and the
// embeddings. Old addresses (/harbours, /masaq, /labs, /voyages, /shelves, /governance, /vsm) sit where
// their pages now live.
// Pure: no DOM, no React.

import { LIBERTY_MACHINE_SYSTEMS, libertyMachineHref, libertyMachineKeyOf, navPath } from './nav';
import { PUBLIC_EDITION, isPrivatePath } from './edition';
import MUSEUM from '../data/museum.json';

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

// Demiton's quick ways on: its views, the queue and the Liberty Machine inside the orbital, every ship,
// and its classes smallest first, by their canonical address
const DEMITON_MENU: MenuItem[] = [
  { label: 'Overview', href: '/orbitals/demiton', group: 'The orbital' },
  { label: 'Shipyard', href: '/shipyard' },
  { label: 'Berth', href: '/shipyard/berth', note: 'in the Shipyard' },
  { label: 'Library', href: '/library' },
  { label: 'Images', href: '/library/images', note: 'in the Library' },
  { label: 'Discoveries', href: '/orbitals/demiton/discoveries', note: 'what our fleet found' },
  { label: 'Head kinds', href: '/orbitals/demiton/discoveries/head-kinds', note: 'in Discoveries' },
  { label: 'Liberty Machine', href: '/orbitals/demiton/liberty-machine' },
  { label: 'Expeditions', href: '/expeditions', group: 'At sea' },
  { label: 'Current Charter', href: '/expeditions/charter' },
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

// Masaq' Reach's quick ways on: its four views, and the models by size band
const MASAQ_MENU: MenuItem[] = [
  { label: 'Labs', href: '/orbitals/masaq/labs', group: 'The Reach' },
  { label: 'Research', href: '/orbitals/masaq/research' },
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
  { label: 'Sleeper Service', href: '/orbitals/sleeper-service', note: 'the museum orbital' },
];

const ORBITALS: Crumb = { label: 'Orbitals', href: '/orbitals', menu: ORBITALS_MENU };
const DEMITON: Crumb = { label: 'Demiton', href: '/orbitals/demiton', menu: DEMITON_MENU };
const MASAQ: Crumb = { label: "Masaq' Reach", href: '/orbitals/masaq', menu: MASAQ_MENU };
// Sleeper Service's quick ways on (13 November): the hall, its wings in their order, and the Lenders room
const MEMORY_MENU: MenuItem[] = [
  { label: 'The entrance hall', href: '/orbitals/sleeper-service', group: 'The museum' },
  ...Object.entries(MUSEUM.wings).map(([k, name]) => ({ label: name, href: `/orbitals/sleeper-service/wings/${k}` })),
  { label: 'The Lenders room', href: '/orbitals/sleeper-service/lenders' },
];
const MEMORY: Crumb = { label: 'Sleeper Service', href: '/orbitals/sleeper-service', menu: MEMORY_MENU };
// Expeditions' quick ways on (12 November, Justin: "make it open with three cards the Current Charter,
// Expeditions, Queue ... instead of using the tabs use the breadcrumbs nav"): the landing's three doors
// live on the crumb, so the pages themselves show no section tab row.
const EXPEDITIONS_MENU: MenuItem[] = [
  { label: 'Current Charter', href: '/expeditions/charter', group: 'The expedition' },
  { label: 'Every expedition', href: '/expeditions/expeditions' },
  { label: 'Queue', href: '/expeditions/queue' },
];
const EXPEDITIONS: Crumb = { label: 'Expeditions', href: '/expeditions', menu: EXPEDITIONS_MENU };
const LIBRARY: Crumb = { label: 'Library', href: '/library' };
const SHIPYARD: Crumb = { label: 'Shipyard', href: '/shipyard' };
const MODELS: Crumb = { label: 'Models', href: '/orbitals/masaq/models' };

// The Liberty Machine is breadcrumb-controlled: it has no section tabs, so its crumb carries the
// overview and the five systems (12 November).
const LIBERTY_MACHINE_MENU: MenuItem[] = [
  { label: 'Overview', href: '/orbitals/demiton/liberty-machine', group: 'The Liberty Machine' },
  ...LIBERTY_MACHINE_SYSTEMS.map((s) => ({ label: `${s.label} ${s.name}`, href: libertyMachineHref(s.key) })),
];
const LIBERTY_MACHINE: Crumb = { label: 'Liberty Machine', href: '/orbitals/demiton/liberty-machine', menu: LIBERTY_MACHINE_MENU };

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
const COUNTRY: Record<string, string> = { us: 'US', cn: 'China', fr: 'France', ca: 'Canada', ae: 'UAE', gb: 'UK', au: 'Australia', za: 'South Africa', br: 'Brazil' };
// a house by its key, as the Reach writes it; any other key is title-cased
const HOUSE: Record<string, string> = {
  openai: 'OpenAI', xai: 'xAI', zai: 'Z.ai', antgroup: 'Ant Group', deepseek: 'DeepSeek', minimax: 'MiniMax',
  stepfun: 'StepFun', bytedance: 'ByteDance', thinkingmachines: 'Thinking Machines', tii: 'TII', nvidia: 'NVIDIA',
  maincode: 'Maincode', wayve: 'Wayve', lelapa: 'Lelapa AI', maritaca: 'Maritaca AI',
  flower: 'Flower Labs', stability: 'Stability AI', uctnlp: 'UCT NLP', masakhane: 'Masakhane',
  sadilar: 'SADiLaR', 'sovereign-au': 'Sovereign Australia AI',
  eleutherai: 'EleutherAI', 'shanghai-ai': 'Shanghai AI Lab', baai: 'BAAI',
  'southern-cross': 'Southern Cross AI', kyutai: 'Kyutai', nilc: 'NILC',
  turing: 'Alan Turing Institute', mila: 'Mila', mbzuai: 'MBZUAI',
};
const WORDS: Record<string, string> = {
  'liberty-machine': 'Liberty Machine', s1: 'S1 Operations', s2: 'S2 Coordination', s3: 'S3 Control', s4: 'S4 Intelligence', s5: 'S5 Policy', sops: 'SOPs', ifeval: 'IFEval', arc: 'ARC',
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
const LB_CATEGORY: Record<string, string> = {
  logic: 'Logic', knowledge: 'Knowledge', reasoning: 'Reasoning', instruction: 'Instruction following', coding: 'Coding',
  agent: 'Agent', 'long-context': 'Long context', abilities: 'Abilities',
};

const CHARTER_PAGE: Record<string, string> = {
  fleet: 'The fleet', ship: 'The ship', tokeniser: 'The tokeniser', reads: 'What it reads', scaffold: 'The scaffold',
  training: 'The training', 'return-leg': 'The return leg', bar: 'The bar',
};

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
 *  and for an address the tree does not know (better no trail than a wrong one). The public edition
 *  (lib/edition.ts) has no trail on a private address, and no crumb or menu item that leads to one. */
export function crumbsFor(path: string): Crumb[] {
  if (!PUBLIC_EDITION) return trailFor(path);
  if (isPrivatePath(path)) return [];
  return trailFor(path)
    .filter((c) => !isPrivatePath(c.href))
    .map((c) => (c.menu ? { ...c, menu: c.menu.filter((m) => !isPrivatePath(m.href)) } : c));
}

function trailFor(path: string): Crumb[] {
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
    if (!x) {
      // the old /masaq and /labs roots still open the Labs view; the canonical root is the Reach's cards
      if (a === 'labs' || a === 'masaq') add('Labs', '/orbitals/masaq/labs');
      return out;
    }
    if (x === 'labs') {
      add('Labs', '/orbitals/masaq/labs');
      return out;
    }
    if (x === 'models' || x === 'ships') {
      out.push(MODELS);
      if (y && BAND[y]) add(BAND[y], `/orbitals/masaq/models/${y}`);
      return out;
    }
    if (x === 'embeddings') {
      add('Embeddings', '/orbitals/masaq/embeddings');
      return out;
    }
    if (x === 'research') {
      add('Research', '/orbitals/masaq/research');
      return out;
    }
    // the Reach's old discoveries address forwards to Demiton's head kinds (13 November): no crumb of its own
    if (x === 'discoveries') return out;
    // a country's pages (13 November): /orbitals/masaq/<cc>[/labs|/research|/models]; the landing of the cards is Labs
    if (/^[a-z]{2}$/.test(x) && (!y || y === 'labs' || y === 'research' || y === 'models') && !z) {
      add('Labs', '/orbitals/masaq/labs');
      add(COUNTRY[x] || labelOf(x), `/orbitals/masaq/${x}/labs`);
      if (y === 'research' || y === 'models') add(labelOf(y), `/orbitals/masaq/${x}/${y}`);
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
    // Sleeper Service, the museum Orbital (13 November): its wings, its exhibits and the Lenders room, named from
    // data/museum.json; an exhibit's trail runs through the era wing it hangs in
    if (b === 'sleeper-service') {
      out.push(MEMORY);
      if (c === 'wings' && d) add(MUSEUM.wings[d as keyof typeof MUSEUM.wings] || labelOf(d), `/orbitals/sleeper-service/wings/${d}`);
      else if (c === 'exhibits' && d) add(MUSEUM.exhibits[d as keyof typeof MUSEUM.exhibits] || labelOf(d), `/orbitals/sleeper-service/exhibits/${d}`);
      else if (c === 'lenders') add('The Lenders room', '/orbitals/sleeper-service/lenders');
      return out;
    }
    if (b === 'demiton') {
      out.push(DEMITON);
      if (c === 'liberty-machine') {
        out.push(LIBERTY_MACHINE);
        const sys = d ? libertyMachineKeyOf(d) : null;
        if (sys) add(labelOf(sys), libertyMachineHref(sys));
        return out;
      }
      if (c === 'berth') { out.push(SHIPYARD); add('Berth', '/shipyard/berth'); }
      else if (c === 'ships') add('Every ship', '/ships');
      else if (c === 'shipbuilder') out.push(SHIPYARD);
      else if (c === 'discoveries') {
        // Demiton's discoveries (12 November): its tabs, a trick, a chain, the traits, a door
        add('Discoveries', '/orbitals/demiton/discoveries');
        if (d && d !== 'overview') tail(3, '/orbitals/demiton/discoveries');
      }
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
    if (!b) return out;
    if (b === 'charter') {
      add('Current Charter', '/expeditions/charter');
      // each of the charter's cards has its own page (13 November)
      if (c) add(CHARTER_PAGE[c] || labelOf(c), `/expeditions/charter/${c}`);
      return out;
    }
    if (b === 'plans' || b === 'expeditions') {
      add('Every expedition', '/expeditions/expeditions');
      return out;
    }
    if (b === 'queue') {
      add('Queue', '/expeditions/queue');
      if (c) add(labelOf(c), `/expeditions/queue/${c}`);
      return out;
    }
    add(labelOf(b), `/expeditions/${b}`);
    if (c && c !== 'overview') add(labelOf(c), `/expeditions/${b}/${c}`);
    return out;
  }

  // the Liberty Machine sits under Demiton (12 November); its crumb's menu is the navigation and the
  // page shows no section tabs. The old flat addresses answer the same trail.
  if (a === 'liberty-machine' || a === 'governance' || a === 'vsm') {
    out.push(ORBITALS, DEMITON, LIBERTY_MACHINE);
    const sys = b ? libertyMachineKeyOf(b) : null;
    if (sys) add(labelOf(sys), libertyMachineHref(sys));
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

  // the two places a new visitor is sent from the home page (13 November): the book, with its reader, and joining
  if (a === 'book') {
    add('The book', '/book');
    if (b === 'read') add('Reading', '/book/read');
    return out;
  }
  if (a === 'join') {
    add('Join', '/join');
    return out;
  }

  if (a === 'leaderboard') {
    add('Leaderboard', '/leaderboard');
    if (!b) return out;
    if (BAND[b]) {
      add(BAND[b], `/leaderboard/${b}`);
      return out;
    }
    // a category of test (13 November): its own page
    if (LB_CATEGORY[b]) {
      add(LB_CATEGORY[b], `/leaderboard/${b}`);
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
