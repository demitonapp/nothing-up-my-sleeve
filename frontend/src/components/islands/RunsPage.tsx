// Every ship ever launched (UI.md "Runs"; /ships/all), as a client island: one row per voyage on the
// ledger, a row opening its ship. The table's renderer is views/ship.ts, loaded at run time.

import { useEffect, useState } from 'react';
import { cardCls, crumbCls, emptyCls } from '@/lib/ui';
import { sectionProps, useApi, useRoute } from '@/lib/useApi';
import { route } from '@/scripts/router';
import { shipHash } from '@/scripts/router';
import SectionNav from '../SectionNav';

export const isRunsPage = (path: string): boolean => route(path.replace(/^#/, '')).page === 'runs-section';

export default function RunsPage() {
  const route = useRoute();
  const [path, setPath] = useState('/');

  useEffect(() => { setPath(route); }, [route]);
  const mine = isRunsPage(path);
  const runs = useApi<any[]>('/api/runs', 5000, mine);
  const ladder = useApi<any>('/api/ladder', 120000, mine);

  useEffect(() => {
    const read = (): void => setPath(location.hash && location.hash.startsWith('#/') ? location.hash.slice(1) : location.pathname);
    read();
    const onPop = (): void => read();
    window.addEventListener('popstate', onPop);
    window.addEventListener('hashchange', onPop);
    return () => { window.removeEventListener('popstate', onPop); window.removeEventListener('hashchange', onPop); };
  }, []);

  useEffect(() => {
    if (!mine || !runs.data) return;
    const ledger = runs.data;
    let live = true;
    const goShip = (id: string): void => {
      const lr = ((ladder.data && ladder.data.runs) || []).find((x: any) => x.run_id === id || x.name === id);
      location.href = lr && lr.ship_key ? shipHash(lr.ship_key, lr.name) : shipHash(lr ? lr.name : id);
    };
    (async () => {
      const { runsTable } = await import('@/scripts/views/ship');
      if (live) runsTable(ledger, null, goShip);
    })();
    return () => { live = false; };
  }, [mine, runs.data, ladder.data]);

  if (!mine) return null;
  return (
    <div {...sectionProps('runs-section')}>
      <SectionNav />
      <h1><a className={crumbCls('back')} href="/harbours">← harbours</a> Every ship <span className="q">every voyage on the ledger, of every size; open one to see it sail</span></h1>
      <section className={cardCls(false, 'panel')}>
        <div className="scroll">
          <table id="runs" className="clickable">
            <thead><tr><th>ship</th><th>name</th><th>voyage</th><th>size</th><th>seed</th><th>status</th><th>tokens</th><th>minutes</th><th>hole-card bpb mean</th><th>started</th></tr></thead>
            <tbody />
          </table>
        </div>
      </section>
      {runs.error ? <div className={emptyCls()}>the ledger could not be read: {runs.error}</div> : null}
    </div>
  );
}
