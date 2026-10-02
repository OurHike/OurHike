-- The junction graph's seam, measured: one row, the numbers
-- export_network_profile.measure_seams puts in trail_graph_profile_manifest.
-- json's `seam` block (EL13 of pipeline/ELT.md's ledger), from
-- int_elevation__seam_nodes. Writing the manifest is stage 4's; this is what
-- it will say.
--
-- Percentiles are nearest-rank, as _percentile takes them, so each is a step
-- that was measured rather than an interpolation between two: the step at
-- place round(fraction * (n - 1)) of the n steps in order, the place rounded
-- as Python's round() rounds (printf('%.0f') on the same double), and 0.0
-- when no node has a step. "Over the dead band" is a step of at least the
-- 3 m dead band in feet, the threshold int_elevation__edge_climbs applies
-- inside an edge.
with nodes as (
    select * from {{ ref('int_elevation__seam_nodes') }}
),

steps as (
    select
        step_ft,
        row_number() over (order by step_ft) - 1 as step_rank,
        count(*) over () as step_count
    from nodes
    where step_ft is not null
),

nearest_rank as (
    select
        step_ft,
        step_rank,
        least(
            step_count - 1,
            greatest(
                0,
                cast(
                    printf(
                        '%.0f',
                        cast('0.5' as double) * cast(step_count - 1 as double)
                    ) as bigint
                )
            )
        ) as p50_rank,
        least(
            step_count - 1,
            greatest(
                0,
                cast(
                    printf(
                        '%.0f',
                        cast('0.95' as double) * cast(step_count - 1 as double)
                    ) as bigint
                )
            )
        ) as p95_rank
    from steps
),

summary as (
    select
        count(*) as measured_nodes,
        count(*) filter (where step_ft > 0) as nodes_with_a_step,
        count(*) filter (
            where step_ft >= {{ elevation_gain_threshold_ft() }}
        ) as steps_over_dead_band,
        max(step_ft) filter (where step_rank = p50_rank) as step_ft_p50,
        max(step_ft) filter (where step_rank = p95_rank) as step_ft_p95,
        max(step_ft) as step_ft_max
    from nearest_rank
),

shared as (
    select
        count(*) as shared_nodes,
        count(*) filter (where coincident) as coincident_ends
    from nodes
)

select
    shared.shared_nodes,
    shared.coincident_ends,
    summary.measured_nodes,
    summary.nodes_with_a_step,
    summary.steps_over_dead_band,
    cast(printf('%.1f', coalesce(summary.step_ft_p50, 0.0)) as double)
        as step_ft_p50,
    cast(printf('%.1f', coalesce(summary.step_ft_p95, 0.0)) as double)
        as step_ft_p95,
    cast(printf('%.1f', coalesce(summary.step_ft_max, 0.0)) as double)
        as step_ft_max
from shared
cross join summary
