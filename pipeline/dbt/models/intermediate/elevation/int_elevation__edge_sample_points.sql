{{ config(materialized='table') }}
-- Where each junction-graph edge reads the DEM: one row per sample along an
-- edge, both ends included. The SQL form of
-- export_network_elevation.edge_sample_points, which export_network_profile.py
-- imports so that the climb and the profile are measured at the same points
-- (EL11 and EL12 of pipeline/ELT.md's ledger read these rows).
-- step_dem_sampling reads them through int_elevation__dem_points, after the
-- A.T.'s.
--
-- THE WALK, as the Python takes it. An edge's published vertices (its
-- trail_graph_geometry.json entry, 6 decimals) projected to EPSG:5070
-- metres, always_xy, as export_network_elevation._transformers projects
-- them; round(length / 25) intervals, at least one, so the spacing lands
-- near 25 m rather than always under it (a 30 m edge is one interval, not
-- two); the samples at length * i / steps for i = 0 .. steps, so both ends
-- are read (a short edge still gets its two ends: an edge is all that is
-- measured, and a truncated walk would lose the drop into a junction); each
-- back to lon/lat. Python's round() is the double's own value, ties to
-- even, which printf('%.0f') is: it agreed on all of 316,006 values, exact
-- ties included, where DuckDB's round() disagreed on 11,002 (measured
-- 2026-10-02 on DuckDB 1.5.5).
--
-- AN EDGE WITH NO LENGTH reads one point, its first vertex as published, as
-- the Python does for one vertex or a line of no projected length, rather
-- than stopping the build. An edge with no vertex reads nothing, and its
-- climb and profile are null.
--
-- TO THE BIT, measured 2026-10-02 on DuckDB 1.5.5 against
-- export_network_elevation.edge_sample_points: 30,004 edges cut from ATC's
-- live centerline of that day at 6 decimals, with one-vertex, no-length,
-- sub-metre and off-the-DEM edges among them: the same 143,019 samples, the
-- same count on every edge, at the same lon/lat to the bit.
with edges as (
    select
        edge_id,
        edge_index,
        geom_geojson,
        cast(json_extract(geom_geojson, '$.coordinates') as double[][])
            as coordinates
    from {{ ref('int_trail_network__edges') }}
),

measured as (
    select
        edge_id,
        edge_index,
        coordinates,
        len(coordinates) as vertex_count,
        case
            when len(coordinates) >= 2
                then
                    st_transform(
                        st_geomfromgeojson(geom_geojson),
                        'EPSG:4326',
                        'EPSG:5070',
                        always_xy := true
                    )
        end as line_5070
    from edges
),

lengths as (
    select
        edge_id,
        edge_index,
        coordinates,
        vertex_count,
        line_5070,
        st_length(line_5070) as length_m
    from measured
),

walked as (
    select
        edge_id,
        edge_index,
        line_5070,
        length_m,
        greatest(
            cast(
                printf(
                    '%.0f',
                    length_m
                    / cast('{{ var("elevation_sample_interval_m") }}' as double)
                ) as bigint
            ),
            1
        ) as steps
    from lengths
    where length_m > 0
),

positions as (
    select
        edge_id,
        edge_index,
        line_5070,
        length_m,
        steps,
        unnest(range(steps + 1)) as sample_index
    from walked
),

-- shapely's interpolate takes the distance and st_lineinterpolatepoint the
-- fraction of the length; the last sample's distance can land a bit past
-- the length, which shapely reads as the end and the fraction is held to.
interpolated as (
    select
        edge_id,
        edge_index,
        sample_index,
        st_lineinterpolatepoint(
            line_5070,
            least(
                (length_m * cast(sample_index as double))
                / cast(steps as double)
                / length_m,
                1.0
            )
        ) as point_5070
    from positions
),

placed as (
    select
        edge_id,
        edge_index,
        sample_index,
        st_transform(
            st_point(st_x(point_5070), st_y(point_5070)),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as point_4326
    from interpolated
),

single as (
    select
        edge_id,
        edge_index,
        list_extract(list_extract(coordinates, 1), 1) as lon,
        list_extract(list_extract(coordinates, 1), 2) as lat
    from lengths
    where vertex_count = 1 or (vertex_count >= 2 and not length_m > 0)
)

select
    edge_id,
    edge_index,
    cast(sample_index as integer) as sample_index,
    st_x(point_4326) as lon,
    st_y(point_4326) as lat
from placed
union all
select
    edge_id,
    edge_index,
    0 as sample_index,
    lon,
    lat
from single
