r"""Thorp's records in Postgres, by the viable system (DECISIONS.md, "One store: Postgres, by the viable system",
approved 2026-11-08 13:42, Justin: "Approve, start phase 1"). One schema per system: `s1` operations, `s2`
coordination, `s3` control, `s3star` audit, `s4` intelligence, `s5` policy. Alembic (migrations/) makes and
changes these tables; nothing else does. The models share `models.Base`, so one metadata holds the whole store.

Phase 1, the small state that used to be JSON and JSONL in data/:

- **S2:** `helm` (who holds this Mac's helm; was helm.json; the lock itself stays an flock, which dies with its
  process), `lanes` (what each lane has out; was lanes.json).
- **S3:** `gate_decisions` and `gate_policy_decisions` (every decision of the gate and each policy's part in it;
  was gate-log.jsonl), `spend_events` (the charter's spend log, one row per hire and release; was
  charter-log.jsonl).
- **S3\*:** `audits` (each orphan or ghost the charter audit found and what was done).
- **S4:** `market_reads` (each Vast.ai price read; was charter-market.jsonl).
- **S5:** `policy_switches` (S5's switch over a policy's default; was policies.json), `policy_exceptions` and
  `policy_exception_matches` (the runs a policy does not govern, by name or pattern, and why; was
  policy-exceptions.json), `charter_terms` (each change to a charter term, the latest in force; was charter.json).
  The policies themselves (statement, check, default) stay in code (vsm.POLICIES): they are checks, not data.
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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from thorp.viable.s3_control.models import Base

S1, S2, S3, S3STAR, S4, S5 = "s1", "s2", "s3", "s3star", "s4", "s5"
SCHEMAS = (S1, S2, S3, S3STAR, S4, S5)


# ---------------------------------------------------------------- S2, coordination


class Helm(Base):
    """Who is at sea on this Mac's helm now: one row while it is held, none when it is free."""

    __tablename__ = "helm"
    __table_args__ = {"schema": S2}

    helm: Mapped[str] = mapped_column(Text, primary_key=True, default="mac", server_default="mac")
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    pid: Mapped[int] = mapped_column(Integer)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Lane(Base):
    """What a lane of the standing queue has out (the Mac, Vast.ai); line null when it is in port."""

    __tablename__ = "lanes"
    __table_args__ = (CheckConstraint("lane in ('mac', 'vast')", name="lane_known"), {"schema": S2})

    lane: Mapped[str] = mapped_column(Text, primary_key=True)
    line: Mapped[str | None] = mapped_column(Text)
    pid: Mapped[int | None] = mapped_column(Integer)
    since: Mapped[str | None] = mapped_column(Text)  # as the coordinator writes it (its own clock, HH:MM:SS or ISO)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- S3, control


class GateDecision(Base):
    """One decision of the S3 gate: a voyage (or a fitout, a charter) asked, passed or refused."""

    __tablename__ = "gate_decisions"
    __table_args__ = (
        CheckConstraint("verdict in ('passed', 'refused')", name="gate_verdict"),
        Index("gate_decisions_at", "at"),
        Index("gate_decisions_name", "name"),
        {"schema": S3},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    name: Mapped[str | None] = mapped_column(Text)  # the voyage's name (its run, once the ledger is here)
    ship: Mapped[str | None] = mapped_column(Text)
    place: Mapped[str] = mapped_column(Text)  # where it was asked: voyage, fitout builder, charter
    verdict: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="here", server_default="here")  # here, a box's papers, imported

    policies: Mapped[list[GatePolicyDecision]] = relationship(
        back_populates="decision", cascade="all, delete-orphan", order_by="GatePolicyDecision.ordinal"
    )


