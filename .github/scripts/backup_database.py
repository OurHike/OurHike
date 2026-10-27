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

WHY THE RESTORE IS PART OF THE BACKUP. Row-level security is on for every table
(alembic/versions/b3d1c7a94e02_enable_row_level_security.py), and a role it
applies to can produce a dump that looks fine and holds nothing: plain pg_dump
refuses, but `pg_dump --enable-row-security` succeeds with zero rows. Nothing
here passes that flag, and the dumping role holds BYPASSRLS (LAUNCH_CHECKLIST.md
section 5b). `verify` is what catches it if either ever stops being true: it
restores both archives into a throwaway database and fails on any table the
live statistics (`pg_stat_user_tables.n_live_tup`) say has rows and the restore
holds none of. Statistics rather than `count(*)` on the live side, because a
role RLS hides rows from would count zero on both sides and pass.

`n_live_tup` is an estimate, so only "has rows" against "has none" is compared,
never the numbers themselves. Both are printed, for the person reading the log.

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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

#: Supavisor's transaction pooler. pg_dump sets session state a transaction
#: pooler does not keep, so the session pooler (5432) or the direct host is
#: the only target that works - migrate.yml explains the three in full.
TRANSACTION_POOLER_PORT = 6543

#: A dump of every hiker's data never crosses the internet in clear. `require`
#: encrypts without checking the server's certificate; `verify-full` with
#: Supabase's CA (sslrootcert=...) is stricter and is accepted as given.
ENCRYPTED_SSLMODES = ("require", "verify-ca", "verify-full")

DUMPED_SCHEMA = "public"
AUTH_TABLES = ("auth.users", "auth.identities")

#: An age X25519 recipient: "age1" and 58 bech32 characters.
AGE_RECIPIENT = re.compile(r"age1[02-9ac-hj-np-z]{58}")

LIVE_ROWS = "live-rows.tsv"
RESTORED_ROWS = "restored-rows.tsv"
MANIFEST = "manifest.json"
ARCHIVES = ("public.dump", "auth.dump")

#: Every table that gets dumped, with what the statistics say it holds. Listed
#: from pg_class rather than from the statistics view, so a table the
#: statistics have never counted is still a table the restore has to contain.
LIVE_ROWS_SQL = """
select n.nspname || '.' || c.relname, coalesce(s.n_live_tup, 0)
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
left join pg_stat_user_tables s on s.relid = c.oid
where c.relkind in ('r', 'p')
  and (n.nspname = 'public' or (n.nspname = 'auth' and c.relname in ('users', 'identities')))
order by 1
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

    def command(self, tool: str, args: list[str], pg_env: Mapping[str, str]) -> tuple[list[str], dict[str, str]]:
        """The argv and environment for one tool. Values travel in the environment only."""
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
        for name in sorted(pg_env):
            docker += ["--env", name]
        return [*docker, self.image, tool, *args], env

    def run(self, tool: str, args: list[str], pg_env: Mapping[str, str], *, capture: bool = False) -> str:
        argv, env = self.command(tool, args, pg_env)
        result = subprocess.run(argv, env=env, text=True, capture_output=capture, check=False)
        if result.returncode != 0:
            if capture and result.stderr:
                print(result.stderr, file=sys.stderr, end="")
            raise Refused(f"{tool} exited {result.returncode}")
        return result.stdout if capture else ""


def _query(tools: Tools, pg_env: Mapping[str, str], sql: str) -> list[list[str]]:
    out = tools.run(
        "psql",
        ["--no-psqlrc", "--no-align", "--tuples-only", "--field-separator=\t", "--set=ON_ERROR_STOP=1", "--command", sql],
        pg_env,
        capture=True,
    )
    return [line.split("\t") for line in out.splitlines() if line]


def _read_counts(path: Path) -> dict[str, int]:
    rows = (line.split("\t") for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {table: int(count) for table, count in rows}


def _write_counts(path: Path, counts: Mapping[str, int]) -> None:
    path.write_text("".join(f"{table}\t{count}\n" for table, count in sorted(counts.items())), encoding="utf-8")


def compare(live: Mapping[str, int], restored: Mapping[str, int]) -> list[str]:
    """Why this restore does not count as a backup, one line per reason. Empty when it does."""
    problems = []
    if not restored:
        problems.append("the restore holds no tables at all")
    for table, estimate in sorted(live.items()):
        if table not in restored:
            problems.append(f"{table} is in the database and missing from the restore")
        elif estimate > 0 and restored[table] == 0:
            problems.append(f"{table}: the live statistics say about {estimate} row(s), and the restore holds none")
    return problems


def report(live: Mapping[str, int], restored: Mapping[str, int]) -> str:
    """Every table side by side, for the log."""
    lines = [f"{'table':40} {'live (estimate)':>16} {'restored':>9}"]
    for table in sorted(set(live) | set(restored)):
        estimate = live.get(table)
        count = restored.get(table)
        lines.append(f"{table:40} {'-' if estimate is None else estimate:>16} {'-' if count is None else count:>9}")
    return "\n".join(lines)


def dump(workdir: Path, tools: Tools, source_env: Mapping[str, str]) -> dict[str, int]:
    """Read the live statistics, then write both archives. Returns the statistics."""
    workdir.mkdir(parents=True, exist_ok=True)
    live = {table: int(count) for table, count in _query(tools, source_env, LIVE_ROWS_SQL)}
    if not any(table.startswith(f"{DUMPED_SCHEMA}.") for table in live):
        raise Refused(f"the database has no tables in schema {DUMPED_SCHEMA}; is BACKUP_DATABASE_URL the right database?")
    _write_counts(workdir / LIVE_ROWS, live)

    # Never --enable-row-security: with it, a role RLS applies to dumps
    # nothing and succeeds. Without it, the same role makes pg_dump refuse.
    tools.run(
        "pg_dump",
        ["--format=custom", "--no-password", f"--schema={DUMPED_SCHEMA}", f"--file={workdir / 'public.dump'}"],
        source_env,
    )
    tables = [f"--table={table}" for table in AUTH_TABLES]
    tools.run("pg_dump", ["--format=custom", "--no-password", *tables, f"--file={workdir / 'auth.dump'}"], source_env)
    return live


def verify(workdir: Path, tools: Tools, scratch_env: Mapping[str, str]) -> list[str]:
    """Restore both archives into the scratch database, count, and compare. Returns the problems."""
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
        counting = " union all ".join(
            f"select '{label.replace(chr(39), chr(39) * 2)}', count(*) from {quoted}" for label, quoted in tables
        )
        restored = {table: int(count) for table, count in _query(tools, scratch_env, counting)}
    _write_counts(workdir / RESTORED_ROWS, restored)

    live = _read_counts(workdir / LIVE_ROWS)
    print(report(live, restored))
    return compare(live, restored)


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
            live = dump(workdir, tools, libpq_environment(os.environ.get("BACKUP_DATABASE_URL", "")))
            print(f"Dumped {len(live)} table(s); the statistics say {sum(live.values())} row(s) between them.")
        elif args.stage == "verify":
            if not args.scratch_url:
                parser.error("verify needs --scratch-url")
            problems = verify(workdir, tools, libpq_environment(args.scratch_url, require_encryption=False))
            if problems:
                print("\nThis dump does not count as a backup:", file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                return 1
            print("\nEvery table the statistics say has rows came back with rows.")
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
