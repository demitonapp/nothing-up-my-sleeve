// One row of tabs for the client islands: the section tabs (SectionNav) and a page's own tabs
// (a size's Overview/Goals, a ship's books, a competitor's Chaining/Tests). The classes and
// data-state are the same as Tabs.astro's, so a link tab and a button tab look and behave alike
// (UI.md, "Navigation").
import type { ReactNode } from 'react';
import { tabCls, tabsCls } from '@/lib/ui';

export interface NavTab {
  key: string;
  label: ReactNode;
  href?: string;
  active: boolean;
  title?: string;
  hidden?: boolean;
  onClick?: () => void;
  data?: Record<string, string>;
}

interface Props {
  items: NavTab[];
  variant?: 'default' | 'line';
  id?: string;
  className?: string;
  ariaLabel?: string;
  /** True when the row switches panels in place (buttons), false when it is a set of addresses. */
  tablist?: boolean;
}

export function TabNav({ items, variant = 'line', id, className = 'subnav', ariaLabel, tablist = false }: Props) {
  const cls = tabCls('');
  return (
    <nav
      className={tabsCls(variant, className)}
      data-orientation="horizontal"
      data-variant={variant}
      id={id}
      aria-label={ariaLabel}
      role={tablist ? 'tablist' : undefined}
    >
      {items.map((t) => t.href ? (
        <a
          key={t.key}
          className={cls}
          data-state={t.active ? 'active' : 'inactive'}
          data-nav={t.key}
          href={t.href}
          title={t.title}
          hidden={t.hidden}
          aria-current={t.active ? 'page' : undefined}
          onClick={t.onClick ? (e) => { e.preventDefault(); t.onClick!(); } : undefined}
          {...(t.data ?? {})}
        >{t.label}</a>
      ) : (
        <button
          key={t.key}
          type="button"
          role="tab"
          aria-selected={t.active}
          className={`${cls} bg-transparent [font-family:inherit]`}
          data-state={t.active ? 'active' : 'inactive'}
          data-nav={t.key}
          title={t.title}
          hidden={t.hidden}
          onClick={t.onClick}
          {...(t.data ?? {})}
        >{t.label}</button>
      ))}
    </nav>
  );
}
