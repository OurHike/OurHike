{{ config(materialized='table') }}
-- Every club notice that closes an AREA, as the source drew it: the areas
-- decision 187 (S6, poll of 2026-10-11) crosses out the trails of,
-- where they run inside, in conditions/trail_closures.json. One row per
-- notice, with its own area made valid and its bounding box.
-- step_closure_trail_lines (pipeline/step_closure_trail_lines.py) reads the
-- boxes, to land only the release's nearby trail lines that may run inside
-- one, and int_closures__area_trail_cuts cuts those lines against the areas.
--
-- THE SOURCE'S OWN AREA, NOT THE PHONE'S. conditions/notices.json carries an
-- area grown 100 m outward so that a route passing near it is
-- shown the notice; that margin is for showing a notice rather than missing
-- it, and it would cross out 100 m of open trail past the closure's edge. So
-- the cut is against the area as the source drew it, as NYS Parks' areas are
-- cut monthly (int_trail_lines__network_area_closures), and a closed park's
-- trails are crossed out exactly where the park is closed.
--
-- THE SAME ROWS AS pub_conditions_notices, OR MORE: the closures mart's rows
-- and the warnings mart's club notices (`warning_kind = 'org_notice'`), of a
-- source seeds/notice_readers.csv names, whose own `obstructs_trail` is true,
-- ATC's excepted (ATC's own band draws those, from
-- conditions/atc_updates.json). That writer marks a row obstructing when the
-- mart's `obstructs_trail` is true and the source is not one of decision 67's
-- hazard areas, so every area it marks obstructing is a row here (Reasoned
-- from its SQL), and pub_conditions_trail_closures, which takes its rows from
-- that writer's file, never meets an obstructing area with no row here. A
-- hazard source's rows never obstruct in the marts either
-- (assert_a_hazard_area_never_closes_a_trail).
--
-- AN AREA IS A GEOMETRY OF DIMENSION 2 once made valid, the test
-- macros/notice_phone_geometry.sql applies before it grows one, so the rows
-- here are the ones conditions/notices.json carries as a Polygon or a
-- MultiPolygon. Made valid as pub_conditions_notices makes it valid (its
-- header has why: one source's ring crossed itself, soak run 531), and then
-- only its polygons kept (ST_CollectionExtract), so a line that making it
-- valid left beside them is not closed ground. An area left empty by either
-- closes nothing a line could run inside, so it is left out, which also
-- keeps an empty geometry away from ST_Intersects (the dbt skill's trap: it
-- segfaults dbt 2.0.6's DuckDB).
--
-- NOTHING HERE STOPS THE HOURLY BUILD. This builds in stage A, where a
-- failure of a model that is not one club source's own stops every
-- conditions file of the hour (build_marts.py's docstring, "ONE SOURCE OR ONE
-- WRITER NEVER STOPS THE REST"). So reading and repairing an area is wrapped
-- in TRY(), which answers null for an expression that raises (measured on
-- dbt 2.0.6's DuckDB 1.5.4, 2026-10-11), and an area that answers null is
-- left out here, as an empty one is: it stays in conditions/notices.json's
-- list and is not crossed out. pub_conditions_notices reads the same
-- geometry without TRY, so such an area would fail that writer alone, in the
-- writers' pass, where one failure is held to its own file.
with readers as (
    select distinct source_key
    from {{ ref('notice_readers') }}
),

marts as (
    select
        closure_id as notice_id,
        source_key,
        obstructs_trail,
        geom_geojson
    from {{ ref('closures', v=1) }}
    union all by name
    select
        warning_id as notice_id,
        source_key,
        obstructs_trail,
        geom_geojson
    from {{ ref('warnings', v=1) }}
    where warning_kind = 'org_notice'
),

closing as (
    select
        marts.notice_id,
        marts.source_key,
        try(st_makevalid(st_geomfromgeojson(marts.geom_geojson))) as geom
    from marts
    inner join readers on marts.source_key = readers.source_key
    where
        coalesce(marts.obstructs_trail, false)
        and marts.source_key != 'atc_trail_updates'
        and marts.geom_geojson is not null
),

areas as (
    select
        notice_id,
        source_key,
        try(st_collectionextract(geom, 3)) as geom
    from closing
    where geom is not null and st_dimension(geom) = 2
)

select
    notice_id,
    source_key,
    st_xmin(geom) as xmin,
    st_ymin(geom) as ymin,
    st_xmax(geom) as xmax,
    st_ymax(geom) as ymax,
    cast(st_asgeojson(geom) as varchar) as area_geojson
from areas
where geom is not null and not st_isempty(geom)
