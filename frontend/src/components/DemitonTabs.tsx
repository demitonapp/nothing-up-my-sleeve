// Demiton's own tabs (12 November, Justin: "/orbitals/demiton has to have tabs for the berth, the
// shipyard and also the library"; "expeditions also moves under the demiton orbital"). The four views
// are one orbital's, so the row is shared by the berth, the shipyard, the library and the expeditions.
import { TabNav } from './TabNav';

export type DemitonView = 'overview' | 'berth' | 'shipyard' | 'library' | 'expeditions';

export default function DemitonTabs({ active }: { active: DemitonView }) {
  return (
    <TabNav
      id="demitontabs"
      ariaLabel="Demiton's views"
      items={[
        { key: 'overview', label: 'Overview', href: '/orbitals/demiton', active: active === 'overview' },
        { key: 'berth', label: 'Berth', href: '/orbitals/demiton/berth', active: active === 'berth' },
        { key: 'shipyard', label: 'Shipyard', href: '/shipyard', active: active === 'shipyard' },
        { key: 'library', label: 'Library', href: '/library', active: active === 'library' },
        { key: 'expeditions', label: 'Expeditions', href: '/expeditions', active: active === 'expeditions' },
      ]}
    />
  );
}
