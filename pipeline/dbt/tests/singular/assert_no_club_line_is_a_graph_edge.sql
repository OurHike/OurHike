-- "Draw now, route later" (the maintainer, 2026-10-04): a club's own line
-- draws on the map
-- and never routes until a dedupe step has checked it against the lines
-- already there, which is not built. A club line that reached the junction
-- graph could carry a route along one copy of a trail and back along
-- another, or down a line nobody has compared with the network. Returns one
-- row per graph edge, or routable line part, made from a club line.
-- A gate on a mart a hiker's safety reads (dbt_project.yml's
-- `marts:` gates): an error in every environment, so in production a
-- failure holds the files below at their last good copy.
{{ config(severity='error') }}
select
    'edge' as what,
    edges.edge_id as id,
    trail_line.trail_line_id
from {{ ref('trail_network', v=1) }} as edges
inner join {{ ref('trail_lines', v=1) }} as trail_line
    on edges.trail_id = trail_line.published_id
where trail_line.line_kind = 'club'
union all
select
    'routable part' as what,
    routable.part_id as id,
    trail_line.trail_line_id
from {{ ref('int_trail_network__routable') }} as routable
inner join {{ ref('trail_lines', v=1) }} as trail_line
    on routable.trail_id = trail_line.published_id
where trail_line.line_kind = 'club'
