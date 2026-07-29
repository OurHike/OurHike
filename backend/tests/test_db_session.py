"""A real sanity check that DuckDB-via-SQLAlchemy works end to end.

Not just "does the app import cleanly" - this defines a tiny throwaway
table, inserts a row, queries it back through a real session, and asserts
the value round-trips correctly. If duckdb-engine ever regresses on basic
DML/transaction behavior, this is what would catch it.
"""

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import declarative_base

# Deliberately a separate, local declarative base - this table is a
# throwaway fixture for this test only, not part of the app's real schema
# in app.db.base.
ThrowawayBase = declarative_base()


class Widget(ThrowawayBase):
    __tablename__ = "widgets"

    # autoincrement=False is deliberate, not stylistic: SQLAlchemy's default
    # "auto" autoincrement on a single-column Integer primary key renders as
    # `SERIAL` on duckdb-engine (it reuses PostgreSQL's DDL compiler), and
    # DuckDB has no `SERIAL` type - `CREATE TABLE` fails with a
    # CatalogException. This test supplies its own ids anyway, so disabling
    # autoincrement sidesteps a real dialect gap rather than masking it; see
    # backend/README.md for the same note aimed at real model authors.
    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String, nullable=False)


def test_can_create_and_query_a_table_against_the_duckdb_test_engine(db_engine, db_session):
    ThrowawayBase.metadata.create_all(db_engine)

    db_session.add(Widget(id=1, name="trekking pole"))
    db_session.commit()

    result = db_session.execute(select(Widget).where(Widget.name == "trekking pole")).scalar_one()

    assert result.id == 1
    assert result.name == "trekking pole"
