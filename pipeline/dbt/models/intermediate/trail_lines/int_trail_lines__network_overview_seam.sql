{{ config(materialized='table') }}
-- The second half of network_overview.geojson's sketch, write_overview()'s
-- steps after int_trail_lines__network_overview_routes (TL20): the floor,
-- then the seam's tolerance.
--
-- THE FLOOR, _above_the_seam_floor(): a coarse line whose whole bounding
-- box, in EPSG:5070, has a diagonal under OVERVIEW_MIN_FEATURE_M (one pixel
-- at OVERVIEW_SEAM_ZOOM, z5: 1,873.7 m) is a dot at the sketch's top zoom
-- and is dropped, unless it is on a through route, which is never dropped.
-- The diagonal is sqrt(dx² + dy²) where the Python takes numpy's hypot; the
-- two can differ in the last bit only, so only a line within an ulp of the
-- floor could land on the other side. The floor is @unvalidated in its own
-- comment (export_nearby_trails.py's OVERVIEW_MIN_FEATURE_M), which says
-- what would settle it.
--
-- THE SEAM: simplify_records() at OVERVIEW_SEAM_TOLERANCE_M, half a z5
-- pixel (936.9 m), in EPSG:5070, on each kept coarse line, keeping a
-- part's coarse vertices where the pass would leave that part undrawable
-- (PART BY PART, below).
with routes as (
    select * from {{ ref('int_trail_lines__network_overview_routes') }}
),

measured as (
    select
        *,
        st_geomfromtext(coarse_wkt) as coarse_line,
        st_transform(
            st_geomfromtext(coarse_wkt),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as coarse_m
    from routes
),

spans as (
    select
        *,
        st_xmax(coarse_m) - st_xmin(coarse_m) as span_x,
        st_ymax(coarse_m) - st_ymin(coarse_m) as span_y
    from measured
),

kept as (
    select *
    from spans
    where
        through_route is not null
        or sqrt(span_x * span_x + span_y * span_y)
        >= {{ var('trail_lines_network_overview_min_feature_m') }}
),

reduced as (
    select
        *,
        st_transform(
            st_simplify(
                coarse_m,
                {{ var('trail_lines_network_overview_seam_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as reduced
    from kept
),

judged as (
    select
        *,
        coalesce(
            not st_isempty(reduced)
            and list_bool_and(
                list_transform(
                    st_dump(reduced),
                    lambda part: (
                        st_xmin(struct_extract(part, 'geom'))
                        < st_xmax(struct_extract(part, 'geom'))
                    )
                    or (
                        st_ymin(struct_extract(part, 'geom'))
                        < st_ymax(struct_extract(part, 'geom'))
                    )
                )
            ),
            false
        ) as is_drawable
    from reduced
),

-- PART BY PART, _simplified_part_by_part(), as
-- int_trail_lines__network_overview_routes asks it of the 100 m pass: a
-- part the pass leaves undrawable keeps the coarse line's vertices, and
-- every other part keeps the pass's.
reduced_parts as (
    select
        trail_line_id,
        unnest(st_dump(reduced)) as reduced_part,
        unnest(st_dump(coarse_line)) as given_part,
        generate_subscripts(st_dump(coarse_line), 1) as part_index
    from judged
    where
        not is_drawable
        and st_geometrytype(coarse_line) = 'MULTILINESTRING'
),

by_part as (
    select
        trail_line_id,
        st_collect(
            list(
                case
                    when
                        st_xmin(struct_extract(reduced_part, 'geom'))
                        < st_xmax(struct_extract(reduced_part, 'geom'))
                        or st_ymin(struct_extract(reduced_part, 'geom'))
                        < st_ymax(struct_extract(reduced_part, 'geom'))
                        then struct_extract(reduced_part, 'geom')
                    else struct_extract(given_part, 'geom')
                end
                order by part_index
            )
        ) as by_part_line
    from reduced_parts
    group by trail_line_id
)

select
    judged.trail_line_id,
    judged.source_key,
    judged.blaze_color,
    judged.trail_status,
    judged.through_route,
    -- WKT, so a unit test can hold it, every vertex exact.
    st_astext(
        case
            when judged.is_drawable then judged.reduced
            when by_part.by_part_line is not null then by_part.by_part_line
            else judged.coarse_line
        end
    ) as seam_wkt
from judged
left join by_part on judged.trail_line_id = by_part.trail_line_id
