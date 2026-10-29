"""Back production's database up: dump it, restore the dump, compare, seal it.

#1908 - Back production's database up nightly to a private R2 bucket, because
Supabase Free keeps no backups. `.github/workflows/backup-database.yml` runs the
three stages below in order and uploads what `seal` writes; LAUNCH_CHECKLIST.md
section 5b is how a person sets it up and restores from it.

    python backup_database.py dump   --workdir DIR [--pg-image postgres:17]
    python backup_database.py verify --workdir DIR --scratch-url URL [--pg-image postgres:17]
    python backup_database.py seal   --workdir DIR

`dump` reads BACKUP_DATABASE_URL and `seal` reads BACKUP_AGE_RECIPIENT, both
from the environment, so neither ever appears on a command line.

WHAT GOES IN. Two custom-format archives, because `pg_dump --table` overrides
`--schema` rather than adding to it:

- `public.dump`: every table the app owns, schema and rows.
- `auth.dump`: `auth.users` and `auth.identities`. `profiles.id` is the Supabase
  Auth user id (backend/README.md), so a restore without these turns every
  hiker who signs in again into a stranger with an empty profile.

Nothing else goes in, so `dump` refuses, before pg_dump runs, when a table in
any other schema may hold rows - unless the schema is one Supabase runs itself
(SUPABASE_SCHEMAS). App data in a schema these archives do not reach was
otherwise left out of every backup without a word: the review of #1930 - Back
production's database up nightly: dump, restore and compare, encrypt with age,
upload to a private bucket - found a 500-row `analytics.events` absent from
both archives while `verify` passed. Refusing stops the nightly upload until
the schema is dumped or listed; that is the price of never uploading a backup
that silently leaves data out.

WHY THE RESTORE IS PART OF THE BACKUP. Row-level security is on for every table
(alembic/versions/b3d1c7a94e02_enable_row_level_security.py), and a role it
applies to can produce a dump that looks fine and holds nothing: plain pg_dump
refuses, but `pg_dump --enable-row-security` succeeds with zero rows. Nothing
here passes that flag, and the dumping role holds BYPASSRLS (LAUNCH_CHECKLIST.md
section 5b). `verify` is what catches it if either ever stops being true: it
restores both archives into a throwaway database and fails unless every table
comes back holding exactly the rows `dump` counted in it.

THE COUNT IS EXACT, AND TAKEN IN THE SNAPSHOT pg_dump DUMPS. `dump` holds one
REPEATABLE READ transaction open (`HeldTransaction`), exports its snapshot with
`pg_export_snapshot()`, counts every table there with `count(*)` under
`row_security = off`, and passes the snapshot to both pg_dump runs
(`--snapshot`). The counts and the archives therefore describe the same
instant, so a restored count must EQUAL its source count, and a write landing
between the count and the dump can neither fail a good backup nor hide a short
one. `row_security = off` makes `count(*)` exact for a role with BYPASSRLS and
an error for one without - the same refusal pg_dump gives, which is the safe
failure - where the default would count zero on both sides and pass.

Measured 2026-10-29 on postgres:17 (17.11), as a BYPASSRLS role that is not a
superuser: `count(*)` under `row_security = off` read all 40 rows of an RLS
table, a role without BYPASSRLS got "query would be affected by row-level
security policy", and pg_dump 17 given the held transaction's snapshot dumped
the 40 rows it had counted while a 41st, inserted after the count, was left
out (41 without `--snapshot`). `test_backup_database.py` holds the same on the
local Postgres 16.

The count used to be `pg_stat_user_tables.n_live_tup`, which reads 0 after
crash recovery or a statistics reset, so an empty dump compared against it
passed (the review of #1930 - Back production's database up nightly: dump,
restore and compare, encrypt with age, upload to a private bucket).

@unvalidated: that Supabase's session pooler (Supavisor, port 5432) lets
pg_dump's connection import a snapshot the held connection exported. Session
mode gives each client connection a server connection of its own for its whole
life, which is what an import needs, but nobody has tried it there. If it does
not work, pg_dump stops with `snapshot "..." does not exist` (Postgres 17.11's
message for a snapshot it cannot import, seen 2026-10-29), the dump step fails
and the tracking issue opens: loud rather than wrong. The first configured run
settles it.

SECRETS STAY OUT OF ARGV. The connection string is split into libpq's own
environment variables (PGHOST, PGPASSWORD...) for each tool, and a Docker-run
tool is passed their NAMES (`--env PGPASSWORD`), never their values. No error
this script raises quotes the connection string.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from urllib.parse import parse_qsl, unquote, urlsplit

#: Supavisor's transaction pooler. pg_dump sets session state a transaction
#: pooler does not keep, so the session pooler (5432) or the direct host is
#: the only target that works - migrate.yml explains the three in full.
TRANSACTION_POOLER_PORT = 6543

#: A dump of every hiker's data never crosses the internet in clear. `require`
#: encrypts without checking the server's certificate; `verify-full` with
#: Supabase's CA (sslrootcert=...) is stricter, and under Docker `Tools` mounts
#: that certificate into the container.
ENCRYPTED_SSLMODES = ("require", "verify-ca", "verify-full")

#: The sslmodes that check the server's certificate against a root certificate.
CERTIFICATE_SSLMODES = ("verify-ca", "verify-full")

DUMPED_SCHEMA = "public"
AUTH_TABLES = ("auth.users", "auth.identities")

#: Schemas Supabase creates and runs itself. Their tables hold the platform's
#: state - Auth's sessions, Storage's object index, Realtime's messages, an
#: extension's jobs or queues - not this app's rows, so rows in them do not
#: stop `dump`; `auth.users` and `auth.identities` are dumped all the same.
#: Each one is named on the page given, all under supabase.com/docs/guides/
#: and read 2026-10-29:
#:   auth, storage        "Supabase-managed schemas such as `auth` and `storage`"
#:                        (local-development/declarative-database-schemas)
#:   realtime             `realtime.messages`, which its policies sit on
#:                        (realtime/authorization)
#:   extensions           "Most extensions are installed under the `extensions`
#:                        schema" (database/extensions)
#:   graphql              `graphql.resolve(...)` (database/extensions/pg_graphql)
#:   graphql_public       "core schemas like public and graphql_public"
#:                        (queues/expose-self-hosted-queues)
#:   vault                `vault.secrets` (database/vault)
#:   net                  pg_net "creates its own schema/namespace named "net""
#:                        (database/extensions/pg_net)
#:   cron                 "The extension creates a `cron` schema" (cron)
#:   supabase_migrations  `supabase_migrations.schema_migrations`
#:                        (deployment/database-migrations)
#:   supabase_functions   `supabase_functions.http_request` (database/webhooks)
#:   pgmq                 "Every new Queue creates two tables in the `pgmq`
#:                        schema" (queues/quickstart)
#:   pgmq_public          helper functions "in the `pgmq_public` schema"
#:                        (queues/api)
#:   etl                  "The `etl` schema is reserved for Pipelines"
#:                        (database/replication/pipelines-faq)
#: @unvalidated against production itself: nobody has listed its schemas. One
#: of Supabase's that is missing here - pgsodium's, say, which no page names -
#: stops the dump and is named in the log, the loud direction to be wrong in,
#: and adding it to this tuple is the fix.
SUPABASE_SCHEMAS = (
    "auth", "storage", "realtime", "extensions", "graphql", "graphql_public", "vault", "net", "cron",
    "supabase_migrations", "supabase_functions", "pgmq", "pgmq_public", "etl",
)  # fmt: skip

#: The only hosts `verify` restores into. It drops schemas `public` and `auth`
#: and switches row-level security off in whatever database it is given, so a
#: `--scratch-url` naming anywhere else - production's string pasted into the
#: wrong field, say - is refused before it is touched.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

#: An age X25519 recipient: "age1" and 58 bech32 characters.
AGE_RECIPIENT = re.compile(r"age1[02-9ac-hj-np-z]{58}")

LIVE_ROWS = "live-rows.tsv"
RESTORED_ROWS = "restored-rows.tsv"
MANIFEST = "manifest.json"
ARCHIVES = ("public.dump", "auth.dump")

#: Every table the two pg_dump runs write, each with its label and its quoted
#: name, so `dump` can count each one.
DUMPED_TABLES_SQL = """
select n.nspname || '.' || c.relname, format('%I.%I', n.nspname, c.relname)
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind in ('r', 'p')
  and (n.nspname = 'public' or (n.nspname = 'auth' and c.relname in ('users', 'identities')))
