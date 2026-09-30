"""The three numbers an organization puts on its own website.

The design's coverage badge, embed 3: **miles maintained · active volunteers ·
hours this season**, one snippet in two shapes. Its own caption says where each
figure comes from - "miles from the registry, volunteers from the roster, hours
from the ones a supervisor signed off" - and this is that sentence as code.

**IT IS PUBLIC, WHICH IS THE WHOLE POINT AND ALSO THE WHOLE RISK.** The badge
sits on an organization's own donate page, read by strangers. So the endpoint
answers without an account - and everything it returns has to be safe in front
of one, which for this project means rule 4: nothing about a NAMED volunteer is
published. Three counts are not three names, and the tests below are what keeps
the difference.

**IT REPLACES A BADGE THAT COULD NEVER HAVE WORKED.** The coverage badge read
`GET /clubs/{slug}/coverage`, which depends on `org_access` and therefore on
`get_current_user` - so an anonymous visitor got 401 and the badge rendered
nothing, on every real site, always. It only ever drew on the demo page, where
a fixture serves it without auth. That is asserted here too, because the reason
this endpoint exists is that the other one is the wrong shape for a public
embed rather than merely inconvenient.
"""

import datetime as dt

import pytest

from app.models.club import OrgState
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_registry import OrgPark, OrgSection, OrgTrail
from app.models.volunteer_hours import HoursState, VolunteerHoursRecord
from tests.factories import make_org, make_profile

# The demo organization's own six sections, whose total the design prints as
# "13.8 miles maintained". Using the design's own numbers rather than round
# ones means the arithmetic is checked against the picture somebody approved.
DEMO_SECTION_MILES = [6.1, 1.58, 2.4, 1.2, 1.7, 0.8]


@pytest.fixture
def org_with_a_registry(db_session):
    """An org with six sections, three volunteers on live assignments, hours."""
    org = make_org(db_session)
    park = OrgPark(club_id=org.id, name="Central Park")
    db_session.add(park)
    db_session.flush()
    trail = OrgTrail(park_id=park.id, name="The Loop")
    db_session.add(trail)
    db_session.flush()
    for index, miles in enumerate(DEMO_SECTION_MILES):
        db_session.add(OrgSection(trail_id=trail.id, name=f"Section {index}", miles=miles))
    db_session.commit()
    return org


def assign(db_session, org, person, *, ended: dt.date | None = None):
    db_session.add(
        MaintainerAssignment(
            maintainer_id=person.id,
            club_id=org.id,
            start_mile=0.0,
            end_mile=1.0,
            effective_from=dt.date(2026, 1, 1),
            effective_to=ended,
        )
    )
    db_session.commit()


def log(db_session, org, person, hours: float, *, state=HoursState.confirmed, on=None):
    db_session.add(
        VolunteerHoursRecord(
            user_id=person.id,
            club_id=org.id,
            worked_on=on or dt.date.today(),
            hours=hours,
            activity="maintenance",
            state=state,
        )
    )
    db_session.commit()


class TestItIsReadableByAStranger:
    def test_an_anonymous_visitor_gets_the_three_numbers(self, client, org_with_a_registry):
        """The badge sits on somebody else's website. Nobody there has an account."""
        response = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard")
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"miles_maintained", "active_volunteers", "hours_this_season"}

    def test_the_coverage_report_it_replaces_refuses_the_same_visitor(self, client, org_with_a_registry):
        """Which is why the badge that read it drew nothing on every real site.

        Not a complaint about the coverage endpoint - it is admin-and-
        supervisor by decision, because a public list of which miles nobody is
        looking after is a list of miles to avoid. The defect was pointing a
        PUBLIC embed at it.
        """
        assert client.get(f"/clubs/{org_with_a_registry.slug}/coverage").status_code == 401

    def test_an_organization_nobody_has_is_a_404(self, client):
        assert client.get("/clubs/not-an-org/scoreboard").status_code == 404

    def test_an_organization_that_left_is_not_served(self, client, db_session, org_with_a_registry):
        org_with_a_registry.state = OrgState.deleted
        db_session.commit()
        assert client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").status_code == 404


