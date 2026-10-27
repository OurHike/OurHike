"""Claims, crews, photos, reviews and hours: the old API's phase 3 behaviour
(#1910) and every security finding its five review passes proved, now in SQL."""

import threading
from decimal import Decimal

import psycopg
import pytest
from conftest import BUCKET, NEIGHBOUR, SCORES_WELL, SITE, status, uid


def claim(db, who="claimer", sites=(SITE,)):
    return db.call(who, "claim_sites", list(sites))[0]["id"]


def photo(db, claim_id, phase, point=None, who="claimer", client_id=None, replaces=None):
    client_id = client_id or f"{phase}-{point}-{who}"
    db.upload(who, claim_id, client_id)
    return db.call(who, "add_photo", claim_id, phase, point, client_id, replaces)


def photograph(db, claim_id, phases=("before", "after"), who="claimer", tag=""):
    for point in (1, 2):
        for phase in phases:
            photo(db, claim_id, phase, point, who, client_id=f"{phase}-{point}-{who}{tag}")


def submitted(db, who="claimer", site=SITE):
    claim_id = claim(db, who, (site,))
    photograph(db, claim_id, who=who)
    db.call(who, "log_hours", claim_id, Decimal("2.5"))
    db.call(who, "submit_claim", claim_id, ["Hide the site", "Block the way in"], "Done")
    return claim_id


def join(db, claim_id, who, inviter="claimer"):
    token = db.call(inviter, "make_invite", claim_id)["token"]
    return db.call(who, "join_claim", token)


# --- Claiming ---------------------------------------------------------------------


def test_a_claim_lasts_fourteen_days_and_holds_the_site_against_a_second_claim(db):
    claim_id = claim(db)
    detail = db.call("claimer", "read_claim", claim_id)
    assert detail["state"] == "claimed" and detail["you_are_crew"] is True
    days = db.owner("select extract(day from due_at - claimed_at) from steward.claim where id = %s", claim_id)[0][0]
    assert days == 14
    assert status(db.refused("someone-else", "claim_sites", [SITE])) == "PT409"


def test_only_a_site_the_analysis_says_needs_work_can_be_claimed(db):
    assert status(db.refused("claimer", "claim_sites", [SCORES_WELL])) == "PT422"
    assert status(db.refused("claimer", "claim_sites", ["no-such-site"])) == "PT422"
    assert status(db.refused("claimer", "claim_sites", [])) == "PT422"


def test_claiming_a_cluster_is_all_or_nothing(db):
    claim(db, "first", (NEIGHBOUR,))
    assert status(db.refused("second", "claim_sites", [SITE, NEIGHBOUR])) == "PT409"
    assert db.call("second", "claim_for_site", SITE) is None


def test_two_claims_on_one_site_at_the_same_moment_end_with_one_claim(db, database_url):
    # The partial unique index refuses the second insert, whichever commits first.
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt(who):
        with psycopg.connect(database_url, autocommit=True) as connection:
            from conftest import Db

            other = Db(connection)
            barrier.wait()
            try:
                other.call(who, "claim_sites", [SITE])
                outcomes.append("claimed")
            except psycopg.Error as error:
                outcomes.append(error.sqlstate)

    threads = [threading.Thread(target=attempt, args=(name,)) for name in ("one", "two")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes) == ["PT409", "claimed"]


def test_a_claim_past_its_due_time_is_released_and_the_site_can_be_claimed_again(db):
    claim_id = claim(db)
    db.age(claim_id, due_at="now() - interval '1 minute'")
    assert db.call("claimer", "read_claim", claim_id)["state"] == "released"
    claim(db, "next-person")


def test_only_the_claimer_can_release_and_releasing_opens_the_site(db):
    claim_id = claim(db)
    join(db, claim_id, "friend")
    assert status(db.refused("friend", "release_claim", claim_id)) == "PT403"
    assert db.call("claimer", "release_claim", claim_id)["state"] == "released"
    claim(db, "next-person")


