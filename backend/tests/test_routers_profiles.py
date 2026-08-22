"""`/profiles` end to end, via the real FastAPI TestClient."""

from app.models.synced_trip import SyncedTrip
from tests.factories import make_profile
from tests.test_account_deletion import _furnish
from tests.tokens import auth_headers, make_token


def test_get_profiles_me_requires_authentication(client):
    response = client.get("/profiles/me")

    assert response.status_code == 401


def test_get_profiles_me_returns_the_current_users_role_and_display_name(client):
    user_id = "88888888-8888-8888-8888-888888888888"
    token = make_token(user_id)

    response = client.get("/profiles/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user_id
    assert body["role"] == "hiker"
    assert body["display_name"] is None
    assert "created_at" in body


class TestDeletingTheAccount:
    """`DELETE /profiles/me` (#895, features/ACCOUNT_SYNC.md phase E).

    The classification is tested against the tables in
    tests/test_account_deletion.py. What is tested here is what only the
    endpoint can be wrong about: the receipt, the transaction, and that the
    door is shut afterwards.
    """

    def test_it_requires_an_account(self, client):
        assert client.delete("/profiles/me").status_code == 401

    def test_the_receipt_counts_what_went(self, client, db_session):
        profile = make_profile(db_session)
        _furnish(db_session, profile.id)

        body = client.delete("/profiles/me", headers=auth_headers(profile.id)).json()

        assert body["trips_deleted"] == 1
        assert body["preferences_deleted"] == 1
        assert body["assignments_released"] == 1
        assert body["app_failure_reports_unlinked"] == 1

    def test_the_receipt_names_what_stayed(self, client, db_session):
        """The half a hiker is most likely to be surprised by.

        The screen says this before the button; this says it again against
        the real rows, because the screen's version is a promise.
        """
        profile = make_profile(db_session)
        _furnish(db_session, profile.id)

        kept = client.delete("/profiles/me", headers=auth_headers(profile.id)).json()["kept"]

        assert kept["photos you shared"] == 1
        assert kept["condition reports"] == 1

    def test_a_hiker_who_contributed_nothing_is_told_exactly_that(self, client, db_session):
        profile = make_profile(db_session)

        kept = client.delete("/profiles/me", headers=auth_headers(profile.id)).json()["kept"]

        assert kept == {}

    def test_the_account_is_gone_afterwards(self, client, db_session):
        profile = make_profile(db_session)

        assert client.delete("/profiles/me", headers=auth_headers(profile.id)).status_code == 200
        assert client.get("/profiles/me", headers=auth_headers(profile.id)).status_code == 401

    def test_deleting_twice_does_not_resurrect_anything(self, client, db_session):
        """The second press has to be refused rather than re-running the scrub.

        A hiker whose network dropped mid-request presses it again, and the
        endpoint they hit is guarded by `get_current_user` - which now
        refuses the account. That is the right answer and it comes out as a
        401 rather than as a second deletion of an account that has none of
        its rows left.
        """
        profile = make_profile(db_session)
        client.delete("/profiles/me", headers=auth_headers(profile.id))

        assert client.delete("/profiles/me", headers=auth_headers(profile.id)).status_code == 401

    def test_it_does_not_reach_another_hikers_account(self, client, db_session):
        mine = make_profile(db_session)
        theirs = make_profile(db_session, display_name="Sundial")
        _furnish(db_session, theirs.id)

        client.delete("/profiles/me", headers=auth_headers(mine.id))

        assert client.get("/profiles/me", headers=auth_headers(theirs.id)).json()["display_name"] == "Sundial"

    def test_a_failure_leaves_the_account_whole(self, client, db_session, monkeypatch):
        """Half a deletion is the one outcome nothing can put right.

        There is no undo here and no second copy to reconcile against, so a
        commit that fails has to leave the hiker signed in with their trips
        rather than half gone with no way to say so.
        """
        import app.routers.profiles as router_module

        profile = make_profile(db_session)
        _furnish(db_session, profile.id)

        def explode(self):
            raise RuntimeError("the database went away")

        monkeypatch.setattr(router_module.Session, "commit", explode, raising=False)

        response = client.delete("/profiles/me", headers=auth_headers(profile.id))

        assert response.status_code == 500
        assert client.get("/profiles/me", headers=auth_headers(profile.id)).status_code == 200
        assert db_session.query(SyncedTrip).filter(SyncedTrip.profile_id == profile.id).count() == 1
