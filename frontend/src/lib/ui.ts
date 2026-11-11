/**
 * The bridge from shadcn/ui to the dashboard's string renderers and Astro markup (UI.md, "shadcn").
 *
 * dashboard.js builds most panels as HTML strings, so it cannot render the React primitives in
 * src/components/ui. It takes their class lists from here instead: the same cva variants and class
 * strings (src/components/ui/classes.ts) the React components use, so a pill drawn by a string and a
 * <Badge> drawn by an island look the same. Sizes are the dashboard's compact ones (UI.md, Tokens).
 */
import { badgeVariants } from '@/components/ui/badge-variants';
import { buttonVariants } from '@/components/ui/button-variants';
import { toggleVariants } from '@/components/ui/toggle-variants';
import { tabsListVariants } from '@/components/ui/tabs-variants';
import * as K from '@/components/ui/classes';
import { cn } from '@/lib/utils';

type BadgeVariant = NonNullable<Parameters<typeof badgeVariants>[0]>['variant'];

// the old pill and run-status words, each to its Badge variant
const TONES: Record<string, BadgeVariant> = {
  good: 'good', live: 'good', finished: 'good', done: 'good',
  bad: 'bad', failed: 'bad',
  blue: 'info', running: 'info',
  accent: 'highlight', paused: 'highlight',
  solid: 'solid',
};

/**
 * Pill: a Badge. `tones` is the old pill's modifiers ("good", "running", "" ...): the first one that
 * names a tone picks the variant, and any other word stays on as a class of its own, as before.
 * `pill` stays on too, for the selectors that still name it.
 */
export function pillCls(tones = ''): string {
  const words = String(tones).split(/\s+/).filter(Boolean);
  const tone = words.find(w => w in TONES);
  return cn('pill', badgeVariants({ variant: tone ? TONES[tone] : 'outline' }), 'font-normal', words.filter(w => w !== tone));
}

/** Button. `outline` is the dashboard's one look; `ghost` for a quiet one beside it. */
export function btnCls(variant: 'outline' | 'ghost' | 'default' = 'outline', extra = ''): string {
  return cn(buttonVariants({ variant, size: 'xs' }), 'text-sm font-normal text-muted-foreground hover:text-primary', extra);
}

/** Toggle, one of a group (a ToggleGroup item): selected when it carries data-state="on". */
export function toggleCls(extra = ''): string {
  return cn(toggleVariants({ variant: 'outline', size: 'sm' }), 'h-7 text-sm font-normal text-muted-foreground no-underline',
    'data-[state=on]:border-primary data-[state=on]:text-primary', extra);
}

// fields keep the browser's own controls (the script reads .value and listens for change), in the
// Input / NativeSelect look; scheme-dark gives the native dropdown and picker the dark theme
const FIELD = 'h-7 w-auto px-2 py-0 text-sm scheme-dark';

/** Input (text, number, search). */
export const fieldCls = (extra = ''): string => cn(K.INPUT, K.INPUT_FOCUS, FIELD, extra);

/** NativeSelect, without its wrapper: the browser's own arrow instead of the icon. */
export const selectCls = (extra = ''): string => cn(K.SELECT, FIELD, 'appearance-auto pr-1 bg-background', extra);

/** Checkbox, as a native one in the Checkbox colours. */
export const checkCls = (extra = ''): string => cn('size-3.5 cursor-pointer accent-primary align-middle', extra);

/** Slider, as a native range in the Slider colours. */
export const rangeCls = (extra = ''): string => cn('h-1.5 cursor-pointer accent-primary', extra);

/** Table, stamped onto every table by DataTable (src/lib/datatable.js). */
export const tableCls = {
  table: cn(K.TABLE, 'text-md tabular-nums'),
  head: K.TABLE_HEAD,
  body: K.TABLE_BODY,
  row: cn(K.TABLE_ROW, 'hover:bg-transparent'),
  th: cn(K.TABLE_HEAD_CELL, 'h-8 text-sm font-medium text-muted-foreground whitespace-normal'),
  td: cn(K.TABLE_CELL, 'px-2 py-1.5 whitespace-normal'),
};

