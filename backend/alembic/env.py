import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# alembic runs with backend/ as the working directory, but env.py itself
# lives in backend/alembic/ - add backend/ to sys.path so `import app...`
# below resolves the same way it does for the app and the test suite.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# --- DuckDB/Alembic dialect gap, worth flagging explicitly -----------------
# duckdb-engine registers a real SQLAlchemy *dialect* ("duckdb"), but ships
# no Alembic DDL *implementation* for it. Without this, Alembic's
# `DefaultImpl.get_by_dialect()` raises `KeyError: 'duckdb'` immediately on
# any local migration run - not a modeling difference, a missing piece of
# integration glue. The fix below registers one by reusing PostgreSQL's
# impl, since duckdb-engine's own compiler is itself PostgreSQL-derived
# (see the SERIAL-vs-DuckDB note in tests/test_db_session.py for the same
# lineage causing a real, worked-around incompatibility elsewhere). This
# only affects the local DuckDB dev path - CI/production run migrations
# against real Postgres, which already has Alembic's native impl.
from alembic.ddl.postgresql import PostgresqlImpl  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402


class DuckDBImpl(PostgresqlImpl):
    __dialect__ = "duckdb"


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Real DATABASE_URL, not the alembic.ini placeholder - one source of truth
# (app.config.settings) shared with app/db/session.py, so migrations always
# run against the same database the app itself would connect to.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# app.db.base's metadata - every model must be importable from there (or
# imported below) for autogenerate to see it.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
