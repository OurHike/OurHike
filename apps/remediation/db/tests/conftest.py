"""The remediation schema on a real Postgres, called the way PostgREST calls it.

The database is the one REMEDIATION_TEST_DATABASE_URL names, default `remediation_test`
on the local Postgres backend/scripts/local-postgres.sh starts. It must be named
`*_test`, because each session drops and rebuilds its `remediation`, `auth` and
`storage` schemas: tests/supabase_stand_ins.sql stands in for the last two, and
the migrations are applied by remediation_db.migrate, which is how they are tested.

A call "as" someone is what PostgREST does with a request: within one
transaction, `set local role` to anon or authenticated and put the token's
claims where auth.uid() and auth.jwt() read them. Row-level security and the
grants then decide, exactly as they would for the app.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

from remediation_db import migrate

DATABASE_URL = os.environ.get("REMEDIATION_TEST_DATABASE_URL", "postgresql://ourhike:ourhike@localhost:5432/remediation_test")
STAND_INS = Path(__file__).with_name("supabase_stand_ins.sql")
ROLES = ("anon", "authenticated", "service_role", "remediation_loader")

#: Invented RIMS_IDs: two that need work (claimable), one that does not.
SITE = "4d9ce529-d198-40ee-9a11-02b0184b5270"
NEIGHBOUR = "f599a2a9-c5c4-4e62-c303-2ebb43e75017"
SCORES_WELL = "4a02a65e-cddb-402b-9b6b-2624b01c2be8"
CLUB = "Example Trail Club"
SITES = [
    {"rims_id": SITE, "club": CLUB, "action": "close_restore"},
    {"rims_id": NEIGHBOUR, "club": CLUB, "action": "harden"},
    {"rims_id": SCORES_WELL, "club": "Second Example Club", "action": "leave"},
]
BUCKET = "remediation-photos"


def _require_disposable(url: str) -> None:
    name = psycopg.conninfo.conninfo_to_dict(url).get("dbname", "")
    if not name.endswith("_test"):
        raise pytest.UsageError(f"REMEDIATION_TEST_DATABASE_URL must name a *_test database, not {name!r}")


def _ensure_database(url: str) -> None:
    info = psycopg.conninfo.conninfo_to_dict(url)
    name = info["dbname"]
    admin = psycopg.conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as connection:
        if not connection.execute("select 1 from pg_database where datname = %s", (name,)).fetchone():
            connection.execute(f'create database "{name}"')


def _ensure_roles(connection: psycopg.Connection) -> None:
    missing = [r for r in ROLES if not connection.execute("select 1 from pg_roles where rolname = %s", (r,)).fetchone()]
    try:
        for role in missing:
            connection.execute(f'create role "{role}" nologin')
        user = connection.execute("select current_user").fetchone()[0]
        for role in ROLES:
            if not connection.execute("select pg_has_role(current_user, %s, 'member')", (role,)).fetchone()[0]:
                connection.execute(f'grant "{role}" to "{user}"')
    except psycopg.errors.InsufficientPrivilege as exc:
        raise pytest.UsageError(
            "the test login cannot create Supabase's roles: run apps/remediation/db/scripts/local-roles.sh once"
        ) from exc


@pytest.fixture(scope="session")
def database_url() -> str:
    _require_disposable(DATABASE_URL)
    _ensure_database(DATABASE_URL)
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        _ensure_roles(connection)
        for policy in connection.execute(
            "select policyname from pg_policies where schemaname = 'storage' and tablename = 'objects'"
        ).fetchall():
            connection.execute(f'drop policy "{policy[0]}" on storage.objects')
        connection.execute("drop schema if exists remediation cascade")
        connection.execute("drop schema if exists storage cascade")
        connection.execute("drop schema if exists auth cascade")
        connection.execute(STAND_INS.read_text())
    assert migrate.migrate(DATABASE_URL) == [path.name for path in migrate.files()]
    return DATABASE_URL


@pytest.fixture
def db(database_url):
    """A connection as the schema's owner, emptied after each test."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("select remediation.load_sites(%s)", (Jsonb(SITES),))
        yield Db(connection)
        connection.execute(
            "truncate remediation.site, remediation.site_load, remediation.profile, remediation.site_list, remediation.site_list_item, remediation.club_weights,"
            " remediation.claim, remediation.follow_up, remediation.photo, remediation.photo_receipt,"
            " storage.objects, auth.users cascade"
        )


def uid(name: str) -> str:
    """A stable user id for a test's name for someone."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"remediation-test:{name}"))


class Refused(Exception):
    pass


class Db:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def _user(self, name: str, *, anonymous: bool = False) -> str:
        user_id = uid(name)
        self.connection.execute(
            "insert into auth.users (id, is_anonymous) values (%s, %s) on conflict do nothing", (user_id, anonymous)
        )
        return user_id

    @contextmanager
    def acting(self, who: str | None, *, anonymous: bool = False):
        """A transaction as `who` (signed in), or as anon when `who` is None."""
        with self.connection.transaction():
            if who is None:
                claims = {"role": "anon"}
                self.connection.execute("set local role anon")
            else:
                claims = {"sub": self._user(who, anonymous=anonymous), "role": "authenticated", "is_anonymous": anonymous}
                self.connection.execute("set local role authenticated")
            self.connection.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
            yield self.connection

    def call(self, who: str | None, function: str, *args, anonymous: bool = False):
        """remediation.<function>(args) as `who`; its result, decoded."""
        placeholders = ", ".join(["%s"] * len(args))
        with self.acting(who, anonymous=anonymous) as connection:
            return connection.execute(f"select remediation.{function}({placeholders})", args).fetchone()[0]

    def refused(self, who: str | None, function: str, *args, anonymous: bool = False) -> psycopg.Error:
        """The error remediation.<function>(args) raises as `who`; fails the test if it succeeds."""
        try:
            self.call(who, function, *args, anonymous=anonymous)
        except psycopg.Error as error:
            return error
        raise AssertionError(f"remediation.{function}{args} succeeded as {who}")

    def upload(self, who: str, claim_id: str, client_id: str = "photo-1") -> str:
        """What Storage does with a photo upload: insert its object row as the uploader."""
        name = self.object_name(claim_id, client_id)
        with self.acting(who) as connection:
            connection.execute(
                "insert into storage.objects (bucket_id, name, owner, owner_id) values (%s, %s, %s, %s)",
                (BUCKET, name, uid(who), uid(who)),
            )
        return name

    def object_name(self, claim_id: str, client_id: str) -> str:
        """A photo's name in the bucket: its claim, and the phone's id for it."""
        return f"{claim_id}/{client_id}.jpg"

    def sees(self, who: str | None, name: str, *, anonymous: bool = False) -> bool:
        """Whether Storage would let `who` download the object, or sign a link to it."""
        with self.acting(who, anonymous=anonymous) as connection:
            return connection.execute("select exists (select from storage.objects where name = %s)", (name,)).fetchone()[0]

    def owner(self, query: str, *args):
        return self.connection.execute(query, args or None).fetchall()

    def age(self, claim_id: str, **columns) -> None:
        """Moves a claim's times, as the passing of days would."""
        sets = ", ".join(f"{column} = {value}" for column, value in columns.items())
        self.connection.execute(f"update remediation.claim set {sets} where id = %s", (claim_id,))


def status(error: psycopg.Error) -> str:
    """The PTnnn code PostgREST turns into an HTTP status, or the SQLSTATE."""
    return error.sqlstate or ""
