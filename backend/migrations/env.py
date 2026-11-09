"""Alembic's environment for Thorp's Postgres models (thorp/viable/s3_control/models.py).

The database is Thorp's own cluster: THORP_PG, or postgresql://thorp@localhost:5433/thorp (fitout_store.url()).

    uv run alembic upgrade head                          # bring the database to the latest models
    uv run alembic revision --autogenerate -m "what"     # after changing the models
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from thorp import ledger_store  # noqa: F401  (registers the ledger tables on Base.metadata)
from thorp import manifest_store  # noqa: F401  (registers the library's books table on Base.metadata)
from thorp.viable import records
from thorp.viable.s2_coordination import queue_store  # noqa: F401  (registers the queue tables on Base.metadata)
from thorp.viable.s3_control import fitout_store, models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata


def _url() -> str:
    u = fitout_store.url()
    return u.replace("postgresql://", "postgresql+psycopg://", 1) if u.startswith("postgresql://") else u


def _include(obj, name, type_, reflected, compare_to):
    """Only Thorp's own schemas (the fitouts, the Wager, the ships, and one per viable system); any other table is not ours."""
    return type_ != "table" or getattr(obj, "schema", None) in OURS


OURS = (*records.SCHEMAS, "fitout", "game", "ship")  # the systems' schemas, and the three they replaced (history)
VERSIONS = "s3"  # Alembic's own record of the revision, kept by S3 (it was in `fitout` until the systems took over)


def _version_schema(connection) -> str:
    """Where the version table is: s3; a database migrated before the systems took their schemas has it in
    `fitout`, and once its tables have moved to s3 the version table follows (and `fitout`, then empty, goes)."""
    def has(schema: str, table: str = "alembic_version") -> bool:
        return bool(connection.exec_driver_sql(
            "select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = %s and c.relname = %s",
            (schema, table)).first())  # fmt: skip

    if has(VERSIONS):
        return VERSIONS
    if has("fitout"):
        if not has("s3", "fitouts"):
            return "fitout"  # the tables have not moved yet: the revision stays beside them until they do
        connection.exec_driver_sql(f"alter table fitout.alembic_version set schema {VERSIONS}")
        connection.exec_driver_sql("""do $$ begin if not exists (select 1 from pg_class c join pg_namespace n
            on n.oid = c.relnamespace where n.nspname = 'fitout') then drop schema fitout; end if; end $$""")
        return VERSIONS
    connection.exec_driver_sql(f"create schema if not exists {VERSIONS}")  # a new database
    return VERSIONS


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_object=_include,
        version_table_schema=VERSIONS,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        versions = _version_schema(connection)  # every schema is made by its own migration, not here
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=_include,
            version_table_schema=versions,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