def test_the_hold_limit_counts_sites_waiting_for_review_since_they_still_hold_the_site(db):
    sites = [f"{n:08d}-0000-0000-0000-000000000000" for n in range(11)]
    db.connection.execute(
        "insert into steward.site (rims_id, club, workable) select unnest(%s::text[]), 'Example Trail Club', true", (sites,)
    )
    for site in sites[:10]:
        claim(db, "hoarder", (site,))
    assert status(db.refused("hoarder", "claim_sites", [sites[10]])) == "PT409"


# --- The crew ---------------------------------------------------------------------


def test_an_invite_link_adds_whoever_opens_it_to_the_crew_and_a_new_link_ends_the_old(db):
    claim_id = claim(db)
    first = db.call("claimer", "make_invite", claim_id)["token"]
    assert db.call("friend", "join_claim", first)["you_are_crew"] is True
    second = db.call("friend", "make_invite", claim_id)["token"]
    assert status(db.refused("late", "join_claim", first)) == "PT404"
    db.call("late", "join_claim", second)
    assert db.call("claimer", "read_claim", claim_id)["crew_size"] == 3


def test_a_crew_is_capped(db):
    claim_id = claim(db)
    token = db.call("claimer", "make_invite", claim_id)["token"]
    for n in range(11):
        db.call(f"member-{n}", "join_claim", token)
    assert status(db.refused("one-too-many", "join_claim", token)) == "PT409"


def test_someone_off_the_crew_cannot_photograph_invite_log_hours_or_submit(db):
    claim_id = claim(db)
    for function, args in (
        ("make_invite", ()),
        ("log_hours", (Decimal(2),)),
        ("submit_claim", ([], None)),
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
    assert [p["path"] for p in again["photos"]] == [db.object_name("claimer", claim_id, "retake")]
    # Named, so the app deletes it: a retake should not leave the first readable.
    assert again["unused_path"] == db.object_name("claimer", claim_id, "first")
    with db.acting("claimer") as connection:
        connection.execute("delete from storage.objects where name = %s", (again["unused_path"],))
    assert db.owner("select name from storage.objects") == [(db.object_name("claimer", claim_id, "retake"),)]


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
        "{claim}/{me}/photo.png",
        "{claim}/{me}/sub/photo.jpg",
        "{claim}/{me}/../x.jpg",
        "not-a-claim/{me}/photo.jpg",
        "{other}/{me}/photo.jpg",
        "{claim}/photo.jpg",
        "{claim}/{crewmate}/photo.jpg",
        "{claim}/{my_user_id}/photo.jpg",
    ],
    ids=["not-jpg", "nested", "dot-dot", "not-a-claim", "other-claim", "no-folder", "crewmates-folder", "user-id-folder"],
)
def test_the_bucket_takes_only_a_crews_jpeg_in_the_uploaders_own_folder_on_the_claim(db, name):
    # The sixth pass's finding 2: with no uploader in the name, any crew member
    # could take the name a crewmate's phone was about to upload under.
    claim_id = claim(db)
    join(db, claim_id, "crewmate")
    other = claim(db, "someone-else", (NEIGHBOUR,))
    names = {
        "claim": claim_id,
        "other": other,
        "me": db.folder("claimer", claim_id),
        "crewmate": db.folder("crewmate", claim_id),
        "my_user_id": uid("claimer"),
    }
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.acting("claimer") as connection:
            connection.execute(
                "insert into storage.objects (bucket_id, name, owner_id) values (%s, %s, %s)",
                (BUCKET, name.format(**names), uid("claimer")),
            )


def test_a_photos_address_names_no_account_and_links_no_two_claims(db):
    # The re-check: the user id in the path was the person's OurHike account id,
    # shown to every reviewer of a submitted claim while their name was hidden.
    first = claim(db)
    second = claim(db, sites=(NEIGHBOUR,))
    paths = [photo(db, claim_id, "extra", client_id="a")["photos"][0]["path"] for claim_id in (first, second)]
    assert all(uid("claimer") not in path for path in paths)
    assert paths[0].split("/")[1] != paths[1].split("/")[1]
    assert db.call("claimer", "photo_folder", first) == paths[0].split("/")[1]


