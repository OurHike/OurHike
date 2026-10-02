{{ config(materialized='table') }}
-- How ATC's half-mile markers orient and scale each centerline piece: the
-- calibration of the mile axis (pipeline/ELT.md's EL03),
-- export_elevation._calibrated_part and the end of
-- calibrate_parts_to_markers, on the pieces of
-- int_trail_lines__mile_axis_pieces and the pairs of
-- int_trail_lines__mile_axis_markers. One row per piece, in mile order.
-- THE PIECE TRAVELS AS WKT TEXT, turned round where the markers reversed
-- it, and ITS NUMBERS AS ONE JSON OBJECT (calibration_json: length_m,
-- start_mile, end_mile and the two anchor lists), for
-- int_trail_lines__mile_axis to make geometry, doubles and DOUBLE[] lists
-- of. Both are text so that a unit test can hold this model to the Python
-- to the bit, which dbt 2.0.6 cannot do with the types themselves (measured
-- 2026-10-02 on this model):
-- - a list column is refused: "Only primitive types like numeric, temporal
--   and varchar are supported for unit_testing";
-- - a GEOMETRY column fails the test (int_trail_lines__mile_axis_pieces);
-- - a DOUBLE column is compared only after rounding to one decimal place:
--   against a true 3365.9360592256835, a planted 3365.9 passed and 3365.96
--   failed; against 0.40036532740230757, 0.44 passed and 0.45 failed. A
--   mile is published to three.
-- Both round trips are exact: DuckDB writes a double at the shortest
-- precision that reads back to it, and 5,005 doubles came back identical
-- through to_json and a cast to DOUBLE[] (measured 2026-10-02 on DuckDB
-- 1.5.5). VARCHAR, integer and boolean columns compare exactly.
--
-- - A piece with two or more pairs is reversed when its markers' mile falls
--   as the along-distance grows: the sign of a least-squares slope, which is
--   np.polyfit(alongs, miles, 1)[0] < 0, and "what catches the 33 real
--   switchback pieces the straight-axis heuristic mis-orients" (measured
--   2026-08-18). One pair carries no direction.
-- - Each pair's along-distance is taken on the piece as now oriented, the
--   miles are made monotone with a running maximum ("the jitter this absorbs
--   is small"), and the along-distances go to miles.
-- - The pieces are sorted by the mile at their start, ties kept in the
--   straight-axis order: piece_id.
--
-- SQL, WITH `spatial`, AND NOTHING LEFT IN PYTHON (decision 23). Measured
-- 2026-10-02 on dbt 2.0.6's DuckDB 1.5.4 against ATC's live centerline (3,025
-- segments) and half-mile markers (4,395), read that day and loaded through
-- extract fixture mode, with the Python run on the same files beside it: the
-- same 562 pieces in the same order, every length, start mile, end mile and
-- anchor mile identical to the bit. 260 anchor along-distances differ, by at
-- most 1.42e-14 mi (int_trail_lines__mile_axis_markers says why).
--
-- Where two anchors share an along-distance on a piece the markers reverse,
-- they are kept in mile order. The Python's numpy argsort does that for 16
-- anchors or fewer, and past 16 it is @unvalidated.
with pieces as (
    select
        pre_calibration_order,
        geom_5070_wkt,
        st_length(st_geomfromtext(geom_5070_wkt)) as forward_length_m,
        -- `line.length` on the reversed line, which can differ from the
        -- forward length in the last digit.
        st_length(st_reverse(st_geomfromtext(geom_5070_wkt)))
            as reversed_length_m
    from {{ ref('int_trail_lines__mile_axis_pieces') }}
),

pairs as (
    select
        pre_calibration_order,
        snapped,
        along_m,
        measure_mi as mile
    from {{ ref('int_trail_lines__mile_axis_markers') }}
),

fits as (
    select
        pre_calibration_order,
        count(*) as anchor_count,
        count(*) filter (where snapped) as snapped_marker_count,
        coalesce(count(*) >= 2 and regr_slope(mile, along_m) < 0, false)
            as reversed_by_markers
    from pairs
    group by pre_calibration_order
),

calibrated_pieces as (
    select
        pieces.pre_calibration_order,
        fits.anchor_count,
        fits.snapped_marker_count,
        fits.reversed_by_markers,
        case
            when fits.reversed_by_markers then pieces.reversed_length_m
            else pieces.forward_length_m
        end as length_m,
        case
            when
                fits.reversed_by_markers
                then
                    st_astext(st_reverse(st_geomfromtext(pieces.geom_5070_wkt)))
            else pieces.geom_5070_wkt
        end as geom_5070_wkt
    from pieces
    inner join fits on pieces.pre_calibration_order = fits.pre_calibration_order
),

anchors as (
    select
        pairs.pre_calibration_order,
        pairs.mile,
        -- `line.length - alongs`, on the reversed line.
        case
            when
                calibrated_pieces.reversed_by_markers
                then calibrated_pieces.length_m - pairs.along_m
            else pairs.along_m
        end as along_m
    from pairs
    inner join
        calibrated_pieces
        on pairs.pre_calibration_order = calibrated_pieces.pre_calibration_order
),

monotone as (
    select
        pre_calibration_order,
        along_m
        / cast('{{ var("mile_axis_metres_per_mile") }}' as double) as along_mi,
        max(mile) over (
            partition by pre_calibration_order
            order by along_m, mile
            rows between unbounded preceding and current row
        ) as mile,
        row_number()
            over (partition by pre_calibration_order order by along_m, mile)
            as anchor_seq
    from anchors
),

anchor_lists as (
    select
        pre_calibration_order,
        list(along_mi order by anchor_seq) as anchor_along_mi,
        list(mile order by anchor_seq) as anchor_mile
    from monotone
    group by pre_calibration_order
),

ends as (
    select
        calibrated_pieces.pre_calibration_order,
        calibrated_pieces.geom_5070_wkt,
        calibrated_pieces.length_m,
        calibrated_pieces.anchor_count,
        calibrated_pieces.snapped_marker_count,
        calibrated_pieces.reversed_by_markers,
        anchor_lists.anchor_along_mi,
        anchor_lists.anchor_mile,
        cast(0.0 as double) as start_along_mi,
        calibrated_pieces.length_m
        / cast('{{ var("mile_axis_metres_per_mile") }}' as double)
            as end_along_mi
    from calibrated_pieces
    inner join
        anchor_lists
        on
            calibrated_pieces.pre_calibration_order
            = anchor_lists.pre_calibration_order
),

miles as (
    select
        *,
        {{ mile_at_along('start_along_mi', 'anchor_along_mi', 'anchor_mile') }}
            as start_mile,
        {{ mile_at_along('end_along_mi', 'anchor_along_mi', 'anchor_mile') }}
            as end_mile
    from ends
)

select
    cast(
        row_number() over (order by start_mile, pre_calibration_order)
        - 1 as integer
    ) as piece_id,
    pre_calibration_order,
    geom_5070_wkt,
    cast(json_object(
        'length_m', length_m,
        'start_mile', start_mile,
        'end_mile', end_mile,
        'anchor_along_mi', anchor_along_mi,
        'anchor_mile', anchor_mile
    ) as varchar) as calibration_json,
    cast(anchor_count as integer) as anchor_count,
    cast(snapped_marker_count as integer) as snapped_marker_count,
    reversed_by_markers
from miles
