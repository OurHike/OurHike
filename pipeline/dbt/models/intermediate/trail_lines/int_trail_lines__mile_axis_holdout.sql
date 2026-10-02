{{ config(materialized='table') }}
-- How well the mile axis reproduces ATC's own miles on markers it never
-- saw: export_elevation.measure_marker_agreement (pipeline/ELT.md's EL04),
-- one row. Each piece with four or more snapped markers is calibrated again
-- from its even-numbered markers alone and scored on the odd-numbered ones,
-- because "scoring the fit on its own control points would measure nothing -
-- interpolation passes through them by construction".
--
-- Its tests in _trail_lines__intermediate.yml are the gate,
-- export_elevation.require_marker_agreement: median, p95 and maximum
-- error under the mile_axis_holdout_* vars, at error. "A quietly-degraded
-- calibration is the one failure mode worse than the fault it fixed,
-- because this time the code would claim to be calibrated." Today only
-- export_elevation.py runs that gate; export_poi.py, export_spurs.py and
-- export_trails.py read the same axis and never check it. Here the gate
-- sits upstream of every mile, so a breach stops them all.
--
-- Measured 2026-10-02 on DuckDB 1.5.5 against ATC's live layers, with the
-- Python run on the same files beside it: 2,020 held-out markers, median
-- 0.003248141658346526 mi and maximum 0.49659499100789617 mi in both, p95
-- 0.05457656690440444 here against 0.05457656690440443 there.
--
-- One difference from the Python, in a figure nothing publishes: with no
-- held-out marker at all the Python scores a single 0.0 and reports a count
-- of 1; this reports 0, with the three errors 0.0 as the Python has them.
with pieces as (
    select
        pre_calibration_order,
        -- `fitted.line.length` on the reversed line, which may differ from
        -- the forward length in the last digit.
        st_length(st_reverse(st_geomfromtext(geom_5070_wkt)))
            as reversed_length_m
    from {{ ref('int_trail_lines__mile_axis_pieces') }}
),

numbered as (
    select
        pre_calibration_order,
        along_m,
        measure_mi as mile,
        -- `pairs.sort()`: by along-distance, then mile.
        row_number()
            over (
                partition by pre_calibration_order order by along_m, measure_mi
            )
            as pair_seq,
        count(*) over (partition by pre_calibration_order) as pair_count
    from {{ ref('int_trail_lines__mile_axis_markers') }}
    where snapped
),

even_fits as (
    -- pairs[::2]: the 1st, 3rd, 5th... marker along the piece.
    select
        pre_calibration_order,
        coalesce(regr_slope(mile, along_m) < 0, false) as reversed_even
    from numbered
    where pair_count >= 4 and pair_seq % 2 = 1
    group by pre_calibration_order
),

oriented as (
    select
        numbered.pre_calibration_order,
        numbered.pair_seq,
        numbered.mile,
        case
            when
                even_fits.reversed_even
                then pieces.reversed_length_m - numbered.along_m
            else numbered.along_m
        end as along_m
    from numbered
    inner join
        even_fits
        on numbered.pre_calibration_order = even_fits.pre_calibration_order
    inner join
        pieces
        on numbered.pre_calibration_order = pieces.pre_calibration_order
),

even_anchors as (
    select
        pre_calibration_order,
        list(along_mi order by anchor_seq) as anchor_along_mi,
        list(mile order by anchor_seq) as anchor_mile
    from (
        select
            pre_calibration_order,
            along_m
            / cast('{{ var("mile_axis_metres_per_mile") }}' as double)
                as along_mi,
            max(mile) over (
                partition by pre_calibration_order
                order by along_m, mile
                rows between unbounded preceding and current row
            ) as mile,
            row_number()
                over (partition by pre_calibration_order order by along_m, mile)
                as anchor_seq
        from oriented
        where pair_seq % 2 = 1
    )
    group by pre_calibration_order
),

held_out as (
    -- pairs[1::2], scored on the even fit.
    select
        oriented.mile,
        oriented.along_m
        / cast('{{ var("mile_axis_metres_per_mile") }}' as double) as along_mi,
        even_anchors.anchor_along_mi,
        even_anchors.anchor_mile
    from oriented
    inner join
        even_anchors
        on oriented.pre_calibration_order = even_anchors.pre_calibration_order
    where oriented.pair_seq % 2 = 0
),

errors as (
    select
        abs(
            {{ mile_at_along('along_mi', 'anchor_along_mi', 'anchor_mile') }}
            - mile
        )
            as error_mi
    from held_out
),

figures as (
    -- np.median and np.percentile(errors, 95), whose default linear
    -- interpolation between ranks is quantile_cont's.
    select
        cast(count(*) as integer) as holdout_marker_count,
        coalesce(quantile_cont(error_mi, 0.5), 0.0) as holdout_median_mi,
        coalesce(quantile_cont(error_mi, 0.95), 0.0) as holdout_p95_mi,
        coalesce(max(error_mi), 0.0) as holdout_max_mi
    from errors
)

select
    holdout_marker_count,
    holdout_median_mi,
    holdout_p95_mi,
    holdout_max_mi,
    -- require_marker_agreement refuses on any one of the three.
    holdout_median_mi
    <= {{ var("mile_axis_holdout_max_median_mi") }} as median_within_gate,
    holdout_p95_mi
    <= {{ var("mile_axis_holdout_max_p95_mi") }} as p95_within_gate,
    holdout_max_mi <= {{ var("mile_axis_holdout_max_mi") }} as max_within_gate
from figures
