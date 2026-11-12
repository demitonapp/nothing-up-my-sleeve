// Governance's three views (UI.md "Governance"), as typed HTML renderers: the five Liberty Machine bands, S3
// control, and acquisition. The island owns the tab, the open drawers and the events; these are the
// dense read-only tables, kept as pure functions of the payloads so the browser and tests share them.

import { big, esc, fmt, fmtBytes, shortModel } from '../../lib/format';
import { alertCls, btnCls, cardCls, emptyCls, pillCls } from '../../lib/ui';

type Payload = any;

const STATES = ['at sea', 'under way', 'awaiting orders', 'paused', 'in port', 'home'];
const STATE_TONE: Record<string, string> = { 'at sea': 'running', 'under way': 'blue', 'in port': '', home: 'good', paused: 'accent', 'awaiting orders': 'bad' };
const STATE_NOTE: Record<string, string> = {
  'at sea': 'a voyage of it is at sea now', 'under way': 'voyages of it are queued', 'in port': 'planned, nothing queued yet', home: 'done',
  paused: 'paused', 'awaiting orders': 'declared running with nothing at sea or queued: stalled, or done and not closed',
};

const cut = (s: unknown, n = 160): string => { const v = String(s ?? ''); return v.length > n ? v.slice(0, n - 1) + '…' : v; };
const when = (at: unknown): string => esc(String(at || '').replace('T', ' ').slice(5, 16));
const statePill = (st: string | null | undefined, declared?: string | null): string => st
  ? `<span class="${pillCls(STATE_TONE[st] ?? '')}${st === 'awaiting orders' ? ' awaiting' : ''}" title="${esc(STATE_NOTE[st] || st)}${declared && declared !== st ? `; declared ${esc(declared)}` : ''}">${esc(st)}</span>`
  : '';
const govBand = (s: Payload, k: string, live: string): string => `<section class="${cardCls(false, 'panel govband')}" data-sys="${k}"><div class="govhead"><span class="govkey">${k}</span><div><h2>${esc(s.name || '')}</h2><div class="s">${esc(s.purpose || '')}</div></div></div>
    <div class="govchips">${(s.members || []).map((m: string) => `<span class="${pillCls('')} mono govchip">${esc(m)}</span>`).join('')}</div><div class="govlive">${live}</div></section>`;
const enforcedPill = (on: boolean): string => on ? `<span class="${pillCls('good')}">enforced</span>` : `<span class="${pillCls('accent')}">advisory</span>`;
const verdictPill = (v: string): string => `<span class="${pillCls({ admitted: 'good', passed: 'good', refused: 'bad', failed: 'bad', observed: 'blue', unresolved: 'accent', 'would fetch': 'accent' }[v] || '')}">${esc(v || '–')}</span>`;
const howPill = (h: string): string => `<span class="${pillCls({ refused: 'bad', bargain: 'accent', excepted: 'blue' }[h] || '')}">${esc(h)}</span>`;
const govToggle = (open: Set<string>, k: string, label: string, n: number | null): string => `<button class="${btnCls('ghost')}" data-gov="${esc(k)}">${open.has(k) ? '▾' : '▸'} ${label}${n != null ? ` (${n})` : ''}</button>`;

