{{ config(materialized='table') }}
-- The parks places.json lists, one row per park unit: export_places.py's
-- load_parks(), step for step (PL01-PL03).
--
-- PL01: no rows unless oprhp_park_polygons may publish
-- (int_sources__publication), where load_parks() reads `reaches_hikers`.
-- Measured 2026-10-02: the two agree on 64 of 64 sources in the real
-- sources.json, the check pipeline/ELT.md asks for before may_publish
-- replaces reaches_hikers here.
--
-- Columns are the registry entry's `name_field`, `id_field` and
-- `unit_field` (default Name, GlobalID, MasterAreaID: export_places.py's
-- PARK_FIELDS), read under dlt's names, so a column OPRHP renames is a
-- registry edit. A field the layer lacks reads as null.
--
-- PL03: every polygon goes through ST_MakeValid first, because
-- ST_Intersection refuses an invalid one. Measured 2026-10-02: 9 of the
-- live layer's 858 polygons fail ST_IsValid, which settles the count
-- export_places.py left @unvalidated.
--
-- PL02, one row per unit: a polygon with no name or id is not a place. A
-- polygon joins its unit, `oprhp_park_polygons:<unit>`; one without a unit
-- joins the single unit whose polygons wear its name, else stands alone as
-- `oprhp_park_polygons:<id>`. A unit takes its commonest name (ties: the
-- shortest, then code-point order) and commonest category (ties:
-- code-point order). `unit_order` is its place in load_parks()'s list,
-- which int_places__resolved uses to pick the first park holding a point,
-- as measure()'s min(idx) does.
with polygons as (
    select * from {{ ref('base_oprhp__park_polygons') }}
),

