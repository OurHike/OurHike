-- reference/podcast_episodes.json (_shared/podcasts/episodes.py): every row
-- of the file, keyed (decision 40), with nothing filtered and nothing joined.
-- Each row is still the JSON its reviewer wrote: reading its fields is the
-- gate's work (int_podcasts__checked), because a field's JSON type is one of
-- the things the gate checks.
--
-- Key: the file and the row's place in it, unique by construction, since a
-- reviewed file has no other id every row is sure to carry (spotify_id is
-- what the gate checks for).
with source as (
    select * from {{ source('podcasts', 'raw_podcasts__podcast_episodes') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/podcast_episodes.json'",
            '_row',
        ]) }} as episode_row_key,
        _row as file_row,
        cast(row_json as json) as episode,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='episode_row_key', order_by='_dlt_id'
) }}
