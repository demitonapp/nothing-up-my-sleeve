"""Outside models as rows, and the goals that approach them (13 November, Justin: the model card should show an existing approach on
a model, "made secure in postgres with relations").

`s4.models` is one row an outside model (its Hugging Face id) of a house (`s4.labs`); `s1.goal_models` relates it to the goals
that take it up, with a role (`beat`, `compare`, `study`) and a note; `s4.model_approaches` is the join the cards read. The keys,
the checks and the join are Postgres's (migration e6a8b0c2d4f6): this module issues one statement a call and holds no data, so a
bad lab, goal or role comes back as the database's own refusal, not a rule re-stated in Python.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from thorp import store

ROLES = ("beat", "compare", "study")


def _refused(e: IntegrityError) -> ValueError:
    msg = str(getattr(e.orig, "diag", None) and e.orig.diag.message_detail or e.orig).strip().splitlines()[0]
    return ValueError(msg)


def add_model(model_id: str, lab_key: str, name: str, params: int | None = None, url: str = "") -> str:
    """Register an outside model (idempotent on its id: a second call updates its name, size and link)."""
    try:
        with store.session() as s:
            s.execute(
                text(
                    "insert into s4.models (id, lab_key, name, params, url) values (:i, :l, :n, :p, :u) "
                    "on conflict (id) do update set lab_key = excluded.lab_key, name = excluded.name, "
                    "params = excluded.params, url = excluded.url"
                ),
                {"i": model_id, "l": lab_key, "n": name, "p": params, "u": url},
            )
    except IntegrityError as e:
        raise _refused(e) from None
    return model_id


def link(goal_id: str, model_id: str, role: str, note: str = "") -> None:
    """A goal takes a model up in a role. Postgres refuses an unknown goal, model or role."""
    try:
        with store.session() as s:
            s.execute(
                text(
                    "insert into s1.goal_models (goal_id, model_id, role, note) values (:g, :m, :r, :n) "
                    "on conflict (goal_id, model_id, role) do update set note = excluded.note"
                ),
                {"g": goal_id, "m": model_id, "r": role, "n": note},
            )
    except IntegrityError as e:
        raise _refused(e) from None


def unlink(goal_id: str, model_id: str, role: str | None = None) -> int:
    with store.session() as s:
        r = s.execute(
            text("delete from s1.goal_models where goal_id = :g and model_id = :m and (cast(:r as text) is null or role = :r)"),
            {"g": goal_id, "m": model_id, "r": role},
        )
        return r.rowcount


def approaches(country: str | None = None, model_id: str | None = None) -> list[dict]:
    """Every model a shown goal takes up, with the goal beside it, from `s4.model_approaches`."""
    where, args = [], {}
    if country:
        where.append("country = :c")
        args["c"] = country
    if model_id:
        where.append("model_id = :m")
        args["m"] = model_id
    sql = "select * from s4.model_approaches" + (" where " + " and ".join(where) if where else "")
    with store.session() as s:
        rows = [dict(r) for r in s.execute(text(sql + " order by model_id, goal_id, role"), args).mappings()]
    return rows


def cards(country: str | None = None) -> list[dict]:
    """The models that have an approach, one card each: the model, and every goal that takes it up. The grouping is the
    page's shape only; which goals, roles and notes there are is the view's."""
    out: dict[str, dict] = {}
    for r in approaches(country):
        c = out.setdefault(
            r["model_id"],
            {"model_id": r["model_id"], "name": r["model_name"], "lab_key": r["lab_key"], "country": r["country"],
             "params": r["params"], "url": r["url"], "approaches": []},
        )  # fmt: skip
        c["approaches"].append({k: r[k] for k in ("goal_id", "goal_text", "goal_status", "role", "note", "expedition_key", "expedition_name")})  # fmt: skip
    return list(out.values())
