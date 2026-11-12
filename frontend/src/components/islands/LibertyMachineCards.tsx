// The Liberty Machine's overview: its five systems as image cards (12 November, Justin: "http://localhost:4321/orbitals/demiton/liberty-machine should
// have 5 cards with a fal image for each level"; "need pages for each Liberty Machine system"). Each card opens its
// system's own page (/orbitals/demiton/liberty-machine/operations … /orbitals/demiton/liberty-machine/s5). Drawn as Demiton's section cards are (views/harbours.ts, the yard
// plate), with art from backend/thorp/dash/art/generate_art.py LIBERTY_MACHINE_SYSTEMS (liberty-machine-s1 … liberty-machine-s5).

import { cardCls } from '@/lib/ui';
import { LIBERTY_MACHINE_SYSTEMS, libertyMachineHref } from '@/lib/nav';
import { artSrc } from '@/scripts/views/helpers';

const JOBS: Record<string, string> = {
  s1: 'the expeditions and the voyages they sail, and acquisition: the books they read',
  s2: 'one GPU, one queue, two lanes: no two voyages fighting for the helm',
  s3: 'the gate every voyage passes, the money it may spend, and S3*: the audit that looks again',
  s4: 'the outside world and the future: the foreign ships, their readings, the hire market',
  s5: 'who we are: the rules Justin signs, enforced at the gate or left advisory',
};

export function LibertyMachineCards() {
  return (
    <nav className="harbours shipyardgrid demitonyard five libertymachinecards" aria-label="Liberty Machine systems">
      {LIBERTY_MACHINE_SYSTEMS.map((s) => (
        <a key={s.key} className={cardCls(true, 'card harbourcard shipyardcard')} href={libertyMachineHref(s.key)}>
          <img className="cardart ship" src={artSrc(`liberty-machine-${s.key}`)} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} />
          <div className="yardplate">
            <span className="yardnum">{s.label}</span>
            <span className="yardrule" aria-hidden="true" />
            <span className="nm">{s.name}</span>
            <span className="job">{JOBS[s.key]}</span>
            <span className="yardopen">open {s.label} {s.name.toLowerCase()} →</span>
          </div>
        </a>
      ))}
    </nav>
  );
}