def test_only_the_crew_is_told_its_folder_on_a_claim(db):
    claim_id = claim(db)
    assert status(db.refused("stranger", "photo_folder", claim_id)) == "PT403"
    photograph(db, claim_id)
    db.call("claimer", "submit_claim", claim_id, [], None)
    # Still answered once submitted, so a photo sent again finds its object.
    assert db.call("claimer", "photo_folder", claim_id) == db.folder("claimer", claim_id)


def test_nothing_can_be_uploaded_to_a_claim_that_is_no_longer_open(db):
    claim_id = submitted(db)
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


def test_the_crew_may_delete_an_object_a_photo_was_replaced_out_of_and_nothing_else(db):
    claim_id = claim(db)
    join(db, claim_id, "crewmate")
    photo(db, claim_id, "before", 1, client_id="replaced")
    photo(db, claim_id, "before", 1, client_id="kept")
    # On its way to the claim: the sixth pass's finding 2 was that any crew
    # member could delete it first, and have the photo refused as not arrived.
    db.upload("crewmate", claim_id, "in-flight")
    with db.acting("claimer") as connection:
        gone = connection.execute("delete from storage.objects where bucket_id = %s returning name", (BUCKET,)).fetchall()
    assert gone == [(db.object_name("claimer", claim_id, "replaced"),)]
    assert sorted(db.owner("select name from storage.objects")) == sorted(
        [(db.object_name("claimer", claim_id, "kept"),), (db.object_name("crewmate", claim_id, "in-flight"),)]
    )
    assert db.call("crewmate", "add_photo", claim_id, "extra", None, "in-flight", None)["photos"]


def test_a_crew_member_cannot_put_a_crewmates_upload_on_the_claim_as_their_own(db):
    claim_id = claim(db)
    join(db, claim_id, "crewmate")
    db.upload("crewmate", claim_id, "theirs")
    assert status(db.refused("claimer", "add_photo", claim_id, "extra", None, "theirs", None)) == "PT422"


# --- Who reads a photo ------------------------------------------------------------
# The sixth pass's finding 1: a public bucket on OurHike's project was anyone's
# free file host. Private now; the select policy is who may download a photo
# or sign a link to one.


def test_a_photo_is_its_crews_until_submitted_then_reviewers_then_everyones_once_verified(db):
    claim_id = claim(db)
    photograph(db, claim_id)
    before = db.object_name("claimer", claim_id, "before-1-claimer")
    assert db.sees("claimer", before)
    assert not db.sees("stranger", before) and not db.sees(None, before)
    db.call("claimer", "submit_claim", claim_id, [], None)
    assert db.sees("reviewer", before)
    assert not db.sees("guest", before, anonymous=True) and not db.sees(None, before)
    db.call("reviewer", "review_claim", claim_id, "verify", None)
    assert db.sees(None, before) and db.sees("guest", before, anonymous=True)


def test_an_object_no_photo_uses_is_nobodys_to_read_not_even_its_uploaders(db):
    claim_id = claim(db)
    pending = db.upload("claimer", claim_id, "not-yet-on-the-claim")
    assert not db.sees("claimer", pending)
    photo(db, claim_id, "before", 1, client_id="replaced")
    photo(db, claim_id, "before", 1, client_id="kept")
    freed = db.object_name("claimer", claim_id, "replaced")
    # Readable only so the crew can delete it, and only while the claim is worked.
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
    folder = db.folder("claimer", released)
    db.call("claimer", "release_claim", released)
    claim_id = claim(db)
    for prefix, age in (("yesterday", "25 hours"), ("today", "1 hour")):
        db.connection.execute(
            "insert into storage.objects (bucket_id, name, created_at)"
            " select %s, %s || '/' || %s || '/' || %s || '-' || n || '.jpg', now() - %s::interval"
            " from generate_series(1, 149) n",
            (BUCKET, released, folder, prefix, age),
        )
    db.upload("claimer", claim_id, "the-150th")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("claimer", claim_id, "the-151st")


