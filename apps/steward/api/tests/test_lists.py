import pytest
from conftest import bearer
from sqlalchemy import select

from steward_api import limits
from steward_api.models import SiteList

SITE_A = "4d9ce529-d198-40ee-9a11-02b0184b5270"
SITE_B = "f599a2a9-c5c4-4e62-c303-2ebb43e75017"


def make_list(client, owner="owner", **body):
    response = client.post("/lists", json={"name": "Spring workday", **body}, headers=bearer(owner))
    assert response.status_code == 201, response.text
    return response.json()


def test_a_new_list_keeps_its_sites_once_each_in_the_order_given(client):
    created = make_list(client, rims_ids=[SITE_B, SITE_A, SITE_B])
    assert created["rims_ids"] == [SITE_B, SITE_A]
    assert created["item_count"] == 2 and created["shared"] is False


def test_saving_a_site_twice_keeps_one_entry_and_removing_it_takes_it_out(client):
    list_id = make_list(client)["id"]
    for _ in range(2):
        assert client.put(f"/lists/{list_id}/items/{SITE_A}", headers=bearer("owner")).status_code == 204
    assert client.get(f"/lists/{list_id}", headers=bearer("owner")).json()["rims_ids"] == [SITE_A]
    assert client.delete(f"/lists/{list_id}/items/{SITE_A}", headers=bearer("owner")).status_code == 204
    assert client.get(f"/lists/{list_id}", headers=bearer("owner")).json()["rims_ids"] == []


@pytest.mark.parametrize("bad", ["<script>", "a b", "x" * 65, "../../etc"])
def test_a_site_id_that_is_not_shaped_like_a_rims_id_is_refused(client, bad):
    list_id = make_list(client)["id"]
    # 404/405 where the path no longer routes to the item endpoint at all ("a b", "../../etc").
    assert client.put(f"/lists/{list_id}/items/{bad}", headers=bearer("owner")).status_code in (404, 405, 422)
    assert client.get(f"/lists/{list_id}", headers=bearer("owner")).json()["rims_ids"] == []
    assert client.post("/lists", json={"name": "x", "rims_ids": [bad]}, headers=bearer("owner")).status_code == 422


def test_somebody_else_s_list_is_404_for_every_verb_so_ids_cannot_be_probed(client):
    list_id = make_list(client)["id"]
    stranger = bearer("stranger")
    assert client.get(f"/lists/{list_id}", headers=stranger).status_code == 404
    assert client.patch(f"/lists/{list_id}", json={"name": "Mine now"}, headers=stranger).status_code == 404
    assert client.put(f"/lists/{list_id}/items/{SITE_A}", headers=stranger).status_code == 404
    assert client.post(f"/lists/{list_id}/share", headers=stranger).status_code == 404
    assert client.delete(f"/lists/{list_id}", headers=stranger).status_code == 404
    assert client.get(f"/lists/{list_id}", headers=bearer("owner")).json()["name"] == "Spring workday"


def test_a_list_name_is_required_trimmed_and_bounded(client):
    assert client.post("/lists", json={"name": "   "}, headers=bearer("owner")).status_code == 422
    assert client.post("/lists", json={"name": "x" * 81}, headers=bearer("owner")).status_code == 422
    assert client.post("/lists", json={"name": "ok", "owner_id": "someone-else"}, headers=bearer("owner")).status_code == 422


def test_one_account_keeps_at_most_the_list_limit(client, monkeypatch):
    monkeypatch.setattr(limits, "LISTS_PER_USER", 2)
    make_list(client)
    make_list(client)
    assert client.post("/lists", json={"name": "third"}, headers=bearer("owner")).status_code == 409


def test_a_list_holds_at_most_the_item_limit(client, monkeypatch):
    monkeypatch.setattr(limits, "ITEMS_PER_LIST", 1)
    list_id = make_list(client)["id"]
    assert client.put(f"/lists/{list_id}/items/{SITE_A}", headers=bearer("owner")).status_code == 204
    assert client.put(f"/lists/{list_id}/items/{SITE_B}", headers=bearer("owner")).status_code == 409


def test_a_share_link_opens_the_list_read_only_for_any_signed_in_user(client):
    client.patch("/me", json={"display_name": "Crew lead"}, headers=bearer("owner"))
    list_id = make_list(client, rims_ids=[SITE_A])["id"]
    share = client.post(f"/lists/{list_id}/share", headers=bearer("owner")).json()["token"]

    opened = client.post("/shared", json={"token": share}, headers=bearer("friend"))
    assert opened.status_code == 200
    assert opened.json()["name"] == "Spring workday" and opened.json()["owner"] == "Crew lead"
    assert opened.json()["rims_ids"] == [SITE_A]
    assert client.post("/shared", json={"token": share}).status_code == 401


def test_only_the_share_token_s_hash_is_stored(client, app):
    list_id = make_list(client)["id"]
    share = client.post(f"/lists/{list_id}/share", headers=bearer("owner")).json()["token"]
    with app.state.sessionmaker() as db:
        stored = db.scalars(select(SiteList.share_token_sha256)).one()
    assert stored and share not in stored and len(stored) == 64


def test_sharing_again_replaces_the_link_and_stopping_sharing_ends_it(client):
    list_id = make_list(client)["id"]
    first = client.post(f"/lists/{list_id}/share", headers=bearer("owner")).json()["token"]
    second = client.post(f"/lists/{list_id}/share", headers=bearer("owner")).json()["token"]
    assert client.post("/shared", json={"token": first}, headers=bearer("friend")).status_code == 404
    assert client.post("/shared", json={"token": second}, headers=bearer("friend")).status_code == 200
    assert client.delete(f"/lists/{list_id}/share", headers=bearer("owner")).status_code == 204
    assert client.post("/shared", json={"token": second}, headers=bearer("friend")).status_code == 404


def test_my_lists_lists_only_mine(client):
    make_list(client, owner="a")
    make_list(client, owner="b")
    assert [entry["name"] for entry in client.get("/lists", headers=bearer("a")).json()] == ["Spring workday"]
