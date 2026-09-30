"""Tests for the volunteer trail monitor commitment (#763).

Two of these are about things that are deliberately absent, and they are the
ones worth keeping:

- **The seven-day cap**, which is what stops this being a streak. A window
  that ends cannot become an obligation that accumulates.
- **No completion state anywhere.** Closing early records that it ended and
  nothing about how much of it was used, because a partial week is a week's
  worth of real work.
"""

import uuid
from datetime import date, timedelta

from tests.factories import make_profile
from tests.tokens import auth_headers


def _window(days, start_offset=0):
    start = date.today() + timedelta(days=start_offset)
    return {
        "starts_on": start.isoformat(),
        "ends_on": (start + timedelta(days=days - 1)).isoformat(),
        "tasks": ["cleanup_packout"],
    }


def test_a_commitment_needs_an_account(client):
    assert client.post("/ridge-runner", json=_window(3)).status_code == 401


def test_a_seven_day_window_is_the_longest_allowed(client, db_session):
    person = make_profile(db_session)

    assert client.post("/ridge-runner", json=_window(7), headers=auth_headers(person.id)).status_code == 201


def test_an_eight_day_window_is_refused_and_says_why(client, db_session):
    person = make_profile(db_session)

    response = client.post("/ridge-runner", json=_window(8), headers=auth_headers(person.id))

    assert response.status_code == 422
    assert "obligation that accumulates" in str(response.json())


def test_a_one_day_window_counts_as_one_day(client, db_session):
    """Inclusive, so a window that starts and ends today is a day rather than
    zero of them."""
    person = make_profile(db_session)

    assert client.post("/ridge-runner", json=_window(1), headers=auth_headers(person.id)).status_code == 201


def test_a_task_this_app_does_not_know_is_refused(client, db_session):
    person = make_profile(db_session)
    payload = {**_window(3), "tasks": ["cleanup_packout", "fly_a_drone"]}

    response = client.post("/ridge-runner", json=payload, headers=auth_headers(person.id))

    assert response.status_code == 422


def test_a_commitment_with_no_tasks_is_refused(client, db_session):
    """The tasks are what the app asks about, so a window with none is a window
    that does nothing."""
    person = make_profile(db_session)
    payload = {**_window(3), "tasks": []}

    assert client.post("/ridge-runner", json=payload, headers=auth_headers(person.id)).status_code == 422


def test_windows_cannot_be_chained_to_get_past_the_cap(client, db_session):
    """Open the next before the last ends and the cap stops capping anything."""
    person = make_profile(db_session)
    client.post("/ridge-runner", json=_window(7), headers=auth_headers(person.id))

    response = client.post("/ridge-runner", json=_window(7, start_offset=3), headers=auth_headers(person.id))

    assert response.status_code == 409
    assert "Close it first" in response.json()["detail"]


def test_a_window_after_the_last_one_ends_is_fine(client, db_session):
    """The cap is on one window, not on how much somebody may do in a season."""
    person = make_profile(db_session)
    client.post("/ridge-runner", json=_window(7), headers=auth_headers(person.id))

    response = client.post("/ridge-runner", json=_window(7, start_offset=8), headers=auth_headers(person.id))

    assert response.status_code == 201


def test_closing_early_records_that_it_ended_and_nothing_else(client, db_session):
    """No percentage, no days kept, no streak - the record shows what was
    submitted, never what was expected and missed."""
    person = make_profile(db_session)
    commitment = client.post("/ridge-runner", json=_window(7), headers=auth_headers(person.id)).json()

    closed = client.post(f"/ridge-runner/{commitment['id']}/close", headers=auth_headers(person.id))

    assert closed.status_code == 200
    body = closed.json()
    assert body["ended_early_at"] is not None
    assert not any("complet" in key or "streak" in key or "progress" in key for key in body)


def test_closing_a_window_ends_it_today_rather_than_in_the_future(client, db_session):
    """Otherwise the app stays in monitor mode for a window somebody closed."""
    person = make_profile(db_session)
    commitment = client.post("/ridge-runner", json=_window(7), headers=auth_headers(person.id)).json()

    closed = client.post(f"/ridge-runner/{commitment['id']}/close", headers=auth_headers(person.id)).json()

    assert closed["ends_on"] == date.today().isoformat()


def test_nobody_can_close_somebody_elses_window(client, db_session):
    person = make_profile(db_session)
    commitment = client.post("/ridge-runner", json=_window(3), headers=auth_headers(person.id)).json()

    response = client.post(f"/ridge-runner/{commitment['id']}/close", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 404


def test_there_is_no_public_read_of_anybodys_commitment(client, db_session):
    """The role is a mode the app is in, visible to its user and to the
    organization receiving the data, and to nobody else. The app issues
    nothing that functions as a badge."""
    person = make_profile(db_session)
    client.post("/ridge-runner", json=_window(3), headers=auth_headers(person.id))

    other = client.get("/ridge-runner/mine", headers=auth_headers(str(uuid.uuid4())))

    assert other.status_code == 200
    assert other.json() == []


def test_the_tasks_come_back_as_a_list(client, db_session):
    person = make_profile(db_session)
    payload = {**_window(3), "tasks": ["trail_clearance", "cleanup_packout"]}

    body = client.post("/ridge-runner", json=payload, headers=auth_headers(person.id)).json()

    assert body["tasks"] == ["cleanup_packout", "trail_clearance"]
