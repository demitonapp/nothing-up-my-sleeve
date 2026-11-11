# The theme audit: images and content, after the three-layer brief (11 November)

Justin: "can you aduit all the images and content and see what else needs to change to more closely align with
the theme." The brief is three layers — **Risso's ink**, **Drake's voyages**, **the young Culture's universe**.

## 1. The image prompts: clean

- **103 subjects**, every one with a plate on disk (the regeneration finished at 17:54, 96 new plates plus the
  seven done earlier).
- **Zero prompts still name another era** after the twenty rewrites: the Greek harbours, the Chinese junks, the
  Venetian carracks, the Byzantine dromons and the Victorian and Greek scenes are gone from the prompt set.
  A regex sweep over every subject returns one hit, `qwen3-4b`, and it is a false positive: its "captured
  carrack" is a prize ship, which the period allows (Drake took the São Filipe).
- **Two more were found in this audit and rewritten**: `exp-kipling` was drawing a **steamship**, and
  `exp-arc_de_triomphe` was drawing the **Arc de Triomphe in Paris with an electric streetlamp**. Both are
  now in the world — a wooden ship with a cargo of books, and a stone triumphal arch on a headland.

## 2. The images: the world is not showing up

This is the finding that matters. The style clause asks for a trace of the young Culture — a ring of light
where a moon would be, a distant habitat, a silver drone — and **flux usually ignores it**. Where the subject
prompt itself names the trace, it appears (the console's plate, Schi'mint's ring, Masaq' Reach, the shipyard).
Where it does not, the image is plain age-of-sail, and sometimes worse:

- `band-xsmall` (regenerated under the new clause) came back with **electric-looking street lamps along the
  quay** — a period violation, not merely a missing trace.
- The class plates (keel, speller, stylist, Augustus) are strong Risso ink and period ships, but they are
  ships in the dark with no universe behind them.

**What this means**: the Culture layer cannot be left to the style clause. It has to be either
(a) written into every subject prompt, or (b) composited after generation. Option (a) is a mechanical change
to all 103 prompts and a full regeneration; option (b) is a small drawn ring/drone laid into the sky of the
existing plates, which is cheaper, more controllable, and can be done as a post-pass with Pillow.

## 3. Content and copy: one visible string was left, now fixed

- **`Foreign.tsx`** said "a foreign ship in **Zayton**" in the visible header; it now says "in the Reach".
- **`Chat.tsx`'s** chat page intro said "the foreign ships in Zayton"; now Masaq' Reach.
- Stale comments naming Phaleron, Piraeus and Zayton in `harbours.ts`, `Harbours.tsx`, `nav.ts`,
  `Expeditions.tsx` and `shipyard/index.astro` are cleared.
- The three old keys survive only where they must: as aliases (`HARBOUR_ALIASES`, `waters._RENAMED`).

## 4. World names that still fight the theme

The mapping from yesterday kept the classes and the expeditions, and this audit does not overturn that — but
two names are now doing active harm, because the art has to depict them:

| name | what it draws | what it should be |
| --- | --- | --- |
| **The Kipling Expedition** | "Kipling" is a Victorian author; the plate drew a steamship | a ship carrying books, unnamed by its author — or a Culture name |
| **Arc de Triomphe** | a Paris monument; the plate drew the real Arc | a triumphal arch on a headland, or a Culture name for the mark it seeks |

The rest read as missions (The Two-Fact Problem, The Smallest Bridge, First Light, The knockout) and are
untouched. The classes stay as they are: they are hulls and jobs, not places.

## 5. What is left, in order of value

1. **Put the trace into every prompt and regenerate** (or composite it). Without this the harbour and the
   console are in the Culture and the rest of the app is not.
2. **Ban the anachronism explicitly**: a negative clause — "no electric light, no street lamps, lanterns and
   tallow only, no modern masonry" — because `band-xsmall` shows flux will add a gaslit quay given the chance.
3. **Rename the two expeditions** whose names force a real-world scene, then regenerate their plates.
4. **Sweep the remaining names** (Kipling, Ogden, Arc de Triomphe) if you want the world wholly consistent;
   this is the naming question from yesterday, reopened by the art.

## The registry's own note

`thorp/dash/UI.md` and `generate_art.py` now carry the three layers and the standing trace. The trace is in
`STYLE`, which is the weakest place to put it; the audit's recommendation is to move it into the subjects.
