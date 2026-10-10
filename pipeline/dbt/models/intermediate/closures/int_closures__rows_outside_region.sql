{{ config(materialized='table') }}
-- THE LON/LAT SWAP TEST, BEFORE THE GATE (decision 81; review finding
-- ARCH-1 of PR #1805 — dlt → dbt re-platform as one go/no-go change): one
-- row per notice, alert or closed area whose geometry reaches outside the
-- box its source publishes in, read from the two unions every closures and
-- warnings row comes from, so that int_closures__gate can hold that source
-- (`held_because`) and it carries its last good rows, while every other
-- source and file publishes. The closures and warnings marts' own tests,
-- closures_areas_land_in_the_region_their_source_publishes_in and
-- warnings_alert_areas_land_in_the_region_their_source_publishes_in, used to
-- be the only check, at severity error, so one such row stopped every hourly
-- file: soak runs 525 to 527 published nothing over 148 closure and 22
-- warning rows outside their box. They stay, at warn, on what the marts
-- still hold. The gate cannot read them: the marts are built from it.
--
-- WHICH ROWS. Every row of int_closures__unioned and int_warnings__unioned
-- that the finals could publish, which is every one but a club notice
-- int_closures__club_notices holds as not current (`notice_held_because`):
-- the rows the marts' tests read, before the gate takes any out. A row
-- carried from the row history (int_closures__window_carried,
-- int_closures__held_carried) is not read here: it was read in the build
-- that first held it, and the marts' tests still read it.
--
-- THE BOXES and what each rests on are macros/lands_outside_its_region.sql's
-- (every margin there is @unvalidated), so this model, the marts' tests and
-- the POI tests hold every source to one box.
with candidates as (
    select
        source_key,
        notice_id,
        geom_geojson
    from {{ ref('int_closures__unioned') }}
    where notice_held_because is null
    union all
    select
        source_key,
        notice_id,
        geom_geojson
    from {{ ref('int_warnings__unioned') }}
    where notice_held_because is null
),

outside as (
    {{ lands_outside_its_region(
        'candidates', 'st_geomfromgeojson(geom_geojson)', id_column='notice_id'
    ) }}
)

select
    row_id,
    source_key,
    region,
    xmin,
    xmax,
    ymin,
    ymax
from outside
