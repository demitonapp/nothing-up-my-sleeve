// The Liberty Machine (UI.md "Liberty Machine"), as a client island, a way in of its own (12 November, Justin: "need pages for
// each Liberty Machine system and then move it up a level out of expeditions into it's own top level item"). /orbitals/demiton/liberty-machine is
// the overview, the five systems as image cards (LibertyMachineCards.tsx); /orbitals/demiton/liberty-machine/operations … /orbitals/demiton/liberty-machine/policy is one system's own page —
// S1 operations, S2 coordination, S3 control, S4 intelligence, S5 policy — with its band from the audit;
// S3's page carries the gate and the audit, S1's carries acquisition. The dense tables live
// in views/governance.ts. Between a system's band and its detail sits the queue's planning cycle
// (LibertyMachineCycle.tsx): the six steps on every tab, then that system's own part of the turn.

import { useEffect, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { emptyCls } from '@/lib/ui';
import { LIBERTY_MACHINE_SYSTEMS, libertyMachineSystemOf } from '@/lib/nav';
import { routePath, sectionProps, useApi, useRoute } from '@/lib/useApi';
import { acquisitionHtml, controlHtml, systemsHtml } from '@/scripts/views/governance';
import { DronePage, S1Drones } from './DroneFleet';
import { Checkpoints } from './Checkpoints';
import { LibertyMachineCards } from './LibertyMachineCards';
import { LibertyMachineCycle } from './LibertyMachineCycle';
import { S5Feedback } from './S5Feedback';

type View = 's1' | 's2' | 's3' | 's4' | 's5';
const INTRO: Record<View, string> = {
  s1: 'S1 is operations: the expeditions, the ships and the books they read. The band is S1’s live numbers; below it acquisition’s S1 — the intakes and every book’s verdict, newest first — because acquisition is a viable system of its own inside S1.',
  s2: 'S2 is coordination: one GPU, one queue, and no two voyages fighting for the helm. The band is S2’s live numbers; below it acquisition’s S2 — the intake lock, the helm an intake never takes, and the caches — because acquisition runs beside a voyage.',
  s3: 'S3 is control: the gate every new voyage passes before it reads a page, the intake gate for books, and the audit (S3*) that looks again independently. The band is S3’s live numbers; the control detail follows, including acquisition’s S3, its intake gate and its audit.',
  s4: 'S4 is intelligence: the outside world — the foreign ships, their readings on our decks, and the arms the fleet is compared against. Below the band, acquisition’s S4: the sources, the Gutenberg catalogue and the legal ceiling.',
  s5: 'S5 is policy: Nothing up my sleeve’s identity, Justin’s rules, switched on (enforced at the gate) or left advisory in data/policies.json. Above, the feedback the other systems send up; below the band, the envelope the plan is held to and acquisition’s S5: the intake rules that serve the policies.',
};

const openInReader = async (id: string): Promise<void> => {
  const { openBook } = await import('@/lib/reader');
  await openBook(id);
};

export default function Governance() {
  const route = useRoute();
  // null is the overview (/orbitals/demiton/liberty-machine); a system's address is its own page
  const [view, setView] = useState<View | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => { setView(libertyMachineSystemOf(route)); }, [route]);
  useEffect(() => {
    const onPop = () => setView(libertyMachineSystemOf(routePath()));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // a drone's own page is not the system's: it reads /api/drones, not the audit
  const parts = route.split('/').filter(Boolean);
  const at = parts[0] === 'orbitals' && parts[1] === 'demiton' ? 2 : 0;
  const droneKey = parts[at] === 'liberty-machine' && parts[at + 1] === 'operations'
    && ['browser', 'email', 'phone'].includes(parts[at + 2] || '')
    ? parts[at + 2]
    : null;
  const isDrone = droneKey !== null;
  // the overview reads nothing: the audit is a system page's
  const on = view !== null && !isDrone;
  const gov = useApi<any>(on ? '/api/governance' : null, 30000);
  const exps = useApi<{ key: string; name: string }[]>(on ? '/api/expeditions' : null, 60000);
  const acq = useApi<any>(on ? '/api/acquisition' : null, 30000);
  const au = useApi<any>(on ? '/api/acquisition/audit' : null, 60000);

  const voyageName = Object.fromEntries((exps.data || []).map((x) => [x.key, x.name]));

  const band = view && gov.data ? systemsHtml(gov.data, voyageName, open, view.toUpperCase()) : '';
  const control = view === 's3' && gov.data && acq.data && au.data ? controlHtml(gov.data, acq.data, au.data, open) : '';
  const acqReady = Boolean(acq.data) && (view !== 's1' || Boolean(au.data));
  const acqBand = view && view !== 's3' && acqReady ? acquisitionHtml(acq.data, au.data, open, view.toUpperCase()) : '';
  const below = control + acqBand;
  const html = band + below;
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

  if (isDrone) {
    return (
      <div {...sectionProps('governance')}>
        <DronePage drone={droneKey ?? 'browser'} />
      </div>
    );
  }

  if (view === null) {
    return (
      <div {...sectionProps('governance')}>
        <h1>Liberty Machine <span className="q">how Thorp governs itself, as Beer's Viable System Model: five systems, each with a page of its own. Read-only: a policy is switched on or off by Justin</span></h1>
        <LibertyMachineCards />
      </div>
    );
  }
  const sys = LIBERTY_MACHINE_SYSTEMS.find((x) => x.key === view)!;

  return (
    <div {...sectionProps('governance')}>
      <h1>{sys.label} {sys.name} <span className="q">{view === 's5'
        ? "the feedback the other systems send up to S5, sorted for S4; then S5's rules, its live numbers and its part in the queue's planning cycle"
        : "one of the Liberty Machine's five systems: what it does, its live numbers, and its part in the queue's planning cycle"}</span></h1>
      {/* the fleet first (12 November, Justin: "the cards should be the first thing shown in this page"):
          S1's workers, the browser drone, the email drone and the phone drone, before the band's numbers */}
      {view === 's1' ? <S1Drones /> : null}
      {view === 's1' ? <Checkpoints /> : null}
      {/* S5 opens on its feedback (13 November, Justin: "I'd like feedback to be the main UX function"); the rules,
          the band and the envelope follow it */}
      {view === 's5' ? <S5Feedback /> : null}
      <div className="gview active" data-gview={view}>
        <p className="s gvintro">{INTRO[view]}</p>
        <div id="govbands">
          {error && !html ? <div className={emptyCls()}>the Liberty Machine could not be read: {error}</div> : html ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: band }} /> : <div className={emptyCls()}>reading the audit…</div>}
          {/* the queue's planning cycle: the six steps on every tab, then this system's own part of it */}
          <LibertyMachineCycle tab={view.toUpperCase() as 'S1' | 'S2' | 'S3' | 'S4' | 'S5'} />
          {below ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: below }} /> : null}
        </div>
      </div>
    </div>
  );
}
