// /login (13 November): the dashboard's login form on a page of its own, linked from Demiton's page when the
// expeditions and the Liberty Machine are hidden. Logged in, it goes back to `?next=` (a path on this site only).

import { useEffect } from 'react';
import { logOut, useLogin } from '@/lib/login';
import { LoginForm } from '../LoginGate';

const nextPath = (): string => {
  const n = new URLSearchParams(location.search).get('next') || '';
  return n.startsWith('/') && !n.startsWith('//') ? n : '/orbitals/demiton';
};

export default function LoginPage() {
  const login = useLogin();
  const fresh = login?.logged_in;
  useEffect(() => {
    if (fresh && new URLSearchParams(location.search).has('next')) location.replace(nextPath());
  }, [fresh]);
  if (!login) return null;
  if (!login.logged_in) return <LoginForm what="the expeditions and the Liberty Machine" />;
  return (
    <div style={{ maxWidth: 340, margin: '48px auto', display: 'grid', gap: 10, fontSize: 14 }}>
      <span>Logged in as <b>{login.username}</b>.</span>
      <a href={nextPath()} style={{ color: 'var(--accent, #e3b341)' }}>Back to Demiton →</a>
      <button type="button" onClick={() => void logOut()} style={{ justifySelf: 'start', background: 'none', color: 'inherit', border: '1px solid var(--line, #2a313c)', borderRadius: 6, padding: '6px 10px', font: 'inherit', cursor: 'pointer' }}>
        Log out
      </button>
    </div>
  );
}
