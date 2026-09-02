"""The CI dbt job's fixtures stay loadable and stay honest (#100).

Two properties matter: load_raw.py can actually load what this writes (a
fixture that drifted from the loader is a green CI step proving nothing),
and the opentrail fixture covers ICON_LEGEND's whole domain so the dbt-side
accepted_values test exercises every documented code.
"""

import duckdb
import pytest

import fetch_opentrail
import load_raw
import make_dbt_fixtures


def test_fixtures_load_through_the_real_loader(tmp_path):
    make_dbt_fixtures.write_fixtures(tmp_path)
    con = duckdb.connect()
    try:
        loaded, skipped = load_raw.load_raw(con, tmp_path)
        assert set(loaded) == {
            "raw_atc__shelters",
            "raw_atc__campsites",
            "raw_atc__viewpoints",
            "raw_atc__parking",
            "raw_atc__privies",
            "raw_atc__communities",
            "raw_atc__bridges",
            "raw_atc__centerline",
            "raw_atc__side_trails",
            "raw_atc__trail_club_sections",
            "raw_atc__half_mile_points_from_springer",
            "raw_atc__at_treadway",
            "raw_opentrail__at",
            "raw_oprhp__oprhp_trails",
            "raw_oprhp__oprhp_trail_closures",
            "raw_oprhp__oprhp_facilities",
            "raw_oprhp__oprhp_park_polygons",
            "raw_nynjtc__nynjtc_long_path",
            "raw_nynjtc__nynjtc_highlands_trail",
            "raw_mohonk__mohonk_trails",
            "raw_dec__dec_hiking_trails",
            "raw_dec__dec_lean_tos",
            "raw_dec__dec_primitive_campsites",
            "raw_dec__dec_scenic_vistas",
            "raw_dec__dec_firetowers",
            "raw_dec__dec_viewing_areas",
            "raw_dec__dec_parking_areas",
            "raw_dec__dec_backcountry_features",
            "raw_usfs__usfs_trails",
            "raw_usfs__usfs_rec_sites",
            "raw_granit__nh_granit_trails",
        }
        assert skipped == [], (
            "every registered feature layer needs a fixture, or the CI dbt build "
            "fails on a staging model whose raw table never loaded"
        )
        icons = {row[0] for row in con.execute("select icon from raw.raw_opentrail__at").fetchall()}
        markers = {row[0] for row in con.execute('select "MARKER" from raw.raw_dec__dec_hiking_trails').fetchall()}
        blazes = {row[0] for row in con.execute('select "Blaze" from raw.raw_mohonk__mohonk_trails').fetchall()}
        publicuse = {row[0] for row in con.execute('select "PUBLICUSE" from raw.raw_dec__dec_lean_tos').fetchall()}
        granit_blazes = {row[0] for row in con.execute('select "BLAZE" from raw.raw_granit__nh_granit_trails').fetchall()}
        granit_ped = {row[0] for row in con.execute('select "PED" from raw.raw_granit__nh_granit_trails').fetchall()}
        usfs_types = {row[0] for row in con.execute("select trail_type from raw.raw_usfs__usfs_trails").fetchall()}
        usfs_designations = {
            row[0]
            for row in con.execute(
                "select national_trail_designation from raw.raw_usfs__usfs_trails where trail_name = 'FIXTURE CRAWFORD PATH'"
            ).fetchall()
        }
        park_polygon_columns = {
            row[0]
            for row in con.execute(
                "select column_name from information_schema.columns where table_name = 'raw_oprhp__oprhp_park_polygons'"
            ).fetchall()
        }
    finally:
        con.close()

    assert icons == set(fetch_opentrail.ICON_LEGEND), (
        "the fixture must cover every documented icon, or the dbt accepted_values test runs against a subset of its domain"
    )
    assert "ORANGE AND RED" in markers, (
        "DEC's MARKER carries one value its own domain does not declare (measured on the live 5,286 rows); "
        "a fixture without it would let an accepted_values test be added that the real layer fails"
    )
    assert "" in markers, "2,929 of the live 5,286 rows read blank - the commonest value must be exercised"
    assert "N/A" in blazes, "the literal string 'N/A' is 124 of Mohonk's live 304 rows, not a null"
    assert None in blazes, "7 of Mohonk's live 304 rows carry no Blaze value at all"
    assert publicuse == {"Y", "N"}, (
        "the public flag the staging models carry through has nothing to say unless both sides are present"
    )
    assert " " in granit_blazes, (
        "GRANIT's BLAZE is a blank STRING on 7,574 of the live 7,643 Whites rows - 99.1% - because the Whites "
        "largely are not blazed. reference/blaze_mapping.json keys that literal ' ' to \"None\" (Unblazed), so a "
        "fixture that dropped it would stop exercising the row the whole mapping turns on"
    )
    assert "White" in granit_blazes, (
        "the A.T. is the one white-blazed line through the Whites - 61 of the live 62 White rows carry TRAILSYS "
        "'Appalachian Trail' - so the colour that IS present has to be exercised too"
    )
    assert granit_ped == {"1", " "}, (
        "PED splits 3,883 '1' against 3,760 blank on the live rows, and blank means UNRECORDED rather than no - "
        "a fixture with only '1' would make a PED filter look lossless when it drops half the layer"
    )
    assert usfs_types == {"TERRA", "SNOW"}, (
        "549 of the live 2,093 WMNF rows are snowmobile and water corridors; a TERRA-only fixture would let the "
        "filter this layer needs be forgotten"
    )
    assert usfs_designations == {1, 2, 3}, (
        "CRAWFORD PATH really does carry all three designation codes across its live segments. That split is the "
        "one thing no 'code 3 = the A.T.' reading explains, and it is why sources.json keeps the field "
        "@unvalidated even though NH GRANIT's white-blazed set independently names nearly the same trails"
    )
    assert park_polygon_columns.isdisjoint({"Name", "NAME", "OBJECTID"}), (
        "sources.json records no field name for oprhp_park_polygons, so its fixture must invent none - "
        "a property here would be a schema nobody measured, and DBT.md's Phase D section says why it is unstaged"
    )


def test_refuses_to_overwrite_a_real_fetch(tmp_path):
    (tmp_path / "shelters.geojson").write_text("{}")

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        make_dbt_fixtures.write_fixtures(tmp_path)


def test_refuses_to_overwrite_a_real_external_fetch(tmp_path):
    """The same guard, one directory down. fetch_external_layers.py writes
    into data/raw/external/, so a workspace that has already fetched OPRHP
    but not ATC would otherwise look empty to the check above."""
    external = tmp_path / "external"
    external.mkdir()
    (external / "oprhp_trails.geojson").write_text("{}")

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        make_dbt_fixtures.write_fixtures(tmp_path)
