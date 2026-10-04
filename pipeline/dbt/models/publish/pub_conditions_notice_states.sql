{{ config(
    format='json',
    location='conditions_notice_states.json',
    meta={'when_empty': 'keep_last_file'},
) }}
-- conditions/notice_states.json (decision 76): the shape of every state a
-- state-wide agency notice names, from int_closures__notice_state_shapes,
-- one object each: its code (`state`, as conditions/notices.json's `states`
-- names it), its name, the margin the phone holds a route to
-- (`edge_margin_m`) and the simplified shape. client/src/lib/
-- publishedNotices.ts reads it beside conditions/notices.json, and
-- lib/plannedNotices.ts shows a state-wide notice to a hike planned inside
-- one of its states. No map draws a shape.
--
-- A FILE OF ITS OWN, so its bytes hold between builds: notices.json changes
-- every hour, and a phone would download every shape again with it.
-- `generated_at` is when the extract landed TIGER's file, not this build's
-- clock, so a build that changes nothing writes the same bytes, its ETag
-- holds, and a phone revalidating gets a 304. It changes when Census
-- republishes or the seed names another state.
--
-- NOTHING IS WRITTEN WHILE THERE IS NO SHAPE, and the phone keeps its last
-- file: a warehouse without TIGER's table (the fixture build, or a month the
-- extract refused it) would otherwise publish an empty list, which hides
-- every state-wide notice until the next month.
with shapes as (
    select * from {{ ref('int_closures__notice_state_shapes') }}
)

select
    {{ python_utc_seconds('max(_loaded_at)') }} as generated_at,
    to_json(
        list(
            json_object(
                'state', state,
                'name', state_name,
                'edge_margin_m', edge_margin_m,
                'geometry', phone_geometry
            )
            order by state
        )
    ) as states
from shapes
having count(*) > 0
