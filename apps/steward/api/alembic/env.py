"""Reads STEWARD_DATABASE_URL alone, not the whole Settings, so a migration
needs only the database and none of the sign-in configuration."""

import os

from sqlalchemy.pool import NullPool

from alembic import context
from steward_api.config import Settings
from steward_api.db import make_engine
from steward_api.models import Base

url = (
    context.config.attributes.get("database_url")
    or os.environ.get("STEWARD_DATABASE_URL")
    or Settings.model_fields["database_url"].default
)


def run() -> None:
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(url, poolclass=NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run()
