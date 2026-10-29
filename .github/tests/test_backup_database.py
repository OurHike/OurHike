"""The nightly backup: what it refuses, what it compares, and the order it runs in.

#1908 - Back production's database up nightly to a private R2 bucket, because
Supabase Free keeps no backups. `.github/scripts/backup_database.py` is the
judgement and `.github/workflows/backup-database.yml` the order; this holds both.

THE TRAP THE RESTORE CHECK EXISTS FOR, REPRODUCED. Row-level security is on for
every table with no policies. A role it applies to makes plain `pg_dump` refuse,
which is safe, but `pg_dump --enable-row-security` succeeds with zero rows. The
tests at the end run the real `main(["dump"])`, `verify` and `seal` against a
real Postgres: a good backup comes back row for row, and an empty, a one-row-
short and a statistics-less one are each refused. They skip where no Postgres
is reachable, which includes CI's settings job; measured 2026-10-29 on the
session's local Postgres 16.15 with age 1.1.1.
"""

from __future__ import annotations

import ast
import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import backup_database as backup
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backup-database.yml"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "backup_database.py"

POOLER = "postgresql://ourhike_backup.abcdefghijklmnopqrst:p%40ss%2Fw0rd@aws-0-us-east-1.pooler.supabase.com:5432/postgres"


# --- The connection string --------------------------------------------------


def test_a_session_pooler_url_becomes_libpq_variables_with_the_password_decoded():
    assert backup.libpq_environment(POOLER) == {
        "PGHOST": "aws-0-us-east-1.pooler.supabase.com",
        "PGPORT": "5432",
        "PGDATABASE": "postgres",
        "PGUSER": "ourhike_backup.abcdefghijklmnopqrst",
        "PGPASSWORD": "p@ss/w0rd",
        "PGSSLMODE": "require",
    }


def test_a_driver_suffix_from_sqlalchemy_is_accepted():
    assert backup.libpq_environment(POOLER.replace("postgresql://", "postgresql+psycopg://"))["PGHOST"].endswith("supabase.com")


def test_the_transaction_pooler_is_refused_by_name_without_quoting_the_secret():
    with pytest.raises(backup.Refused) as refusal:
        backup.libpq_environment(POOLER.replace(":5432/", ":6543/"))

    assert "6543" in str(refusal.value) and "session pooler" in str(refusal.value)
    assert "p@ss" not in str(refusal.value) and "p%40ss" not in str(refusal.value)


@pytest.mark.parametrize("sslmode", ["disable", "allow", "prefer"])
def test_a_dump_never_travels_unencrypted(sslmode):
    with pytest.raises(backup.Refused, match="unencrypted"):
        backup.libpq_environment(f"{POOLER}?sslmode={sslmode}")


def test_a_stricter_sslmode_and_its_certificate_are_passed_on():
    env = backup.libpq_environment(f"{POOLER}?sslmode=verify-full&sslrootcert=/etc/ssl/supabase.crt")

    assert (env["PGSSLMODE"], env["PGSSLROOTCERT"]) == ("verify-full", "/etc/ssl/supabase.crt")


def test_only_the_scratch_database_may_go_unencrypted():
    """The job's own throwaway Postgres has no TLS, and nothing leaves the runner to reach it."""
    env = backup.libpq_environment("postgresql://postgres:scratch@localhost:5432/postgres", require_encryption=False)

    assert env["PGSSLMODE"] == "prefer"


@pytest.mark.parametrize(
    "url",
    ["", "https://example.org/postgres", "postgresql:///no-host", "postgresql://u:secret@host:notaport/db"],
    ids=["empty", "not-postgres", "no-host", "bad-port"],
)
def test_a_connection_string_that_cannot_be_used_is_refused_without_being_quoted(url):
    with pytest.raises(backup.Refused) as refusal:
        backup.libpq_environment(url)

    assert "secret" not in str(refusal.value)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_verify_restores_into_a_scratch_database_on_this_machine(host):
    backup.refuse_unless_local(
        backup.libpq_environment(f"postgresql://postgres:scratch@{host}:5432/postgres", require_encryption=False)
    )


@pytest.mark.parametrize("host", ["aws-0-us-east-1.pooler.supabase.com", "db.example.org", "10.0.0.5", "localhost.example.org"])
def test_verify_refuses_a_scratch_database_anywhere_else_before_touching_it(host, tmp_path, monkeypatch, capsys):
    """verify drops `public` and `auth` in the database it is given; the review
    found row-level security off on every table of one it was pointed at."""

    def touched(*args, **kwargs):
        raise AssertionError("verify ran a tool against a database it should have refused")

    monkeypatch.setattr(backup.Tools, "run", touched)
    scratch_url = f"postgresql://postgres:scratch@{host}:5432/postgres"

    assert backup.main(["verify", "--workdir", str(tmp_path), "--scratch-url", scratch_url]) == 1
    assert f"--scratch-url names host {host}" in capsys.readouterr().err


