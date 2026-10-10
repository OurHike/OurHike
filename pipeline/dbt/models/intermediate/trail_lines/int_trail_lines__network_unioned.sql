{{ config(materialized='table') }}
-- Every row of every network line layer, before any filter: one branch per
-- layer, `union all by name`. export_nearby_trails.py reads each layer's
-- fetched GeoJSON whole and filters it feature by feature; this is those
-- features, read from the warehouse instead.
--
-- `properties` IS THE ROW'S COLUMNS AS ONE JSON OBJECT, and the reason is
-- the registry. Every filter in keep_reason() reads a column by the name
-- sources.json gives it (`foot_field`, `status_field`, `excluded_when`'s
-- keys), and those names are data, not SQL: a column reference written here
-- per layer would be a second copy of the registry. So each branch selects
-- its row's columns, turns that row into JSON with to_json() over the row
-- alias in a select of its own (the alias is then its only reference, which
-- `dbt lint`'s RF03 asks of a single-table select), reads the staging key
-- back out of the JSON, and int_trail_lines__network_judged reads a
-- field by its warehouse column name (int_trail_lines__network_sources'
-- `*_column`). A column the layer does not have reads as absent, which is
-- how missing_declared_fields() can be asked in SQL at all (TL08). Values
-- keep the types dlt landed them as. Not DuckDB's `*columns(...)` unpacking,
-- which does the same in one line: dbt 2.0.6's own SQL parser warns
-- SyntaxInvalid (dbt0101) on it (measured 2026-10-02), though DuckDB runs it.
--
-- FIVE LAYERS COME THROUGH stg_ MODELS AND NOT base_ MODELS: OPRHP's, DEC's,
-- the two NYNJTC layers and Mohonk's, staged in Phase D (#100 — Build the
-- dbt ELT transform layer before NYNJTC's own trail network arrives) before
-- base models existed. Their `properties` carry the stg column names, which
-- for some columns are not the raw ones (stg_oprhp__trails' `public_flag`
-- is the raw `public`); every column a filter reads keeps its raw name in
-- all five, checked against each model's select list. DEC's two id columns
-- are restored to their raw names below, because the published id reads
-- them.
--
-- A row's published id is int_trail_lines__network_judged's to build, from
-- `properties` and `source_row` (TL05).
{%- set base_branches = [
    ('usfs_trails', 'usfs', 'base_usfs__trails'),
    ('njdep_park_trails', 'njgin', 'base_njgin__njdep_park_trails'),
    ('nj_statewide_trails', 'njgin', 'base_njgin__nj_statewide_trails'),
    ('nyc_parks_trails', 'nycparks', 'base_nycparks__nyc_parks_trails'),
    ('nyc_dot_greenways', 'nycdot', 'base_nycdot__nyc_dot_greenways'),
    ('nyc_cscl_paths', 'nycdot', 'base_nycdot__nyc_cscl_paths'),
    ('nyc_park_drives', 'nycdot', 'base_nycdot__nyc_park_drives'),
    ('nps_trails', 'nps', 'base_nps__trails'),
    ('blm_trails', 'blm', 'base_blm__trails'),
    ('cotrex_trails', 'cotrex', 'base_cotrex__trails'),
    ('wa_rco_trails', 'wa_rco', 'base_wa_rco__trails'),
    ('utah_sgid_trails', 'utah_sgid', 'base_utah_sgid__trails'),
    ('ncta_trail', 'ncta', 'base_ncta__trail'),
    ('alaska_trails', 'alaska_trails', 'base_alaska_trails__alaska_trails'),
    ('pasda_dcnr_trails', 'pasda', 'base_pasda__dcnr_trails'),
    ('ct_deep_blue_blazed', 'ct_deep', 'base_ct_deep__blue_blazed'),
    ('nc_mst_trail', 'nc_mst', 'base_nc_mst__trail'),
    ('azgeo_arizona_trail', 'azgeo', 'base_azgeo__arizona_trail'),
    ('tahoe_rim_trail', 'tahoe_rim', 'base_tahoe_rim__trail'),
    ('duluth_superior_hiking_trail', 'duluth', 'base_duluth__superior_hiking_trail'),
    ('massgis_long_distance_trails', 'massgis', 'base_massgis__long_distance_trails'),
    ('pcta_centerline', 'pcta', 'base_pcta__centerline'),
    ('cdtc_centerline', 'cdtc', 'base_cdtc__centerline'),
    ('wi_ice_age_trail', 'wi_dnr', 'base_wi_dnr__wi_ice_age_trail'),
] %}
{#- The fourth field: whether the stg model carries `source_row`, the
    raw table's order, which the two NYNJTC layers do. Their object id
    (`fid`, `objectid`) rides in `properties` and is their published id;
    `source_row` numbers a line only where that id is null
    (stg_nynjtc__long_path says why it is kept). -#}
{%- set staged_branches = [
    ('oprhp_trails', 'nysparks', 'stg_oprhp__trails', false),
    ('nynjtc_long_path', 'nynjtc', 'stg_nynjtc__long_path', true),
    ('nynjtc_highlands_trail', 'nynjtc', 'stg_nynjtc__highlands_trail', true),
    ('mohonk_trails', 'mohonk', 'stg_mohonk__trails', false),
] %}

with
{%- for source_key, club, model in base_branches %}
{{ source_key }}_json as (
    select
        json_extract_string(
            rows_as_json.row_json, '$.trail_segment_key'
        ) as trail_segment_key,
        rows_as_json.row_json
    from (
        select to_json(row_columns) as row_json
        from (
            select * exclude (geom, _loaded_at, _dlt_load_id, _dlt_id)
            from {{ ref(model) }}
        ) as row_columns
    ) as rows_as_json
),

{{ source_key }} as (
    select
        layer.trail_segment_key,
        '{{ source_key }}' as source_key,
        '{{ club }}' as club,
        row_json.row_json,
        layer.geom,
        cast(null as bigint) as source_row,
        layer._loaded_at
    from {{ ref(model) }} as layer
    inner join {{ source_key }}_json as row_json
        on layer.trail_segment_key = row_json.trail_segment_key
),
{%- endfor %}
{%- for source_key, club, model, ordered in staged_branches %}
{{ source_key }}_json as (
    select
        json_extract_string(
            rows_as_json.row_json, '$.trail_segment_key'
        ) as trail_segment_key,
        rows_as_json.row_json
    from (
        select to_json(row_columns) as row_json
        from (
            select * exclude (geom, loaded_at{{ ', source_row' if ordered }})
            from {{ ref(model) }}
        ) as row_columns
    ) as rows_as_json
),

{{ source_key }} as (
    select
        layer.trail_segment_key,
        '{{ source_key }}' as source_key,
        '{{ club }}' as club,
        row_json.row_json,
        layer.geom,
        {{ 'layer.source_row' if ordered else 'cast(null as bigint)' }}
            as source_row,
        layer.loaded_at as _loaded_at
    from {{ ref(model) }} as layer
    inner join {{ source_key }}_json as row_json
        on layer.trail_segment_key = row_json.trail_segment_key
),
{%- endfor %}

dec_hiking_trails_row as (
    select
        json_extract_string(
            rows_as_json.row_json, '$.trail_segment_key'
        ) as trail_segment_key,
        rows_as_json.row_json
    from (
        select to_json(row_columns) as row_json
        from (
            select * exclude (geom, loaded_at)
            from {{ ref('stg_dec__hiking_trails') }}
        ) as row_columns
    ) as rows_as_json
),

-- DEC's stg model renames its two id columns (OBJECTID as `source_id`,
-- GLOBALID as `stable_id`); they go back to their raw names here.
dec_hiking_trails_json as (
    select
        trail_segment_key,
        json_merge_patch(
            row_json,
            json_object(
                'objectid', json_extract(row_json, '$.source_id'),
                'globalid', json_extract(row_json, '$.stable_id'),
                'source_id', null,
                'stable_id', null
            )
        ) as row_json
    from dec_hiking_trails_row
),

dec_hiking_trails as (
    select
        layer.trail_segment_key,
        'dec_hiking_trails' as source_key,
        'nysdec' as club,
        row_json.row_json,
        layer.geom,
        cast(null as bigint) as source_row,
        layer.loaded_at as _loaded_at
    from {{ ref('stg_dec__hiking_trails') }} as layer
    inner join dec_hiking_trails_json as row_json
        on layer.trail_segment_key = row_json.trail_segment_key
),

unioned as (
    {%- for source_key, club, model in base_branches %}
    select * from {{ source_key }}
    union all by name
    {%- endfor %}
    {%- for source_key, club, model, ordered in staged_branches %}
    select * from {{ source_key }}
    union all by name
    {%- endfor %}
    select * from dec_hiking_trails
),

-- The staging key went into `row_json` with the other columns. It is not a
-- property any filter reads, so it comes out again.
keyless as (
    select
        * exclude (row_json),
        json_merge_patch(
            row_json, json_object('trail_segment_key', null)
        ) as properties
    from unioned
)

select
    trail_segment_key,
    source_key,
    club,
    properties,
    -- The row's place in its raw table, where the layer's stg model carries
    -- it: the order the Python numbers a feature with no id by.
    source_row,
    geom,
    _loaded_at
from keyless