order by 1
"""

#: Tables outside `public` that may hold rows, in schemas that are not
#: Supabase's own: what `dump` refuses over. "May hold rows" is read from the
#: catalog, because the backup role has no grant on a schema nobody told it
#: about and so cannot count one: `reltuples` above 0, or any page on disk
#: (`pg_relation_size`), which also catches a table never analyzed, whose
#: `reltuples` is -1. Both are readable without any grant on the table -
#: measured 2026-10-29 on postgres:17 (17.11), where a role with no grant on
#: its schema read `reltuples` -1 and 24576 bytes for a 500-row table.
#: A table emptied by DELETE keeps its pages until VACUUM, so it can stop a
#: dump it need not: the safe direction to be wrong in.
UNCOVERED_TABLES_SQL = f"""
select n.nspname || '.' || c.relname, c.reltuples::bigint, pg_relation_size(c.oid)
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r'
  and c.relpersistence <> 't'
  and n.nspname <> '{DUMPED_SCHEMA}'
  and n.nspname <> 'information_schema'
  and n.nspname !~ '^pg_'
  and n.nspname <> all (array[{", ".join(f"'{schema}'" for schema in SUPABASE_SCHEMAS)}])
  and (c.reltuples > 0 or pg_relation_size(c.oid) > 0)
