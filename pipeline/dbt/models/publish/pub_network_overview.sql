{{ config(format='json', location='network_overview.geojson') }}
{%- set decimals = var('trail_lines_network_overview_seam_decimals') %}
-- network_overview.geojson, the sketch of every other organization's trails
-- the opening camera draws (#1135, client/src/lib/config.ts's
-- NETWORK_OVERVIEW_KEY), in the shape export_nearby_trails.py's
-- write_overview() writes (decision 44's v1).
--
-- Reads int_trail_lines__network_overview_seam, the lines left after the
-- floor and simplified to the seam's tolerance (TL20), and through it the
-- 1 m line at full precision, which is what write_overview() is handed. Not
-- the trail_lines mart's six-decimal geometry: the sketch is simplified
-- from the uncut line in the Python, and parity holds it to that.
--
-- ONE FEATURE PER (source, through route, blaze_color, trail_status), every
-- line of the group one part of a MultiLineString at OVERVIEW_SEAM_DECIMALS,
-- three, cut as Python's round() cuts (the printf cast,
-- int_trail_lines__network_published says why it is not round()). A group
-- on a through route carries its trail's `name` and `through_route: true`;
-- the haze groups carry neither. `trail_status` rides in the key so closed
-- ground never folds into an open-looking feature (write_overview()'s own
-- safety argument). Features in the key's order, as sorted() orders the
-- tuples, a haze group before a named one; the parts of a feature by line
-- id, where the Python's are in its records' order, which the warehouse does
-- not hold. A MultiLineString's parts draw the same in any order.
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
),

features as (
    select
        source_key,
        route_name,
        blaze_color,
        trail_status,
        json_object(
            'type', 'Feature',
            'properties', json_merge_patch(
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
            ),
            'geometry', json_object(
                'type', 'MultiLineString',
                'coordinates', to_json(group_lines)
            )
        ) as feature
    from grouped
)

select
    -- Quoted because `type` is a keyword to SQLFluff's RF04, and GeoJSON names
    -- the member so; quoting it is what RF06 calls unnecessary.
    'FeatureCollection' as "type",  -- noqa: RF06
    coalesce(
        list(
            feature
            order by source_key, route_name, blaze_color, trail_status
        ),
        []
    ) as features
from features