# --- Secrets stay out of argv -----------------------------------------------


def test_a_docker_run_tool_gets_the_variable_names_and_never_their_values(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_DATABASE_URL", POOLER)
    tools = backup.Tools(workdir=tmp_path, image="postgres:17")
    pg_env = backup.libpq_environment(POOLER)

    argv, env = tools.command("pg_dump", ["--format=custom"], pg_env)

    assert argv[:2] == ["docker", "run"] and "postgres:17" in argv
    assert ["--env", "PGPASSWORD"] == argv[argv.index("PGPASSWORD") - 1 : argv.index("PGPASSWORD") + 1]
    assert not any("p@ss" in arg or "pooler.supabase.com" in arg for arg in argv)
    assert env["PGPASSWORD"] == "p@ss/w0rd"
    assert "BACKUP_DATABASE_URL" not in env, "the whole connection string never reaches a tool"


def test_a_root_certificate_is_mounted_read_only_into_the_container_at_its_own_path(tmp_path, monkeypatch):
    certificate = tmp_path / "supabase-ca.crt"
    certificate.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    pg_env = backup.libpq_environment(f"{POOLER}?sslmode=verify-full&sslrootcert=supabase-ca.crt")

    argv, env = backup.Tools(workdir=tmp_path / "work", image="postgres:17").command("psql", ["--version"], pg_env)

    mount = argv[argv.index(f"{certificate}:{certificate}:ro") - 1 : argv.index(f"{certificate}:{certificate}:ro") + 1]
    assert mount == ["--volume", f"{certificate}:{certificate}:ro"]
    assert env["PGSSLROOTCERT"] == str(certificate), "the relative path would resolve against the container's workdir"
    assert ["--env", "PGSSLROOTCERT"] == argv[argv.index("PGSSLROOTCERT") - 1 : argv.index("PGSSLROOTCERT") + 1]


@pytest.mark.parametrize(
    ("query", "refusal"),
    [
        ("sslmode=verify-full", "none: name Supabase's CA certificate"),
        ("sslmode=verify-ca", "none: name Supabase's CA certificate"),
        ("sslmode=verify-full&sslrootcert=system", "the postgres image has none"),
        ("sslmode=verify-full&sslrootcert=/nowhere/supabase-ca.crt", "not a file on this machine"),
    ],
    ids=["verify-full-no-certificate", "verify-ca-no-certificate", "system-bundle", "missing-file"],
)
def test_a_certificate_check_docker_cannot_make_is_refused_by_name(tmp_path, query, refusal):
    pg_env = backup.libpq_environment(f"{POOLER}?{query}")

    with pytest.raises(backup.Refused, match=refusal):
        backup.Tools(workdir=tmp_path, image="postgres:17").command("pg_dump", ["--format=custom"], pg_env)


def test_require_needs_no_certificate_under_docker(tmp_path):
    argv, _ = backup.Tools(workdir=tmp_path, image="postgres:17").command("pg_dump", [], backup.libpq_environment(POOLER))

    assert not [arg for arg in argv if arg.endswith(":ro")]


def test_a_tool_on_path_inherits_no_stray_libpq_setting(tmp_path, monkeypatch):
    """A PGHOST left in the runner's environment must not redirect a dump."""
    monkeypatch.setenv("PGHOST", "somewhere-else.example")
    argv, env = backup.Tools(workdir=tmp_path).command("psql", ["--version"], {"PGHOST": "intended.example"})

    assert argv == ["psql", "--version"]
    assert env["PGHOST"] == "intended.example"


# --- The comparison ---------------------------------------------------------


def test_a_table_with_rows_that_restores_empty_is_the_failure():
    problems = backup.compare({"public.closures": 12, "public.profiles": 3}, {"public.closures": 0, "public.profiles": 3})

    assert problems == ["public.closures: 12 row(s) when it was dumped, 0 in the restore"]


def test_a_table_missing_from_the_restore_fails_whatever_it_held():
    assert backup.compare({"public.empty_table": 0}, {"public.other": 1}) == [
        "public.empty_table is in the database and missing from the restore"
    ]


def test_a_restore_with_no_tables_at_all_fails():
    assert "the restore holds no tables at all" in backup.compare({}, {})


def test_empty_on_both_sides_is_a_faithful_backup():
    assert backup.compare({"public.reports": 0, "public.closures": 40}, {"public.reports": 0, "public.closures": 40}) == []


def test_compare_refuses_a_restore_one_row_short_because_the_count_is_exact():
    """`dump` counts in the snapshot it dumps, so any difference is a missing row, never an estimate being off."""
    assert backup.compare({"public.closures": 40}, {"public.closures": 39}) == [
        "public.closures: 40 row(s) when it was dumped, 39 in the restore"
    ]


def test_the_report_puts_every_table_side_by_side():
    lines = backup.report({"public.closures": 12}, {"public.closures": 12, "auth.users": 2}).splitlines()

    assert lines[1].split() == ["auth.users", "-", "2"]
    assert lines[2].split() == ["public.closures", "12", "12"]


def test_a_held_transaction_keeps_psql_stdin_open_inside_docker(tmp_path):
    """Without `--interactive`, Docker hands psql an empty stdin and the held transaction ends at once."""
    argv, _ = backup.Tools(workdir=tmp_path, image="postgres:17").command("psql", ["--quiet"], {}, interactive=True)

    assert "--interactive" in argv[: argv.index("postgres:17")]


def test_the_supabase_schemas_never_include_the_ones_this_backup_exists_for():
    assert backup.DUMPED_SCHEMA not in backup.SUPABASE_SCHEMAS
    assert "auth" in backup.SUPABASE_SCHEMAS, "auth's other tables are Supabase's; users and identities are dumped by name"


# --- Egress -----------------------------------------------------------------


def _at_the_line() -> int:
    """The largest night whose thirty copies stay within EGRESS_WARN_SHARE of the quota."""
    return int(backup.EGRESS_WARN_SHARE * backup.FREE_EGRESS_QUOTA_BYTES) // backup.NIGHTS_A_MONTH


def test_egress_warning_stays_quiet_up_to_the_share_and_speaks_past_it():
    assert backup.egress_warning(_at_the_line()) == ""
    assert backup.egress_warning(_at_the_line() + 1) != ""


def test_egress_warning_names_the_night_the_month_and_the_quota():
    said = backup.egress_warning(170 * 10**6)

    assert "about 170 MB" in said and "5.1 GB" in said and "50%" in said and "5 GB egress quota" in said
    assert "picked rather than measured" in said, "the share is ours, and the issue must not read it as Supabase's number"
    assert "@" not in said, "an @word in an issue body notifies whoever owns that login"


# --- Sealing ----------------------------------------------------------------


def test_sealing_refuses_anything_that_is_not_an_age_public_key(tmp_path):
    with pytest.raises(backup.Refused, match="age public key"):
        backup.seal(tmp_path, "AGE-SECRET-KEY-1QQQQ", datetime.datetime(2026, 10, 27, tzinfo=datetime.UTC))


@pytest.mark.skipif(shutil.which("age-keygen") is None, reason="age is not installed here; the workflow installs it")
def test_sealing_leaves_only_ciphertext_and_counts_behind(tmp_path):
    for name in (*backup.ARCHIVES, backup.LIVE_ROWS, backup.RESTORED_ROWS):
        (tmp_path / name).write_text(f"contents of {name}\n", encoding="utf-8")
    key_file = tmp_path / "identity.txt"
    subprocess.run(["age-keygen", "-o", str(key_file)], check=True, capture_output=True)
    recipient = subprocess.run(["age-keygen", "-y", str(key_file)], check=True, capture_output=True, text=True).stdout.strip()

    sealed, key = backup.seal(tmp_path, recipient, datetime.datetime(2026, 10, 27, 5, 12, 3, tzinfo=datetime.UTC))

    assert key == "postgres/2026/10/27/ourhike-20261027T051203Z.tar.age"
    assert sealed.read_bytes().startswith(b"age-encryption.org/v1")
    assert not any((tmp_path / name).exists() for name in (*backup.ARCHIVES, "ourhike-20261027T051203Z.tar"))


# --- The workflow's order ---------------------------------------------------


def _steps() -> dict[str, dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return {step.get("id") or step.get("name"): step for step in workflow["jobs"]["backup"]["steps"]}


def test_each_stage_runs_only_after_the_one_before_it_succeeded():
    steps = _steps()

    assert steps["dump"]["if"] == "steps.can.outputs.go == 'true'"
    assert steps["verify"]["if"] == "steps.dump.outcome == 'success'"
    assert steps["seal"]["if"] == "steps.verify.outcome == 'success'"
    assert steps["upload"]["if"] == "steps.seal.outcome == 'success'"


def test_only_the_sealed_file_is_uploaded():
    upload = _steps()["upload"]

    assert upload["env"]["SEALED"] == "${{ steps.seal.outputs.file }}"
    assert 'aws s3 cp "$SEALED"' in upload["run"]


def test_the_database_credential_reaches_the_dump_and_nothing_after_it():
    holders = [name for name, step in _steps().items() if "secrets.BACKUP_DATABASE_URL" in str(step.get("env", {}))]

    assert holders == ["can", "dump"]


def test_nothing_ever_asks_pg_dump_to_apply_row_level_security():
    """With that flag, a role RLS applies to dumps nothing and succeeds.

    Read from the script's code rather than its text, because its docstring
    has to name the flag to say why it is absent."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    strings = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]
    assert not [text for text in strings if "enable-row-security" in text]

    runs = [step.get("run", "") for step in _steps().values()]
    assert not [run for run in runs if "enable-row-security" in run]


def _workflow_steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["backup"]["steps"]


def _run_step(step: dict, env: dict[str, str], tmp_path: Path) -> subprocess.CompletedProcess:
    """A step's `run` script under bash as GitHub runs it: `bash -e`, no profile, no rc file."""
    script = tmp_path / "step.sh"
    script.write_text(step["run"], encoding="utf-8")
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", str(script)],
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
    )


# --- The tracking issue -------------------------------------------------------
#
# The inline github-script run under `node` against a stubbed Octokit, with
# the real tracking-issue.js, as test_pending_approvals_workflow.py does: the
# script is a block string to YAML, so only running it shows what it writes.

TRACKING_HARNESS = """
const fs = require('fs')
const body = fs.readFileSync(process.argv[1], 'utf8')
const fixture = JSON.parse(process.argv[2])
Object.assign(process.env, fixture.env)
const calls = []
const github = {
  paginate: async (fn, args) => fn(args),
  rest: {issues: {
    listForRepo: async () => (fixture.existing ? [fixture.existing] : []),
    create: async (a) => { calls.push({call: 'create', ...a}); return {data: {number: 1908}} },
    update: async (a) => { calls.push({call: 'update', ...a}) },
    createComment: async (a) => { calls.push({call: 'createComment', ...a}) },
  }},
}
const context = {repo: {owner: 'OurHike', repo: 'OurHike'}}
const core = {info: () => {}, warning: () => {}}
const script = new Function('github', 'context', 'core', 'require', `return (async () => {${body}})()`)
script(github, context, core, require)
  .then(() => console.log(JSON.stringify(calls)))
  .catch((error) => { console.error(error.stack); process.exit(1) })
"""

#: The outcomes of a night on which every step worked.
GOOD_NIGHT = {
    "GO": "true",
    "MISSING": "",
    "PYTHON": "success",
    "AGE": "success",
    "TOOLS": "success",
    "DUMP": "success",
    "VERIFY": "success",
    "SEAL": "success",
    "UPLOAD": "success",
    "KEY": "postgres/2026/10/29/ourhike-20261029T051203Z.tar.age",
    "EGRESS_WARNING": "",
}

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH; CI runners always have it")


def _issue_calls(tmp_path: Path, outcomes: dict[str, str], existing: dict | None = None) -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    script = tmp_path / "issue.js"
    script.write_text(_steps()["Open, update, or close the tracking issue"]["with"]["script"], encoding="utf-8")
    env = {**workflow["env"], "RUN_URL": "https://example.invalid/run", **GOOD_NIGHT, **outcomes}
    completed = subprocess.run(
        ["node", "-e", TRACKING_HARNESS, "--", str(script), json.dumps({"env": env, "existing": existing})],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "GITHUB_WORKSPACE": str(REPO_ROOT)},
    )
    assert completed.returncode == 0, f"the script threw:\n{completed.stderr}"
    return json.loads(completed.stdout)


