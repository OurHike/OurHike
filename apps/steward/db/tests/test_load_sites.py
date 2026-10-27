"""The analysis job's load of the latest sites."""

import json
from pathlib import Path

import psycopg
import pytest
from conftest import SITE, SITES
from psycopg.types.json import Jsonb

from steward_db import load_sites


def loaded(db):
    return dict((r, w) for r, w in db.owner("select rims_id, workable from steward.site"))


def test_a_site_is_claimable_when_its_action_is_restore_or_harden(db):
    assert loaded(db) == {s["rims_id"]: s["action"] in ("close_restore", "harden") for s in SITES}


def test_a_load_replaces_the_last_one(db):
    newer = [{"rims_id": f"{n:08d}-1111-1111-1111-111111111111", "club": "New Club", "action": "harden"} for n in range(3)]
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(newer),))
    assert set(loaded(db)) == {s["rims_id"] for s in newer}


def test_a_load_with_far_fewer_sites_than_are_held_is_refused_and_changes_nothing(db):
    many = [{"rims_id": f"{n:08d}-2222-2222-2222-222222222222", "club": "C", "action": "harden"} for n in range(20)]
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(many),))
    with pytest.raises(psycopg.errors.RaiseException, match="refusing to replace"):
        db.connection.execute("select steward.load_sites(%s)", (Jsonb(many[:5]),))
    assert len(loaded(db)) == 20


def test_a_run_of_loads_cannot_halve_the_sites_one_load_at_a_time(db):
    # The sixth pass's finding 4: each of these is more than half the last.
    many = [{"rims_id": f"{n:08d}-3333-3333-3333-333333333333", "club": "C", "action": "harden"} for n in range(20)]
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(many),))
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(many[:11]),))
    with pytest.raises(psycopg.errors.RaiseException, match="refusing to replace"):
        db.connection.execute("select steward.load_sites(%s)", (Jsonb(many[:6]),))
    assert len(loaded(db)) == 11


def test_no_burst_of_loads_walks_the_list_down_or_pushes_the_months_largest_out(db):
    # The re-check: against the last ten loads, 120 calls in a second took
    # 3,442 sites to 1. The floor is now the month's largest load.
    many = [{"rims_id": f"{n:08d}-5555-5555-5555-555555555555", "club": "C", "action": "harden"} for n in range(40)]
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(many),))
    for _ in range(150):
        db.connection.execute("select steward.load_sites(%s)", (Jsonb(many[:20]),))
    with pytest.raises(psycopg.errors.RaiseException, match="refusing to replace"):
        db.connection.execute("select steward.load_sites(%s)", (Jsonb(many[:19]),))
    # A month on, the largest is the recent ones.
    db.connection.execute("update steward.site_load set loaded_at = now() - interval '31 days' where sites = 40")
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(many[:10]),))
    assert len(loaded(db)) == 10


def test_a_load_that_suddenly_calls_most_sites_unworkable_is_refused(db):
    many = [{"rims_id": f"{n:08d}-4444-4444-4444-444444444444", "club": "C", "action": "harden"} for n in range(20)]
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(many),))
    left_alone = [{**site, "action": "leave"} for site in many]
    with pytest.raises(psycopg.errors.RaiseException, match="refusing to replace"):
        db.connection.execute("select steward.load_sites(%s)", (Jsonb(left_alone),))
    assert all(loaded(db).values())


def test_records_that_are_not_sites_are_skipped_not_loaded(db):
    odd = [*SITES, "not a record", {"rims_id": "<script>"}, {"club": "no id"}]
    db.connection.execute("select steward.load_sites(%s)", (Jsonb(odd),))
    assert set(loaded(db)) == {s["rims_id"] for s in SITES}


def test_the_loader_role_can_load_and_do_nothing_else(db):
    with db.connection.transaction():
        db.connection.execute("set local role steward_loader")
        db.connection.execute("select steward.load_sites(%s)", (Jsonb(SITES),))
    for statement in ("select * from steward.claim", "select steward.me()", "delete from steward.site"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.connection.transaction():
                db.connection.execute("set local role steward_loader")
                db.connection.execute(statement)


def test_the_command_reads_sites_json_and_sends_only_what_the_load_needs(db, database_url, tmp_path):
    sites_json = tmp_path / "sites.json"
    sites_json.write_text(json.dumps([{**s, "lat": 1.0, "lon": 2.0, "name": "x"} for s in SITES]))
    assert load_sites.load(database_url, sites_json) == len(SITES)
    assert SITE in loaded(db)


def test_the_command_takes_the_loaders_login_from_the_environment_only(db, database_url, tmp_path, monkeypatch, capsys):
    # A --database-url argument would put the password in the runner's process list.
    sites_json = tmp_path / "sites.json"
    sites_json.write_text(json.dumps(SITES))
    monkeypatch.delenv(load_sites.DATABASE_URL, raising=False)
    assert load_sites.main([str(sites_json)]) == 1
    assert "STEWARD_SITES_DATABASE_URL" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        load_sites.main(["--database-url", database_url, str(sites_json)])
    monkeypatch.setenv(load_sites.DATABASE_URL, database_url)
    assert load_sites.main([str(sites_json)]) == 0


def test_the_load_jobs_psycopg_is_the_one_the_tests_run():
    def pin(name):
        lines = (Path(__file__).parent.parent / name).read_text().splitlines()
        return [line for line in lines if line.startswith("psycopg")]

    assert pin("requirements.in") == pin("requirements-dev.in")
