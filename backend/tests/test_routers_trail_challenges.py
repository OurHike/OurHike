"""Tests for app/routers/trail_challenges.py (#1780, features/CHALLENGES.md).

Three things the design's "What proves it" asks of the backend, and what each
section below holds:

- **A repeated tag is idempotent** - on the outbox's id, and on the place
  itself when a second device tags it again under a new id.
- **Counts never carry a name**, and a count of fewer than
  `CHALLENGE_COUNT_FLOOR` distinct hikers is withheld as `null`.
- **An entry after close is refused, and only an org admin reads entries.**
  The refusal sentences are asserted to the letter, because the phone shows
  them as they are; the CSV is asserted cell by cell, because a club opens it
  in a spreadsheet.

The permission rows for the club routes live in test_org_permission_matrix.py
with every other org endpoint.
"""

import csv
import datetime as dt
import io
import uuid

import httpx
import pytest

from app.core.registry_pr import open_challenge_pr
from app.core.trail_challenge import CHALLENGE_COUNT_FLOOR, has_closed, spreadsheet_safe
from app.models.club import OrgState
from app.models.trail_challenge import ChallengeEntry, ChallengeTag, ClubChallenge, TagHow
from app.routers.trail_challenges import CSV_COLUMNS
from tests.factories import make_admin, make_org, make_profile
from tests.tokens import auth_headers

# `<slug>-<name>`, the shape the save route requires of an id.
CHALLENGE = "ramapo-trail-conference-fire-towers-2027"


def _definition(challenge_id: str = CHALLENGE, **fields) -> dict:
    """A reviewed-file-shaped definition, as the console saves one."""
    return {
        "id": challenge_id,
        "org": "ramapo-trail-conference",
        "trail": "LP",
        "name": "Fire towers of the Ramapos",
        "status": "draft",
        "window": {"opens": "2027-05-15", "closes": "2027-09-01"},
        "finish": {"count": 3, "label": "for the patch"},
        "reward": None,
        "sections": [{"id": "towers", "title": "Fire towers", "short": "Towers"}],
        "items": [
            {"id": "jackie-jones", "section": "towers", "title": "Jackie Jones fire tower", "match": {"kind": "self_report"}}
        ],
        **fields,
    }


def _own(db_session, club, challenge_id: str = CHALLENGE, **fields) -> ClubChallenge:
    """A challenge this club owns, written directly - the entry tests are
    about the entry route, not about saving."""
    row = ClubChallenge(
        challenge_id=challenge_id,
        club_id=club.id,
        # Published: a draft takes no entries and no finished notice, and
        # the save route would refuse `takes_entries` on one.
        definition=_definition(challenge_id, status="published"),
        **{"takes_entries": True, "window_closes": None, **fields},
    )
    db_session.add(row)
    db_session.commit()
    return row


def _tag(client, user_id: str, **overrides):
    body = {
        "id": str(uuid.uuid4()),
        "challenge_id": CHALLENGE,
        "item_id": "jackie-jones",
        "how": "gps",
        "authored_at": "2026-06-01T20:15:00Z",
        **overrides,
    }
    return client.post("/challenges/tags", json=body, headers=auth_headers(user_id))


def _enter(client, user_id: str, challenge_id: str = CHALLENGE, **overrides):
    body = {
        "id": str(uuid.uuid4()),
        # make_org's domain: the publisher domain the phone was shown.
        "org_domain": "ramapotrails.org",
        "name": "Jane Doe",
        "email": "jane@example.com",
        "item_ids": ["jackie-jones"],
        "consented": True,
        **overrides,
    }
    return client.post(f"/challenges/{challenge_id}/entries", json=body, headers=auth_headers(user_id))


@pytest.fixture
def club(db_session):
    """A claimed organization - the only state that owns a challenge."""
    return make_org(db_session, state=OrgState.claimed)


@pytest.fixture
def admin(db_session, club):
    person = make_profile(db_session)
    make_admin(db_session, club, person)
    return person


# ------------------------------------------------------------------ #
# POST /challenges/tags
# ------------------------------------------------------------------ #


def test_post_challenges_tags_needs_an_account(client):
    assert client.post("/challenges/tags", json={}).status_code == 401


