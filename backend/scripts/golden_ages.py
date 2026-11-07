"""Draft the content experiment's shelves from the Gutenberg catalogue (2026-11-06, see DECISIONS).

Four curated shelves (Greek polis, Islamic golden age, continental Renaissance in translation, and
books about those ages) plus three random draws, all English, all passing the legal checks: every
person in the Authors field has a death year and died by 1955; every translator, editor or adapter
was born in 1760 or later. Children's retellings, periodicals and the held-out books are excluded.
Writes lists/content-<shelf>-draft.csv with a `work` column (a work counts once across translations
and volumes, for the one-third cap) and adds the chosen ids to lists/overrides.csv.
Usage: uv run python scripts/golden_ages.py
"""

from __future__ import annotations

import csv
import random
import re

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)
from thorp.sources import gutenberg as g

PERSON = re.compile(
    r"([^;]+?),\s*(?:(\d{1,4})\??\s*(BCE)?|active[^;-]*)?\s*-\s*(\d{1,4})\??\s*(BCE)?"
)
CHILD = re.compile(
    r"juvenile|children|fairy tales from|for boys|for girls|stories from|best-known tales|princess badoura|sindbad|cats'",
    re.I,
)
PERIODICAL = re.compile(
    r"magazine|journal|review|punch|gazette|weekly|monthly|index of|catalog", re.I
)

# (shelf, work key, author pattern, title pattern) -- a title pattern of None takes every title
GREEK = [
    ("plato", r"\bPlato\b", None),
    ("xenophon", r"\bXenophon\b", None),
    ("aeschylus", r"\bAeschylus\b", None),
    ("sophocles", r"\bSophocles\b", None),
    ("euripides", r"\bEuripides\b", None),
    ("aristophanes", r"\bAristophanes\b", None),
    ("aristotle", r"\bAristotle\b", None),
    ("demosthenes", r"\bDemosthenes\b", None),
    ("lysias", r"\bLysias\b", None),
    ("hippocrates", r"\bHippocrates\b", None),
    ("herodotus", r"\bHerodotus\b", None),
    ("pindar", r"\bPindar\b", None),
    ("isocrates", r"\bIsocrates\b", None),
]
ISLAMIC = [
    ("koran", None, r"\bKoran\b|Qur'an"),
    ("nights", None, r"Thousand Nights|Thousand and One Nights|Arabian Nights|Supplemental Nights"),
    ("rumi", r"Jalal al-Din Rumi", None),
    ("jami", r"\bJami\b", None),
    ("khayyam", r"Omar Khayyam", None),
    ("persian-literature", None, r"^The Persian Literature"),
    ("ghazzali", r"Ghazzali", None),
    ("sadi", r"^Sadi\b|; Sadi\b", None),
    ("hafiz", r"fi", None),  # Hafiz is matched by id below
    ("avicenna", r"Avicenna", None),
    ("firdausi", r"Firdaws", None),
]
RENAISSANCE = [
    ("machiavelli", r"Machiavelli", None),
    ("castiglione", r"Castiglione", None),
    ("vasari", r"Vasari", None),
    ("cellini", r"Cellini", None),
    ("boccaccio", r"Boccaccio", None),
    ("petrarch", r"Petrarca", None),
    ("erasmus", r"Erasmus", None),
    ("more", r"More, Thomas, Saint", None),
    ("leonardo", r"Leonardo, da Vinci", None),
    ("galileo", r"Galilei", None),
    ("cervantes", r"Cervantes", None),
    ("guicciardini", r"Guicciardini", None),
    ("bruno", r"Bruno, Giordano", None),
    ("campanella", r"Campanella", None),
    ("aretino", r"Aretino", None),
]
ABOUT = [
    ("grote", r"Grote, George", None),
    ("mahaffy", r"Mahaffy", None),
    ("jebb", r"Jebb, Richard", None),
    ("dickinson", r"Dickinson, G\. Lowes", r"Greek"),
    ("pater", r"Pater, Walter", r"Renaissance|Plato|Greek"),
    (
        "symonds",
        r"Symonds, John Addington",
        r"Renaissance|Greek|Italy|Italian|Michelangelo|Boccaccio",
    ),
    ("burckhardt", r"Burckhardt", None),
    ("lane-arabian-society", None, r"Arabian Society in the Middle Ages"),
    ("ameer-ali", r"Ameer Ali|Amir Ali", None),
    ("muir", r"Muir, William", r"Caliph|Mahomet|Mohammed"),
    ("villari", r"Villari", None),
    ("oliphant-florence", None, r"Makers of Florence"),
    ("roscoe", r"Roscoe, William", r"Lorenzo|Leo the Tenth"),
    ("gibbon-islam", None, r"Decline and Fall.*Volume 5"),
    ("zimmern-alice", None, r"Greek Commonwealth"),
    ("bury", r"Bury, J\. B\.", r"Greece"),
    ("butcher", r"Butcher, S\. H\.", r"Greek Genius|Aspects"),
    ("lang-andrew-homer", None, r"^$"),
]
# held out of every shelf (and the eval decks for the ages)
HELD_TITLES = re.compile(
    r"don quixote|anabasis|peloponnesian|orlando furioso|jerusalem delivered|bust[aā]n|confessions of al ghazzali|divan of hafiz",
    re.I,
)
HELD = {
    "greek": [7142, 1170, 830],
    "islamic": [74883, 60471, 58977],
    "renaissance": [615, 392, 996],
}
EXCLUDE_EXTRA = {1170, 1171, 1172}  # other Anabasis editions stay off the Greek shelf


