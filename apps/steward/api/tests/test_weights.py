import importlib.util
import sys
from pathlib import Path

import pytest
from conftest import bearer

from steward_api import limits
from steward_api.analysis import AnalysisDirectory, AnalysisUnavailable

CLUB = "Example Trail Club"
CHANGE = {"club": CLUB, "deficit": 40, "water": 20, "trail": 6, "cluster": 8, "restricted": 10}


def weights(client, who="viewer", club=CLUB):
    response = client.get("/weights", params={"club": club}, headers=bearer(who))
    assert response.status_code == 200
    return response.json()


def test_a_club_nobody_has_changed_ranks_by_the_defaults(client):
    view = weights(client)
    assert view["current"] == view["defaults"] == limits.DEFAULT_WEIGHTS
    assert view["history"] == []


def test_weights_need_sign_in_to_read_or_change(client):
    assert client.get("/weights", params={"club": CLUB}).status_code == 401
    assert client.post("/weights", json=CHANGE).status_code == 401


def test_a_change_becomes_the_club_s_weights_and_its_history_names_who_and_when(client):
    client.patch("/me", json={"display_name": "Trail boss"}, headers=bearer("boss"))
    response = client.post("/weights", json={**CHANGE, "note": "Water first this year"}, headers=bearer("boss"))
    assert response.status_code == 201
    view = weights(client, who="boss")
    assert view["current"] == {k: CHANGE[k] for k in limits.WEIGHT_NAMES}
    [entry] = view["history"]
    assert entry["changed_by"] == "Trail boss" and entry["by_you"] is True and entry["note"] == "Water first this year"
    assert weights(client, who="somebody-else")["history"][0]["by_you"] is False


def test_the_history_never_hands_out_the_changer_s_account_id(client):
    client.post("/weights", json=CHANGE, headers=bearer("secret-user-id"))
    assert "secret-user-id" not in str(weights(client))


def test_restoring_an_earlier_set_is_a_new_entry_that_points_back_at_it(client):
    client.post("/weights", json=CHANGE, headers=bearer("a"))
    first_id = weights(client)["history"][0]["id"]
    client.post("/weights", json={**CHANGE, "deficit": 80}, headers=bearer("b"))
    assert weights(client)["current"]["deficit"] == 80

    restored = client.post(f"/weights/{first_id}/restore", json={"note": "Undo"}, headers=bearer("c"))
    assert restored.status_code == 201
    view = restored.json()
    assert view["current"]["deficit"] == 40
    assert [e["restored_from"] for e in view["history"]] == [first_id, None, None]


@pytest.mark.parametrize(
    "change",
    [
        {**CHANGE, "club": "A club the analysis has never heard of"},
        {**CHANGE, "deficit": 101},
        {**CHANGE, "water": -1},
        {**CHANGE, "trail": 2.5},
        {k: v for k, v in CHANGE.items() if k != "cluster"},
        {**CHANGE, "changed_by": "someone-else"},
    ],
)
def test_a_change_outside_the_rules_is_refused(client, change):
    assert client.post("/weights", json=change, headers=bearer("a")).status_code == 422
    assert weights(client)["history"] == []


def test_a_change_that_changes_nothing_is_refused_so_the_history_stays_readable(client):
    defaults = {"club": CLUB, **limits.DEFAULT_WEIGHTS}
    assert client.post("/weights", json=defaults, headers=bearer("a")).status_code == 422


def test_one_account_changes_weights_at_most_the_daily_limit(client, monkeypatch):
    monkeypatch.setattr(limits, "WEIGHT_CHANGES_PER_DAY", 2)
    for deficit in (41, 42):
        assert client.post("/weights", json={**CHANGE, "deficit": deficit}, headers=bearer("busy")).status_code == 201
    assert client.post("/weights", json={**CHANGE, "deficit": 43}, headers=bearer("busy")).status_code == 429
    assert client.post("/weights", json={**CHANGE, "deficit": 43}, headers=bearer("other")).status_code == 201


def test_a_change_is_503_when_the_club_list_cannot_be_read(client, app):
    def unavailable():
        raise AnalysisUnavailable("down")

    app.state.analysis = AnalysisDirectory(unavailable)
    assert client.post("/weights", json=CHANGE, headers=bearer("a")).status_code == 503


def test_the_history_keeps_the_name_a_change_was_made_under(client):
    client.patch("/me", json={"display_name": "Trail boss"}, headers=bearer("boss"))
    client.post("/weights", json=CHANGE, headers=bearer("boss"))
    client.patch("/me", json={"display_name": "Somebody new"}, headers=bearer("boss"))
    assert weights(client)["history"][0]["changed_by"] == "Trail boss"


def test_restoring_an_entry_id_past_any_real_one_is_a_422_not_a_500(client):
    # The review's finding 11: an id past Postgres's integer range was a 500.
    response = client.post("/weights/99999999999999999999999/restore", json={}, headers=bearer("a"))
    assert response.status_code == 422


def test_the_daily_limit_holds_against_parallel_requests(client, monkeypatch):
    # The review's finding 8: counted then inserted, 12 parallel requests got
    # past a cap of 3 in 6 runs of 7. The caller's row is now locked first.
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(limits, "WEIGHT_CHANGES_PER_DAY", 3)
    client.get("/me", headers=bearer("racer"))

    def change(deficit):
        return client.post("/weights", json={**CHANGE, "deficit": deficit}, headers=bearer("racer")).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(change, range(20, 32)))
    assert statuses.count(201) == 3, statuses


def _pipeline_rules():
    path = Path(__file__).resolve().parents[2] / "pipeline" / "steward_analysis" / "rules.py"
    spec = importlib.util.spec_from_file_location("steward_pipeline_rules", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses looks its module up while building the class
    spec.loader.exec_module(module)
    return module


def test_the_weight_names_and_defaults_are_the_analysis_job_s():
    rules = _pipeline_rules()
    assert limits.WEIGHT_NAMES == rules.WEIGHT_NAMES
    assert limits.DEFAULT_WEIGHTS == {name: getattr(rules.DEFAULT_WEIGHTS, name) for name in rules.WEIGHT_NAMES}