def test_a_tag_resent_under_its_own_id_is_201_then_200_and_one_row(client, db_session):
    user_id = str(uuid.uuid4())
    tag_id = str(uuid.uuid4())

    first = _tag(client, user_id, id=tag_id)
    second = _tag(client, user_id, id=tag_id)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == tag_id
    assert db_session.query(ChallengeTag).count() == 1


def test_the_same_place_tagged_again_under_a_new_id_returns_the_first_tag_with_200(client, db_session):
    """Two devices, one hiker, one place: the same fact arriving twice."""
    user_id = str(uuid.uuid4())
    first = _tag(client, user_id, how="gps")

    again = _tag(client, user_id, how="hand")

    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    # The first stands - a later hand tap does not demote a walked tag.
    assert again.json()["how"] == "gps"
    assert db_session.query(ChallengeTag).count() == 1


def test_a_tag_id_that_belongs_to_another_hiker_is_409(client, db_session):
    tag_id = str(uuid.uuid4())
    assert _tag(client, str(uuid.uuid4()), id=tag_id).status_code == 201

    stolen = _tag(client, str(uuid.uuid4()), id=tag_id)

    assert stolen.status_code == 409
    assert stolen.json()["detail"] == "That tag id belongs to someone else."
    assert db_session.query(ChallengeTag).count() == 1


def test_a_tag_authored_more_than_five_minutes_ahead_is_422(client):
    tomorrow = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat()

    assert _tag(client, str(uuid.uuid4()), authored_at=tomorrow).status_code == 422


def test_a_tag_naming_an_id_the_pipeline_could_never_publish_is_422(client):
    """`ID_PATTERN` is pipeline/lib/challenges.py's `_ID`: an id outside it
    is not on any phone, so a tag of it is a tag of nothing."""
    assert _tag(client, str(uuid.uuid4()), item_id="../McAfee Knob").status_code == 422


def test_a_tag_for_a_challenge_no_club_has_saved_is_accepted_and_not_late(client):
    """The ATC's draft publishes from the reviewed file alone; its tags must
    not wait on a console row."""
    response = _tag(client, str(uuid.uuid4()), challenge_id="atc-summer-bucket-list-2027")

    assert response.status_code == 201
    # No `late` in the answer: it was an oracle for an id's owner and date.
    assert "late" not in response.json()


@pytest.mark.parametrize("authored_at", ["2025-08-30T15:00:00Z", "2025-09-10T12:00:00Z"])
def test_a_tag_after_window_closes_is_accepted(client, db_session, club, authored_at):
    _own(db_session, club, window_closes=dt.date(2025, 9, 1))

    response = _tag(client, str(uuid.uuid4()), authored_at=authored_at)

    assert response.status_code == 201


def test_the_window_closes_when_the_closing_day_has_ended_everywhere():
    """CLOSE_LEEWAY: 12:00 UTC the next day is midnight at UTC-12."""
    assert not has_closed(dt.date(2025, 9, 1), dt.datetime(2025, 9, 2, 11, 59))
    assert has_closed(dt.date(2025, 9, 1), dt.datetime(2025, 9, 2, 12, 0))


def test_a_tag_is_stored_in_utc_from_the_phones_own_offset(client, db_session):
    _tag(client, str(uuid.uuid4()), authored_at="2026-06-01T20:15:00-04:00")

    assert db_session.query(ChallengeTag).one().authored_at == dt.datetime(2026, 6, 2, 0, 15)


# ------------------------------------------------------------------ #
# POST /challenges/{challenge_id}/entries
# ------------------------------------------------------------------ #


def test_an_entry_for_a_challenge_no_club_owns_is_409_not_taking_entries(client):
    response = _enter(client, str(uuid.uuid4()))

    assert response.status_code == 409
    assert response.json()["detail"] == "This challenge's club is not taking entries through OurHike yet."


def test_an_entry_when_takes_entries_is_off_is_409_not_taking_entries(client, db_session, club):
    _own(db_session, club, takes_entries=False)

    response = _enter(client, str(uuid.uuid4()))

    assert response.status_code == 409
    assert response.json()["detail"] == "This challenge's club is not taking entries through OurHike yet."


