{{ config(materialized='table') }}
-- Each junction-graph edge's climb, [gain, loss] in whole feet, or nothing:
-- one row per edge of int_trail_network__edges. EL10 and EL11 of
-- pipeline/ELT.md's ledger, the SQL form of
-- export_network_elevation.edge_climb over lib/elevation_gain.py's dead band
-- (macros/dead_band_gain.sql). trail_graph_elevation.json is written from it
-- (pub_trail_graph_elevation), and the trail_network mart is planned to carry
-- it as climb_gain_ft and climb_loss_ft (ELT.md, "The eleven marts").
--
-- IN FEET BEFORE THE DEAD BAND: the DEM's metres over
-- elevation_metres_per_foot, unrounded, then the 3 m dead band in feet
-- (elevation_gain_threshold_m over the same foot), as edge_climb converts
-- once, before either sum, "because a threshold applied in the wrong unit is
-- a different threshold". Each unbroken run of samples is measured on its
-- own, so a DEM gap inside an edge adds nothing: that under-counts by
-- whatever happened inside the gap, the honest direction, and
-- partially_covered says which edges it applies to. Loss is the same dead
-- band on the ground turned over, as a positive number. Both are rounded to
-- the nearest whole foot as Python's round() rounds them (printf('%.0f')),
-- so an edge's climb can read up to half a foot under or over its unrounded
-- figure. That is today's rounding, kept for parity, and it is not toward
-- caution: half a foot an edge, either way, on a route the phone sums edge
-- by edge. Rounding gain up would be the cautious direction for a hiker's
-- time estimate; nobody has decided to change it.
--
-- WITHIN AN EDGE, NEVER ACROSS A NODE JOIN. Each edge is measured from its
-- own samples only; the phone sums edges. There is no concatenated profile
-- for a seam to hide in (#559's ~36,800 ft of phantom climb).
--
-- AN EDGE NOBODY MEASURED HAS NO CLIMB, never [0, 0]: an edge with no sample
-- the DEM answered has gain_ft and loss_ft null. "This edge is flat" and
-- "nobody has measured this edge" are different claims, and a route with
-- one null edge has no climb figure on the phone.
--
-- may_publish is the edge's source's (int_sources__publication), carried
-- for pub_trail_graph_elevation, which publishes no climb for an edge whose
-- source may not publish. Every graph edge comes from a line that may, so it
-- is a second lock; a source the registry does not list may not.
with edges as (
    select
        edge_id,
        edge_index,
        source_key
    from {{ ref('int_trail_network__edges') }}
),

samples as (
    select
        edge_id,
        count(*) as sample_count,
        count(elevation_m) as measured_sample_count,
        list(
            elevation_m
            / cast('{{ var("elevation_metres_per_foot") }}' as double)
            order by sample_index
        ) as elevations_ft
    from {{ ref('int_elevation__edge_samples') }}
    group by edge_id
),

publication as (
    select
        source_key,
        may_publish
    from {{ ref('int_sources__publication') }}
),

climbed as (
    select
        edge_id,
        sample_count,
        measured_sample_count,
        {{ dead_band_gain('elevations_ft', elevation_gain_threshold_ft()) }}
            as gain,
        {{ dead_band_gain(
            'list_transform(elevations_ft, lambda foot: -foot)',
            elevation_gain_threshold_ft()
        ) }} as loss
    from samples
)

select
    edges.edge_id,
    edges.edge_index,
    edges.source_key,
    coalesce(climbed.sample_count, 0) as sample_count,
    coalesce(climbed.measured_sample_count, 0) as measured_sample_count,
    case
        when climbed.measured_sample_count > 0
            then cast(printf('%.0f', climbed.gain) as integer)
    end as gain_ft,
    case
        when climbed.measured_sample_count > 0
            then cast(printf('%.0f', climbed.loss) as integer)
    end as loss_ft,
    coalesce(climbed.measured_sample_count > 0, false) as measured,
    coalesce(
        climbed.measured_sample_count > 0
        and climbed.measured_sample_count < climbed.sample_count,
        false
    ) as partially_covered,
    coalesce(publication.may_publish, false) as may_publish
from edges
left join climbed on edges.edge_id = climbed.edge_id
left join publication on edges.source_key = publication.source_key
