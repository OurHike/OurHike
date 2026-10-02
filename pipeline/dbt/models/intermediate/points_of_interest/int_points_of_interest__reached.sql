{{ config(materialized='table') }}
-- The POIs in their file's ground that a hiker could reach (PO08, PO10):
-- export_poi.py's gate_osm_water_reach() and mark_off_trail_records(), in
-- read_sources()' order, after the corridor clip. Every row that is not OSM
-- water passes unchanged; nothing else is gated on reach.
--
-- AN OSM WATER POINT SHIPS ONLY WITH A VERDICT THAT SAYS REACHABLE. A point
-- with no verdict is dropped, and that is the safe direction rather than an
-- oversight (gate_osm_water_reach(), #749 — OSM water points are published
-- anywhere in the 30-mile corridor, so a pin promises water a hiker cannot
-- reach): an OSM node nobody has judged is one nobody has checked a hiker
-- can walk to. The Python reaches that state when osm_water.geojson grows
-- without build_osm_water_reach.py being re-run; here the verdicts
-- (int_points_of_interest__osm_water_verdicts) are taken in the same build
-- as the points, so a missing one means step_osm_water_grade and
-- int_points_of_interest__osm_water_reach disagree, which
-- assert_every_corridor_osm_water_point_has_a_verdict fails the build on.
-- "No verdict file, so stop" (read_sources()' SystemExit) has no
-- equivalent to port: build_marts.py runs the step before this model or not
-- at all.
--
-- THE MARK (PO10): a reachable OSM point whose nearest walk is another
-- organization's published trail carries that organization's key as
-- `not_on_at`, which withholds its A.T. mile (int_points_of_interest__miles).
-- load_osm_water_network_anchors() reads it off the verdicts' `nearest_source`
-- for reachable points only, and so does this.
with in_corridor as (
    select * from {{ ref('int_points_of_interest__in_corridor') }}
),

verdicts as (
    select
        poi_key,
        nearest,
        nearest_source,
        reachable
    from {{ ref('int_points_of_interest__osm_water_verdicts') }}
),

judged as (
    select
        in_corridor.*,
        coalesce(verdicts.reachable, false) as is_reachable,
        case
            when verdicts.reachable and verdicts.nearest = 'network_trail'
                then verdicts.nearest_source
        end as anchor
    from in_corridor
    left join verdicts on in_corridor.poi_key = verdicts.poi_key
)

select
    * exclude (is_reachable, anchor),
    -- mark_off_trail_records(): only OSM water is ever marked.
    case when source_key = 'osm_water' then anchor end as not_on_at
from judged
where source_key != 'osm_water' or is_reachable
