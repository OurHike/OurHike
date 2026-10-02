{{ config(materialized='table') }}
{#- The disc's radius in metres, multiplied as doubles, the way Python's
    `radius_miles * METERS_PER_MILE` multiplies (8046.72 at 5 miles). -#}
{%- set radius = var('places_trail_radius_miles') %}
{%- set radius_m = "cast(" ~ radius ~ " as double) * 1609.344::double" %}
{%- set threshold = var('trail_lines_network_named_trail_threshold_miles') %}
-- Every row places.json publishes, measured and in the file's order:
-- export_places.py's load_named_trails(), measure() and the end of
-- build_output() in SQL (PL07-PL11), in their order. The mart is this, typed.
--
-- PL07, THE LONG TRAILS. Every (source, name) whose published lines total
-- at least trail_lines_network_named_trail_threshold_miles (TL12's 50 miles,
-- export_nearby_trails.py's NAMED_TRAIL_THRESHOLD_MILES, @unvalidated in its
-- own comment, which names a run on the live registry as what settles it),
-- summed under int_places__lines' `trail_name`, so the A.T. is one trail.
-- A trail centres on its box's middle and carries the box.
--
-- PL08, MILES OF PUBLISHED TRAIL, measured in EPSG:5070 metres:
-- - a park: the length of every published line inside its boundary;
-- - a trailhead, parking area or town: the length within
--   places_trail_radius_miles of its point, through a buffer of the point
--   (ST_Buffer's default of 8 segments a quarter, as export_places.py's
--   measure() builds it). The radius is @unvalidated: dbt_project.yml says
--   what would settle it;
-- - a trail: its own length.
-- Rounded to a tenth, as Python's round() rounds: the printf cut, never
-- DuckDB's round(), which differed from Python on 14,125 of 266,800 doubles
-- at the half (the tl-net worker's measurement in
-- int_trail_lines__network_published's header).
--
-- PL09, `within`: the park a point sits in, by name, where its boundary
-- contains the point; where two do, the first in int_places__park_units'
-- `unit_order`, as measure()'s min(idx) takes it.
--
-- PL10, A TRAILHEAD OR PARKING AREA WITH NO PUBLISHED LINE NEAR IT IS
-- DROPPED, when anything was measured: a USFS trailhead in Arizona is not a
-- place this app can put a trail under. Decided on the metres, not the
-- rounded figure: eighty metres of trail prints 0.0 and is kept. A town and
-- a park are never dropped: "no trail data held" is a true sentence and the
-- row a hiker who lives there should find.
--
-- PL11, NO LINES AT ALL: nothing is measured, `trail_miles` is null on
-- every row and `trail_miles_measured` false, never 0 on every row. That
-- state is ordinary (the licence gate holding every steward's lines back and
-- the A.T. export not run), and it must not read as "no park holds any
-- trail"; with nothing to measure, nothing is dropped for being far from it.
--
-- MUST-MATCH NUMBERS ARE TEXT HERE: `lon`, `lat`, `bbox` and `trail_miles`
-- are their JSON text, which the places mart casts back, because a dbt 2.0.6
-- unit test compares a DOUBLE only after rounding it to one decimal place
-- (.claude/skills/dbt/SKILL.md, "Contracts, and the traps in them"). A park's
-- and a trail's point and box are cut to 5 decimals, as round(x, 5) cuts
-- them; a waypoint's point is the published one, uncut.
with parks as (
    select * from {{ ref('int_places__park_units') }}
),

points as (
    select * from {{ ref('int_places__point_places') }}
),

lines as (
    select
        source_key,
        club,
        _loaded_at,
        trail_name,
        geom,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true) as g
    from (
        select
            *,
            st_geomfromgeojson(geom_geojson) as geom
        from {{ ref('int_places__lines') }}
    ) as published
),

measurement as (
    select count(*) > 0 as measured from lines
),

trail_totals as (
    select
        source_key,
        trail_name,
        sum(st_length(g)) as metres,
        st_extent_agg(geom) as extent,
        any_value(club) as club,
        max(_loaded_at) as _loaded_at
    from lines
    group by source_key, trail_name
),

trail_boxes as (
    select
        *,
        cast(printf('%.5f', st_xmin(extent)) as double) as west,
        cast(printf('%.5f', st_ymin(extent)) as double) as south,
        cast(printf('%.5f', st_xmax(extent)) as double) as east,
        cast(printf('%.5f', st_ymax(extent)) as double) as north
    from trail_totals
    where
        nullif({{ python_strip('trail_name') }}, '') is not null
        and metres / 1609.344 >= {{ threshold }}
),

park_shapes as (
    select
        place_id,
        geom,
        st_centroid(geom) as centroid,
        st_extent(geom) as extent,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true) as g
    from (
        select
            place_id,
            st_geomfromtext(park_wkt) as geom
        from parks
    ) as unit_shapes
),

