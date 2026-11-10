// Governance (UI.md "Governance"), as a client island: the five VSM systems, S3 control and
// acquisition, with the open drawers and book links. The dense tables live in views/governance.ts.

import { useEffect, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { emptyCls, tabCls, tabsCls } from '@/lib/ui';
import { routePath, sectionProps, useApi, useRoute } from '@/lib/useApi';
import { acquisitionHtml, controlHtml, systemsHtml } from '@/scripts/views/governance';

type View = 'systems' | 'control' | 'acquisition';
const viewFrom = (p: string): View => p.startsWith('/governance/control') ? 'control' : p.startsWith('/governance/acquisition') ? 'acquisition' : 'systems';
const openInReader = async (id: string): Promise<void> => {
  const { openBook } = await import('@/lib/reader');
  await openBook(id);
};

export default function Governance() {
  const route = useRoute();
  const [view, setView] = useState<View>('systems');
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => { setView(viewFrom(route)); }, [route]);
  useEffect(() => {
    const onPop = () => setView(viewFrom(routePath()));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const gov = useApi<any>('/api/governance', 30000);
  const exps = useApi<{ key: string; name: string }[]>('/api/expeditions', 60000);
  const acq = useApi<any>(view === 'systems' ? null : '/api/acquisition', 30000);
  const au = useApi<any>(view === 'systems' ? null : '/api/acquisition/audit', 60000);

  const voyageName = Object.fromEntries((exps.data || []).map((x) => [x.key, x.name]));
  const go = (v: View) => {
    setView(v);
    history.pushState(null, '', v === 'systems' ? '/governance' : `/governance/${v}`);
  };

  const html = view === 'systems'
    ? (gov.data ? systemsHtml(gov.data, voyageName, open) : null)
    : view === 'control'
      ? (gov.data && acq.data ? controlHtml(gov.data, acq.data, au.data, open) : null)
      : (acq.data ? acquisitionHtml(acq.data, au.data, open) : null);

  const error = view === 'systems' ? gov.error : view === 'control' ? gov.error || acq.error : acq.error;

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
      <h1>VSM <span className="q">Thorp's rules as Beer's Viable System Model: S5 policy (the identity, Justin's rules), S4 intelligence (the outside world), S3 control (the gate every voyage passes, and the audit), S2 coordination (one GPU, one queue), S1 operations (the expeditions, and acquisition: the books they read). Read-only: a policy is switched on or off by Justin in data/policies.json</span></h1>
      <nav className={tabsCls('line', 'subnav')} data-orientation="horizontal" data-variant="line" id="govnav">
        <a className={tabCls('')} data-state={view === 'systems' ? 'active' : 'inactive'} data-gview="systems" href="/governance" onClick={(e) => { e.preventDefault(); go('systems'); }}>The five systems</a>
        <a className={tabCls('')} data-state={view === 'control' ? 'active' : 'inactive'} data-gview="control" href="/governance/control" onClick={(e) => { e.preventDefault(); go('control'); }}>S3 control</a>
        <a className={tabCls('')} data-state={view === 'acquisition' ? 'active' : 'inactive'} data-gview="acquisition" href="/governance/acquisition" onClick={(e) => { e.preventDefault(); go('acquisition'); }}>Acquisition</a>
      </nav>
      <div className={`gview${view === 'systems' ? ' active' : ''}`} data-gview="systems">
        <p className="s gvintro">The five systems. Each band is one system: its purpose, its code and its live numbers from the audit.</p>
        <div id="govbands">{error ? <div className={emptyCls()}>the audit could not be read: {error}</div> : html ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} /> : <div className={emptyCls()}>reading the audit…</div>}</div>
      </div>
      <div className={`gview${view === 'control' ? ' active' : ''}`} data-gview="control">
        <p className="s gvintro">S3 is control: what lets the operations run on their own without breaking Thorp's identity. For voyages it is the gate every new voyage passes before it reads a page (<span className="mono">vsm.gate</span>, from <span className="mono">train.prepare</span> and the fitout builder); for books it is the intake gate (<span className="mono">acquisition.admit</span>). The audit (S3*) looks again, independently of both.</p>
        <div id="govcontrol">{error ? <div className={emptyCls()}>the gate could not be read: {error}</div> : html ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} /> : <div className={emptyCls()}>reading the gate…</div>}</div>
      </div>
      <div className={`gview${view === 'acquisition' ? ' active' : ''}`} data-gview="acquisition">
        <p className="s gvintro">Acquisition is how books enter Thorp's library: fetched, registered and checked that they clean. Beer's model is recursive, so it is a viable system of its own inside Thorp's S1, with its own five systems (<span className="mono">thorp/acquisition.py</span>). Cleaning happens when a book is read (<span className="mono">thorp/cleaning.py</span>), so the source's own text stays the record.</p>
        <div id="govacq">{error ? <div className={emptyCls()}>acquisition could not be read: {error}</div> : html ? <div onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} /> : <div className={emptyCls()}>reading acquisition…</div>}</div>
      </div>
    </div>
  );
}
