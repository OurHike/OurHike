"""Claims, photos and hours: the old API's phase 3 behaviour (#1910) and every
security finding its review passes proved, now in SQL, for the claim as the
maintainer reshaped it on 2026-10-28: one person, no crew, no review, and done
is public at once."""

import threading
from decimal import Decimal

import psycopg
import pytest
from conftest import BUCKET, NEIGHBOUR, SCORES_WELL, SITE, status, uid


def claim(db, who="claimer", sites=(SITE,)):
    return db.call(who, "claim_sites", list(sites))[0]["id"]


def photo(db, claim_id, phase, point=None, who="claimer", client_id=None, replaces=None):
    client_id = client_id or f"{phase}-{point}"
    db.upload(who, claim_id, client_id)
    return db.call(who, "add_photo", claim_id, phase, point, client_id, replaces)


def photograph(db, claim_id, phases=("before", "after"), who="claimer", tag=""):
    for point in (1, 2):
        for phase in phases:
            photo(db, claim_id, phase, point, who, client_id=f"{phase}-{point}{tag}")


def done(db, who="claimer", site=SITE):
    claim_id = claim(db, who, (site,))
    photograph(db, claim_id, who=who)
    db.call(who, "log_hours", claim_id, Decimal("2.5"))
    db.call(who, "finish_claim", claim_id, ["Hide the site", "Block the way in"], "Done")
    return claim_id


# --- Claiming ---------------------------------------------------------------------


def test_a_claim_lasts_fourteen_days_and_holds_the_site_against_a_second_claim(db):
    claim_id = claim(db)
    detail = db.call("claimer", "read_claim", claim_id)
    assert detail["state"] == "claimed" and detail["yours"] is True and detail["kind"] == "restore"
    assert db.owner("select due_at - claimed_at = interval '14 days' from remediation.claim")[0][0]
    assert status(db.refused("second", "claim_sites", [SITE])) == "PT409"


def test_only_a_site_the_analysis_says_needs_work_can_be_claimed(db):
    assert status(db.refused("claimer", "claim_sites", [SCORES_WELL])) == "PT422"
    assert status(db.refused("claimer", "claim_sites", ["not-a-site"])) == "PT422"


def test_claiming_a_cluster_is_all_or_nothing(db):
    claim(db, "first", (NEIGHBOUR,))
    assert status(db.refused("claimer", "claim_sites", [SITE, NEIGHBOUR])) == "PT409"
    assert db.call("claimer", "my_claims") == []


def test_two_claims_on_one_site_at_the_same_moment_end_with_one_claim(db, database_url):
    barrier = threading.Barrier(2)
    outcomes = []

    def take(who):
        with psycopg.connect(database_url, autocommit=True) as connection:
            from conftest import Db

            barrier.wait()
            try:
                Db(connection).call(who, "claim_sites", [SITE])
                outcomes.append("claimed")
            except psycopg.Error as error:
                outcomes.append(status(error))

    threads = [threading.Thread(target=take, args=(who,)) for who in ("one", "two")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes) == ["PT409", "claimed"]


def test_a_claim_past_its_due_time_is_released_and_the_site_can_be_claimed_again(db):
    claim_id = claim(db)
    db.age(claim_id, due_at="now() - interval '1 minute'")
    assert db.call("claimer", "read_claim", claim_id)["state"] == "released"
    claim(db, "next")


def test_only_the_claimer_can_release_and_releasing_opens_the_site(db):
    claim_id = claim(db)
    assert status(db.refused("stranger", "release_claim", claim_id)) == "PT403"
    assert db.call("claimer", "release_claim", claim_id)["state"] == "released"
    claim(db, "next")


def test_one_account_holds_at_most_ten_sites(db):
    many = [f"{n:08d}-6666-6666-6666-666666666666" for n in range(11)]
    db.connection.execute("insert into remediation.site (rims_id, club, workable) select unnest(%s::text[]), 'C', true", (many,))
    db.call("claimer", "claim_sites", many[:10])
    assert status(db.refused("claimer", "claim_sites", [many[10]])) == "PT409"


def test_someone_else_cannot_photograph_log_hours_finish_or_release(db):
    claim_id = claim(db)
    for function, args in (
        ("log_hours", (Decimal(2),)),
        ("finish_claim", ([], None)),
        ("remove_photo", ("00000000-0000-0000-0000-000000000000",)),
        ("release_claim", ()),
    ):
        assert status(db.refused("stranger", function, claim_id, *args)) == "PT403"
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("stranger", claim_id)


# --- Photos -----------------------------------------------------------------------


