{{ config(materialized='table') }}
-- The corridor-view sketch of the centerline (TL17; PR #872 — Publish a
-- corridor-view centerline, and ask for it before the app has booted),
-- export_trails.write_overview(): one row per line of the one
-- MultiLineString trails_overview.geojson draws before the real line
-- lands.
--
-- From the SAME 1 m segments trails.geojson's chains are merged from, never
-- from the chains: Douglas-Peucker keeps a segment's ends, so the segments
-- and the chains simplify to different vertices. (export_trails.py's comment
-- at its call says the chains "would give the same vertices"; the chain
-- merge's own docstring says the same of the 1 m pass. Neither holds where a
-- segment end could be dropped, and this model follows the code, not the
-- comment.) Each segment Douglas-Peucker'd again, by the
-- simplified_in_metres macro, at trail_lines_overview_tolerance_m (100 m)
-- in EPSG:5070, as write_overview() calls simplify_records(), keeping its
-- 1 m line where the pass leaves it undrawable, every part in the layer's
-- order, each coordinate rounded to trail_lines_overview_decimals (4) as
-- Python's round() rounds it. The tolerance and the decimals are argued in
-- export_trails.py: 100 m is the worst the sketch is ever wrong by, 0.43 px
-- at the pin seam.
--
-- Only the centerline (CHAIN_MERGED_SOURCES), and only where it may publish:
-- the sketch is the centerline's geometry.
--
-- `coordinates_json` is each line's rounded coordinates as JSON text, so a
-- unit test holds them to the bit.
with simplified as (
    select * from {{ ref('int_trail_lines__at_simplified') }}
    where source_key in ('centerline')
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

coarse as (
    select
        simplified.source_order,
        simplified.source_row,
        st_geomfromtext(simplified.geom_wkt) as line_geom,
        {{ simplified_in_metres(
            'st_geomfromtext(simplified.geom_wkt)',
            var('trail_lines_overview_tolerance_m')
        ) }} as reduced_geom
    from simplified
    inner join publication
        on simplified.source_key = publication.source_key
    where publication.may_publish
),

kept as (
    select
        source_order,
        source_row,
        case
            when {{ line_is_drawable('reduced_geom') }} then reduced_geom
            else line_geom
        end as geom
    from coarse
),

parts as (
    select
        source_order,
        source_row,
        struct_extract(part, 'path') as part_path,
        struct_extract(part, 'geom') as part_line
    from (
        select
            source_order,
            source_row,
            unnest(st_dump(geom)) as part
        from kept
    ) as dumped
)

select
    row_number() over (
        order by source_order, source_row, part_path
    ) - 1 as line_order,
    cast(
        to_json(
            list_transform(
                {{ line_vertices('part_line') }},
                lambda xy: [
                    cast(
                        format(
                            '{:.{{ var("trail_lines_overview_decimals") }}f}',
                            list_extract(xy, 1)
                        ) as double
                    ),
                    cast(
                        format(
                            '{:.{{ var("trail_lines_overview_decimals") }}f}',
                            list_extract(xy, 2)
                        ) as double
                    )
                ]
            )
        ) as varchar
    ) as coordinates_json
from parts
