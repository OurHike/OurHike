{{ config(materialized='table') }}
-- The A.T. half of the trail_lines mart: one row per line trails.geojson
-- publishes, in exactly the mart's columns. The centerline's chains first,
-- in their numbering, then the side trails and spurs in the layer's order,
-- as export_trails.merge_chain_records() returns them.
--
-- THE 6-DECIMAL CUT (decision 8), where export_trails.py writes GDAL's
-- digits: every coordinate rounded to trail_lines_published_decimals as
-- Python's round() rounds it (a correctly rounded decimal, which
-- format('{:.6f}') is too), vertex for vertex, never ST_ReducePrecision,
-- which drops vertices and would misalign trail_miles.json (ELT.md's
-- pitfall 1). A line the cut would leave with a part of fewer than two
-- distinct vertices keeps full precision instead: export_nearby_trails.py's
-- _rounded_geometry, the never-degenerate rule. Six decimals is ~0.1 m, an
-- order under the 1 m pass the vertices already came through.
--
-- The text is ST_AsGeoJSON of the cut line, which prints each double in the
-- fewest digits that read back to it, as Python's json does.
with chains as (
    select * from {{ ref('int_trail_lines__at_chain_miles') }}
),

side_trails as (
    select * from {{ ref('int_trail_lines__at_side_trails') }}
),

lines as (
    select
        trail_line_id,
        club,
        source_key,
        _loaded_at,
        'centerline' as line_kind,
        chain_index as feature_order,
        name,
        blaze_color,
        st_geomfromtext(geom_wkt) as geom,
        length_m,
        published_length_m,
        cast(vertex_miles_json as double[]) as vertex_miles,
        monotonic_breaks,
        cast(null as double) as spur_length_ft,
        cast(null as varchar) as spur_destination_poi_id,
        cast(null as integer) as spur_destination_distance_m,
        cast(null as double) as spur_junction_mile
    from chains
    union all
    select
        trail_line_id,
        club,
        source_key,
        _loaded_at,
        case when is_spur then 'spur' else 'side_trail' end as line_kind,
        (select count(*) from chains)
        + row_number() over (order by source_order, source_row)
        - 1 as feature_order,
        name,
        blaze_color,
        st_geomfromtext(geom_wkt) as geom,
        length_m,
        published_length_m,
        cast(null as double[]) as vertex_miles,
        cast(null as integer) as monotonic_breaks,
        spur_length_ft,
        spur_destination_poi_id,
        spur_destination_distance_m,
        spur_junction_mile
    from side_trails
),

-- Each part's vertices, cut.
cut as (
    select
        *,
        list_transform(
            st_dump(geom),
            lambda part: list_transform(
                {{ line_vertices("struct_extract(part, 'geom')") }},
                lambda xy: [
                    cast(
                        format(
                            '{:.{{ var("trail_lines_published_decimals") }}f}',
                            list_extract(xy, 1)
                        ) as double
                    ),
                    cast(
                        format(
                            '{:.{{ var("trail_lines_published_decimals") }}f}',
                            list_extract(xy, 2)
                        ) as double
                    )
                ]
            )
        ) as cut_parts
    from lines
),

drawn as (
    select
        *,
        list_bool_and(
            list_transform(
                cut_parts, lambda part: len(list_distinct(part)) >= 2
            )
        ) as cut_is_drawable,
        list_transform(
            cut_parts,
            lambda part: st_makeline(
                list_transform(
                    part,
                    lambda xy: st_point(
                        list_extract(xy, 1), list_extract(xy, 2)
                    )
                )
            )
        ) as cut_lines
    from cut
)

select
    trail_line_id,
    club,
    source_key,
    _loaded_at,
    line_kind,
    feature_order,
    name,
    blaze_color,
    cast(null as varchar) as trail_status,
    cast(null as varchar) as trail_status_basis,
    cast(null as varchar) as closure_kind,
    cast(null as varchar) as duplicate_of,
    st_asgeojson(
        case
            when not cut_is_drawable then geom
            when st_geometrytype(geom) = 'LINESTRING'
                then list_extract(cut_lines, 1)
            else st_collect(cut_lines)
        end
    ) as geom_geojson,
    length_m,
    published_length_m,
    vertex_miles,
    monotonic_breaks,
    spur_length_ft,
    spur_destination_poi_id,
    spur_destination_distance_m,
    spur_junction_mile
from drawn
