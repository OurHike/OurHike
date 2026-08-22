"""`GET /profiles/me/export`: everything we hold, in the hiker's hands.

Phase E of features/ACCOUNT_SYNC.md (#895). The half that runs before the
deletion, and the half whose failure mode is silence: an export that quietly
omitted a table would look exactly like an export of somebody who had not
used that feature. So the tests here are mostly about COMPLETENESS rather
than shape - one furnished account, and an assertion that every table
carrying a `profiles.id` key reaches the file.
"""

from __future__ import annotations

import json

from app.core.account_export import NOT_INCLUDED, build_export
from app.db.base import Base
from app.models.profile import Role
from tests.factories import make_closure, make_profile
from tests.test_account_deletion import _furnish
from tests.tokens import auth_headers

# Which archive section carries each profile-linked table. The mapping is
# written out because the section names are deliberately NOT the table names
# - the file is the hiker's and "trips" beats "synced_trips" - which means
# nothing can derive this, and a table added later has to be given a home
# here before `test_every_profile_linked_table_reaches_the_file` will pass.
SECTION_FOR_TABLE = {
    "synced_trips": "trips",
    "synced_planned_hikes": "planned_hike",
    "hikes": "hikes",
    "user_preferences": "preferences",
    "maintainer_assignments": "trail_sections_you_maintain",
    "volunteer_hours": "volunteer_hours",
    "app_failures": "app_problems_you_reported",
    "reports": "condition_reports",
    "field_notes": "trail_notes",
    "note_flags": "notes_you_flagged",
    "closures": "closures_you_reported",
    "poi_photos": "photos_you_shared",
    "profiles": "your_account",
}


def _furnished(db_session):
    profile = make_profile(db_session, role=Role.maintainer, display_name="Switchback")
    _furnish(db_session, profile.id)
    make_closure(db_session, reported_by=profile.id)
    return profile


def test_export_requires_an_account(client):
    assert client.get("/profiles/me/export").status_code == 401


def test_every_profile_linked_table_reaches_the_file(db_session):
    """The completeness guard, read from the metadata rather than a list.

    A table added later with a `profiles.id` key and no home in
    SECTION_FOR_TABLE fails here, which is the moment to decide what a hiker
    should be handed rather than three releases after somebody notices their
    export is short.
    """
    profile = _furnished(db_session)
    archive = build_export(db_session, profile)

    linked = {
        table.name
        for table in Base.metadata.tables.values()
        if any(fk.column.table.name == "profiles" for fk in table.foreign_keys)
    }
    unhoused = linked - set(SECTION_FOR_TABLE)
    assert unhoused == set(), f"no archive section holds {sorted(unhoused)} - give it one in account_export.py"

    empty = [table for table in linked if not archive[SECTION_FOR_TABLE[table]]]
    assert empty == [], f"these sections came back empty for a hiker who has a row in each: {sorted(empty)}"


def test_it_carries_the_columns_the_response_schemas_redact(db_session):
    """The reason this dumps columns instead of reusing `*Out` schemas.

    `ReportOut.from_row` withholds `reporter_id` from anyone who is not the
    reporter or a moderator, and `ClosureOut` drops `reported_by` outright
    (#430). Both are right for a public read and both would be wrong here.
    """
    profile = _furnished(db_session)
    archive = build_export(db_session, profile)

    assert archive["condition_reports"][0]["reporter_id"] == profile.id
    assert archive["closures_you_reported"][0]["reported_by"] == profile.id


def test_a_photo_carries_the_key_that_identifies_its_object(db_session):
    """The one field the tables do not have, because it is derived.

    `poi_photo_key` computes the R2 key from (poi_id, contributor_id) rather
    than storing it (core/photos.py), so a plain column dump would hand back
    a photo record with nothing identifying the photograph.
    """
    profile = _furnished(db_session)
    archive = build_export(db_session, profile)

    assert archive["photos_you_shared"][0]["storage_key"] == f"poi-photos/shelter-1/{profile.id}.jpg"


def test_timestamps_carry_their_zone(db_session):
    """A naive UTC stamp in a file somebody opens next month is a wrong stamp.

    The columns are naive UTC by this backend's convention (core/time.py),
    which is safe while it stays inside the process and is a trap the moment
    it is written to a file the hiker reads in their own timezone.
    """
    profile = _furnished(db_session)
    archive = build_export(db_session, profile)

    assert archive["your_account"]["created_at"].endswith("Z")
    assert archive["exported_at"].endswith("Z")


def test_it_says_what_it_does_not_contain(db_session):
    profile = _furnished(db_session)
    archive = build_export(db_session, profile)

    assert archive["what_this_file_does_not_contain"] == list(NOT_INCLUDED)
    joined = " ".join(NOT_INCLUDED).lower()
    # The three gaps a hiker cannot see from the file itself.
    assert "photograph" in joined
    assert "never left your phone" in joined
    assert "supabase auth" in joined


def test_the_whole_archive_is_json(db_session, client):
    """Not a formality: `document` is a JSON column and `harms` is a list.

    A column type that `json.dumps` refuses would 500 the endpoint for
    exactly the hikers who have the most data, which is the worst possible
    distribution of that bug.
    """
    profile = _furnished(db_session)

    response = client.get("/profiles/me/export", headers=auth_headers(profile.id))

    assert response.status_code == 200, response.text
    assert json.loads(response.text)["exported_for"] == profile.id


def test_it_holds_nobody_elses_rows(db_session, client):
    mine = _furnished(db_session)
    theirs = make_profile(db_session, display_name="Sundial")
    _furnish(db_session, theirs.id)

    archive = client.get("/profiles/me/export", headers=auth_headers(mine.id)).json()

    ids = json.dumps(archive)
    assert theirs.id not in ids
    assert "Sundial" not in ids


def test_a_hiker_with_nothing_gets_a_file_rather_than_an_error(db_session, client):
    """The empty case is ordinary, and has to read as empty rather than broken."""
    profile = make_profile(db_session)

    archive = client.get("/profiles/me/export", headers=auth_headers(profile.id)).json()

    assert archive["your_account"]["id"] == profile.id
    assert archive["trips"] == []
    assert archive["preferences"] is None
    assert archive["planned_hike"] is None