def _rows(body: str) -> list[list[str]]:
    rows = [line for line in body.splitlines() if line.startswith("| ") and not line.startswith("| stage")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]


@needs_node
@pytest.mark.parametrize(
    ("step", "stage"),
    [
        ("GO", "settings"),
        ("PYTHON", "set up Python"),
        ("AGE", "install age"),
        ("TOOLS", "fetch postgres:17"),
        ("DUMP", "dump"),
        ("VERIFY", "restore check"),
        ("SEAL", "encrypt"),
        ("UPLOAD", "upload"),
    ],
)
def test_the_issue_blames_the_step_that_failed_and_none_after_it(tmp_path, step, stage):
    """The review's case: a failed `Install age` or `docker pull` was reported as a dump failure."""
    order = ["PYTHON", "AGE", "TOOLS", "DUMP", "VERIFY", "SEAL", "UPLOAD"]
    if step == "GO":
        # setup-python has no condition and still runs; every step gated on the settings is skipped.
        outcomes = {"GO": "false", "MISSING": "BACKUP_DATABASE_URL", **{name: "skipped" for name in order[1:]}}
    else:
        outcomes = {step: "failure", **{name: "skipped" for name in order[order.index(step) + 1 :]}}

    [created] = _issue_calls(tmp_path, outcomes)

    assert created["call"] == "create"
    assert [row[0] for row in _rows(created["body"])] == [stage]
    assert "was not backed up" in created["body"]


