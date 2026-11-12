// The VSM (UI.md "VSM"), as a client island, a way in of its own (12 November, Justin: "need pages for
// each vsm system and then move it up a level out of expeditions into it's own top level item"). /vsm is
// the overview, the five systems as image cards (VsmCards.tsx); /vsm/s1 … /vsm/s5 is one system's own page —
// S1 operations, S2 coordination, S3 control, S4 intelligence, S5 policy — with its band from the audit;
// S3's page carries the gate and the audit, S1's carries acquisition. The dense tables live
// in views/governance.ts.

import { useEffect, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { emptyCls } from '@/lib/ui';
import { VSM_SYSTEMS, vsmSystemOf } from '@/lib/nav';
import { routePath, sectionProps, useApi, useRoute } from '@/lib/useApi';
import { acquisitionHtml, controlHtml, systemsHtml } from '@/scripts/views/governance';
import SectionNav from '../SectionNav';
import { VsmCards } from './VsmCards';

type View = 's1' | 's2' | 's3' | 's4' | 's5';
const INTRO: Record<View, string> = {
  s1: 'S1 is operations: the expeditions, the ships and the books they read. The band is S1’s live numbers; below it acquisition’s S1 — the intakes and every book’s verdict, newest first — because acquisition is a viable system of its own inside S1.',
  s2: 'S2 is coordination: one GPU, one queue, and no two voyages fighting for the helm. The band is S2’s live numbers; below it acquisition’s S2 — the intake lock, the helm an intake never takes, and the caches — because acquisition runs beside a voyage.',
  s3: 'S3 is control: the gate every new voyage passes before it reads a page, the intake gate for books, and the audit (S3*) that looks again independently. The band is S3’s live numbers; the control detail follows, including acquisition’s S3, its intake gate and its audit.',
  s4: 'S4 is intelligence: the outside world — the foreign ships, their readings on our decks, and the arms the fleet is compared against. Below the band, acquisition’s S4: the sources, the Gutenberg catalogue and the legal ceiling.',
  s5: 'S5 is policy: Nothing up my sleeve’s identity, Justin’s rules, switched on (enforced at the gate) or left advisory in data/policies.json. Below the band, acquisition’s S5: the intake rules that serve the policies.',
};

const openInReader = async (id: string): Promise<void> => {
  const { openBook } = await import('@/lib/reader');
  await openBook(id);
};

export default function Governance() {
  const route = useRoute();
  // null is the overview (/vsm); a system's address is its own page
  const [view, setView] = useState<View | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => { setView(vsmSystemOf(route)); }, [route]);
  useEffect(() => {
    const onPop = () => setView(vsmSystemOf(routePath()));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // the overview reads nothing: the audit is a system page's
  const on = view !== null;
  const gov = useApi<any>(on ? '/api/governance' : null, 30000);
  const exps = useApi<{ key: string; name: string }[]>(on ? '/api/expeditions' : null, 60000);
  const acq = useApi<any>(on ? '/api/acquisition' : null, 30000);
  const au = useApi<any>(on ? '/api/acquisition/audit' : null, 60000);

  const voyageName = Object.fromEntries((exps.data || []).map((x) => [x.key, x.name]));

  const band = view && gov.data ? systemsHtml(gov.data, voyageName, open, view.toUpperCase()) : '';
  const control = view === 's3' && gov.data && acq.data && au.data ? controlHtml(gov.data, acq.data, au.data, open) : '';
  const acqReady = Boolean(acq.data) && (view !== 's1' || Boolean(au.data));
  const acqBand = view && view !== 's3' && acqReady ? acquisitionHtml(acq.data, au.data, open, view.toUpperCase()) : '';
  const html = band + control + acqBand;
  const error = gov.error || acq.error || (view === 's1' || view === 's3' ? au.error : null);

  const onClick = (e: ReactMouseEvent) => {
    const t = e.target as HTMLElement;
    const g = t.closest('[data-gov]') as HTMLElement | null;
    if (g) {
      e.preventDefault();
      const k = g.dataset.gov!;
      setOpen((prev) => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n; });
      return;
    }
    const b = t.closest('a[data-book]') as HTMLElement | null;
    if (b) { e.preventDefault(); void openInReader(b.dataset.book!); }
  };

  if (view === null) {
    return (
      <div {...sectionProps('governance')}>
        <SectionNav />
        <h1>VSM <span className="q">how Thorp governs itself, as Beer's Viable System Model: five systems, each with a page of its own. Read-only: a policy is switched on or off by Justin</span></h1>
        <VsmCards />
      </div>
    );
  }
  const sys = VSM_SYSTEMS.find((x) => x.key === view)!;

  return (
    <div {...sectionProps('governance')}>
      <SectionNav />
      <h1>{sys.label} {sys.name} <span className="q">one of the VSM's five systems: what it does, and its live numbers</span></h1>
      <div className="gview active" data-gview={view}>
        <p className="s gvintro">{INTRO[view]}</p>
        <div id="govbands">
          {error && !html ? <div className={emptyCls()}>the VSM could not be read: {error}</div> : html ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} /> : <div className={emptyCls()}>reading the audit…</div>}
        </div>
      </div>
    </div>
  );
}
