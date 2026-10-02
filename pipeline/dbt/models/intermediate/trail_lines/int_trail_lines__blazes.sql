{{ config(materialized='table') }}
-- Every staged line feature's blaze, the A.T.'s and the network's, as
-- lib/blaze.py answers it (TL03): one row per feature, keyed on its staging
-- key. The two exports answer differently, and this model gives each
-- source the answer its own exporter gives today.
--
-- THE A.T.'S TWO SOURCES (centerline, side_trails), export_trails.py's
-- normalize_source_features(): normalize_blaze_color() first, then
-- map_source_blaze() on what it produced, and only where
-- reference/blaze_mapping.json has a table for the source and the decode
-- succeeded. The decode is the coded-domain label where the field has a
-- domain and the value is one of its codes; else the registry's
-- `blaze_default` when the row has no value; else 'Unknown', undecoded.
-- Neither A.T. source has a table today, so for both it is the decode alone.
-- The domains come from int_trail_lines__coded_domains (tl-at's, TL02),
-- which reads them as rows where the Python makes a live ArcGIS call.
--
-- THE NETWORK'S SOURCES, export_nearby_trails.py's resolve_blaze(). There
-- is no decode: OPRHP's `Blaze` is domain-coded but its codes are the words,
-- and NYNJTC's is a plain string, so the fetched value is what the table is
-- keyed on. A source with no `blaze_field` takes its `blaze_default`
-- ('Unknown' where it states none) and no disposition. A row whose field is
-- null is 'absent', the source declining to state a blaze, which the Python
-- counts rather than warns about. A blank string is asked of the table
-- first, because a blank a publisher means is a reviewed fact (#1207), and is
-- 'absent' unless the table maps it. Anything else is map_source_blaze() on
-- the raw value: 'mapped', 'deferred' or 'unmapped', the last being the one
-- a person has to look at. So `blaze_decoded` is true on every network row,
-- and 'absent' is a disposition only network rows carry.
--
-- A RAW VALUE MATCHES A TABLE ONLY AS TEXT, as a JSON object's keys are and
-- as Python's dict lookup is typed: a number published in a blaze column
-- never matches "1". Where the Python's map_source_blaze() would raise
-- UnknownPaint on a member outside lib/blaze.py's PALETTE and
-- NEUTRAL_MEMBERS, the accepted_values test on `blaze_color` fails the build.
with registry as (
    select * from {{ ref('stg_registry__sources') }}
),

line_sources as (
    select
        source_key,
        json_extract_string(entry, '$.blaze_field') as blaze_field,
        json_extract_string(entry, '$.blaze_default') as blaze_default
    from registry
    where
        list_contains(json_keys(entry), 'blaze_field')
        or list_contains(json_keys(entry), 'blaze_default')
),

-- reference/blaze_mapping.json's `sources`: one table per source key.
mapping_document as (
    select document_json from {{ ref('base_ourhike__blaze_mapping') }}
),

table_entries as (
    select
        unnest(
            map_entries(
                cast(
                    json_extract(document_json, '$.sources')
                    as map (varchar, json)
                )
            )
        ) as source_table
    from mapping_document
),

source_tables as (
    select
        struct_extract(source_table, 'key') as source_key,
        struct_extract(source_table, 'value') as table_json
    from table_entries
),

-- `(table.get("mapped") or {})`: a raw value and the palette member a
-- reviewer said it is. A member written as null is no mapping at all.
mapped_entries as (
    select
        source_key,
        unnest(
            map_entries(
                cast(
                    coalesce(json_extract(table_json, '$.mapped'), json('{}'))
                    as map (varchar, varchar)
                )
            )
        ) as mapped_entry
    from source_tables
),

mapped_values as (
    select
        source_key,
        struct_extract(mapped_entry, 'key') as raw_value,
        struct_extract(mapped_entry, 'value') as palette_member
    from mapped_entries
    where struct_extract(mapped_entry, 'value') is not null
),

-- `raw_value in (table.get("deferred") or {})`: values somebody has seen and
-- decided not to paint yet, each with its reason in the file.
deferred_values as (
    select
        source_key,
        unnest(
            json_keys(
                coalesce(json_extract(table_json, '$.deferred'), json('{}'))
            )
        ) as raw_value
    from source_tables
),

coded_domains as (
    select * from {{ ref('int_trail_lines__coded_domains') }}
),

-- The A.T.'s two sources, as their staging models land them. The centerline
-- has no blaze field, so it has no raw value.
at_rows as (
    select
        trail_segment_key,
        'centerline' as source_key,
        cast(null as varchar) as raw_text
    from {{ ref('stg_atc__centerline_segments') }}
    union all
    select
        trail_segment_key,
        'side_trails' as source_key,
        cast(blaze as varchar) as raw_text
    from {{ ref('stg_atc__side_trails') }}
),

-- The decode compares a raw value with a domain's codes as text, where
-- normalize_blaze_color()'s `raw_value in coded_domain` compares them typed.
-- They agree on side_trails: its Blaze field is esriFieldTypeString with
-- codes '0' to '9' (tl-at, 2026-10-02, read from the live layer's domain),
-- so both sides are strings. They would part only on a future
-- integer-coded field whose values landed as text, where the Python's
-- '5' in {5: ...} misses and this join's '5' = '5' matches.
at_decoded as (
    select
        at_rows.trail_segment_key,
        at_rows.source_key,
        case
            when at_rows.raw_text is null
                then coalesce(line_sources.blaze_default, 'Unknown')
            when domain_code.label is not null then domain_code.label
            else 'Unknown'
        end as decoded_color,
        case
            when at_rows.raw_text is null
                then line_sources.blaze_default is not null
            else domain_code.label is not null
        end as blaze_decoded
    from at_rows
    inner join line_sources on at_rows.source_key = line_sources.source_key
    left join coded_domains as domain_code
        on
            at_rows.source_key = domain_code.source_key
            and line_sources.blaze_field = domain_code.field_name
            and at_rows.raw_text = cast(domain_code.code as varchar)
),

at_blazes as (
    select
        at_decoded.trail_segment_key,
        at_decoded.source_key,
        case
            when
                not at_decoded.blaze_decoded
                or source_tables.source_key is null
                then at_decoded.decoded_color
            when mapped_values.palette_member is not null
                then mapped_values.palette_member
            else 'Unknown'
        end as blaze_color,
        at_decoded.blaze_decoded,
        case
            when
                not at_decoded.blaze_decoded
                or source_tables.source_key is null
                then null
            when mapped_values.palette_member is not null then 'mapped'
            when deferred_values.raw_value is not null then 'deferred'
            else 'unmapped'
        end as blaze_disposition
    from at_decoded
    left join source_tables
        on at_decoded.source_key = source_tables.source_key
    left join mapped_values
        on
            at_decoded.source_key = mapped_values.source_key
            and at_decoded.decoded_color = mapped_values.raw_value
    left join deferred_values
        on
            at_decoded.source_key = deferred_values.source_key
            and at_decoded.decoded_color = deferred_values.raw_value
),

network_sources as (
    select * from {{ ref('int_trail_lines__network_sources') }}
),

-- The network's rows with their blaze field's raw JSON value, read by the
-- column dlt landed the field under.
network_raw as (
    select
        unioned.trail_segment_key,
        unioned.source_key,
        network_sources.blaze_field,
        network_sources.blaze_default,
        json_extract(
            unioned.properties, '$.' || network_sources.blaze_column
        ) as raw_value
    from {{ ref('int_trail_lines__network_unioned') }} as unioned
    inner join network_sources
        on unioned.source_key = network_sources.source_key
),

network_values as (
    select
        trail_segment_key,
        source_key,
        blaze_field,
        blaze_default,
        case
            when json_type(raw_value) = 'VARCHAR'
                then json_extract_string(raw_value, '$')
        end as raw_text,
        coalesce(json_type(raw_value), 'NULL') = 'NULL' as is_absent
    from network_raw
),

network_blazes as (
    select
        network_values.trail_segment_key,
        network_values.source_key,
        case
            when network_values.blaze_field is null
                then coalesce(network_values.blaze_default, 'Unknown')
            when network_values.is_absent then 'Unknown'
            when mapped_values.palette_member is not null
                then mapped_values.palette_member
            else 'Unknown'
        end as blaze_color,
        true as blaze_decoded,
        case
            when network_values.blaze_field is null then null
            when network_values.is_absent then 'absent'
            when mapped_values.palette_member is not null then 'mapped'
            when {{ python_strip('network_values.raw_text') }} = ''
                then 'absent'
            when deferred_values.raw_value is not null then 'deferred'
            else 'unmapped'
        end as blaze_disposition
    from network_values
    left join mapped_values
        on
            network_values.source_key = mapped_values.source_key
            and network_values.raw_text = mapped_values.raw_value
    left join deferred_values
        on
            network_values.source_key = deferred_values.source_key
            and network_values.raw_text = deferred_values.raw_value
)

select * from at_blazes
union all by name
select * from network_blazes
