"""The fitout data model (SQLAlchemy), owned by S3 control: a fitout is a plan of what a voyage reads, and its
prechecks are what must be measured true before it may sail. Alembic (migrations/) creates and changes these
tables; nothing else does (Justin, 2026-11-07: "use alembic to manage the python data migrations and models").

Schema `s3` (S3 control; `fitout` until the systems took their schemas, 8 November):
- `fitouts`, `stages`: the fitout and its stages in order.
- `precheck_items`: the catalogue of checks (what is measured, the pass rule, the VSM system that owns it).
- `fitout_prechecks`: which items a fitout must pass (required) or carries as planned.
- `precheck_results`: every reading, kept; the views `current_results` (the latest per fitout and item) and
  `readiness` (per fitout: required, passed, outstanding, planned, and whether it may sail) are made in the
  first migration.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA = "s3"  # S3 control (was `fitout` until the systems took their schemas)
SYSTEMS = ("S1", "S2", "S3", "S3*", "S4", "S5")
KINDS = ("cleaning", "library", "tokeniser", "policy")


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class Fitout(Base):
    __tablename__ = "fitouts"
    __table_args__ = (
        CheckConstraint("status in ('draft', 'ready', 'sailing', 'home')", name="fitout_status"),
    )

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    aim: Mapped[str] = mapped_column(Text, default="", server_default="")
    clean: Mapped[str] = mapped_column(Text)  # the cleaning version its books are read with
    tokeniser: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    positions: Mapped[str] = mapped_column(Text, default="rope", server_default="rope")
    status: Mapped[str] = mapped_column(Text, default="draft", server_default="draft")
    adopted: Mapped[str] = mapped_column(Text, default="", server_default="")  # who adopted it, when
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stages: Mapped[list[Stage]] = relationship(
        back_populates="fitout", cascade="all, delete-orphan", order_by="Stage.ordinal"
    )
    prechecks: Mapped[list[FitoutPrecheck]] = relationship(
        back_populates="fitout", cascade="all, delete-orphan"
    )


class Stage(Base):
    __tablename__ = "stages"
    __table_args__ = (
        CheckConstraint("phase in ('pretraining', 'post-training')", name="stage_phase"),
    )

    fitout_key: Mapped[str] = mapped_column(
        Text, ForeignKey("fitouts.key", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    library: Mapped[str] = mapped_column(Text)  # a list in lists/
    tokens: Mapped[int | None] = mapped_column(BigInteger)  # None: the whole library
    selection: Mapped[str] = mapped_column(Text, default="all", server_default="all")
    passes: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lr: Mapped[float | None] = mapped_column(Float)
    tack: Mapped[dict | None] = mapped_column(JSONB)
    purpose: Mapped[str] = mapped_column(Text, default="", server_default="")
    # the declared selection of the library's books (thorp/selection.py): weights by language, an Ogden-ness bar,
    # a period, filters by kind, voice and source. None: `library` is a list written by hand.
    compose: Mapped[dict | None] = mapped_column(JSONB)

    fitout: Mapped[Fitout] = relationship(back_populates="stages")


class PrecheckItem(Base):
    __tablename__ = "precheck_items"
    __table_args__ = (
        CheckConstraint(f"system in {SYSTEMS}", name="item_system"),
        CheckConstraint(f"kind in {KINDS}", name="item_kind"),
        CheckConstraint("comparator in ('=', '<=', '>=')", name="item_comparator"),
    )

    key: Mapped[str] = mapped_column(Text, primary_key=True)  # e.g. clean.quotes, library.period
    name: Mapped[str] = mapped_column(Text)
    about: Mapped[str] = mapped_column(Text)  # what it checks and why
    system: Mapped[str] = mapped_column(Text)  # the VSM system that owns it
    kind: Mapped[str] = mapped_column(Text)
    measure: Mapped[str] = mapped_column(Text)  # what the value is
    comparator: Mapped[str] = mapped_column(Text)
    threshold: Mapped[float] = mapped_column(Float)
    clean_version: Mapped[str | None] = mapped_column(Text)  # the cleaning version it belongs to


class FitoutPrecheck(Base):
    __tablename__ = "fitout_prechecks"

    fitout_key: Mapped[str] = mapped_column(
        Text, ForeignKey("fitouts.key", ondelete="CASCADE"), primary_key=True
    )
    item_key: Mapped[str] = mapped_column(Text, ForeignKey("precheck_items.key"), primary_key=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    note: Mapped[str] = mapped_column(Text, default="", server_default="")

    fitout: Mapped[Fitout] = relationship(back_populates="prechecks")
    item: Mapped[PrecheckItem] = relationship()


class PrecheckResult(Base):
    __tablename__ = "precheck_results"
    __table_args__ = (
        Index("precheck_results_latest", "fitout_key", "item_key", "checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fitout_key: Mapped[str] = mapped_column(Text, ForeignKey("fitouts.key", ondelete="CASCADE"))
    item_key: Mapped[str] = mapped_column(Text, ForeignKey("precheck_items.key"))
    value: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    checked_by: Mapped[str] = mapped_column(Text, default="", server_default="")


class LibraryFact(Base):
    """What the library knows of a book (thorp/library_facts.py): its language, writer's years, the year it is
    placed in and the rule that placed it, its kind and voice and the rules that gave them, its Ogden-ness. Rebuilt
    by `thorp select facts`; the table is the dashboard's and SQL's view of the rows a composition reads."""

    __tablename__ = "library_facts"

    book: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text, default="", server_default="")
    source: Mapped[str] = mapped_column(Text)  # the collection: gutenberg, archive, local
    set: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    translated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    born: Mapped[int | None] = mapped_column(Integer)
    died: Mapped[int | None] = mapped_column(Integer)
    gate_death: Mapped[int | None] = mapped_column(Integer)  # the latest death among every credited name (S5 'period')
    year: Mapped[int | None] = mapped_column(Integer)
    year_basis: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    kind_rule: Mapped[str] = mapped_column(Text)
    voice: Mapped[str] = mapped_column(Text)
    voice_rule: Mapped[str] = mapped_column(Text)
    ogden: Mapped[float | None] = mapped_column(Float)
    ogden_from: Mapped[str] = mapped_column(Text, default="", server_default="")
    words: Mapped[int] = mapped_column(BigInteger)
    fetched: Mapped[str] = mapped_column(Text, default="", server_default="")
    held_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    control: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    title_key: Mapped[str] = mapped_column(Text, default="", server_default="")
    shelves: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    facts_fingerprint: Mapped[str] = mapped_column(Text)  # the build these rows belong to
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Composition(Base):
    """One composing of a reading list from a declared selection: which selection (and its hash), drawn from which
    facts, what list it wrote (and its sha1), what it yielded and what the S3 gate's library prechecks said of it.
    Every composing is kept, so a fitout's books can always be traced to the words that chose them."""

    __tablename__ = "compositions"
    __table_args__ = (Index("compositions_fitout", "fitout_key", "composed_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fitout_key: Mapped[str] = mapped_column(Text)  # not a foreign key: a selection may be tried before its fitout exists
    ordinal: Mapped[int | None] = mapped_column(Integer)  # the stage
    spec: Mapped[dict] = mapped_column(JSONB)
    spec_hash: Mapped[str] = mapped_column(Text)
    facts_fingerprint: Mapped[str] = mapped_column(Text)
    list_path: Mapped[str] = mapped_column(Text)
    list_sha1: Mapped[str] = mapped_column(Text)
    books: Mapped[int] = mapped_column(Integer)
    words: Mapped[int] = mapped_column(BigInteger)
    summary: Mapped[dict] = mapped_column(JSONB)  # counts by language, kind, voice, source, period, Ogden-ness
    funnel: Mapped[list] = mapped_column(JSONB)  # [rule, books left, what it did]
    notes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    prechecks: Mapped[list] = mapped_column(JSONB)  # the S3 gate's library items read on the list
    passed: Mapped[bool] = mapped_column(Boolean)
    against: Mapped[str] = mapped_column(Text, default="", server_default="")  # a list it was set beside
    diff: Mapped[dict | None] = mapped_column(JSONB)
    composed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    composed_by: Mapped[str] = mapped_column(Text, default="", server_default="")


VIEWS = {
    "current_results": """
        create or replace view s3.current_results as
        select distinct on (fitout_key, item_key) *
        from s3.precheck_results
        order by fitout_key, item_key, checked_at desc, id desc""",
    "readiness": """
        create or replace view s3.readiness as
        select f.key as fitout_key,
               count(*) filter (where fp.required)                                    as required,
               count(*) filter (where fp.required and r.passed)                       as passed,
               count(*) filter (where fp.required and r.passed is distinct from true) as outstanding,
               count(*) filter (where not fp.required)                                as planned,
               coalesce(bool_and(coalesce(r.passed, false)) filter (where fp.required), false)
                 and count(*) filter (where fp.required) > 0                           as ready
        from s3.fitouts f
        join s3.fitout_prechecks fp on fp.fitout_key = f.key
        left join s3.current_results r on r.fitout_key = fp.fitout_key and r.item_key = fp.item_key
        group by f.key""",
}


# ---- the Navigator's Wager (S4 intelligence's game; thorp/viable/s4_intelligence/wager.py), schema `s4`
GAME_SCHEMA = "s4"  # S4 intelligence (was `game`)


class WagerRound(Base):
    """A round: one lever pulled on a control voyage. Dealt by the Navigator on the Bet tab (or one of Ogden
    v0.1's own pairs); `pull_spec` is the voyage the lever makes, queued when the Navigator says so."""

    __tablename__ = "rounds"
    __table_args__ = {"schema": GAME_SCHEMA}

    key: Mapped[str] = mapped_column(Text, primary_key=True)  # the pull voyage's name
    preset: Mapped[str] = mapped_column(Text)  # the class page it was dealt on
    lever: Mapped[str] = mapped_column(Text)
    control: Mapped[str] = mapped_column(Text)  # the control voyage's name
    pull: Mapped[str] = mapped_column(Text)  # the pull voyage's name
    pull_spec: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="dealt", server_default="dealt")  # dealt, queued
    dealt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WagerBet(Base):
    """A chip: the Navigator's call of how the pull moves one card (and, for a bonus, the layer it falls in)."""

    __tablename__ = "bets"
    __table_args__ = {"schema": GAME_SCHEMA}

    round_key: Mapped[str] = mapped_column(Text, primary_key=True)
    card: Mapped[str] = mapped_column(Text, primary_key=True)
    player: Mapped[str] = mapped_column(Text, primary_key=True, default="Justin", server_default="Justin")
    move: Mapped[str] = mapped_column(Text)
    layer: Mapped[int | None] = mapped_column(Integer)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    practice: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # placed after the pull sailed


# ---- the ships (schema `s1`, S1 operations; was `ship`): what a ship is, held in the database, not in code (Justin, 2026-11-08:
# "these things shouldn't be hardcoded, we have postgres for a reason"; "a ship has characteristics: size,
# training content, training methodology, voyages, discoveries"). Read through thorp/ship_store.py.
SHIP_SCHEMA = "s1"  # S1 operations (was `ship`)


class Size(Base):
    """A ship's size: one rung of the ladder (a preset), with its name and its role (300k The keel, 100m The
    explorer, 350m The trader), where it trains, how it is judged and the metrics that judge it."""

    __tablename__ = "sizes"
    __table_args__ = {"schema": SHIP_SCHEMA}

    preset: Mapped[str] = mapped_column(Text, primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, unique=True)  # smallest first
    name: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[str] = mapped_column(Text)  # what a ship of this size is for
    overview: Mapped[str] = mapped_column(Text, default="", server_default="")
    kind: Mapped[str | None] = mapped_column(Text)  # nursery, proxy, or none
    vocab: Mapped[int | None] = mapped_column(Integer)
    trains_where: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(Text, default="planned", server_default="planned")
    scored: Mapped[str] = mapped_column(Text, default="", server_default="")
    # [[name, what it measures, "live" | "to come"], ...]
    metrics: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")


class ShipRecord(Base):
    """A ship: a size fitted out one way (training content and method, the fitout). Named once and never
    renamed. Its voyages are its runs, one per seed."""

    __tablename__ = "ships"
    __table_args__ = {"schema": SHIP_SCHEMA}

    key: Mapped[str] = mapped_column(Text, primary_key=True)  # "<preset>:<fitout id>"
    name: Mapped[str] = mapped_column(Text, unique=True)
    preset: Mapped[str] = mapped_column(Text)  # the exact shape, a size or a variant of one (300k-h4)
    size: Mapped[str] = mapped_column(Text, ForeignKey(f"{SHIP_SCHEMA}.sizes.preset"))
    fitout_id: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str] = mapped_column(Text, default="", server_default="")  # the fitout in a line
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(Text, default="in service", server_default="in service")  # or "retired"
    retired_note: Mapped[str | None] = mapped_column(Text)  # why it was retired, in Justin's words where he gave them
    seeded_from: Mapped[dict | str | None] = mapped_column(JSONB)  # the run whose trained mind it starts from
    expedition: Mapped[str | None] = mapped_column(Text)  # the expedition that commissioned it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoyageRecord(Base):
    """A voyage: one run of a ship (the run itself, its metrics and status, stay in the ledger)."""

    __tablename__ = "voyages"
    __table_args__ = (Index("voyages_ship", "ship_key"), {"schema": SHIP_SCHEMA})

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    ship_key: Mapped[str] = mapped_column(Text, ForeignKey(f"{SHIP_SCHEMA}.ships.key", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    seed: Mapped[int | None] = mapped_column(Integer)
    started: Mapped[str | None] = mapped_column(Text)  # as the ledger records it (UTC, ISO)
