-- sources.json's `organizations.orgs`, one row per organization, keyed by
-- the stable steward id #929 introduced and carrying the registry's
-- `provider` it stands for. 30 on 2026-10-01, one per provider.
with registry as (
    select * from {{ ref('base_registry__sources') }}
),

orgs as (
    select
        unnest(map_entries(cast(
            json_extract(document_json, '$.organizations.orgs')
            as map (varchar, json)
        ))) as org
    from registry
)

select
    struct_extract(org, 'key') as steward_id,
    json_extract_string(struct_extract(org, 'value'), '$.provider') as provider,
    json_extract_string(struct_extract(org, 'value'), '$.name') as org_name,
    json_extract_string(struct_extract(org, 'value'), '$.note') as org_note,
    json_extract_string(struct_extract(org, 'value'), '$.state') as org_state
from orgs