registry as (
    select * from {{ ref('stg_registry__sources') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

organizations as (
    select * from {{ ref('stg_registry__organizations') }}
),

-- The park layer's entry, only where it may publish (PL01).
entry as (
    select
        registry.source_key,
        registry.provider,
        registry.entry
    from registry
    inner join publication on registry.source_key = publication.source_key
    where
        registry.source_key = 'oprhp_park_polygons'
        and publication.may_publish
),

-- entry.get(role, default): a key the entry holds wins, even when it holds
-- null, and the default fills in only for a key it does not hold.
declared as (
    select
        'name' as field_role,
        entry.entry,
        'Name' as default_field,
        'name_field' as entry_key
    from entry
    union all
    select
        'id' as field_role,
        entry.entry,
        'GlobalID' as default_field,
        'id_field' as entry_key
    from entry
    union all
    select
        'unit' as field_role,
        entry.entry,
        'MasterAreaID' as default_field,
        'unit_field' as entry_key
    from entry
),

roles as (
    select
        field_role,
        case
            when list_contains(json_keys(entry), entry_key)
                then json_extract_string(entry, '$.' || entry_key)
            else default_field
        end as field_name
    from declared
    union all
    select
        'category' as field_role,
        'Category' as field_name
    from entry
),

-- dlt's sql_ci_v1 naming, the same steps int_trail_lines__network_sources
-- spells out and tests against dlt's own normalize_identifier.
replaced as (
    select
        field_role,
        regexp_replace(
            {{ python_strip('field_name') }}, '[^a-zA-Z0-9_]+', '_', 'g'
        ) as step
    from roles
),

prefixed as (
    select
        field_role,
        case
            when regexp_matches(step, '^[0-9]') then '_' || step else step
        end as step
    from replaced
),

named_columns as (
    select
        field_role,
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

-- One row whatever the entry says: all null when the layer may not publish.
field_columns as (
    select
        any_value(column_name) filter (where field_role = 'name')
            as name_column,
        any_value(column_name) filter (where field_role = 'id') as id_column,
        any_value(column_name) filter (where field_role = 'unit')
            as unit_column,
        any_value(column_name) filter (where field_role = 'category')
            as category_column
    from named_columns
),

-- The state every one of the provider's rows is in, where its organization
-- declares one (organization_states(): `state` on the organization, a New
-- York agency publishing New York).
park_state as (
    select organizations.org_state as state
    from entry
    inner join organizations on entry.provider = organizations.provider
    where coalesce(organizations.org_state, '') != ''
),

-- Every polygon with a geometry, its columns as one JSON object keyed by
-- dlt's names, so a field is read by the name the entry gives it. The
-- null patch drops `geom` from the object; the geometry travels beside it.
attributes as (
    select
        source_row,
        geom,
        _loaded_at,
        json_merge_patch(to_json(polygons), '{"geom": null}') as attributes
    from polygons
    where geom is not null
),

-- Numbered in the layer's order as ST_Read numbers it (`part`), each
-- declared field read as text, the way load_parks() casts it. field_columns
-- is all null when the layer may not publish, and then nothing is a place.
field_text as (
    select
        row_number() over (order by attributes.source_row) - 1 as part,
        json_extract_string(
            attributes.attributes, '$.' || field_columns.name_column
        ) as name_text,
        json_extract_string(
            attributes.attributes, '$.' || field_columns.id_column
        ) as id_text,
        json_extract_string(
            attributes.attributes, '$.' || field_columns.unit_column
        ) as unit_text,
        json_extract_string(
            attributes.attributes, '$.' || field_columns.category_column
        ) as category_text,
        attributes.geom,
        attributes._loaded_at
    from attributes
    cross join field_columns
    where field_columns.name_column is not null
),

-- Stripped to null as _clean() does, and every polygon made valid (PL03).
parts as (
    select
        part,
        nullif({{ python_strip('name_text') }}, '') as name,
        nullif({{ python_strip('id_text') }}, '') as feature_id,
        nullif({{ python_strip('unit_text') }}, '') as unit,
        nullif({{ python_strip('category_text') }}, '') as category,
        st_makevalid(geom) as geom,
        _loaded_at
    from field_text
),

places as (
    select * from parts
    where name is not null and feature_id is not null
),

unit_parts as (
    select
        'oprhp_park_polygons:' || unit as place_id,
        part,
        name,
        category,
        geom,
        _loaded_at,
        true as from_a_unit
    from places
    where unit is not null
),

-- Which unit each name is worn by, among the polygons that carry a unit.
names_on_units as (
    select
        name,
        min(place_id) as place_id,
        count(distinct place_id) as units
    from unit_parts
    group by name
),

orphan_parts as (
    select
        case
            when names_on_units.units = 1 then names_on_units.place_id
            else 'oprhp_park_polygons:' || places.feature_id
        end as place_id,
        places.part,
        places.name,
        places.category,
        places.geom,
        places._loaded_at,
        false as from_a_unit
    from places
    left join names_on_units on places.name = names_on_units.name
    where places.unit is null
),

unit_members as (
    select * from unit_parts
    union all
    select * from orphan_parts
),

names_worn as (
    select
        place_id,
        name,
        count(*) as wearing
    from unit_members
    group by place_id, name
),

unit_names as (
    select
        place_id,
        name
    from names_worn
    qualify
        row_number() over (
            partition by place_id
            order by wearing desc, length(name) asc, name asc
        ) = 1
),

categories_worn as (
    select
        place_id,
        category,
        count(*) as wearing
    from unit_members
    where category is not null
    group by place_id, category
),

unit_categories as (
    select
        place_id,
        category
    from categories_worn
    qualify
        row_number() over (
            partition by place_id order by wearing desc, category asc
        ) = 1
),

units as (
    select
        place_id,
        st_astext(st_union_agg(geom order by part)) as park_wkt,
        count(*) as polygons,
        -- A unit's place in load_parks()'s dict: its first unit-carrying
        -- polygon if it has one, else after every such unit, at its first.
        bool_or(from_a_unit) as has_unit_id,
        coalesce(min(part) filter (where from_a_unit), min(part)) as first_part,
        max(_loaded_at) as _loaded_at
    from unit_members
    group by place_id
)

select
    units.place_id,
    unit_names.name,
    unit_categories.category,
    -- One organization per provider, which stg_registry__organizations'
    -- tests hold; max() only makes the subquery a scalar.
    (select max(park_state.state) from park_state) as state,
    row_number() over (
        order by not units.has_unit_id, units.first_part
    ) - 1 as unit_order,
    units.polygons,
    units.park_wkt,
    -- pipeline/extract/nysparks/places.py claims oprhp_park_polygons.
    'nysparks' as club,
    'oprhp_park_polygons' as source_key,
    units._loaded_at
from units
inner join unit_names on units.place_id = unit_names.place_id
left join unit_categories on units.place_id = unit_categories.place_id
