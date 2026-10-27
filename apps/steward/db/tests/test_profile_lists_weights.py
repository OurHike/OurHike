"""You, your lists and their share links, and club weights: the old API's
phase 2 behaviour (#1906), now in SQL."""

import sys
from pathlib import Path

import pytest
from conftest import CLUB, NEIGHBOUR, SITE, status

# --- You -------------------------------------------------------------------------


def test_the_first_call_makes_a_profile_with_no_name(db):
    assert db.call("volunteer", "me") == {"display_name": None}
    assert db.call("volunteer", "set_display_name", "  Ridge Runner  ") == {"display_name": "Ridge Runner"}
    assert db.call("volunteer", "set_display_name", None) == {"display_name": None}


@pytest.mark.parametrize(
    "name",
    ["", "   ", "x" * 41, "tab\there", "Ridge\u202eRunner", "zero\u200bwidth", "private\ue000use", "bell\x07"],
    ids=["empty", "blank", "too-long", "tab", "bidi-override", "zero-width", "private-use", "control"],
)
def test_a_name_that_is_empty_too_long_or_hides_characters_is_refused(db, name):
    # The review's finding 10: a bidi override lets one name pass for another.
    # (NUL is not here: Postgres text cannot hold it, so it never reaches a function.)
    assert status(db.refused("volunteer", "set_display_name", name)) == "PT422"


# --- Lists -----------------------------------------------------------------------


def test_a_list_keeps_its_sites_in_order_once_each(db):
    made = db.call("owner", "create_list", "Spring workday", [SITE, NEIGHBOUR, SITE])
    assert made["rims_ids"] == [SITE, NEIGHBOUR] and made["item_count"] == 2
    db.call("owner", "add_to_list", made["id"], SITE)
    assert db.call("owner", "read_list", made["id"])["rims_ids"] == [SITE, NEIGHBOUR]
    db.call("owner", "remove_from_list", made["id"], SITE)
    assert db.call("owner", "read_list", made["id"])["rims_ids"] == [NEIGHBOUR]
    assert [summary["name"] for summary in db.call("owner", "my_lists")] == ["Spring workday"]


def test_someone_elses_list_is_no_such_list_whatever_they_try(db):
    made = db.call("owner", "create_list", "Mine", [])
    for function, args in (
        ("read_list", ()),
        ("rename_list", ("Theirs",)),
        ("delete_list", ()),
        ("add_to_list", (SITE,)),
        ("share_list", ()),
        ("unshare_list", ()),
    ):
        assert status(db.refused("stranger", function, made["id"], *args)) == "PT404"


def test_a_share_link_opens_the_list_for_anyone_signed_in_until_it_is_replaced(db):
    made = db.call("owner", "create_list", "Shared", [SITE])
    first = db.call("owner", "share_list", made["id"])["token"]
    assert db.call("friend", "open_shared_list", first)["rims_ids"] == [SITE]
    second = db.call("owner", "share_list", made["id"])["token"]
    assert status(db.refused("friend", "open_shared_list", first)) == "PT404"
    assert db.call("friend", "open_shared_list", second)["name"] == "Shared"
    db.call("owner", "unshare_list", made["id"])
    assert status(db.refused("friend", "open_shared_list", second)) == "PT404"
    assert status(db.refused(None, "open_shared_list", second)) in {"PT401", "42501"}


def test_only_the_tokens_hash_is_kept(db):
    made = db.call("owner", "create_list", "Shared", [])
    token = db.call("owner", "share_list", made["id"])["token"]
    stored = db.owner("select share_token_sha256 from steward.site_list where id = %s", made["id"])[0][0]
    assert token not in stored and len(stored) == 64


def test_lists_and_their_items_are_capped(db):
    for n in range(50):
        db.call("owner", "create_list", f"List {n}", [])
    assert status(db.refused("owner", "create_list", "One too many", [])) == "PT409"
    too_many = [f"site-{n}" for n in range(501)]
    assert status(db.refused("other", "create_list", "Huge", too_many)) == "PT422"


def test_a_site_id_that_could_carry_markup_is_refused(db):
    made = db.call("owner", "create_list", "Mine", [])
    assert status(db.refused("owner", "add_to_list", made["id"], "<script>")) == "PT422"


# --- Weights ---------------------------------------------------------------------


def weights(**changed):
    values = {"deficit": 60, "water": 12, "trail": 6, "cluster": 8, "restricted": 10} | changed
    return [values[k] for k in ("deficit", "water", "trail", "cluster", "restricted")]


def test_the_default_weights_are_the_analysis_jobs(db):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
    from steward_analysis.rules import DEFAULT_WEIGHTS, WEIGHT_NAMES

    expected = {name: getattr(DEFAULT_WEIGHTS, name) for name in WEIGHT_NAMES}
    assert db.call(None, "read_weights", CLUB)["defaults"] == expected


def test_a_change_is_kept_with_the_name_its_changer_had_then(db):
    db.call("leader", "set_display_name", "Trail Boss")
    view = db.call("leader", "change_weights", CLUB, *weights(water=24), "Water first")
    assert view["current"]["water"] == 24
    db.call("leader", "set_display_name", "Someone Else")
    entry = db.call(None, "read_weights", CLUB)["history"][0]
    assert entry["changed_by"] == "Trail Boss" and entry["note"] == "Water first" and entry["by_you"] is False
    assert db.call("leader", "read_weights", CLUB)["history"][0]["by_you"] is True


def test_a_change_must_be_to_a_known_club_and_change_something(db):
    assert status(db.refused("leader", "change_weights", "No Such Club", *weights(water=24), None)) == "PT422"
    assert status(db.refused("leader", "change_weights", CLUB, *weights(), None)) == "PT422"
    assert status(db.refused("leader", "change_weights", CLUB, *weights(water=101), None)) == "PT422"


def test_one_account_changes_weights_at_most_30_times_a_day(db):
    for n in range(30):
        db.call("busy", "change_weights", CLUB, *weights(water=n + 20), None)
    assert status(db.refused("busy", "change_weights", CLUB, *weights(water=99), None)) == "PT429"


def test_restore_is_a_new_entry_pointing_back(db):
    first = db.call("a", "change_weights", CLUB, *weights(water=24), None)["history"][0]
    db.call("b", "change_weights", CLUB, *weights(water=30), None)
    restored = db.call("c", "restore_weights", first["id"], "Back to water 24")
    assert restored["current"]["water"] == 24 and restored["history"][0]["restored_from"] == first["id"]
    assert status(db.refused("c", "restore_weights", 999999, None)) == "PT404"


def test_the_open_weights_view_is_the_whole_history_without_who_beyond_their_name(db):
    db.call("leader", "change_weights", CLUB, *weights(water=24), None)
    with db.acting(None) as connection:
        columns = [d.name for d in connection.execute("select * from steward.open_weights").description]
    assert "changed_by" in columns and not {"changed_by_id", "user_id"} & set(columns)