order by 1
"""

#: What `HeldTransaction` runs first: the same five settings pg_dump 17.11 sends
#: for its own session (logged with `log_statement = all`, 2026-10-29). The
#: timeouts matter more here than there, because this transaction sits idle
#: while both dumps run, and a timeout that ended it would invalidate the
#: snapshot the second dump has yet to import. `transaction_timeout` exists from
#: Postgres 17 only, hence the guard rather than a plain SET, which a 16 server
#: refuses.
HOLD_SQL = """
begin isolation level repeatable read, read only;
set statement_timeout = 0;
set lock_timeout = 0;
set idle_in_transaction_session_timeout = 0;
set row_security = off;
select set_config('transaction_timeout', '0', false) where current_setting('server_version_num')::int >= 170000
"""

#: The restored tables, each with its label and its quoted name.
RESTORED_TABLES_SQL = """
select n.nspname || '.' || c.relname, format('%I.%I', n.nspname, c.relname)
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind in ('r', 'p') and n.nspname in ('public', 'auth')
order by 1
"""


class Refused(Exception):
    """A setting or a result that must stop the backup, said without quoting any secret."""


def libpq_environment(url: str, *, require_encryption: bool = True) -> dict[str, str]:
    """The libpq environment variables for a connection string, so no command line carries it.

    Refuses the transaction pooler, and - unless `require_encryption` is off,
    which only the scratch database inside the job may do - any `sslmode` that
    would let the dump travel in clear. Defaults a missing `sslmode` to
    `require`, where libpq itself would default to `prefer`.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise Refused("the connection string does not parse as a URL") from None
    if parts.scheme.split("+", 1)[0] not in ("postgresql", "postgres"):
        raise Refused("the connection string is not a postgresql:// URL")
    if not parts.hostname:
        raise Refused("the connection string names no host")
    if port == TRANSACTION_POOLER_PORT:
        raise Refused(
            f"the connection string is on port {TRANSACTION_POOLER_PORT}, Supavisor's transaction pooler. "
            "pg_dump needs one session for its whole run: use the session pooler on 5432."
        )
    query = dict(parse_qsl(parts.query))
    sslmode = query.get("sslmode", "require" if require_encryption else "prefer")
    if require_encryption and sslmode not in ENCRYPTED_SSLMODES:
        raise Refused(f"sslmode={sslmode} would let the dump travel unencrypted; use one of {', '.join(ENCRYPTED_SSLMODES)}")

    env = {
        "PGHOST": parts.hostname,
        "PGPORT": str(port or 5432),
        "PGDATABASE": unquote(parts.path.lstrip("/")) or "postgres",
        "PGSSLMODE": sslmode,
    }
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    if "sslrootcert" in query:
        env["PGSSLROOTCERT"] = query["sslrootcert"]
    return env


