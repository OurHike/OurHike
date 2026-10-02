{{ config(materialized='table') }}
-- Each A.T.-family POI's NOBO mile from Springer, on the same
-- marker-calibrated axis the elevation profile is sampled along (PO11,
-- export_poi.py's attach_miles(); #753 — Publish a mile on every POI, because
-- this codebase measures a mile two different ways and a plan cannot survive
-- that; #652 — The elevation profile's mile axis is out of order in 18
-- places, by up to 46 miles). A position, never a heading. One row per
-- poi_by_type POI that gets a mile.
--
-- The mile is read off int_trail_lines__mile_axis by the axis_mile() macro,
-- the trail_lines family's one rule for every reader of the axis
-- (macros/axis_mile.sql says each step and what it rests on): the point in
-- EPSG:5070 metres, transformed with always_xy as
-- _reproject_points_to_meters() transforms it; its nearest piece, a tie
-- going to the piece the point does not end on and then to the lower id
-- (@unvalidated against STRtree's own tie order beyond the one junction the
-- trail_lines family measured); how far along it the point projects; and
-- the mile there, interpolated between ATC's half-mile markers. Then three
-- decimals, cut as Python's round() cuts: printf('%.3f'), which agreed with
-- Python's round(x, 3) on all 517,613 doubles tried, where DuckDB's round()
-- disagreed on 59,050 (measured 2026-10-01).
--
-- A POI on another organization's trail gets no mile (PO10): attach_miles()
-- "always succeeds - there is no distance at which it declines", so the
-- refusal is the not_on_at mark set upstream, never inferred from the
-- result. A point four miles off the A.T. would otherwise carry a perfectly
-- formed mile, and the day planner treats every POI with a mile as a stop
-- on an A.T. day. Null on every row today
-- (int_points_of_interest__in_corridor).
--
-- `mile` is TEXT here, the three-decimal string, so a unit test can hold it
-- exactly: a dbt 2.0.6 unit test compares a double only to one decimal
-- place (.claude/skills/dbt/SKILL.md, "Contracts, and the traps in them").
-- The points_of_interest mart casts it back to a double, which is the same
-- double Python's round(mile, 3) gives.
with points as (
    select
        poi_id,
        st_transform(
            st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as point_5070
    from {{ ref('int_points_of_interest__enriched') }}
    where
        phone_files = 'poi_by_type'
        and not_on_at is null
),

located as {{ axis_mile('points', ['poi_id'], 'point_5070') }}

select
    poi_id,
    piece_id as mile_piece_id,
    printf('%.3f', mile) as mile
from located
