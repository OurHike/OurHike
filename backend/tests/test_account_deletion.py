"""Deleting an account: what goes, what stays, and what cannot get back in.

Phase E of features/ACCOUNT_SYNC.md (#895). The classification itself lives
in app/core/account_deletion.py and is argued there; this file is what stops
it drifting, and it is deliberately built around ONE fixture that gives a
hiker a row in every table that references `profiles.id`.

That shape is the point. A per-table test would pass forever after somebody
adds an eleventh table and forgets it here, and "which tables reference a
profile" is exactly the question this feature gets wrong by omission rather
than by error - so `test_every_table_that_names_a_profile_is_accounted_for`
reads the metadata rather than a list a human maintains.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import inspect

from app.core.account_deletion import delete_account
from app.db.base import Base
from app.models.app_failure import AppFailure
from app.models.closure import Closure
from app.models.club import Club
from app.models.field_note import FieldNote, NoteFlag
from app.models.hike import Hike
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.poi_photo import PoiPhoto
from app.models.preferences import UserPreferences
from app.models.profile import Profile, Role
from app.models.report import Report
from app.models.synced_trip import SyncedPlannedHike, SyncedTrip
from app.models.volunteer_hours import HoursState, VolunteerHoursRecord
from tests.factories import make_closure, make_profile
from tests.tokens import auth_headers

# Tables the completeness check below cannot judge by counting rows, with the
# reason. `profiles` is the only one: its row is scrubbed rather than deleted,
# so it is neither empty (which would read as "gone") nor unchanged (which
# would read as "kept"), and `test_the_scrub_clears_every_column_that_says_who
# _it_was` is what actually checks it.
NOT_JUDGED_BY_ROW_COUNT = {"profiles"}


def _furnish(db, profile_id: str, *, hours_state=HoursState.claimed) -> None:
    """One row in every table that names a profile, for one hiker."""
    club = Club(id=f"club-{profile_id}", name="A club")
    db.add(club)
    db.add(SyncedTrip(id=f"trip-{profile_id}", profile_id=profile_id, document={"name": "Grayson"}))
    db.add(SyncedPlannedHike(profile_id=profile_id, start_mile=1.0, end_mile=9.0))
    db.add(Hike(user_id=profile_id, overall_start_reference=0.0, overall_end_reference=100.0))
    db.add(UserPreferences(profile_id=profile_id, data={"units": "imperial"}))
    db.add(
        MaintainerAssignment(
            maintainer_id=profile_id,
            club_id=club.id,
            start_mile=1.0,
            end_mile=2.0,
            effective_from=dt.date(2026, 1, 1),
        )
    )
    db.add(
        VolunteerHoursRecord(
            user_id=profile_id,
            worked_on=dt.date(2026, 5, 1),
            hours=4.0,
            activity="maintenance",
            state=hours_state,
        )
    )
    db.add(
        AppFailure(
            reporter_id=profile_id,
            what_happened="the map went blank at the Fontana ford",
            contact="ridgerunner@example.com",
        )
    )
    db.add(
        Report(
            reporter_id=profile_id,
            type="blowdown",
            reporter_type="thru",
            visibility="public",
            mile=12.0,
        )
    )
    note = FieldNote(id=f"note-{profile_id}", reporter_id=profile_id, reporter_type="thru", note="water is flowing")
    db.add(note)
    db.add(PoiPhoto(poi_id="shelter-1", contributor_id=profile_id, attribution_name="Switchback"))
    db.commit()
    # A flag has to point at a note that already exists.
    db.add(NoteFlag(note_id=note.id, flagged_by=profile_id))
    db.commit()


@pytest.fixture
def hiker(db_session):
    profile = make_profile(db_session, role=Role.maintainer, display_name="Switchback")
    _furnish(db_session, profile.id)
    make_closure(db_session, reported_by=profile.id)
    return profile


def _count(db, model, condition) -> int:
    return db.query(model).filter(condition).count()


def test_the_private_rows_go(db_session, hiker):
    delete_account(db_session, hiker)
    db_session.commit()

    assert _count(db_session, SyncedTrip, SyncedTrip.profile_id == hiker.id) == 0
    assert _count(db_session, SyncedPlannedHike, SyncedPlannedHike.profile_id == hiker.id) == 0
    assert _count(db_session, Hike, Hike.user_id == hiker.id) == 0
    assert _count(db_session, UserPreferences, UserPreferences.profile_id == hiker.id) == 0
    assert _count(db_session, MaintainerAssignment, MaintainerAssignment.maintainer_id == hiker.id) == 0


def test_the_published_contributions_stay(db_session, hiker):
    delete_account(db_session, hiker)
    db_session.commit()

    assert _count(db_session, Report, Report.reporter_id == hiker.id) == 1
    assert _count(db_session, FieldNote, FieldNote.reporter_id == hiker.id) == 1
    assert _count(db_session, Closure, Closure.reported_by == hiker.id) == 1
    assert _count(db_session, PoiPhoto, PoiPhoto.contributor_id == hiker.id) == 1
    # A flag is a moderation request about somebody else's note. Withdrawing
    # it on the way out would drop an unreviewed note off the queue.
    assert _count(db_session, NoteFlag, NoteFlag.flagged_by == hiker.id) == 1


def test_a_shared_photo_keeps_the_trail_name_it_was_licensed_under(db_session, hiker):
    """The one thing deletion cannot take back, and the reason it cannot.

    CC BY-SA 4.0 (#577) was granted on condition of credit, and
    `attribution_name` is that credit. Stripping it would break the licence
    for everyone downstream who took the photo on those terms, so the
    deletion screen says so before the button rather than after it.
    """
    delete_account(db_session, hiker)
    db_session.commit()

    photo = db_session.query(PoiPhoto).filter(PoiPhoto.contributor_id == hiker.id).one()
    assert photo.attribution_name == "Switchback"


def test_the_person_is_scrubbed_but_the_row_survives(db_session, hiker):
    delete_account(db_session, hiker)
    db_session.commit()

    row = db_session.get(Profile, hiker.id)
    assert row is not None, "the row has to survive: five tables hold a NOT NULL key to it"
    assert row.display_name is None
    assert row.deleted_at is not None
    # A deleted maintainer is not a maintainer - `require_role` reads this.
    assert row.role == Role.hiker


def test_an_app_failure_report_keeps_what_broke_and_loses_how_to_reach_them(db_session, hiker):
    delete_account(db_session, hiker)
    db_session.commit()

    failure = db_session.query(AppFailure).one()
    assert failure.what_happened == "the map went blank at the Fontana ford"
    assert failure.reporter_id is None
    assert failure.contact is None


def test_hours_nobody_confirmed_go(db_session, hiker):
    delete_account(db_session, hiker)
    db_session.commit()

    assert _count(db_session, VolunteerHoursRecord, VolunteerHoursRecord.user_id == hiker.id) == 0


def test_hours_a_club_stood_behind_stay(db_session):
    profile = make_profile(db_session)
    _furnish(db_session, profile.id, hours_state=HoursState.confirmed)

    summary = delete_account(db_session, profile)
    db_session.commit()

    assert _count(db_session, VolunteerHoursRecord, VolunteerHoursRecord.user_id == profile.id) == 1
    assert summary.hours_kept == 1
    assert summary.hours_deleted == 0


def test_it_does_not_reach_into_another_hikers_rows(db_session, hiker):
    bystander = make_profile(db_session, display_name="Sundial")
    _furnish(db_session, bystander.id)

    delete_account(db_session, hiker)
    db_session.commit()

    assert _count(db_session, SyncedTrip, SyncedTrip.profile_id == bystander.id) == 1
    assert _count(db_session, UserPreferences, UserPreferences.profile_id == bystander.id) == 1
    assert db_session.get(Profile, bystander.id).display_name == "Sundial"


def test_the_summary_names_what_stayed(db_session, hiker):
    summary = delete_account(db_session, hiker)
    db_session.commit()

    # No "volunteer hours a club confirmed" line: this hiker's hours were
    # only ever claimed, so they went, and a zero is not on the receipt.
    assert summary.contributions_kept == {
        "closures you reported": 1,
        "condition reports": 1,
        "trail notes": 1,
        "notes you flagged for a moderator": 1,
        "photos you shared": 1,
    }


def test_the_summary_omits_the_zeroes(db_session):
    """Somebody who never contributed anything is told exactly that."""
    profile = make_profile(db_session)

    summary = delete_account(db_session, profile)
    db_session.commit()

    assert summary.contributions_kept == {}


def test_every_table_that_names_a_profile_is_accounted_for(db_session, hiker):
    """Read from the metadata, not from a list somebody maintains by hand.

    The failure this catches is the one this feature is most likely to have:
    a table added later with a `profiles.id` foreign key, whose rows neither
    go nor are deliberately kept, because nobody remembered this file
    existed. It cannot judge whether the answer is right - only that an
    answer was given for every table.
    """
    delete_account(db_session, hiker)
    db_session.commit()

    linked = {
        table.name
        for table in Base.metadata.tables.values()
        if any(fk.column.table.name == "profiles" for fk in table.foreign_keys)
    }
    assert linked, "the metadata should know about profile-linked tables"

    unanswered = set()
    for name in linked - NOT_JUDGED_BY_ROW_COUNT:
        table = Base.metadata.tables[name]
        columns = [c.name for c in table.columns if any(fk.column.table.name == "profiles" for fk in c.foreign_keys)]
        rows = db_session.execute(
            table.select().where(
                # Any column on this table still pointing at the deleted id.
                # Zero rows means "deleted"; rows means "kept", and either is
                # a decision. What fails is a table nobody furnished, because
                # then this test never saw it at all.
                table.c[columns[0]] == hiker.id
            )
        ).fetchall()
        if not rows and name not in _TABLES_EMPTIED:
            unanswered.add(name)

    assert unanswered == set(), (
        f"these tables lost their rows without this file saying so: {sorted(unanswered)} - "
        "add them to _TABLES_EMPTIED with a reason, or keep the rows"
    )


# The tables `delete_account` empties, each because the rows were only ever
# this hiker's own. Listed rather than inferred so that a table joining this
# set is a line somebody wrote on purpose.
_TABLES_EMPTIED = {
    "synced_trips",
    "synced_planned_hikes",
    "hikes",
    "user_preferences",
    "maintainer_assignments",
    "volunteer_hours",
    # `reporter_id` is nullable and null is the ordinary state here, so this
    # is the one table that can forget the link without losing the row.
    "app_failures",
}


def test_the_metadata_test_can_see_the_tables_it_claims_to(db_session):
    """A guard on the guard: `linked` must actually name the tables we know about.

    Without this, a change that made `linked` empty - a metadata import
    quietly dropping models, say - would turn the test above into an
    assertion that passes by looking at nothing.
    """
    linked = {
        table.name
        for table in Base.metadata.tables.values()
        if any(fk.column.table.name == "profiles" for fk in table.foreign_keys)
    }
    assert {"synced_trips", "reports", "poi_photos", "user_preferences"} <= linked


def test_a_deleted_account_cannot_sign_back_in(client, db_session):
    """The load-bearing half, because Supabase Auth still has the user.

    This backend cannot delete the Supabase Auth user - that needs a
    service-role key app/config.py does not hold - so after a deletion the
    hiker's session is still valid and its token still verifies. Without the
    check in core/auth.py the next request would find the scrubbed row and
    hand the account straight back.
    """
    user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    assert client.get("/profiles/me", headers=auth_headers(user_id)).status_code == 200

    profile = db_session.get(Profile, user_id)
    delete_account(db_session, profile)
    db_session.commit()

    again = client.get("/profiles/me", headers=auth_headers(user_id))
    assert again.status_code == 401
    assert "deleted" in again.json()["detail"].lower()


def test_the_scrub_clears_every_column_that_says_who_it_was(db_session, hiker):
    """Whatever `Profile` grows, the identifying half of it has to be cleared.

    Spelled as "everything except the four columns that are allowed to
    survive" rather than as a list of what to clear, so a column added to
    `Profile` later fails here instead of quietly surviving a deletion.
    """
    delete_account(db_session, hiker)
    db_session.commit()
    row = db_session.get(Profile, hiker.id)

    survives = {"id", "created_at", "deleted_at", "role"}
    for column in inspect(Profile).mapper.columns:
        if column.key not in survives:
            assert getattr(row, column.key) is None, (
                f"{column.key} survived the scrub - either clear it in scrub_profile, "
                "or add it to `survives` here with a reason it is not identifying"
            )
