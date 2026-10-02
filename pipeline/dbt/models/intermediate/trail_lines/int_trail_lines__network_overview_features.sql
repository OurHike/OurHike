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
with seam as (
    select * from {{ ref('int_trail_lines__network_overview_seam') }}
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

grouped as (
    select
        source_key,
        route_name,
        blaze_color,
        trail_status,
        list(cut_part order by trail_line_id, part_index) as group_lines
    from rounded
    group by source_key, route_name, blaze_color, trail_status
)

select
    source_key,
    route_name,
    blaze_color,
    trail_status,
    row_number() over (
        order by source_key, route_name, blaze_color, trail_status
    ) - 1 as feature_order,
    cast(
        json_merge_patch(
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
        ) as varchar
    ) as properties_json,
    cast(to_json(group_lines) as varchar) as coordinates_json
from grouped
