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
-- pixel (936.9 m), in EPSG:5070, on each kept coarse line, keeping the
-- coarse line where the pass would leave a part undrawable.
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
)

select
    trail_line_id,
    source_key,
    blaze_color,
    trail_status,
    through_route,
    -- WKT, so a unit test can hold it, every vertex exact.
    st_astext(
        case
            when
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
                )
                then reduced
            else coarse_line
        end
    ) as seam_wkt
from reduced
