-- The warnings that are not organization notices (pipeline/ELT.md's warnings
-- mart, decision 2): NWS's relayed alerts and OurHike's serious reports, one
-- row each, by name, nothing filtered. The warnings mart adds the notices
-- int_closures__unioned holds that do not block the trail.
-- No hazard POI branch: ELT.md's ledger, "No hazard POI exists to port".
with nws as (
    select * from {{ ref('int_warnings__nws_relayed') }}
),

reports as (
    select * from {{ ref('int_warnings__serious_reports') }}
)

select * from nws

union all by name

select * from reports
