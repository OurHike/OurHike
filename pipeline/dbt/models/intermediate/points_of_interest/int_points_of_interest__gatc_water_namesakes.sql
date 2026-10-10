{{ config(materialized='table') }}
-- ATC's own points that name the place a GATC water source is at (the
-- gatc_water_atc_names seed, reviewed row by row), each with its point.
-- int_points_of_interest__gatc_water reads each onto ATC's mile axis and
-- holds a placed source whose mile disagrees with its namesake's (decision
-- 75). One row per seed row per ATC point carrying that Name in that layer:
-- a Name ATC uses twice gives two rows, and the check takes the one nearer
-- GATC's mile. A seed row whose Name ATC no longer carries gives none, and
-- checks nothing (assert_gatc_water_names_find_both_halves warns).
--
-- ATC publishes no water layer: WATER_SOURCES.md §4 swept all 146 ATC-org
-- services for one, and its index (CSI) says how far water is, never where.
-- So a GATC source is checked against the shelter, campsite or road gap's
-- parking area it is named for.
with names as (
    select * from {{ ref('gatc_water_atc_names') }}
),

atc as (
    select
        'shelters' as atc_layer,
        name,
        globalid,
        geom
    from {{ ref('stg_atc__shelters') }}
    union all by name
    select
        'campsites' as atc_layer,
        name,
        globalid,
        geom
    from {{ ref('stg_atc__campsites') }}
    union all by name
    select
        'parking' as atc_layer,
        name,
        globalid,
        geom
    from {{ ref('stg_atc__parking') }}
)

select
    names.gatc_mile,
    names.entry_starts,
    names.atc_layer,
    names.atc_name,
    atc.globalid as atc_global_id,
    atc.geom as atc_geom
from names
inner join atc
    on
        names.atc_layer = atc.atc_layer
        and names.atc_name = atc.name
where atc.geom is not null
