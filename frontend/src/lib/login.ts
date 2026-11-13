// The dashboard's login (13 November, Justin: "this page http://localhost:4321/orbitals/demiton should not show
// expeditions and liberty machine unless i'm logged in. Happy using a username and password for now").
//
// The server holds it (backend/thorp/dash/auth.py): a username and password set with `thorp login set`, and an
// HttpOnly cookie the page never reads. This module only asks the server who is logged in (GET /api/login) and logs in
// or out (POST /api/login, /api/logout); every island that cares listens for LOGIN_EVENT, so logging in on one card
// shows the hidden ones without a reload.

import { useEffect, useState } from 'react';

export interface LoginState {
  logged_in: boolean;
  username: string | null;
  /** false until `thorp login set` has made a login: the form says so instead of asking */
  configured: boolean;
}

export const LOGIN_EVENT = 'thorp:login';

let known: LoginState | null = null;
let asking: Promise<LoginState> | null = null;

const announce = (s: LoginState): LoginState => {
  known = s;
  window.dispatchEvent(new CustomEvent<LoginState>(LOGIN_EVENT, { detail: s }));
  return s;
};

/** Who is logged in, asked once a page and shared by every island. A server that cannot answer is "logged out". */
export function fetchLogin(): Promise<LoginState> {
  if (known) return Promise.resolve(known);
  if (!asking) {
    asking = fetch('/api/login', { credentials: 'same-origin', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : { logged_in: false, username: null, configured: true }))
      .catch(() => ({ logged_in: false, username: null, configured: true }))
      .then((s: LoginState) => announce(s))
      .finally(() => { asking = null; });
  }
  return asking;
}

export async function logIn(username: string, password: string): Promise<LoginState> {
  const r = await fetch('/api/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `the login failed (${r.status})`);
  return announce({ logged_in: true, username: j.username ?? username, configured: true });
}

export async function logOut(): Promise<LoginState> {
  await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' }).catch(() => {});
  return announce({ logged_in: false, username: null, configured: true });
}

/** The login state, null until the server has answered (render nothing private until then). */
export function useLogin(): LoginState | null {
  const [s, setS] = useState<LoginState | null>(known);
  useEffect(() => {
    let live = true;
    fetchLogin().then((v) => live && setS(v));
    const on = (e: Event) => setS((e as CustomEvent<LoginState>).detail);
    window.addEventListener(LOGIN_EVENT, on);
    return () => { live = false; window.removeEventListener(LOGIN_EVENT, on); };
  }, []);
  return s;
}
