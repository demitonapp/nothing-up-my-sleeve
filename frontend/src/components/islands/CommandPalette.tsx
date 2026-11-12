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
}

/** The places the palette can take you. Grouped in the order below; the top-level ways in come first,
 *  then Demiton's views, the ships, Masaq' Reach, the discoveries and the leaderboard boards. */
export const DESTINATIONS: Dest[] = [
  { group: 'The site', label: 'Orbitals', href: '/orbitals', note: 'Demiton and the trading orbital' },
  { group: 'The site', label: 'Demiton', href: '/orbitals/demiton', note: 'our own orbital, its views and its fleet' },
  { group: 'The site', label: 'Masaq’ Reach', href: '/orbitals/masaq', note: 'the trading orbital' },
  { group: 'The site', label: 'Leaderboard', href: '/leaderboard', note: 'the tests and their boards' },
  { group: 'The site', label: 'Settings', href: '/settings', note: 'storage, the store, the server and the switches' },
  { group: 'The site', label: 'The bet', href: '/bet' },

  { group: 'Demiton', label: 'Shipyard', href: '/shipyard', note: 'the berth, the SOP, the hull sizes and the standard' },
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
    group: 'Demiton', label: `${s.label} ${s.name}`, href: libertyMachineHref(s.key), note: 'a system of the Liberty Machine',
  })),

  { group: 'The ships', label: 'Every ship', href: '/ships', note: 'every ship of our fleet, and every run' },
  { group: 'The ships', label: 'The towing tank · 300k', href: '/ships/300k', keywords: 'smallest class' },
  { group: 'The ships', label: 'The measured mile · 1m', href: '/ships/1m' },
  { group: 'The ships', label: 'The sea trial · 9m', href: '/ships/9m' },
  { group: 'The ships', label: 'The coasting run · 21m', href: '/ships/21m' },
  { group: 'The ships', label: 'The paragraph · 50m', href: '/ships/50m' },
  { group: 'The ships', label: 'Invention · 100m', href: '/ships/100m' },
  { group: 'The ships', label: 'The trader · 350m', href: '/ships/350m', note: 'the largest class' },

  { group: 'Masaq’ Reach', label: 'Labs', href: '/orbitals/masaq/labs', note: 'a card a country: its labs, research and models' },
  ...([['us', 'United States'], ['cn', 'China'], ['fr', 'France'], ['ca', 'Canada'], ['ae', 'United Arab Emirates'], ['au', 'Australia'], ['gb', 'United Kingdom'], ['za', 'South Africa'], ['br', 'Brazil']] as [string, string][]).map(([cc, name]) => ({
    group: 'Masaq’ Reach', label: name, href: `/orbitals/masaq/${cc}/labs`, note: 'its labs, research and models', keywords: `${cc} country labs research models`,
  })),
  { group: 'Masaq’ Reach', label: 'Research', href: '/orbitals/masaq/research', note: 'universities, collectives and national infrastructure' },
  { group: 'Masaq’ Reach', label: 'Models', href: '/orbitals/masaq/models', note: 'every outside model by size band' },
  { group: 'Masaq’ Reach', label: 'Embeddings', href: '/orbitals/masaq/embeddings', note: 'the embeddings ontology' },

  { group: 'Discoveries', label: 'Discoveries', href: '/orbitals/demiton/discoveries', note: 'what our fleet found' },
  { group: 'Discoveries', label: 'Tests', href: '/orbitals/demiton/discoveries/tests', note: 'the four questions, the logic and cause decks' },
  { group: 'Discoveries', label: 'Skills', href: '/orbitals/demiton/discoveries/skills', note: 'the ladder and every trick' },
  { group: 'Discoveries', label: 'Stars', href: '/orbitals/demiton/discoveries/stars', note: 'the heads our ships lit and the sixteen cards' },
  { group: 'Discoveries', label: 'Head kinds', href: '/orbitals/demiton/discoveries/head-kinds', note: 'every kind research has named, the cards beyond the sixteen and the Qwen mapping' },

  ...TEST_CATEGORIES.map((c) => ({
    group: 'Leaderboard', label: c.label, href: `/leaderboard/${c.key}`,
    note: c.note,
    keywords: `${c.ours} ${c.published}`,
  })),
  { group: 'Leaderboard', label: 'Extra small board', href: '/leaderboard/xsmall', note: 'under 1B' },
  { group: 'Leaderboard', label: 'Small board', href: '/leaderboard/small', note: '1B – 4B' },
  { group: 'Leaderboard', label: 'Medium board', href: '/leaderboard/medium', note: '4B – 32B' },
  { group: 'Leaderboard', label: 'Large board', href: '/leaderboard/large', note: 'above 32B' },
];

/** The list, filtered by label, note or keywords: places whose label starts with the query first, then
 *  a word of the label, then the label anywhere, then the note; groups stay in their own order, so the
 *  headers never interleave. Pure, so the ranking can be read without a browser. */
export function filterDestinations(dests: Dest[], q: string): Dest[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return dests;
  const score = (d: Dest): number => {
    const label = d.label.toLowerCase();
    if (label.startsWith(needle)) return 0;
    if (label.split(/[^a-z0-9]+/).some((w) => w.startsWith(needle))) return 1;
    if (label.includes(needle)) return 2;
    if (`${d.note || ''} ${d.keywords || ''}`.toLowerCase().includes(needle)) return 3;
    if (d.group.toLowerCase().includes(needle)) return 4;
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
          placeholder="Where to? Type a place, page or section…"
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
