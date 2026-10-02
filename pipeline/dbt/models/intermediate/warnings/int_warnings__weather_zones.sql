-- Every NWS zone the weather squares know, one row each, as
-- export_weather_alerts.py's bake() reads squares.json (WN03):
--   squares     the trail squares the zone's outline overlaps (its `zones`
--               entry, `by_zone`), [] for a zone that reaches no trail
--   is_known    the zone is in the zone files build_weather_squares.py
--               pinned (`known_zones`), which is what tells "a zone nowhere
--               near a trail" from "a zone those files have never heard of"
--
-- A zone is "<kind>/<id>": forecast, fire or county, then NWS's id. The kind
-- matters: forecast zone NHZ010 and fire weather zone NHZ010 are different
-- outlines under one id (export_weather_alerts.py's zone_keys()).
with squares_documents as (
    select * from {{ ref('stg_derived__weather_squares') }}
),

-- Each part of the document is read once, as a map: a JSON path per zone
-- re-reads the whole document for each one, which took 34 s for 615 zones
-- on a 26,103-square document (measured 2026-10-02, DuckDB 1.5.5).
maps as (
    select
        release,
        cast(json_extract(squares_document, '$.zones') as map (varchar, json))
            as zone_map,
        cast(
            json_extract(squares_document, '$.known_zones')
            as map (varchar, varchar[])
        ) as known_map
    from squares_documents
),

-- `zones`: each zone that overlaps a trail square, and those squares.
zone_squares as (
    select
        release,
        unnest(map_keys(zone_map)) as zone_key,
        unnest(map_values(zone_map)) as squares
    from maps
),

-- `known_zones`: every id each pinned file holds, trail or not.
kinds as (
    select
        release,
        unnest(map_keys(known_map)) as zone_kind,
        unnest(map_values(known_map)) as zone_ids
    from maps
),

known_ids as (
    select
        release,
        zone_kind,
        unnest(zone_ids) as zone_id
    from kinds
),

known as (
    select distinct
        release,
        zone_kind || '/' || zone_id as zone_key
    from known_ids
),

zones as (
    select
        coalesce(zone_squares.release, known.release) as squares_release,
        coalesce(zone_squares.zone_key, known.zone_key) as zone_key,
        coalesce(zone_squares.squares, cast('[]' as json)) as squares,
        known.zone_key is not null as is_known
    from zone_squares
    full outer join known
        on
            zone_squares.release = known.release
            and zone_squares.zone_key = known.zone_key
)

select
    {{ dbt_utils.generate_surrogate_key(['squares_release', 'zone_key']) }}
        as weather_zone_key,
    squares_release,
    zone_key,
    split_part(zone_key, '/', 1) as zone_kind,
    split_part(zone_key, '/', 2) as zone_id,
    squares,
    is_known
from zones
