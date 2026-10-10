{{ config(materialized='table') }}
-- NO PROSE IS PUBLISHED (decision 55; pipeline/ELT.md, phase C). One row per
-- text value of a club notice that holds its source's own wording: a value
-- int_warnings__notice_wording_unioned collected from that source's base
-- model, which its staging model does not carry. Each row holds that source
-- in int_closures__gate (decision 81; review finding ARCH-1 of PR #1805 —
-- dlt → dbt re-platform as one go/no-go change), so its paragraphs never
-- reach a mart and it carries its last good rows, while every other source
-- and file publishes. Its test warns, so the log names the rows and the run
-- turns red after publishing (build_marts.py's PARTIAL_EXIT). Until decision
-- 81 the test failed the build, which stopped every hourly file: soak run
-- 530 published nothing over two wi_dnr_park_closures titles.
--
-- WHAT IT COMPARES. Each value of a club notice row the finals could publish
-- is read as words (notice_wording_text(): tags cut, whitespace folded), and
-- it leaks when it contains a whole wording value of its own source. Those
-- rows are int_closures__unioned's and int_warnings__unioned's club branches,
-- every column the finals take from them, before the gate: the gate reads
-- this model, so it cannot read the finals the gate decides. A row
-- int_closures__club_notices holds as not current (`notice_held_because`)
-- is never published, so it is not read. Every pub_conditions_* writer reads
-- a club notice only through the marts (tests/test_generated_notice_models.py
-- holds that no writer reads a club notice model), so this covers the files
-- too. Only rows of the club notice sources are read: no other branch reads
-- their base models, so no other row can hold their words.
--
-- WHAT IT MISSES, said so: a part of a paragraph shorter than the whole
-- value, and a value shorter than notice_is_wording()'s threshold
-- (@unvalidated). A value one of its source's facts already holds, such as
-- a description identical to the title or a place's name a title names, in
-- its own row or another, is not wording (the union leaves it out), so a
-- title can never fail on text the source's facts already carry. A row
-- carried from the row history (int_closures__window_carried,
-- int_closures__held_carried) is not read again: it was read here in the
-- build that first held it (Reasoned: every mart row passed this check, at
-- severity error before decision 81, as a gate hold since).
with wording as (
    select distinct
        source_key,
        wording
    from {{ ref('int_warnings__notice_wording_unioned') }}
),

-- Unqualified, from a subquery: `to_json(final_row)` names the row, which
-- dbt lint's RF03 and AL05 read as an unqualified reference and an unused
-- alias unless every reference beside it is unqualified too. A closures-type
-- notice lands in the closures mart only where it obstructs the trail, and
-- in the warnings mart otherwise (decision 7), so `mart` says which.
published as (
    select
        case when obstructs_trail then 'closures' else 'warnings' end as mart,
        notice_id as row_id,
        source_key,
        to_json(final_row) as row_json
    from (
        select * exclude (notice_held_because, geom_geojson)
        from {{ ref('int_closures__unioned') }}
        where
            starts_with(notice_kind, 'club_')
            and notice_held_because is null
    ) as final_row
    union all
    select
        'warnings' as mart,
        notice_id as row_id,
        source_key,
        to_json(final_row) as row_json
    from (
        select * exclude (notice_held_because, geom_geojson)
        from {{ ref('int_warnings__unioned') }}
        where
            starts_with(notice_kind, 'club_')
            and notice_held_because is null
    ) as final_row
),

-- Every text value but the geometry: `geom_geojson` is a coordinate string,
-- which no wording can be, and it was most of what this searched (22,073,095
-- of 24,101,736 characters of UA run 538's notices.json, read in the review
-- of PR #1805 — dlt → dbt re-platform as one go/no-go change, 2026-10-05).
-- `published` leaves it out before a row becomes JSON, so it is never even
-- written out: since decision 81 this runs before the gate, on the path every
-- mart and writer waits for (soak run 539, publish-conditions.yml
-- 37254930168, built it in 21.05 s, then after the finals).
published_values as (
    select
        published.mart,
        published.row_id,
        published.source_key,
        entry.key as column_name,
        {{ notice_wording_text("json_extract_string(entry.value, '$')") }}
            as published_text
    from published
    cross join json_each(published.row_json) as entry
    where json_type(entry.value) = 'VARCHAR' and entry.key != 'geom_geojson'
)

select
    {{ dbt_utils.generate_surrogate_key([
        'published_values.mart',
        'published_values.row_id',
        'published_values.column_name',
        'wording.wording',
    ]) }} as leak_key,
    published_values.mart,
    published_values.row_id,
    published_values.column_name,
    published_values.source_key,
    wording.wording
from published_values
inner join wording
    on
        published_values.source_key = wording.source_key
        and contains(published_values.published_text, wording.wording)