/** Tabs: a nav of hash links. `line` for a page's own tabs under its title; the default for the header. */
export function tabsCls(variant: 'default' | 'line' = 'default', extra = ''): string {
  return cn('group/tabs', tabsListVariants({ variant }), 'h-8 max-w-full min-w-0 flex-wrap', variant === 'line' && 'h-auto justify-start', extra);
}
/** One tab: active when it carries data-state="active" (setTab below). */
export const tabCls = (extra = ''): string =>
  cn(K.TABS_TRIGGER, 'flex-none px-2.5 text-sm font-normal no-underline uppercase tracking-[.06em] text-muted-foreground hover:text-primary data-[state=active]:text-primary', extra);
/** Marks one tab of a nav active, as Radix Tabs does: data-state and aria-current. */
export function setTab(a: Element, on: boolean): void {
  a.classList.toggle('active', on);
  a.setAttribute('data-state', on ? 'active' : 'inactive');
  if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
}

/** Card: a panel or a card that opens something (`link`). */
export const cardCls = (link = false, extra = ''): string =>
  cn(K.CARD, 'min-w-0 gap-2 rounded-lg px-4 py-3.5 shadow-none text-foreground no-underline',
    link && 'cursor-pointer transition-colors hover:border-primary focus-visible:border-primary focus-visible:outline-none', extra);

/** Breadcrumb link: a back link or a crumb in a page title. */
export const crumbCls = (extra = ''): string =>
  cn(K.BREADCRUMB_LINK, 'mr-2 text-base font-normal tracking-normal normal-case text-muted-foreground no-underline hover:text-primary', extra);

/** Empty: why nothing is there and what fills it. `cell` for one inside a table cell. */
export const emptyCls = (cell = false): string =>
  cell ? cn('empty', K.EMPTY_DESCRIPTION, 'py-6 text-center')
    : cn('empty', K.EMPTY, K.EMPTY_DESCRIPTION, 'col-span-full block p-6 md:p-8');  // block: the message is one line of text, not a stack

/** HoverCard content (the ⓘ help); Tooltip content (a one-line hover, as on the RunGrid). */
export const hoverCardCls = cn(K.HOVER_CARD_CONTENT, 'w-72 p-3 text-sm leading-normal font-normal normal-case tracking-normal text-left whitespace-normal');
export const tooltipCls = cn(K.TOOLTIP_CONTENT, 'text-sm pointer-events-none');

/** Alert: a verdict, the ledger's reading. `tone` is open (muted), yes (good) or no (bad). */
export function alertCls(tone = 'open', extra = ''): string {
  const t: Record<string, string> = { yes: 'border-good text-good', no: 'border-bad text-bad', open: 'text-muted-foreground' };
  return cn('verdict', 'relative w-full rounded-lg border bg-card px-3 py-2 text-lg', t[tone] ?? t.open, tone, extra);
}

/**
 * AlertDialog, for a question that must be answered before going on (in place of confirm()).
 * A native <dialog> gives the focus trap and Escape; the look is AlertDialog's. Resolves true on
 * the confirming button, false on Cancel, Escape or a click outside.
 */
export function confirmDialog(message: string, { title = 'Are you sure?', ok = 'Continue', cancel = 'Cancel' } = {}): Promise<boolean> {
  return new Promise(resolve => {
    const d = document.createElement('dialog');
    d.className = cn(K.ALERT_DIALOG_CONTENT, 'm-auto max-w-[min(32rem,calc(100%-2rem))] p-0 text-foreground backdrop:bg-black/60');
    d.setAttribute('aria-labelledby', 'cdtitle');
    d.innerHTML = `<div class="grid gap-4 p-5"><div class="flex flex-col gap-2"><h2 id="cdtitle" class="text-lg font-semibold"></h2><p class="text-sm text-muted-foreground"></p></div>
      <div class="flex justify-end gap-2"><button value="no" class="${btnCls('outline')}"></button><button value="yes" class="${cn(buttonVariants({ variant: 'default', size: 'xs' }), 'text-sm')}"></button></div></div>`;
    d.querySelector('h2')!.textContent = title;
    d.querySelector('p')!.textContent = message;
    const [no, yes] = d.querySelectorAll('button');
    no.textContent = cancel; yes.textContent = ok;
    const done = (v: boolean) => { d.close(); d.remove(); resolve(v); };
    no.onclick = () => done(false);
    yes.onclick = () => done(true);
    d.addEventListener('cancel', e => { e.preventDefault(); done(false); });
    d.addEventListener('click', e => { if (e.target === d) done(false); });
    document.body.appendChild(d);
    d.showModal();
    yes.focus();
  });
}