def persons(authors: str):
    out = []
    for part in authors.split(";"):
        part = part.strip()
        if not part or part.lower().startswith("anonymous"):
            continue
        role = re.search(r"\[([^\]]+)\]", part)
        role = role.group(1).lower() if role else "author"
        dates = re.search(r"(\d{1,4})\??\s*(BCE)?\s*-\s*(\d{1,4})?\??\s*(BCE)?", part)
        born = died = None
        if dates:
            born = -int(dates.group(1)) if dates.group(2) else int(dates.group(1))
            if dates.group(3):
                died = -int(dates.group(3)) if dates.group(4) else int(dates.group(3))
        elif re.search(r"active", part):
            died = 0  # "active 14th century": long dead
            born = 0
        out.append((part, role, born, died))
    return out


def legal(c: dict) -> tuple[bool, str]:
    ps = persons(c["Authors"])
    if not ps:
        return True, "anonymous"
    for name, role, born, died in ps:
        if died is None:
            return False, f"no death year: {name[:40]}"
        if died > 1955:
            return False, f"died {died}: {name[:40]}"
        if "author" not in role and (born is None or born < 1760):
            return False, f"{role} born {born}: {name[:40]}"
    return True, "ok"


def english_texts():
    return [
        c
        for c in g.catalogue()
        if c["Type"] == "Text" and "en" in [x.strip() for x in c["Language"].split(";")]
    ]


def pick(spec, cat, held_ids):
    rows, refused = [], []
    for work, apat, tpat in spec:
        for c in cat:
            gid = int(c["Text#"])
            if gid in held_ids:
                continue
            if apat and not re.search(apat, c["Authors"]):
                continue
            if tpat and not re.search(tpat, c["Title"]):
                continue
            if HELD_TITLES.search(c["Title"]):
                continue
            if (
                CHILD.search(c["Title"])
                or CHILD.search(c.get("Subjects", ""))
                or PERIODICAL.search(c["Title"])
            ):
                continue
            ok, why = legal(c)
            (rows if ok else refused).append(
                (work, gid, c["Title"].replace("\n", " "), c["Authors"], why)
            )
    # one copy of each text: Gutenberg re-released some books under new ids (Burton's Nights twice),
    # so a title already taken under a lower id is dropped
    seen, titles, out = set(), set(), []
    for r in sorted(rows, key=lambda r: r[1]):
        key = (r[0], g.norm(r[2]))
        if r[1] in seen or key in titles:
            continue
        seen.add(r[1])
        titles.add(key)
        out.append(r)
    return out, refused


def write(name, rows, family):
    p = ROOT / f"lists/content-{name}-draft.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["title", "author", "language", "family", "text", "work"])
        for work, gid, title, authors, _ in rows:
            w.writerow(
                [
                    f"{title[:120]} [pg{gid}]",
                    g.surname(authors.split(";")[0].split(",")[0]) if authors else "",
                    "en",
                    family,
                    "",
                    work,
                ]
            )
    return p


