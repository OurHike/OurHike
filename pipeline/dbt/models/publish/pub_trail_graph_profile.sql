{{ config(format='json_document', location='trail_graph_profile.json') }}
-- trail_graph_profile.json, each junction-graph edge's dense profile, in the
-- shape export_network_profile.write_artifact writes with
-- json.dumps(profiles, separators=(",", ":")): a bare JSON array
-- index-aligned with trail_graph.json's `edges`, entry i describing edge i,
-- each entry the edge's samples in whole feet from its start to its end, a
-- hole in the DEM as null in its own place, or the whole entry null where
-- the DEM covers none of the edge. The ribbon on a day hike draws it; route
-- climb comes from trail_graph_elevation.json, never from summing this file
-- (export_network_profile.py's seam rule).
--
-- ONE ENTRY PER EDGE, IN EDGE ORDER, as pub_trail_graph_elevation's: the
-- entries are int_trail_network__edges' rows by edge_index, and an edge with
-- no published sample (the DEM never answered it, it has no vertex, or its
-- source may not publish, which the elevation mart applies) is null in its
-- own place. The samples come from the elevation mart's rows for the edge,
-- in seq order, each elevation_ft already the whole foot this file prints.
--
-- THE DOCUMENT IS ONE TEXT VALUE, written verbatim (phone_file's
-- `json_document` format). Empty, it writes [], as json.dumps([]) does.
with edges as (
    select
        edge_id,
        edge_index
    from {{ ref('int_trail_network__edges') }}
),

samples as (
    select
        line_id,
        seq,
        elevation_ft
    from {{ ref('elevation') }}
    where line_id != 'AT'
),

profiles as (
    select
        line_id,
        count(elevation_ft) as measured_samples,
        '['
        || string_agg(
            coalesce(cast(cast(elevation_ft as integer) as varchar), 'null'),
            ','
            order by seq
        )
        || ']' as profile
    from samples
    group by line_id
),

entries as (
    select
        edges.edge_index,
        case
            when profiles.measured_samples > 0 then profiles.profile
            else 'null'
        end as entry
    from edges
    left join profiles on edges.edge_id = profiles.line_id
)

select
    '[' || coalesce(string_agg(entry, ',' order by edge_index), '') || ']'
        as profiles_json
from entries