def test_the_first_before_photo_starts_the_work_and_a_new_photo_replaces_the_old_at_its_point(db):
    claim_id = claim(db)
    first = photo(db, claim_id, "before", 1, client_id="first")
    assert first["state"] == "in_progress" and first["started_at"] is not None
    again = photo(db, claim_id, "before", 1, client_id="retake")
    assert [p["path"] for p in again["photos"]] == [db.object_name(claim_id, "retake")]
    # Named, so the app deletes it: a retake should not become public with the work.
    assert again["unused_path"] == db.object_name(claim_id, "first")
    with db.acting("claimer") as connection:
        connection.execute("delete from storage.objects where name = %s", (again["unused_path"],))
    assert db.owner("select name from storage.objects") == [(db.object_name(claim_id, "retake"),)]


def test_a_photo_must_have_arrived_in_storage_before_it_goes_on_the_claim(db):
    claim_id = claim(db)
    assert status(db.refused("claimer", "add_photo", claim_id, "before", 1, "never-uploaded", None)) == "PT422"


@pytest.mark.parametrize(
    ("phase", "point", "client_id"),
    [("before", None, "a"), ("before", 3, "a"), ("extra", 1, "a"), ("sideways", 1, "a"), ("extra", None, "../../etc")],
    ids=["no-point", "point-3", "extra-with-point", "unknown-phase", "path-in-id"],
)
def test_a_photo_with_a_bad_slot_or_id_is_refused(db, phase, point, client_id):
    claim_id = claim(db)
    assert status(db.refused("claimer", "add_photo", claim_id, phase, point, client_id, None)) == "PT422"


