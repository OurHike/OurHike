"""SQLAlchemy declarative base.

Every ORM model in the app imports `Base` from here and subclasses it. This
module (and its accumulated `Base.metadata`) is also what alembic/env.py
points `target_metadata` at for autogenerate - so any new model must be
imported somewhere reachable from here (or from alembic/env.py directly)
before autogenerate will see it.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
