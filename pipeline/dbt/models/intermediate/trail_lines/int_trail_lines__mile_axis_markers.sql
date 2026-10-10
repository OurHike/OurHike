{{ config(materialized='table') }}
-- Which of ATC's half-mile markers calibrates which centerline piece, and
-- where along it: the snap of the mile axis (pipeline/ELT.md's EL03),
-- export_elevation._snap_markers_to_parts and the fallback in
-- calibrate_parts_to_markers. One row per (piece, marker) pair.
--
-- `snapped`: the marker is within mile_axis_marker_snap_max_m (100 m) of
-- the piece and no piece is nearer. Measured 2026-08-18 against the live
-- layers, the markers sit on the centerline (p99 0.0 m, max 3.4 m), so 100 m
-- is "~30x the worst real offset" (export_elevation.py).
--
-- Not snapped: the piece had no marker of its own, and takes the nearest
-- marker outright. 182 of 558 pieces on the real data, 7.5 mi in all, none
-- longer than 0.43 mi (export_elevation.py, 2026-08-18); "mile error there is
-- bounded by the marker spacing plus the piece's own length".
--
-- `along_m` is the marker's distance along the piece AS THE STRAIGHT AXIS
-- ORIENTED IT, before the markers have a say, which is the along-distance
-- export_elevation.py computes with shapely's project. Here it is
-- st_linelocatepoint times the length, a fraction times a length where
-- shapely returns the length itself: the two differed in the last binary
-- digit on 36 of 500 random lines (measured 2026-10-02 on DuckDB 1.5.5),
-- and on ATC's live layers the same day, through dbt 2.0.6, 260 anchor
-- along-distances differed by at most 1.42e-14 mi
-- (int_trail_lines__mile_axis_calibration has that run).
--
-- TIES, where the Python has no rule: a marker equally near two pieces
-- snaps to the earlier piece, and a piece with no marker of its own takes the
-- earliest of equally near markers. shapely's STRtree.nearest returns "a
-- single result ... based on the order that tree geometries are visited;
-- this order may be nondeterministic" (its own docstring, shapely 2.1.2).
with pieces as (
    select
        pre_calibration_order,
        st_geomfromtext(geom_5070_wkt) as geom_5070
    from {{ ref('int_trail_lines__mile_axis_pieces') }}
),

markers as (
    -- A marker with no Measure is left out: in the Python it would turn its
    -- piece's miles into NaN (np.maximum.accumulate carries one forward).
    -- stg_atc__half_mile_markers' not_null test fails the build first.
    select
        source_row as marker_row,
        source_id as point_id,
        measure_mi,
        st_transform(
            st_point(longitude, latitude),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as geom_5070
    from {{ ref('stg_atc__half_mile_markers') }}
    where
        measure_mi is not null
        and longitude is not null
        and latitude is not null
),

snapped as (
    select
        pieces.pre_calibration_order,
        markers.marker_row,
        markers.point_id,
        markers.measure_mi,
        true as snapped,
        st_distance(pieces.geom_5070, markers.geom_5070) as distance_m,
        st_linelocatepoint(pieces.geom_5070, markers.geom_5070)
        * st_length(pieces.geom_5070) as along_m
    from markers
    inner join pieces
        on
            st_dwithin(
                pieces.geom_5070,
                markers.geom_5070,
                {{ var("mile_axis_marker_snap_max_m") }}
            )
    qualify row_number() over (
        partition by markers.marker_row
        order by
            st_distance(pieces.geom_5070, markers.geom_5070),
            pieces.pre_calibration_order
    ) = 1
),

anchored_outright as (
    select
        pieces.pre_calibration_order,
        markers.marker_row,
        markers.point_id,
        markers.measure_mi,
        false as snapped,
        st_distance(pieces.geom_5070, markers.geom_5070) as distance_m,
        st_linelocatepoint(pieces.geom_5070, markers.geom_5070)
        * st_length(pieces.geom_5070) as along_m
    from pieces
    cross join markers
    where
        pieces.pre_calibration_order not in (
            select snapped.pre_calibration_order from snapped
        )
    qualify row_number() over (
        partition by pieces.pre_calibration_order
        order by
            st_distance(pieces.geom_5070, markers.geom_5070), markers.marker_row
    ) = 1
),

pairs as (
    select * from snapped
    union all by name
    select * from anchored_outright
)

select
    {{ dbt_utils.generate_surrogate_key([
        'pre_calibration_order',
        'marker_row',
    ]) }} as axis_marker_key,
    pre_calibration_order,
    cast(marker_row as integer) as marker_row,
    point_id,
    measure_mi,
    snapped,
    distance_m,
    along_m
from pairs
