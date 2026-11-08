"""Alembic's environment for Thorp's Postgres models (thorp/viable/s3_control/models.py).

The database is Thorp's own cluster: THORP_PG, or postgresql://thorp@localhost:5433/thorp (fitout_store.url()).

    uv run alembic upgrade head                          # bring the database to the latest models
    uv run alembic revision --autogenerate -m "what"     # after changing the models
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from thorp.viable import records
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


OURS = (models.SCHEMA, models.GAME_SCHEMA, models.SHIP_SCHEMA, *records.SCHEMAS)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_object=_include,
        version_table_schema=models.SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        for schema in (models.SCHEMA, models.GAME_SCHEMA, models.SHIP_SCHEMA):  # the viable systems' schemas are
            connection.exec_driver_sql(f"create schema if not exists {schema}")  # made by their migration, not here
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=_include,
            version_table_schema=models.SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
