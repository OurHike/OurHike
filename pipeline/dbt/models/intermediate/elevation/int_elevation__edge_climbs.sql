{{ config(materialized='table') }}
-- Each junction-graph edge's climb, [gain, loss] in whole feet, or nothing:
-- one row per edge of int_trail_network__edges. The SQL form of
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
-- whatever happened inside the gap, which is NOT the cautious direction for
-- a hiker's time estimate (int_suggested_hikes__routed says why short is the
-- dangerous side), and nothing published marks it; partially_covered says
-- which edges it applies to. How often it happens: on UA's whole network,
-- 3 of 3,551,452 edges span a DEM gap and 125 have no elevation at all (124
-- NPS, 1 CDTC), across 738 tiles (publish-vector-data.yml run 37114537637,
-- Measured 2026-10-03). The fixture's 57 of 117 is its small DEM, not
-- coverage. @unvalidated whether the 124 NPS edges are the territories and
-- Alaska, where the 1/3 arc-second product has no tile; a per-edge lookup
-- against the tile index would settle it. Loss is the same dead
-- band on the ground turned over, as a positive number.
--
-- BOTH ROUND UP TO THE WHOLE FOOT, toward caution (the
-- maintainer's poll of 2026-10-14; CLAUDE.md: "Round toward caution, and say
-- which way you rounded"). ceil(), so an edge's climb reads under one foot
-- over its unrounded figure and never under it. The phone sums a route edge
-- by edge, and more gain or more loss only ever adds time to its estimate
-- (client/src/lib/pace.ts: 600 m of ascent an hour, and a descent penalty of
-- 0 to 60 minutes per 1,000 m that only adds), so a route is never priced
-- short by the rounding. Nearest-foot rounding could put it half a foot an
-- edge under. A zero stays zero: the dead band banks no climb under 3 m, so
-- an unrounded figure is exactly 0 or at least 9.84 ft (the smallest non-zero
-- gain and loss in UA's trail_graph_elevation.json of release 2026-10-10-2
-- are both 10 ft, Measured 2026-10-14). A figure the double puts a hair over
-- a whole foot rounds up a whole foot, which errs the cautious way.
-- export_network_elevation.edge_climb, today's exporter until the cutover,
-- rounds to the nearest foot (Python's round()), so the two files differ by
-- one foot wherever that rounding went down, and by nothing else: parity.py's
-- trail_graph_elevation family explains that difference
-- (CLIMB_ROUNDED_UP_REASON) and no other. On UA's 685,963 climbing edges it
-- is about +0.5 ft each, 0.63% of all gain (Reasoned: uniform fractional
-- parts, since the unrounded figures are not published).
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
            then cast(ceil(climbed.gain) as integer)
    end as gain_ft,
    case
        when climbed.measured_sample_count > 0
            then cast(ceil(climbed.loss) as integer)
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
