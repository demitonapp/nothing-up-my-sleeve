// The section tabs under the header, for a client island. It reads the live address itself, so an
// island that pushes a new path (the size page's canonical address, a discoveries tab, an expedition
// tab) gets the right row and the right active tab without every page wiring it by hand.
import { useEffect, useState } from 'react';
import { routePath } from '@/lib/useApi';
import { sectionNavFor } from '@/lib/nav';
import { TabNav } from './TabNav';

export default function SectionNav() {
  // the first render is the server's, where there is no address to read
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  if (!ready) return null;
  const section = sectionNavFor(routePath());
  // a section with one way in needs no row: the header already says where you are (12 November, the
  // orbitals have no siblings now that the shipyard is inside Demiton and the labs inside Masaq' Reach)
  if (!section || section.items.length < 2) return null;
  return <TabNav items={section.items} id={`${section.key}-nav`} ariaLabel={`${section.label} sections`} />;
}
