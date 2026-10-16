-- Absence reported loudly: build_trail_graph.py's main() prints a
-- WARNING when trails.geojson is missing, because a graph without the A.T.
-- still routes every other trail but refuses a tap on the widest line on the
-- map with "that tap isn't on a marked hiking route", which there is false.
-- The A.T. is absent from the network's lines by design (the route owner's
-- line wins), so its own centerline and side trails are the only way it
-- reaches the graph. It holds or it does not, so its warning and its error
-- are the same row: an error in dev and CI, and in
-- production and UA a warning that build_marts.py reports as an error, red
-- after the publish, while the rest of the graph still routes, as the
-- Python's warning let it. Returns a row when no A.T. part is routable.
select count(*) as at_parts
from {{ ref('int_trail_network__routable') }}
where is_at and refused_because is null
having count(*) = 0
