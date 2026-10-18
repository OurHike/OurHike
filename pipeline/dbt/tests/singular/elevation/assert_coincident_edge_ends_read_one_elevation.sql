-- Where every edge-end meeting at a junction is the same published
-- coordinate, the ends read one DEM point, so their published elevations are
-- one value and the node has no step (;
-- export_network_profile.measure_seams: "a node whose incident ends are all
-- the SAME published coordinate has no step by construction, because the
-- same lon/lat reads the same DEM pixel"). That is what lets a consumer
-- holding trail_graph_geometry.json tell an honest join from an 8 m snap by
-- comparing two coordinates, which the profile's docstring offers as the
-- way to recover most of the per-edge chopping's under-count.
--
-- Each row is such a node with a step: an edge's end sample no longer read
-- at its published end vertex. A warning, not an error, because it can also
-- fire without a defect: an end sample round-trips through EPSG:5070 and
-- back, and the sampler answers by 6-decimal key, so two readings of one
-- vertex could in principle straddle a key or a pixel edge; the odds are
-- about one in 10^8 a node (Reasoned from a ~1e-14 degree round trip against
-- 1e-6 degree keys, never seen), and the build should not stop for them.
-- An error when every coincident node has a step (macros/test_levels.sql's
-- named_rows_level(), over `total_rows`, the
-- coincident nodes): the sampler, not a pixel edge.
{{ config(
    fail_calc=named_rows_level(),
    warn_if='>0',
    error_if='>1',
    meta={'scores_a_level': true}
) }}
with totals as (
    select count(*) as total_rows
    from {{ ref('int_elevation__seam_nodes') }}
    where coincident
)

select
    seam.node_id,
    seam.incident_ends,
    seam.measured_ends,
    seam.step_ft,
    totals.total_rows
from {{ ref('int_elevation__seam_nodes') }} as seam
cross join totals
where seam.coincident and seam.step_ft > 0
