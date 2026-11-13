// The command palette (11 November; 12 November, Justin: "command K should be about navigation in the
// app, not chatting, that's covered by the chat terminal"): ⌘K or Ctrl+K on any page opens a filter
// over the app's places — the orbitals and their views, the ships, the expeditions, the Liberty
// Machine's systems, the discoveries and the leaderboard boards — and ⏎ goes there. ↑↓/⇥ move, esc
// closes. The chat is the terminal's own shortcut (⌘J), so this palette never opens a model.
//
// `chatHref` stays exported because the chat views use it to address a model's chat page; the palette
// itself no longer reads /api/chat/models or lists a model.

import { useEffect, useMemo, useRef, useState } from 'react';
import foreign from '@/data/foreign.json';
import { fieldCls } from '@/lib/ui';
import { LIBERTY_MACHINE_SYSTEMS, libertyMachineHref } from '@/lib/nav';
import { TEST_CATEGORIES } from '@/lib/testCategories';
import { AXES, DISCOVERIES, KINDS, OBJECTS, OURS, slugOf } from '@/lib/fieldMap';
import { TRICKS, WAYPOINTS } from '@/lib/fieldTricks';
import { CHAIN_KEYS, DEMITON_DISCOVERIES as DB } from '@/lib/discoveryPaths';
import { PUBLIC_EDITION, hiddenHere } from '@/lib/edition';

/** The foreign ships with a page of their own (data/foreign.json, written from thorp.foreign.models).
 *  Kept for `chatHref`, not for the palette's list. */
const FOREIGN_PAGES = new Set<string>((foreign as { keys: string[] }).keys);

export interface Model {
  kind: 'thorp' | 'foreign';
  model?: string | null;
  ship_key: string;
  name: string;
  params: number | null;
  available: boolean;
  run: { run: string; step: string } | null;
  why: string | null;
}

/** A model's chat address, as a thread records it: the ship's own tab for our ships, the harbour ship's
 *  for a foreign one that has a page, and the retired /chat (which now opens the console) for one that
 *  does not. The ship key is used as it is written (`300k:2980e0eca706`): its colon is a legal path
 *  character, and percent-encoding it misses the route. */
export const chatHref = (m: Pick<Model, 'kind' | 'model' | 'ship_key'>): string => {
  if (m.kind === 'foreign') {
    const key = String(m.model || '');
    return FOREIGN_PAGES.has(key) ? `/foreign/${key}/chat` : `/chat?model=${encodeURIComponent(key)}`;
  }
  return `/ships/${m.ship_key}/chat`;
};

export interface Dest {
  group: string;
  label: string;
  href: string;
  note?: string;
  /** Extra words a reader may type for this place (the label and note are searched too). */
  keywords?: string;
  /** Shown only once something is typed: the long lists (every discovery, every trick) would bury the places. */
  searchOnly?: boolean;
  /** The entry's own key (a trick's few_shot, a discovery's two-hop-curse): typed in full, it ranks first. */
  key?: string;
}

// Everything in Demiton's discoveries, searchable (13 November, Justin: "cmd k needs to be able to search all the
// discoveries"): the two axes and their categories, our own sections, the field's discoveries (each opens its card
// on its kind-of-claim page), every trick and the explorer's four chains. Built from the map's own data, so a new
// discovery or trick is found without an edit here.
const kindName = (k: string): string => (KINDS.find((c) => c.key === k) || { name: k }).name;
const objectName = (k: string): string => (OBJECTS.find((c) => c.key === k) || { name: k }).name;
const kindSlug = (k: string): string => { const c = KINDS.find((x) => x.key === k); return c ? slugOf(c) : k; };
const waypointName = (k: string): string => (WAYPOINTS.find((w) => w.key === k) || { name: k }).name;

