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


# ---------------------------------------------------------------- phase 1b


class OutsideReading(Base):
    """S4: a reading of an outside model (or of the field): a deck, a knockout, the logic deck, a book list scored,
    the chain grades. `name` is what the file under data/compare/ was called (deck-EleutherAI--pythia-14m), so a
    reading is found as it always was; `kind` and `model` say what it is and of whom."""

    __tablename__ = "outside_readings"
    __table_args__ = (Index("outside_readings_kind_model", "kind", "model"), {"schema": S4})

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)  # chain-grades, deck, knockout, knockout-deck, logic, scored, other
    model: Mapped[str | None] = mapped_column(Text)
    reading: Mapped[dict] = mapped_column(JSONB)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Crowning(Base):
    """S1: a ship crowned its size's version n (Thorp 9m v2): the ship, its chaining lift, when. Was
    thorp-versions.json. A version rises only when a new ship beats the last by more than the noise."""

    __tablename__ = "crownings"
    __table_args__ = (Index("crownings_ship", "ship_key"), {"schema": S1})

    preset: Mapped[str] = mapped_column(Text, primary_key=True)
    v: Mapped[int] = mapped_column(Integer, primary_key=True)
    ship_key: Mapped[str] = mapped_column(Text)
    ship: Mapped[str] = mapped_column(Text)
    chaining_lift: Mapped[float] = mapped_column(Float)
    crowned: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StoreList(Base):
    """S1: a ship's store, frozen (scripts/make_stores.py): the list it is, its books and tokens, how it was ranked,
    the list's content hash (the stores rule refuses a store changed since). Was stores.json."""

    __tablename__ = "stores"
    __table_args__ = {"schema": S1}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    path: Mapped[str] = mapped_column(Text)
    books: Mapped[int] = mapped_column(Integer)
    tokens: Mapped[int] = mapped_column(BigInteger)
    sha1: Mapped[str] = mapped_column(Text)
    measures: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")  # ranked_by, repeat_rate, ...
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Intake(Base):
    """S1: an intake, a book list put through the intake gate (thorp acquire). Was acquisition/intakes/<id>.json."""

    __tablename__ = "intakes"
    __table_args__ = {"schema": S1}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    list: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    started: Mapped[str | None] = mapped_column(Text)
    finished: Mapped[str | None] = mapped_column(Text)
    record: Mapped[dict] = mapped_column(JSONB)  # the whole record as acquisition writes it (counts, rules, bytes)


class IntakeVerdict(Base):
    """S1: one book's verdict at the intake gate (or by an older path), as logged. Was acquisition/log.jsonl."""

    __tablename__ = "intake_verdicts"
    __table_args__ = (Index("intake_verdicts_intake", "intake_id"), Index("intake_verdicts_book", "book_id"),
                      {"schema": S1})  # fmt: skip

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    intake_id: Mapped[str | None] = mapped_column(Text)  # none for a book taken in by an older path
    how: Mapped[str | None] = mapped_column(Text)
    book_id: Mapped[str | None] = mapped_column(Text)
    verdict: Mapped[str | None] = mapped_column(Text)
    entry: Mapped[dict] = mapped_column(JSONB)  # the rest: title, authors, source, set, refused, notes, ...


class IntakeHolder(Base):
    """S2's record of the intake taking books in now (the lock stays an flock). Was acquisition/intake.json."""

    __tablename__ = "intake_holder"
    __table_args__ = {"schema": S2}

    lock: Mapped[str] = mapped_column(Text, primary_key=True, default="intake", server_default="intake")
    id: Mapped[str] = mapped_column(Text)
    list: Mapped[str | None] = mapped_column(Text)
    pid: Mapped[int] = mapped_column(Integer)
    since: Mapped[str] = mapped_column(Text)


class TokeniserRecord(Base):
    """S1: a shared tokeniser, registered when it is trained: its id (the hash of its books and settings), the
    settings, the per-book stats. Its files (spm.model and its own settings, books and stats beside it) stay the
    artifact a voyage reads, here or aboard a hired box; this is the register that ties it to its books."""

    __tablename__ = "tokenisers"
    __table_args__ = {"schema": S1}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    path: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSONB)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TokeniserBook(Base):
    """S1: a book a tokeniser was trained on."""

    __tablename__ = "tokeniser_books"
    __table_args__ = (Index("tokeniser_books_book", "book_id"), {"schema": S1})

    tokeniser_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{S1}.tokenisers.id", ondelete="CASCADE"), primary_key=True)
    book_id: Mapped[str] = mapped_column(Text, primary_key=True)


