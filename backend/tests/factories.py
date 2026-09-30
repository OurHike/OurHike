"""Rows the tests need to exist, rather than rows they are about.

Almost every test in this suite opens by making somebody to act and something
to act on. That was written out inline: three lines of ORM ceremony for a
profile, seven or eight for a closure, thirty-eight and twelve times over. It
told a reader nothing - the row being set up is the same row every time, and
the only part that varies is the role or the mile markers, which was the one
part buried in the middle.

Two files had already noticed and each half-fixed it, differently:
test_routers_closures.py grew `_closure_and_maintainer` and
test_routers_moderation.py grew `_submitted_closure` plus `_make_maintainer`,
for the same rows, and most of the tests in both files went on inlining it
anyway. This is that, once.

Plain functions rather than fixtures because the count varies - a test about
what a public list excludes needs two closures, and a fixture yields one.
"""

import uuid
from datetime import date, timedelta

from app.core.time import utc_now
from app.models.closure import Closure
from app.models.club import Club, OrgAdmin, OrgState
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_registry import OrgPark, OrgSection, OrgTrail
from app.models.org_role import OrgRole, RoleCategory
from app.models.profile import Profile, Role
from app.models.work_project import WorkProject


def make_profile(db_session, role=Role.hiker, **fields) -> Profile:
    """Somebody, committed, with a random id.

    The id is what the tests actually use - `auth_headers(profile.id)` is how a
    request gets made as them - so it comes back on the object rather than
    being generated at the call site and passed in.
    """
    profile = Profile(id=str(uuid.uuid4()), role=role, **fields)
    db_session.add(profile)
    db_session.commit()
    return profile


def make_closure(db_session, reported_by, **fields) -> Closure:
    """A submitted closure over a mile of trail.

    The defaults are the ones every test that does not care about them was
    already writing: storm damage, mile 1 to 2, no moderation yet. A test about
    what a list excludes passes its own markers and moderation status, which is
    then the only thing on the line and readable as the point.
    """
    closure = Closure(
        reported_by=reported_by,
        **{
            "reason_type": "storm_damage",
            "start_mile_marker": 1.0,
            "end_mile_marker": 2.0,
            **fields,
        },
    )
    db_session.add(closure)
    db_session.commit()
    return closure


def make_org(db_session, slug="ramapo-trail-conference", **fields) -> Club:
    """An organization with live trails and nobody running it.

    `unclaimed` is the default because it is the state every organization in
    this repository is actually in today - 33 sources across nine
    organizations, each registered by a maintainer writing a row - and it is
    what the claim tests need. A test about a running org passes
    `state=OrgState.claimed` and an admin, which is then the only thing on the
    line and readable as the point.
    """
    club = Club(
        slug=slug,
        **{
            "name": "Ramapo Trail Conference",
            "domain": "ramapotrails.org",
            "state": OrgState.unclaimed,
            **fields,
        },
    )
    db_session.add(club)
    db_session.commit()
    return club


def make_admin(db_session, club, person, *, approved=True, is_codeowner=True, **fields) -> OrgAdmin:
    """A seat at an organization, approved by default.

    Approved by default because almost every test wants somebody who can
    already act; the approval screen's own tests pass `approved=False`, which
    is the case they are about.
    """
    seat = OrgAdmin(
        club_id=club.id,
        person_id=person.id,
        is_codeowner=is_codeowner,
        approved_at=utc_now() if approved else None,
        **fields,
    )
    db_session.add(seat)
    db_session.commit()
    return seat


def make_section(db_session, club, *, name="Pine Meadow North", region=None, **fields) -> OrgSection:
    """A section, with the park and trail above it made on the way.

    Three tiers for one row looks heavy and is what the registry actually is:
    a test that only cares about a section should not have to build the two
    tiers that give it a home, so this builds them and returns the one that
    was asked for.
    """
    park = OrgPark(club_id=club.id, name=f"{name} park")
    db_session.add(park)
    db_session.flush()
    trail = OrgTrail(park_id=park.id, name=f"{name} trail")
    db_session.add(trail)
    db_session.flush()
    section = OrgSection(
        trail_id=trail.id,
        name=name,
        region=region,
        **{"start_mile": 11.0, "end_mile": 14.3, "miles": 3.3, **fields},
    )
    db_session.add(section)
    db_session.commit()
    return section


def make_assignment(db_session, club, person, *, role=None, section=None, **fields) -> MaintainerAssignment:
    """A live assignment - `effective_to` null, which is what "current" means."""
    assignment = MaintainerAssignment(
        maintainer_id=person.id,
        club_id=club.id,
        role_id=role.id if role is not None else None,
        section_id=section.id if section is not None else None,
        **{
            "start_mile": 11.0,
            "end_mile": 14.3,
            "effective_from": date.today(),
            **fields,
        },
    )
    db_session.add(assignment)
    db_session.commit()
    return assignment


def make_role(db_session, club, *, name="Maintainer", category=RoleCategory.trail_maintenance, **fields) -> OrgRole:
    role = OrgRole(club_id=club.id, name=name, category=category, **fields)
    db_session.add(role)
    db_session.commit()
    return role


def make_workday(db_session, club, **fields) -> WorkProject:
    """An upcoming, in-app-signup workday a week out."""
    project = WorkProject(
        club_id=club.id,
        **{
            "title": "Clear blowdowns, Pine Meadow",
            "starts_on": date.today() + timedelta(days=7),
            "ends_on": date.today() + timedelta(days=7),
            "meet_point": "Reeves Meadow Visitor Center, 8am",
            **fields,
        },
    )
    db_session.add(project)
    db_session.commit()
    return project