const DISCOVERY_DESTS: Dest[] = [
  ...AXES.flatMap((a) => [
    { group: 'Discoveries', label: a.name, href: `${DB}/${a.slug}`, note: `axis ${a.n}: ${a.question}`, keywords: a.categories.map((c) => c.name).join(' ') },
    ...a.categories.map((c) => ({
      group: 'Discoveries', label: `${a.name} · ${c.name}`, href: `${DB}/${a.slug}/${slugOf(c)}`, note: c.question, keywords: c.about,
    })),
  ]),
  ...OURS.map((o) => ({
    group: 'Discoveries', label: o.title, href: o.href, note: `from our fleet · ${kindName(o.kind)} · ${objectName(o.object)}`, keywords: o.about,
  })),
  ...CHAIN_KEYS.map((k) => {
    const t = TRICKS.find((x) => x.key === k);
    return { group: 'Discoveries', label: `${t ? t.name : k}: the climb`, href: `${DB}/chains/${k}`, note: 'one of the explorer’s four discovery chains, rung by rung', keywords: `chain ${k}` };
  }),
  ...DISCOVERIES.map((d) => ({
    group: 'Field discoveries', label: d.title, href: `${DB}/kind-of-claim/${kindSlug(d.kind)}#${d.key}`,
    note: `${d.source} · ${kindName(d.kind)} · ${objectName(d.object)}`, keywords: d.finding, key: d.key, searchOnly: true,
  })),
  ...TRICKS.map((t) => ({
    group: 'Tricks of the trade', label: t.name, href: t.href,
    note: `${waypointName(t.waypoint)} · ${t.source || 'our own test'}`, keywords: t.does, key: t.key, searchOnly: true,
  })),
];

/** The places the palette can take you. Grouped in the order below; the top-level ways in come first,
 *  then Demiton's views, the ships, Masaq' Reach, the discoveries and the leaderboard boards. */