@needs_node
def test_the_issue_carries_the_label_the_night_shift_queue_ranks_first(tmp_path):
    [created] = _issue_calls(tmp_path, {"DUMP": "failure", "VERIFY": "skipped", "SEAL": "skipped", "UPLOAD": "skipped"})
    issue = {"number": 1, "title": created["title"], "labels": created["labels"], "updated_at": "2026-10-29T05:30:00Z"}
    spec = importlib.util.spec_from_file_location("night_queue", REPO_ROOT / "scripts" / "night_queue.py")
    night_queue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(night_queue)

    assert night_queue.verdict(issue) == (True, (1, "2026-10-29T05:30:00Z", 1)), (
        "scripts/night_queue.py does not put an open backup issue at the head of the night-shift queue"
    )


def test_no_other_workflow_opens_an_issue_with_the_backup_title():
    """tracking-issue.js matches label AND title, so sharing deployment-health is safe and sharing a title is not."""
    title = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["env"]["ISSUE_TITLE"]
    others = [
        path.name
        for path in WORKFLOW.parent.glob("*.yml")
        if path != WORKFLOW and f'ISSUE_TITLE: "{title}"' in path.read_text(encoding="utf-8")
    ]

    assert not others


@needs_node
def test_a_dump_too_large_for_the_egress_quota_opens_the_issue_as_a_warning_on_a_good_night(tmp_path):
    warning = backup.egress_warning(170 * 10**6)

    [created] = _issue_calls(tmp_path, {"EGRESS_WARNING": warning})

    assert created["call"] == "create"
    assert "**Production was backed up on" in created["body"] and "was not backed up" not in created["body"]
    [[stage, _, meaning]] = _rows(created["body"])
    assert (stage, meaning) == ("egress", warning)


