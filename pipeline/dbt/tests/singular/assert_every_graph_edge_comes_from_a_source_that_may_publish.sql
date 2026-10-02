-- Every mart keeps only rows whose source may publish (pipeline/ELT.md, "The
-- eleven marts"), and the trail_network mart cannot filter its own rows:
-- the edges are numbered before it, and every companion file is aligned by
-- that number. So the filter is the trail_lines mart's, upstream of the
-- noding, and this holds it there. Returns one row per edge whose source
-- int_sources__publication holds back, or does not know.
select
    edges.edge_id,
    edges.source_key
from {{ ref('trail_network') }} as edges
left join {{ ref('int_sources__publication') }} as publishable
    on edges.source_key = publishable.source_key
where not coalesce(publishable.may_publish, false)