@pytest.mark.parametrize(
    "name",
    [
        "{claim}/photo.png",
        "{claim}/sub/photo.jpg",
        "{claim}/../x.jpg",
        "not-a-claim/photo.jpg",
        "{other}/photo.jpg",
        "{claim}/{my_user_id}/photo.jpg",
    ],
    ids=["not-jpg", "nested", "dot-dot", "not-a-claim", "someone-elses-claim", "folder"],
)
def test_the_bucket_takes_only_the_claimers_jpeg_at_the_claims_own_address(db, name):
    claim_id = claim(db)
    other = claim(db, "someone-else", (NEIGHBOUR,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.acting("claimer") as connection:
            connection.execute(
                "insert into storage.objects (bucket_id, name, owner_id) values (%s, %s, %s)",
                (BUCKET, name.format(claim=claim_id, other=other, my_user_id=uid("claimer")), uid("claimer")),
            )


def test_nothing_can_be_uploaded_to_a_claim_that_is_no_longer_open(db):
    claim_id = done(db)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("claimer", claim_id, "late")
    overdue = claim(db, "slow", (NEIGHBOUR,))
    db.age(overdue, due_at="now() - interval '1 minute'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("slow", overdue, "too-late")


def test_an_uploaded_object_can_never_be_overwritten(db):
    # No update policy: row-level security filters out every row an update
    # could touch, so it changes nothing rather than failing.
    claim_id = claim(db)
    db.upload("claimer", claim_id, "once")
    with db.acting("claimer") as connection:
        changed = connection.execute("update storage.objects set owner_id = 'someone' where bucket_id = %s", (BUCKET,)).rowcount
    assert changed == 0
    assert db.owner("select owner_id from storage.objects") == [(uid("claimer"),)]


def test_the_claimer_may_delete_an_object_a_photo_was_replaced_out_of_and_nothing_else(db):
    claim_id = claim(db)
    photo(db, claim_id, "before", 1, client_id="replaced")
    photo(db, claim_id, "before", 1, client_id="kept")
    # On its way to the claim: deleting it would have the photo refused as not arrived.
    db.upload("claimer", claim_id, "in-flight")
    with db.acting("claimer") as connection:
        gone = connection.execute("delete from storage.objects where bucket_id = %s returning name", (BUCKET,)).fetchall()
    assert gone == [(db.object_name(claim_id, "replaced"),)]
    assert sorted(db.owner("select name from storage.objects")) == sorted(
        [(db.object_name(claim_id, "kept"),), (db.object_name(claim_id, "in-flight"),)]
    )


def test_a_queued_photo_sent_again_after_a_lost_answer_is_stored_once(db):
    # The third pass's P2.
    claim_id = claim(db)
    photo(db, claim_id, "extra", client_id="queued-1")
    again = db.call("claimer", "add_photo", claim_id, "extra", None, "queued-1", None)
    assert len(again["photos"]) == 1


def test_a_photo_sent_again_after_the_work_was_marked_done_is_answered_not_refused(db):
    claim_id = done(db)
    assert db.call("claimer", "add_photo", claim_id, "before", 1, "before-1", None)["state"] == "done"
    assert status(db.refused("stranger", "add_photo", claim_id, "before", 1, "before-1", None)) == "PT403"


def test_a_replay_of_a_photo_since_replaced_does_not_put_it_back(db):
    # The fourth pass's C.
    claim_id = claim(db)
    photo(db, claim_id, "before", 1, client_id="photo-x")
    newer = photo(db, claim_id, "before", 1, client_id="photo-y")["photos"][0]["id"]
    replay = db.call("claimer", "add_photo", claim_id, "before", 1, "photo-x", None)
    assert [p["id"] for p in replay["photos"]] == [newer]


def test_a_replay_of_a_removed_extra_does_not_bring_it_back(db):
    claim_id = claim(db)
    extra = photo(db, claim_id, "extra", client_id="extra-x")["photos"][0]["id"]
    db.call("claimer", "remove_photo", claim_id, extra)
    assert db.call("claimer", "add_photo", claim_id, "extra", None, "extra-x", None)["photos"] == []


def test_a_queued_photo_taken_before_its_point_was_photographed_again_is_refused_not_put_over(db):
    # One person, two phones: the slot moved on while this one waited for signal.
    claim_id = claim(db)
    newer = photo(db, claim_id, "after", 1, client_id="from-the-other-phone")["photos"][0]["id"]
    db.upload("claimer", claim_id, "my-old-photo")
    assert status(db.refused("claimer", "add_photo", claim_id, "after", 1, "my-old-photo", "nothing")) == "PT412"
    assert [p["id"] for p in db.call("claimer", "read_claim", claim_id)["photos"]] == [newer]
    db.upload("claimer", claim_id, "my-new-photo")
    over = db.call("claimer", "add_photo", claim_id, "after", 1, "my-new-photo", newer)
    assert [p["id"] for p in over["photos"]] != [newer]


def test_two_copies_of_one_queued_photo_racing_store_one(db, database_url):
    claim_id = claim(db)
    db.upload("claimer", claim_id, "racing")
    barrier = threading.Barrier(2)
    results = []

    def send():
        with psycopg.connect(database_url, autocommit=True) as connection:
            from conftest import Db

            barrier.wait()
            results.append(Db(connection).call("claimer", "add_photo", claim_id, "extra", None, "racing", None))

    threads = [threading.Thread(target=send) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert [len(r["photos"]) for r in results] == [1, 1]
    assert db.owner("select count(*) from remediation.photo")[0][0] == 1


def test_a_claim_holds_at_most_40_photos(db):
    claim_id = claim(db)
    for n in range(40):
        photo(db, claim_id, "extra", client_id=f"extra-{n}")
    db.upload("claimer", claim_id, "extra-40")
    assert status(db.refused("claimer", "add_photo", claim_id, "extra", None, "extra-40", None)) == "PT409"


# --- Who reads a photo ------------------------------------------------------------
# The sixth pass's finding 1: a public bucket on OurHike's project was anyone's
# free file host. Private now; the select policy is who may download a photo
# or sign a link to one.


def test_a_photo_is_its_claimers_until_the_work_is_done_then_everyones(db):
    claim_id = claim(db)
    photograph(db, claim_id)
    before = db.object_name(claim_id, "before-1")
    assert db.sees("claimer", before)
    assert not db.sees("stranger", before) and not db.sees(None, before)
    db.call("claimer", "finish_claim", claim_id, [], None)
    assert db.sees(None, before) and db.sees("stranger", before) and db.sees("guest", before, anonymous=True)


def test_an_object_no_photo_uses_is_nobodys_to_read_not_even_its_uploaders(db):
    claim_id = claim(db)
    pending = db.upload("claimer", claim_id, "not-yet-on-the-claim")
    assert not db.sees("claimer", pending)
    photo(db, claim_id, "before", 1, client_id="replaced")
    photo(db, claim_id, "before", 1, client_id="kept")
    freed = db.object_name(claim_id, "replaced")
    # Readable only so the claimer can delete it, and only while the claim is worked.
    assert db.sees("claimer", freed) and not db.sees("stranger", freed)
    db.call("claimer", "release_claim", claim_id)
    assert not db.sees("claimer", freed)


def test_an_account_may_have_twenty_uploads_waiting_to_go_on_a_claim(db):
    claim_id = claim(db)
    for n in range(20):
        db.upload("claimer", claim_id, f"waiting-{n}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("claimer", claim_id, "one-too-many")
    db.call("claimer", "add_photo", claim_id, "extra", None, "waiting-0", None)
    db.upload("claimer", claim_id, "room-again")


def test_uploads_left_waiting_on_a_claim_that_closed_do_not_lock_the_account_out(db):
    closed = claim(db)
    for n in range(20):
        db.upload("claimer", closed, f"lost-answer-{n}")
    db.call("claimer", "release_claim", closed)
    db.upload("claimer", claim(db, sites=(NEIGHBOUR,)), "next-claim")


def test_an_account_may_upload_150_photos_a_day(db):
    # Earlier uploads, to a claim since released, so only the day's cap is near.
    released = claim(db, sites=(NEIGHBOUR,))
    db.call("claimer", "release_claim", released)
    claim_id = claim(db)
    for prefix, age in (("yesterday", "25 hours"), ("today", "1 hour")):
        db.connection.execute(
            "insert into storage.objects (bucket_id, name, created_at)"
            " select %s, %s || '/' || %s || '-' || n || '.jpg', now() - %s::interval"
            " from generate_series(1, 149) n",
            (BUCKET, released, prefix, age),
        )
    db.upload("claimer", claim_id, "the-150th")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("claimer", claim_id, "the-151st")


# --- Hours and done ---------------------------------------------------------------


@pytest.mark.parametrize("hours", [0, -1, 0.3, 72.5])
def test_hours_are_in_half_hours_and_bounded(db, hours):
    claim_id = claim(db)
    assert status(db.refused("claimer", "log_hours", claim_id, Decimal(str(hours)))) == "PT422"


def test_done_needs_a_before_and_an_after_at_both_photo_points(db):
    claim_id = claim(db)
    photograph(db, claim_id, phases=("before",))
    error = db.refused("claimer", "finish_claim", claim_id, [], None)
    assert status(error) == "PT422" and "after at point 1" in str(error)


def test_done_is_public_at_once_with_the_claimers_name_steps_and_hours(db):
    # Decided 2026-10-28: no review, so done is done.
    db.call("claimer", "set_display_name", "Ridge Runner")
    claim_id = done(db)
    outside = db.call("stranger", "read_claim", claim_id)
    assert outside["full"] is True and outside["state"] == "done" and outside["claimer"] == "Ridge Runner"
    assert outside["steps_done"] == ["Hide the site", "Block the way in"] and outside["hours"] == 2.5
    with db.acting(None) as connection:
        row = connection.execute("select state, claimer, hours from remediation.open_claims").fetchone()
        photos = connection.execute("select count(*) from remediation.open_photos").fetchone()[0]
    assert row == ("done", "Ridge Runner", Decimal("2.5")) and photos == 4
    assert db.call("claimer", "my_hours") == {"done": 2.5, "in_progress": 0, "claims": 1}


def test_a_claim_being_worked_is_its_claimers_alone(db):
    # The sixth pass's finding 3, for one person's claim.
    claim_id = claim(db)
    photograph(db, claim_id)
    db.call("claimer", "log_hours", claim_id, Decimal(3))
    outside = db.call("stranger", "read_claim", claim_id)
    assert outside["full"] is False and outside["state"] == "in_progress" and outside["claimer"] is None
    assert outside["photos"] == [] and outside["notes"] is None and outside["hours"] is None
    assert db.call("claimer", "read_claim", claim_id)["full"] is True
    with db.acting(None) as connection:
        assert connection.execute("select claimer from remediation.open_claims").fetchone()[0] is None


def test_deleting_your_data_releases_your_claims_and_removes_your_lists_hours_and_name(db):
    claim_id = claim(db)
    db.call("claimer", "set_display_name", "Leaver")
    db.call("claimer", "log_hours", claim_id, Decimal(2))
    db.call("claimer", "create_list", "Mine", [SITE])
    finished = done(db, site=NEIGHBOUR)
    db.call("claimer", "delete_my_data")
    assert db.call("claimer", "me") == {"display_name": None}
    assert db.call("claimer", "my_lists") == []
    assert db.call("anyone", "read_claim", claim_id)["state"] == "released"
    kept = db.call("anyone", "read_claim", finished)
    # The work stays, as the site's history, without the name or the hours.
    assert kept["state"] == "done" and kept["claimer"] is None and kept["hours"] is None


def test_the_open_views_show_an_overdue_claim_as_released_and_only_done_photos(db):
    overdue = claim(db)
    db.age(overdue, due_at="now() - interval '1 minute'")
    in_progress = claim(db, "worker", (NEIGHBOUR,))
    photo(db, in_progress, "before", 1, who="worker")
    with db.acting(None) as connection:
        states = dict(connection.execute("select id::text, state from remediation.open_claims").fetchall())
        photos = connection.execute("select count(*) from remediation.open_photos").fetchone()[0]
    assert states[overdue] == "released" and states[in_progress] == "in_progress"
    assert photos == 0