def test_an_entry_is_409_when_the_club_owning_the_id_has_not_proved_the_domain_the_hiker_was_shown(client, db_session, club):
    """Owning an id is first come and a slug is whatever a registrant typed. A
    hiker whose finish screen named the ATC sends the ATC's domain, and a club
    that proved any other domain collects nothing - even one that registered
    the slug `atc` and saved the ATC's id."""
    _own(db_session, club)

    response = _enter(client, str(uuid.uuid4()), org_domain="appalachiantrail.org")

    assert response.status_code == 409
    assert response.json()["detail"] == "This challenge's club is not taking entries through OurHike yet."
    assert db_session.query(ChallengeEntry).count() == 0


def test_an_entry_for_a_challenge_owned_by_a_club_that_is_not_claimed_is_409(client, db_session, club):
    """`claimed` is the one state in which somebody proved the domain; a
    frozen or held organization collects nobody's address."""
    _own(db_session, club)
    club.state = OrgState.frozen
    db_session.commit()

    response = _enter(client, str(uuid.uuid4()))

    assert response.status_code == 409
    assert response.json()["detail"] == "This challenge's club is not taking entries through OurHike yet."


def test_an_entry_after_the_window_closes_is_409_naming_the_closing_date(client, db_session, club):
    _own(db_session, club, window_closes=dt.date(2025, 9, 1))

    response = _enter(client, str(uuid.uuid4()))

    assert response.status_code == 409
    assert response.json()["detail"] == "Entries for this challenge closed on September 1, 2025."
    assert db_session.query(ChallengeEntry).count() == 0


