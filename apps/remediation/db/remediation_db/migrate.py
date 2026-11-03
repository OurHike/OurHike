"""Applies migrations/*.sql, in name order, each once.

    python -m remediation_db.migrate --database-url postgresql://... [--dry-run]

A reviewed, deliberate step, never run on deploy (backend/README.md's rule for
OurHike's own migrations, for its reasons). Each file runs in a transaction of
its own and is recorded in remediation.migration with its SHA-256, and a file
already applied whose text has since changed stops the run: an applied
migration is history, and a change to one is a new file.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"

BOOKKEEPING = """
create schema if not exists remediation;
create table if not exists remediation.migration (
  name text primary key,
  sha256 text not null,
  applied_at timestamptz not null default now()
);
"""

#: What a Supabase project has and a plain Postgres does not. Checked first, so
#: a migration aimed at the wrong database stops before it changes anything.
PRECONDITIONS = (
    ("auth.users", "select to_regclass('auth.users') is not null"),
    ("auth.uid()", "select to_regprocedure('auth.uid()') is not null"),
    ("storage.objects", "select to_regclass('storage.objects') is not null"),
    ("the roles anon and authenticated", "select count(*) = 2 from pg_roles where rolname in ('anon', 'authenticated')"),
    # The remediation functions read storage.objects as their owner. Supabase's
    # postgres role bypasses row-level security; a role that did not would see
    # no objects there, and every photo would be refused as not arrived.
    (
        "a migrating role that bypasses row-level security or owns storage.objects",
        "select rolbypassrls or rolsuper or exists (select from pg_tables where schemaname = 'storage'"
        " and tablename = 'objects' and tableowner = current_user) from pg_roles where rolname = current_user",
    ),
)


class MigrationError(RuntimeError):
    pass


def files() -> list[Path]:
    return sorted(MIGRATIONS.glob("*.sql"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pending(connection: psycopg.Connection) -> list[Path]:
    """The files not yet applied. Raises MigrationError if an applied one
    changed. Reads only: a dry run on a project never migrated leaves it as it
    was, with no remediation schema (the sixth review pass, finding 7)."""
    if connection.execute("select to_regclass('remediation.migration') is null").fetchone()[0]:
        applied = {}
    else:
        applied = dict(connection.execute("select name, sha256 from remediation.migration").fetchall())
    for path in files():
        if path.name in applied and applied[path.name] != digest(path):
            raise MigrationError(f"{path.name} was applied with different text; write a new migration instead")
    return [path for path in files() if path.name not in applied]


def check_preconditions(connection: psycopg.Connection) -> None:
    for what, query in PRECONDITIONS:
        if not connection.execute(query).fetchone()[0]:
            raise MigrationError(f"this database has no {what}: is it a Supabase project?")


def migrate(database_url: str, *, dry_run: bool = False) -> list[str]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        check_preconditions(connection)
        todo = pending(connection)
        if dry_run:
            return [path.name for path in todo]
        with connection.transaction():
            connection.execute(BOOKKEEPING)
        for path in todo:
            with connection.transaction():
                connection.execute(path.read_text())
                connection.execute("insert into remediation.migration (name, sha256) values (%s, %s)", (path.name, digest(path)))
        return [path.name for path in todo]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--dry-run", action="store_true", help="list what would be applied, apply nothing")
    args = parser.parse_args(argv)
    try:
        done = migrate(args.database_url, dry_run=args.dry_run)
    except MigrationError as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 1
    verb = "would apply" if args.dry_run else "applied"
    print(f"{verb}: {', '.join(done) if done else 'nothing, the schema is current'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
