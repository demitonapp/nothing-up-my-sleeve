"""The fitout data model (SQLAlchemy), owned by S3 control: a fitout is a plan of what a voyage reads, and its
prechecks are what must be measured true before it may sail. Alembic (migrations/) creates and changes these
tables; nothing else does (Justin, 2026-11-07: "use alembic to manage the python data migrations and models").

Schema `fitout`:
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

SCHEMA = "fitout"
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


VIEWS = {
    "current_results": """
        create or replace view fitout.current_results as
        select distinct on (fitout_key, item_key) *
        from fitout.precheck_results
        order by fitout_key, item_key, checked_at desc, id desc""",
    "readiness": """
        create or replace view fitout.readiness as
        select f.key as fitout_key,
               count(*) filter (where fp.required)                                    as required,
               count(*) filter (where fp.required and r.passed)                       as passed,
               count(*) filter (where fp.required and r.passed is distinct from true) as outstanding,
               count(*) filter (where not fp.required)                                as planned,
               coalesce(bool_and(coalesce(r.passed, false)) filter (where fp.required), false)
                 and count(*) filter (where fp.required) > 0                           as ready
        from fitout.fitouts f
        join fitout.fitout_prechecks fp on fp.fitout_key = f.key
        left join fitout.current_results r on r.fitout_key = fp.fitout_key and r.item_key = fp.item_key
        group by f.key""",
}
