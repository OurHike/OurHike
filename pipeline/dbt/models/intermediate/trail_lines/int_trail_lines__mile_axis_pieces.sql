{{ config(materialized='table') }}
-- The A.T. centerline merged into as few pieces as touch, oriented and put
-- in order along a straight Springer->Katahdin line: the first two steps of
-- the mile axis (pipeline/ELT.md's EL01 and EL02), before ATC's half-mile
-- markers calibrate it in int_trail_lines__mile_axis. One row per piece, in
-- the order export_elevation.ordered_oriented_parts returns them.
--
-- EL01, export_elevation.load_merged_trail_line:
-- ST_LineMerge(ST_Union_Agg(geom)) over every segment, read in the order the
-- layer's pages served them (stg_atc__centerline_segments' source_row), the
-- order the Python's ST_Read scan hands them to the same two functions.
-- The real data does not merge to one line: 558 pieces, 114 of them under
-- ~10 m, because real segment ends do not always touch (the Python's
-- docstring, 2026-07-28); 562 on the layer read 2026-10-02.
--
-- EL02, ordered_oriented_parts: a piece is reversed when its first vertex
-- projects further along the straight axis than its last, and the pieces are
-- sorted by their first vertex's projection, ties kept in merge order. The
-- projection is only a first guess at the order: #652 measured it misplacing
-- 18 stretches by more than ten miles, and the markers decide in the next
-- model. Then each piece goes to EPSG:5070 metres, always_xy, as
-- export_elevation.reproject_lines_to_meters takes it.
--
-- Measured 2026-10-02 against ATC's live layer, on DuckDB 1.5.5 and again
-- through dbt 2.0.6's DuckDB 1.5.4: the same 562 pieces as the Python, in
-- the same order, each geometry identical to the bit
-- (int_trail_lines__mile_axis_calibration has the rest of that run).
--
-- THE PIECES ARE WKT TEXT, NOT GEOMETRY, so that a unit test can hold this
-- step to the Python. dbt 2.0.6 cannot read a GEOMETRY column back when it
-- infers a unit test's expected schema: "Failed to convert type BinaryView.
-- Error: BinaryView is not supported for DuckDB" (measured 2026-10-02 on this
-- model). DuckDB writes WKT at the shortest precision that reads back to the
-- same double, so the round trip loses nothing: 2,000 of 2,000 random points
-- came back identical (measured the same day on DuckDB 1.5.5).
-- int_trail_lines__mile_axis turns the text back into geometry for every
-- consumer.
with segments as (
    select
        source_row,
        geom
    from {{ ref('stg_atc__centerline_segments') }}
    where geom is not null
),

merged as (
    select st_linemerge(st_union_agg(geom order by source_row)) as geom
    from segments
),

dumped as (
    select unnest(st_dump(geom)) as part
    from merged
),

parts as (
    select
        -- st_dump numbers a MultiLineString's lines from 1, and gives a lone
        -- LineString an empty path.
        coalesce(list_extract(struct_extract(part, 'path'), 1), 1)
            as part_index,
        struct_extract(part, 'geom') as geom
    from dumped
),

straight_axis as (
    -- export_elevation._trail_axis_projection's constants as doubles, and
    -- its two differences taken in double, as Python takes them.
    select
        cast('{{ var("mile_axis_springer_lon") }}' as double) as springer_lon,
        cast('{{ var("mile_axis_springer_lat") }}' as double) as springer_lat,
        cast('{{ var("mile_axis_katahdin_lon") }}' as double)
        - cast('{{ var("mile_axis_springer_lon") }}' as double) as axis_dx,
        cast('{{ var("mile_axis_katahdin_lat") }}' as double)
        - cast('{{ var("mile_axis_springer_lat") }}' as double) as axis_dy
),

projected as (
    select
        parts.part_index,
        parts.geom,
        (st_x(st_startpoint(parts.geom)) - straight_axis.springer_lon)
        * straight_axis.axis_dx
        + (st_y(st_startpoint(parts.geom)) - straight_axis.springer_lat)
        * straight_axis.axis_dy as start_projection,
        (st_x(st_endpoint(parts.geom)) - straight_axis.springer_lon)
        * straight_axis.axis_dx
        + (st_y(st_endpoint(parts.geom)) - straight_axis.springer_lat)
        * straight_axis.axis_dy as end_projection
    from parts
    cross join straight_axis
),

oriented as (
    select
        part_index,
        start_projection > end_projection as reversed_by_straight_axis,
        case
            when start_projection > end_projection then st_reverse(geom)
            else geom
        end as geom,
        -- The oriented piece's first vertex, whichever end that is.
        least(start_projection, end_projection) as first_projection
    from projected
)

select
    cast(
        row_number() over (order by first_projection, part_index) - 1 as integer
    ) as pre_calibration_order,
    cast(part_index as integer) as merge_part_index,
    reversed_by_straight_axis,
    st_astext(geom) as geom_wkt,
    st_astext(st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true))
        as geom_5070_wkt
from oriented
