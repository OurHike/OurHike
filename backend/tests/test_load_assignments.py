"""Tests for load_assignments.py - the way assignments get into the database.

#249's fourth gap: `MaintainerAssignment` and `Club` had no write path at
all, so resolution and the report form's preview both ran against
structurally empty tables - and `lookupMaintainers` returns `[]` on failure,
which made "nothing is loaded" and "nobody is assigned" the same answer.

Two properties carry most of this file:

  - **Re-running it is safe.** A club's records get re-exported; the loader
    is pointed at the file again. An unchanged file must write nothing, and a
    changed stretch must not silently rewrite who looked after it last June -
    that history is the reason the model is versioned at all.
  - **A bad file fails with a sentence, before the database sees it.** Every
    check exists because the alternative is a constraint name, which tells an
    operator nothing about which line of their spreadsheet is wrong.
"""

import uuid
from datetime import date

import pytest

from app.models.club import Club
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Profile, Role
from load_assignments import InvalidFile, apply, parse
from tests.factories import make_profile


@pytest.fixture()
def pat(db_session) -> Profile:
    profile = make_profile(db_session, Role.maintainer, display_name="Pat")
    return profile


def _document(pat: Profile, **assignment_overrides) -> dict:
    return {
        "clubs": [{"id": "nbatc", "name": "Natural Bridge ATC", "region": "Central Virginia"}],
        "assignments": [
            {
                "maintainer_id": pat.id,
                "club_id": "nbatc",
                "start_mile": 728.0,
                "end_mile": 754.5,
                "effective_from": "2026-01-01",
                **assignment_overrides,
            }
        ],
    }


def _load(db_session, document: dict) -> list[str]:
    changes = apply(db_session, *parse(document))
    db_session.commit()
    return changes


def test_it_loads_a_club_and_its_assignment(db_session, pat):
    changes = _load(db_session, _document(pat))

    assert db_session.query(Club).count() == 1
    [assignment] = db_session.query(MaintainerAssignment).all()
    assert assignment.maintainer_id == pat.id
    assert (assignment.start_mile, assignment.end_mile) == (728.0, 754.5)
    assert assignment.effective_from == date(2026, 1, 1)
    assert len(changes) == 2


def test_running_it_twice_changes_nothing(db_session, pat):
    """The ordinary operational case: a club re-exports, somebody re-runs the
    loader. A second copy of every assignment would double every thanks."""
    _load(db_session, _document(pat))

    changes = _load(db_session, _document(pat))

    assert changes == []
    assert db_session.query(MaintainerAssignment).count() == 1


def test_a_moved_boundary_adds_a_row_rather_than_rewriting_one(db_session, pat):
    """Append-only, because the model is versioned.

    Editing the stretch in place would change who looked after mile 754 last
    June - the exact history `effective_from`/`effective_to` exist to keep. A
    second row is a mistake an operator can see; a rewrite is not.
    """
    _load(db_session, _document(pat))

    _load(db_session, _document(pat, end_mile=760.0))

    assert db_session.query(MaintainerAssignment).count() == 2


def test_closing_a_stretch_is_the_one_edit_it_will_make(db_session, pat):
    """A hand-off closes the old row and opens a new one, so the close has to
    be expressible. It is announced rather than done quietly."""
    _load(db_session, _document(pat))

    changes = _load(db_session, _document(pat, effective_to="2026-06-30"))

    [assignment] = db_session.query(MaintainerAssignment).all()
    assert assignment.effective_to == date(2026, 6, 30)
    assert any("ends" in line for line in changes)


def test_consent_can_be_withdrawn(db_session, pat):
    """`publicly_creditable` is consent, so a club taking it back has to take
    effect - refusing the change as "an edit to history" would leave a
    volunteer's name published after they asked for it not to be."""
    _load(db_session, _document(pat, publicly_creditable=True))

    _load(db_session, _document(pat, publicly_creditable=False))

    [assignment] = db_session.query(MaintainerAssignment).all()
    assert assignment.publicly_creditable is False


def test_a_renamed_club_is_updated_in_place(db_session, pat):
    """Unlike an assignment: a club's name is a fact about today, not a
    version of anything."""
    _load(db_session, _document(pat))
    document = _document(pat)
    document["clubs"][0]["name"] = "Natural Bridge Appalachian Trail Club"

    _load(db_session, document)

    assert db_session.query(Club).count() == 1
    assert db_session.get(Club, "nbatc").name == "Natural Bridge Appalachian Trail Club"


def test_it_does_not_promote_anybody_to_a_moderator_role(db_session):
    """Looking after a stretch is not permission to moderate safety reports
    about named individuals, and a data-loading script is the last place
    anybody would look for an account being promoted."""
    hiker = make_profile(db_session, Role.hiker)

    _load(db_session, _document(hiker))

    db_session.refresh(hiker)
    assert hiker.role is Role.hiker


# --- Refusals, each with a sentence an operator can act on -----------------


def test_an_unknown_maintainer_says_so_rather_than_violating_a_constraint(db_session):
    """The ordinary cause is a volunteer who has not signed into the app yet,
    which is a thing to go and fix rather than a thing to debug."""
    stranger = str(uuid.uuid4())
    document = {
        "clubs": [{"id": "nbatc", "name": "Natural Bridge ATC"}],
        "assignments": [
            {
                "maintainer_id": stranger,
                "club_id": "nbatc",
                "start_mile": 1,
                "end_mile": 2,
                "effective_from": "2026-01-01",
            }
        ],
    }

    with pytest.raises(InvalidFile, match="signed in"):
        apply(db_session, *parse(document))


def test_an_unknown_club_says_which_one(db_session, pat):
    document = _document(pat)
    document["clubs"] = []

    with pytest.raises(InvalidFile, match="No club nbatc"):
        apply(db_session, *parse(document))


def test_a_backwards_stretch_is_refused(pat):
    """It covers nothing, so every thanks written on it resolves to nobody -
    a feature that looks switched off rather than misconfigured."""
    with pytest.raises(InvalidFile, match="past end_mile"):
        parse(_document(pat, start_mile=800.0, end_mile=700.0))


def test_an_end_date_before_the_start_is_refused(pat):
    with pytest.raises(InvalidFile, match="before effective_from"):
        parse(_document(pat, effective_to="2025-01-01"))


def test_a_missing_field_names_the_field(pat):
    document = _document(pat)
    del document["assignments"][0]["effective_from"]

    with pytest.raises(InvalidFile, match="effective_from"):
        parse(document)


def test_a_club_with_no_name_is_refused(pat):
    document = _document(pat)
    document["clubs"][0]["name"] = ""

    with pytest.raises(InvalidFile, match="name"):
        parse(document)


def test_an_unparseable_date_is_refused(pat):
    with pytest.raises(InvalidFile):
        parse(_document(pat, effective_from="June 2026"))


def test_a_file_that_is_not_an_object_is_refused():
    with pytest.raises(InvalidFile, match="JSON object"):
        parse([{"id": "nbatc"}])


def test_the_example_file_in_this_repo_actually_parses():
    """It is the documentation for the format, so a typo in it is a wrong
    instruction rather than a stale comment."""
    import json
    from pathlib import Path

    document = json.loads((Path(__file__).resolve().parents[1] / "assignments.example.json").read_text())

    clubs, assignments = parse(document)

    assert [club["id"] for club in clubs] == ["natural-bridge-atc"]
    # Two rows for one stretch: a hand-off is a close plus an open, which is
    # the thing the format most needs to demonstrate.
    assert len(assignments) == 2
    assert assignments[0]["effective_to"] == "2026-06-30"
    assert "effective_to" not in assignments[1]