// the cleaning audit (liberty_machine.clean_audit): per store, line breaks before and after the current cleaning
function cleaningTable(c: Payload): string {
  if (!c || !c.libraries) return `<div class="${emptyCls()}">${esc((c && c.error) || 'the cleaning audit has not run yet')}</div>`;
  return `<div class="scroll"><table data-nosort><thead><tr><th>library</th><th>books read</th><th title="words per line break, as the source gives it → as Nothing up my sleeve reads it">words per line break</th><th title="the share of line breaks that fall inside a paragraph (a single newline between two lines of text), raw → cleaned; lower is better">breaks inside a paragraph</th><th>same text every time</th></tr></thead><tbody>${Object.entries(c.libraries).map(([lib, x]: [string, any]) => `<tr><td class="mono">${esc(lib)}</td><td>${x.books}</td><td>${fmt(x.words_per_break[0], 1)} → <b>${fmt(x.words_per_break[1], 1)}</b></td><td>${(100 * x.inside_paragraph_share[0]).toFixed(0)}% → <b>${(100 * x.inside_paragraph_share[1]).toFixed(0)}%</b></td><td>${x.deterministic ? `<span class="${pillCls('good')}">yes</span>` : `<span class="${pillCls('bad')}">no</span>`}</td></tr>`).join('')}</tbody></table></div>
    <p class="s">Cleaning version <b class="mono">${esc(c.version || '')}</b> (thorp/cleaning.py), applied when a book is read; the source's own text stays the record.</p>`;
}
// the library's audit (acquisition.audit, S3*): every registered book against the intake rules, and the rest
function libraryAudit(au: Payload, open: Set<string>, withCleaning = false): string {
  if (!au || !au.audit) return `<div class="${emptyCls()}">${au && au.error ? esc(au.error) : 'reading every book in the library against the rules… (a few seconds; kept warm)'}</div>`;
  const a = au.audit, rules = a.rules || {};
  const rows = Object.entries(rules).map(([k, r]: [string, any]) => {
    const isOpen = open.has('lib:' + k);
    return `<tr><td><b>${esc(k)}</b></td><td>${r.adopted ? `<span class="${pillCls('good')}">serves ${esc(r.serves)}</span>` : `<span class="${pillCls('accent')}">proposed</span>`}</td><td class="${r.breaking && r.adopted ? 'warn' : ''}"><b>${r.breaking}</b> ${Object.entries(r.by_set || {}).map(([s, n]) => `<span class="s">${esc(s)} ${n}</span>`).join(' · ')}</td><td>${r.breaking ? govToggle(open, 'lib:' + k, 'the books', null) : ''}</td></tr>`
      + (isOpen ? `<tr><td colspan="4"><div class="govbooks">${(r.examples || []).map((x: any) => `<div><a href="#" data-book="${esc(x.book)}" class="mono">${esc(x.book)}</a> ${esc(cut(x.title, 70))} <span class="s">${esc(x.why)}</span></div>`).join('')}${r.breaking > (r.examples || []).length ? `<div class="s">and ${r.breaking - r.examples.length} more (python -m thorp.acquisition audit)</div>` : ''}</div></td></tr>` : '');
  }).join('');
  return `<div class="govstats"><div class="govstat"><b>${(a.books || 0).toLocaleString()}</b><span>books in the library</span></div><div class="govstat${a.duplicates.groups ? ' warn' : ' ok'}"><b>${a.duplicates.groups}</b><span>texts registered twice</span></div><div class="govstat${a.missing_files.count ? ' warn' : ' ok'}"><b>${a.missing_files.count}</b><span>registered books with no text on disk</span></div><div class="govstat${a.sample.drifted.length ? ' warn' : ' ok'}"><b>${a.sample.drifted.length}</b><span>of ${a.sample.checked} sampled no longer hash as registered</span></div><div class="govstat${a.sample.boilerplate_left.length ? ' warn' : ' ok'}"><b>${a.sample.boilerplate_left.length}</b><span>of ${a.sample.checked} sampled with a source's boilerplate left</span></div></div>
    <div class="scroll"><table data-nosort><thead><tr><th>rule</th><th></th><th>books in the library breaking it</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
    ${withCleaning ? `<h3 class="govsub">Cleaning</h3>${cleaningTable(a.cleaning)}` : ''}
    <p class="s">Checked ${when(a.checked_at)}; recomputed in the background every five minutes.</p>`;
}

