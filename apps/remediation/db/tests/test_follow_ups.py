"""Follow-up visits (PLAN.md §6; decided 2026-10-28): three for each restored
site, each opening the day after Labor Day in the three years after the work
was done, anyone's to take for 14 days."""

import datetime

import pytest
from conftest import NEIGHBOUR, SITE, status
from test_claims import claim, done, photo


def day_after_labor_day(year: int) -> datetime.date:
    first = datetime.date(year, 9, 1)
    return first + datetime.timedelta(days=(7 - first.weekday()) % 7 + 1)


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2025, "2025-09-02"), (2026, "2026-09-08"), (2027, "2027-09-07"), (2031, "2031-09-02")],
)
def test_peak_season_ends_the_day_after_the_first_monday_in_september(db, year, expected):
    assert str(db.owner("select remediation._day_after_labor_day(%s)", year)[0][0]) == expected


def follow_ups(db, site=SITE, who="anyone"):
    return db.call(who, "site_follow_ups", site)


def open_now(db, follow_up_id):
    """Moves a follow-up's window to today, as the turn of the year would."""
    db.connection.execute(
        "update remediation.follow_up set opens_on = current_date, closes_on = current_date + 365 where id = %s",
        (follow_up_id,),
    )


def test_marking_a_restoration_done_schedules_three_visits_after_the_next_three_labor_days(db):
    done(db)
    visits = follow_ups(db)
    today = datetime.date.today()
    first_year = today.year if day_after_labor_day(today.year) > today else today.year + 1
    assert [(v["visit"], v["opens_on"], v["closes_on"], v["state"]) for v in visits] == [
        (n, str(day_after_labor_day(first_year + n - 1)), str(day_after_labor_day(first_year + n)), "waiting") for n in (1, 2, 3)
    ]


def test_a_visit_cannot_be_taken_before_it_opens(db):
    done(db)
    error = db.refused("visitor", "take_follow_up", follow_ups(db)[0]["id"])
    assert status(error) == "PT409" and "opens on" in str(error)


def test_anyone_may_take_an_open_visit_and_only_one_person_at_a_time(db):
    done(db)
    first = follow_ups(db)[0]["id"]
    open_now(db, first)
    taken = db.call("visitor", "take_follow_up", first)
    assert taken["kind"] == "follow_up" and taken["visit"] == 1 and taken["state"] == "claimed"
    assert status(db.refused("second-visitor", "take_follow_up", first)) == "PT409"
    assert follow_ups(db)[0]["state"] == "taken"


def test_a_restored_site_is_not_claimed_again_from_scratch_while_its_visits_are_to_come(db):
    done(db)
    error = db.refused("someone", "claim_sites", [SITE])
    assert status(error) == "PT409" and "follow-up" in str(error)


def test_a_visit_rephotographs_the_points_against_the_restorations_after_photos(db):
    done(db)
    first = follow_ups(db)[0]["id"]
    open_now(db, first)
    visit = db.call("visitor", "take_follow_up", first)["id"]
    reference = db.call("visitor", "read_claim", visit)["reference"]
    assert sorted((p["phase"], p["point"]) for p in reference) == [("after", 1), ("after", 2)]
    db.upload("visitor", visit, "before-again")
    assert status(db.refused("visitor", "add_photo", visit, "before", 1, "before-again", None)) == "PT422"
    started = photo(db, visit, "after", 1, who="visitor", client_id="again-1")
    assert started["state"] == "in_progress"
    error = db.refused("visitor", "finish_claim", visit, [], None)
    assert status(error) == "PT422" and "after at point 2" in str(error) and "before at point" not in str(error)
    photo(db, visit, "after", 2, who="visitor", client_id="again-2")
    assert db.call("visitor", "finish_claim", visit, ["Moved the debris back"], None)["state"] == "done"
    assert follow_ups(db)[0]["state"] == "done"
    assert status(db.refused("another", "take_follow_up", first)) == "PT409"
    # A visit schedules no visits of its own.
    assert db.owner("select count(*) from remediation.follow_up")[0][0] == 3


def test_a_visit_taken_and_not_done_in_time_opens_again(db):
    done(db)
    first = follow_ups(db)[0]["id"]
    open_now(db, first)
    visit = db.call("visitor", "take_follow_up", first)["id"]
    db.age(visit, due_at="now() - interval '1 minute'")
    assert follow_ups(db)[0]["state"] == "open"
    db.call("second-visitor", "take_follow_up", first)


def test_a_visit_nobody_took_before_the_next_one_opened_is_missed(db):
    done(db)
    first = follow_ups(db)[0]["id"]
    db.connection.execute(
        "update remediation.follow_up set opens_on = current_date - 400, closes_on = current_date - 35 where id = %s",
        (first,),
    )
    assert follow_ups(db)[0]["state"] == "missed"
    assert status(db.refused("visitor", "take_follow_up", first)) == "PT409"


def test_the_visits_are_open_data(db):
    done(db, site=NEIGHBOUR)
    with db.acting(None) as connection:
        rows = connection.execute("select visit, state from remediation.open_follow_ups order by visit").fetchall()
    assert rows == [(1, "waiting"), (2, "waiting"), (3, "waiting")]


def test_a_released_restoration_schedules_nothing(db):
    claim_id = claim(db)
    db.call("claimer", "release_claim", claim_id)
    assert follow_ups(db) == []
