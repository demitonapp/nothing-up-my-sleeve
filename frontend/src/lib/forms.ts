// ---- Forms (UI.md, "Forms"): the pieces every form on the dashboard shares.
import { esc } from './format';

let errSeq = 0;
export function fieldError(el: HTMLElement, message: string): void {
  if (!el) return;
  el.setAttribute('aria-invalid', 'true');
  const id = el.dataset.errId || `ferr${++errSeq}`;
  el.dataset.errId = id;
  let msg = document.getElementById(id);
  if (!msg) {
    msg = document.createElement('div');
    msg.id = id;
    msg.className = 'ferr';
    msg.setAttribute('role', 'alert');
    el.insertAdjacentElement(el.matches('input,select,textarea') ? 'afterend' : 'beforeend', msg);
  }
  msg.innerHTML = esc(message);
  el.setAttribute('aria-describedby', [el.getAttribute('aria-describedby'), id].filter((v): v is string => Boolean(v)).filter((v, i, a) => a.indexOf(v) === i).join(' '));
}
export function clearErrors(root: Document | Element = document): void {
  root.querySelectorAll('[aria-invalid="true"]').forEach((el) => {
    el.removeAttribute('aria-invalid');
    const id = (el as HTMLElement).dataset.errId;
    if (id) {
      document.getElementById(id)?.remove();
      el.setAttribute('aria-describedby', (el.getAttribute('aria-describedby') || '').split(' ').filter((x) => x && x !== id).join(' '));
    }
  });
  root.querySelectorAll('.ferr').forEach((m) => m.remove());
}

export function busy(btn: HTMLButtonElement, text: string): (after?: string) => void {
  if (!btn) return () => {};
  const was = btn.innerHTML;
  const dis = btn.disabled;
  btn.disabled = true;
  btn.setAttribute('aria-busy', 'true');
  btn.textContent = text;
  return (after) => {
    btn.removeAttribute('aria-busy');
    btn.disabled = dis;
    btn.innerHTML = after ?? was;
  };
}

const store = {
  get(k: string): string | null {
    try { return localStorage.getItem(k); } catch { return null; }
  },
  set(k: string, v: string | null): void {
    try { if (v == null || v === '') localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* storage blocked */ }
  },
};
export { store };

function remember(el: HTMLSelectElement | HTMLInputElement): void {
  if (el.dataset.rememberWired) return;
  el.dataset.rememberWired = '1';
  const key = 'thorp.filter.' + el.id;
  const restore = () => {
    const v = store.get(key);
    if (v == null || el.dataset.restored) return;
    if (el.tagName === 'SELECT' && ![...(el as HTMLSelectElement).options].some((o) => o.value === v)) return; // its options aren't in yet
    el.dataset.restored = '1';
    if (el.value !== v) { el.value = v; el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); }
  };
  el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => { if (el.dataset.restored || store.get(key) == null) el.dataset.restored = '1'; store.set(key, el.value); });
  if (el.tagName === 'SELECT') new MutationObserver(restore).observe(el, { childList: true });
  restore();
}
export function filterBars(root: Document | Element = document): void {
  root.querySelectorAll('[data-remember]').forEach((el) => remember(el as HTMLSelectElement | HTMLInputElement));
  root.querySelectorAll('[data-filters]').forEach((bar) => {
    if (bar.querySelector('.freset')) return;
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'freset';
    b.textContent = 'reset';
    b.title = 'every filter here back to all';
    b.onclick = () => bar.querySelectorAll('select, input[type=search], input[type=text]').forEach((el) => {
      const sel = el as HTMLSelectElement | HTMLInputElement;
      const first = el.tagName === 'SELECT' ? ((sel as HTMLSelectElement).options[0] ? (sel as HTMLSelectElement).options[0].value : '') : '';
      if (sel.value !== first) { sel.value = first; sel.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); }
    });
    bar.appendChild(b);
  });
}
