-- reference/trail_name_aliases.json's `trails`, one row per published
-- spelling: which long trail a source's own spelling is (TL21), the
-- reviewed half of export_nearby_trails.py's _alias_index(). USFS's five
-- spellings of the Continental Divide are one trail through this table, and
-- client/src/map/longTrailNames.ts is the same table on the client
-- (tests/test_trail_name_aliases.py keeps the two in step).
--
-- Exact on the publisher's spelling, never a prefix: a road named after a
-- trail is not the trail, and that refusal is the file's, not this model's.
-- The test on (source_key, published_spelling) stops the build where two
-- entries claim one spelling, which _alias_index() would answer with the
-- later entry, silently.
with aliases_document as (
    select document_json from {{ ref('base_ourhike__trail_name_aliases') }}
),

trail_entries as (
    select
        unnest(
            map_entries(
                cast(
                    json_extract(document_json, '$.trails')
                    as map (varchar, json)
                )
            )
        ) as trail_entry
    from aliases_document
),

trails as (
    select
        struct_extract(trail_entry, 'key') as alias_key,
        json_extract_string(
            struct_extract(trail_entry, 'value'), '$.trail'
        ) as trail_name,
        json_extract(
            struct_extract(trail_entry, 'value'), '$.published_as'
        ) as published_as
    from trail_entries
),

source_spellings as (
    select
        alias_key,
        trail_name,
        unnest(
            map_entries(cast(published_as as map (varchar, varchar[])))
        ) as source_entry
    from trails
)

select
    alias_key,
    struct_extract(source_entry, 'key') as source_key,
    unnest(struct_extract(source_entry, 'value')) as published_spelling,
    trail_name
from source_spellings
