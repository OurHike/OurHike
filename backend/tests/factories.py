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

from app.models.closure import Closure
from app.models.profile import Profile, Role


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
