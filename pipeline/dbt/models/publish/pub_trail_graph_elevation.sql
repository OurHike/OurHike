{{ config(format='json_document', location='trail_graph_elevation.json') }}
-- trail_graph_elevation.json, each junction-graph edge's climb, in the shape
-- export_network_elevation.write_artifact writes with json.dumps(climbs,
-- separators=(",", ":")): a bare JSON array index-aligned with
-- trail_graph.json's `edges`, entry i describing edge i, each entry
-- [gain_ft, loss_ft] in whole feet or null. The card prices a day hike's
-- climb from it, and a route with one null edge has no climb figure, so an
-- entry is null wherever nobody measured the edge, never [0, 0].
--
-- ONE ENTRY PER EDGE, IN EDGE ORDER, whatever the climbs hold: the entries
-- are int_trail_network__edges' rows by edge_index, the order trail_graph.json
-- lists them in, so a missing climb is a null in its own place and can never
-- shift edge 41's climb onto edge 40's name. Also null where the edge's
-- source may not publish (int_sources__publication): every edge in the graph
-- comes from a line that may, so that is a second lock rather than a rule
-- this file is expected to apply. The trail_network mart is planned to carry
-- these climbs (pipeline/ELT.md, "The eleven marts"); this reads
-- int_elevation__edge_climbs until it does.
--
-- THE DOCUMENT IS ONE TEXT VALUE, written verbatim (phone_file's
-- `json_document` format), because the file is a top-level array. Empty, it
-- writes [], as json.dumps([]) does.
with edges as (
    select
        edge_id,
        edge_index,
        source_key
    from {{ ref('int_trail_network__edges') }}
),

climbs as (
    select * from {{ ref('int_elevation__edge_climbs') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

entries as (
    select
        edges.edge_index,
        case
            when climbs.gain_ft is not null and publication.may_publish
                then
                    '[' || cast(climbs.gain_ft as varchar) || ','
                    || cast(climbs.loss_ft as varchar) || ']'
            else 'null'
        end as entry
    from edges
    left join climbs on edges.edge_id = climbs.edge_id
    left join publication on edges.source_key = publication.source_key
)

select
    '[' || coalesce(string_agg(entry, ',' order by edge_index), '') || ']'
        as climbs_json
from entries