@dataclass(frozen=True)
class Tools:
    """Runs pg_dump, pg_restore and psql, on PATH or inside a Docker image.

    The image is how the job gets Postgres 17's tools: pg_dump refuses a
    server newer than itself, and the runner's own client is 16.
    """

    workdir: Path
    image: str | None = None

    def command(
        self, tool: str, args: list[str], pg_env: Mapping[str, str], *, interactive: bool = False
    ) -> tuple[list[str], dict[str, str]]:
        """The argv and environment for one tool. Values travel in the environment only.

        `interactive` keeps the tool's stdin open inside Docker, which
        `HeldTransaction` needs to go on feeding psql statements.
        """
        inherited = {key: value for key, value in os.environ.items() if not key.startswith("PG") and key != "BACKUP_DATABASE_URL"}
        env = {**inherited, **pg_env}
        if self.image is None:
            return [tool, *args], env
        docker = [
            "docker", "run", "--rm", "--network", "host",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--volume", f"{self.workdir}:{self.workdir}",
            "--workdir", str(self.workdir),
        ]  # fmt: skip
        if interactive:
            docker.append("--interactive")
        docker += self._root_certificate(pg_env, env)
        for name in sorted(pg_env):
            docker += ["--env", name]
        return [*docker, self.image, tool, *args], env

    def _root_certificate(self, pg_env: Mapping[str, str], env: dict[str, str]) -> list[str]:
        """The `--volume` that shows the container the root certificate libpq is told to check against.

        The container sees none of the runner's files, so a certificate named
        by `sslrootcert` is mounted at its own absolute path, read-only, and
        PGSSLROOTCERT is rewritten to that path. Without the mount,
        `verify-full` fails with "root certificate file ... does not exist",
        as the review of #1930 - Back production's database up nightly: dump,
        restore and compare, encrypt with age, upload to a private bucket -
        found and `test_backup_database.py` reproduces against a local server.
        The postgres:17 image carries no CA bundle - no ca-certificates
        package, and nothing in /etc/ssl/certs but its own snakeoil
        certificate (measured 2026-10-29 on 17.11) - so `sslrootcert=system`
        cannot work in it; and a checking sslmode with no certificate named
        makes libpq look for `~/.postgresql/root.crt`, which the image does
        not have either. Both are refused by name.
        """
        certificate = pg_env.get("PGSSLROOTCERT")
        if certificate == "system":
            raise Refused(
                "sslrootcert=system trusts the image's own CA bundle, and the postgres image has none: "
                "name Supabase's CA certificate file instead"
            )
        if certificate:
            path = Path(certificate).resolve()
            if not path.is_file():
                raise Refused(f"sslrootcert names {certificate}, which is not a file on this machine")
            env["PGSSLROOTCERT"] = str(path)
            return ["--volume", f"{path}:{path}:ro"]
        if pg_env.get("PGSSLMODE") in CERTIFICATE_SSLMODES:
            raise Refused(
                f"sslmode={pg_env['PGSSLMODE']} checks the server against a root certificate, and inside "
                f"{self.image} there is none: name Supabase's CA certificate with sslrootcert=<path>"
            )
        return []

    def run(self, tool: str, args: list[str], pg_env: Mapping[str, str], *, capture: bool = False) -> str:
        argv, env = self.command(tool, args, pg_env)
        result = subprocess.run(argv, env=env, text=True, capture_output=capture, check=False)
        if result.returncode != 0:
            if capture and result.stderr:
                print(result.stderr, file=sys.stderr, end="")
            raise Refused(f"{tool} exited {result.returncode}")
        return result.stdout if capture else ""


