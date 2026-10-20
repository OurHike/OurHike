-- Every gatc_water_atc_names row finds its GATC row and its ATC point, so
-- each check the measurement rests on still runs (the seed's
-- description). A row that finds neither checks nothing: a GATC republish
-- that moved a mile or reworded a name, or an ATC renamed point, turns a
-- checked source into an unchecked one with every other test green. Warns,
-- because the source still ships on the measurement as a whole; the row is
-- for a person to re-pair or remove. An error when no row pairs
-- (macros/test_levels.sql's named_rows_level(), over `total_rows`, the
-- seed's rows): a republish that moved everything, not a name to re-pair.
-- Asked only of a build that holds GATC's rows: the fixture warehouse never
-- does (its table is read off a PDF).
{{ config(
    fail_calc=named_rows_level(),
    warn_if='>0',
    error_if='>1',
    meta={'scores_a_level': true}
) }}
with names as (
    select * from {{ ref('gatc_water_atc_names') }}
),

sources as (
    select * from {{ ref('stg_gatc__water_sources') }}
),

namesakes as (
    select * from {{ ref('int_points_of_interest__gatc_water_namesakes') }}
),

landed as (
    select count(*) as gatc_rows from sources
),

totals as (
    select count(*) as total_rows from names
),

gatc_halves as (
    select distinct
        names.gatc_mile,
        names.entry_starts
    from names
    inner join sources
        on
            names.gatc_mile = sources.mile_text
            and starts_with(sources.entry, names.entry_starts)
),

atc_halves as (
    select distinct
        gatc_mile,
        entry_starts
    from namesakes
)

select
    names.gatc_mile,
    names.entry_starts,
    gatc_halves.gatc_mile is not null as has_gatc_row,
    atc_halves.gatc_mile is not null as has_atc_point,
    totals.total_rows
from names
cross join landed
cross join totals
left join gatc_halves
    on
        names.gatc_mile = gatc_halves.gatc_mile
        and names.entry_starts = gatc_halves.entry_starts
left join atc_halves
    on
        names.gatc_mile = atc_halves.gatc_mile
        and names.entry_starts = atc_halves.entry_starts
where
    landed.gatc_rows > 0
    and (gatc_halves.gatc_mile is null or atc_halves.gatc_mile is null)
