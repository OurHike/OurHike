"""pipeline/make_dbt_staging.py's output stays what it would write, and keys nothing it should not.

The generator writes the dbt staging layer for every club ArcGIS layer of a staged type that no
hand-written model reads (pipeline/ELT.md, "Loading everything the clubs publish (decision 54)"): a
base model per raw table, keyed on the registry's measured key (decision 40), a staging model per
club and type, each type's union, and the region each source is held to. Its output is committed,
so a registry edit that changes a key, a title or a date field, or a layer registered without its
models, fails here until the generator is run again.
"""

import re
from pathlib import Path

import pytest

import make_dbt_staging
from make_dbt_staging import KeyRefused, Table

MODELS = Path(make_dbt_staging.MODELS)


def test_the_committed_files_are_exactly_what_the_generator_writes():
    problems = make_dbt_staging.differences(make_dbt_staging.render())
    assert problems == [], "run `python make_dbt_staging.py` from pipeline/ and commit what it writes:\n" + "\n".join(problems)


def test_every_staged_types_arcgis_layer_has_a_model_reading_its_raw_table():
    """No layer of a type the generator stages is left with no base model, hand-written or generated."""
    from extract._contract import discover
    from extract._kinds import ArcgisLayer

    read = set()
    for path in MODELS.rglob("*.sql"):
        read.update(re.findall(r"source\('[a-z0-9_]+',\s*'(raw_[a-z0-9_]+)'\)", path.read_text()))
    unstaged = [
        resource.table
        for club_file in discover()
        if club_file.type in make_dbt_staging.SHAPES
        for resource in club_file.resources
        if isinstance(resource, ArcgisLayer)
        and resource.entry.get("kind") in make_dbt_staging.KINDS
        and resource.table not in read
    ]
    assert unstaged == []


def test_there_are_layers_to_stage():
    """Decision 54's wave 1 on this branch: 83 places, 6 elevation, 98 trail-line and 69 point layers at least."""
    by_type = {}
    for table in make_dbt_staging.tables():
        by_type[table.type] = by_type.get(table.type, 0) + 1
    assert by_type.get("places", 0) >= 83
    assert by_type.get("elevation", 0) >= 6
    assert by_type.get("trail_lines", 0) >= 98
    assert by_type.get("points_of_interest", 0) >= 69


def _table(entry: dict, type_: str = "places") -> Table:
    return Table(folder="club", type=type_, key=entry["key"], table=f"raw_club__{entry['key']}", cadence="monthly", entry=entry)


@pytest.mark.parametrize(
    ("entry", "inputs"),
    [
        ({"key": "a", "id_field": "GlobalID"}, ["'a'", "globalid"]),
        ({"key": "a", "id_fields": ["NAME", "COUNTY"]}, ["'a'", "name", "county"]),
        ({"key": "a", "id_field": "OBJECTID", "key_fields": ["GlobalID"]}, ["'a'", "globalid"]),
        ({"key": "a", "key_fields": ["geometry", "Name"]}, ["'a'", "geometry_key('geom')", "name"]),
        # A one-row layer: the registry key and its shape (base_pcta__centerline's precedent).
        ({"key": "a", "key_fields": []}, ["'a'", "geometry_key('geom')"]),
        # dlt's sql_ci_v1 names, path by path, and a reserved word quoted.
        ({"key": "a", "id_fields": ["Shape__Length", "NHRECPOL_", "DESC_"]}, ["'a'", "shape__length", "nhrecpol", '"desc"']),
    ],
)
def test_the_key_is_the_registry_key_then_the_measured_fields_as_dlt_names_them(entry, inputs):
    assert _table(entry).key_inputs() == inputs


@pytest.mark.parametrize(
    "entry",
    [
        {"key": "a"},
        {"key": "a", "id_field": None},
        {"key": "a", "id_field": "OBJECTID"},
        {"key": "a", "id_fields": ["FID"]},
        {"key": "a", "key_fields": ["geometry", "OBJECTID_1"]},
        {"key": "a", "key_fields": ["geometry", "every attribute column"]},
    ],
)
def test_a_row_with_no_measured_key_or_a_server_row_id_in_it_is_refused(entry):
    """Decision 40: never a server row id, which a reload mints again; and no table staged without a key."""
    with pytest.raises(KeyRefused):
        _table(entry).key_inputs()


def test_an_arcgis_date_is_cast_from_epoch_milliseconds_to_a_utc_timestamp():
    sql = make_dbt_staging.base_sql(_table({"key": "a", "id_field": "GlobalID", "date_fields": ["UPDATED", "Edit_Date"]}))
    assert "* exclude (geometry, updated, edit_date)" in sql
    assert "to_timestamp(updated / 1000) as updated" in sql
    assert "to_timestamp(edit_date / 1000) as edit_date" in sql