@needs_node
def test_a_good_night_with_room_in_the_quota_closes_the_open_issue(tmp_path):
    existing = {"number": 1908, "title": "Nightly database backup", "body": "the dump failed"}

    calls = _issue_calls(tmp_path, {}, existing=existing)

    assert [call["call"] for call in calls] == ["createComment", "update"]
    assert calls[1]["state"] == "closed"


def test_the_main_branch_guard_runs_before_any_step_that_reads_a_secret():
    steps = _workflow_steps()

    assert steps[0].get("id") == "ref"
    assert "secrets." not in str(steps[0]), "the guard itself must not need production's credentials"


@pytest.mark.parametrize(
    "ref", ["refs/heads/claude/nightly-db-backup", "refs/heads/main-copy", "refs/tags/v1.0.0", "refs/pull/1930/merge"]
)
def test_a_run_from_any_ref_but_main_is_refused(ref, tmp_path):
    """A dispatch can name any branch, and this job hands that branch's code production's credentials."""
    refused = _run_step(_steps()["ref"], {"REF": ref}, tmp_path)

    assert refused.returncode == 1
    assert f"::error title=Backup refused::{ref} is not refs/heads/main" in refused.stdout


def test_a_run_from_main_goes_on(tmp_path):
    assert _run_step(_steps()["ref"], {"REF": "refs/heads/main"}, tmp_path).returncode == 0


def test_the_tracking_issue_hears_every_outcome_of_a_run_from_main_and_nothing_from_a_refused_ref():
    assert _steps()["Open, update, or close the tracking issue"]["if"] == "always() && steps.ref.outcome == 'success'"


# --- Against a real Postgres --------------------------------------------------
#
# One source and one scratch database per module (per xdist worker), reset
# between tests rather than made afresh: DROP DATABASE waits for a checkpoint,
# which took 3m35s on this session's loaded Postgres 16.15 (measured
# 2026-10-29), against well under a second for the reset.

ADMIN_URL = os.environ.get("OURHIKE_BACKUP_TEST_ADMIN_URL", "postgresql://ourhike:ourhike@localhost:5432/ourhike_dev")

#: The two Supabase Auth tables `dump` reads, as a stand-in `auth` schema.
AUTH_SQL = (
    "create schema auth; create table auth.users (id uuid primary key); "
    "create table auth.identities (id uuid primary key, user_id uuid not null);"
)

#: 40 closures with row-level security on, five users and two identities.
FORTY_CLOSURES_SQL = (
    AUTH_SQL + "create table public.closures (id int primary key, note text);"
    "insert into public.closures select n, 'closure ' || n from generate_series(1, 40) n;"
    "alter table public.closures enable row level security;"
    "insert into auth.users select gen_random_uuid() from generate_series(1, 5);"
    "insert into auth.identities select gen_random_uuid(), id from auth.users limit 2;"
)
FORTY_CLOSURES = {"auth.identities": 2, "auth.users": 5, "public.closures": 40}


