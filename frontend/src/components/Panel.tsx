/**
 * Panel (UI.md, Layout): a titled box with an optional note saying how to read it, built from
 * shadcn's Card. Rendered by Astro at build time (no client JS), so the script can still fill the
 * children by id as it fills a hand-written `section.panel`.
 */
import type { ReactNode } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export function Panel({ title, note, id, className, children }:
  { title?: ReactNode; note?: ReactNode; id?: string; className?: string; children?: ReactNode }) {
  return (
    <Card id={id} className={cn('min-w-0 gap-2 rounded-lg px-3.5 py-3 shadow-none', className)}>
      {title && (
        <CardHeader className="px-0">
          <CardTitle className="text-[length:var(--fs-md)] font-semibold tracking-[.06em] text-muted-foreground uppercase">
            {title}
            {note && <span className="ml-2 font-normal tracking-normal normal-case">{note}</span>}
          </CardTitle>
        </CardHeader>
      )}
      <CardContent className="px-0">{children}</CardContent>
    </Card>
  );
}
