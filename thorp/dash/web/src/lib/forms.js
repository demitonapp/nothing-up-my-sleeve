// ---- Forms (UI.md, "Forms"): the pieces every form on the dashboard shares.
// - fieldError(el, message): marks a control (or a block standing for one) invalid, in shadcn's aria-invalid look, with the
//   message beneath it, tied to it by aria-describedby; clearErrors(root) takes every mark off.
// - busy(button, text): the button says what it is doing and takes no second click; it returns the function that restores it.
// - filterBars(): every bar marked data-filters gets a "reset" link, and every control marked data-remember keeps its value
//   per viewer (localStorage, guarded), restored once its options arrive, since many are filled by the script.
import { esc } from './format.js';

let errSeq = 0;
export function fieldError(el, message) {
  if (!el) return;
  el.setAttribute('aria-invalid', 'true');
  const id = el.dataset.errId || `ferr${++errSeq}`;
  el.dataset.errId = id;
  let msg = document.getElementById(id);
  if (!msg) {
    msg = document.createElement('div');
    msg.id = id; msg.className = 'ferr'; msg.setAttribute('role', 'alert');
    el.insertAdjacentElement(el.matches('input,select,textarea') ? 'afterend' : 'beforeend', msg);
  }
  msg.innerHTML = esc(message);
  el.setAttribute('aria-describedby', [el.getAttribute('aria-describedby'), id].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(' '));
}
export function clearErrors(root = document) {
  root.querySelectorAll('[aria-invalid="true"]').forEach(el => {
    el.removeAttribute('aria-invalid');
    const id = el.dataset.errId;
    if (id) { document.getElementById(id)?.remove(); el.setAttribute('aria-describedby', (el.getAttribute('aria-describedby') || '').split(' ').filter(x => x && x !== id).join(' ')); }
  });
  root.querySelectorAll('.ferr').forEach(m => m.remove());
}

export function busy(btn, text) {
  if (!btn) return () => {};
  const was = btn.innerHTML, dis = btn.disabled;
  btn.disabled = true; btn.setAttribute('aria-busy', 'true'); btn.textContent = text;
  return (after) => { btn.removeAttribute('aria-busy'); btn.disabled = dis; btn.innerHTML = after ?? was; };
}

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { if (v == null || v === '') localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } },
};
export { store };

function remember(el) {
  if (el.dataset.rememberWired) return;
  el.dataset.rememberWired = '1';
  const key = 'thorp.filter.' + el.id;
  const restore = () => {
    const v = store.get(key);
    if (v == null || el.dataset.restored) return;
    if (el.tagName === 'SELECT' && ![...el.options].some(o => o.value === v)) return;  // its options aren't in yet
    el.dataset.restored = '1';
    if (el.value !== v) { el.value = v; el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); }
  };
  el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => { if (el.dataset.restored || store.get(key) == null) el.dataset.restored = '1'; store.set(key, el.value); });
  if (el.tagName === 'SELECT') new MutationObserver(restore).observe(el, { childList: true });
  restore();
}
export function filterBars(root = document) {
  root.querySelectorAll('[data-remember]').forEach(remember);
  root.querySelectorAll('[data-filters]').forEach(bar => {
    if (bar.querySelector('.freset')) return;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'freset'; b.textContent = 'reset';
    b.title = 'every filter here back to all';
    b.onclick = () => bar.querySelectorAll('select, input[type=search], input[type=text]').forEach(el => {
      const first = el.tagName === 'SELECT' ? (el.options[0] ? el.options[0].value : '') : '';
      if (el.value !== first) { el.value = first; el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); }
    });
    bar.appendChild(b);
  });
}
