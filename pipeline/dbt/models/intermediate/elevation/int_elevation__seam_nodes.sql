-- The vertical step at every junction two or more edge-ends meet at: one row
-- per such node. EL13 of pipeline/ELT.md's ledger, the per-node half of
-- export_network_profile.measure_seams; int_elevation__seam_measurement
-- sums it into the numbers trail_graph_profile_manifest.json reports.
--
-- THE HAZARD, MEASURED ON EVERY BUILD. build_trail_graph.py's
-- ENDPOINT_SNAP_M = 8.0 joins ends that stop short of each other, so two
-- edges sharing a node can sit metres apart on the ground and an unmeasured
-- distance apart vertically. A route profile concatenated across such a join
-- reads the step as climbing, which is #559 arriving in a new artifact; so
-- the profile is per edge, route climb comes from trail_graph_elevation.json,
-- and this says how big the steps are.
--
-- `coincident` is true where every incident end is the same published
-- coordinate, compared as trail_graph_geometry.json writes it (its 6
-- decimals, as the doubles they parse to): there the ends read one DEM point
-- and have no step by construction
-- (assert_coincident_edge_ends_read_one_elevation). Steps are in the whole
-- feet trail_graph_profile.json publishes, from each edge's first and last
-- sample, because feet are what a consumer would sum. An edge the DEM never
-- answered contributes ends with no elevation, as its profile is null; a
-- node with fewer than two measured ends has no step, since one measured end
-- cannot disagree with anything. An edge with no vertex has no ends.
with edges as (
    select
        edge_id,
        from_node,
        to_node,
        cast(json_extract(geom_geojson, '$.coordinates') as double[][])
            as coordinates
    from {{ ref('int_trail_network__edges') }}
),

-- Each edge's published first and last sample, null where its profile is
-- null (no sample the DEM answered) or the sample is a hole.
profiled as (
    select
        edge_id,
        max(case when sample_index = 0 then elevation_ft end) as first_ft,
        max(case when last_sample then elevation_ft end) as last_ft,
        count(elevation_ft) > 0 as published
    from (
        select
            edge_id,
            sample_index,
            elevation_ft,
            sample_index = max(sample_index) over (partition by edge_id)
                as last_sample
        from {{ ref('int_elevation__edge_samples') }}
    ) as samples
    group by edge_id
),

ends as (
    select
        edges.from_node as node_id,
        list_extract(edges.coordinates, 1) as coordinate,
        case when profiled.published then profiled.first_ft end as elevation_ft
    from edges
    left join profiled on edges.edge_id = profiled.edge_id
    where len(edges.coordinates) > 0
    union all
    select
        edges.to_node as node_id,
        list_extract(edges.coordinates, -1) as coordinate,
        case when profiled.published then profiled.last_ft end as elevation_ft
    from edges
    left join profiled on edges.edge_id = profiled.edge_id
    where len(edges.coordinates) > 0
)

select
    node_id,
    count(*) as incident_ends,
    count(distinct coordinate) = 1 as coincident,
    count(elevation_ft) as measured_ends,
    case
        when count(elevation_ft) > 1
            then cast(max(elevation_ft) - min(elevation_ft) as double)
    end as step_ft
from ends
group by node_id
having count(*) > 1
