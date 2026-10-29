"""The engine options that only matter in production.

`app/db/session.py`'s `engine_options` is a pure function precisely so these
can be asserted without a database, a pooler, or a deployment - the settings
it decides are ones whose absence shows up as a 500 in production and as
nothing at all locally (see tests/test_pooler.py for the other half, which
does open a real connection through a real pooler).
"""

from app.db.session import engine_options

DIRECT_URL = "postgresql+psycopg://ourhike:ourhike@localhost:5432/ourhike_dev"
POOLED_URL = "postgresql+psycopg://postgres.abc:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"


def test_prepared_statements_are_off_by_default():
    """The safe default, and it does not depend on spotting a pooler.

    A heuristic on the host or the port would be one dashboard redesign away
    from silently switching prepared statements back on in production, so the
    setting is unconditional rather than clever.
    """
    for url in (DIRECT_URL, POOLED_URL):
        options = engine_options(url, prepared_statements=False)

        assert options["connect_args"] == {"prepare_threshold": None}


def test_prepared_statements_can_be_turned_back_on():
    """The escape hatch for a direct connection - and it must leave
    `connect_args` off entirely rather than passing a threshold of its own,
    so psycopg's own default is what applies."""
    options = engine_options(DIRECT_URL, prepared_statements=True)

    assert "connect_args" not in options


def test_pre_ping_is_always_on():
    """A round trip on checkout, against a connection any pooler, load
    balancer or idle timeout may have closed under us."""
    for prepared_statements in (True, False):
        options = engine_options(DIRECT_URL, prepared_statements=prepared_statements)

        assert options["pool_pre_ping"] is True


def test_bound_values_never_reach_an_exceptions_text():
    """A traceback from a scheduled job is a public Actions log line, and
    `[parameters: ...]` would put a month's counts in it."""
    for prepared_statements in (True, False):
        assert engine_options(DIRECT_URL, prepared_statements=prepared_statements)["hide_parameters"] is True


def test_the_apps_engine_was_built_with_hidden_parameters():
    from app.db.session import engine

    assert engine.hide_parameters is True


def test_a_failed_statement_on_such_an_engine_does_not_name_its_values(db_engine):
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    from app.config import settings

    engine = create_engine(db_engine.url, **engine_options(settings.database_url, prepared_statements=False))
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1 / (:visits - :visits)"), {"visits": 4242})
    except DBAPIError as failure:
        assert "4242" not in str(failure)
    else:
        raise AssertionError("dividing by zero did not fail")
    finally:
        engine.dispose()


def test_a_non_psycopg_driver_is_not_handed_a_psycopg_argument():
    """`connect_args` is passed straight to the DBAPI.

    `prepare_threshold` is psycopg's; handing it to another driver would
    raise a TypeError on the first connection rather than at startup, which
    is the worst place to learn it. Nothing configures a different driver
    today - this is here so that changing one does not break the other.
    """
    options = engine_options(
        "postgresql+psycopg2://ourhike:ourhike@localhost:5432/ourhike_dev",
        prepared_statements=False,
    )

    assert "connect_args" not in options
    assert options["pool_pre_ping"] is True
