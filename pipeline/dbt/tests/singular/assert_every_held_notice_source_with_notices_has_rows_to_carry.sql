-- A HELD NOTICE SOURCE WHOSE NOTICES WERE READ KEEPS ROWS IN THE MARTS, OR
-- conditions/notices.json KEEPS ITS LAST COPY (review finding DBT-10 of PR
-- #1805 — dlt → dbt re-platform as one go/no-go change, with decision 81).
-- A notice source int_closures__gate holds although this build read rows of
-- it carries its last good rows (int_closures__held_carried, and
-- int_closures__window_carried for a feed). Where the row history holds none
-- (a cold start, or no build of this history ever passed it), the marts hold
-- no row of it, and pub_conditions_notices then writes nothing rather than
-- publish that club as having no notices: the phone keeps its last file
-- whole. This names each such source, so that file standing still is never
-- silent.
--
-- Returns one row per notice source that may publish, is held, had rows
-- this build, and has no row in the closures or warnings mart. Warns, never
-- fails: every other file still publishes. `holds_a_source` makes
-- build_marts.py print these rows and turn the run red after the publish
-- (its PARTIAL_EXIT).
{{ config(severity='warn', meta={'holds_a_source': true}) }}

with notice_sources as (
    select distinct source_key
    from {{ ref('notice_readers') }}
),

in_the_marts as (
    select source_key from {{ ref('closures', v=1) }}
    union distinct
    select source_key from {{ ref('warnings', v=1) }}
),

gate as (
    select * from {{ ref('int_closures__gate') }}
)

select
    gate.source_key,
    gate.rows_total,
    gate.held_because
from gate
inner join notice_sources on gate.source_key = notice_sources.source_key
left join in_the_marts on gate.source_key = in_the_marts.source_key
where
    not gate.passed
    and gate.may_publish
    and gate.rows_total > 0
    and in_the_marts.source_key is null
