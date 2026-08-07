"""Load maintaining clubs and their stretch assignments from a reviewed file.

**The way rows get into `clubs` and `maintainer_assignments`** (#249). Until
this existed there was none: `/maintainer-assignments` is GET-only and clubs
have no router at all, so resolution and the form's preview both ran against
structurally empty tables - and `lookupMaintainers` returns `[]` on failure,
which made "the table is empty" indistinguishable from "nobody is assigned".

WHY A FILE AND A SCRIPT, RATHER THAN AN ADMIN ENDPOINT

Because of what these rows are. An assignment says a named volunteer is at a
known place on a predictable schedule - the exact fact
features/SAYING_THANKS.md declines to publish without consent - and it comes
from a club's own records, in a spreadsheet, updated a few times a season. An
endpoint would need its own authentication, its own audit trail and its own
admin surface to be used safely, and would be used four times a year. A file
in a pull request already has review, history, and a person who pressed
merge.

VOLUNTEERING.md's larger module is where a real admin surface belongs when
clubs are managing themselves. This is the deliberate answer for one club
getting started, not a substitute for it.

APPEND-ONLY, BECAUSE THE MODEL IS VERSIONED

app/models/maintainer_assignment.py: "a hand-off closes one row and opens
another rather than overwriting anything". So this never edits an assignment.
Re-running it with an unchanged file writes nothing; re-running it with a
changed `start_mile` on an existing row writes a SECOND row and says so,
which is a mistake the operator can see rather than a silent rewrite of who
looked after a stretch last June. Closing a stretch means adding
`effective_to` to the file - and that IS an edit, so it is the one field this
will update, loudly.

Clubs are different: a club's name is a fact about today, not a version, so a
renamed club is updated in place.

    python load_assignments.py assignments.json           # says what it would do
    python load_assignments.py assignments.json --commit  # does it

Nothing is written without `--commit`, the same posture
`R2_PHOTO_WRITE_ENABLED` takes in app/core/photos.py: a run that should not
write should be unable to, rather than merely unlikely to.

WHAT THIS DOES NOT TOUCH: `Profile.role`

Loading an assignment does not promote anybody to `Role.maintainer`. Role is
an account-level permission that gates the moderation queue - a different job
from looking after a stretch - and a data-loading script quietly granting
people access to safety reports about named individuals is exactly the kind
of side effect nobody would come here looking for.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.club import Club
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Profile


class InvalidFile(Exception):
    """The file cannot be loaded, with a sentence saying why.

    Raised rather than exiting, so `main` owns the exit code and the tests can
    read the message instead of catching SystemExit.
    """


def _as_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise InvalidFile(f"{field} must be a YYYY-MM-DD string, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidFile(f"{field}: {error}") from error


def parse(document: Any) -> tuple[list[dict], list[dict]]:
    """Validate the file's shape and return `(clubs, assignments)`.

    Separate from the database work so the shape can be checked without one,
    and so a malformed file fails before anything is opened.

    **Every check here is one that would otherwise surface as a database
    error mentioning a constraint name**, which tells an operator nothing
    about which line of their spreadsheet is wrong.
    """
    if not isinstance(document, dict):
        raise InvalidFile("The file must be a JSON object with `clubs` and `assignments`.")

    clubs = document.get("clubs", [])
    assignments = document.get("assignments", [])
    if not isinstance(clubs, list) or not isinstance(assignments, list):
        raise InvalidFile("`clubs` and `assignments` must both be lists.")

    for club in clubs:
        for field in ("id", "name"):
            if not club.get(field):
                raise InvalidFile(f"Every club needs a non-empty `{field}`: {club!r}")

    for row in assignments:
        for field in ("maintainer_id", "club_id", "start_mile", "end_mile", "effective_from"):
            if row.get(field) is None:
                raise InvalidFile(f"Every assignment needs `{field}`: {row!r}")

        start, end = row["start_mile"], row["end_mile"]
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise InvalidFile(f"start_mile and end_mile must be numbers: {row!r}")
        if start > end:
            # Silently produces a stretch that covers nothing, so every
            # thanks written on it resolves to nobody - a feature that looks
            # switched off rather than misconfigured.
            raise InvalidFile(f"start_mile {start} is past end_mile {end}: {row!r}")

        frm = _as_date(row["effective_from"], "effective_from")
        if row.get("effective_to") is not None:
            to = _as_date(row["effective_to"], "effective_to")
            if to < frm:
                raise InvalidFile(f"effective_to {to} is before effective_from {frm}: {row!r}")

    return clubs, assignments


def _key(row: dict) -> tuple:
    """What makes two assignments the same one.

    Not the id: the file is written by hand from a club's records, so it
    should not have to invent UUIDs. This is the natural key - who, for which
    club, over which stretch, from when - and it is what makes re-running the
    loader safe.
    """
    return (
        row["maintainer_id"],
        row["club_id"],
        float(row["start_mile"]),
        float(row["end_mile"]),
        _as_date(row["effective_from"], "effective_from"),
    )


def apply(db: Session, clubs: list[dict], assignments: list[dict]) -> list[str]:
    """Write the rows, returning one line per change for the operator to read.

    Flushes but never commits - `main` decides that, which is what makes
    `--commit` a real gate rather than a label. A dry run gets the same lines
    from the same code path, so what it prints is what would happen.
    """
    changes: list[str] = []

    for row in clubs:
        club = db.get(Club, row["id"])
        if club is None:
            db.add(Club(id=row["id"], name=row["name"], region=row.get("region")))
            changes.append(f"club + {row['name']}")
        elif club.name != row["name"] or club.region != row.get("region"):
            # In place, deliberately: a club's name is a fact about today,
            # not a version. Assignments below are the opposite.
            changes.append(f"club ~ {club.name} -> {row['name']}")
            club.name, club.region = row["name"], row.get("region")

    db.flush()

    known = {_key(_row_of(a)): a for a in db.query(MaintainerAssignment).all()}

    for row in assignments:
        # The FK would say `violates foreign key constraint` and name nothing
        # useful. A maintainer id comes from Supabase's auth users, so the
        # ordinary cause is a volunteer who has not signed in yet - which is
        # a thing to go and fix, not a thing to debug.
        if db.get(Profile, row["maintainer_id"]) is None:
            raise InvalidFile(
                f"No profile {row['maintainer_id']} - a maintainer has to have signed in "
                "at least once before a stretch can be assigned to them."
            )
        if db.get(Club, row["club_id"]) is None:
            raise InvalidFile(f"No club {row['club_id']} - add it to `clubs` in this file.")

        existing = known.get(_key(row))
        if existing is None:
            db.add(
                MaintainerAssignment(
                    maintainer_id=row["maintainer_id"],
                    club_id=row["club_id"],
                    start_mile=float(row["start_mile"]),
                    end_mile=float(row["end_mile"]),
                    effective_from=_as_date(row["effective_from"], "effective_from"),
                    effective_to=(None if row.get("effective_to") is None else _as_date(row["effective_to"], "effective_to")),
                    publicly_creditable=bool(row.get("publicly_creditable", False)),
                )
            )
            changes.append(f"assignment + mi {row['start_mile']}-{row['end_mile']} from {row['effective_from']}")
            continue

        # The one edit an existing assignment may take: closing it. Everything
        # else about a past assignment is history, and history is what this
        # model exists to keep.
        wanted_to = None if row.get("effective_to") is None else _as_date(row["effective_to"], "effective_to")
        if existing.effective_to != wanted_to:
            changes.append(f"assignment ~ mi {row['start_mile']}-{row['end_mile']} ends {existing.effective_to} -> {wanted_to}")
            existing.effective_to = wanted_to

        if bool(existing.publicly_creditable) != bool(row.get("publicly_creditable", False)):
            # Consent, so it has to be revocable - and a club withdrawing it
            # must take effect rather than being refused as an edit.
            changes.append(
                f"assignment ~ mi {row['start_mile']}-{row['end_mile']} "
                f"creditable -> {bool(row.get('publicly_creditable', False))}"
            )
            existing.publicly_creditable = bool(row.get("publicly_creditable", False))

    db.flush()
    return changes


def _row_of(assignment: MaintainerAssignment) -> dict:
    """A stored assignment in the file's own shape, so one `_key` serves both."""
    return {
        "maintainer_id": assignment.maintainer_id,
        "club_id": assignment.club_id,
        "start_mile": assignment.start_mile,
        "end_mile": assignment.end_mile,
        "effective_from": assignment.effective_from.isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path, help="A JSON file with `clubs` and `assignments`.")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write. Without it, this says what it would do and rolls back.",
    )
    args = parser.parse_args(argv)

    try:
        document = json.loads(args.file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read {args.file}: {error}", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        changes = apply(db, *parse(document))
        if args.commit:
            db.commit()
        else:
            db.rollback()
    except InvalidFile as error:
        db.rollback()
        print(f"{args.file}: {error}", file=sys.stderr)
        return 2
    finally:
        db.close()

    for line in changes:
        print(line)
    if not changes:
        print("Nothing to do - the database already matches this file.")
    elif not args.commit:
        print(f"\n{len(changes)} change(s) NOT written. Re-run with --commit.")
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
