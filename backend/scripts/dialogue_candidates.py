"""The dialogue candidates for Table Talk's conversation stage (2026-11-08, Justin: "Yes, score them";
ships/plans/first-50m-vast.md, part B1).

`list`: the Gutenberg catalogue's English texts, no author known to have died after 1955, sorted into four kinds by
the catalogue's Subjects and Bookshelves (and, but for plays, the title):
- **catechism**: catechisms, and books the catalogue files under "Questions and answers"
- **philosophical dialogue**: Plato, Lucian, Socrates, Berkeley's and Hume's dialogues, dialogues on philosophy
- **table talk**: table talk, conversations, colloquies
- **play**: a book the catalogue files under drama or plays (a title saying "comedy" is not enough)
The first kind that matches wins, in that order. Writes `lists/dialogue-candidates.csv` (the intake's list:
`thorp acquire lists/dialogue-candidates.csv`) and `lists/dialogue-candidates-kinds.csv` (each book's kind and
its authors' latest death year). The 7 November count (DECISIONS.md, "Table Talk") was 1,224 plays, 61
philosophical dialogues, 24 catechisms and 77 books of table talk; this rule finds 1,503, 61, 257 and 73, the
catechisms and plays larger because books whose authors have no dates are kept here (the intake gate then refuses
those, its rule "dead by 1955").

`score`: every candidate whose text is in the library, scored for Ogden-ness as Ogden v0.2's books were
(thorp.ogden.score on the first 400,000 characters; the bar 68%). Writes `lists/dialogue-ogden-scores.csv`.

    uv run --project backend python backend/scripts/dialogue_candidates.py list
    uv run --project backend python backend/scripts/dialogue_candidates.py score
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter

from thorp import paths
from thorp.paths import ROUTER as ROOT

BAR = 0.68  # Ogden v0.1's and v0.2's bar
KINDS = [
    ("catechism", re.compile(r"\bcatechism|questions and answers", re.I)),
    (
        "philosophical dialogue",
        re.compile(
            r"\bsocrates\b|^plato,|^lucian|dialogues? concerning|three dialogues|\bdialogues?\b.*\b(philosoph|plato|socrat)"
            r"|\b(philosoph|plato|socrat).*\bdialogues?\b|^Dialogues? (of|on|concerning|between)",
            re.I,
        ),
    ),
    ("table talk", re.compile(r"table.talk|\bconversation(s|al)?\b|\bcolloqu", re.I)),
    ("play", re.compile(r"\bdrama\b|\bplays?\b|\bcomed(y|ies)\b|\btraged(y|ies)\b|\bfarces?\b", re.I)),
]
FAMILIES = [  # the original's language family, by author, for the shelf's variety (else Germanic)
    (r"^(Plato|Lucian|Aristophanes|Sophocles|Euripides|Aeschylus|Menander|Xenophon)\b", "Hellenic"),
    (r"^(Plautus|Terence|Seneca|Cicero)\b", "Italic"),
    (
        r"^(Molière|Moli|Racine|Corneille|Beaumarchais|Marivaux|Goldoni|Calder|Lope de Vega|Cervantes|Rostand"
        r"|Maeterlinck|Hugo|Musset|Dumas|Sardou|Brieux|Pirandello|D'Annunzio|Echegaray|Benavente|Gald|Erasmus"
        r"|Leopardi|Voltaire|Diderot|Fontenelle)",
        "Romance",
    ),
    (r"^(Chekhov|Gogol|Tolstoy|Turgenev|Ostrovsky|Andreyev|Gorky|Pushkin|Griboyedov)", "Slavic"),
]


def deaths(authors: str) -> list[int | None]:
    """Each author's death year from the catalogue's "Name, born-died" (BCE years negative), None when not given."""
    out: list[int | None] = []
    for a in [x for x in authors.split(";") if x.strip()]:
        m = re.findall(r"(\d{3,4})\??\s*(BCE)?\s*-\s*(\d{3,4})?\??\s*(BCE)?", a)
        if not m:
            out.append(None)
            continue
        _, _, d, bce = m[-1]
        out.append(-int(d) if (d and bce) else (int(d) if d else None))
    return out


def kind_of(r: dict) -> str | None:
    subj = r["Subjects"] + " ; " + r["Bookshelves"]
    title = r["Title"].replace("\n", " ")
    for k, rx in KINDS:
        hay = subj if k == "play" else subj + " ; " + title + (" ; " + r["Authors"] if k == "philosophical dialogue" else "")
        if rx.search(hay):
            return None if k == "play" and not re.search(r"drama|plays", subj, re.I) else k
    return None


def candidates() -> list[dict]:
    csv.field_size_limit(10**9)
    with open(paths.data_dir() / "catalogue" / "pg_catalog.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if r["Type"] != "Text" or r["Language"] != "en":
            continue
        known = [x for x in deaths(r["Authors"]) if x is not None]
        if known and max(known) > 1955:
            continue
        kind = kind_of(r)
        if not kind:
            continue
        first = r["Authors"].split(",")
        author = first[0] + (", " + first[1].strip() if len(first) > 1 else "")
        family = next((f for rx, f in FAMILIES if re.search(rx, r["Authors"][:80])), "Germanic")
        out.append({
            "kind": kind, "id": r["Text#"], "title": r["Title"].replace("\n", " ")[:120], "author": author,
            "family": family, "death": max(known) if known else "unknown",
        })  # fmt: skip
    return out


def cmd_list() -> None:
    rows = candidates()
    with open(ROOT / "lists" / "dialogue-candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows({"title": r["title"], "author": r["author"], "language": "en", "family": r["family"],
                     "text": f"gutenberg:{r['id']}"} for r in rows)  # fmt: skip
    with open(ROOT / "lists" / "dialogue-candidates-kinds.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["book", "kind", "death"])
        w.writeheader()
        w.writerows({"book": f"pg{r['id']}", "kind": r["kind"], "death": r["death"]} for r in rows)
    print(len(rows), dict(Counter(r["kind"] for r in rows)))


def cmd_score() -> None:
    from thorp import manifest, ogden
    from thorp.sources import load_text

    with open(ROOT / "lists" / "dialogue-candidates-kinds.csv") as f:
        kinds = {r["book"]: r for r in csv.DictReader(f)}
    books = {b.id: b for b in manifest.all_books()}
    out, missing = [], Counter()
    for bid, k in kinds.items():
        b = books.get(bid)
        if b is None:
            missing[k["kind"]] += 1
            continue
        try:
            text = load_text(bid)
        except Exception:  # noqa: BLE001 (a book whose text is not here cannot be scored)
            missing[k["kind"]] += 1
            continue
        s = ogden.score(text[:400000])
        out.append({
            "book": bid, "kind": k["kind"], "title": b.title, "author": b.author or "", "death": k["death"],
            "words": int(len(text) / 5.7), "ogden": round(s["ogden"], 4), "names": round(s["names"], 4),
        })  # fmt: skip
    out.sort(key=lambda r: -r["ogden"])
    with open(ROOT / "lists" / "dialogue-ogden-scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]) if out else ["book"])
        w.writeheader()
        w.writerows(out)
    print(f"scored {len(out)}; not in the library: {dict(missing)}")
    for kind, _ in KINDS:
        rows = [r for r in out if r["kind"] == kind]
        if not rows:
            continue
        at = [r for r in rows if r["ogden"] >= BAR]
        med = sorted(r["ogden"] for r in rows)[len(rows) // 2]
        print(f"{kind:24} scored {len(rows):5}  median {med:.0%}  at the bar {len(at):4}  "
              f"({sum(r['words'] for r in at) / 1e6:.1f}M words of {sum(r['words'] for r in rows) / 1e6:.1f}M)")  # fmt: skip


if __name__ == "__main__":
    {"list": cmd_list, "score": cmd_score}[sys.argv[1] if len(sys.argv) > 1 else "list"]()