def test_a_queued_photo_sent_again_after_a_lost_answer_is_stored_once(db):
    # The third pass's P2.
    claim_id = claim(db)
    photo(db, claim_id, "extra", client_id="queued-1")
    again = db.call("claimer", "add_photo", claim_id, "extra", None, "queued-1", None)
    assert len(again["photos"]) == 1


def test_a_photo_sent_again_after_the_claim_was_submitted_is_answered_not_refused(db):
    claim_id = submitted(db)
    assert db.call("claimer", "add_photo", claim_id, "before", 1, "before-1-claimer", None)["state"] == "submitted"
    assert status(db.refused("stranger", "add_photo", claim_id, "before", 1, "before-1-claimer", None)) == "PT403"


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
    claim_id = claim(db)
    join(db, claim_id, "friend")
    friends = photo(db, claim_id, "after", 1, who="friend", client_id="friend-photo")["photos"][0]["id"]
    db.upload("claimer", claim_id, "my-old-photo")
    assert status(db.refused("claimer", "add_photo", claim_id, "after", 1, "my-old-photo", "nothing")) == "PT412"
    assert [p["id"] for p in db.call("claimer", "read_claim", claim_id)["photos"]] == [friends]
    db.upload("claimer", claim_id, "my-new-photo")
    over = db.call("claimer", "add_photo", claim_id, "after", 1, "my-new-photo", friends)
    assert [p["id"] for p in over["photos"]] != [friends]


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
    assert db.owner("select count(*) from steward.photo")[0][0] == 1


def test_a_claim_holds_at_most_40_photos(db):
    claim_id = claim(db)
    for n in range(40):
        photo(db, claim_id, "extra", client_id=f"extra-{n}")
    db.upload("claimer", claim_id, "extra-40")
    assert status(db.refused("claimer", "add_photo", claim_id, "extra", None, "extra-40", None)) == "PT409"


# --- Hours, submitting, reviewing ---------------------------------------------------


@pytest.mark.parametrize("hours", [0, -1, 0.3, 72.5])
def test_hours_are_in_half_hours_and_bounded(db, hours):
    claim_id = claim(db)
    assert status(db.refused("claimer", "log_hours", claim_id, Decimal(str(hours)))) == "PT422"


def test_submitting_needs_both_photo_points_before_and_after(db):
    claim_id = claim(db)
    photo(db, claim_id, "before", 1)
    error = db.refused("claimer", "submit_claim", claim_id, [], None)
    assert status(error) == "PT422" and "after at point 1, before at point 2, after at point 2" in str(error)


def test_a_submission_stops_the_clock_so_a_slow_reviewer_never_costs_the_claim(db):
    claim_id = submitted(db)
    db.age(claim_id, due_at="now() - interval '1 day'")
    assert db.call("reviewer", "read_claim", claim_id)["state"] == "submitted"


def test_nobody_on_the_crew_can_review_their_own_submission(db):
    claim_id = claim(db)
    join(db, claim_id, "friend")
    photograph(db, claim_id)
    db.call("claimer", "submit_claim", claim_id, [], None)
    for who in ("claimer", "friend"):
        assert status(db.refused(who, "review_claim", claim_id, "verify", None)) == "PT403"
        assert claim_id not in [c["id"] for c in db.call(who, "reviews")]
    assert claim_id in [c["id"] for c in db.call("reviewer", "reviews")]


def test_verifying_confirms_the_crews_hours_and_keeps_the_reviewers_name_as_it_was(db):
    claim_id = submitted(db)
    db.call("reviewer", "set_display_name", "Club Coordinator")
    verified = db.call("reviewer", "review_claim", claim_id, "verify", None)
    db.call("reviewer", "set_display_name", "Renamed")
    assert verified["state"] == "verified" and verified["reviewed_by"] == "Club Coordinator"
    assert db.call("claimer", "my_hours") == {"verified": 2.5, "waiting": 0, "claims": 1}


