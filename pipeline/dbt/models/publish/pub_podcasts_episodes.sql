{{ config(format='json', location='podcasts_episodes.json') }}
-- podcasts/episodes.json, the list client/src/lib/podcasts.ts reads, in the
-- shape export_podcasts.py's build_document() writes: the source file's path
-- and the episodes, in the file's order. `minutes` is left out of an episode
-- that has none rather than written as null (as_published's absent-means-
-- unknown rule): json_merge_patch drops a member a patch sets to null.
with podcasts as (
    select * from {{ ref('podcasts') }}
),

episodes as (
    select
        list_position,
        json_merge_patch(
            json_object(
                'spotify_id', spotify_id,
                'title', title,
                'show', show_name,
                'hikes', hikes,
                'at_miles', at_miles,
                'pois', pois,
                'links', to_json(links)
            ),
            json_object('minutes', minutes)
        ) as episode
    from podcasts
)

select
    -- export_podcasts.py's own literal.
    'reference/podcast_episodes.json' as source,
    -- An empty list is [], never null (pipeline/ELT.md's pitfall 2).
    coalesce(list(episode order by list_position), []) as episodes
from episodes
