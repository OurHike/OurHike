{{ config(materialized='table') }}
-- What each blue-blazed spur leads to (TL27-TL29), export_spurs.py's
-- build_spur_records() and attach_junction_miles(), with lib/spurs.py's
-- rules: one row per side trail, its decoded `Type`, and for a spur what
-- spurs.json says of it.
--
-- TL27, A SPUR is a side trail whose Type decodes to "3" (SPUR_TYPE_CODE,
-- "Spur (eg View, Camp)"), lib/spurs.decode_type in its order: the text
-- stripped as Python strips it; a code of the domain as itself; one of
-- TYPE_LITERAL_ALIASES (the misspelt literal 60 live side trails carry for
-- "2"); a domain name read back to its code, ignoring case; a bare number
-- only when there is no domain at all. The domain is
-- int_trail_lines__coded_domains', a frozen copy of the live call.
--
-- TL28, THE TWO ENDS, from the side trail's full-resolution line: a
-- LineString's first and last vertex, a MultiLineString's first part's first
-- and last part's last. Each end's distance to the nearest vertex of ATC's
-- whole centerline, if within JUNCTION_MAX_M (100 m), in lib/spurs.py's
-- equirectangular metres. orient(): both ends within ON_TRAIL_M (25 m) is an
-- alternate route, two equal distances cannot be told apart, and no end near
-- the trail is not a junction, and each of the three gives no junction and no
-- destination; otherwise the nearer end is the junction, the other the far
-- end. The far end's destination is the nearest of
-- int_trail_lines__spur_destinations within DESTINATION_MAX_M (150 m),
-- rounded to the metre as Python's round() rounds it.
--
-- TL29, THE JUNCTION MILE: the junction on int_trail_lines__mile_axis by the
-- axis_mile macro, the same mile a POI gets (#136 — Publish the mile at
-- which each spur joins the AT), rounded to 3 decimals as
-- Python's round() does. Null where the ends cannot be told apart: absent
-- means unknown, never a guess at whichever end won by a metre.
--
-- ONE DEPARTURE FROM THE PYTHON'S ARITHMETIC: distance_m() calls math.hypot,
-- and DuckDB has none, so this is sqrt(dx * dx + dy * dy), which can differ
-- from hypot in the last bit (Reasoned). That moves an answer only for a
-- distance within one bit of 25, 100 or 150 m, of another candidate's, or of
-- a half metre.
--
-- spur_record_json is the spurs.json record itself, its keys sorted as
-- json.dumps(sort_keys=True) sorts them, so a unit test can hold every field
-- to the bit (a dbt 2.0.6 unit test compares a double only to one decimal).
with side_trails as (
    select * from {{ ref('int_trail_lines__at_features') }}
    where source_key = 'side_trails'
),

centerline as (
    select st_geomfromtext(geom_wkt) as geom
    from {{ ref('int_trail_lines__at_features') }}
    where source_key = 'centerline' and geom_wkt is not null
),

type_domain as (
    -- export_spurs.TYPE_FIELD
    select
        code,
        label
    from {{ ref('int_trail_lines__coded_domains') }}
    where source_key = 'side_trails' and field_name = 'Type'
),

typed as (
    select
        trail_segment_key,
        trail_line_id,
        source_row,
        name,
        length_ft,
        st_geomfromtext(geom_wkt) as geom,
        {{ python_strip('trail_type') }} as type_text
    from side_trails
),

decoded as (
    select
        typed.*,
        case
            when coalesce(typed.type_text, '') = '' then null
            when code_match.code is not null then code_match.code
            {%- for alias in var('trail_lines_type_literal_aliases') %}
            when lower(typed.type_text) = '{{ alias[0] }}'
                then '{{ alias[1] }}'
            {%- endfor %}
            when name_match.code is not null then name_match.code
            when
                not exists (select 1 from type_domain)
                and regexp_full_match(typed.type_text, '[0-9]+')
                then typed.type_text
        end as type_code
    from typed
    left join type_domain as code_match on typed.type_text = code_match.code
    left join type_domain as name_match
        on
            lower(typed.type_text)
            = lower({{ python_strip('name_match.label') }})
),

