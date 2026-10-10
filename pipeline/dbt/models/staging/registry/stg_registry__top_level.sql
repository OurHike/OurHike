-- Every top-level entry of sources.json, in the file's order, with what
-- kind of block it is. A key ending `_licence`, `_support` or `_store`
-- whose value is an object is a block: a fact about an organization, joined
-- to its steward by `author` (or `also_covers`, #1432) in int_sources__
-- stewards and int_sources__registered. Every other entry is kept, with a
-- null `block_kind`, because staging filters nothing (decision 40).
--
-- The order matters: export_sources.py's `_block` takes the first block in
-- the file that names a steward, so `entry_position` is the tie-break.
with registry as (
    select * from {{ ref('base_registry__sources') }}
),

entries as (
    select
        unnest(
            map_entries(cast(document_json as map (varchar, json)))
        ) as entry,
        generate_subscripts(
            map_keys(cast(document_json as map (varchar, json))), 1
        ) as entry_position
    from registry
),

named as (
    select
        struct_extract(entry, 'key') as entry_name,
        entry_position,
        struct_extract(entry, 'value') as entry_value
    from entries
)

select
    entry_name,
    entry_position,
    case
        when json_type(entry_value) != 'OBJECT' then null
        when ends_with(entry_name, '_licence') then 'licence'
        when ends_with(entry_name, '_support') then 'support'
        when ends_with(entry_name, '_store') then 'store'
    end as block_kind,
    json_extract_string(entry_value, '$.author') as author,
    case
        when json_type(json_extract(entry_value, '$.also_covers')) = 'ARRAY'
            then cast(json_extract(entry_value, '$.also_covers') as varchar[])
        else []
    end as also_covers,
    entry_value
from named
