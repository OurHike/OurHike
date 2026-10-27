"""The migrations apply, once, to something that looks like a Supabase project."""

import psycopg
import pytest

from steward_db import migrate


def test_every_migration_is_applied_and_a_second_run_applies_nothing(database_url):
    assert migrate.migrate(database_url) == []
    with psycopg.connect(database_url) as connection:
        applied = [row[0] for row in connection.execute("select name from steward.migration order by name")]
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