park_metres as (
    select
        park_shapes.place_id,
        sum(st_length(st_intersection(lines.g, park_shapes.g))) as metres
    from park_shapes
    inner join lines on st_intersects(lines.g, park_shapes.g)
    group by park_shapes.place_id
),

point_shapes as (
    select
        place_id,
        st_point(lon, lat) as geom,
        st_buffer(
            st_transform(
                st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
            ),
            {{ radius_m }}
        ) as disc
    from points
),

point_metres as (
    select
        point_shapes.place_id,
        sum(st_length(st_intersection(lines.g, point_shapes.disc))) as metres
    from point_shapes
    inner join lines on st_intersects(lines.g, point_shapes.disc)
    group by point_shapes.place_id
),

point_within as (
    select
        point_shapes.place_id,
        arg_min(parks.name, parks.unit_order) as within_park
    from point_shapes
    inner join park_shapes on st_contains(park_shapes.geom, point_shapes.geom)
    inner join parks on park_shapes.place_id = parks.place_id
    group by point_shapes.place_id
),

park_places as (
    select
        parks.place_id,
        parks.name,
        'park' as kind,
        cast(null as varchar) as poi_id,
        parks.category,
        parks.state,
        cast(null as varchar) as within_park,
        cast(printf('%.5f', st_x(park_shapes.centroid)) as double) as lon,
        cast(printf('%.5f', st_y(park_shapes.centroid)) as double) as lat,
        [
            cast(printf('%.5f', st_xmin(park_shapes.extent)) as double),
            cast(printf('%.5f', st_ymin(park_shapes.extent)) as double),
            cast(printf('%.5f', st_xmax(park_shapes.extent)) as double),
            cast(printf('%.5f', st_ymax(park_shapes.extent)) as double)
        ] as bbox,
        coalesce(park_metres.metres, 0) as metres,
        parks.source_key as source,
        parks.club,
        parks.source_key,
        parks._loaded_at
    from parks
    inner join park_shapes on parks.place_id = park_shapes.place_id
    left join park_metres on parks.place_id = park_metres.place_id
),

point_rows as (
    select
        points.place_id,
        points.name,
        points.kind,
        points.poi_id,
        cast(null as varchar) as category,
        points.state,
        point_within.within_park,
        points.lon,
        points.lat,
        cast(null as double[]) as bbox,
        coalesce(point_metres.metres, 0) as metres,
        points.source,
        points.club,
        points.source_key,
        points._loaded_at
    from points
    left join point_metres on points.place_id = point_metres.place_id
    left join point_within on points.place_id = point_within.place_id
),

trail_rows as (
    select
        'trail:' || source_key || ':' || trail_name as place_id,
        trail_name as name,
        'trail' as kind,
        cast(null as varchar) as poi_id,
        cast(null as varchar) as category,
        cast(null as varchar) as state,
        cast(null as varchar) as within_park,
        cast(printf('%.5f', (west + east) / 2) as double) as lon,
        cast(printf('%.5f', (south + north) / 2) as double) as lat,
        [west, south, east, north] as bbox,
        metres,
        source_key as source,
        club,
        source_key,
        _loaded_at
    from trail_boxes
),

all_places as (
    select * from park_places
    union all
    select * from point_rows
    union all
    select * from trail_rows
),

kept as (
    select
        all_places.*,
        measurement.measured
    from all_places
    cross join measurement
    where
        not (
            measurement.measured
            and all_places.kind in ('trailhead', 'parking')
            and all_places.metres = 0
        )
)

select
    place_id,
    row_number() over (order by kind, name, place_id) as place_order,
    kind,
    name,
    poi_id,
    category,
    state,
    within_park,
    cast(to_json(lon) as varchar) as lon,
    cast(to_json(lat) as varchar) as lat,
    cast(to_json(bbox) as varchar) as bbox,
    case when measured then metres end as trail_metres,
    case
        when measured
            then
                cast(
                    to_json(cast(printf('%.1f', metres / 1609.344) as double))
                    as varchar
                )
    end as trail_miles,
    measured as trail_miles_measured,
    source,
    club,
    source_key,
    _loaded_at
from kept
