{{ config(materialized='table') }}
-- The reached POIs less OSM's twins of opentrail's water (PO09):
-- export_poi.py's dedupe_water(), after the reach gate as read_sources()
-- runs it. An OSM water point within WATER_DEDUP_RADIUS_M (var
-- `poi_water_dedup_radius_m`, 25 m) of any opentrail water point is dropped,
-- measured with lib/spurs.py's distance_m() (macro poi_distance_m), as the
-- Python measures it. The radius's measurement is on the Python constant
-- (2026-08-13: 41 of 174 opentrail water points have an OSM node within
-- 25 m, then the tail thins to real neighbours).
--
-- DIRECTION IS FIXED, NOT NEAREST-WINS: the opentrail point keeps its
-- published id, so a Report filed against it stays attached. Only an OSM
-- point is ever dropped, and only against opentrail's water, whatever its
-- confidence.
with reached as (
    select * from {{ ref('int_points_of_interest__reached') }}
),

opentrail_water as (
    select
        lon,
        lat
    from reached
    where source_key = 'opentrail_at' and poi_type = 'water'
),

twins as (
    select distinct reached.poi_key
    from reached
    inner join opentrail_water
        on {{ poi_distance_m(
            'reached.lat', 'reached.lon',
            'opentrail_water.lat', 'opentrail_water.lon'
        ) }} <= {{ var('poi_water_dedup_radius_m') }}
    where reached.source_key = 'osm_water' and reached.poi_type = 'water'
)

select reached.*
from reached
where reached.poi_key not in (select twins.poi_key from twins)
