"""Who counts as a survey volunteer and who reviews which section.

#1984 — A club's enrolment, settings and waiver have endpoints, and an
enrolled volunteer is a person `org_access` did not know about.

`require_inventory_volunteer` and `require_inventory_reviewer` guard the
survey's record, queue and review endpoints, which arrive with later issues;
these tests hold their answers before any endpoint leans on them.
"""

import pytest
from fastapi import HTTPException

from app.core.inventory_access import (
    InventoryReviewer,
    require_inventory_reviewer,
    require_inventory_volunteer,
    supervised_section_ids,
)
from app.core.org_access import resolve_access
from app.core.time import utc_now
from app.models.club import OrgState
from app.models.inventory import InventoryEnrollment
from tests.factories import make_admin, make_assignment, make_org, make_profile, make_role, make_section


@pytest.fixture
def chain(db_session):
    """A chair over two crews, each holding a section, and a section nobody's
    role reaches."""
    org = make_org(db_session, state=OrgState.claimed)
    chair_role = make_role(db_session, org, name="Trails chair")
    crew_role = make_role(db_session, org, name="Maintainer", reports_to_role_id=chair_role.id)
    own = make_section(db_session, org, name="Chair's own section")
    crew = make_section(db_session, org, name="Crew section")
    elsewhere = make_section(db_session, org, name="Nobody's section")
    people = {name: make_profile(db_session) for name in ("admin", "supervisor", "maintainer", "outsider")}
    make_admin(db_session, org, people["admin"])
    make_assignment(db_session, org, people["supervisor"], role=chair_role, section=own)
    make_assignment(db_session, org, people["maintainer"], role=crew_role, section=crew)
    db_session.commit()
    return {
        "org": org,
        "people": people,
        "chair_role": chair_role,
        "crew_role": crew_role,
        "own": own,
        "crew": crew,
        "elsewhere": elsewhere,
    }


def _access(db_session, chain, who):
    return resolve_access(db_session, chain["org"], chain["people"][who].id)


def test_the_local_chair_is_any_approved_admin_and_reviews_every_section(db_session, chain):
    """Decided by the maintainer by poll, 2026-11-04."""
    reviewer = require_inventory_reviewer(_access(db_session, chain, "admin"), db_session)

    assert reviewer.section_ids is None
    assert reviewer.may_review(chain["elsewhere"].id)
    assert reviewer.may_review(None)


def test_a_supervisor_reviews_their_own_section_and_those_under_their_role_and_no_other(db_session, chain):
    reviewer = require_inventory_reviewer(_access(db_session, chain, "supervisor"), db_session)

    assert reviewer.section_ids == frozenset({chain["own"].id, chain["crew"].id})
    assert not reviewer.may_review(chain["elsewhere"].id)


def test_a_record_with_no_section_is_the_chairs_alone(db_session, chain):
    """Nothing places it under anybody's role, so no supervisor can claim it."""
    reviewer = InventoryReviewer(access=_access(db_session, chain, "supervisor"), section_ids=frozenset({chain["own"].id}))

    assert not reviewer.may_review(None)


@pytest.mark.parametrize("who", ["maintainer", "outsider"])
def test_a_maintainer_or_an_outsider_reviews_nothing(db_session, chain, who):
    with pytest.raises(HTTPException) as refused:
        require_inventory_reviewer(_access(db_session, chain, who), db_session)

    assert refused.value.status_code == 403


def test_a_proposed_lead_supervises_nothing_until_an_admin_confirms_it(db_session, chain):
    """resolve_access's rule from #1635 — The organization console's new
    endpoints trust self-registered orgs with maintainer powers, seats and
    mail - which supervised_section_ids copies."""
    proposed = make_profile(db_session)
    make_assignment(
        db_session,
        chain["org"],
        proposed,
        role=chain["chair_role"],
        section=chain["elsewhere"],
        proposed_by=chain["people"]["supervisor"].id,
    )

    assert supervised_section_ids(db_session, chain["org"].id, proposed.id) == frozenset()


def test_a_volunteer_who_has_not_finished_the_field_guide_cannot_survey_yet(db_session, chain):
    outsider = chain["people"]["outsider"]
    db_session.add(InventoryEnrollment(club_id=chain["org"].id, person_id=outsider.id, waiver_version="1", typed_name="Pat R."))
    db_session.commit()

    with pytest.raises(HTTPException) as refused:
        require_inventory_volunteer(_access(db_session, chain, "outsider"), db_session)

    assert refused.value.status_code == 403


def test_a_volunteer_with_the_field_guide_finished_can_survey_holding_nothing_else(db_session, chain):
    outsider = chain["people"]["outsider"]
    db_session.add(
        InventoryEnrollment(
            club_id=chain["org"].id,
            person_id=outsider.id,
            waiver_version="1",
            typed_name="Pat R.",
            training_completed_at=utc_now(),
        )
    )
    db_session.commit()

    enrollment = require_inventory_volunteer(_access(db_session, chain, "outsider"), db_session)

    assert enrollment.person_id == outsider.id


def test_holding_a_maintainer_assignment_does_not_make_somebody_a_survey_volunteer(db_session, chain):
    with pytest.raises(HTTPException) as refused:
        require_inventory_volunteer(_access(db_session, chain, "maintainer"), db_session)

    assert refused.value.status_code == 403


def test_a_proposed_crew_member_does_not_widen_their_supervisors_reach(db_session, chain):
    """The adversarial review's escalation: a supervisor proposes somebody onto
    a section, and no admin has confirmed it. Until one does, the section is
    not under the supervisor's role."""
    proposed = make_profile(db_session)
    crew_role = chain["crew_role"]
    make_assignment(
        db_session,
        chain["org"],
        proposed,
        role=crew_role,
        section=chain["elsewhere"],
        proposed_by=chain["people"]["supervisor"].id,
    )

    reach = supervised_section_ids(db_session, chain["org"].id, chain["people"]["supervisor"].id)

    assert chain["elsewhere"].id not in reach
    assert reach == frozenset({chain["own"].id, chain["crew"].id})


def test_a_confirmed_crew_member_does_widen_it(db_session, chain):
    confirmed = make_profile(db_session)
    make_assignment(
        db_session,
        chain["org"],
        confirmed,
        role=chain["crew_role"],
        section=chain["elsewhere"],
        proposed_by=chain["people"]["supervisor"].id,
        confirmed_at=utc_now(),
    )

    assert chain["elsewhere"].id in supervised_section_ids(db_session, chain["org"].id, chain["people"]["supervisor"].id)
