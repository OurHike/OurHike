"""Nothing reaches a table directly; the functions and the open views are the
whole surface, and each is granted only to whom it is for."""

import psycopg
import pytest
from conftest import CLUB, SITE, status

TABLES = (
    "site",
    "profile",
    "site_list",
    "site_list_item",
    "club_weights",
    "claim",
    "claim_member",
    "photo",
    "photo_receipt",
    "hours",
    "migration",
)


@pytest.mark.parametrize("who", [None, "someone"], ids=["anon", "signed-in"])
@pytest.mark.parametrize("table", TABLES)
def test_no_table_can_be_read_or_written_directly(db, who, table):
    for statement in (f"select * from remediation.{table}", f"delete from remediation.{table}"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.acting(who) as connection:
                connection.execute(statement)


def test_every_table_has_row_level_security_on(db):
    off = db.owner(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
        " where n.nspname = 'remediation' and c.relkind = 'r' and not c.relrowsecurity and c.relname <> 'migration'"
    )
    assert off == []


def test_signed_out_callers_get_only_the_open_views_and_a_clubs_weights(db):
    with db.acting(None) as connection:
        for view in ("open_claims", "open_photos", "open_weights"):
            connection.execute(f"select * from remediation.{view}").fetchall()
    assert db.call(None, "read_weights", CLUB)["current"]["deficit"] == 60
    error = db.refused(None, "claim_sites", [SITE])
    assert isinstance(error, psycopg.errors.InsufficientPrivilege)


def test_signed_in_callers_cannot_load_sites(db):
    assert isinstance(db.refused("someone", "load_sites", psycopg.types.json.Jsonb([])), psycopg.errors.InsufficientPrivilege)


def test_no_helper_is_callable_by_anyone(db):
    callable_helpers = db.owner(
        "select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace"
        " where n.nspname = 'remediation' and p.proname like '\\_%'"
        " and (has_function_privilege('anon', p.oid, 'execute') or has_function_privilege('authenticated', p.oid, 'execute'))"
    )
    assert callable_helpers == []


def test_a_function_signed_out_is_told_to_sign_in_when_it_is_reachable(db):
    # Every write function is executable only by authenticated; this checks the
    # second wall, the function's own check, for a token with no user in it.
    with pytest.raises(psycopg.Error) as caught:
        with db.acting(None) as connection:
            connection.execute("set local role authenticated")
            connection.execute("select remediation.me()")
    assert status(caught.value) == "PT401"


def test_supabase_anonymous_sign_ins_are_refused(db):
    assert status(db.refused("guest", "me", anonymous=True)) == "PT401"


def test_every_security_definer_function_pins_its_search_path(db):
    loose = db.owner(
        "select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace"
        " where n.nspname = 'remediation' and p.prosecdef"
        " and not exists (select from unnest(p.proconfig) c where c like 'search_path=%')"
    )
    assert loose == []


def test_the_open_files_columns_are_the_open_views(db):
    # apps/remediation/pipeline/remediation_analysis/open_data.py writes an empty view
    # with these names, so they must be the views' own.
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "pipeline" / "remediation_analysis" / "open_data.py"
    tree = ast.parse(source.read_text())
    declared = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign | ast.Assign)
        and getattr(node.target if isinstance(node, ast.AnnAssign) else node.targets[0], "id", None) == "VIEW_COLUMNS"
    )
    for view, columns in declared.items():
        actual = [
            row[0]
            for row in db.owner(
                "select column_name from information_schema.columns where table_schema = 'remediation' and table_name = %s"
                " order by ordinal_position",
                view,
            )
        ]
        assert actual == columns, view