export function systemsHtml(d: Payload, voyageName: Record<string, string>, open: Set<string>, key?: string): string {
  const A = d.audit || {}, sys: Record<string, Payload> = Object.fromEntries((d.systems || []).map((x: any) => [x.key, x]));
  const pol = (A.S3 || {}).policies || {}, stmt = A.S5 || {}, breaking = A.breaking || {};
  const chips = (s: Payload) => (s.members || []).map((m: string) => `<span class="${pillCls('')} mono govchip">${esc(m)}</span>`).join('');
  const band = (k: string, live: string) => { const s = sys[k] || { key: k }; return `<section class="${cardCls(false, 'panel govband')}" data-sys="${k}"><div class="govhead"><span class="govkey">${k}</span><div><h2>${esc(s.name || '')}</h2><div class="s">${esc(s.purpose || '')}</div></div></div>
    <div class="govchips">${chips(s)}</div><div class="govlive">${live}</div></section>`; };
  const enforcedBadge = (on: boolean) => on ? `<span class="${pillCls('good')}">enforced</span>` : `<span class="${pillCls('accent')}">advisory</span>`;
  const s5 = `<table data-nosort><thead><tr><th>policy</th><th>statement</th><th>adopted</th><th></th></tr></thead><tbody>${Object.entries(stmt).map(([k, p]: [string, any]) => `<tr><td><b>${esc(k)}</b></td><td>${esc(p.statement)}</td><td class="s">${esc(p.adopted || '')}</td><td>${enforcedBadge(p.enforced)}</td></tr>`).join('')}</tbody></table>
    <p class="s">A policy is switched on (enforced at the gate, S3) or left advisory by Justin, in s5.policy_switches (<code>thorp s5 switch</code>); not from here.</p>`;
  const s4a = A.S4 || {};
  const s4 = `<div class="govstats"><a href="/leaderboard" class="govstat"><b>${(s4a.competitors || []).length}</b><span>2–4B competitors</span></a><a href="/leaderboard" class="govstat"><b>${(s4a.reference_ladder || []).length}</b><span>models on the reference ladder</span></a></div>
    <div class="s">${(s4a.competitors || []).map((m: string) => `<a href="/leaderboard/competitor/${encodeURIComponent(m)}">${esc(shortModel(m))}</a>`).join(' · ')}</div>`;
  const order = Object.keys(pol).sort((a, b) => (b === 'stores' ? 1 : 0) - (a === 'stores' ? 1 : 0) || (pol[b].queued_runs_breaking_it || 0) - (pol[a].queued_runs_breaking_it || 0));
  const s3 = `<div class="govstats">${order.map((k) => { const p = pol[k], n = p.queued_runs_breaking_it || 0, x = p.queued_runs_excepted || 0; return `<div class="govstat${k === 'stores' ? ' big' : ''}${n ? ' warn' : ' ok'}"><b>${n}</b><span>queued voyage${n === 1 ? '' : 's'} breaking <b>${esc(k)}</b> ${enforcedBadge(p.enforced)}${x ? `<br><b class="govexc">${x}</b> excepted${p.exception ? `: ${esc(p.exception)}` : ''}` : ''}</span></div>`; }).join('')}
      <div class="govstat"><b>${(A.S3 || {}).runs_not_finished ?? '–'}</b><span>voyages started and not finished</span></div></div>
    <p class="s"><a href="/orbitals/demiton/liberty-machine/s3">S3 control →</a> the gate's latest decisions, the bargains and exceptions in force, the intake gate for books, and the audit (S3*)</p>
    ${pol.stores && !pol.stores.enforced && pol.stores.queued_runs_breaking_it ? `<div class="${alertCls('open')}">The stores policy: ${pol.stores.queued_runs_breaking_it} of ${(A.S1 || {}).queued ?? '–'} queued voyages read outside the ship's stores. Whether to enforce it is the decision pending with Justin.</div>` : ''}
    ${order.filter((k) => (breaking[k] || []).length).map((k) => { const isOpen = open.has(k), lines = breaking[k];
      return `<div class="govbreak"><button class="${btnCls('ghost')}" data-gov="${esc(k)}">${isOpen ? '▾' : '▸'} the voyages breaking ${esc(k)} (${pol[k].queued_runs_breaking_it}${lines.length < pol[k].queued_runs_breaking_it ? `, the first ${lines.length} shown` : ''})</button>${isOpen ? `<div class="govlines">${lines.map((l: string) => `<span class="mono">${esc(l)}</span>`).join('')}</div>` : ''}</div>`; }).join('')}`;
  const lints = (A.S2 || {}).queue_lints || [], helmOf = (A.S2 || {}).helm;
  const helmLine = helmOf ? `<div><span class="${pillCls('good')}">at the helm</span> <b>${esc(helmOf.name || '')}</b> <span class="s">${esc(helmOf.kind || '')}${helmOf.pid ? ` · pid ${helmOf.pid}` : ''}${helmOf.since ? ` · since ${esc(String(helmOf.since).slice(11, 16))}` : ''}</span></div>` : '<div class="s">no voyage at the helm (S2 takes it with the next voyage to sail)</div>';
  const s2 = `<div class="govstats"><div class="govstat"><b>${(A.S1 || {}).queued ?? '–'}</b><span>voyages queued</span></div></div>` + helmLine + (lints.length ? `<div class="${alertCls('no')}"><ul class="govlints">${lints.map((l: string) => `<li>${esc(l)}</li>`).join('')}</ul></div>` : `<span class="${pillCls('good')}">no collisions</span> <span class="s">the queue lints clean: one GPU, one queue, no shared file written twice</span>`);
  const vs = (A.S1 || {}).expeditions || (A.S1 || {}).voyages || {}, rank = (st: string) => STATES.indexOf(st);
  const present = STATES.filter((st) => Object.values(vs).includes(st));
  const acq = (A.S1 || {}).acquisition || {}, last = acq.last_intake;
  const s1 = `<div class="govstats">${present.map((st) => `<div class="govstat${st === 'awaiting orders' ? ' warn' : ''}"><b>${Object.values(vs).filter((x) => x === st).length}</b><span>expeditions ${esc(st)}</span></div>`).join('')}</div>
    <div class="govvoy">${Object.entries(vs).sort((a: any, b: any) => rank(a[1]) - rank(b[1])).map(([k, st]: [string, any]) => `<a href="/expeditions/${esc(k)}">${esc(voyageName[k] || k)}</a> ${statePill(st)}`).join('<span class="govsep"></span>')}</div>
    <div class="govacqline"><a href="/orbitals/demiton/liberty-machine/operations"><b>Acquisition →</b></a> <span class="s">the books the voyages read, a viable system of its own: ${acq.books != null ? `${acq.books.toLocaleString()} books in the library, about ${big(acq.tokens_est)} tokens` : 'not read yet'}${acq.taking_in ? ` · <b>taking books in now</b> (${esc(acq.taking_in.id || '')})` : ''} · ${last ? `last intake ${esc(String(last.started || '').replace('T', ' ').slice(5, 16))} from ${esc(last.list || '')}` : 'no intake yet'}</span></div>`;
  const bands: Record<string, string> = {
    S5: band('S5', s5),
    S4: band('S4', s4),
    S3: band('S3', s3),
    S2: band('S2', s2),
    S1: band('S1', s1),
  };
  return key ? (bands[key] || '') : bands.S5 + bands.S4 + bands.S3 + bands.S2 + bands.S1;
}

export function controlHtml(g: Payload, q: Payload, au: Payload, open: Set<string>): string {
  const A = g.audit || {}, S3 = A.S3 || {}, pol = S3.policies || {}, stmt = A.S5 || {};
  const sys3 = (g.systems || []).find((s: any) => s.key === 'S3') || { name: 'Control' };
  const gate = `<section class="${cardCls(false, 'panel')}"><h2>The gate <span class="note">every S5 policy applied to a new voyage before it reads a page. Enforced: the gate refuses a voyage that breaks it; advisory: it is let through and noted. A policy that admits an opt-in lets a voyage through that gives its reason in words (the bargain). A written exception takes voyages out of a policy by name. Counts are over the queue; refused lately, over the gate's last 400 decisions</span></h2>
    <div class="scroll"><table data-nosort><thead><tr><th>policy</th><th>statement</th><th></th><th>opt-in</th><th>queued, breaking it</th><th>excepted</th><th>bargained</th><th>refused lately</th></tr></thead><tbody>${Object.entries(pol).map(([k, p]: [string, any]) => `<tr><td><b>${esc(k)}</b></td><td>${esc((stmt[k] || {}).statement || '')}<div class="s">adopted ${esc((stmt[k] || {}).adopted || '')}</div></td><td>${enforcedPill(p.enforced)}</td><td>${p.opt_in ? 'in words' : '–'}</td><td class="${p.queued_runs_breaking_it ? 'warn' : ''}"><b>${p.queued_runs_breaking_it || 0}</b></td><td>${p.queued_runs_excepted || 0}</td><td>${p.queued_runs_bargained || 0}</td><td class="${p.refused_lately ? 'warn' : ''}">${p.refused_lately || 0}</td></tr>`).join('')}</tbody></table></div></section>`;
  const glog = S3.gate_log || [];
  const spoke = (x: Payload) => (x.decisions || []).map((d: any) => `${howPill(d.how)} <b>${esc(d.policy)}</b> <span class="s">${esc(cut(d.why, 140))}</span>`).join('<br>') || '<span class="s">no policy had anything to say</span>';
  const decisions = `<section class="${cardCls(false, 'panel')}"><h2>Its decisions <span class="note">the gate's latest decisions, newest first (s3.gate_decisions in Postgres): every voyage that sailed and every fitout the builder queued, with each policy that spoke and how. The record began on the evening of 7 November</span></h2>
    ${glog.length ? `<div class="scroll ctlscroll"><table data-nosort><thead><tr><th>when</th><th>voyage</th><th>asked by</th><th>verdict</th><th>the policies that spoke</th></tr></thead><tbody>${glog.map((x: any) => `<tr><td class="s mono">${when(x.at)}</td><td class="mono">${esc(x.name || '')}</td><td class="s">${esc(x.where || '')}</td><td>${verdictPill(x.verdict)}</td><td>${spoke(x)}</td></tr>`).join('')}</tbody></table></div>` : `<div class="${emptyCls()}">no decisions recorded yet: the record begins with the next voyage to sail or the next fitout queued (liberty_machine.gate writes data/gate-log.jsonl)</div>`}</section>`;
  const bg = S3.bargains || {};
  const bargainRows = Object.entries(bg).flatMap(([k, list]: [string, any]) => {
    const by: Record<string, string[]> = {};
    list.forEach((x: any) => (by[x.why] = by[x.why] || []).push(x.voyage));
    return Object.entries(by).map(([why, vs]) => {
      const id = 'bg:' + k + ':' + why.slice(0, 40);
      return `<tr><td><b>${esc(k)}</b></td><td>${esc(why)}</td><td>${govToggle(open, id, `${vs.length} voyage${vs.length === 1 ? '' : 's'}`, null)}${open.has(id) ? `<div class="govlines">${vs.map((v) => `<span class="mono">${esc(v)}</span>`).join('')}</div>` : ''}</td></tr>`;
    });
  }).join('');
  const bargains = `<section class="${cardCls(false, 'panel')}"><h2>The bargains <span class="note">queued voyages that break a policy which admits an opt-in, let through on the reason they give in words (data.opt_in)</span></h2>
    ${bargainRows ? `<div class="scroll"><table data-nosort><thead><tr><th>policy</th><th>the reason given</th><th>voyages</th></tr></thead><tbody>${bargainRows}</tbody></table></div>` : `<div class="${emptyCls()}">no queued voyage opts out of a policy</div>`}</section>`;
  const ex = S3.exceptions || {};
  const exceptions = `<section class="${cardCls(false, 'panel')}"><h2>The exceptions <span class="note">voyages a policy does not govern, by name or pattern, each with its reason, written by Justin in data/policy-exceptions.json</span></h2>
    ${Object.keys(ex).length ? `<div class="scroll"><table data-nosort><thead><tr><th>policy</th><th>reason</th><th>adopted</th><th>by name</th><th>patterns</th></tr></thead><tbody>${Object.entries(ex).map(([k, e]: [string, any]) => `<tr><td><b>${esc(k)}</b></td><td>${esc(e.reason)}</td><td class="s">${esc(e.adopted || '–')}</td><td>${e.runs}</td><td class="mono s">${(e.patterns || []).map(esc).join('<br>') || '–'}</td></tr>`).join('')}</tbody></table></div>` : `<div class="${emptyCls()}">no written exceptions</div>`}</section>`;
  const refusedBy = (q.S3 || {}).refused_by_rule || {}, observedBy = (q.S3 || {}).observed_breaking || {}, libRules = ((au || {}).audit || {}).rules || {};
  const intake = `<section class="${cardCls(false, 'panel')}"><h2>The intake gate <span class="note">acquisition's S3: the rules a book passes before it enters the library. A rule that serves one of Nothing up my sleeve's S5 policies refuses at an intake; a proposed rule is recorded only, until Justin adopts it. Refused: by intakes; observed: books that came in by thorp fetch or a voyage's preparation, logged with the verdict the gate would have given; in the library: the audit, every registered book</span> ${(q.S3 || {}).enforced ? `<span class="${pillCls('good')}">enforced at intakes</span>` : `<span class="${pillCls('accent')}">switched off (data/policies.json)</span>`}</h2>
    <div class="scroll"><table data-nosort><thead><tr><th>rule</th><th>statement</th><th></th><th>checked</th><th>refused</th><th>observed</th><th>in the library</th></tr></thead><tbody>${(q.S5 || []).map((r: any) => `<tr><td><b>${esc(r.key)}</b></td><td>${esc(r.statement)}</td><td>${r.adopted ? `<span class="${pillCls('good')}">serves ${esc(r.serves)}</span>` : `<span class="${pillCls('accent')}">proposed</span>`}</td><td class="s">${esc(r.when)}</td><td>${refusedBy[r.key] || 0}</td><td>${observedBy[r.key] || 0}</td><td class="${(libRules[r.key] || {}).breaking && r.adopted ? 'warn' : ''}">${libRules[r.key] ? libRules[r.key].breaking : '–'}</td></tr>`).join('')}</tbody></table></div>
    <p class="s"><a href="/orbitals/demiton/liberty-machine/operations">Acquisition →</a> its intakes, the log of every book's verdict, the sources and the legal ceiling</p></section>`;
  const audit = `<section class="${cardCls(false, 'panel')}"><h2>The audit (S3*) <span class="note">sporadic and independent of both gates: it reads the books, not the specs. The cleaning audit reads a few books of each store; the library audit reads every registered book against the intake rules</span></h2>
    <h3 class="govsub">Cleaning</h3>${cleaningTable((A['S3*'] || {}).cleaning)}
    <h3 class="govsub">The library</h3>${libraryAudit(au, open)}</section>`;
  return `<section class="${cardCls(false, 'panel govband')}" data-sys="S3"><div class="govhead"><span class="govkey">S3</span><div><h2>${esc(sys3.name || 'Control')}</h2><div class="s">${esc(sys3.purpose || '')}</div></div></div>
      <div class="govstats"><div class="govstat"><b>${Object.values(pol).filter((p: any) => p.enforced).length}</b><span>of ${Object.keys(pol).length} policies enforced</span></div><div class="govstat${Object.values(pol).some((p: any) => p.queued_runs_breaking_it && p.enforced) ? ' warn' : ' ok'}"><b>${Object.values(pol).reduce((n: number, p: any) => n + (p.enforced ? p.queued_runs_breaking_it || 0 : 0), 0)}</b><span>queued voyages an enforced policy would refuse</span></div><div class="govstat"><b>${Object.values(pol).reduce((n: number, p: any) => n + (p.queued_runs_bargained || 0), 0)}</b><span>bargains</span></div><div class="govstat"><b>${glog.length}</b><span>decisions recorded</span></div><div class="govstat${glog.some((x: any) => x.verdict === 'refused') ? ' warn' : ''}"><b>${glog.filter((x: any) => x.verdict === 'refused').length}</b><span>of them refusals</span></div></div></section>
    ${gate}${decisions}<div class="row">${bargains}${exceptions}</div>${intake}${audit}`;
}