class GatePolicyDecision(Base):
    """A policy's part in a gate decision: how it was applied (kept, excepted, advisory, bargain, refused), why."""

    __tablename__ = "gate_policy_decisions"
    __table_args__ = {"schema": S3}

    decision_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(f"{S3}.gate_decisions.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy: Mapped[str] = mapped_column(Text)
    how: Mapped[str] = mapped_column(Text)
    why: Mapped[str | None] = mapped_column(Text)

    decision: Mapped[GateDecision] = relationship(back_populates="policies")


class SpendEvent(Base):
    """The charter's spend: a ship hired, a ship released (with what it cost). The fields every event carries are
    columns; the rest of what was recorded (the quote, the preset, the measured rate) is `detail`."""

    __tablename__ = "spend_events"
    __table_args__ = (Index("spend_events_instance", "instance"), {"schema": S3})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event: Mapped[str] = mapped_column(Text)  # hired, released
    instance: Mapped[int | None] = mapped_column(BigInteger)
    run_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


# ---------------------------------------------------------------- S3*, audit


class Audit(Base):
    """What the charter audit found: an orphan (hired, labelled, not sailing) or a ghost (logged out, not listed)."""

    __tablename__ = "audits"
    __table_args__ = (CheckConstraint("finding in ('orphan', 'ghost')", name="audit_finding"), {"schema": S3STAR})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finding: Mapped[str] = mapped_column(Text)
    instance: Mapped[int] = mapped_column(BigInteger)
    run_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)  # released, closed in the log, left (not asked to release)
    cost: Mapped[float | None] = mapped_column(Float)


# ---------------------------------------------------------------- S4, intelligence


class MarketRead(Base):
    """One price read from Vast.ai for one GPU: the best offer keeping the terms, and what the voyage would cost."""

    __tablename__ = "market_reads"
    __table_args__ = (Index("market_reads_gpu_at", "gpu", "at"), {"schema": S4})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gpu: Mapped[str] = mapped_column(Text)
    offer_id: Mapped[int | None] = mapped_column(BigInteger)
    dph: Mapped[float] = mapped_column(Float)
    reliability: Mapped[float | None] = mapped_column(Float)
    hours: Mapped[float | None] = mapped_column(Float)
    cost: Mapped[float | None] = mapped_column(Float)


# ---------------------------------------------------------------- S5, policy


class PolicySwitch(Base):
    """S5's switch over a policy's default (vsm.POLICIES): enforced or not, and in whose words."""

    __tablename__ = "policy_switches"
    __table_args__ = {"schema": S5}

    policy: Mapped[str] = mapped_column(Text, primary_key=True)
    enforced: Mapped[bool] = mapped_column(Boolean)
    words: Mapped[str] = mapped_column(Text, default="", server_default="")
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyException(Base):
    """A written exception: the runs a policy does not govern, and the reason."""

    __tablename__ = "policy_exceptions"
    __table_args__ = {"schema": S5}

    policy: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    adopted: Mapped[str] = mapped_column(Text, default="", server_default="")
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")  # what else was written (follow_ups)

    matches: Mapped[list[PolicyExceptionMatch]] = relationship(
        back_populates="exception", cascade="all, delete-orphan", order_by="PolicyExceptionMatch.ordinal"
    )


class PolicyExceptionMatch(Base):
    """A run an exception covers, by its name, or by a glob over names."""

    __tablename__ = "policy_exception_matches"
    __table_args__ = (CheckConstraint("kind in ('run', 'pattern')", name="match_kind"), {"schema": S5})

    policy: Mapped[str] = mapped_column(
        Text, ForeignKey(f"{S5}.policy_exceptions.policy", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)

    exception: Mapped[PolicyException] = relationship(back_populates="matches")


class CharterTerm(Base):
    """A change to one of the charter's terms (s5_policy/charter.DEFAULTS); the latest per term is in force."""

    __tablename__ = "charter_terms"
    __table_args__ = (Index("charter_terms_term", "term", "id"), {"schema": S5})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(Text)
    value: Mapped[dict | list | str | int | float | bool] = mapped_column(JSONB)
    words: Mapped[str] = mapped_column(Text, default="", server_default="")
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
