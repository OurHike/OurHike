{{ config(materialized='table') }}
-- Each A.T.-family POI's NOBO mile from Springer, on the same
-- marker-calibrated axis the elevation profile is sampled along (PO11,
-- export_poi.py's attach_miles(), #753, #652). A position, never a heading.
-- One row per poi_by_type POI that gets a mile.
--
-- How the mile is read off int_trail_lines__mile_axis, step for step with
-- attach_miles() and the order that model's comment gives a consumer:
-- 1. the point in EPSG:5070 metres, transformed with always_xy, as
--    _reproject_points_to_meters() transforms it;
-- 2. the nearest piece by st_distance, a tie going to the lower piece_id,
--    where shapely's STRtree.nearest() returns one of the tied pieces;
-- 3. how far along that piece the point projects, in miles: the located
--    fraction times the piece's length, over the international mile (the
--    Python's line.project(), then CalibratedPart.mile_at()'s division);
-- 4. the mile there, mile_at_along(): unit slope before the first anchor
--    and past the last, interpolated between, as np.interp is;
-- 5. three decimals, rounded as Python's round() rounds (python_round(),
--    which DuckDB's round() is not: they disagree on 59,050 of 517,613
--    doubles, measured 2026-10-01).
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

axis as (
    select * from {{ ref('int_trail_lines__mile_axis') }}
),

nearest as (
    select
        points.poi_id,
        points.point_5070,
        axis.piece_id,
        axis.geom_5070,
        axis.length_m,
        axis.anchor_along_mi,
        axis.anchor_mile,
        row_number() over (
            partition by points.poi_id
            order by
                st_distance(axis.geom_5070, points.point_5070), axis.piece_id
        ) as pick
    from points
    cross join axis
),

along as (
    select
        poi_id,
        piece_id,
        anchor_along_mi,
        anchor_mile,
        st_linelocatepoint(geom_5070, point_5070)
        * length_m
        / {{ var('mile_axis_metres_per_mile') }} as along_mi
    from nearest
    where pick = 1
),

placed as (
    select
        poi_id,
        piece_id,
        {{ mile_at_along('along_mi', 'anchor_along_mi', 'anchor_mile') }}
            as unrounded_mile
    from along
)

select
    poi_id,
    piece_id as mile_piece_id,
    printf('%.3f', unrounded_mile) as mile
from placed