#: psql as a machine reads it: tab-separated rows, no headers, no footers, no
#: ~/.psqlrc, and the first error ends it.
PSQL_FLAGS = ("--no-psqlrc", "--no-align", "--tuples-only", "--field-separator=\t", "--set=ON_ERROR_STOP=1")


def _query(tools: Tools, pg_env: Mapping[str, str], sql: str) -> list[list[str]]:
    out = tools.run("psql", [*PSQL_FLAGS, "--command", sql], pg_env, capture=True)
    return [line.split("\t") for line in out.splitlines() if line]


class HeldTransaction:
    """One psql process holding one transaction open, fed statements on its stdin.

    `pg_dump --snapshot` can import a snapshot only while the transaction that
    exported it is still open, and `psql --command` ends its transaction when
    it returns. So this keeps one psql running for the length of `dump`: each
    `query` writes its SQL followed by `\\echo <marker>`, and reads rows up to
    the marker line. Leaving the `with` block commits and closes the session;
    leaving it on an exception just closes stdin, and Postgres rolls the
    transaction back when the connection goes.
    """

    def __init__(self, tools: Tools, pg_env: Mapping[str, str]) -> None:
        self._tools = tools
        self._pg_env = pg_env
        self._marker = f"ourhike-backup-{uuid.uuid4().hex}"
        self._process: subprocess.Popen[str] | None = None
        self._stderr = None

    def __enter__(self) -> HeldTransaction:
        argv, env = self._tools.command("psql", [*PSQL_FLAGS, "--quiet"], self._pg_env, interactive=True)
        # A file rather than a pipe, so a chatty stderr can never fill a pipe
        # nobody is reading and stall psql mid-answer.
        self._stderr = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        self._process = subprocess.Popen(
            argv, env=env, text=True, encoding="utf-8", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr
        )
        try:
            self.query(HOLD_SQL)
        except BaseException:
            self._close(commit=False)
            self._stderr.close()
            raise
        return self

    def query(self, sql: str) -> list[list[str]]:
        """Run `sql` inside the held transaction and return its rows."""
        process = self._process
        assert process is not None and process.stdin is not None and process.stdout is not None
        try:
            process.stdin.write(f"{sql};\n\\echo {self._marker}\n")
            process.stdin.flush()
        except BrokenPipeError:
            self._exited()
        rows = []
        for line in process.stdout:
            line = line.rstrip("\n")
            if line == self._marker:
                return rows
            if line:
                rows.append(line.split("\t"))
        self._exited()

    def _exited(self) -> NoReturn:
        """psql stopped answering: say why, as `Tools.run` does, without quoting a secret."""
        assert self._process is not None and self._stderr is not None
        code = self._process.wait()
        self._stderr.seek(0)
        said = self._stderr.read()
        if said:
            print(said, file=sys.stderr, end="")
        raise Refused(f"psql exited {code}")

    def __exit__(self, kind: object, value: object, traceback: object) -> None:
        code = self._close(commit=kind is None)
        try:
            if kind is None and code != 0:
                self._exited()
        finally:
            if self._stderr is not None:
                self._stderr.close()

    def _close(self, *, commit: bool) -> int:
        """End the session, committing only when asked, and return psql's exit status."""
        process = self._process
        assert process is not None and process.stdin is not None
        try:
            if commit:
                process.stdin.write("commit;\n")
            process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            return process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()
        finally:
            if process.stdout is not None:
                process.stdout.close()


def _rows_by_catalog(reltuples: int) -> str:
    """`pg_class.reltuples` as a reader should take it: -1 means never counted, not minus one row."""
    return "never counted by the catalog" if reltuples < 0 else f"about {reltuples:,} row(s) by the catalog"


def _counting_sql(tables: list[list[str]]) -> str:
    """One query counting every `(label, quoted name)` in `tables` exactly."""
    return " union all ".join(
        f"select '{label.replace(chr(39), chr(39) * 2)}', count(*) from {quoted}" for label, quoted in tables
    )


