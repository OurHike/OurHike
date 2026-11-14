"""backend-tests.yml refuses a change that deletes or renames a migration (#1918, item 15).

The first half holds check_migrations_kept.py's reading of `git diff
--name-status --no-renames`. The second runs the workflow's step itself, its
shell and all, in a scratch repository whose `origin` holds the base commit,
so what is proved is the step CI runs and not a copy of it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import check_migrations_kept as guard
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backend-tests.yml"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_migrations_kept.py"
STEP = "Refuse deleting or renaming a migration"


def test_a_deleted_migration_is_refused():
    assert guard.deleted_migrations("D\tbackend/alembic/versions/f00dfeed0001_add_a_table.py\n") == [
        "backend/alembic/versions/f00dfeed0001_add_a_table.py"
    ]


def test_an_added_or_edited_migration_is_not():
    listing = "A\tbackend/alembic/versions/a1_new.py\nM\tbackend/alembic/versions/b2_old.py\n"
    assert guard.deleted_migrations(listing) == []


def test_a_deletion_outside_the_versions_directory_is_not():
    listing = "D\tbackend/app/routers/old.py\nD\tbackend/alembic/env.py\nD\tbackend/alembic/versions/__pycache__/x.pyc\n"
    assert guard.deleted_migrations(listing) == []


def test_main_answers_one_annotation_per_deleted_file_and_fails(capsys):
    listing = "D\tbackend/alembic/versions/a1.py\nD\tbackend/alembic/versions/b2.py\n"
    assert guard.main(listing) == 1
    errors = [line for line in capsys.readouterr().out.splitlines() if line.startswith("::error ")]
    assert [line.split("::")[1] for line in errors] == [
        "error file=backend/alembic/versions/a1.py",
        "error file=backend/alembic/versions/b2.py",
    ]


def test_main_passes_an_empty_listing(capsys):
    assert guard.main("") == 0
    assert "No file under backend/alembic/versions/" in capsys.readouterr().out


# --- the step itself ---------------------------------------------------------------


def _step() -> dict:
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    (step,) = [s for s in parsed["jobs"]["pytest-postgres"]["steps"] if s.get("name") == STEP]
    return step


def test_the_step_runs_on_every_event_rather_than_behind_the_scope():
    """A check that skips itself refuses nothing: no `if:` at all."""
    assert "if" not in _step()


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def _scratch(tmp_path: Path) -> tuple[Path, str]:
    """A bare `origin` holding a base with two migrations, and a clone of it one commit deep at that base.

    The script sits at the path the step names, so the step's own relative path is what runs it."""
    work = tmp_path / "work"
    (work / "backend" / "alembic" / "versions").mkdir(parents=True)
    (work / ".github" / "scripts").mkdir(parents=True)
    (work / ".github" / "scripts" / "check_migrations_kept.py").write_text(SCRIPT.read_text(encoding="utf-8"))
    for name in ("a1_first.py", "b2_second.py"):
        (work / "backend" / "alembic" / "versions" / name).write_text(f"revision = {name[:2]!r}\n")
    _git(work, "init", "-q", "-b", "main")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "base")
    base = _git(work, "rev-parse", "HEAD")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--depth=1", f"file://{origin}", str(clone))
    return clone, base


def _run(clone: Path, base: str) -> subprocess.CompletedProcess[str]:
    """The step's `run:` under the shell GitHub gives a step with none named: bash -eo pipefail."""
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", _step()["run"]],
        cwd=clone / "backend",
        env={**os.environ, "BASE_SHA": base, "GIT_CONFIG_GLOBAL": os.devnull},
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("change", "refused"),
    [
        ("add", False),
        ("edit", False),
        ("delete", True),
        ("rename", True),
    ],
)
def test_the_step_refuses_a_deleted_or_renamed_migration_and_nothing_else(tmp_path, change, refused):
    clone, base = _scratch(tmp_path)
    versions = clone / "backend" / "alembic" / "versions"
    if change == "add":
        (versions / "c3_third.py").write_text("revision = 'c3'\n")
    elif change == "edit":
        (versions / "b2_second.py").write_text("revision = 'b2'\n# a comment\n")
    elif change == "delete":
        (versions / "b2_second.py").unlink()
    elif change == "rename":
        (versions / "b2_second.py").rename(versions / "b2_renamed.py")
    _git(clone, "add", "-A")
    _git(clone, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", change)
    result = _run(clone, base)
    assert (result.returncode != 0) is refused, result.stdout + result.stderr
    assert ("::error file=backend/alembic/versions/b2_second.py::" in result.stdout) is refused


def test_the_step_fails_rather_than_passing_when_the_base_cannot_be_fetched(tmp_path):
    clone, _ = _scratch(tmp_path)
    result = _run(clone, "0" * 40)
    assert result.returncode != 0
    assert "Could not fetch the base commit" in result.stdout
