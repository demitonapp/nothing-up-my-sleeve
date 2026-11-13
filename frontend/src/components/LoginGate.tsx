// What only a logged-in browser sees (lib/login.ts): the expeditions and the Liberty Machine. Logged out, the page shows
// the login form in their place; until the server has said who is logged in, it shows nothing, so a private page never
// flashes up first.

import { useState, type ReactNode } from 'react';
import { logIn, useLogin } from '@/lib/login';

const muted = { color: 'var(--muted, #8b949e)' } as const;
const field = {
  width: '100%', background: 'var(--bg, #0e1116)', color: 'inherit', border: '1px solid var(--line, #2a313c)',
  borderRadius: 6, padding: '7px 9px', font: 'inherit',
} as const;

/** The username and password form. `what` names what it opens, in a few words ("the expeditions"). */
export function LoginForm({ what }: { what: string }) {
  const login = useLogin();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try { await logIn(username.trim(), password); setPassword(''); } catch (x) { setErr(String((x as Error)?.message ?? x)); } finally { setBusy(false); }
  };

  return (
    <form
      onSubmit={send}
      aria-label="Log in"
      style={{
        maxWidth: 340, margin: '48px auto', display: 'grid', gap: 10, fontSize: 14, padding: 18,
        background: 'var(--panel, #161b22)', border: '1px solid var(--line, #2a313c)', borderRadius: 8,
      }}
    >
      <b style={{ fontSize: 16 }}>Log in</b>
      <span style={muted}>to see {what}.</span>
      {login && !login.configured ? (
        <span style={muted}>No login has been set yet. In a terminal: <span className="mono">uv run --project backend thorp login set</span></span>
      ) : null}
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ ...muted, fontSize: 12 }}>Username</span>
        <input name="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required style={field} />
      </label>
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ ...muted, fontSize: 12 }}>Password</span>
        <input name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required style={field} />
      </label>
      {err ? <span role="alert" style={{ color: 'var(--bad, #f85149)', fontSize: 13 }}>{err}</span> : null}
      <button
        type="submit"
        disabled={busy}
        style={{ background: 'var(--accent, #e3b341)', color: '#111', border: 0, borderRadius: 6, padding: '8px 10px', font: 'inherit', fontWeight: 600, cursor: 'pointer' }}
      >
        {busy ? 'Logging in…' : 'Log in'}
      </button>
    </form>
  );
}

/** Its children for a logged-in browser, the login form for anyone else. */
export default function LoginGate({ what, children }: { what: string; children: ReactNode }) {
  const login = useLogin();
  if (!login) return null;
  return login.logged_in ? <>{children}</> : <LoginForm what={what} />;
}
