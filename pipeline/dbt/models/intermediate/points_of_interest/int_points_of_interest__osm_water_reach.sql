{{ config(materialized='table') }}
{%- set radius_m =
    "cast(" ~ var('poi_water_match_radius_ft') ~ " as double) * "
    ~ var('poi_metres_per_foot') %}
{%- set ceiling_m = var('poi_osm_water_measure_ceiling_m') %}
-- The distance half of OSM water's reach (PO06): for every OSM water point
-- inside the corridor, the nearest thing a hiker could be walking from, and
-- whether it is within MATCH_RADIUS_FT of it. build_osm_water_reach.py's
-- measure_distances(), and its constants: the radius is
-- fetch_trail_water.py's MATCH_RADIUS_FT (var `poi_water_match_radius_ft`,
-- 100 ft), the one judgement both water gates share; the ceiling is
-- MEASURE_CEILING_M (var `poi_osm_water_measure_ceiling_m`, 5 mi), a
-- reporting limit and the join's radius, never a gate.
--
-- WHAT A HIKER COULD BE WALKING FROM is a union of four, and a point passes
-- on whichever is closest: the centerline, ATC's side trails, every
-- published network line whose organization reaches hikers
-- (export_nearby_trails.shipped_line_source_keys(): water derived from a
-- trail nobody may publish would be that organization's data reaching a
-- hiker), and a shelter or campsite. Which one won is reported and never
-- changes the gate. OSM's own path network is never in it.
--
-- THE TIE-BREAK IS THE PYTHON'S ORDER: nearest first, and between equal
-- distances centerline, then side trail, then network trail, then site, the
-- order measure_distances() builds its `found` dict in and min() keeps the
-- first of. Inside one layer the Python's arg_min() keeps whichever equal row
-- DuckDB reads first; this keeps the lowest source key and then the lowest
-- point, which can name a different organization only where two
-- organizations' lines lie at exactly the same distance (Reasoned: both
-- answers are network lines, so the not_on_at mark and the missing mile are
-- the same; the organization's name is not published).
--
-- Distances are EPSG:5070 metres from ST_Distance, the Python's own measure
-- (ELT.md's geometry rules). `nearest_m` is the distance at 2 dp as text,
-- what measure_distances() records and the grade's run is read from;
-- `walk_key` is the other end of the walk as the EPQS cache keys it, so a
-- unit test can hold both exactly. The grade is step_osm_water_grade's.
with water as (
    select
        poi_key,
        source_feature_id as osm_id,
        lon,
        lat,
        st_transform(
            st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as point_5070
    from {{ ref('int_points_of_interest__in_corridor') }}
    where source_key = 'osm_water'
),

shipped as (
    select source_key
    from {{ ref('stg_registry__sources') }}
    where reaches_hikers
),

lines as (
    select
        1 as priority,
        'centerline' as nearest,
        cast(null as varchar) as line_source,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
            as geom_5070
    from {{ ref('stg_atc__centerline_segments') }}
    where geom is not null
    union all
    select
        2 as priority,
        'side_trail' as nearest,
        cast(null as varchar) as line_source,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
            as geom_5070
    from {{ ref('stg_atc__side_trails') }}
    where geom is not null
    union all
    select
        3 as priority,
        'network_trail' as nearest,
        network.source_key as line_source,
        st_transform(
            st_geomfromgeojson(network.geom_geojson),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as geom_5070
    from {{ ref('int_trail_lines__network_published') }} as network
    inner join shipped on network.source_key = shipped.source_key
),

sites as (
    select
        4 as priority,
        -- measure_distances() reports a site by its kind, singular.
        case layer when 'shelters' then 'shelter' else 'campsite' end
            as nearest,
        cast(null as varchar) as line_source,
        st_transform(
            st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as geom_5070
    from {{ ref('int_points_of_interest__water_sites') }}
),

candidates as (
    select
        water.poi_key,
        lines.priority,
        lines.nearest,
        lines.line_source,
        st_distance(water.point_5070, lines.geom_5070) as distance_m,
        st_closestpoint(lines.geom_5070, water.point_5070) as walk_5070
    from water
    inner join lines
        on st_dwithin(water.point_5070, lines.geom_5070, {{ ceiling_m }})
    union all
    select
        water.poi_key,
        sites.priority,
        sites.nearest,
        sites.line_source,
        st_distance(water.point_5070, sites.geom_5070) as distance_m,
        sites.geom_5070 as walk_5070
    from water
    inner join sites
        on st_dwithin(water.point_5070, sites.geom_5070, {{ ceiling_m }})
),

nearest as (
    select
        poi_key,
        nearest,
        line_source,
        distance_m,
        st_transform(walk_5070, 'EPSG:5070', 'EPSG:4326', always_xy := true)
            as walk_geom
    from candidates
    where distance_m <= {{ ceiling_m }}
    qualify row_number() over (
        partition by poi_key
        order by
            distance_m,
            priority,
            line_source,
            st_x(walk_5070),
            st_y(walk_5070)
    ) = 1
)

select
    water.poi_key,
    water.osm_id,
    water.lon,
    water.lat,
    nearest.nearest,
    nearest.line_source as nearest_source,
    printf('%.2f', nearest.distance_m) as nearest_m,
    st_x(nearest.walk_geom) as walk_lon,
    st_y(nearest.walk_geom) as walk_lat,
    printf('%.6f,%.6f', st_y(nearest.walk_geom), st_x(nearest.walk_geom))
        as walk_key,
    coalesce(nearest.distance_m <= {{ radius_m }}, false) as passes_distance,
    case
        when nearest.poi_key is null
            then
                'no trail, side trail, network trail, shelter or campsite '
                || 'within '
                || printf('%.0f', {{ ceiling_m }} / 1609.344)
                || ' miles'
        when nearest.distance_m > {{ radius_m }}
            then
                'the nearest '
                || replace(nearest.nearest, '_', ' ')
                || ' is '
                || printf(
                    '%.0f',
                    nearest.distance_m / {{ var('poi_metres_per_foot') }}
                )
                || ' ft away, past the '
                || printf('%.0f', {{ var('poi_water_match_radius_ft') }})
                || ' ft a hiker walks for water'
    end as reason
from water
left join nearest on water.poi_key = nearest.poi_key
