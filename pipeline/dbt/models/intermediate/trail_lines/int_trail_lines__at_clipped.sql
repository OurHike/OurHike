{{ config(materialized='table') }}
-- The A.T.'s line features that touch the corridor (TL14),
-- export_trails.clip_to_corridor(): a feature is kept whole when any part of
-- its full-resolution line intersects int_trail_lines__corridor, and never
-- cut down to the boundary. It runs before the 1 m pass, so a feature can
-- never be excluded because simplification moved it. Only features with a
-- line geometry reach it (TL04).
with features as (
    select * from {{ ref('int_trail_lines__at_features') }}
),

corridor as (
    select geom as corridor_geom from {{ ref('int_trail_lines__corridor') }}
)

select features.*
from features
cross join corridor
where
    features.has_line_geometry
    and st_intersects(
        st_geomfromtext(features.geom_wkt), corridor.corridor_geom
    )
