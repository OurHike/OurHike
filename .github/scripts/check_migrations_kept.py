"""Refuse a change that deletes or renames a file under backend/alembic/versions/.

    git diff --name-status --no-renames BASE HEAD -- backend/alembic/versions/ \
        | python3 .github/scripts/check_migrations_kept.py

WHY (#1918 — Backend findings the 2026-10-27 pre-launch review filed
together, item 15). `migrate.yml` runs a migration against production from
`main`, and production's `alembic_version` then names that revision. Reverting
the pull request that added it takes the file out of `main` and leaves the
database stamped with a revision `main` cannot name. Measured by that review:
`alembic upgrade head` against a database stamped `f00dfeed0001` fails with
`Can't locate revision identified by 'f00dfeed0001'`. Every later `migrate.yml`
run fails the same way, while the hosting service keeps deploying code.

So a migration that has reached `main` is undone by a NEW migration that
reverses it, never by deleting the file. That is the only way back that leaves
every database's stamp nameable. This check holds the rule at the pull
request, where it costs one red check, instead of on the next `migrate.yml`
run, where it costs a stranded production database.

A RENAME IS A DELETION here. Alembic finds a revision by the `revision` id
inside the file, not by its name, so renaming a file alone strands nothing.
But a rename that also edits the id does. Reading a rename as a delete plus an
add (`--no-renames`) refuses both, and a file's name is not worth keeping a
loophole open for.

Only `D` lines refuse. An edit to an existing migration (`M`) is a different
question: whether the edit changes what a database that already ran it holds.
This check does not try to answer that one.
"""

from __future__ import annotations

import sys

VERSIONS = "backend/alembic/versions/"


def deleted_migrations(name_status: str) -> list[str]:
    """Every migration file `git diff --name-status --no-renames` reports deleted.

    A path outside VERSIONS, a status other than `D`, a blank line, and a file
    that is not Python (a stray `__pycache__` entry, say) are ignored. Python
    is all Alembic reads as a revision.
    """
    deleted = []
    for line in name_status.splitlines():
        status, _, path = line.partition("\t")
        if status.strip() == "D" and path.startswith(VERSIONS) and path.endswith(".py"):
            deleted.append(path)
    return deleted


def main(stdin: str) -> int:
    deleted = deleted_migrations(stdin)
    for path in deleted:
        print(
            f"::error file={path}::{path} is deleted or renamed by this change. A migration on main may already "
            "have run against production, and a database stamped with a revision main no longer has cannot be "
            "upgraded. Reverse it with a new migration instead (.github/scripts/check_migrations_kept.py)."
        )
    if not deleted:
        print("No file under backend/alembic/versions/ is deleted or renamed.")
    return 1 if deleted else 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
