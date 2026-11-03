"""The migrations apply, once, to something that looks like a Supabase project."""

import psycopg
import pytest
from conftest import STAND_INS

from remediation_db import migrate


def test_every_migration_is_applied_and_a_second_run_applies_nothing(database_url):
    assert migrate.migrate(database_url) == []
    with psycopg.connect(database_url) as connection:
        applied = [row[0] for row in connection.execute("select name from remediation.migration order by name")]
    assert applied == [path.name for path in migrate.files()]


def test_an_applied_migration_whose_text_changed_stops_the_run(database_url, monkeypatch):
    first, real = migrate.files()[0], migrate.digest
    monkeypatch.setattr(migrate, "digest", lambda path: "0" * 64 if path == first else real(path))
    with pytest.raises(migrate.MigrationError, match="write a new migration"):
        migrate.migrate(database_url)


def test_a_database_that_is_not_a_supabase_project_is_refused_before_anything_changes(database_url):
    plain = psycopg.conninfo.make_conninfo(database_url, dbname="postgres")
    with pytest.raises(migrate.MigrationError, match="is it a Supabase project"):
        migrate.migrate(plain)


def test_a_dry_run_on_a_project_never_migrated_changes_nothing(database_url):
    # The sixth pass's finding 7: it used to create the remediation schema and its
    # bookkeeping table on the way to listing what it would do.
    fresh = psycopg.conninfo.make_conninfo(database_url, dbname="remediation_dry_run_test")
    with psycopg.connect(psycopg.conninfo.make_conninfo(database_url, dbname="postgres"), autocommit=True) as admin:
        admin.execute("drop database if exists remediation_dry_run_test")
        admin.execute("create database remediation_dry_run_test")
    try:
        with psycopg.connect(fresh, autocommit=True) as connection:
            connection.execute(STAND_INS.read_text())
        assert migrate.migrate(fresh, dry_run=True) == [path.name for path in migrate.files()]
        with psycopg.connect(fresh) as connection:
            assert connection.execute("select to_regnamespace('remediation')").fetchone()[0] is None
    finally:
        with psycopg.connect(psycopg.conninfo.make_conninfo(database_url, dbname="postgres"), autocommit=True) as admin:
            admin.execute("drop database if exists remediation_dry_run_test")
