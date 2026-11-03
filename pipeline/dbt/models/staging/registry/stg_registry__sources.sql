-- sources.json's `sources`, one row per registered source, in the file's
-- order, each field typed as the registry writes it. `provider` is '' where a
-- source names none, as export_sources.py reads it (`source.get("provider",
-- "")`). `reaches_hikers` is a boolean only where the registry wrote one:
-- null otherwise, which the not_null test on it refuses, because a source
-- with no answer would put a steward on a hiker's screen, or take one off,
-- with nobody having decided which (export_sources.py's build_output()).
with registry as (
    select * from {{ ref('base_registry__sources') }}
),

entries as (
    select
        unnest(
            cast(json_extract(document_json, '$.sources') as json[])
        ) as entry,
        generate_subscripts(
            cast(json_extract(document_json, '$.sources') as json[]), 1
        ) as file_row
    from registry
)

select
    json_extract_string(entry, '$.key') as source_key,
    file_row,
    json_extract_string(entry, '$.title') as title,
    coalesce(json_extract_string(entry, '$.provider'), '') as provider,
    json_extract_string(entry, '$.steward') as steward,
    json_extract_string(entry, '$.kind') as kind,
    json_extract_string(entry, '$.trust') as trust,
    case
        when json_type(json_extract(entry, '$.reaches_hikers')) = 'BOOLEAN'
            then cast(json_extract(entry, '$.reaches_hikers') as boolean)
    end as reaches_hikers,
    json_extract_string(entry, '$.licence_basis') as licence_basis,
    json_extract_string(entry, '$.freshness.kind') as freshness_kind,
    json_extract_string(entry, '$.attribution') as attribution,
    entry
from entries
