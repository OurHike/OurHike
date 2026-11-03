"""Who GitHub asks to approve an organization's registry.

**THE FILE IS PART HAND-WRITTEN AND PART GENERATED**, so the generator
replaces a marked block and touches nothing else. The prose above the block
explains why the file exists at all and what branch protection does with it;
a generator that rewrote the whole file would delete that on its first run.

**AN ORGANIZATION WITH NO NAMEABLE OWNERS GETS NO LINE.** A CODEOWNERS
pattern with no owners after it does not mean "anybody may approve" - it
means the previous matching rule is overridden and nobody is requested,
which is worse than silence. So an org whose codeowners have not linked a
GitHub account is left out entirely, and `.github/CODEOWNERS`'s existing
`*` line keeps covering its directory until they do.
"""

from app.core.codeowners import GENERATED_END, GENERATED_START, codeowners_block, render_codeowners
from app.core.time import utc_now
from app.models.club import OrgAdmin, OrgState
from tests.factories import make_org, make_profile

EXISTING = """# Who to notify about this repository.

* @jaimito-asuntos-gringuenos
"""


def _codeowner(db_session, club, login, *, approved=True):
    person = make_profile(db_session, github_login=login)
    db_session.add(
        OrgAdmin(
            club_id=club.id,
            person_id=person.id,
            is_codeowner=True,
            approved_at=utc_now() if approved else None,
        )
    )
    db_session.commit()
    return person


class TestWhoGetsNamed:
    def test_an_orgs_directory_is_owned_by_its_linked_codeowners(self, client, db_session):
        club = make_org(db_session, state=OrgState.claimed)
        _codeowner(db_session, club, "maria-rtc")
        _codeowner(db_session, club, "joseph-rtc")

        block = codeowners_block(db_session)

        assert "/pipeline/reference/orgs/ramapo-trail-conference/ @joseph-rtc @maria-rtc" in block

    def test_a_codeowner_who_has_not_linked_github_is_not_named(self, client, db_session):
        """Nothing to write. A login we do not hold cannot be guessed."""
        club = make_org(db_session, state=OrgState.claimed)
        _codeowner(db_session, club, "maria-rtc")
        unlinked = make_profile(db_session)
        db_session.add(OrgAdmin(club_id=club.id, person_id=unlinked.id, is_codeowner=True))
        db_session.commit()

        block = codeowners_block(db_session)

        assert "@maria-rtc" in block
        assert block.count("/pipeline/reference/orgs/ramapo-trail-conference/") == 1

    def test_an_org_with_nobody_linked_gets_no_line_at_all(self, client, db_session):
        """A pattern with no owners after it overrides the `*` rule and
        requests nobody, which is worse than leaving the org uncovered."""
        club = make_org(db_session, state=OrgState.claimed)
        unlinked = make_profile(db_session)
        db_session.add(OrgAdmin(club_id=club.id, person_id=unlinked.id, is_codeowner=True))
        db_session.commit()

        assert "ramapo-trail-conference" not in codeowners_block(db_session)

    def test_an_admin_who_is_not_a_codeowner_is_not_named(self, client, db_session):
        club = make_org(db_session, state=OrgState.claimed)
        person = make_profile(db_session, github_login="helper")
        db_session.add(OrgAdmin(club_id=club.id, person_id=person.id, is_codeowner=False))
        db_session.commit()

        assert "@helper" not in codeowners_block(db_session)

    def test_a_seat_nobody_has_accepted_is_not_named(self, client, db_session):
        """Being invited is not agreeing, and an unapproved seat holding
        approval power would let an invitation grant it."""
        club = make_org(db_session, state=OrgState.claimed)
        _codeowner(db_session, club, "not-yet", approved=False)

        assert "@not-yet" not in codeowners_block(db_session)

    def test_a_held_registration_owns_nothing(self, client, db_session):
        """`pending` means nobody at the organization has confirmed it
        exists here. Handing its registry to whoever registered it would
        make the squat authoritative."""
        club = make_org(db_session, state=OrgState.pending)
        _codeowner(db_session, club, "squatter")

        assert "@squatter" not in codeowners_block(db_session)


class TestThatTheFileStaysReadable:
    def test_the_hand_written_part_survives(self, client, db_session):
        club = make_org(db_session, state=OrgState.claimed)
        _codeowner(db_session, club, "maria-rtc")

        rendered = render_codeowners(EXISTING, codeowners_block(db_session))

        assert "# Who to notify about this repository." in rendered
        assert "* @jaimito-asuntos-gringuenos" in rendered

    def test_regenerating_twice_changes_nothing(self, client, db_session):
        """A generator that reshuffles produces a diff on every run, and a
        diff that is always there is a diff nobody reads."""
        club = make_org(db_session, state=OrgState.claimed)
        _codeowner(db_session, club, "maria-rtc")
        _codeowner(db_session, club, "joseph-rtc")

        once = render_codeowners(EXISTING, codeowners_block(db_session))
        twice = render_codeowners(once, codeowners_block(db_session))

        assert once == twice

    def test_the_org_lines_come_after_the_star_line(self, client, db_session):
        """CODEOWNERS is last-match-wins. An org line above `*` would be
        overridden by it and own nothing."""
        club = make_org(db_session, state=OrgState.claimed)
        _codeowner(db_session, club, "maria-rtc")

        rendered = render_codeowners(EXISTING, codeowners_block(db_session))

        assert rendered.index("* @jaimito") < rendered.index("/pipeline/reference/orgs/")

    def test_the_block_is_delimited_so_a_person_can_see_what_to_edit(self, client, db_session):
        rendered = render_codeowners(EXISTING, codeowners_block(db_session))

        assert GENERATED_START in rendered
        assert GENERATED_END in rendered
