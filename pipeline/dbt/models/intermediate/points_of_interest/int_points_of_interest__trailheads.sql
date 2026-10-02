{{ config(materialized='table') }}
{%- set radius = var('poi_trailhead_trail_radius_m') %}
-- Each of the other organizations' trailheads, and whether every trail line
-- near it is closed (PO34, export_nearby_poi.py's mark_closed_trailheads(),
-- #1695 — Draw a trailhead whose trails are all closed with a ✕). One row per
-- trailhead that ships.
--
-- A hiker reads this: the phone draws such a trailhead in the closure's ink
-- with a white cross, and its card says how near the closed trails are
-- (client/src/lib/trailData.ts's trailsClosedWithinM, chrome/PoiCard.tsx).
-- So `trails_closed_within_m` is set to var `poi_trailhead_trail_radius_m`
-- (TRAILHEAD_TRAIL_RADIUS_M, 100 m: nothing in any layer says which trails a
-- trailhead serves, so "its trails" is every line within it) only where at
-- least one line is that near and every one of them is closed.
--
-- MISS RATHER THAN CRY WOLF, and every uncertain state goes that way, as in
-- the Python. The lines are the published network
-- (int_trail_lines__network_published), each closed where its trail_status
-- reads `closed` and open on anything else, a missing status included, plus
-- the A.T.'s own centerline and side trails, which nearby_trails.geojson does
-- not carry and which count as open lines: so a trailhead beside the open
-- A.T. and a closed side path is not marked. A trailhead with no line within
-- the radius is not marked either: "no trail here" is not "every trail here
-- is closed". The near test is the Python's: each line intersecting the
-- trailhead buffered by the radius in EPSG:5070 metres.
with trailheads as (
    select
        poi_id,
        st_transform(
            st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as point_5070
    from {{ ref('int_points_of_interest__identified') }}
    where
        phone_files = 'nearby_poi'
        and poi_type = 'trailhead'
),

network_lines as (
    select
        st_transform(
            st_geomfromgeojson(geom_geojson),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as geom_5070,
        lower(coalesce(cast(trail_status as varchar), '')) = 'closed' as closed
    from {{ ref('int_trail_lines__network_published') }}
),

at_lines as (
    select
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
            as geom_5070,
        false as closed
    from {{ ref('stg_atc__centerline_segments') }}
    where geom is not null
    union all
    select
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
            as geom_5070,
        false as closed
    from {{ ref('stg_atc__side_trails') }}
    where geom is not null
),

lines as (
    select * from network_lines
    union all
    select * from at_lines
),

near as (
    select
        trailheads.poi_id,
        count(*) as line_count,
        count(*) filter (where lines.closed) as closed_count
    from trailheads
    inner join lines
        on st_intersects(
            lines.geom_5070, st_buffer(trailheads.point_5070, {{ radius }})
        )
    group by trailheads.poi_id
)

select
    trailheads.poi_id,
    coalesce(near.line_count, 0) as lines_within_radius,
    coalesce(near.closed_count, 0) as closed_lines_within_radius,
    case
        when near.line_count > 0 and near.closed_count = near.line_count
            then {{ radius }}
    end as trails_closed_within_m
from trailheads
left join near on trailheads.poi_id = near.poi_id