export const DESTINATIONS: Dest[] = [
  { group: 'The site', label: 'Orbitals', href: '/orbitals', note: PUBLIC_EDITION ? 'the trading orbital and the museum' : 'Demiton and the trading orbital' },
  { group: 'The site', label: 'Demiton', href: '/orbitals/demiton', note: 'our own orbital, its views and its fleet' },
  { group: 'The site', label: 'Masaq’ Reach', href: '/orbitals/masaq', note: 'the trading orbital' },
  { group: 'The site', label: 'Leaderboard', href: '/leaderboard', note: 'the tests and their boards' },
  { group: 'The site', label: 'The book', href: '/book', note: 'Nothing Up My Sleeve: read it, download it, send it to a Kindle', keywords: 'epub kindle read download nothing up my sleeve' },
  { group: 'The site', label: 'Join', href: '/join', note: 'investor, researcher, GPU provider, corpus provider', keywords: 'help faction side contribute volunteer' },
  { group: 'The site', label: 'Settings', href: '/settings', note: 'storage, the store, the server and the switches' },
  { group: 'The site', label: 'The bet', href: '/bet' },

  { group: 'Demiton', label: 'Shipyard', href: '/shipyard', note: 'the berth, where the fleet lies' },
  { group: 'Demiton', label: 'Berth', href: '/shipyard/berth', note: 'in the Shipyard: the two rings and every ship of the fleet' },
  { group: 'Demiton', label: 'Library', href: '/library', note: 'the books and sources our ships read' },
  { group: 'Demiton', label: 'Library images', href: '/library/images', note: 'the plates and illustrations' },
  { group: 'Demiton', label: 'Expeditions', href: '/expeditions', note: 'the current charter, the expeditions and the queue' },
  { group: 'Demiton', label: 'Current charter', href: '/expeditions/charter', note: 'the fleet, the master charter and the goals' },
  ...([['fleet', 'The fleet', 'the eight ships of v0.1'], ['ship', 'The ship', 'the hull: layers, width, heads, context'], ['tokeniser', 'The tokeniser', 'the vocabulary and the control symbols'],
    ['reads', 'What it reads', 'the recipe, passes, cleaning and order'], ['scaffold', 'The scaffold', 'cards, riddles and how a pin is held'], ['training', 'The training', 'optimiser, learning rate, batch, schedule'],
    ['return-leg', 'The return leg', 'the instruct ship’s leg']] as [string, string, string][]).map(([slug, name, note]) => ({
    group: 'Demiton', label: `Charter · ${name}`, href: `/expeditions/charter/${slug}`, note, keywords: 'charter master',
  })),
  { group: 'Demiton', label: 'Every expedition', href: '/expeditions/expeditions', note: 'the open preparations and the settled record' },
  { group: 'Demiton', label: 'The queue', href: '/expeditions/queue', note: 'what sails next, in order' },
  { group: 'Demiton', label: 'Liberty Machine', href: '/orbitals/demiton/liberty-machine', note: 'how the fleet governs itself' },
  ...LIBERTY_MACHINE_SYSTEMS.map((s) => ({
    group: 'Demiton', label: `${s.label} ${s.name}`, href: libertyMachineHref(s.key),
    note: s.key === 's5' ? 'the feedback the systems send up, sorted for S4' : 'a system of the Liberty Machine',
    keywords: s.key === 's5' ? 'feedback inbox taxonomy proposals' : undefined,
  })),

  { group: 'The ships', label: 'Every ship', href: '/ships', note: 'every ship of our fleet, and every run' },
  { group: 'The ships', label: 'The towing tank · 300k', href: '/ships/300k', keywords: 'smallest class' },
  { group: 'The ships', label: 'The measured mile · 1m', href: '/ships/1m' },
  { group: 'The ships', label: 'The sea trial · 9m', href: '/ships/9m' },
  { group: 'The ships', label: 'The coasting run · 21m', href: '/ships/21m' },
  { group: 'The ships', label: 'The paragraph · 50m', href: '/ships/50m' },
  { group: 'The ships', label: 'Invention · 100m', href: '/ships/100m' },
  { group: 'The ships', label: 'The trader · 350m', href: '/ships/350m', note: 'the largest class' },

  { group: 'Masaq’ Reach', label: 'Countries', href: '/orbitals/masaq/countries', note: "a card a country: Contact's reading of it, and its labs, research and models", keywords: 'labs contact culture' },
  { group: 'Masaq’ Reach', label: 'Masaq’ Hub', href: '/orbitals/masaq/hub', note: 'the houses that belong to no one country: Hugging Face, BigScience, Masakhane', keywords: 'hugging face bigscience bloom masakhane transnational' },
  ...([['us', 'United States'], ['cn', 'China'], ['fr', 'France'], ['ca', 'Canada'], ['ae', 'United Arab Emirates'], ['au', 'Australia'], ['gb', 'United Kingdom'], ['za', 'South Africa'], ['br', 'Brazil']] as [string, string][]).map(([cc, name]) => ({
    group: 'Masaq’ Reach', label: name, href: `/orbitals/masaq/${cc}/labs`, note: 'its labs, research and models', keywords: `${cc} country labs research models`,
  })),
  { group: 'Masaq’ Reach', label: 'Research', href: '/orbitals/masaq/research', note: 'universities, collectives and national infrastructure' },
  { group: 'Masaq’ Reach', label: 'Models', href: '/orbitals/masaq/models', note: 'every outside model by size band' },
  { group: 'Masaq’ Reach', label: 'Embeddings', href: '/orbitals/masaq/embeddings', note: 'the embeddings ontology' },

  { group: 'Discoveries', label: 'Discoveries', href: '/orbitals/demiton/discoveries', note: 'what our fleet found, and the field’s discoveries on two axes' },
  ...DISCOVERY_DESTS,

  ...TEST_CATEGORIES.map((c) => ({
    group: 'Leaderboard', label: c.label, href: `/leaderboard/${c.key}`,
    note: c.note,
    keywords: `${c.ours} ${c.published}`,
  })),
  { group: 'Leaderboard', label: 'Extra small board', href: '/leaderboard/xsmall', note: 'under 1B' },
  { group: 'Leaderboard', label: 'Small board', href: '/leaderboard/small', note: '1B – 4B' },
  { group: 'Leaderboard', label: 'Medium board', href: '/leaderboard/medium', note: '4B – 32B' },
  { group: 'Leaderboard', label: 'Large board', href: '/leaderboard/large', note: 'above 32B' },
  // the public edition (lib/edition.ts) offers no place it leaves out: no Demiton, no ships, no settings
].filter((d) => !hiddenHere(d.href));

/** The list, filtered by label, note or keywords: places whose label starts with the query first, then
 *  a word of the label, then the label anywhere, then the note; groups stay in their own order, so the
 *  headers never interleave. Pure, so the ranking can be read without a browser. */