export function acquisitionHtml(q: Payload, au: Payload, open: Set<string>, key?: string): string {
  const sys: Record<string, Payload> = Object.fromEntries((q.systems || []).map((x: any) => [x.key, x]));
  const band = (k: string, live: string) => govBand(sys[k] || { key: k }, k, live);
  const s5 = `<div class="scroll"><table data-nosort><thead><tr><th>rule</th><th>statement</th><th>serves</th><th>checked</th></tr></thead><tbody>${(q.S5 || []).map((r: any) => `<tr><td><b>${esc(r.key)}</b></td><td>${esc(r.statement)}</td><td>${r.adopted ? `<span class="${pillCls('good')}">${esc(r.serves)}</span> <span class="s">adopted ${esc(r.policy_adopted || '')}</span>` : `<span class="${pillCls('accent')}">proposed</span> <span class="s">recorded only, until Justin adopts it</span>`}</td><td class="s">${esc(r.when)}</td></tr>`).join('')}</tbody></table></div>
    <p class="s">A rule that serves a policy applies one of Nothing up my sleeve's S5 policies (Governance, S5) to books. A proposed rule is adopted by an entry in DECISIONS.md and a policy in thorp/liberty_machine.py, by Justin; not from here.</p>`;
  const c = (q.S4 || {}).ceiling || {}, share = c.gutenberg_legal_books ? c.fetched_legal_books / c.gutenberg_legal_books : 0;
  const gathered = ((q.S1 || {}).summary || {}).gathered || { books: 0, sources: 0 };
  const srcStatus = (st: string) => `<span class="${pillCls(/^admitted/.test(st) ? 'good' : /^candidate/.test(st) ? 'accent' : '')}">${esc(st)}</span>`;
  const s4 = (c.catalogue ? `<div class="govstats"><div class="govstat big"><b>${(c.gutenberg_legal_books || 0).toLocaleString()}</b><span>Gutenberg books in English that pass the death rule, about ${big(c.gutenberg_legal_tokens_est[0])}–${big(c.gutenberg_legal_tokens_est[1])} tokens</span></div><div class="govstat"><b>${(c.fetched_legal_books || 0).toLocaleString()}</b><span>of them in the library (${(100 * share).toFixed(1)}%), about ${big(c.fetched_legal_tokens_est)} tokens</span></div><div class="govstat"><b>${big(c.reachable_tokens_est['open books'][0])}–${big(c.reachable_tokens_est['open books'][1])}</b><span>tokens reachable from open book sources</span></div><div class="govstat"><b>${big(c.reachable_tokens_est['with Institutional Books'][0])}–${big(c.reachable_tokens_est['with Institutional Books'][1])}</b><span>with Institutional Books, under its terms</span></div></div>
      <div class="acqmeter" title="the legal Gutenberg in the library"><span style="width:${Math.max(0.5, 100 * share).toFixed(1)}%"></span></div>
      <p class="s">Also in the catalogue: ${(c.gutenberg_undated_books || 0).toLocaleString()} with a person who has no dates, ${(c.gutenberg_after_1955_books || 0).toLocaleString()} with someone who died after 1955, ${(c.gutenberg_unsigned_books || 0).toLocaleString()} unsigned. Estimates and sources: <span class="mono">${esc(c.plan || '')}</span>.</p>` : `<div class="${emptyCls()}">no Gutenberg catalogue yet: uv run thorp fetch a list once to download it</div>`)
    + `<div class="scroll"><table data-nosort><thead><tr><th>source</th><th>what it holds</th><th>after Nothing up my sleeve's rule</th><th>licence or terms</th><th>access</th><th></th></tr></thead><tbody>${((q.S4 || {}).sources || []).map((s: any) => `<tr><td><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a></td><td class="s">${esc(s.holds)}</td><td>${esc(s.after_rule)}</td><td class="s">${esc(s.licence)}</td><td class="s">${esc(s.access)}${s.wall ? `<div class="s" title="${esc(s.wall)}"><b>wall:</b> ${esc(cut(s.wall, 140))}</div>` : ''}</td><td>${srcStatus(s.status)}</td></tr>`).join('')}</tbody></table></div>`
    + `<p class="s">The gather pipeline (<span class="mono">thorp gather SOURCE</span>, <span class="mono">thorp/gather.py</span>): ${gathered.books ? `<b>${gathered.books.toLocaleString()}</b> books from ${gathered.sources} scanned sources in this library` : 'nothing from a scanned source yet'}; <span class="mono">thorp gather --list</span> says what can be fetched and <span class="mono">thorp gather --plan N</span> sizes a pilot. Every record goes through the same intake gate above.</p>`;
  const s3a = q.S3 || {}, verdicts = s3a.verdicts || {}, refusedBy = s3a.refused_by_rule || {};
  const s3 = `<div class="govstats">${s3a.enforced ? `<div class="govstat ok"><b>on</b><span>the intake gate refuses on adopted rules</span></div>` : `<div class="govstat warn"><b>off</b><span>the intake gate only records (data/policies.json "intake")</span></div>`}${['admitted', 'refused', 'known', 'observed', 'failed', 'unresolved', 'would fetch'].filter((v) => verdicts[v]).map((v) => `<div class="govstat${v === 'refused' || v === 'failed' ? ' warn' : ''}"><b>${verdicts[v].toLocaleString()}</b><span>${esc(v)}</span></div>`).join('') || `<div class="govstat"><b>0</b><span>verdicts logged</span></div>`}</div>
    ${Object.keys(refusedBy).length ? `<p class="s">Refused at intakes, by rule: ${Object.entries(refusedBy).map(([k, n]) => `<b>${esc(k)}</b> ${n}`).join(' · ')}</p>` : ''}
    <p class="s"><a href="/orbitals/demiton/liberty-machine/s3">S3 control →</a> the intake gate beside the voyage gate</p>
    <h3 class="govsub">The audit (S3*)</h3>${libraryAudit(au, open, true)}`;
  const s2a = q.S2 || {}, inn = s2a.intake, h = s2a.helm;
  const s2 = `${inn ? `<div><span class="${pillCls('good')}">taking books in</span> <b class="mono">${esc(inn.id || '')}</b> <span class="s">${esc(inn.list || '')}${inn.since ? ` · since ${esc(String(inn.since).slice(11, 16))}` : ''}</span></div>` : `<div class="s">no intake taking books in: one at a time, by the intake lock (data/acquisition/intake.lock)</div>`}
    <div class="s">${h ? `The helm is held by <b class="mono">${esc(h.name || '')}</b> (${esc(h.kind || '')}). ` : 'The helm is free. '}Acquisition never takes the helm (it needs the network, not the GPU), so an intake can run beside a voyage at sea. At most one request every ${s2a.request_interval_s ?? 2} s to any one host.</div>
    <div class="scroll"><table data-nosort><thead><tr><th>cache</th><th>files</th><th>size</th></tr></thead><tbody>${(s2a.caches || []).map((x: any) => `<tr><td class="mono">data/texts/${esc(x.source)}/</td><td>${x.files.toLocaleString()}</td><td>${fmtBytes(x.bytes)}</td></tr>`).join('')}</tbody></table></div>`;
  const totals = ((au || {}).audit || {}).totals || [], ins = (q.S1 || {}).intakes || [], log = (q.S1 || {}).log || [];
  const why = (e: any) => [...(e.refused || []).map((x: string) => `<span class="bad">${esc(cut(x, 120))}</span>`), ...(e.notes || []).map((x: string) => `<span class="s">${esc(cut(x, 120))}</span>`), e.error ? `<span class="bad">${esc(cut(e.error, 120))}</span>` : ''].filter(Boolean).join('<br>');
  const s1 = (totals.length ? `<div class="scroll"><table data-nosort><thead><tr><th>source</th><th>set</th><th>books</th><th>size</th><th>about</th></tr></thead><tbody>${totals.map((t: any) => `<tr><td>${esc(t.source)}</td><td>${esc(t.set)}</td><td>${t.books.toLocaleString()}</td><td>${fmtBytes(t.bytes)}</td><td>${big(t.tokens_est)} tokens</td></tr>`).join('')}</tbody></table></div>` : '')
    + `<h3 class="govsub">Intakes</h3>` + (ins.length ? `<div class="scroll"><table data-nosort><thead><tr><th>intake</th><th>list</th><th>started</th><th></th><th>admitted</th><th>known</th><th>refused</th><th>failed</th><th>unresolved</th><th>size</th></tr></thead><tbody>${ins.map((r: any) => `<tr><td class="mono">${esc(r.id)}${r.dry_run ? ` <span class="${pillCls('accent')}">dry run</span>` : ''}</td><td class="mono s">${esc(r.list)}</td><td class="s">${when(r.started)}</td><td>${statePill(r.status === 'taking in' ? 'at sea' : 'home')}</td><td>${r.counts.admitted}${r.dry_run ? ` <span class="s">(${r.counts['would fetch']} would be)</span>` : ''}</td><td>${r.counts.known}</td><td class="${r.counts.refused ? 'warn' : ''}">${r.counts.refused}</td><td class="${r.counts.failed ? 'warn' : ''}">${r.counts.failed}</td><td>${r.counts.unresolved}</td><td>${fmtBytes(r.bytes)}</td></tr>`).join('')}</tbody></table></div>`
      : `<div class="${emptyCls()}">no intake yet: <span class="mono">uv run thorp acquire lists/&lt;list&gt;.csv</span> (add <span class="mono">--dry-run</span> to see the gate's verdicts without fetching)</div>`)
    + `<h3 class="govsub">Every book's verdict, newest first</h3>` + (log.length ? `<div class="scroll ctlscroll"><table data-nosort><thead><tr><th>when</th><th>book</th><th>title</th><th>how</th><th>verdict</th><th>why</th></tr></thead><tbody>${log.map((e: any) => `<tr><td class="s mono">${when(e.at)}</td><td class="mono">${e.book_id ? `<a href="#" data-book="${esc(e.book_id)}">${esc(e.book_id)}</a>` : '–'}</td><td>${esc(cut(e.title, 60))}</td><td class="s">${esc(e.intake || e.how || '')}</td><td>${verdictPill(e.verdict)}</td><td>${why(e) || '<span class="s">–</span>'}</td></tr>`).join('')}</tbody></table></div>`
      : `<div class="${emptyCls()}">no book's verdict logged yet: an intake logs every row, and thorp fetch or a voyage's preparation logs each book new to the library</div>`);
  const bands: Record<string, string> = {
    S5: band('S5', s5),
    S4: band('S4', s4),
    S3: band('S3', s3),
    S2: band('S2', s2),
    S1: band('S1', s1),
  };
  return key ? (bands[key] || '') : `<div class="govbands">${bands.S5}${bands.S4}${bands.S3}${bands.S2}${bands.S1}</div>`;
}