class TableTalk(Base):
    """S1: a question put to a ship at the table and its answer (thorp/table.py). Was table/<voyage>.jsonl."""

    __tablename__ = "table_talk"
    __table_args__ = (Index("table_talk_voyage", "voyage", "at"), {"schema": S1})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    voyage: Mapped[str] = mapped_column(Text)  # the voyage's name, as the file was named
    run_id: Mapped[str | None] = mapped_column(Text)
    step: Mapped[int | None] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    temperature: Mapped[float | None] = mapped_column(Float)
    seed: Mapped[int | None] = mapped_column(Integer)
    stopped: Mapped[str | None] = mapped_column(Text)


def tables():
    """The tables this module defines (the records), not the fitouts, the Wager or the ships beside them."""
    return [m.local_table for m in Base.registry.mappers if m.class_.__module__ == __name__]


# ---------------------------------------------------------------- the schedule (S2), and its judge (S5)


class ScheduledJob(Base):
    """S2: a job Thorp runs on a schedule (Justin, 8 November: "thorps schedules tasks shouldn't be in claude code, but
    rather part of our VSM model and in postgres"). A cron (five fields, this Mac's local time) or one time; a job is
    either a command, or a prompt put to the judge (S5's choice of Thorp's most capable model). `system` is the VSM
    system that owns the job's purpose; `limits` its bounds (max_minutes, cwd)."""

    __tablename__ = "schedule_jobs"
    __table_args__ = (
        CheckConstraint("kind in ('judge', 'command')", name="job_kind"),
        CheckConstraint("(cron is null) <> (fire_at is null)", name="job_when"),
        CheckConstraint("system in ('S1', 'S2', 'S3', 'S3*', 'S4', 'S5')", name="job_system"),
        {"schema": S2},
    )

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    system: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    cron: Mapped[str | None] = mapped_column(Text)
    fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    prompt: Mapped[str | None] = mapped_column(Text)  # for the judge, word for word
    command: Mapped[str | None] = mapped_column(Text)  # for a command (sh -c)
    limits: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    source: Mapped[str] = mapped_column(Text, default="", server_default="")  # where it came from
    words: Mapped[str] = mapped_column(Text, default="", server_default="")  # who set it up or changed it, when
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # due times before this are not owed

    firings: Mapped[list[JobFiring]] = relationship(back_populates="job", order_by="JobFiring.id")


class JobFiring(Base):
    """S2: one firing of a job: the time it was due, who judged it (or the command), how it ended, what it said."""

    __tablename__ = "schedule_firings"
    __table_args__ = (
        Index("schedule_firings_once", "job_key", "due_at", unique=True),  # a due time fires once, whatever ticks
        CheckConstraint("outcome in ('running', 'ok', 'failed', 'timeout', 'missed')", name="firing_outcome"),
        {"schema": S2},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_key: Mapped[str] = mapped_column(Text, ForeignKey(f"{S2}.schedule_jobs.key", ondelete="CASCADE"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    judge: Mapped[str | None] = mapped_column(Text)  # the judge's name (claude, a Thorp ship), or 'command'
    outcome: Mapped[str] = mapped_column(Text, default="running", server_default="running")
    exit_code: Mapped[int | None] = mapped_column(Integer)
    pid: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")  # the end of what it said
    output_path: Mapped[str | None] = mapped_column(Text)  # all it said, under data/runs/schedule/

    job: Mapped[ScheduledJob] = relationship(back_populates="firings")


class Judge(Base):
    """S5: which model judges the jobs that need judgment, "Thorp's most capable model" (Justin: "claude initially but
    eventually a thorp model"). Every choice kept; the latest is in force. `command` is the argv the prompt is given to
    (on stdin), so a Thorp model takes over by a new row, not a change of code."""

    __tablename__ = "judges"
    __table_args__ = {"schema": S5}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)  # claude, or thorp:<ship>
    command: Mapped[list] = mapped_column(JSONB)  # e.g. ["claude", "-p"]; the prompt arrives on stdin
    words: Mapped[str] = mapped_column(Text, default="", server_default="")
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