export function filterDestinations(dests: Dest[], q: string): Dest[] {
  // underscores and hyphens read as spaces, so "few shot" finds few_shot and "two hop" the two-hop curse
  const norm = (s: string): string => s.toLowerCase().replace(/[_\-·]+/g, ' ');
  const needle = norm(q.trim());
  if (!needle) return dests.filter((d) => !d.searchOnly);
  const words = needle.split(/\s+/).filter(Boolean);
  const score = (d: Dest): number => {
    const label = norm(d.label);
    if (label.startsWith(needle) || (d.key && norm(d.key) === needle)) return 0;
    if (label.split(/[^a-z0-9]+/).some((w) => w.startsWith(needle))) return 1;
    if (label.includes(needle)) return 2;
    const rest = norm(`${d.note || ''} ${d.keywords || ''} ${d.key || ''}`);
    if (rest.includes(needle)) return 3;
    // every word of the query somewhere in the entry, in any order (13 November: a long list is searched by words)
    const all = `${label} ${rest} ${norm(d.group)}`;
    if (words.length > 1 && words.every((w) => all.includes(w))) return 3;
    if (norm(d.group).includes(needle)) return 4;
    return -1;
  };
  const groups = new Map<string, Dest[]>();
  for (const d of dests) {
    if (!groups.has(d.group)) groups.set(d.group, []);
    groups.get(d.group)!.push(d);
  }
  return [...groups.values()].flatMap((list) => list
    .map((d, i) => ({ d, i, s: score(d) }))
    .filter((x) => x.s >= 0)
    .sort((a, b) => a.s - b.s || a.i - b.i)
    .map((x) => x.d));
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [at, setAt] = useState(0);
  const box = useRef<HTMLInputElement | null>(null);

  // ⌘K anywhere opens it; esc closes it; the header's ⌘K button can ask for it by name
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    const onAsk = (): void => setOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('thorp:palette', onAsk);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('thorp:palette', onAsk);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    setQ('');
    setAt(0);
    const t = window.setTimeout(() => box.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  const rows = useMemo(() => filterDestinations(DESTINATIONS, q), [q]);

  const go = (d: Dest | undefined): void => {
    if (!d) return;
    setOpen(false);
    window.location.assign(d.href);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setAt((i) => Math.min(rows.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setAt((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      go(rows[at]);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      setAt((i) => (rows.length ? (i + 1) % rows.length : 0));
    }
  };

  if (!open) return null;
  let group = '';
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="navigate the app"
      style={{ position: 'fixed', inset: 0, zIndex: 120, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh', background: 'rgba(0,0,0,.5)' }}
      onClick={() => setOpen(false)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(640px, 92vw)', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 24px 60px rgba(0,0,0,.4)', overflow: 'hidden' }}
      >
        <input
          ref={box}
          className={fieldCls('')}
          value={q}
          onChange={(e) => { setQ(e.target.value); setAt(0); }}
          onKeyDown={onKeyDown}
          placeholder="Where to? Type a place, a page, a discovery or a trick…"
          aria-label="where to navigate"
          aria-controls="cmdkrows"
          autoComplete="off"
          spellCheck={false}
          style={{ width: '100%', border: 0, borderBottom: '1px solid var(--line)', borderRadius: 0, padding: '12px 14px', fontSize: '1em' }}
        />
        <div id="cmdkrows" role="listbox" aria-label="places" style={{ maxHeight: '52vh', overflowY: 'auto' }}>
          {!rows.length ? <div className="note" style={{ padding: '12px 14px' }}>no place matches “{q.trim()}”</div> : null}
          {rows.map((d, i) => {
            const head = d.group !== group;
            group = d.group;
            return (
              <div key={`${d.group}:${d.href}`}>
                {head ? (
                  <div className="note" style={{ padding: '9px 14px 3px', textTransform: 'uppercase', letterSpacing: '.08em', fontSize: 10 }}>{d.group}</div>
                ) : null}
                <button
                  type="button"
                  role="option"
                  aria-selected={i === at}
                  onMouseEnter={() => setAt(i)}
                  onClick={() => go(d)}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                    padding: head ? '4px 14px 9px' : '9px 14px', border: 0, borderBottom: '1px solid var(--line)',
                    background: i === at ? 'var(--raise)' : 'transparent', color: 'inherit', font: 'inherit',
                  }}
                >
                  <b>{d.label}</b>
                  {d.note ? <span className="note" style={{ display: 'block', marginTop: 2 }}>{d.note}</span> : null}
                </button>
              </div>
            );
          })}
        </div>
        <div className="note" style={{ padding: '8px 14px', display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span>↑↓ choose · ⏎ go · esc close</span>
          <span>{rows.length} of {DESTINATIONS.length}</span>
        </div>
      </div>
    </div>
  );
}
