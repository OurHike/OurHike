-- The network's line sources: one row per sources.json entry that
-- export_nearby_trails.py exports, with every field its filters read, both
-- in the registry's spelling and as the column dlt landed it under.
--
-- WHICH ENTRIES (TL01). network_line_sources(): an external organization's
-- layer (kind `external_arcgis_layer` or `socrata_geojson_layer`,
-- lib/source_registry.py's is_external_source) carrying blaze metadata, a
-- `blaze_field` or a `blaze_default` key. The same marker without an
-- external kind is an A.T. line source, which export_trails.py exports.
--
-- WHAT A FIELD IS CALLED IN THE WAREHOUSE. sources.json names each column as
-- the steward spells it (`Trail_Name`, `MARKER`, `PrimaryName`), and the
-- extract lands it under dlt's sql_ci_v1 naming (extract/_run.py). The
-- `field_columns` CTE below is that naming in SQL, step for step in dlt's
-- order; tests/test_dbt_trail_lines_network_parity.py holds the unit test's
-- answers to dlt's own normalize_identifier. Folding case has a consequence
-- the Python never had: a field the registry spells `Name` also reads a
-- column the steward spelled `NAME` (Reasoned; no registered network layer
-- carries both spellings of one name, checked against the fixtures only).
--
-- `may_publish` is int_sources__publication's, the one home of the rule
-- (pipeline/ELT.md, "Who may publish"). This model keeps every network
-- source whatever it says, because the build-stopping checks on the registry
-- (TL08, TL09) hold for a held-back source too: export_nearby_trails.py runs
-- them over every network source, shipping or not.
with registry as (
    select * from {{ ref('stg_registry__sources') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

lines as (
    select
        registry.source_key,
        registry.file_row,
        registry.kind,
        registry.steward,
        registry.attribution,
        registry.reaches_hikers,
        publication.may_publish,
        publication.publication_rule,
        registry.entry
    from registry
    inner join publication on registry.source_key = publication.source_key
    where
        registry.kind in ('external_arcgis_layer', 'socrata_geojson_layer')
        and (
            list_contains(json_keys(registry.entry), 'blaze_field')
            or list_contains(json_keys(registry.entry), 'blaze_default')
        )
),

declared as (
    select
        source_key,
        file_row,
        kind,
        steward,
        attribution,
        reaches_hikers,
        may_publish,
        publication_rule,
        json_extract_string(entry, '$.blaze_field') as blaze_field,
        json_extract_string(entry, '$.blaze_default') as blaze_default,
        json_extract_string(entry, '$.name_field') as name_field,
        json_extract_string(entry, '$.name_constant') as name_constant,
        coalesce(
            cast(json_extract(entry, '$.name_placeholders') as varchar[]), []
        ) as name_placeholders,
        json_extract_string(entry, '$.foot_field') as foot_field,
        -- FOOT_ALLOWED_DEFAULT, export_nearby_trails.py's {"Y"}: what a foot
        -- field has to read where the entry declares no set of its own.
        coalesce(
            cast(json_extract(entry, '$.foot_allowed') as varchar[]), ['Y']
        ) as foot_allowed,
        json_extract_string(entry, '$.status_field') as status_field,
        -- {field: [values]}, kept as JSON: int_trail_lines__network_judged
        -- reads each field's value list by its key.
        coalesce(
            json_extract(entry, '$.excluded_when'), json('{}')
        ) as excluded_when,
        coalesce(
            cast(json_extract(entry, '$.owns_route_names') as varchar[]), []
        ) as owns_route_names,
        json_extract_string(entry, '$.duplicate_of') as duplicate_of,
        json_extract_string(entry, '$.boundary_source') as boundary_source,
        cast(
            json_extract(entry, '$.boundary_names') as varchar[]
        ) as boundary_names
    from lines
),

-- Each field a filter reads, in missing_declared_fields()'s order: name,
-- foot, blaze and status, then the `excluded_when` keys, an empty one left
-- out. Only the fields an entry states: the "Name" default of a source with
-- no `name_field` is not one, because that source never claimed the column.
stated_lists as (
    select
        source_key,
        list_filter(
            [
                json_extract_string(entry, '$.name_field'),
                json_extract_string(entry, '$.foot_field'),
                json_extract_string(entry, '$.blaze_field'),
                json_extract_string(entry, '$.status_field')
            ]
            || coalesce(json_keys(json_extract(entry, '$.excluded_when')), []),
            lambda field: coalesce(field, '') != ''
        ) as stated_fields
    from lines
),

-- Every field name this model needs a column for: the stated ones, each once
-- at its first place (dict.fromkeys keeps first occurrences), and the name
-- field with its "Name" default, at place 0 (keep_reason and declared_name
-- both read `source.get("name_field", "Name")`).
stated as (
    select
        source_key,
        unnest(stated_fields) as field_name,
        generate_subscripts(stated_fields, 1) as field_order
    from stated_lists
),

field_names as (
    select
        source_key,
        field_name,
        min(field_order) as field_order
    from stated
    group by source_key, field_name
    union all
    select
        source_key,
        coalesce(name_field, 'Name') as field_name,
        0 as field_order
    from declared
),

-- dlt's sql_ci_v1, in its own order: strip; each run of characters outside
-- [A-Za-z0-9_] becomes one `_`; a leading digit gets a `_` before it;
-- trailing `_` go unless the whole name is `_`; runs of `_` fold into one;
-- lowercase (dlt/common/normalizers/naming/sql_cs_v1.py and sql_ci_v1.py).
replaced as (
    select
        source_key,
        field_name,
        field_order,
        regexp_replace(
            {{ python_strip('field_name') }}, '[^a-zA-Z0-9_]+', '_', 'g'
        ) as step
    from field_names
),

prefixed as (
    select
        source_key,
        field_name,
        field_order,
        case
            when regexp_matches(step, '^[0-9]') then '_' || step else step
        end as step
    from replaced
),

field_columns as (
    select
        source_key,
        field_name,
        field_order,
        lower(
            regexp_replace(
                case
                    when step = '_' then step
                    else regexp_replace(step, '_+$', '')
                end,
                '__+',
                '_',
                'g'
            )
        ) as column_name
    from prefixed
),

columns_by_source as (
    select
        source_key,
        list(field_name order by field_order) filter (
            where field_order > 0
        ) as declared_fields,
        list(column_name order by field_order) filter (
            where field_order > 0
        ) as declared_columns,
        any_value(column_name) filter (where field_order = 0) as name_column
    from field_columns
    group by source_key
),

-- Each named field's column on its own, so a reader takes a scalar.
named_columns as (
    select
        declared.source_key,
        any_value(field_columns.column_name) filter (
            where
            field_columns.field_name = declared.foot_field
            and field_columns.field_order > 0
        ) as foot_column,
        any_value(field_columns.column_name) filter (
            where
            field_columns.field_name = declared.blaze_field
            and field_columns.field_order > 0
        ) as blaze_column,
        any_value(field_columns.column_name) filter (
            where
            field_columns.field_name = declared.status_field
            and field_columns.field_order > 0
        ) as status_column
    from declared
    inner join field_columns on declared.source_key = field_columns.source_key
    group by declared.source_key
),

-- The columns each layer landed with, read off one of its rows: every row
-- of a layer is one table's row, so all carry the same keys, null or not.
-- A layer with no rows lands no list, and is not checked: an empty layer is
-- the completeness test's question (int_trail_lines__network_counts), as it
-- is fail_if_incomplete()'s in the Python.
landed as (
    select
        source_key,
        json_keys(any_value(properties)) as landed_columns
    from {{ ref('int_trail_lines__network_unioned') }}
    group by source_key
),

-- TL08, missing_declared_fields(): each field the entry declares whose
-- column the layer did not land, in declared order. Measured 2026-09-26: a
-- renamed motorized column on NH GRANIT's layer made `excluded_when` match
-- nothing, and 2,375 mi of motorized corridor shipped from a green run
-- (#1646). One difference from the Python, which asks whether any fetched
-- feature carries the key: the warehouse has a column only where the layer
-- declared one (an ArcGIS layer's field list, extract/_kinds.py's
-- column_hints) or some row had a value (a Socrata dataset, which declares
-- none). So on a Socrata layer a declared field null on every row reads as
-- missing here and stops the build, where the Python would carry on.
missing as (
    select
        field_columns.source_key,
        list(
            field_columns.field_name order by field_columns.field_order
        ) filter (
            where
            not list_contains(
                landed.landed_columns, field_columns.column_name
            )
        ) as missing_declared_fields
    from field_columns
    inner join landed on field_columns.source_key = landed.source_key
    where field_columns.field_order > 0
    group by field_columns.source_key
)

select
    declared.*,
    coalesce(columns_by_source.declared_fields, []) as declared_fields,
    coalesce(columns_by_source.declared_columns, []) as declared_columns,
    columns_by_source.name_column,
    named_columns.foot_column,
    named_columns.blaze_column,
    named_columns.status_column,
    -- TL09: `name_field` says where to read the name and `name_constant` says
    -- there is nowhere to read it, so an entry stating both has decided
    -- neither. name_constant_conflicts() stops the export on it; the test on
    -- this column stops the build.
    (
        declared.name_constant is not null and declared.name_field is not null
    ) as declares_name_twice,
    -- As JSON text, in declared order, so a unit test can hold it (a 2.0.6
    -- unit test refuses a list column it compares).
    cast(
        to_json(coalesce(missing.missing_declared_fields, []))
        as varchar
    ) as missing_declared_fields,
    -- A source both junior in one declared pair and senior in another, which
    -- deduplicate()'s pair-by-pair order would answer and
    -- int_trail_lines__network_deduplicated does not: its test stops the
    -- build on one.
    (
        declared.duplicate_of is not null
        and declared.source_key in (
            select seniors.duplicate_of from declared as seniors
            where seniors.duplicate_of is not null
        )
    ) as chains_duplicates
from declared
left join columns_by_source
    on declared.source_key = columns_by_source.source_key
left join named_columns on declared.source_key = named_columns.source_key
left join missing on declared.source_key = missing.source_key
