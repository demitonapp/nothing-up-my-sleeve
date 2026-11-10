// One ship's page (UI.md "Ship"), shared helpers: the header's parts, the stages list and the library
// aboard. Pure renderers (no charts, no document) so the server-rendered island can import them; the
// chart panels are the already-typed views/ship.ts, imported at run time by the island.

import { big, esc, fmt, get } from '../../lib/format';
import { alertCls, emptyCls, pillCls, toggleCls } from '../../lib/ui';
import { modelHash, route } from '../router';
import { shipHash } from '../router';
import type { Route } from '../router';

type Payload = any;

export interface ShipAddress {
  key: string | null;
  sailing: string | null;
  tab: string;
}

export const isShipPage = (path: string): boolean => route(path.replace(/^#/, '')).page === 'ship';

export const shipAddress = (path: string): ShipAddress => {
  const rt: Route = route(path.replace(/^#/, ''));
  if (rt.page !== 'ship') return { key: null, sailing: null, tab: 'betting' };
  return { key: (rt.ship as string | null) ?? null, sailing: (rt.sailing as string | null) ?? null, tab: (rt.stab as string) || 'betting' };
};

export interface ShipChoice { ship: Payload | null; run: Payload | null }

/** Resolve the address against the ledger: a ship key (or an older run name/id) and one of its sailings
 *  (the latest when none is named). Mirrors the monolith's shipRun, minus its module state. */
export function chooseShip(ships: Payload[] | null, runs: Payload[] | null, addr: ShipAddress, selected?: string | null): ShipChoice {
  const rs = Array.isArray(runs) ? runs : [];
  const sh = Array.isArray(ships) ? ships : [];
  const ship = sh.find((x) => x.key === addr.key) || null;
  if (ship) {
    const sail = ship.sailings.find((x: any) => x.name === addr.sailing || x.run_id === addr.sailing) || ship.sailings[ship.sailings.length - 1];
    return { ship, run: rs.find((r) => r.run_id === sail.run_id) || null };
  }
  let run: Payload | null = null;
  if (addr.key) run = rs.find((r) => r.name === addr.key || r.run_id === addr.key) || rs.find((r) => r.run_id.startsWith(addr.key!)) || null;
  else run = rs.find((r) => r.run_id === selected) || rs.find((r) => r.status === 'running' && r.name && !r.name.startsWith('smoke')) || rs[0] || null;
  return { ship: run && run.ship_key ? sh.find((x) => x.key === run!.ship_key) || null : null, run };
}

export interface ShipHeader {
  classText: string;
  classHref: string | null;
  name: string;
  fitout: string;
  tags: string;
  sailings: string;
  statShip: string;
  status: string;
}

export function shipHeader(rung: Payload | null, ship: Payload | null, run: Payload | null, key: string | null, tab: string, expeditions: Record<string, string>): ShipHeader {
  const preset = ship ? ship.preset : run && run.preset;
  const cls = preset && rung;
  const sails = ship ? ship.sailings : run ? [{ run_id: run.run_id, name: run.name, seed: run.seed, status: run.status }] : [];
  return {
    classText: cls ? `${cls.preset} · ${cls.name}` : preset || '',
    classHref: cls ? modelHash(cls) : null,
    name: ship ? ship.name : run ? (run.ship || run.name || run.run_id.slice(0, 12)) : `no ship called ${key}`,
    fitout: ship ? ship.subtitle : '',
    tags: ship ? (ship.archived ? `<span class="${pillCls('')}" title="fitted out before 7 November, 06:40">First Fleet · archived</span>` : `<span class="${pillCls('blue')}">in service</span>`)
      + (ship.expedition ? ` <a class="${pillCls('accent')}" href="/expeditions/${esc(ship.expedition)}">${esc(expeditions[ship.expedition] || ship.expedition)}</a>` : '') : '',
    sailings: sails.map((x: any) => `<a class="${toggleCls('sailing')}" data-state="${run && x.run_id === run.run_id ? 'on' : 'off'}" href="${ship ? shipHash(ship.key, x.name, tab) : shipHash(x.name, null, tab)}"
      title="${esc(x.label || x.name)}" data-rid="${esc(x.run_id || '')}">seed <b>${x.seed ?? '–'}</b> ${esc(x.name)} · ${esc((x.status || '').split(':')[0])}${x.ft_en != null ? ` · ${fmt(x.ft_en)}` : ''}</a>`).join(''),
    statShip: ship ? ship.name : run ? (run.ship || run.name || run.run_id.slice(0, 12)) : '',
    status: run ? (run.status || '').split(':')[0] : '',
  };
}

export function stageListHtml(st: any[] | null): { hidden: boolean; rows: string } {
  if (!st || !st.length) return { hidden: true, rows: '' };
  return {
    hidden: false,
    rows: st.map((s: any) => `<tr><td>${s.index + 1}</td><td><b>${esc(s.name)}</b></td>
      <td>${esc(String(s.recipe || '–').replace('lists/', '').replace('.csv', ''))}</td><td>${s.passes ?? '–'}</td><td>${s.first_step}–${s.last_step}</td><td>${big(s.tokens)}</td></tr>`).join(''),
  };
}

const WHERE_TONE: Record<string, string> = { 'the ship\'s stores': 'good', 'outside the stores': 'bad' };

export function aboardHtml(d: Payload | null): { hidden: boolean; html: string } {
  if (!d || d.error || !d.libraries) return { hidden: true, html: '' };
  return {
    hidden: false,
    html: `<div class="ovq">${d.where ? `<span class="${pillCls(WHERE_TONE[d.where] || '')}">${esc(d.where)}</span> ` : ''}<b>${d.books ?? '–'}</b> books · about <b>${big(d.tokens)}</b> tokens${d.recorded ? '' : ` <span class="s" title="this voyage sailed before the library aboard was recorded (16:40), so it is worked out from its spec; the lists may have changed since">(worked out from its spec)</span>`}</div>
      <div class="scroll"><table data-nosort><thead><tr><th>library</th><th>stage</th><th>where</th><th>books</th><th>hash</th></tr></thead><tbody>${d.libraries.map((l: any) => `<tr><td><a href="/library" data-lib="${esc(l.path)}"><b>${esc(l.name || l.path)}</b></a><div class="s mono">${esc(l.path)}</div></td>
        <td>${esc(l.stage || '–')}</td><td><span class="${pillCls(WHERE_TONE[l.where] || '')}">${esc(l.where || '')}</span></td><td>${l.books ?? '–'}</td><td class="mono s">${esc((l.sha1 || '').slice(0, 10))}</td></tr>`).join('')}</tbody></table></div>
      ${d.opt_in ? `<div class="${alertCls('open')}">opted out of the stores: ${esc(d.opt_in)}</div>` : ''}
      ${(d.refused || []).length ? `<div class="s">refused: ${d.refused.map((r: string) => `<span class="mono">${esc(r)}</span>`).join(', ')}</div>` : ''}`,
  };
}

export const loadAboard = async (runId: string): Promise<{ hidden: boolean; html: string }> => {
  try { return aboardHtml(await get('/api/voyage/' + encodeURIComponent(runId) + '/library')); }
  catch { return { hidden: true, html: '' }; }
};

export const emptyText = (text: string): string => `<div class="${emptyCls()}">${text}</div>`;
