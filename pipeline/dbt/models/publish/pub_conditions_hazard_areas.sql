{{ config(
    format='json',
    location='conditions_hazard_areas.json',
    meta={'when_empty': 'keep_last_file'},
) }}
-- conditions/hazard_areas.json (decision 84, the maintainer's poll of
-- 2026-10-05, Q5: "Their own small file, read at launch"): the notices of
-- conditions/notices.json that carry decision 67's `hazard` (hunting,
-- shooting or burned_area), and no others. Decision 77 has a phone download
-- notices.json only once a hike is planned, and the map draws hunting areas,
-- shooting sites and burned areas from these rows, so a phone with nothing
-- planned drew none; client/src/lib/publishedNotices.ts reads this file at
-- launch instead, whatever is planned.
--
-- ONE HOME FOR EVERY RULE: this writer selects from pub_conditions_notices'
-- own table and keeps each hazard row exactly as that writer wrote it, so
-- the row shape (features/ORG_NOTICES.md section 2), decision 77's phone
-- geometry (macros/notice_phone_geometry.sql), the dates, the carried rows
-- of a held source and decision 76's `states` are that writer's and nothing
-- here can drift from them. The rows keep that writer's order, by
-- source_key then notice_id, and `generated_at` is that writer's stamp.
--
-- THE SAME WITHHOLDING. While pub_conditions_notices selects no row (a build
-- without the row history while a notice source is held), this selects none,
-- and the phone keeps its last copy of both files. A build whose notices hold
-- no hazard row writes an empty list: the file arrived, and no source
-- publishes a hazard area.
with document as (
    select
        generated_at,
        notices
    from {{ ref('pub_conditions_notices') }}
),

notice_rows as (
    select unnest(cast(notices as json[])) as notice
    from document
),

hazard_rows as (
    select
        notice,
        json_extract_string(notice, '$.source_key') as source_key,
        json_extract_string(notice, '$.notice_id') as notice_id
    from notice_rows
    where json_extract_string(notice, '$.hazard') is not null
),

hazard_notices as (
    select list(notice order by source_key, notice_id) as notices
    from hazard_rows
)

select
    document.generated_at,
    coalesce(to_json(hazard_notices.notices), cast('[]' as json)) as notices
from document
cross join hazard_notices
