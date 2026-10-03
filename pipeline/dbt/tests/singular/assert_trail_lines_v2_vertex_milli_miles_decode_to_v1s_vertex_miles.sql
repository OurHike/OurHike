-- trail_lines v2's whole thousandths of a mile, each divided back by 1,000,
-- are v1's vertex miles exactly, double for double, on every line (stage 6
-- of #1793). That division is what client/src/lib/trailMiles.ts does to
-- v2/trail_miles.json, and IEEE 754 rounds it to the double nearest the
-- quotient; v1's file prints each mile so that JSON.parse reads back the
-- same double. So a row here is a vertex whose mile a v2 phone would hold
-- differently from a v1 phone: a mile not rounded at 3 decimals, which
-- thousandths cannot carry. A mile is a safety field (pipeline/ELT.md, "The
-- eleven marts"), so any row fails the build. Returns no rows.
with v1 as (
    select
        trail_line_id,
        vertex_miles
    from {{ ref('trail_lines', v=1) }}
),

v2 as (
    select
        trail_line_id,
        vertex_milli_miles,
        list_transform(vertex_milli_miles, lambda k: k / 1000) as decoded
    from {{ ref('trail_lines', v=2) }}
)

select
    v1.trail_line_id,
    v1.vertex_miles,
    v2.vertex_milli_miles
from v1
full outer join v2 on v1.trail_line_id = v2.trail_line_id
where
    v1.trail_line_id is null
    or v2.trail_line_id is null
    or (v1.vertex_miles is null) != (v2.vertex_milli_miles is null)
    or v2.decoded != v1.vertex_miles