class TestTheThreeFigures:
    def test_the_miles_are_the_registry_sections_added_up(self, client, org_with_a_registry):
        """13.8, which is the number the design's own badge prints."""
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["miles_maintained"] == pytest.approx(13.8, abs=0.05)

    def test_a_section_with_no_length_does_not_become_zero_miles_of_something(self, client, db_session, org_with_a_registry):
        """Absent is unknown, never zero - the rule the capacity export follows.

        A section whose length nobody has measured must not quietly drag the
        total down, and must not be counted as if it were nothing.
        """
        trail = db_session.query(OrgTrail).first()
        db_session.add(OrgSection(trail_id=trail.id, name="Unmeasured", miles=None))
        db_session.commit()
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["miles_maintained"] == pytest.approx(13.8, abs=0.05)

    def test_active_volunteers_counts_people_on_live_assignments(self, client, db_session, org_with_a_registry):
        for _ in range(3):
            assign(db_session, org_with_a_registry, make_profile(db_session))
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["active_volunteers"] == 3

    def test_somebody_who_handed_their_section_back_is_not_still_active(self, client, db_session, org_with_a_registry):
        """`effective_to is None` is the definition of current everywhere here.

        A count that included them would say an organization has more people
        than it has, on the organization's own donate page.
        """
        assign(db_session, org_with_a_registry, make_profile(db_session))
        assign(
            db_session,
            org_with_a_registry,
            make_profile(db_session),
            ended=dt.date(2026, 6, 1),
        )
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["active_volunteers"] == 1

    def test_one_person_on_three_sections_is_one_volunteer(self, client, db_session, org_with_a_registry):
        busy = make_profile(db_session)
        for _ in range(3):
            assign(db_session, org_with_a_registry, busy)
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["active_volunteers"] == 1

    def test_hours_are_the_ones_a_supervisor_signed_off(self, client, db_session, org_with_a_registry):
        """The design's own caption. A claimed hour is somebody's assertion."""
        person = make_profile(db_session)
        log(db_session, org_with_a_registry, person, 10.0, state=HoursState.confirmed)
        log(db_session, org_with_a_registry, person, 99.0, state=HoursState.claimed)
        log(db_session, org_with_a_registry, person, 99.0, state=HoursState.disputed)
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["hours_this_season"] == pytest.approx(10.0)

    def test_last_season_is_not_this_season(self, client, db_session, org_with_a_registry):
        person = make_profile(db_session)
        log(db_session, org_with_a_registry, person, 5.0)
        log(
            db_session,
            org_with_a_registry,
            person,
            500.0,
            on=dt.date(dt.date.today().year - 1, 7, 1),
        )
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["hours_this_season"] == pytest.approx(5.0)

    def test_it_says_when_the_season_started(self, client, org_with_a_registry):
        """So "this season" is checkable rather than a word.

        A badge printing "164 hours this season" over an unstated window is a
        number nobody can verify and an organization cannot explain.
        """
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["season_started"] == f"{dt.date.today().year}-01-01"

    def test_another_organizations_hours_are_not_these(self, client, db_session, org_with_a_registry):
        other = make_org(db_session, slug="somebody-else", name="Somebody Else")
        person = make_profile(db_session)
        log(db_session, other, person, 400.0)
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert body["hours_this_season"] == pytest.approx(0.0)

    def test_an_organization_with_nothing_yet_answers_zeroes_rather_than_failing(self, client, db_session):
        """A club that registered this morning still has a badge to paste."""
        bare = make_org(db_session, slug="brand-new", name="Brand New")
        body = client.get(f"/clubs/{bare.slug}/scoreboard").json()
        assert body["miles_maintained"] == 0
        assert body["active_volunteers"] == 0
        assert body["hours_this_season"] == 0


class TestWhatItMustNeverSay:
    def test_it_names_nobody(self, client, db_session, org_with_a_registry):
        """Rule 4, as a string search over everything that goes out.

        Three counts are not three names. This endpoint is read by strangers on
        an organization's own website, and a volunteer who put their hand up to
        cut tread did not put their name on a public page.
        """
        person = make_profile(db_session, display_name="Switchback")
        assign(db_session, org_with_a_registry, person)
        log(db_session, org_with_a_registry, person, 4.0)
        raw = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").text
        assert "Switchback" not in raw
        assert person.id not in raw

    def test_it_carries_no_list_of_anything(self, client, db_session, org_with_a_registry):
        """A count can become a list in one careless edit.

        The coverage endpoint returns gap NAMES and the old badge discarded
        them client-side, which put the safety property in a browser. Here
        there is nothing to discard: the response has no array in it at all.
        """
        assign(db_session, org_with_a_registry, make_profile(db_session))
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert not any(isinstance(value, list) for value in body.values())

    def test_it_does_not_say_which_sections_are_uncovered(self, client, db_session, org_with_a_registry):
        """The one thing the coverage report exists to keep off a public page.

        A hiker reading "these three miles have nobody on them" makes a routing
        decision out of an organization's staffing problem.
        """
        body = client.get(f"/clubs/{org_with_a_registry.slug}/scoreboard").json()
        assert "gaps" not in body
        assert "sections" not in body