spurs as (
    select
        *,
        st_dump(geom) as parts
    from decoded
    where type_code = '{{ var("trail_lines_spur_type_code") }}'
),

-- line_endpoints(): (lat, lon) of each end, or none.
ends as (
    select
        trail_line_id,
        st_y(st_startpoint(struct_extract(list_extract(drawn, 1), 'geom')))
            as first_lat,
        st_x(st_startpoint(struct_extract(list_extract(drawn, 1), 'geom')))
            as first_lon,
        st_y(st_endpoint(struct_extract(list_extract(drawn, -1), 'geom')))
            as last_lat,
        st_x(st_endpoint(struct_extract(list_extract(drawn, -1), 'geom')))
            as last_lon
    from (
        select
            trail_line_id,
            st_geometrytype(geom) as geometry_type,
            st_npoints(geom) as vertex_count,
            list_filter(
                parts, lambda part: st_npoints(struct_extract(part, 'geom')) > 0
            ) as drawn
        from spurs
    ) as parted
    where
        (geometry_type = 'LINESTRING' and vertex_count >= 2)
        or (geometry_type = 'MULTILINESTRING' and len(drawn) > 0)
),

end_points as (
    select
        trail_line_id,
        'first' as end_name,
        first_lat as end_lat,
        first_lon as end_lon
    from ends
    union all
    select
        trail_line_id,
        'last' as end_name,
        last_lat as end_lat,
        last_lon as end_lon
    from ends
),

-- Every centerline vertex, in a 0.002-degree grid: at least 154 m wide on
-- both axes anywhere on the A.T. (34-46 degrees north), so every vertex
-- within the 100 m junction radius of an end lies in its cell or a
-- neighbour, which is PointIndex's own 3x3 argument.
centerline_vertices as (
    select
        list_extract(xy, 2) as vertex_lat,
        list_extract(xy, 1) as vertex_lon,
        floor(list_extract(xy, 2) / 0.002) as cell_lat,
        floor(list_extract(xy, 1) / 0.002) as cell_lon
    from (
        select unnest({{ line_vertices("struct_extract(part, 'geom')") }}) as xy
        from (select unnest(st_dump(geom)) as part from centerline) as parted
    ) as flattened
),

rows_around as (
    select unnest([-1, 0, 1]) as neighbour_lat
),

columns_around as (
    select unnest([-1, 0, 1]) as neighbour_lon
),

end_cells as (
    select
        end_points.*,
        floor(end_points.end_lat / 0.002) + rows_around.neighbour_lat
            as cell_lat,
        floor(end_points.end_lon / 0.002) + columns_around.neighbour_lon
            as cell_lon
    from end_points
    cross join rows_around
    cross join columns_around
),

end_offsets as (
    select
        end_cells.trail_line_id,
        end_cells.end_name,
        (centerline_vertices.vertex_lat - end_cells.end_lat)
        * {{ var('trail_lines_metres_per_degree') }} as dy,
        (centerline_vertices.vertex_lon - end_cells.end_lon)
        * {{ var('trail_lines_metres_per_degree') }}
        * cos(
            ((end_cells.end_lat + centerline_vertices.vertex_lat) / 2)
            * (pi() / 180.0)
        ) as dx
    from end_cells
    inner join centerline_vertices
        on
            end_cells.cell_lat = centerline_vertices.cell_lat
            and end_cells.cell_lon = centerline_vertices.cell_lon
),

-- PointIndex.nearest() on the centerline: the least distance within
-- JUNCTION_MAX_M, or none.
end_distances as (
    select
        trail_line_id,
        end_name,
        min(sqrt(dx * dx + dy * dy)) as distance_m
    from end_offsets
    where
        sqrt(dx * dx + dy * dy)
        <= {{ var('trail_lines_spur_junction_max_m') }}
    group by trail_line_id, end_name
),

