{{ config(materialized='table') }}
-- The A.T.'s published lines at the 1 m pass (TL15),
-- export_trails.simplify_records(): each line taken to EPSG:5070, where a
-- metre is a metre on both axes, Douglas-Peucker'd at
-- trail_lines_simplify_tolerance_m (1 m; that function's docstring has the
-- measurement behind it), and taken back, always_xy on both legs. It runs
-- after the clip, so the corridor test saw the full line.
--
-- NEVER DROPS A FEATURE: where the pass leaves any part with fewer than two
-- distinct vertices, the line keeps its full-resolution geometry, never the
-- reprojected one (line_is_drawable, export_trails._has_drawable_geometry).
-- `simplified` says which happened.
--
-- Measured 2026-10-02 on ATC's 4,221 live lines: ST_Simplify here gives
-- shapely.simplify(..., preserve_topology=False)'s vertices, every one to
-- the bit, and the same one fallback.
--
-- Two lengths in EPSG:5070 metres, for the mart: `length_m` of the full
-- line, before the pass, which can only shorten it, and
-- `published_length_m` of the line this model publishes. Geometry in and out
-- is WKT text (int_trail_lines__at_features says why).
with clipped as (
    select * from {{ ref('int_trail_lines__at_clipped') }}
),

reduced as (
    select
        * exclude (geom_wkt),
        st_geomfromtext(geom_wkt) as full_geom,
        st_transform(
            st_simplify(
                st_transform(
                    st_geomfromtext(geom_wkt),
                    'EPSG:4326',
                    'EPSG:5070',
                    always_xy := true
                ),
                {{ var('trail_lines_simplify_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as reduced_geom
    from clipped
),

chosen as (
    select
        * exclude (reduced_geom),
        {{ line_is_drawable('reduced_geom') }} as simplified,
        case
            when {{ line_is_drawable('reduced_geom') }} then reduced_geom
            else full_geom
        end as published_geom
    from reduced
)

select
    * exclude (full_geom, published_geom),
    st_astext(published_geom) as geom_wkt,
    st_astext(full_geom) as full_geom_wkt,
    st_length(
        st_transform(full_geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
    ) as length_m,
    st_length(
        st_transform(
            published_geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
        )
    ) as published_length_m
from chosen