def add_overrides(paths):
    ov = ROOT / "lists/overrides.csv"
    have = {(r["title"], r["author"]) for r in csv.DictReader(open(ov, encoding="utf-8"))}
    with open(ov, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        for p in paths:
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if (r["title"], r["author"]) not in have:
                    w.writerow(
                        [r["title"], r["author"], r["title"].rsplit("[pg", 1)[1].rstrip("]")]
                    )


def main():
    cat = english_texts()
    held = {i for ids in HELD.values() for i in ids} | EXCLUDE_EXTRA
    # never draw a book that is a hole card, a truth or already in the hundred
    taken = set()
    for L in (
        "lists/hole-cards.csv",
        "lists/hole-cards-v2.csv",
        "lists/truths.csv",
        "lists/hundred-by-reach.csv",
    ):
        taken |= {r.chosen for r in g.resolve_list(ROOT / L) if r.chosen}
    held |= taken
    out = []
    for name, spec, fam in (
        ("greek", GREEK, "Hellenic"),
        ("islamic", ISLAMIC, "Afroasiatic"),
        ("renaissance", RENAISSANCE, "Romance"),
        ("about", ABOUT, "Germanic"),
    ):
        rows, refused = pick(spec, cat, held)
        if name == "islamic":
            rows = [r for r in rows if r[0] != "hafiz"]
        out.append(write(name, rows, fam))
        works = {}
        for r in rows:
            works[r[0]] = works.get(r[0], 0) + 1
        print(f"{name}: {len(rows)} titles, {len(refused)} refused; works {works}")
        for r in refused[:6]:
            print(f"   refused {r[1]} {r[2][:40]} -- {r[4]}")
    curated = set()
    for p in out:
        curated |= {
            int(r["title"].rsplit("[pg", 1)[1].rstrip("]"))
            for r in csv.DictReader(open(p, encoding="utf-8"))
        }
    held |= curated
    # three random draws: legal English texts, no periodicals or children's retellings, none taken
    pool = [
        c
        for c in cat
        if int(c["Text#"]) not in held
        and not PERIODICAL.search(c["Title"])
        and legal(c)[0]
        and persons(c["Authors"])
    ]
    for seed in (1, 2, 3):
        rng = random.Random(seed)
        draw = rng.sample(pool, 45)
        rows = [
            ("random", int(c["Text#"]), c["Title"].replace("\n", " "), c["Authors"], "ok")
            for c in draw
        ]
        out.append(write(f"random-{seed}", rows, "Germanic"))
        print(f"random-{seed}: 45 drawn from {len(pool)}")
    add_overrides(out)
    for name, ids in HELD.items():
        p = ROOT / f"lists/held-{name}.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["title", "author", "language", "family", "text"])
            for gid in ids:
                c = next(x for x in cat if int(x["Text#"]) == gid)
                w.writerow(
                    [
                        f"{c['Title'].splitlines()[0][:120]} [pg{gid}]",
                        g.surname(c["Authors"].split(";")[0].split(",")[0]),
                        "en",
                        {"greek": "Hellenic", "islamic": "Afroasiatic", "renaissance": "Romance"}[
                            name
                        ],
                        "",
                    ]
                )
        add_overrides([p])


if __name__ == "__main__":
    main()


def label_traits():
    """Append fiction and verse labels for every draft row to lists/traits.csv, by the pool's rule
    (the catalogue's subject tags, scripts/make_pool.py); first person is left blank."""
    cat = {int(c["Text#"]): c for c in g.catalogue() if c["Text#"].isdigit()}
    tp = ROOT / "lists/traits.csv"
    have = {r["title"] for r in csv.DictReader(open(tp, encoding="utf-8"))}
    n = 0
    with open(tp, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        for p in sorted(ROOT.glob("lists/content-*-draft.csv")):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if r["title"] in have:
                    continue
                c = cat.get(int(r["title"].rsplit("[pg", 1)[1].rstrip("]")), {})
                s = (c.get("Subjects", "") + " " + c.get("Bookshelves", "")).lower()
                fiction = int(
                    any(k in s for k in ("fiction", "stories", "novel", "drama", "tales", "fairy"))
                )
                verse = int(any(k in s for k in ("poetry", "poems", "verse")))
                w.writerow([r["title"], fiction, verse, ""])
                have.add(r["title"])
                n += 1
    print(f"labelled {n} titles in lists/traits.csv")