-- orient(): which end is the junction, or none.
oriented as (
    select
        ends.*,
        first_end.distance_m as first_distance_m,
        last_end.distance_m as last_distance_m,
        case
            when first_end.distance_m is null and last_end.distance_m is null
                then null
            when first_end.distance_m is null then 'last'
            when last_end.distance_m is null then 'first'
            when
                first_end.distance_m
                <= {{ var('trail_lines_spur_on_trail_m') }}
                and last_end.distance_m
                <= {{ var('trail_lines_spur_on_trail_m') }}
                then null
            when first_end.distance_m = last_end.distance_m then null
            when first_end.distance_m < last_end.distance_m then 'first'
            else 'last'
        end as junction_end
    from ends
    left join end_distances as first_end
        on
            ends.trail_line_id = first_end.trail_line_id
            and first_end.end_name = 'first'
    left join end_distances as last_end
        on
            ends.trail_line_id = last_end.trail_line_id
            and last_end.end_name = 'last'
),

junctions as (
    select
        trail_line_id,
        case when junction_end = 'first' then first_lat else last_lat end
            as junction_lat,
        case when junction_end = 'first' then first_lon else last_lon end
            as junction_lon,
        case when junction_end = 'first' then last_lat else first_lat end
            as far_lat,
        case when junction_end = 'first' then last_lon else first_lon end
            as far_lon
    from oriented
    where junction_end is not null
),

destination_offsets as (
    select
        junctions.trail_line_id,
        destinations.poi_id,
        destinations.destination_order,
        (destinations.latitude - junctions.far_lat)
        * {{ var('trail_lines_metres_per_degree') }} as dy,
        (destinations.longitude - junctions.far_lon)
        * {{ var('trail_lines_metres_per_degree') }}
        * cos(
            ((junctions.far_lat + destinations.latitude) / 2) * (pi() / 180.0)
        ) as dx
    from junctions
    inner join {{ ref('int_trail_lines__spur_destinations') }} as destinations
        on
            abs(destinations.latitude - junctions.far_lat) <= 0.002
            and abs(destinations.longitude - junctions.far_lon) <= 0.003
),

-- PointIndex.nearest() on the destinations: the least distance within
-- DESTINATION_MAX_M, a tie to the POI listed first.
destinations as (
    select
        trail_line_id,
        poi_id as destination_poi_id,
        cast(round_even(sqrt(dx * dx + dy * dy), 0) as integer)
            as destination_distance_m
    from destination_offsets
    where
        sqrt(dx * dx + dy * dy)
        <= {{ var('trail_lines_spur_destination_max_m') }}
    qualify
        row_number() over (
            partition by trail_line_id
            order by sqrt(dx * dx + dy * dy), destination_order
        ) = 1
),

junction_points as (
    select
        trail_line_id,
        st_transform(
            st_point(junction_lon, junction_lat),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as junction_point
    from junctions
),

junction_miles as {{
    axis_mile('junction_points', ['trail_line_id'], 'junction_point')
}},

described as (
    select
        decoded.trail_segment_key,
        decoded.trail_line_id,
        decoded.type_code,
        coalesce(
            decoded.type_code = '{{ var("trail_lines_spur_type_code") }}', false
        ) as is_spur,
        coalesce(decoded.type_code is null and decoded.type_text != '', false)
            as type_undecodable,
        decoded.name,
        decoded.length_ft,
        destinations.destination_poi_id,
        destinations.destination_distance_m,
        cast(format('{:.3f}', junction_miles.mile) as double) as junction_mile
    from decoded
    left join destinations
        on decoded.trail_line_id = destinations.trail_line_id
    left join junction_miles
        on decoded.trail_line_id = junction_miles.trail_line_id
)

select
    *,
    case
        when is_spur
            then cast(
                json_object(
                    'destination_distance_m', destination_distance_m,
                    'destination_poi_id', destination_poi_id,
                    'junction_mile', junction_mile,
                    'length_ft', length_ft,
                    'name', name
                ) as varchar
            )
    end as spur_record_json
from described
