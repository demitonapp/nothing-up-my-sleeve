// The VSM (UI.md "VSM"), as a client island: the five systems as five sub-tabs — S1 operations,
// S2 coordination, S3 control, S4 intelligence, S5 policy — each with its band from the audit;
// the S3 tab carries the gate and the audit, the S1 tab carries acquisition. The dense tables live
// in views/governance.ts.

import { useEffect, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { emptyCls, tabCls, tabsCls } from '@/lib/ui';
import { routePath, sectionProps, useApi, useRoute } from '@/lib/useApi';
import { acquisitionHtml, controlHtml, systemsHtml } from '@/scripts/views/governance';

type View = 's1' | 's2' | 's3' | 's4' | 's5';
const viewFrom = (p: string): View => {
  const m = /^\/vsm\/(s[1-5])\b/.exec(p);
  if (m) return m[1] as View;
  if (p.startsWith('/vsm/control')) return 's3';
  if (p.startsWith('/vsm/acquisition')) return 's1';
  return 's1';
};
const TABS: { view: View; label: string }[] = [
  { view: 's1', label: 'S1 Operations' },
  { view: 's2', label: 'S2 Coordination' },
  { view: 's3', label: 'S3 Control' },
  { view: 's4', label: 'S4 Intelligence' },
  { view: 's5', label: 'S5 Policy' },
];
const INTRO: Record<View, string> = {
  s1: 'S1 is operations: the expeditions, the ships and the books they read. The band is S1’s live numbers; below it acquisition’s S1 — the intakes and every book’s verdict, newest first — because acquisition is a viable system of its own inside S1.',
  s2: 'S2 is coordination: one GPU, one queue, and no two voyages fighting for the helm. The band is S2’s live numbers; below it acquisition’s S2 — the intake lock, the helm an intake never takes, and the caches — because acquisition runs beside a voyage.',
  s3: 'S3 is control: the gate every new voyage passes before it reads a page, the intake gate for books, and the audit (S3*) that looks again independently. The band is S3’s live numbers; the control detail follows, including acquisition’s S3, its intake gate and its audit.',
  s4: 'S4 is intelligence: the outside world — the foreign ships, their readings on our decks, and the arms the fleet is compared against. Below the band, acquisition’s S4: the sources, the Gutenberg catalogue and the legal ceiling.',
  s5: 'S5 is policy: Nothing up my sleeve’s identity, Justin’s rules, switched on (enforced at the gate) or left advisory in data/policies.json. Below the band, acquisition’s S5: the intake rules that serve the policies.',
};
const hrefOf = (v: View): string => (v === 's1' ? '/vsm' : `/vsm/${v}`);

const openInReader = async (id: string): Promise<void> => {
  const { openBook } = await import('@/lib/reader');
  await openBook(id);
};

export default function Governance() {
  const route = useRoute();
  const [view, setView] = useState<View>('s1');
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => { setView(viewFrom(route)); }, [route]);
  useEffect(() => {
    const onPop = () => setView(viewFrom(routePath()));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const gov = useApi<any>('/api/governance', 30000);
  const exps = useApi<{ key: string; name: string }[]>('/api/expeditions', 60000);
  const acq = useApi<any>('/api/acquisition', 30000);
  const au = useApi<any>('/api/acquisition/audit', 60000);

  const voyageName = Object.fromEntries((exps.data || []).map((x) => [x.key, x.name]));
  const go = (v: View) => {
    setView(v);
    history.pushState(null, '', hrefOf(v));
  };

  const band = gov.data ? systemsHtml(gov.data, voyageName, open, view.toUpperCase()) : '';
  const control = view === 's3' && gov.data && acq.data && au.data ? controlHtml(gov.data, acq.data, au.data, open) : '';
  const acqReady = Boolean(acq.data) && (view !== 's1' || Boolean(au.data));
  const acqBand = view !== 's3' && acqReady ? acquisitionHtml(acq.data, au.data, open, view.toUpperCase()) : '';
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

  return (
    <div {...sectionProps('governance')}>
      <h1>VSM <span className="q">Nothing up my sleeve's rules as Beer's Viable System Model, in five systems: S1 operations (the expeditions, and acquisition: the books they read), S2 coordination (one GPU, one queue), S3 control (the gate every voyage passes, and the audit), S4 intelligence (the outside world) and S5 policy (the identity, Justin's rules). Read-only: a policy is switched on or off by Justin in data/policies.json</span></h1>
      <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="vnav">
        <a className={tabCls('')} data-state="inactive" data-vtab="overview" href="/expeditions">Overview</a>
        <a className={tabCls('')} data-state="inactive" data-vtab="queue" href="/expeditions/queue">Queue</a>
        <a className={tabCls('')} data-state="inactive" data-vtab="expeditions" href="/expeditions/plans">Plans</a>
        <a className={tabCls('')} data-state="active" data-vtab="vsm" href="/vsm">VSM</a>
      </nav>
      <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="govnav">
        {TABS.map((t) => (
          <a key={t.view} className={tabCls('')} data-state={view === t.view ? 'active' : 'inactive'} data-gview={t.view} href={hrefOf(t.view)}
            onClick={(e) => { e.preventDefault(); go(t.view); }}>{t.label}</a>
        ))}
      </nav>
      <div className="gview active" data-gview={view}>
        <p className="s gvintro">{INTRO[view]}</p>
        <div id="govbands">
          {error && !html ? <div className={emptyCls()}>the VSM could not be read: {error}</div> : html ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} /> : <div className={emptyCls()}>reading the audit…</div>}
        </div>
      </div>
    </div>
  );
}