def _psql(url: str, sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(["psql", url, "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-c", sql], capture_output=True, text=True)


def _reachable() -> bool:
    if not all(shutil.which(tool) for tool in ("psql", "pg_dump", "pg_restore")):
        return False
    return _psql(ADMIN_URL, "select 1").returncode == 0


def _drop_all(base: str, names: list[str]) -> None:
    """Drop every database in `names` at once, so their checkpoints overlap rather than queue."""
    admin = f"{base}/{ADMIN_URL.rsplit('/', 1)[1]}"
    drops = [
        subprocess.Popen(["psql", admin, "-X", "-q", "-c", f"drop database if exists {name} with (force)"]) for name in names
    ]
    for drop in drops:
        drop.wait()


@dataclass
class Postgres:
    """The databases one test module shares, and what a test may do to them."""

    base: str
    source: str
    scratch: str
    made: list[str]

    def reset(self, sql: str) -> None:
        """Leave the source database holding exactly what `sql` builds: every other schema is dropped first."""
        result = _psql(
            self.source,
            "do $$ declare s text; begin for s in select nspname from pg_namespace "
            "where nspname !~ '^pg_' and nspname <> 'information_schema' loop "
            "execute format('drop schema %I cascade', s); end loop; end $$; create schema public; " + sql,
        )
        assert result.returncode == 0, result.stderr

    def copy_of_source(self) -> str:
        """A new database cloned from the source's files - its rows, and none of its statistics."""
        name = f"backup_test_copy_{uuid.uuid4().hex[:8]}"
        result = _psql(
            f"{self.base}/{ADMIN_URL.rsplit('/', 1)[1]}", f"create database {name} template {self.source.rsplit('/', 1)[1]}"
        )
        assert result.returncode == 0, result.stderr
        self.made.append(name)
        return f"{self.base}/{name}"


@pytest.fixture(scope="module")
def postgres():
    """A source and a scratch database for the module, all dropped together at the end."""
    if not _reachable():
        pytest.skip("no local Postgres with psql, pg_dump and pg_restore; CI's settings job has none")
    base = ADMIN_URL.rsplit("/", 1)[0]
    suffix = uuid.uuid4().hex[:8]
    made: list[str] = []
    try:
        for name in (f"backup_test_src_{suffix}", f"backup_test_scratch_{suffix}"):
            created = _psql(ADMIN_URL, f"create database {name}")
            if created.returncode != 0:
                pytest.skip(f"this role cannot create databases: {created.stderr.strip()}")
            made.append(name)
        if _psql(f"{base}/{made[0]}?sslmode=require", "select 1").returncode != 0:
            pytest.skip("this Postgres refuses TLS, and `dump` will not connect without it")
        yield Postgres(base=base, source=f"{base}/{made[0]}", scratch=f"{base}/{made[1]}", made=made)
    finally:
        _drop_all(base, made)


@pytest.fixture
def run(postgres, tmp_path, monkeypatch):
    """`backup_database.main` as the workflow calls it, against the module's databases."""
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
    workdir = tmp_path / "backup"

    def stage(name: str, *, source: str | None = None) -> int:
        if name == "dump":
            monkeypatch.setenv("BACKUP_DATABASE_URL", f"{source or postgres.source}?sslmode=require")
            return backup.main(["dump", "--workdir", str(workdir)])
        if name == "verify":
            return backup.main(["verify", "--workdir", str(workdir), "--scratch-url", postgres.scratch])
        return backup.main([name, "--workdir", str(workdir)])

    stage.workdir = workdir
    return stage


def _docker_has(image: str) -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode == 0


@pytest.mark.skipif(not _docker_has("postgres:17"), reason="no Docker here with postgres:17 already pulled; tests never pull")
def test_verify_full_reaches_the_server_from_inside_docker_with_the_named_certificate(tmp_path):
    """The review's `root certificate file ... does not exist`, end to end:
    psql 17 in the container checks the local server's own certificate."""
    if not _reachable():
        pytest.skip("no local Postgres to connect to")
    served = Path(_psql(ADMIN_URL, "show ssl_cert_file").stdout.strip() or "/nonexistent")
    if not served.is_file():
        pytest.skip("the local Postgres serves no certificate this test can read")
    # Copied to a path the image does not have and the workdir mount does not
    # cover, as a certificate on the runner would be.
    (tmp_path / "certs").mkdir()
    certificate = tmp_path / "certs" / "server-root.crt"
    shutil.copyfile(served, certificate)
    checked = f"{ADMIN_URL}?sslmode=verify-full&sslrootcert={certificate}"
    if _psql(checked, "select 1").returncode != 0:
        pytest.skip("the local Postgres's certificate does not pass verify-full for its own host")

    (tmp_path / "work").mkdir()
    tools = backup.Tools(workdir=tmp_path / "work", image="postgres:17")
    out = tools.run(
        "psql",
        ["-X", "-At", "-c", "select ssl from pg_stat_ssl where pid = pg_backend_pid()"],
        backup.libpq_environment(checked),
        capture=True,
    )

    assert out.strip() == "t"


def test_a_good_backup_comes_back_row_for_row_through_dump_and_verify(postgres, run):
    postgres.reset(FORTY_CLOSURES_SQL)

    assert run("dump") == 0
    assert run("verify") == 0
    assert backup._read_counts(run.workdir / backup.LIVE_ROWS) == FORTY_CLOSURES
    assert backup._read_counts(run.workdir / backup.RESTORED_ROWS) == FORTY_CLOSURES


def _outputs(run) -> dict[str, str]:
    lines = (run.workdir.parent / "github_output").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


def test_the_dump_logs_each_archive_and_hands_the_workflow_its_bytes(postgres, run, capsys):
    postgres.reset(FORTY_CLOSURES_SQL)

    assert run("dump") == 0

    said = capsys.readouterr().out
    assert "public.dump: " in said and "auth.dump: " in said and " uncompressed" in said
    outputs = _outputs(run)
    on_disk = sum((run.workdir / name).stat().st_size for name in backup.ARCHIVES)
    text = sum(
        len(subprocess.run(["pg_restore", "--file=-", str(run.workdir / name)], capture_output=True, check=True).stdout)
        for name in backup.ARCHIVES
    )
    assert (int(outputs["archive_bytes"]), int(outputs["egress_bytes"])) == (on_disk, text)
    assert outputs["egress_warning"] == ""


def test_a_night_too_large_for_the_quota_warns_and_still_succeeds(postgres, run, monkeypatch):
    """Thirty nights past the share is a bill problem, not a broken backup: the dump still counts."""
    postgres.reset(FORTY_CLOSURES_SQL)
    monkeypatch.setattr(backup, "FREE_EGRESS_QUOTA_BYTES", 1000)

    assert run("dump") == 0
    assert "past the 50% of Supabase Free's" in _outputs(run)["egress_warning"]


@pytest.mark.skipif(shutil.which("age-keygen") is None, reason="age is not installed here; the workflow installs it")
def test_a_verified_backup_seals_into_one_age_file_holding_both_archives_and_their_counts(postgres, run, tmp_path, monkeypatch):
    postgres.reset(FORTY_CLOSURES_SQL)
    identity = tmp_path / "identity.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True).stdout.strip()
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", recipient)

    assert (run("dump"), run("verify"), run("seal")) == (0, 0, 0)

    [sealed] = run.workdir.glob("*.tar.age")
    plain = tmp_path / "opened.tar"
    subprocess.run(["age", "--decrypt", "--identity", str(identity), "--output", str(plain), str(sealed)], check=True)
    opened = tmp_path / "opened"
    with tarfile.open(plain) as bundle:
        bundle.extractall(opened, filter="data")
    assert sorted(p.name for p in opened.iterdir()) == sorted(
        [*backup.ARCHIVES, backup.LIVE_ROWS, backup.RESTORED_ROWS, backup.MANIFEST]
    )
    assert backup._read_counts(opened / backup.LIVE_ROWS) == backup._read_counts(opened / backup.RESTORED_ROWS) == FORTY_CLOSURES
    assert not [name for name in backup.ARCHIVES if (run.workdir / name).exists()], (
        "plaintext archives were left beside the sealed file"
    )


def test_an_empty_dump_from_row_level_security_is_refused_by_the_restore(postgres, run, capsys):
    """The issue's trap, end to end. FORCE makes RLS apply to the owner, which
    stands in for a role without BYPASSRLS without needing a superuser here."""
    postgres.reset(FORTY_CLOSURES_SQL)
    assert run("dump") == 0
    assert _psql(postgres.source, "alter table public.closures force row level security").returncode == 0

    # What `dump` does now: refuse at the count, the same refusal pg_dump gives.
    refused = run.workdir.parent / "refused"
    assert backup.main(["dump", "--workdir", str(refused)]) == 1
    assert "row-level security" in capsys.readouterr().err

    # The trap: a dump made with --enable-row-security succeeds and holds no closures.
    source_env = backup.libpq_environment(postgres.source, require_encryption=False)
    backup.Tools(workdir=run.workdir).run(
        "pg_dump",
        ["--format=custom", "--enable-row-security", "--schema=public", f"--file={run.workdir / 'public.dump'}"],
        source_env,
    )

    assert run("verify") == 1
    assert "public.closures: 40 row(s) when it was dumped, 0 in the restore" in capsys.readouterr().err


def test_a_restore_one_row_short_is_refused(postgres, run, capsys):
    postgres.reset(FORTY_CLOSURES_SQL)
    assert run("dump") == 0

    # An archive missing one row: the same table dumped again after a delete.
    assert _psql(postgres.source, "delete from public.closures where id = 40").returncode == 0
    source_env = backup.libpq_environment(postgres.source, require_encryption=False)
    backup.Tools(workdir=run.workdir).run(
        "pg_dump", ["--format=custom", "--schema=public", f"--file={run.workdir / 'public.dump'}"], source_env
    )

    assert run("verify") == 1
    assert "public.closures: 40 row(s) when it was dumped, 39 in the restore" in capsys.readouterr().err


def test_the_counts_are_exact_when_the_database_has_lost_its_statistics(postgres, run, capsys):
    """The review's finding, reproduced: after crash recovery or a statistics
    reset `n_live_tup` reads 0, and an empty dump compared against it passed.
    A database cloned from a template has the template's rows and none of its
    statistics, which is that state without needing a superuser."""
    postgres.reset(FORTY_CLOSURES_SQL + "analyze;")
    copy = postgres.copy_of_source()
    statistics = _psql(copy, "select coalesce(sum(n_live_tup), 0) from pg_stat_user_tables where relname = 'closures'")
    assert statistics.stdout.strip() == "0", "the clone kept its statistics, so this no longer reproduces the finding"

    assert run("dump", source=copy) == 0
    assert backup._read_counts(run.workdir / backup.LIVE_ROWS) == FORTY_CLOSURES

    # And the empty dump the statistics let through is refused.
    copy_env = backup.libpq_environment(copy, require_encryption=False)
    backup.Tools(workdir=run.workdir).run(
        "pg_dump", ["--format=custom", "--schema-only", "--schema=public", f"--file={run.workdir / 'public.dump'}"], copy_env
    )
    assert run("verify") == 1
    assert "public.closures: 40 row(s) when it was dumped, 0 in the restore" in capsys.readouterr().err


def test_a_table_with_rows_in_a_schema_the_backup_does_not_dump_stops_the_dump(postgres, run, capsys):
    """The review's 500-row `analytics.events`, which used to be absent from
    both archives while `verify` passed. Never analyzed, so the catalog's
    `reltuples` is -1 and only its pages on disk give it away."""
    postgres.reset(
        FORTY_CLOSURES_SQL + "create schema analytics; create table analytics.events (id int);"
        "insert into analytics.events select generate_series(1, 500);"
    )

    assert run("dump") == 1
    said = capsys.readouterr().err
    assert "analytics.events (never counted by the catalog" in said and "SUPABASE_SCHEMAS" in said
    assert not (run.workdir / "public.dump").exists(), "pg_dump ran although the dump was refused"


def test_rows_in_a_schema_supabase_runs_itself_do_not_stop_the_dump(postgres, run):
    """Storage's object index is Supabase's, not this app's, and is left out on purpose."""
    postgres.reset(
        FORTY_CLOSURES_SQL + "create schema storage; create table storage.objects (id int);"
        "insert into storage.objects select generate_series(1, 7); analyze storage.objects;"
    )

    assert run("dump") == 0
    assert "storage.objects" not in backup._read_counts(run.workdir / backup.LIVE_ROWS)


def test_an_empty_table_outside_public_does_not_stop_the_dump(postgres, run):
    """Only rows are refused over: an app schema with nothing in it loses nothing."""
    postgres.reset(FORTY_CLOSURES_SQL + "create schema analytics; create table analytics.events (id int);")

    assert run("dump") == 0


def test_a_write_between_the_count_and_the_dump_stays_out_of_the_archive(postgres, run, monkeypatch):
    """Both pg_dump runs import the held transaction's snapshot, so a row
    committed after the count is in neither the count nor the archive - and
    the restore still matches the count exactly."""
    postgres.reset(FORTY_CLOSURES_SQL)
    real_run = backup.Tools.run

    def write_first(tools, tool, args, pg_env, **kwargs):
        if tool == "pg_dump" and not getattr(write_first, "wrote", False):
            write_first.wrote = True
            assert _psql(postgres.source, "insert into public.closures values (41, 'after the count')").returncode == 0
        return real_run(tools, tool, args, pg_env, **kwargs)

    monkeypatch.setattr(backup.Tools, "run", write_first)

    assert run("dump") == 0
    assert run("verify") == 0
    assert backup._read_counts(run.workdir / backup.RESTORED_ROWS)["public.closures"] == 40
    assert _psql(postgres.source, "select count(*) from public.closures").stdout.strip() == "41"
