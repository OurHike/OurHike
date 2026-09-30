"""Which GitHub account a codeowner is, and where that fact may come from.

**WHY THIS IS STORED WHEN THE EMAIL IS NOT.** `get_current_email` reads the
address off the token and keeps nothing, because every check that needs it
happens inside a request that carries one. The GitHub login cannot work that
way: `.github/CODEOWNERS` is generated from the roster at a moment when no
admin is making a request, so the login has to be on a row. That is the whole
reason for the column, and it is worth saying because "store one, do not
store the other" otherwise looks like an oversight.

**AND IT MAY ONLY COME FROM THE PROVIDER.** A typed username proves nothing -
anybody can write `@torvalds` into a form - and a CODEOWNERS entry naming the
wrong account hands somebody else approval over an organization's registry.
So the login is read from the verified token and the request body is not
consulted at all, which is the same rule, for the same reason, as the
registration domain check.
"""

from app.models.profile import Profile
from tests.factories import make_profile
from tests.tokens import auth_headers


class TestLinkingAGitHubAccount:
    def test_the_login_comes_from_the_token(self, client, db_session):
        person = make_profile(db_session)

        response = client.post(
            "/profiles/me/github",
            headers=auth_headers(person.id, github_login="maria-rtc"),
        )

        assert response.status_code == 200
        db_session.expire_all()
        assert db_session.get(Profile, person.id).github_login == "maria-rtc"

    def test_a_login_in_the_body_is_ignored(self, client, db_session):
        """The body is not a source. A caller who could name the account
        would be naming whose approval counts on their organization."""
        person = make_profile(db_session)

        client.post(
            "/profiles/me/github",
            json={"github_login": "torvalds"},
            headers=auth_headers(person.id, github_login="maria-rtc"),
        )

        db_session.expire_all()
        assert db_session.get(Profile, person.id).github_login == "maria-rtc"

    def test_a_token_that_carries_no_github_identity_links_nothing(self, client, db_session):
        """Signed in through some other provider, or through none. A 409
        rather than a 403: they are allowed to be here, there is just
        nothing to read."""
        person = make_profile(db_session)

        response = client.post("/profiles/me/github", headers=auth_headers(person.id))

        assert response.status_code == 409
        db_session.expire_all()
        assert db_session.get(Profile, person.id).github_login is None

    def test_a_login_is_stored_lowercased(self, client, db_session):
        """GitHub logins are case-insensitive, and CODEOWNERS entries that
        differ only in case are the same owner written twice."""
        person = make_profile(db_session)

        client.post("/profiles/me/github", headers=auth_headers(person.id, github_login="Maria-RTC"))

        db_session.expire_all()
        assert db_session.get(Profile, person.id).github_login == "maria-rtc"

    def test_two_accounts_cannot_hold_the_same_login(self, client, db_session):
        """Refused rather than moved. Two profiles claiming one account
        makes a CODEOWNERS entry ambiguous about which seat it stands for,
        and taking it from the first would let anybody with that username
        unseat them."""
        first = make_profile(db_session)
        second = make_profile(db_session)
        client.post("/profiles/me/github", headers=auth_headers(first.id, github_login="maria-rtc"))

        response = client.post(
            "/profiles/me/github",
            headers=auth_headers(second.id, github_login="maria-rtc"),
        )

        assert response.status_code == 409
        db_session.expire_all()
        assert db_session.get(Profile, second.id).github_login is None

    def test_linking_twice_is_not_an_error(self, client, db_session):
        """The console calls this whenever somebody signs in with GitHub;
        pressing it again is the same fact arriving twice."""
        person = make_profile(db_session)
        client.post("/profiles/me/github", headers=auth_headers(person.id, github_login="maria-rtc"))

        response = client.post(
            "/profiles/me/github",
            headers=auth_headers(person.id, github_login="maria-rtc"),
        )

        assert response.status_code == 200

    def test_a_signed_out_visitor_links_nothing(self, client):
        assert client.post("/profiles/me/github").status_code == 401