def test_an_entry_is_201_and_stored_as_sent(client, db_session, club):
    _own(db_session, club, window_closes=dt.date(2099, 9, 1))

    response = _enter(
        client,
        str(uuid.uuid4()),
        name="  Jane Doe  ",
        mailing_address="12 Reeves Meadow Rd\nSloatsburg NY",
        item_ids=["jackie-jones", "jackie-jones", "pine-meadow"],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jane Doe"
    assert body["item_ids"] == ["jackie-jones", "pine-meadow"]
    assert body["finished_only"] is False
    assert body["sent_at"].endswith("Z")


@pytest.mark.parametrize("consented", [False, None])
def test_an_entry_without_consented_true_is_422(client, db_session, club, consented):
    _own(db_session, club)
    overrides = {"consented": consented} if consented is not None else {}
    body = {"id": str(uuid.uuid4()), "name": "Jane", "email": "jane@example.com", "item_ids": ["jackie-jones"]}
    body.update(overrides)

    response = client.post(f"/challenges/{CHALLENGE}/entries", json=body, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 422


def test_an_entry_with_neither_email_nor_mailing_address_is_422(client, db_session, club):
    _own(db_session, club)

    response = _enter(client, str(uuid.uuid4()), email=None, mailing_address="   ")

    assert response.status_code == 422


def test_an_entry_listing_no_items_is_422(client, db_session, club):
    _own(db_session, club)

    assert _enter(client, str(uuid.uuid4()), item_ids=[]).status_code == 422


def test_an_entry_resent_under_its_own_id_is_200_even_after_the_window_closes(client, db_session, club):
    """A flush that committed and lost its response resends; it was accepted,
    so it is answered, not refused - whatever the date is now."""
    row = _own(db_session, club)
    user_id = str(uuid.uuid4())
    entry_id = str(uuid.uuid4())
    assert _enter(client, user_id, id=entry_id).status_code == 201
    row.window_closes = dt.date(2025, 9, 1)
    db_session.commit()

    again = _enter(client, user_id, id=entry_id)

    assert again.status_code == 200
    assert again.json()["id"] == entry_id
    assert db_session.query(ChallengeEntry).count() == 1


def test_a_second_entry_for_the_same_challenge_is_409_already_sent(client, db_session, club):
    _own(db_session, club)
    user_id = str(uuid.uuid4())
    assert _enter(client, user_id).status_code == 201

    second = _enter(client, user_id)

    assert second.status_code == 409
    assert second.json()["detail"] == "You have already sent an entry for this challenge."
    assert db_session.query(ChallengeEntry).count() == 1


def test_an_entry_id_that_belongs_to_another_hiker_is_409(client, db_session, club):
    _own(db_session, club)
    entry_id = str(uuid.uuid4())
    assert _enter(client, str(uuid.uuid4()), id=entry_id).status_code == 201

    assert _enter(client, str(uuid.uuid4()), id=entry_id).status_code == 409


# --- finished_only: the no-reward finish screen's "Let the club know" ---


def test_a_finished_notice_is_accepted_when_the_club_takes_no_entries(client, db_session, club):
    _own(db_session, club, takes_entries=False)

    response = _enter(client, str(uuid.uuid4()), email=None, item_ids=["jackie-jones"], finished_only=True)

    assert response.status_code == 201
    assert response.json()["finished_only"] is True
    stored = db_session.query(ChallengeEntry).one()
    assert stored.item_ids == []
    assert stored.email is None and stored.mailing_address is None


@pytest.mark.parametrize("contact", [{"email": "jane@example.com"}, {"mailing_address": "12 Reeves Meadow Rd"}])
def test_a_finished_notice_carrying_contact_details_is_422(client, db_session, club, contact):
    """Refused rather than dropped: "just tell them" never carries an
    address the hiker did not mean to send."""
    _own(db_session, club, takes_entries=False)

    response = _enter(client, str(uuid.uuid4()), **{"email": None, **contact}, item_ids=[], finished_only=True)

    assert response.status_code == 422
    assert db_session.query(ChallengeEntry).count() == 0


def test_a_finished_notice_still_needs_consented_true(client, db_session, club):
    _own(db_session, club, takes_entries=False)

    response = _enter(client, str(uuid.uuid4()), email=None, item_ids=[], finished_only=True, consented=False)

    assert response.status_code == 422


def test_a_finished_notice_is_409_when_no_club_owns_the_challenge_or_after_close(client, db_session, club):
    nobody = _enter(client, str(uuid.uuid4()), email=None, item_ids=[], finished_only=True)
    _own(db_session, club, takes_entries=False, window_closes=dt.date(2025, 9, 1))
    closed = _enter(client, str(uuid.uuid4()), email=None, item_ids=[], finished_only=True)

    assert nobody.status_code == 409
    assert nobody.json()["detail"] == "This challenge's club is not taking entries through OurHike yet."
    assert closed.status_code == 409
    assert closed.json()["detail"] == "Entries for this challenge closed on September 1, 2025."


# ------------------------------------------------------------------ #
# GET /clubs/{slug}/challenges and .../counts
# ------------------------------------------------------------------ #


def _hikers_tag(db_session, count: int, *, challenge_id: str = CHALLENGE, authored_at=dt.datetime(2026, 6, 1, 12)):
    for _ in range(count):
        hiker = make_profile(db_session)
        db_session.add(
            ChallengeTag(
                id=str(uuid.uuid4()),
                user_id=hiker.id,
                challenge_id=challenge_id,
                item_id="jackie-jones",
                how=TagHow.gps,
                authored_at=authored_at,
            )
        )
    db_session.commit()


def test_counts_withhold_hikers_in_below_challenge_count_floor(client, db_session, club, admin):
    _own(db_session, club)
    _hikers_tag(db_session, CHALLENGE_COUNT_FLOOR - 1)

    body = client.get(f"/clubs/{club.slug}/challenges/{CHALLENGE}/counts", headers=auth_headers(admin.id)).json()

    assert body["hikers_in"] is None
    assert body["hikers_in_floor"] == CHALLENGE_COUNT_FLOOR


def test_counts_show_hikers_in_at_challenge_count_floor_and_never_a_name(client, db_session, club, admin):
    _own(db_session, club)
    _hikers_tag(db_session, CHALLENGE_COUNT_FLOOR)

    body = client.get(f"/clubs/{club.slug}/challenges/{CHALLENGE}/counts", headers=auth_headers(admin.id)).json()

    assert body["hikers_in"] == CHALLENGE_COUNT_FLOOR
    assert set(body) == {"hikers_in", "hikers_in_floor", "finished"}


def test_the_challenges_list_carries_name_status_window_and_counts(client, db_session, club, admin):
    _own(db_session, club, window_closes=dt.date(2027, 9, 1))
    _enter(client, str(uuid.uuid4()))

    rows = client.get(f"/clubs/{club.slug}/challenges", headers=auth_headers(admin.id)).json()

    assert len(rows) == 1
    assert rows[0]["challenge_id"] == CHALLENGE
    assert rows[0]["name"] == "Fire towers of the Ramapos"
    # `_own` saves a published definition: only those take entries.
    assert rows[0]["status"] == "published"
    assert rows[0]["window"] == {"opens": "2027-05-15", "closes": "2027-09-01"}
    assert rows[0]["hikers_in"] is None
    assert rows[0]["hikers_in_floor"] == CHALLENGE_COUNT_FLOOR
    assert rows[0]["finished"] == 1


def test_counts_and_entries_are_404_for_a_challenge_another_club_owns(client, db_session, club, admin):
    """404 rather than 403, so an admin of one club cannot learn which ids
    another club has saved."""
    other = make_org(db_session, slug="another-conference", state=OrgState.claimed)
    _own(db_session, other)

    for path in (f"/clubs/{club.slug}/challenges/{CHALLENGE}/counts", f"/clubs/{club.slug}/challenges/{CHALLENGE}/entries"):
        assert client.get(path, headers=auth_headers(admin.id)).status_code == 404, path
    assert (
        client.get(f"/clubs/{club.slug}/challenges/nobody-saved-this/counts", headers=auth_headers(admin.id)).status_code == 404
    )


# ------------------------------------------------------------------ #
# GET /clubs/{slug}/challenges/{challenge_id}/entries - the CSV
# ------------------------------------------------------------------ #


def _read_csv(response) -> list[list[str]]:
    assert response.text.startswith("﻿"), "the byte-order mark Excel needs to read UTF-8"
    return list(csv.reader(io.StringIO(response.text.removeprefix("﻿"))))


def test_the_entries_csv_is_an_attachment_with_csv_columns_as_its_header(client, db_session, club, admin):
    _own(db_session, club)

    response = client.get(f"/clubs/{club.slug}/challenges/{CHALLENGE}/entries", headers=auth_headers(admin.id))

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == f'attachment; filename="{CHALLENGE}-entries.csv"'
    assert _read_csv(response) == [list(CSV_COLUMNS)]


def test_the_entries_csv_prefixes_a_quote_to_a_cell_a_spreadsheet_would_run(client, db_session, club, admin):
    """A name typed as a formula arrives in the club's spreadsheet as text."""
    _own(db_session, club)
    _enter(
        client,
        str(uuid.uuid4()),
        name='=HYPERLINK("https://example.com","claim")',
        email=None,
        mailing_address="+1 Reeves Meadow Rd",
    )

    rows = _read_csv(client.get(f"/clubs/{club.slug}/challenges/{CHALLENGE}/entries", headers=auth_headers(admin.id)))
    row = dict(zip(rows[0], rows[1]))

    assert row["name"] == '\'=HYPERLINK("https://example.com","claim")'
    assert row["mailing_address"] == "'+1 Reeves Meadow Rd"
    assert row["email"] == ""


def test_the_entries_csv_lists_hand_tagged_item_ids_and_finished_only(client, db_session, club, admin):
    """The club decides what a hand tag is worth, so the file says which were."""
    _own(db_session, club)
    hiker = str(uuid.uuid4())
    _tag(client, hiker, item_id="jackie-jones", how="gps")
    _tag(client, hiker, item_id="pine-meadow", how="hand")
    _enter(client, hiker, item_ids=["jackie-jones", "pine-meadow", "claudius-smith"])
    _enter(client, str(uuid.uuid4()), name="Sam Roe", email=None, item_ids=[], finished_only=True)

    rows = _read_csv(client.get(f"/clubs/{club.slug}/challenges/{CHALLENGE}/entries", headers=auth_headers(admin.id)))
    entries = [dict(zip(rows[0], row)) for row in rows[1:]]

    assert entries[0]["item_count"] == "3"
    assert entries[0]["item_ids"] == "jackie-jones;pine-meadow;claudius-smith"
    assert entries[0]["hand_tagged_item_ids"] == "pine-meadow"
    # Never tagged on the server at all - not "from the walk" by omission.
    assert entries[0]["untagged_item_ids"] == "claudius-smith"
    assert entries[0]["finished_only"] == "false"
    assert entries[0]["sent_at"].endswith("Z")
    assert entries[1]["name"] == "Sam Roe"
    assert entries[1]["item_count"] == "0"
    assert entries[1]["finished_only"] == "true"


# ------------------------------------------------------------------ #
# PUT /clubs/{slug}/challenges/{challenge_id}
# ------------------------------------------------------------------ #


def _save(client, club, admin, challenge_id: str = CHALLENGE, **body):
    return client.put(
        f"/clubs/{club.slug}/challenges/{challenge_id}",
        json={"definition": _definition(challenge_id), **body},
        headers=auth_headers(admin.id),
    )


def test_put_creates_then_updates_one_club_challenges_row(client, db_session, club, admin):
    created = _save(client, club, admin)
    changed = client.put(
        f"/clubs/{club.slug}/challenges/{CHALLENGE}",
        json={"definition": _definition(window={"opens": None, "closes": "2027-10-15"})},
        headers=auth_headers(admin.id),
    )

    assert created.status_code == 200
    assert created.json()["window_closes"] == "2027-09-01"
    assert created.json()["takes_entries"] is False
    assert changed.status_code == 200
    assert changed.json()["window_closes"] == "2027-10-15"
    db_session.expire_all()
    row = db_session.query(ClubChallenge).one()
    assert row.club_id == club.id
    assert row.updated_by == admin.id


def test_put_is_409_when_another_club_owns_the_challenge_id(client, db_session, club, admin):
    other = make_org(db_session, slug="another-conference", state=OrgState.claimed)
    _own(db_session, other)

    response = _save(client, club, admin)

    assert response.status_code == 409
    assert response.json()["detail"] == "Another organization already has a challenge with this id. Pick another."
    db_session.expire_all()
    assert db_session.get(ClubChallenge, CHALLENGE).club_id == other.id


def test_put_is_422_for_another_orgs_name_or_an_id_without_this_clubs_slug(client, club, admin):
    """The squat the save route closes: a claimed club saving the ATC's id
    first, with `org: atc` in it, owned it - and the ATC's own save was then
    refused as taken."""
    atc_id = "atc-summer-bucket-list-2027"
    as_the_atc = client.put(
        f"/clubs/{club.slug}/challenges/{atc_id}",
        json={"definition": _definition(atc_id, org="atc")},
        headers=auth_headers(admin.id),
    )
    another_org = client.put(
        f"/clubs/{club.slug}/challenges/{CHALLENGE}",
        json={"definition": _definition(org="atc")},
        headers=auth_headers(admin.id),
    )

    assert as_the_atc.status_code == 422
    assert another_org.status_code == 422
    assert another_org.json()["detail"] == "definition.org must be 'ramapo-trail-conference', the organization saving it."


def test_put_is_409_for_an_organization_nobody_has_confirmed(client, db_session):
    held = make_org(db_session, slug="held-conference", state=OrgState.pending)
    founder = make_profile(db_session)
    make_admin(db_session, held, founder)

    assert _save(client, held, founder).status_code == 409


@pytest.mark.parametrize(
    "definition",
    [
        _definition("some-other-id"),
        _definition(org=""),
        _definition(name="  "),
        _definition(items="jackie-jones"),
        _definition(status="live"),
        _definition(window={"opens": None, "closes": "September 1"}),
    ],
)
def test_put_is_422_for_a_definition_this_backend_cannot_read(client, club, admin, definition):
    response = client.put(
        f"/clubs/{club.slug}/challenges/{CHALLENGE}",
        json={"definition": definition},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_put_refuses_takes_entries_on_a_draft_or_a_challenge_with_no_reward(client, club, admin):
    """ "A draft takes no entries" - the maintainer's decision of 2026-09-30."""
    draft = _save(client, club, admin, takes_entries=True)
    no_reward = client.put(
        f"/clubs/{club.slug}/challenges/{CHALLENGE}",
        json={"definition": _definition(status="published"), "takes_entries": True},
        headers=auth_headers(admin.id),
    )
    with_reward = client.put(
        f"/clubs/{club.slug}/challenges/{CHALLENGE}",
        json={
            "definition": _definition(status="published", reward={"kind": "patch", "rules_url": None}),
            "takes_entries": True,
        },
        headers=auth_headers(admin.id),
    )

    assert draft.status_code == 422
    assert no_reward.status_code == 422
    assert with_reward.status_code == 200
    assert with_reward.json()["takes_entries"] is True


# ------------------------------------------------------------------ #
# POST /clubs/{slug}/challenges/{challenge_id}/publish
# ------------------------------------------------------------------ #


def test_publish_with_the_opener_switched_off_opens_nothing_and_says_so(client, db_session, club, admin):
    _own(db_session, club)

    response = client.post(f"/clubs/{club.slug}/challenges/{CHALLENGE}/publish", headers=auth_headers(admin.id))

    assert response.status_code == 200
    assert response.json()["pull_request"] is None
    assert "does not open pull requests" in response.json()["detail"]


def test_publish_records_the_pull_request_the_opener_returns(client, db_session, club, admin, monkeypatch):
    from app.config import settings
    from app.core.registry_pr import OpenedPr

    monkeypatch.setattr(settings, "registry_pr_enabled", True, raising=False)
    monkeypatch.setattr(settings, "registry_pr_token", "a-token", raising=False)
    monkeypatch.setattr(
        "app.routers.trail_challenges.open_challenge_pr",
        lambda club, challenge_id, definition: OpenedPr(number=9, url="https://github.com/OurHike/OurHike/pull/9"),
    )
    _own(db_session, club)

    response = client.post(f"/clubs/{club.slug}/challenges/{CHALLENGE}/publish", headers=auth_headers(admin.id))

    assert response.json()["pull_request"] == "https://github.com/OurHike/OurHike/pull/9"
    db_session.expire_all()
    assert db_session.get(ClubChallenge, CHALLENGE).pr_url == "https://github.com/OurHike/OurHike/pull/9"


def test_open_challenge_pr_writes_one_file_under_the_clubs_challenges_directory_and_never_merges(db_session, club, monkeypatch):
    """The containment guard `open_registry_pr` has, on the challenge path:
    one file, inside pipeline/reference/challenges/<slug>/, no merge."""
    from app.config import settings

    monkeypatch.setattr(settings, "registry_pr_enabled", True, raising=False)
    monkeypatch.setattr(settings, "registry_pr_token", "a-token", raising=False)
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, body))
        path = request.url.path
        if path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "basesha"}})
        if request.method == "GET" and path.endswith("/pulls"):
            return httpx.Response(200, json=[])
        if path.endswith("/git/blobs") or path.endswith("/git/trees") or path.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "sha"})
        if path.endswith("/git/refs"):
            return httpx.Response(201, json={})
        if request.method == "POST" and path.endswith("/pulls"):
            return httpx.Response(201, json={"number": 3, "html_url": "https://example/3"})
        return httpx.Response(404, json={})

    opened = open_challenge_pr(club, CHALLENGE, _definition(), client=httpx.Client(transport=httpx.MockTransport(handler)))

    trees = [body for method, path, body in calls if path.endswith("/git/trees")]
    assert [entry["path"] for entry in trees[0]["tree"]] == [f"pipeline/reference/challenges/{club.slug}/{CHALLENGE}.json"]
    assert not any("/merge" in path for _, path, _ in calls)
    assert opened.url == "https://example/3"