def test_sending_back_or_rejecting_needs_a_reason(db):
    claim_id = submitted(db)
    for verdict in ("send_back", "reject"):
        assert status(db.refused("reviewer", "review_claim", claim_id, verdict, None)) == "PT422"
    assert status(db.refused("reviewer", "review_claim", claim_id, "maybe", "Hmm")) == "PT422"


def test_a_send_back_gives_the_crew_back_the_time_it_had_left_and_at_least_the_minimum(db):
    # The review's finding 9: a send-back used to reset the clock to 7 days.
    plenty = submitted(db)
    db.age(plenty, submitted_at="now() - interval '1 day'", due_at="now() + interval '9 days'")
    back = db.call("reviewer", "review_claim", plenty, "send_back", "Retake point 2")
    left = db.owner("select extract(day from due_at - now()) from steward.claim where id = %s", back["id"])[0][0]
    assert left >= 9
    short = submitted(db, "second", NEIGHBOUR)
    db.age(short, submitted_at="now()", due_at="now() + interval '1 day'")
    db.call("reviewer", "review_claim", short, "send_back", "Retake")
    left = db.owner("select extract(day from due_at - now()) from steward.claim where id = %s", short)[0][0]
    assert left >= 6


def test_after_a_send_back_the_after_photos_must_be_retaken(db):
    claim_id = submitted(db)
    db.call("reviewer", "review_claim", claim_id, "send_back", "Closer, please")
    db.age(claim_id, sent_back_at="now() + interval '1 second'")
    error = db.refused("claimer", "submit_claim", claim_id, [], None)
    assert "retaken since it was sent back" in str(error)


def test_rejecting_releases_the_site_counts_no_hours_and_bars_the_rejecter_from_it(db):
    claim_id = submitted(db)
    rejected = db.call("rejecter", "review_claim", claim_id, "reject", "Not this site")
    assert rejected["state"] == "released"
    assert db.call("claimer", "my_hours")["verified"] == 0
    assert status(db.refused("rejecter", "claim_sites", [SITE])) == "PT409"
    claim(db, "somebody-else")


# --- Deleting your data -----------------------------------------------------------


def test_deleting_your_data_releases_your_claims_and_removes_your_lists_hours_and_name(db):
    claim_id = claim(db)
    db.call("claimer", "set_display_name", "Leaver")
    db.call("claimer", "log_hours", claim_id, Decimal(2))
    db.call("claimer", "create_list", "Mine", [SITE])
    db.call("claimer", "delete_my_data")
    assert db.call("claimer", "me") == {"display_name": None}
    assert db.call("claimer", "my_lists") == [] and db.call("claimer", "my_claims") == []
    assert db.call("anyone", "read_claim", claim_id)["state"] == "released"
    assert db.owner("select count(*) from steward.claim_member where claim_id = %s and left_at is null", claim_id) == [(0,)]


def test_deleting_your_data_takes_you_off_every_crew_but_never_onto_its_reviewers(db):
    # The third pass, on N7.
    claim_id = claim(db)
    join(db, claim_id, "leaver")
    db.call("leaver", "delete_my_data")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.upload("leaver", claim_id, "after-leaving")
    photograph(db, claim_id)
    db.call("claimer", "submit_claim", claim_id, [], None)
    assert db.call("leaver", "read_claim", claim_id)["you_may_review"] is False
    assert status(db.refused("leaver", "review_claim", claim_id, "verify", None)) == "PT403"


def test_someone_who_left_by_deleting_their_data_can_be_invited_back(db):
    claim_id = claim(db)
    join(db, claim_id, "leaver")
    db.call("leaver", "delete_my_data")
    join(db, claim_id, "leaver")
    assert [c["id"] for c in db.call("leaver", "my_claims")] == [claim_id]


def test_deleting_your_data_does_not_reset_how_many_sites_you_hold(db):
    # The fourth pass's B.
    db.connection.execute("update steward.site set workable = true")
    db.connection.execute(
        "insert into steward.site (rims_id, club, workable)"
        " select lpad(n::text, 8, '0') || '-0000-0000-0000-000000000000', 'Example Trail Club', true"
        " from generate_series(1, 11) n"
    )
    for n in range(1, 11):
        submitted(db, "hoarder", f"{n:08d}-0000-0000-0000-000000000000")
    db.call("hoarder", "delete_my_data")
    assert status(db.refused("hoarder", "claim_sites", ["00000011-0000-0000-0000-000000000000"])) == "PT409"


