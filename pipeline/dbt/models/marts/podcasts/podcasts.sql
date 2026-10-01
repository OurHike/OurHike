-- The podcast episodes picked for hikes (#1683): every row of
-- reference/podcast_episodes.json that int_podcasts__checked found no
-- problem with, in the file's order. Its test refuses a build in which any
-- row has a problem, so in a build that reaches the writers this is every
-- row of the file: a dropped episode stops the list rather than shrinking
-- it, as export_podcasts.py refuses to upload one that dropped anything.
--
-- One row per episode, keyed by its Spotify id (PC01, PC06). What the
-- reviewer wrote only for the next reviewer (`places`, `note`, `reviewed`)
-- stays out, as lib/podcasts.py's as_published() leaves it out.
with checked as (
    select * from {{ ref('int_podcasts__checked') }}
)

select
    spotify_id,
    title,
    show_name,
    minutes,
    hikes,
    at_miles,
    pois,
    cast(links as map (varchar, varchar)) as links,
    file_row as list_position
from checked
where problem is null