def _read_counts(path: Path) -> dict[str, int]:
    rows = (line.split("\t") for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {table: int(count) for table, count in rows}


def _write_counts(path: Path, counts: Mapping[str, int]) -> None:
    path.write_text("".join(f"{table}\t{count}\n" for table, count in sorted(counts.items())), encoding="utf-8")


def compare(dumped: Mapping[str, int], restored: Mapping[str, int]) -> list[str]:
    """Why this restore does not count as a backup, one line per reason. Empty when it does.

    Exact equality, because `dump` counted in the very snapshot it dumped: one
    row short is a backup missing a row, not an estimate being off.
    """
    problems = []
    if not restored:
        problems.append("the restore holds no tables at all")
    for table, count in sorted(dumped.items()):
        if table not in restored:
            problems.append(f"{table} is in the database and missing from the restore")
        elif restored[table] != count:
            problems.append(f"{table}: {count} row(s) when it was dumped, {restored[table]} in the restore")
    return problems


def report(dumped: Mapping[str, int], restored: Mapping[str, int]) -> str:
    """Every table side by side, for the log."""
    lines = [f"{'table':40} {'dumped':>12} {'restored':>12}"]
    for table in sorted(set(dumped) | set(restored)):
        before = dumped.get(table)
        after = restored.get(table)
        lines.append(f"{table:40} {'-' if before is None else before:>12} {'-' if after is None else after:>12}")
    return "\n".join(lines)


def dump(workdir: Path, tools: Tools, source_env: Mapping[str, str]) -> dict[str, int]:
    """Count every table, then write both archives, all in one snapshot. Returns the counts."""
    workdir.mkdir(parents=True, exist_ok=True)
    with HeldTransaction(tools, source_env) as held:
        [[snapshot]] = held.query("select pg_export_snapshot()")
        uncovered = held.query(UNCOVERED_TABLES_SQL)
        if uncovered:
            raise Refused(
                "these tables may hold rows in a schema the backup does not dump, so it would leave them out: "
                + "; ".join(
                    f"{label} ({_rows_by_catalog(int(rows))}, {int(size):,} bytes on disk)" for label, rows, size in uncovered
                )
                + f". Dump the schema, or, if Supabase runs it, add it to SUPABASE_SCHEMAS in {Path(__file__).name}."
            )
        tables = held.query(DUMPED_TABLES_SQL)
        if not any(label.startswith(f"{DUMPED_SCHEMA}.") for label, _ in tables):
            raise Refused(f"the database has no tables in schema {DUMPED_SCHEMA}; is BACKUP_DATABASE_URL the right database?")
        counts = {label: int(count) for label, count in held.query(_counting_sql(tables))}
        _write_counts(workdir / LIVE_ROWS, counts)

        # Never --enable-row-security: with it, a role RLS applies to dumps
        # nothing and succeeds. Without it, the same role makes pg_dump refuse.
        common = ["--format=custom", "--no-password", f"--snapshot={snapshot}"]
        tools.run("pg_dump", [*common, f"--schema={DUMPED_SCHEMA}", f"--file={workdir / 'public.dump'}"], source_env)
        auth_tables = [f"--table={table}" for table in AUTH_TABLES]
        tools.run("pg_dump", [*common, *auth_tables, f"--file={workdir / 'auth.dump'}"], source_env)
    return counts


def refuse_unless_local(scratch_env: Mapping[str, str]) -> None:
    """Refuse a scratch database that is not on this machine (LOCAL_HOSTS)."""
    host = scratch_env.get("PGHOST", "")
    if host not in LOCAL_HOSTS:
        raise Refused(
            f"--scratch-url names host {host}, and verify restores only into a database on this machine "
            f"({', '.join(LOCAL_HOSTS)}): it drops schemas public and auth and switches row-level security off "
            "in the database it is given"
        )


def verify(workdir: Path, tools: Tools, scratch_env: Mapping[str, str]) -> list[str]:
    """Restore both archives into the scratch database, count, and compare. Returns the problems."""
    refuse_unless_local(scratch_env)
    # A fresh database's own `public` is dropped so the archive's CREATE SCHEMA
    # restores as written, and `auth` is created because a `--table` dump
    # carries its tables and not their schema.
    _query(tools, scratch_env, "drop schema if exists public cascade; drop schema if exists auth cascade; create schema auth")
    for archive in ARCHIVES:
        tools.run(
            "pg_restore",
            ["--no-owner", "--no-privileges", "--exit-on-error", f"--dbname={scratch_env['PGDATABASE']}", str(workdir / archive)],
            scratch_env,
        )

    tables = _query(tools, scratch_env, RESTORED_TABLES_SQL)
    restored: dict[str, int] = {}
    if tables:
        # The count has to measure the archive, not what row-level security
        # lets the counting role see: the restored tables keep RLS, and a role
        # it applies to would count a full table as empty. This copy is
        # thrown away with the job, so switching it off here touches nothing.
        _query(
            tools,
            scratch_env,
            "; ".join(f"alter table {quoted} disable row level security, no force row level security" for _, quoted in tables),
        )
        restored = {table: int(count) for table, count in _query(tools, scratch_env, _counting_sql(tables))}
    _write_counts(workdir / RESTORED_ROWS, restored)

    dumped = _read_counts(workdir / LIVE_ROWS)
    print(report(dumped, restored))
    return compare(dumped, restored)


def seal(workdir: Path, recipient: str, now: datetime.datetime) -> tuple[Path, str]:
    """Bundle the archives and counts into one tar, encrypt it to `recipient`, and delete the plaintext.

    Returns the sealed file and the bucket key it belongs under. The private
    key never comes near this: only the public recipient is needed to seal,
    so a leaked bucket token exposes ciphertext and nothing else.
    """
    if not AGE_RECIPIENT.fullmatch(recipient):
        raise Refused("BACKUP_AGE_RECIPIENT is not an age public key (age1 followed by 58 characters)")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    members = [*ARCHIVES, LIVE_ROWS, RESTORED_ROWS]
    manifest = {
        "created_at": now.isoformat(timespec="seconds"),
        "sha256": {name: hashlib.sha256((workdir / name).read_bytes()).hexdigest() for name in members},
    }
    (workdir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    plain = workdir / f"ourhike-{stamp}.tar"
    with tarfile.open(plain, "w") as bundle:
        for name in [*members, MANIFEST]:
            bundle.add(workdir / name, arcname=name)
    sealed = plain.with_suffix(".tar.age")
    result = subprocess.run(["age", "--encrypt", "--recipient", recipient, "--output", str(sealed), str(plain)], check=False)
    for name in [*ARCHIVES, plain.name]:
        (workdir / name).unlink(missing_ok=True)
    if result.returncode != 0:
        raise Refused(f"age exited {result.returncode}")
    return sealed, f"postgres/{now:%Y/%m/%d}/{sealed.name}"


def _output(name: str, value: str) -> None:
    """A step output for the workflow, and a line for anybody running this by hand."""
    print(f"{name}={value}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as out:
            out.write(f"{name}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage", choices=("dump", "verify", "seal"))
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--pg-image", help="Run the Postgres tools in this Docker image instead of from PATH.")
    parser.add_argument("--scratch-url", help="verify: the throwaway database to restore into.")
    args = parser.parse_args(argv)
    workdir = args.workdir.resolve()
    tools = Tools(workdir=workdir, image=args.pg_image)

    try:
        if args.stage == "dump":
            counts = dump(workdir, tools, libpq_environment(os.environ.get("BACKUP_DATABASE_URL", "")))
            print(
                f"Dumped {len(counts)} table(s) holding {sum(counts.values())} row(s) between them, counted in the dump's snapshot."
            )
        elif args.stage == "verify":
            if not args.scratch_url:
                parser.error("verify needs --scratch-url")
            problems = verify(workdir, tools, libpq_environment(args.scratch_url, require_encryption=False))
            if problems:
                print("\nThis dump does not count as a backup:", file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                return 1
            print("\nEvery table came back holding exactly the rows it held when it was dumped.")
        else:
            now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
            sealed, key = seal(workdir, os.environ.get("BACKUP_AGE_RECIPIENT", ""), now)
            _output("file", str(sealed))
            _output("key", key)
    except Refused as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