# --- Who is named -----------------------------------------------------------------


def test_names_on_a_claim_show_to_its_crew_and_to_others_only_once_it_is_verified(db):
    # Decided 2026-10-27, by poll: the public sees that a site is claimed and
    # when it is due, not who will be out there.
    claim_id = claim(db)
    db.call("claimer", "set_display_name", "Ridge Runner")
    assert db.call("claimer", "read_claim", claim_id)["claimer"] == "Ridge Runner"
    stranger_view = db.call("stranger", "read_claim", claim_id)
    assert stranger_view["claimer"] is None and stranger_view["crew"] == []
    with db.acting(None) as connection:
        assert connection.execute("select claimer from steward.open_claims").fetchone()[0] is None
    photograph(db, claim_id)
    db.call("claimer", "submit_claim", claim_id, [], None)
    db.call("reviewer", "review_claim", claim_id, "verify", None)
    assert db.call("stranger", "read_claim", claim_id)["claimer"] == "Ridge Runner"
    with db.acting(None) as connection:
        assert connection.execute("select claimer from steward.open_claims").fetchone()[0] == "Ridge Runner"


def test_a_claims_report_and_photos_are_its_crews_then_its_reviewers_then_everyones(db):
    # The sixth pass's finding 3: notes, the review note and every photo's
    # address went to any signed-in account. `full` says which view this is,
    # so an empty list is never read as no photos.
    claim_id = claim(db)
    photograph(db, claim_id)
    db.call("claimer", "log_hours", claim_id, Decimal(3))
    outside = db.call("stranger", "read_claim", claim_id)
    assert outside["full"] is False and outside["state"] == "in_progress" and outside["crew_size"] == 1
    assert outside["photos"] == [] and outside["notes"] is None and outside["crew"] == []
    assert db.call("claimer", "read_claim", claim_id)["full"] is True
    db.call("claimer", "submit_claim", claim_id, ["Hide the site"], "Brushed in the path")
    reviewer_view = db.call("reviewer", "read_claim", claim_id)
    assert reviewer_view["full"] is True and reviewer_view["notes"] == "Brushed in the path"
    assert reviewer_view["you_may_review"] is True and len(reviewer_view["photos"]) == 4
    # The re-check: anyone may send a claim back, so doing it must not keep
    # them a view of the crew's next round of work.
    sent_back = db.call("reviewer", "review_claim", claim_id, "send_back", "The after photo at point 2 is blurred")
    assert sent_back["full"] is False and sent_back["notes"] is None
    assert db.call("stranger", "read_claim", claim_id)["review_note"] is None
    assert db.call("claimer", "read_claim", claim_id)["review_note"] == "The after photo at point 2 is blurred"
    photograph(db, claim_id, phases=("after",), tag="-again")
    db.call("claimer", "submit_claim", claim_id, [], "Retaken")
    # Rejecting closes the claim; whoever did it still sees the verdict they gave.
    rejected = db.call("second-reviewer", "review_claim", claim_id, "reject", "Not this site")
    assert rejected["full"] is True and rejected["review_note"] == "Not this site"


def test_the_open_views_show_an_overdue_claim_as_released_and_only_verified_photos(db):
    overdue = claim(db)
    db.age(overdue, due_at="now() - interval '1 minute'")
    in_progress = claim(db, "worker", (NEIGHBOUR,))
    photo(db, in_progress, "before", 1, who="worker")
    with db.acting(None) as connection:
        states = dict(connection.execute("select id::text, state from steward.open_claims").fetchall())
        photos = connection.execute("select count(*) from steward.open_photos").fetchone()[0]
    assert states[overdue] == "released" and states[in_progress] == "in_progress"
    assert photos == 0