def test_a_layer_with_no_name_field_takes_its_registry_name_constant():
    conformed = make_dbt_staging._conformed(_table({"key": "a", "id_field": "MOREINFO", "name_constant": "Catskill Park"}))
    assert conformed[0] == "cast('Catskill Park' as varchar) as name"


def test_a_long_name_constant_is_cut_for_the_line_limit_and_joins_back_to_itself():
    """SQLFluff's LT05 holds a line to 80, so a long constant is pieces joined with ||, which DuckDB reads as the whole."""
    import duckdb

    constant = "Ala Kahakai National Historic Trail - Ka'awaloa Trail (SIHP 14176)"
    sql = make_dbt_staging._name({"name_constant": constant})
    assert all(len(line) + 4 <= 80 for line in sql.split("\n"))
    assert duckdb.sql(f"select {sql}").fetchone()[0] == constant


def test_a_trail_line_layer_is_staged_with_its_name():
    conformed = make_dbt_staging._conformed(
        _table({"key": "a", "key_fields": ["geometry"], "name_field": "TRAILNAME"}, "trail_lines")
    )
    assert conformed == ["cast(trailname as varchar) as name"]


def test_a_point_layer_is_staged_with_its_name_its_type_and_the_id_it_publishes_under():
    """A point publishes under its layer's own id, and under its base model's key where id_field is a server row id."""
    own = make_dbt_staging._conformed(
        _table({"key": "a", "id_field": "GlobalID", "name_field": "FET_NAME", "type_field": "FET_TYPE"}, "points_of_interest")
    )
    assert own == [
        "cast(fet_name as varchar) as name",
        "cast(fet_type as varchar) as category",
        "cast(globalid as varchar) as source_id",
    ]
    keyed = make_dbt_staging._conformed(
        _table({"key": "a", "id_field": "OBJECTID", "key_fields": ["geometry"], "name_field": "Name"}, "points_of_interest")
    )
    assert keyed == [
        "cast(name as varchar) as name",
        "cast(null as varchar) as category",
        "cast(poi_key as varchar) as source_id",
    ]


def test_the_point_union_is_not_the_hand_written_one_it_feeds():
    """int_points_of_interest__unioned is hand-written and reads the generated union as one branch."""
    shape = make_dbt_staging.SHAPES["points_of_interest"]
    assert shape.union != "int_points_of_interest__unioned"
    hand = (MODELS / "intermediate" / "points_of_interest" / "int_points_of_interest__unioned.sql").read_text()
    assert make_dbt_staging.GENERATED not in hand.split("\n", 1)[0]


def test_an_elevation_layer_names_its_field_or_its_geometry_z():
    field = make_dbt_staging._conformed(
        _table({"key": "a", "id_field": "GlobalID", "elevation_source": "field Max_Elevat"}, "elevation")
    )
    z = make_dbt_staging._conformed(_table({"key": "a", "id_field": "GlobalID", "elevation_source": "geometry Z"}, "elevation"))
    assert field == ["cast(max_elevat as varchar) as published_elevation"]
    assert z == ["cast(null as varchar) as published_elevation"]
    with pytest.raises(ValueError):
        make_dbt_staging._conformed(_table({"key": "a", "id_field": "GlobalID"}, "elevation"))


def test_each_union_reads_exactly_the_staging_models_the_generator_writes_for_its_type():
    files = make_dbt_staging.render()
    for type_, shape in make_dbt_staging.SHAPES.items():
        union = files.get(MODELS / "intermediate" / type_ / f"{shape.union}.sql")
        if union is None:
            continue
        refs = set(re.findall(r"ref\('(stg_[a-z0-9_]+)'\)", union))
        written = {path.stem for path in files if path.name.startswith("stg_") and path.stem.endswith(f"__{type_}")}
        assert refs == written


def test_a_region_set_by_hand_in_the_macro_is_not_generated_again():
    files = make_dbt_staging.render()
    generated = set(re.findall(r"= '([a-z0-9_]+)' then", files[make_dbt_staging.REGIONS_MACRO]))
    assert not generated & make_dbt_staging.hand_set_regions()
    undecided = {table.key for table in make_dbt_staging.tables() if table.type not in make_dbt_staging.REGIONS_DECIDED_BY_HAND}
    assert generated | make_dbt_staging.hand_set_regions() >= undecided
    # A type whose boxes the macro decides gets none generated, so a row it leaves out stays eastern.
    decided = {table.key for table in make_dbt_staging.tables() if table.type in make_dbt_staging.REGIONS_DECIDED_BY_HAND}
    assert not generated & decided
