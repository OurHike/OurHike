-- sources.json's `org_marks.orgs`, one row per provider: where OurHike's ask
-- for that organization's mark stands (#933), in the block's own
-- `state_vocabulary`.
with registry as (
    select * from {{ ref('base_registry__sources') }}
),

marks as (
    select
        unnest(map_entries(cast(
            json_extract(document_json, '$.org_marks.orgs')
            as map (varchar, json)
        ))) as mark_entry
    from registry
)

select
    struct_extract(mark_entry, 'key') as provider,
    json_extract_string(
        struct_extract(mark_entry, 'value'), '$.state'
    ) as mark_state
from marks
