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


def test_a_table_read_off_a_pdf_has_no_freshness_and_its_evaluator_exception_and_every_other_keeps_its_sources():
    """CI's `dbt source freshness` failed on the PDF tables the fixture warehouse never holds (run 37218932289,
    2026-10-04: ata_water_cache_boxes, bmta_access_points, rmc_recommended_hikes), since fixture mode lands no PDF.

    So exactly the generated tables read off a PDF carry `freshness: null`, and each has its
    fct_sources_without_freshness row in seeds/dbt_project_evaluator_exceptions.csv, so the evaluator's rule
    still holds for every other table. generate_notice_models.py's PDF notices are held the same way.
    """
    import csv

    import yaml

    without = set()
    for path in MODELS.glob("staging/*/_*__generated__sources.yml"):
        for source in yaml.safe_load(path.read_text())["sources"]:
            for table in source["tables"]:
                if "freshness" in (table.get("config") or {}):
                    assert table["config"]["freshness"] is None, table["name"]
                    without.add(f"{source['name']}.{table['name']}")
    pdfs = {f"{table.folder}.{table.table}" for table in make_dbt_staging.tables() if table.read_from_pdf}
    assert pdfs >= {"ata.raw_ata__ata_water_cache_boxes", "bmta.raw_bmta__bmta_access_points"}
    assert without == pdfs
    with (MODELS.parent / "seeds" / "dbt_project_evaluator_exceptions.csv").open(newline="") as handle:
        excepted = {row["id_to_exclude"] for row in csv.DictReader(handle) if row["fct_name"] == "fct_sources_without_freshness"}
    assert pdfs <= excepted, sorted(pdfs - excepted)


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
    # A content type's rows carry no geometry (section C, decision 54 wave 3), so no box is drawn for them.
    undecided = {
        table.key
        for table in make_dbt_staging.tables()
        if table.type not in make_dbt_staging.REGIONS_DECIDED_BY_HAND and table.shape.geometry
    }
    assert generated | make_dbt_staging.hand_set_regions() >= undecided
    # A type whose boxes the macro decides gets none generated, so a row it leaves out stays eastern.
    decided = {table.key for table in make_dbt_staging.tables() if table.type in make_dbt_staging.REGIONS_DECIDED_BY_HAND}
    assert not generated & decided


# --- section C's content types (decision 54 wave 3, 2026-10-04) ---------------------------------------------------


def _content(type_: str, reader: str, entry: dict, table: str | None = None) -> Table:
    return Table(
        folder="club",
        type=type_,
        key=entry["key"],
        table=table or f"raw_club__{entry['key']}",
        cadence="monthly",
        entry=entry,
        reader=reader,
    )


def test_a_content_table_is_staged_with_no_geometry_and_its_prose_left_out_of_properties():
    feed = _content("podcasts", "PodcastEpisodes", {"key": "show", "key_fields": ["guid"]})

    base = make_dbt_staging.base_sql(feed)
    staging = make_dbt_staging.stg_sql("club", "podcasts", [feed])

    assert "st_geomfromgeojson" not in base and "geom" not in staging.split("json_merge_patch")[0]
    assert '"description": null' in staging and '"content_encoded": null' in staging, "an episode's notes stop at base_"
    assert "cast(pubdate as varchar) as published" in staging and "cast(enclosure_url as varchar) as audio_url" in staging
    assert make_dbt_staging.union_sql("podcasts", ["stg_club__podcasts"]).count("geom") == 0


def test_a_hike_types_terms_are_a_base_model_keyed_on_taxonomy_and_id_and_no_union_branch():
    terms = _content("suggested_hikes", "SiteTerms", {"key": "hikes", "key_fields": ["id"]}, table="raw_club__hikes_terms")

    assert terms.lookup and terms.base == "base_club__hikes_terms" and terms.key_column == "term_key"
    assert terms.key_inputs() == ["'hikes'", "taxonomy", "id"]
    assert "lookup beside stg_club__suggested_hikes" in make_dbt_staging.base_yaml("club", [terms])


def test_each_nps_list_is_conformed_by_its_endpoint_and_a_photo_by_its_own_licence():
    assets = _content(
        "photos", "NpsContent", {"key": "assets", "key_fields": ["id"], "url": "https://x/api/v1/multimedia/galleries/assets"}
    )
    tours = _content("suggested_hikes", "NpsContent", {"key": "tours", "key_fields": ["id"], "url": "https://x/api/v1/tours"})

    photo = make_dbt_staging._conformed(assets)
    assert "json_extract_string(constraintsinfo, '$.constraint') as licence" in photo
    assert "cast(credit as varchar) as credit" in photo
    assert "cast(null as varchar) as link" in make_dbt_staging._conformed(tours)
    with pytest.raises(ValueError, match="no NPS_COLUMNS row"):
        make_dbt_staging._conformed(_content("photos", "NpsContent", {"key": "z", "url": "https://x/api/v1/alerts"}))


def test_every_content_union_is_a_club_union_beside_the_marts_own_path():
    for type_ in ("podcasts", "suggested_hikes", "challenges", "photos"):
        shape = make_dbt_staging.SHAPES[type_]
        assert not shape.geometry and shape.union == f"int_{type_}__club_unioned"
