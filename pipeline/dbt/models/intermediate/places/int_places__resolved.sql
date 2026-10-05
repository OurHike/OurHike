{{ config(materialized='table', tags=['builds_alone']) }}
-- builds_alone: Out of Memory Error here in monthly run 20 (37296900535).
-- Not enough: alone in monthly run 21 (37323395441) it ran out at 12.4 GiB.
{#- The disc's radius in metres, multiplied as doubles, the way Python's
    `radius_miles * METERS_PER_MILE` multiplies (8046.72 at 5 miles). -#}
{%- set radius = var('places_trail_radius_miles') %}
{%- set radius_m = "cast(" ~ radius ~ " as double) * 1609.344::double" %}
{%- set threshold = var('trail_lines_network_named_trail_threshold_miles') %}
{#- The most vertices a measured piece of a polygon holds, and the most
    times one polygon is halved ("MEMORY" below). -#}
{%- set piece_vertices = 1024 %}
{%- set piece_halvings = 32 %}
-- Every row places.json publishes, measured, in file order:
-- export_places.py's load_named_trails(), measure() and the end of
-- build_output() (PL07-PL11). The places mart is this, typed.
--
-- PL07, long trails: every (source, name) whose published lines total at
-- least trail_lines_network_named_trail_threshold_miles (50, TL12's
-- NAMED_TRAIL_THRESHOLD_MILES, @unvalidated in export_nearby_trails.py's
-- own comment, which names a run on the live registry as what settles
-- it), summed by `trail_name` so the A.T. is one trail.
--
-- PL08, miles of published trail, in EPSG:5070 metres: for a park, the
-- lines inside its boundary; for a trailhead, parking area or town, the
-- lines within places_trail_radius_miles of its point (@unvalidated;
-- dbt_project.yml says what would settle it), through ST_Buffer's default
-- circle as measure() builds it; for a trail, its own length. Rounded to a
-- tenth with printf, as Python's round() rounds, never DuckDB's round(),
-- which differed from Python on 14,125 of 266,800 doubles at the half
-- (measured; int_trail_lines__network_published's header).
--
-- PL09, `within`: the park whose boundary contains the point; where two
-- do, the first in int_places__park_units' `unit_order`.
--
-- PL10: a trailhead or parking area with no published line near it is
-- dropped when anything was measured: a USFS trailhead in Arizona is not a
-- place this app can put a trail under. Decided on the metres, so eighty
-- metres of trail prints 0.0 and is kept. A town or park is never dropped:
-- "no trail data held" is true, and the row is what a hiker who lives
-- there should find.
--
-- PL11, no lines at all (an ordinary state: no steward's lines may publish
-- and the A.T. export has not run): nothing is measured, so `trail_miles`
-- is null and `trail_miles_measured` false on every row, never 0
-- everywhere, which would read as "no park holds any trail"; and nothing
-- is dropped for being far from a line.
--
-- THE CLUBS' PARKS AND TOWNS (decision 54's wave 1 places layers,
-- int_places__club_units, only those whose layer may publish) are measured
-- the same two ways: a club park by the lines inside its boundary, a club
-- town by the lines within the radius of its point. Each is kept whatever it
-- measures, as NY Parks' parks and the waypoint towns are. A club park is
-- never a `within`: a trailhead inside a national forest still reads the NY
-- Parks unit it is in, as today's file says, because a club park's layer is
-- not deduplicated against NY Parks' and the first-listed park would
-- otherwise turn on a layer's registry order. A club town carries no
-- `poi_id`: it is a place a hiker names, not a waypoint the app opens.
--
-- MEMORY: A POLYGON IS MEASURED IN PIECES. Built alone, this model still
-- ran out of its 12.4 GiB in monthly run 21 (37323395441: "failed to
-- allocate data of size 16.0 MiB" after 32 s). ST_Intersection holds each
-- row's polygon until its whole chunk of up to 2,048 rows is done, so the
-- join of many lines against one detailed park held that park once per
-- line. Measured 2026-10-05 on DuckDB 1.5.5's spatial: 999 lines against
-- one 50,001-vertex polygon peaked at 0.78 GiB (16.8 bytes a vertex a
-- row), where ST_Intersects on the same rows took 0.01 GiB. Which real
-- polygons did that in run 21 is unmeasured. So a park or club park of
-- more than `piece_vertices` vertices (set at the top) is halved across
-- its longer side, and each half again, until no piece has more
-- (polygon_pieces), and the lines are measured against the pieces: at
-- 1,024 a row holds at most about 17 kB of polygon, 35 MB for a chunk
-- (Reasoned, from the 16.8 bytes). That size is @unvalidated as the
-- fastest: picked to keep a chunk small, never timed on the real polygons;
-- a monthly build timed at 256, 1,024 and 4,096 would settle it. A park's
-- metres are the sum of its pieces' (Reasoned): a line crossing a cut is
-- measured on both sides of it, and only a stretch lying exactly along a
-- cut, which falls on the midpoint of a piece's EPSG:5070 box rather than
-- on anything surveyed, would count twice. A polygon of `piece_vertices`
-- vertices or fewer is one piece, measured exactly as before. The lines
-- are no longer held as a table carrying both their geometries
-- (`published` is read where it is used), and one spatial join measures
-- every kind of shape.
-- Measured 2026-10-05 on invented national-scale rows (332,630 lines,
-- 40,000 points, 300 parks, 8,000 club parks of 9.6 million vertices and
-- 1,000 club towns; 4 threads): peak 3.44 GiB before, 2.67 GiB after. With
-- one 245,141-vertex corridor park crossed by 8,000 more lines, the old
-- query failed under a 5 GB memory_limit with run 21's own error, and this
-- one peaked at 2.69 GiB, and built under a 2 GB limit too. On all 46,370
-- rows every column but trail_metres came out equal, trail_miles text
-- included, and trail_metres within 1.3e-14 relative. What the real
-- network peaks at is unmeasured until a monthly run builds it.
--
-- `lon`, `lat`, `bbox` and `trail_miles` are JSON text, cast back in the
-- places mart, because a dbt 2.0.6 unit test compares a DOUBLE only to one
-- decimal (.claude/skills/dbt/SKILL.md, "Contracts, and the traps in
-- them"). A park's and a trail's point and box are cut to 5 decimals, as
-- round(x, 5) cuts them.
with recursive parks as (
    select * from {{ ref('int_places__park_units') }}
),

points as (
    select * from {{ ref('int_places__point_places') }}
),

-- Read where each use needs it, never held: DuckDB materializes a CTE read
-- more than once, and the lines used to be held that way, carrying both
-- geometries of every line ("MEMORY" above).
published as not materialized (
    select * from {{ ref('int_places__lines') }}
),

measurement as (
    select count(*) > 0 as measured from published
),

trail_totals as (
    select
        source_key,
        trail_name,
        sum(
            st_length(
                st_transform(
                    geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
                )
            )
        ) as metres,
        st_extent_agg(geom) as extent,
        any_value(club) as club,
        max(_loaded_at) as _loaded_at
    from (
        select
            *,
            st_geomfromgeojson(geom_geojson) as geom
        from published
    ) as published_lines
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

point_within as (
    select
        point_shapes.place_id,
        arg_min(parks.name, parks.unit_order) as within_park
    from point_shapes
    inner join park_shapes on st_contains(park_shapes.geom, point_shapes.geom)
    inner join parks on park_shapes.place_id = parks.place_id
    group by point_shapes.place_id
),

club_units as (
    select * from {{ ref('int_places__club_units') }}
),

club_park_shapes as (
    select
        place_id,
        geom,
        st_centroid(geom) as centroid,
        st_extent(geom) as extent,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true) as g
    from (
        select
            place_id,
            st_geomfromtext(geom_wkt) as geom
        from club_units
        where kind = 'park'
    ) as club_park_geoms
),

club_town_shapes as (
    select
        place_id,
        geom,
        st_buffer(
            st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true),
            {{ radius_m }}
        ) as disc
    from (
        select
            place_id,
            st_geomfromtext(geom_wkt) as geom
        from club_units
        where kind = 'town'
    ) as club_town_geoms
),

-- Every park and club park polygon, cut into pieces ("MEMORY" above): a
-- piece of more than `piece_vertices` vertices is replaced by its two
-- halves, until none is or it has been halved `piece_halvings` times. GEOS
-- returns a half as it finds it, so a club park that is a collection keeps
-- its lines and points, as the uncut polygon measured them.
polygon_shapes as (
    select
        'park' as shape_kind,
        place_id,
        g as piece,
        0 as halvings
    from park_shapes
    union all
    select
        'club_park' as shape_kind,
        place_id,
        g as piece,
        0 as halvings
    from club_park_shapes
),

polygon_pieces as (
    select
        shape_kind,
        place_id,
        piece,
        halvings
    from polygon_shapes
    union all
    select
        halves.shape_kind,
        halves.place_id,
        st_intersection(
            halves.piece,
            st_makeenvelope(
                halves.west, halves.south, halves.east, halves.north
            )
        ) as piece,
        halves.halvings + 1 as halvings
    from (
        -- The two halves of a piece's box, 1 m wider on its outer sides so
        -- no cut meets the piece's own extreme vertices.
        select
            bounds.shape_kind,
            bounds.place_id,
            bounds.piece,
            bounds.halvings,
            case
                when bounds.wide and sides.side = 1
                    then (bounds.xmin + bounds.xmax) / 2
                else bounds.xmin - 1
            end as west,
            case
                when not bounds.wide and sides.side = 1
                    then (bounds.ymin + bounds.ymax) / 2
                else bounds.ymin - 1
            end as south,
            case
                when bounds.wide and sides.side = 0
                    then (bounds.xmin + bounds.xmax) / 2
                else bounds.xmax + 1
            end as east,
            case
                when not bounds.wide and sides.side = 0
                    then (bounds.ymin + bounds.ymax) / 2
                else bounds.ymax + 1
            end as north
        from (
            select
                polygon_pieces.*,
                st_xmin(polygon_pieces.piece) as xmin,
                st_ymin(polygon_pieces.piece) as ymin,
                st_xmax(polygon_pieces.piece) as xmax,
                st_ymax(polygon_pieces.piece) as ymax,
                st_xmax(polygon_pieces.piece) - st_xmin(polygon_pieces.piece)
                >= st_ymax(polygon_pieces.piece)
                - st_ymin(polygon_pieces.piece) as wide
            from polygon_pieces
            where
                st_npoints(polygon_pieces.piece) > {{ piece_vertices }}
                and polygon_pieces.halvings < {{ piece_halvings }}
        ) as bounds
        cross join (values (0), (1)) as sides (side)
    ) as halves
),

measured_pieces as (
    select
        shape_kind,
        place_id,
        piece
    from polygon_pieces
    where
        (
            st_npoints(piece) <= {{ piece_vertices }}
            or halvings >= {{ piece_halvings }}
        )
        and not st_isempty(piece)
),

-- Every shape in one join: the parks' and club parks' pieces, the points'
-- discs and the club towns' discs, each named by its kind, so a park's id
-- and a waypoint's can never meet. The lines come in as bare EPSG:5070
-- geometry.
measured_shapes as (
    select
        shape_kind,
        place_id,
        piece as shape
    from measured_pieces
    union all
    select
        'point' as shape_kind,
        place_id,
        disc as shape
    from point_shapes
    union all
    select
        'club_town' as shape_kind,
        place_id,
        disc as shape
    from club_town_shapes
),

lines as (
    select
        st_transform(
            st_geomfromgeojson(geom_geojson),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as g
    from published
),

shape_metres as (
    select
        measured_shapes.shape_kind,
        measured_shapes.place_id,
        sum(st_length(st_intersection(lines.g, measured_shapes.shape)))
            as metres
    from measured_shapes
    inner join lines on st_intersects(lines.g, measured_shapes.shape)
    group by measured_shapes.shape_kind, measured_shapes.place_id
),

park_metres as (
    select
        place_id,
        metres
    from shape_metres
    where shape_kind = 'park'
),

point_metres as (
    select
        place_id,
        metres
    from shape_metres
    where shape_kind = 'point'
),

club_park_metres as (
    select
        place_id,
        metres
    from shape_metres
    where shape_kind = 'club_park'
),

club_town_metres as (
    select
        place_id,
        metres
    from shape_metres
    where shape_kind = 'club_town'
),

club_places as (
    select
        club_units.place_id,
        club_units.name,
        club_units.kind,
        cast(null as varchar) as poi_id,
        club_units.category,
        club_units.state,
        cast(null as varchar) as within_park,
        cast(
            printf(
                '%.5f',
                st_x(coalesce(club_park_shapes.centroid, club_town_shapes.geom))
            ) as double
        ) as lon,
        cast(
            printf(
                '%.5f',
                st_y(coalesce(club_park_shapes.centroid, club_town_shapes.geom))
            ) as double
        ) as lat,
        case
            when club_units.kind = 'park'
                then [
                    cast(
                        printf('%.5f', st_xmin(club_park_shapes.extent))
                        as double
                    ),
                    cast(
                        printf('%.5f', st_ymin(club_park_shapes.extent))
                        as double
                    ),
                    cast(
                        printf('%.5f', st_xmax(club_park_shapes.extent))
                        as double
                    ),
                    cast(
                        printf('%.5f', st_ymax(club_park_shapes.extent))
                        as double
                    )
                ]
        end as bbox,
        coalesce(club_park_metres.metres, club_town_metres.metres, 0)
            as metres,
        club_units.source_key as source,
        club_units.club,
        club_units.source_key,
        club_units._loaded_at
    from club_units
    left join club_park_shapes
        on club_units.place_id = club_park_shapes.place_id
    left join club_park_metres
        on club_units.place_id = club_park_metres.place_id
    left join club_town_shapes
        on club_units.place_id = club_town_shapes.place_id
    left join club_town_metres
        on club_units.place_id = club_town_metres.place_id
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
    union all
    select * from club_places
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
