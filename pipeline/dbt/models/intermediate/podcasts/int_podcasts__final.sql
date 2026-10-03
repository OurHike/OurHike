-- int_podcasts__final: the podcasts mart's rows before their row dates, every
-- contracted column but _first_seen_at and _changed_at. This is what
-- models/marts/podcasts/podcasts.sql held until decision 57;
-- int_podcasts__history snapshots it, and the mart reads that snapshot.
--
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
--
-- PUBLICATION: the list is OurHike's own, `ourhike_podcast_episodes` on its
-- row of unregistered_publishing_sources, and publishes only while that row
-- says it may (int_sources__publication, the one home of the rule).
with checked as (
    select * from {{ ref('int_podcasts__checked') }}
),

publication as (
    select source_key from {{ ref('int_sources__publication') }}
    where source_key = 'ourhike_podcast_episodes' and may_publish
)

select
    checked.spotify_id,
    'podcasts' as club,
    publication.source_key,
    checked._loaded_at,
    checked.title,
    checked.show_name,
    checked.minutes,
    checked.hikes,
    checked.at_miles,
    checked.pois,
    cast(checked.links as map (varchar, varchar)) as links,
    checked.file_row as list_position
from checked
cross join publication
where checked.problem is null
