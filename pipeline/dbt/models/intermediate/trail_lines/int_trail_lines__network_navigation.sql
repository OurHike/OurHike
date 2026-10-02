{{ config(materialized='table') }}
-- Every network line that ships, simplified to 1 m (TL15, the network's
-- half): export_trails.py's simplify_records() at
-- DEFAULT_SIMPLIFY_TOLERANCE_M, which export_nearby_trails.py's main() calls
-- on the deduplicated records. int_trail_lines__network_published cuts this
-- line to six decimals for the trail_lines mart and nearby_trails.geojson;
-- the overview sketch is simplified again from this line at full precision,
-- as write_overview() is handed it.
--
-- THE PASS: Douglas-Peucker at 1.0 m in EPSG:5070 (always_xy), then back to
-- longitude and latitude, which is shapely.simplify(...,
-- preserve_topology=False) between the same two pyproj transforms. Measured
-- 2026-10-02, DuckDB 1.5.5 against shapely 2.1.2 (GEOS 3.13.1): the same
-- doubles, vertex for vertex, on all 66 lines the fixture warehouse ships and
-- on 400 of the 404 lines test_simplify_trails.py's _awkward_lines() builds,
-- at 1 m and at 100 m. The other 4 are loops inside the tolerance, which both
-- collapse to one point twice; the fallback below handles them as the
-- Python does.
--
-- NEVER DROPS A FEATURE, simplify_records()' own rule: a line the pass
-- leaves with a part of fewer than two distinct vertices keeps its
-- full-resolution geometry WHOLE, every part of it, as _drawable_all()
-- answers. A part has two distinct vertices exactly when its bounding box
-- has width or height, which is the test below.
with deduplicated as (
    select * from {{ ref('int_trail_lines__network_deduplicated') }}
),

reduced as (
    select
        *,
        st_geomfromtext(geom_wkt) as geom,
        st_transform(
            st_simplify(
                st_transform(
                    st_geomfromtext(geom_wkt),
                    'EPSG:4326',
                    'EPSG:5070',
                    always_xy := true
                ),
                {{ var('trail_lines_network_navigation_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as reduced
    from deduplicated
),

checked as (
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
        ) as drawable
    from reduced
)

select
    trail_segment_key,
    source_key,
    club,
    file_row,
    trail_line_id,
    name,
    trail_status,
    trail_status_basis,
    closure_kind,
    blaze_color,
    duplicate_of,
    -- The line before the pass, which `length_m` is measured on.
    geom_wkt as full_resolution_wkt,
    -- WKT, so this model's unit tests can hold its output (a 2.0.6 unit test
    -- panics on GEOMETRY); every vertex reads back exactly.
    st_astext(case when drawable then reduced else geom end) as geom_wkt,
    -- Whether the pass would have left a part undrawable, so the line kept
    -- its full-resolution vertices.
    not drawable as kept_full_resolution,
    _loaded_at
from checked
