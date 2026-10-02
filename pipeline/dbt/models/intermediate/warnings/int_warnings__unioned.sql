-- The warnings that are not organization notices (pipeline/ELT.md's warnings
-- mart, decision 2): NWS's relayed alerts and OurHike's serious reports, one
-- row each, by name, nothing filtered. The warnings mart adds the notices
-- int_closures__unioned holds that do not block the trail.
--
-- HAZARD POIS ARE THE THIRD BRANCH OF DECISION 2, AND ARE NOT HERE YET. No
-- type in lib/poi_schema.py's POI_TYPES is a hazard, DEC's FORD is held back
-- (ELT.md's PO31), and the points_of_interest mart they would come from is
-- being rebuilt in its own stage. When a hazard type exists, its branch goes
-- here, reading points_of_interest from the monthly build through --defer
-- (ELT.md, "Three clocks"), shaped as the two below are:
--     union all by name
--     select 'points_of_interest:' || poi_id as notice_id, ...,
--         'hazard_poi' as notice_kind, false as obstructs_trail, ...
--     from ref('points_of_interest') where poi_type in (<the hazard types>)
-- It has no parity baseline, because nothing publishes a hazard today
-- (ELT.md's warnings ledger: "a new rule with no parity baseline").
with nws as (
    select * from {{ ref('int_warnings__nws_relayed') }}
),

reports as (
    select * from {{ ref('int_warnings__serious_reports') }}
)

select * from nws

union all by name

select * from reports