def test_open_challenge_pr_refuses_an_id_that_is_not_a_plain_path_segment(db_session, club, monkeypatch):
    from app.config import settings
    from app.core.registry_pr import RegistryPrRefused

    monkeypatch.setattr(settings, "registry_pr_enabled", True, raising=False)
    monkeypatch.setattr(settings, "registry_pr_token", "a-token", raising=False)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500, json={})

    with pytest.raises(RegistryPrRefused):
        open_challenge_pr(club, "../../.github/workflows/x", {}, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert calls == []


def test_the_org_export_carries_saved_challenges_and_no_hikers_entries(client, db_session, club, admin):
    """`/clubs/{slug}/export` is everything the organization wrote here. Its
    challenge definitions are that; the entries hikers sent are people's
    names and addresses, and the CSV is the one route to them."""
    _own(db_session, club)
    _enter(client, str(uuid.uuid4()))

    exported = client.get(f"/clubs/{club.slug}/export", headers=auth_headers(admin.id)).json()

    assert [row["challenge_id"] for row in exported["challenges"]] == [CHALLENGE]
    assert "Jane Doe" not in str(exported)


def test_a_finished_notice_is_409_for_a_draft(client, db_session, club):
    """ "A draft takes no entries" reaches the notice too: it carries a name."""
    row = _own(db_session, club, takes_entries=False)
    row.definition = _definition(CHALLENGE)
    db_session.commit()

    response = _enter(client, str(uuid.uuid4()), email=None, item_ids=[], finished_only=True)

    assert response.status_code == 409
    assert db_session.query(ChallengeEntry).count() == 0


def test_a_frozen_organization_reads_no_entries(client, db_session, club, admin):
    """Two people contesting one org: neither reads its entrants' addresses."""
    _own(db_session, club)
    club.state = OrgState.frozen
    db_session.commit()

    response = client.get(f"/clubs/{club.slug}/challenges/{CHALLENGE}/entries", headers=auth_headers(admin.id))

    assert response.status_code == 409


def test_put_is_422_for_a_definition_past_the_size_cap(client, club, admin):
    huge = _definition(
        items=[{"id": f"i{n}", "section": "towers", "title": "x" * 500, "match": {"kind": "self_report"}} for n in range(600)]
    )

    response = client.put(f"/clubs/{club.slug}/challenges/{CHALLENGE}", json={"definition": huge}, headers=auth_headers(admin.id))

    assert response.status_code == 422


def test_a_hiker_takes_back_one_tag_by_place_and_every_tag_on_leaving(client, db_session):
    hiker = str(uuid.uuid4())
    _tag(client, hiker, item_id="jackie-jones")
    _tag(client, hiker, item_id="pine-meadow")
    stranger = str(uuid.uuid4())
    _tag(client, stranger, item_id="jackie-jones")

    one = client.delete(f"/challenges/{CHALLENGE}/items/jackie-jones/tag", headers=auth_headers(hiker))
    again = client.delete(f"/challenges/{CHALLENGE}/items/jackie-jones/tag", headers=auth_headers(hiker))
    assert (one.status_code, again.status_code) == (204, 204)
    assert {t.item_id for t in db_session.query(ChallengeTag).filter(ChallengeTag.user_id == hiker)} == {"pine-meadow"}

    left = client.delete(f"/challenges/{CHALLENGE}/tags", headers=auth_headers(hiker))
    assert left.status_code == 204
    assert db_session.query(ChallengeTag).filter(ChallengeTag.user_id == hiker).count() == 0
    # Only the caller's own.
    assert db_session.query(ChallengeTag).filter(ChallengeTag.user_id == stranger).count() == 1


def test_a_walked_tag_upgrades_a_hand_tag_of_the_same_item(client, db_session):
    hiker = str(uuid.uuid4())
    _tag(client, hiker, how="hand")

    again = _tag(client, hiker, how="gps")

    assert again.status_code == 200
    assert again.json()["how"] == "gps"
    assert _tag(client, hiker, how="hand").json()["how"] == "gps"


def test_tags_past_the_per_hiker_cap_are_refused(client, monkeypatch):
    monkeypatch.setattr("app.routers.trail_challenges.TAGS_PER_HIKER_CAP", 2)
    hiker = str(uuid.uuid4())

    codes = [_tag(client, hiker, item_id=f"item-{n}").status_code for n in range(3)]

    assert codes == [201, 201, 409]


def test_saving_past_the_per_club_cap_is_refused(client, club, admin, monkeypatch):
    monkeypatch.setattr("app.routers.trail_challenges.CHALLENGES_PER_CLUB_CAP", 1)

    first = _save(client, club, admin)
    second = _save(client, club, admin, challenge_id=f"{club.slug}-another")

    assert (first.status_code, second.status_code) == (200, 409)


def test_put_is_422_for_a_definition_nested_past_the_cap(client, club, admin):
    deep: dict = {}
    node = deep
    for _ in range(40):
        node["x"] = {}
        node = node["x"]

    response = client.put(
        f"/clubs/{club.slug}/challenges/{CHALLENGE}",
        json={"definition": _definition(extra=deep)},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_deleting_an_organization_purges_its_entries_and_releases_its_ids(client, db_session, club, admin):
    _own(db_session, club)
    _enter(client, str(uuid.uuid4()))
    hiker = str(uuid.uuid4())
    _tag(client, hiker)

    assert client.delete(f"/clubs/{club.slug}", headers=auth_headers(admin.id)).status_code == 204

    assert db_session.query(ChallengeEntry).count() == 0
    assert db_session.query(ClubChallenge).count() == 0
    # The hiker's own tag is theirs and stays.
    assert db_session.query(ChallengeTag).filter(ChallengeTag.user_id == hiker).count() == 1


def test_the_spreadsheet_guard_reads_a_folded_lead_and_a_line_feed():
    assert spreadsheet_safe("\uff1dcmd") == "'\uff1dcmd"
    assert spreadsheet_safe("\n=1+1") == "'\n=1+1"
    assert spreadsheet_safe("Zo\u00eb") == "Zo\u00eb"
