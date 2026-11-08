"""The crowns deck (2026-11-08, Justin: "Who is the Queen of England depends on things ... what time period,
what version of england, who is asking, someone from the monarchy or someone from the peasantry ... the head was
disputed vociferously"; "Yes, pre-register"): does a model's answer to a disputed question move with the asker's
standpoint? Writes lists/tricks/crowns.csv.

Every item is an invented kingdom with two claimants and an asker. The first premise is the record (who holds
whom king, by what standpoint); the second gives the asker's standpoint; neither alone answers "So to Pim, the
king of Brell is". The words are invented (make_logic_deck.nonce_words, checked against the lexicon), so no
history supplies the answer; both claimants are in the record, so copying cannot decide; half the items name
the answer's claim last, so recency cannot decide either. Four kinds of standpoint, from the musing:

- side (the disputed head: Stephen or Matilda): the Vorn crowned Tal and the Mesk crowned Odo; Pim is one of the Mesk
- time (what time period): Tal was king of Brell before the drask and Odo after it; Pim lived in Brell after the drask
- place (what version of England): in Skalk they hold Tal is king and in Drum they hold Odo; Pim lives in Drum
- station (the monarchy or the peasantry): at the court they hold Tal is king and in the fields Odo; Pim works in the fields

Variants, scored as the logic deck's are (thorp.evaluators.logic.score_deck):
- `both`, `first`, `second`, `swapped`, `padded`, `one_hop`: as the logic deck; the padded premise is another
  person of the rival's standpoint, naming that standpoint twice (the bridge card's distractor)
- `flip`: the record with the asker's standpoint turned to the other claimant's, and the answer turned with it;
  a model that ignores the standpoint reads `both` and `flip` with opposite signs
- `ask_disputed`, `ask_settled`: "Q: Who is the king of Brell?\\nA:" after a disputed record and after a settled
  one (both standpoints for one king, the other named as his steward, so the same names are there to copy);
  the idea "That depends on whom you ask." against a flat answer. The ask-back reading is the first less the second.

Columns as the logic deck's: item, relation (crowns-side, crowns-time, crowns-place, crowns-station), variant,
prompt, frame, idea, rival, bridge (the asker's standpoint word), distractor (the padded premise's), answer_word.
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from make_logic_deck import FILLER, nonce_words  # noqa: E402

from thorp.paths import ROUTER as ROOT  # noqa: E402

KINDS = ("side", "time", "place", "station")
HEDGE = "That depends on whom you ask."


def _cap(w: str) -> str:
    return w[:1].upper() + w[1:]


def _kind_sentences(kind: str, w: dict, ans: str, riv: str, ans_last: bool) -> dict:
    """The record, the asker's standpoint (for the answer and, flipped, for the rival), the padded premise and
    the settled record, for one kind. `w` holds the item's invented words; ans and riv are the two claimants."""
    king, pim, dax = w["kingdom"], w["asker"], w["other"]
    a_side, r_side = w["ours"], w["theirs"]  # the answer's standpoint word, the rival's
    if kind == "side":
        claim = {ans: f"the {a_side} crowned {ans}", riv: f"the {r_side} crowned {riv}"}
        stand = lambda s: f"{pim} is one of the {s}."  # noqa: E731
        pad = f"{dax} is one of the {r_side}, and the {r_side} ride at night."
        settled = f"In {king} the {r_side} crowned {riv}, and the {a_side} crowned {riv} too; {ans} is his steward."
        record = "In {k} {c1}, and {c2}."
    elif kind == "time":
        a_side, r_side = "after", "before"
        if (w["n"] // 2) % 2:  # half the items ask the earlier king, crossed with which claim comes last
            a_side, r_side = "before", "after"
        ev = w["event"]
        claim = {ans: f"{ans} was king {a_side} the {ev}", riv: f"{riv} was king {r_side} the {ev}"}
        stand = lambda s: f"{pim} lived in {king} {s} the {ev}."  # noqa: E731
        pad = f"{dax} lived in {king} {r_side} the {ev}, and {r_side} the {ev} the winters were long."
        settled = f"In {king}, {riv} was king before the {ev} and after it; {ans} was his steward."
        record = "In {k}, {c1}, and {c2}."
    elif kind == "place":
        claim = {ans: f"in {a_side} they hold that {ans} is king", riv: f"in {r_side} they hold that {riv} is king"}
        stand = lambda s: f"{pim} lives in {s}."  # noqa: E731
        pad = f"{dax} lives in {r_side}, and {r_side} is cold."
        settled = f"In {king}, in {r_side} and in {a_side} alike, they hold that {riv} is king; {ans} is his steward."
        record = "In {k}, {c1}, and {c2}."
    else:  # station: the court or the fields, crossed with which claim comes last
        at = {"the court": "at the court", "the fields": "in the fields"}
        a_side, r_side = ("the fields", "the court") if (w["n"] // 2) % 2 == 0 else ("the court", "the fields")
        claim = {ans: f"{at[a_side]} they hold that {ans} is king", riv: f"{at[r_side]} they hold that {riv} is king"}
        stand = lambda s: f"{pim} works {at[s]}."  # noqa: E731
        pad = f"{dax} works {at[r_side]}, and {r_side} {'is' if r_side == 'the court' else 'are'} busy."
        settled = f"In {king}, at the court and in the fields alike, they hold that {riv} is king; {ans} is his steward."
        record = "In {k}, {c1}, and {c2}."
    c1, c2 = (claim[riv], claim[ans]) if ans_last else (claim[ans], claim[riv])
    return {
        "record": record.format(k=king, c1=c1, c2=c2),
        "stand": stand(a_side),
        "stand_flip": stand(r_side),
        "pad": pad,
        "settled": settled,
        "bridge": a_side,
        "distractor": r_side,
        "one_hop": (
            f"To {pim}, {ans} is king of {king}, and to {dax}, {riv} is."
            if not ans_last
            else f"To {dax}, {riv} is king of {king}, and to {pim}, {ans} is."
        ),
    }


def build(items: int = 40, seed: int = 1141) -> list[dict]:
    """`items` items, the four kinds in turn (so 40 gives ten of each)."""
    rng = random.Random(seed)
    words = nonce_words(8 * items + 40, rng)
    rows = []
    for i in range(items):
        kind = KINDS[i % len(KINDS)]
        n = i // len(KINDS)  # the item's number within its kind
        w = {
            "kingdom": _cap(words.pop()),
            "asker": _cap(words.pop()),
            "other": _cap(words.pop()),
            "ours": _cap(words.pop()),
            "theirs": _cap(words.pop()),
            "event": words.pop(),
            "n": n,
        }
        ans, riv = _cap(words.pop()), _cap(words.pop())
        ans_last = n % 2 == 1
        s = _kind_sentences(kind, w, ans, riv, ans_last)
        king, pim = w["kingdom"], w["asker"]
        frame = f"So to {pim}, the king of {king} is"
        ask = f"Q: Who is the king of {king}?\nA:"
        flat = f"The king of {king} is {riv if n % 2 == 0 else ans}."
        base = {
            "item": f"crowns-{kind}-{n}",
            "relation": f"crowns-{kind}",
            "bridge": s["bridge"],
            "distractor": s["distractor"],
            "answer_word": ans,
        }
        for variant, pre, fr, idea, rival in (
            ("both", f"{s['record']} {s['stand']}", frame, ans, riv),
            ("first", f"{s['record']} {FILLER}", frame, ans, riv),
            ("second", f"{FILLER} {s['stand']}", frame, ans, riv),
            ("swapped", f"{s['stand']} {s['record']}", frame, ans, riv),
            ("padded", f"{s['record']} {s['stand']} {s['pad']}", frame, ans, riv),
            ("one_hop", f"{s['one_hop']} {FILLER}", frame, ans, riv),
            ("flip", f"{s['record']} {s['stand_flip']}", frame, riv, ans),
            ("ask_disputed", f"{s['record']} {FILLER}", ask, HEDGE, flat),
            ("ask_settled", f"{s['settled']} {FILLER}", ask, HEDGE, f"The king of {king} is {riv}."),
        ):
            rows.append({**base, "variant": variant, "pre": pre, "frame": fr, "idea": idea, "rival": rival})
    return rows


COLS = ["item", "relation", "variant", "prompt", "frame", "idea", "rival", "bridge", "distractor", "answer_word"]


def main(items: int = 40, seed: int = 1141, out: str = "crowns.csv") -> None:
    rows = build(items, seed)
    p = ROOT / "lists" / "tricks" / out
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({**{k: r.get(k, "") for k in COLS}, "prompt": f"{r['pre']} {r['frame']}"})
    print(len(rows), "rows,", len({r["item"] for r in rows}), "items ->", p)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]), int(a[1]), a[2]) if a else main()
