{{ config(materialized='table') }}
-- Each junction-graph edge's samples with the DEM's answer at each, in metres
-- and in the whole feet trail_graph_profile.json publishes: one row per row of
-- int_elevation__edge_sample_points. EL12 of pipeline/ELT.md's ledger, the
-- SQL form of export_network_profile.edge_profile's rounding.
--
-- WHOLE FEET, as the Python rounds them: the DEM's metres over
-- elevation_metres_per_foot, rounded once, from the unrounded metres, as
-- Python's round() rounds (the double's own value, ties to even), which is
-- printf('%.0f') (int_elevation__edge_sample_points has the measurement).
-- Never from a tenth of a foot first: rounding twice moves a value that
-- rounds to x.5 at one decimal off its own nearest foot. export_network_
-- profile.py says why whole feet and not tenths (3DEP's ~0.5 m sample-to-
-- sample error is 1.6 ft).
--
-- A DEM GAP IS NULL, NEVER 0, and keeps its place in the edge's samples, so
-- the distance a chart derives from the array's length stays true.
--
-- A SAMPLE THE DEM WAS NOT READ FOR HAS NO ELEVATION HERE: the join needs the
-- line, the sample and the point itself to match, as int_elevation__profile's
-- does, and assert_every_elevation_sample_was_read_at_its_own_point fails the
-- build on any point of int_elevation__dem_points the step did not read at
-- that point.
with points as (
    select * from {{ ref('int_elevation__edge_sample_points') }}
),

dem as (
    select * from {{ ref('stg_derived__dem_samples') }}
)

select
    points.edge_id,
    points.edge_index,
    points.sample_index,
    dem.elevation_m,
    -- printf of a null is null, so a gap stays one.
    cast(
        printf(
            '%.0f',
            dem.elevation_m
            / cast('{{ var("elevation_metres_per_foot") }}' as double)
        ) as integer
    ) as elevation_ft
from points
left join dem
    on
        points.edge_id = dem.line_id
        and points.sample_index = dem.sample_index
        and points.lon = dem.lon
        and points.lat = dem.lat
