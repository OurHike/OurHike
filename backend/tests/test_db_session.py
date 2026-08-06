"""A real sanity check that Postgres-via-SQLAlchemy works end to end.

Not just "does the app import cleanly" - this defines a tiny throwaway
table, inserts a row, queries it back through a real session, and asserts
the value round-trips correctly. If the engine, the driver, or the session
wiring regresses on basic DML/transaction behavior, this is what would catch
it, before any endpoint test has to.

It doubles as the fixture's own smoke test: a failure here with a connection
error means no local Postgres is running, which is `scripts/local-postgres.sh`
away rather than anything wrong with the code under test.
"""

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import declarative_base

# Deliberately a separate, local declarative base - this table is a
# throwaway fixture for this test only, not part of the app's real schema
# in app.db.base. conftest's teardown reflects the live schema rather than
# reading Base.metadata, which is what makes sure this one gets dropped too.
ThrowawayBase = declarative_base()


class Widget(ThrowawayBase):
    __tablename__ = "widgets"

    # A plain autoincrementing integer PK, which SQLAlchemy renders as
    # `SERIAL` here. The app's own models use app-generated UUID strings
    # instead (see app/models/hike.py) - that is a modeling choice about ids
    # coming from Supabase and the client, not a dialect limitation, and this
    # throwaway table has no reason to copy it.
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


def test_can_create_and_query_a_table_against_the_test_engine(db_engine, db_session):
    ThrowawayBase.metadata.create_all(db_engine)

    widget = Widget(name="trekking pole")
    db_session.add(widget)
    db_session.commit()

    result = db_session.execute(select(Widget).where(Widget.name == "trekking pole")).scalar_one()

    # The id was never supplied - the database minted it, which is the half of
    # this that a metadata-only check would not exercise.
    assert result.id is not None
    assert result.name == "trekking pole"
