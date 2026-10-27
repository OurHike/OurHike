"""The analysis job's load of the latest sites."""

import json

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
