{{ config(materialized='table') }}
-- club_sections.json's clubs and its unattributed miles, lib/club_sections.
-- assemble(): one row per club the centerline names, south to north, with
-- its stretches from int_trail_lines__club_stretches, and one row,
-- `section_key` '(unattributed)', for the runs no club is named for, which
-- are published rather than dropped ("41 miles the fresh source cannot name
-- reads as 'not recorded'; leaving it out would read as 'no trail here'").
--
-- TL26, NAMES FROM THE POLYGONS ONLY, through int_trail_lines__club_names: a
-- club the polygons do not name, or name with no text, keeps its acronym as
-- its name, and has no region.
--
-- A club's order is its first stretch's start, then its acronym; its miles
-- the stretches' lengths summed and rounded to one decimal as Python's
-- round() does. While every marker sits on a half mile, as all 4,395 live
-- ones do (measured 2026-10-02), every length is a multiple of a quarter
-- mile and the sum is exact in any order, so it equals the Python's
-- stretch-by-stretch sum.
with stretches as (
    select * from {{ ref('int_trail_lines__club_stretches') }}
),

names as (
    select * from {{ ref('int_trail_lines__club_names') }}
),

clubs as (
    select
        acronym,
        min(start_mile) as first_start_mile,
        cast(
            format('{:.1f}', sum(end_mile - start_mile)) as double
        ) as miles,
        cast(
            to_json(list(json(stretch_json) order by run_order)) as varchar
        ) as stretches_json
    from stretches
    where acronym is not null
    group by acronym
),

unattributed as (
    select
        cast(
            coalesce(
                to_json(list(json(stretch_json) order by run_order)),
                json('[]')
            ) as varchar
        ) as stretches_json
    from stretches
    where acronym is null
)

select
    clubs.acronym as section_key,
    clubs.acronym,
    coalesce(nullif(names.club_name, ''), clubs.acronym) as club_name,
    names.region,
    clubs.miles,
    clubs.stretches_json,
    row_number() over (order by clubs.first_start_mile, clubs.acronym) - 1
        as club_order
from clubs
left join names on clubs.acronym = names.acronym
union all
select
    '(unattributed)' as section_key,
    cast(null as varchar) as acronym,
    cast(null as varchar) as club_name,
    cast(null as varchar) as region,
    cast(null as double) as miles,
    stretches_json,
    cast(null as bigint) as club_order
from unattributed
