// Mailboxes for the email drone (12 November, Justin: "need to be able to configure microsoft emails,
// google and protonmail here ... make it the best UX you can"). The three providers do not share an
// auth method, so the page does not pretend they do: Google takes an App Password, ProtonMail takes the
// Bridge password (its IMAP is on this Mac), and Microsoft takes a device-code OAuth sign-in because it
// no longer accepts a password for IMAP.
//
// The panel owns the add/edit flow; every save is tested against the real IMAP and SMTP servers
// (thorp/email_accounts.py) and the result, or the exact error and a provider-specific hint, is shown
// before the mailbox is trusted. Secrets never come back from the API.

import { useEffect, useRef, useState } from 'react';
import { btnCls, cardCls, emptyCls, fieldCls, pillCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';

interface Server {
  host: string;
  port: number;
  ssl: boolean;
  starttls: boolean;
  verify?: boolean;
}

interface Provider {
  key: 'microsoft' | 'google' | 'protonmail';
  label: string;
  detail: string;
  auth: 'oauth' | 'password';
  imap: Server;
  smtp: Server;
  help: string;
  help_url: string;
  domains: string[];
}

interface Account {
  id: string;
  provider: Provider['key'];
  email: string;
  label: string;
  status: 'connected' | 'error' | 'testing' | 'new';
  last_checked?: string | null;
  error?: string | null;
  has_secret?: boolean;
  detail?: { imap?: { messages?: number; folders?: string[] }; smtp?: { ok?: boolean } };
}

interface Payload {
  providers: Provider[];
  accounts: Account[];
  microsoft: { client_id: string; client_id_set: boolean };
}

interface Device {
  client_id: string;
  device_code: string;
  user_code: string;
  verification_uri: string;
  interval: number;
  message?: string;
}

const post = async (url: string, body: unknown): Promise<any> => {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  let j: any = null;
  try { j = await r.json(); } catch { /* an empty body is fine */ }
  if (!r.ok) throw new Error(j?.error || `${r.status} ${r.statusText}`);
  return j;
};

const when = (at?: string | null): string => {
  if (!at) return 'never checked';
  const s = Math.max(0, (Date.now() - new Date(at).getTime()) / 1000);
  if (s < 90) return 'just now';
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
};

/** The provider's mark, drawn rather than shipped: a 2x2 for Microsoft, a four-colour ring for Google,
 *  a violet diamond for Proton. */
function ProviderMark({ p }: { p: Provider['key'] }) {
  if (p === 'microsoft') {
    return (
      <span className="mailmark ms" aria-hidden="true">
        <i /><i /><i /><i />
      </span>
    );
  }
  if (p === 'google') return <span className="mailmark google" aria-hidden="true">G</span>;
  return <span className="mailmark proton" aria-hidden="true">P</span>;
}

const providerLabel = (key: string, providers: Provider[]): string => providers.find((p) => p.key === key)?.label || key;

/** One mailbox's line: its provider, its address, whether the last test passed, and its two actions. */
function AccountRow({ a, providers, onTest, onRemove, busy }: {
  a: Account;
  providers: Provider[];
  onTest: (id: string) => void;
  onRemove: (id: string) => void;
  busy: boolean;
}) {
  const imap = a.detail?.imap;
  const smtp = a.detail?.smtp;
  return (
    <div className={`mailaccount ${a.status}`}>
      <ProviderMark p={a.provider} />
      <div className="mailaccountbody">
        <div className="mailaccounthead">
          <b>{a.email}</b>
          <span className={pillCls(a.status === 'connected' ? 'good' : a.status === 'error' ? 'bad' : 'accent')}>
            {a.status === 'connected' ? 'connected' : a.status === 'error' ? 'error' : a.status}
          </span>
          <span className="s">{providerLabel(a.provider, providers)}</span>
        </div>
        {a.status === 'connected' ? (
          <p className="s">
            INBOX {imap?.messages != null ? `${imap.messages.toLocaleString()} messages` : 'read'}
            {smtp?.ok ? ' · SMTP signed in' : ''} · {when(a.last_checked)}
            {imap?.folders?.length ? ` · ${imap.folders.slice(0, 4).join(', ')}` : ''}
          </p>
        ) : a.error ? (
          <p className="s mailerror">{a.error}</p>
        ) : (
          <p className="s">not tested yet</p>
        )}
      </div>
      <div className="mailaccountactions">
        <button className={btnCls('ghost')} disabled={busy} onClick={() => onTest(a.id)}>test</button>
        <button className={btnCls('ghost')} disabled={busy} onClick={() => onRemove(a.id)}>remove</button>
      </div>
    </div>
  );
}

/** The Add-a-mailbox dialog: provider, the provider's own steps, the fields that provider needs, and
 *  the connection test's verdict. */
function AddMailbox({ providers, microsoft, initial, onClose, onSaved }: {
  providers: Provider[];
  microsoft: Payload['microsoft'];
  initial?: Provider['key'];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [provider, setProvider] = useState<Provider['key']>(initial || 'google');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [label, setLabel] = useState('');
  const [username, setUsername] = useState('');
  const [clientId, setClientId] = useState(microsoft.client_id || '');
  const [advanced, setAdvanced] = useState(false);
  const [imap, setImap] = useState<Server>({ host: '', port: 993, ssl: true, starttls: false, verify: true });
  const [smtp, setSmtp] = useState<Server>({ host: '', port: 587, ssl: false, starttls: true, verify: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [device, setDevice] = useState<Device | null>(null);
  const [msState, setMsState] = useState<string>('');
  const timer = useRef<number | undefined>(undefined);
  const emailRef = useRef<HTMLInputElement>(null);

  const p = providers.find((x) => x.key === provider)!;
  const isMs = provider === 'microsoft';

  // the provider presets fill the advanced fields; a provider switch resets them
  useEffect(() => {
    setImap({ ...p.imap });
    setSmtp({ ...p.smtp });
    setResult(null);
    setError(null);
    setDevice(null);
    setMsState('');
  }, [provider]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    emailRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [onClose]);

  const guess = (value: string) => {
    if (!value.includes('@')) return;
    const domain = value.split('@').pop()!.toLowerCase();
    const found = providers.find((x) => x.domains.some((d) => domain === d || domain.endsWith('.' + d)));
    if (found && found.key !== provider) setProvider(found.key);
  };

  const save = async () => {
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await post('/api/drones/email/accounts', {
        provider, email, password, label: label || undefined, username: username || undefined,
        imap: advanced ? imap : undefined, smtp: advanced ? smtp : undefined,
      });
      setResult(r.result);
      setPassword('');
      onSaved();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const setClient = async () => {
    setBusy(true); setError(null);
    try {
      await post('/api/drones/email/ms/client', { client_id: clientId });
      setMsState('client saved');
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const startMs = async () => {
    setBusy(true); setError(null); setResult(null);
    try {
      if (clientId) await post('/api/drones/email/ms/client', { client_id: clientId });
      const d = (await post('/api/drones/email/ms/start', { client_id: clientId || undefined })) as Device;
      setDevice(d);
      setMsState('waiting for the sign-in');
      const every = Math.max(3, Number(d.interval) || 5) * 1000;
      timer.current = window.setInterval(async () => {
        try {
          const r = await post('/api/drones/email/ms/poll', {
            device_code: d.device_code, client_id: d.client_id, email: email || undefined,
          });
          if (r.state === 'connected') {
            if (timer.current) window.clearInterval(timer.current);
            timer.current = undefined;
            setDevice(null);
            setMsState('connected');
            setResult(r.result);
            onSaved();
          } else if (r.state === 'error') {
            if (timer.current) window.clearInterval(timer.current);
            timer.current = undefined;
            setError(r.error || 'the Microsoft sign-in failed');
            setDevice(null);
          }
        } catch (e) {
          if (timer.current) window.clearInterval(timer.current);
          timer.current = undefined;
          setError(String((e as Error)?.message ?? e));
          setDevice(null);
        }
      }, every);
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const ok = result?.ok;

  return (
    <div className="mailbackdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="maildialog" role="dialog" aria-modal="true" aria-label="Add a mailbox">
        <div className="maildialoghead">
          <h2>Add a mailbox</h2>
          <button className={btnCls('ghost')} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="mailchoices">
          {providers.map((x) => (
            <button
              key={x.key}
              type="button"
              className={`mailchoice${provider === x.key ? ' on' : ''}`}
              onClick={() => setProvider(x.key)}
            >
              <ProviderMark p={x.key} />
              <span><b>{x.label}</b><span className="s">{x.detail}</span></span>
            </button>
          ))}
        </div>

        <div className="mailsteps">
          <b>{p.label} needs:</b>
          <p>{p.help}</p>
          <a href={p.help_url} target="_blank" rel="noreferrer">{isMs ? 'Open the app registrations' : p.key === 'google' ? 'Open Google App Passwords' : 'Open Proton Mail Bridge'} ↗</a>
        </div>

        {isMs && !device ? (
          <>
            <label className="dronelabel" htmlFor="mail-email">Microsoft address</label>
            <input ref={emailRef} id="mail-email" className={fieldCls('w-full')} value={email} placeholder="you@outlook.com"
              onChange={(e) => { setEmail(e.target.value); guess(e.target.value); }} />
            <label className="dronelabel" htmlFor="ms-client">Application (client) id <span className="s">one-time, from the app registration</span></label>
            <div className="mailclientrow">
              <input id="ms-client" className={fieldCls('w-full')} value={clientId} placeholder="00000000-0000-0000-0000-000000000000"
                onChange={(e) => setClientId(e.target.value)} />
              <button className={btnCls('ghost')} disabled={busy || !clientId} onClick={() => void setClient()}>save id</button>
            </div>
            <p className="s">In the app registration: <b>Authentication → Allow public client flows = Yes</b>, and add
              the delegated <b>IMAP.AccessAsUser.All</b> and <b>SMTP.Send</b> permissions (Office 365 Exchange Online).</p>
            <div className="maildialogactions">
              <button className={btnCls('default')} disabled={busy || !clientId || !email} onClick={() => void startMs()}>
                {busy ? 'starting…' : 'Sign in with Microsoft'}
              </button>
            </div>
          </>
        ) : null}

        {device ? (
          <div className="maildevice">
            <p>Enter this code at <a href={device.verification_uri} target="_blank" rel="noreferrer">{device.verification_uri}</a>:</p>
            <div className="mailcode">{device.user_code}</div>
            <button className={btnCls('ghost')} onClick={() => void navigator.clipboard?.writeText(device.user_code)}>copy code</button>
            <p className="s">Sign in as <b>{email}</b>. This panel finishes by itself when Microsoft says yes.</p>
            <span className={pillCls('running')}>{msState || 'waiting…'}</span>
          </div>
        ) : null}

        {!isMs ? (
          <>
            <label className="dronelabel" htmlFor="mail-email">{p.label} address</label>
            <input ref={emailRef} id="mail-email" className={fieldCls('w-full')} value={email}
              placeholder={provider === 'google' ? 'you@gmail.com' : 'you@proton.me'}
              onChange={(e) => { setEmail(e.target.value); guess(e.target.value); }} />
            <label className="dronelabel" htmlFor="mail-secret">
              {provider === 'google' ? 'Google App Password' : 'Proton Mail Bridge password'}
              <span className="s">{provider === 'google' ? '16 characters, spaces are fine' : 'from the Bridge app, not your Proton login'}</span>
            </label>
            <input id="mail-secret" type="password" autoComplete="new-password" className={fieldCls('w-full')} value={password}
              placeholder={provider === 'google' ? 'abcd efgh ijkl mnop' : 'Bridge password'}
              onChange={(e) => setPassword(e.target.value)} />
            <label className="dronelabel" htmlFor="mail-label">name it <span className="s">optional</span></label>
            <input id="mail-label" className={fieldCls('w-full')} value={label} placeholder="Work mail"
              onChange={(e) => setLabel(e.target.value)} />

            <details className="mailadvanced" onToggle={(e) => setAdvanced((e.target as HTMLDetailsElement).open)}>
              <summary>Advanced: server settings</summary>
              <div className="mailservergrid">
                <label className="mailfull">username <span className="s">only if it differs from the address</span>
                  <input className={fieldCls('w-full')} value={username} placeholder={email || 'the address'} onChange={(e) => setUsername(e.target.value)} />
                </label>
                <label>IMAP host<input className={fieldCls('w-full')} value={imap.host} onChange={(e) => setImap({ ...imap, host: e.target.value })} /></label>
                <label>port<input className={fieldCls('w-full')} type="number" value={imap.port} onChange={(e) => setImap({ ...imap, port: Number(e.target.value) })} /></label>
                <label className="mailcheck"><input type="checkbox" checked={imap.ssl} onChange={(e) => setImap({ ...imap, ssl: e.target.checked })} /> SSL</label>
                <label className="mailcheck"><input type="checkbox" checked={imap.starttls} onChange={(e) => setImap({ ...imap, starttls: e.target.checked })} /> STARTTLS</label>
                <label>SMTP host<input className={fieldCls('w-full')} value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })} /></label>
                <label>port<input className={fieldCls('w-full')} type="number" value={smtp.port} onChange={(e) => setSmtp({ ...smtp, port: Number(e.target.value) })} /></label>
                <label className="mailcheck"><input type="checkbox" checked={smtp.starttls} onChange={(e) => setSmtp({ ...smtp, starttls: e.target.checked })} /> STARTTLS</label>
                <label className="mailcheck"><input type="checkbox" checked={smtp.ssl} onChange={(e) => setSmtp({ ...smtp, ssl: e.target.checked })} /> SSL</label>
              </div>
            </details>

            <div className="maildialogactions">
              <button className={btnCls('default')} disabled={busy || !email || !password} onClick={() => void save()}>
                {busy ? 'testing the mailbox…' : 'Test and connect'}
              </button>
              <span className="s">The test signs in, reads INBOX's count and signs in to SMTP. Nothing is sent.</span>
            </div>
          </>
        ) : null}

        {error ? <p className={pillCls('bad')}>{error}</p> : null}
        {result ? (
          <div className={`mailresult ${ok ? 'ok' : 'bad'}`}>
            {ok ? (
              <>
                <b>Connected.</b>
                <p className="s">INBOX {result.imap?.messages?.toLocaleString?.() ?? result.imap?.messages} messages
                  {result.smtp?.ok ? ' · SMTP signed in' : ''} · tested just now.</p>
              </>
            ) : (
              <>
                <b>Not connected.</b>
                <p className="s">{result.error}</p>
                {result.hint ? <p className="s"><b>{result.hint}</b></p> : null}
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** The mailboxes panel on the email drone's page. */
export function EmailAccounts() {
  const [tick, setTick] = useState(0);
  const { data, error } = useApi<Payload>(`/api/drones/email/accounts?t=${tick}`, 15000);
  const [adding, setAdding] = useState(false);
  const [addProvider, setAddProvider] = useState<Provider['key'] | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (error) return <div className={emptyCls()}>the mailboxes could not be read: {error}</div>;
  if (!data) return <div className={emptyCls()}>reading the mailboxes…</div>;

  const providers = data.providers;
  const accounts = data.accounts;

  const test = async (id: string) => {
    setBusy(true); setMsg(null);
    try {
      const r = await post('/api/drones/email/test', { id });
      setMsg(r.result?.ok ? `${r.account?.email} is connected` : r.result?.error || 'the test failed');
      setTick((n) => n + 1);
    } catch (e) {
      setMsg(String((e as Error)?.message ?? e));
    } finally { setBusy(false); }
  };

  const remove = async (id: string) => {
    const { confirmDialog } = await import('@/lib/ui');
    const yes = await confirmDialog('Remove this mailbox from the email drone? The password or token is deleted too.', {
      title: 'Remove mailbox?', ok: 'Remove', cancel: 'Keep',
    });
    if (!yes) return;
    setBusy(true); setMsg(null);
    try {
      await post('/api/drones/email/remove', { id });
      setTick((n) => n + 1);
    } catch (e) {
      setMsg(String((e as Error)?.message ?? e));
    } finally { setBusy(false); }
  };

  return (
    <section className={cardCls(false, 'panel emailaccounts')}>
      <div className="emailaccountshead">
        <div>
          <h2>Mailboxes</h2>
          <p className="s">The email drone reads one of these and drafts replies. Sending stays off until you
            say otherwise; every mailbox is tested against its real IMAP and SMTP servers before it is trusted.</p>
        </div>
        <button className={btnCls('default')} onClick={() => { setAddProvider(undefined); setAdding(true); }}>Add a mailbox</button>
      </div>

      {accounts.length ? (
        <div className="mailaccounts">
          {accounts.map((a) => (
            <AccountRow key={a.id} a={a} providers={providers} onTest={(id) => void test(id)} onRemove={(id) => void remove(id)} busy={busy} />
          ))}
        </div>
      ) : (
        <div className="mailempty">
          <div className="mailprovidergrid">
            {providers.map((p) => (
              <button key={p.key} className="mailprovider" onClick={() => { setAddProvider(p.key); setAdding(true); }}>
                <ProviderMark p={p.key} />
                <b>{p.label}</b>
                <span className="s">{p.detail}</span>
                <span className="mailproviderhow">{p.auth === 'oauth' ? 'sign in with a device code' : p.key === 'google' ? 'app password' : 'Bridge password'}</span>
              </button>
            ))}
          </div>
          <p className="s">No mailboxes yet. Add one above; it is checked before it appears as connected.</p>
        </div>
      )}

      {msg ? <p className={pillCls(msg.includes('connected') ? 'good' : 'bad')}>{msg}</p> : null}

      {adding ? (
        <AddMailbox
          providers={providers}
          microsoft={data.microsoft}
          initial={addProvider}
          onClose={() => setAdding(false)}
          onSaved={() => setTick((n) => n + 1)}
        />
      ) : null}
    </section>
  );
}
