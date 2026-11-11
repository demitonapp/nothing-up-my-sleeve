# Naming the world into the Culture's early days (11 November)

Justin: "the style is rissos, the inspriation is drake and the merchant ships exploring new worlds, the world
is banks early days of the culture"; and "naming must change and art style accordingly", scoped to **world
names only** — the places, the expeditions and the classes — with the app's own furniture (sidebar, panel,
queue, the leaderboard's columns) left as it is.

**Applied, 11 November**: the three places only. Every other name in this document is a proposal and has not
been changed. What the applied rename touched: `thorp/dash/waters.py` (keys, names, abouts, and an alias table
so an old key still resolves), `thorp/dash/server.py` (the shipbuilder defaults and the lanes' display names),
`thorp/foreign.py` (the foreign ships' harbour), the harbour routes in `frontend/src/pages/harbours/[...path].astro`
(the new keys, with the old three kept as addresses that forward), `views/harbours.ts` and
`views/shipbuilder.ts` (the alias map and the builder's key), `Foreign.tsx` and `Expeditions.tsx` (two links
and a mount), and the three art files, regenerated as Orbitals with the old PNGs removed.

## The rule

- **The ship is the age of sail; the universe is the Culture.** A class is a hull you could draw (keel,
  sloop, galleon); the places and the expeditions carry the young Culture's own naming — short, cool,
  slightly amused, as Banks named Orbitals and ships.
- **No name may be a Culture artefact quoted whole.** *Vavatch* was destroyed; *Masaq'* is a later,
  settled Orbital. The early days are unnamed in the books, so these are new names in that register, not
  borrowings.
- **Short where it is a place, wry where it is an expedition.** An Orbital gets four to eight letters; an
  expedition gets a phrase with a straight face.

## The places (3 harbours → Orbitals)

| now | key | proposed | why |
| --- | --- | --- | --- |
| Phaleron | `phaleron` | **Schi'mint** | the first Orbital, where the young Culture trains its crews: a teaching place, not a port |
| Piraeus | `piraeus` | **Vavatch End** | the deep harbour's role: a great construction and fitting Orbital on the edge of the new worlds |
| Zayton | `zayton` | **Masaq' Reach** | the market harbour: the cosmopolitan one, where every civilisation's ships come to trade |

The apostrophes are deliberate: Banks' place names carry them, and they read as *not ours*.

## The classes (6 → the Culture's hulls)

The classes are the one part a reader still has to *picture*, so they stay hulls — but the naming moves from
a ship's parts to the Culture's own hull codes, which is what a GSV/GCU/ROU is to a reader of the books.

| now | proposed | what it is |
| --- | --- | --- |
| keel | **Keel** (kept) | the hull laid down: the 300k's form. The one name that is the physical beginning and needs no gloss |
| pilot | **Pilot** (kept) | the small cutter that goes first: the 1m |
| speller | **Speller** (kept) | reads the alphabet: the alphabet class |
| stylist | **Stylist** (kept) | the prose class |
| paragraph | **Paragraph** (kept) | the chaining class |
| explorer | **Explorer** (kept) | the discovery class |

*Kept, deliberately, and this is the one place I would argue with the brief*: the class names are not
world-building, they are what the ship *does*, and the ladder's art already draws them as vessels a size up
from the last. Renaming them would not make the world more Culture and would make the ladder harder to
read. If you want them moved too, the natural set is the Culture's hull codes — **Keel → GSV**, Pilot →
**GCU**, Speller → **ROU**, Stylist → **MSV**, Paragraph → **LOU**, Explorer → **VFP** — but a reader has to
learn six acronyms.

## The expeditions (17 → the Culture's missions)

| now | key | proposed | why |
| --- | --- | --- | --- |
| The book-value loop | `book_value` | **Reading the Library** | the Culture's own name for what a library is worth |
| First Light | `first_light` | **First Light** (kept) | it is already the moment a ship sees: no better word |
| Laying the keel | `seedling` | **Laying Down** | the hull on the stocks |
| The Magician's Apprentice | `apprentice` | **Apprentice** (kept) | the transplant is still a magician's trick |
| Table Talk | `table_talk` | **Table Talk** (kept) | the conversation at the table |
| The Magician's Apprentice II | `apprentice_2` | **Apprentice II** | |
| The best keel | `best_keel` | **Best Keel** (kept) | |
| The two-fact problem | `two_facts` | **The Two-Fact Problem** (kept) | |
| The card census | `card_census` | **Census** (kept) | |
| The knockout | `knockout` | **Knockout** (kept) | the causal test, not a place |
| Discovering the induction head | `induction` | **Induction** (kept) | |
| Ogden v0.1 | `ogden` | **Ogden v0.1** (kept) | a corpus name, not a world name |
| The Smallest Bridge | `smallest_bridge` | **The Smallest Bridge** (kept) | |
| The logic tutor | `logic_tutor` | **The Tutor** | |
| The two bets | `two_bets` | **Two Bets** (kept) | |
| The Kipling Expedition | `kipling` | **The Kipling** (kept) | |
| Arc de Triomphe | `arc_de_triomphe` | **Arc de Triomphe** (kept) | |

*Read straight, this table says the expeditions barely need renaming* — they are missions, not places, and
a mission called "The Two-Fact Problem" is already a phrase a Culture Mind would tolerate. The world names
that actually grate are the **places** (Greek, Chinese, Levantine ports in a universe with no Greece, China
or Levant) and the **classes**, if you want them moved.

## What the change costs, per name

- **A harbour key** is in `thorp/fleet.py`, `/harbours/<key>`, the harbour art file, and any spec or reading
  that names it: three places, plus a redirect for the old address.
- **An expedition key** is in `fleet.EXPEDITIONS`, its spec labels, `/expeditions/<key>`, `plan` queue lines,
  the store's rows and its art file: a migration, with the old keys kept as aliases so a queued line and a
  saved reading still resolve.
- **A class name** is in the ladder, the art subjects, the leaderboard's class column and every voyage label.

## The recommendation

1. **Do the three places now** — 3 keys, 1 redirect each, 3 art files: cheap, and it is the part of the
   naming that is actually a lie today.
2. **Leave the classes and expeditions as they are** unless you want the six acronyms; they read as missions
   and hulls, not as places in a world.
3. **Regenerate the art once**, after the names are signed.
