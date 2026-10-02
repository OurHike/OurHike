{{ config(
    format='json',
    location='suggested_hikes.json',
    meta={'when_empty': 'keep_last_file'}
) }}
-- suggested_hikes.json, the hike shelf client/src/lib/suggestedHikesData.ts
-- reads, in the shape export_suggested_hikes.py writes it: the moment the
-- run started, the source, and each hike's shelf record in hike-number order.
-- A shelf record is SHELF_FIELDS (#1473 — The hike shelf is 85% of the cache
-- ceiling, and crossing it deletes the shelf rather than trimming it): what
-- the client reads off a shelf record, where the drawn line came from, and
-- what a finder filters on. Everything else is the hike's detail
-- (pub_suggested_hikes_detail).
--
-- ABSENT, NEVER EMPTY: a hike with no confirmed photograph carries no
-- `photo` key, and one whose walk was never priced no `climb` key (SH08).
-- Each sits in the record with the rest, and json_merge_patch removes the
-- ones absent with a null patch, and leaves a present one whole with `{}`
-- (pub_suggested_hikes_detail says why not the other way round). The fields
-- the publisher left blank stay, as null, as record_for() writes them.
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
),

shelf as (
    select
        list_position,
        json_merge_patch(
            json_object(
                'id', hike_id,
                'name', name,
                'miles', miles,
                'difficulty', difficulty,
                'author', json_object('kind', author_kind, 'name', author_name),
                'segments', segments,
                'routeProvenance', route_provenance,
                'routeGrade', route_grade,
                'routeNotes', route_notes,
                'features', features,
                'region', region,
                'park', park,
                'publishedDifficulty', published_difficulty,
                'estimatedHours', estimated_hours,
                'dogs', dogs,
                'routeType', route_type,
                'closed', closed,
                'climb',
                case
                    when climb_gain_ft is not null
                        then
                            json_object(
                                'gainFt', climb_gain_ft, 'lossFt', climb_loss_ft
                            )
                end,
                'photo',
                case
                    when photo_url is not null
                        then
                            json_object(
                                'url', photo_url,
                                'credit', photo_credit,
                                'licence', photo_licence
                            )
                end
            ),
            json_object(
                'climb',
                case when climb_gain_ft is not null then json('{}') end,
                'photo',
                case when photo_url is not null then json('{}') end
            )
        ) as record
    from hikes
)

select
    -- utc_stamp(): the UTC instant to the second, `Z`-suffixed.
    {{ python_utc_seconds('now()') }} as generated_at,
    '{{ var("suggested_hikes_source_key") }}' as source,
    list(record order by list_position) as hikes
from shelf
having count(*) > 0
