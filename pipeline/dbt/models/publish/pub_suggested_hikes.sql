{{ config(
    format='json',
    location='suggested_hikes.json',
    meta={'when_empty': 'keep_last_file'}
) }}
-- suggested_hikes.json, the hike shelf client/src/lib/suggestedHikesData.ts
-- reads, in the shape export_suggested_hikes.py writes it: the moment the
-- run started, the source, and each shipped hike's shelf record in
-- hike-number order. Each record is the mart's `shelf_record`, built and
-- unit-tested in int_suggested_hikes__records (SH10, SH11).
--
-- NOTHING IS WRITTEN WHEN NO HIKE SHIPS (when_empty: keep_last_file).
-- "Nothing passed grading" and "there are no suggested hikes" are different
-- claims, and an empty shelf would make every phone read the second, so
-- export_suggested_hikes.py writes nothing then, and the last good file
-- stays: the same for a registry entry that does not reach hikers, an export
-- the fetch did not reach, and a graph that routes nothing.
with hikes as (
    select * from {{ ref('suggested_hikes') }}
    where phone_file = 'suggested_hikes'
)

select
    -- utc_stamp(): the UTC instant to the second, `Z`-suffixed.
    {{ python_utc_seconds('now()') }} as generated_at,
    '{{ var("suggested_hikes_source_key") }}' as source,
    list(shelf_record order by list_position) as hikes
from hikes
having count(*) > 0
