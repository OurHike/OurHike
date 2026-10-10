{{ config(materialized='table') }}
{%- set decimals = var('trail_lines_network_overview_seam_decimals') %}
-- network_overview.geojson's features, one row per group, as
-- write_overview() builds them from the lines left after the floor and the
-- seam's pass (int_trail_lines__network_overview_seam). pub_network_overview
-- wraps them into the file.
--
-- ONE FEATURE PER (source, through route, blaze_color, trail_status), every
-- line of the group one part of a MultiLineString at OVERVIEW_SEAM_DECIMALS,
-- three, cut as Python's round() cuts (the printf cast;
-- int_trail_lines__network_published says why it is not round()). A group
-- on a through route carries its trail's `name` and `through_route: true`;
-- the haze groups carry neither. `trail_status` rides in the key so closed
-- ground never folds into an open-looking feature (write_overview()'s own
-- safety argument). Features in the key's order, as sorted() orders the
-- tuples, a haze group before a named one; the parts of a feature by line
-- id, where the Python's are in its records' order, which the warehouse does
-- not hold. A MultiLineString's parts draw the same in any order.
--
-- The properties and coordinates are JSON text, so a unit test can hold
-- them (a 2.0.6 unit test refuses a list column).
--
-- THE CLUBS' LINES COME LAST (decision 64): int_trail_lines__club_overview's
-- rows, grouped the same way, after every network group, so the network's
-- features keep their order. A club group carries `line_kind` 'club', the
-- mark nearby_trails.geojson's club lines carry, and no `trail_status`
-- member: a club line's status is unknown, never open.
with seam as (
    select
        *,
        false as is_club
    from {{ ref('int_trail_lines__network_overview_seam') }}
    union all by name
    select
        *,
        true as is_club
    from {{ ref('int_trail_lines__club_overview') }}
),

lines as (
    select
        *,
        coalesce(through_route, '') as route_name,
        st_geometrytype(st_geomfromtext(seam_wkt)) = 'MULTILINESTRING'
            as is_multi,
        json_extract(
            st_asgeojson(st_geomfromtext(seam_wkt)), '$.coordinates'
        ) as coordinates
    from seam
),

listed as (
    select
        *,
        case
            when is_multi then cast(coordinates as double[][][])
            else [cast(coordinates as double[][])]
        end as line_parts
    from lines
),

parts as (
    select
        is_club,
        source_key,
        route_name,
        blaze_color,
        trail_status,
        trail_line_id,
        unnest(line_parts) as line_part,
        generate_subscripts(line_parts, 1) as part_index
    from listed
),

rounded as (
    select
        *,
        list_transform(
            line_part,
            lambda point: list_transform(
                point,
                lambda coordinate: cast(
                    printf('%.{{ decimals }}f', coordinate) as double
                )
            )
        ) as cut_part
    from parts
),

-- WHAT THE CUT LEAVES, _drawn_at_the_cut(): a vertex the cut lands on the
-- one before it is dropped, then a part left with fewer than two vertices.
-- Neither draws anything on a phone, and dropping both takes UA's release
-- 2026-10-03-2 file from 41,216,145 bytes to 4,851,329 (Measured 2026-10-05;
-- that function's docstring has the rest). A group with no part left has
-- no row here, and so writes no feature. A window over the vertices rather
-- than a two-parameter lambda, which SQLFluff 4.3.0 cannot parse
-- (int_elevation__sample_points says so too).
cut_vertices as (
    select
        is_club,
        source_key,
        route_name,
        blaze_color,
        trail_status,
        trail_line_id,
        part_index,
        unnest(cut_part) as vertex,
        generate_subscripts(cut_part, 1) as vertex_index
    from rounded
),

drawn_vertices as (
    select *
    from cut_vertices
    qualify coalesce(
        lag(vertex) over (
            partition by is_club, trail_line_id, part_index
            order by vertex_index
        ) != vertex,
        true
    )
),

drawn as (
    select
        is_club,
        source_key,
        route_name,
        blaze_color,
        trail_status,
        trail_line_id,
        part_index,
        list(vertex order by vertex_index) as drawn_part
    from drawn_vertices
    group by
        is_club,
        source_key,
        route_name,
        blaze_color,
        trail_status,
        trail_line_id,
        part_index
),

grouped as (
    select
        is_club,
        source_key,
        route_name,
        blaze_color,
        trail_status,
        list(drawn_part order by trail_line_id, part_index) as group_lines
    from drawn
    where len(drawn_part) >= 2
    group by is_club, source_key, route_name, blaze_color, trail_status
)

select
    source_key,
    route_name,
    blaze_color,
    trail_status,
    row_number() over (
        order by is_club, source_key, route_name, blaze_color, trail_status
    ) - 1 as feature_order,
    cast(
        case
            when is_club
                then json_object(
                    'source', source_key,
                    'blaze_color', blaze_color,
                    'line_kind', 'club'
                )
            else json_merge_patch(
                json_object(
                    'source', source_key,
                    'blaze_color', blaze_color,
                    'trail_status', trail_status
                ),
                -- Null members are dropped, so a haze group carries neither.
                json_object(
                    'name', nullif(route_name, ''),
                    'through_route', case when route_name != '' then true end
                )
            )
        end as varchar
    ) as properties_json,
    cast(to_json(group_lines) as varchar) as coordinates_json
from grouped
