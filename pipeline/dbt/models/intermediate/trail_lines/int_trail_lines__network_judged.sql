{{ config(materialized='table') }}
-- Every network row, judged as export_nearby_trails.py's build_records()
-- judges a fetched feature. A row ships where `dropped_because` is null;
-- otherwise that column gives keep_reason()'s words, so no row is dropped
-- without a reason.
--
-- The tests, in order (the `reasoned` CTE); the first to fail names the
-- drop: no geometry (TL04), outside the named boundary (TL13), not a foot
-- trail (TL06), excluded use (TL07), status not shipped (TL10), route owned
-- by another source (TL11), unsupported geometry. Values match as text
-- only, as the Python compares JSON values with the registry's strings: a
-- number never reads as "1".
--
-- TL13 needs INSIDE_BOUNDARY_MIN_FRACTION (0.8) of the line's length inside
-- the named park polygons, in degrees as inside_boundary() measures it. 0.8
-- is @unvalidated in the Python's own comment, which names what would
-- settle it: a real drive between 0.8 and 1.0.
--
-- `trail_line_id` is `{source_key}:{id}` (TL05, lib/feature_id.py): the
-- first non-null of GlobalID, OBJECTID and Socrata's `_socrata_id`, else
-- `generated-<n>` (`layer_position` below), else the row's staging key. The
-- Python reads `GlobalID` in exactly that case and then the GeoJSON
-- feature's `id`, which is not landed; dlt lowercases every column, so case
-- cannot be matched here. That an ArcGIS feature's `id` always equals its
-- OBJECTID is Reasoned from the REST API's GeoJSON output and @unvalidated:
-- one live fetch comparing the two on each registered ArcGIS layer settles
-- it.
--
-- THE STAGING KEY, WHERE THE LAYER GIVES NO ID AND ITS ROWS NO ORDER. The
-- Python numbers such a line by its place in the fetched file, and only a
-- stg model carrying `source_row` (the two NYNJTC layers) keeps that place.
-- Every other such layer is published under decision 40's staging key, as
-- every club line is (int_trail_lines__club_published): unique in its
-- layer, and the same id for the same row in the next release, where a
-- place names another line once anything above it moves. Its last fallback
-- had been the row's rank in staging-key order, which matched no id
-- today's exporter publishes: on monthly run 30 it named another line than
-- today's on every one of cotrex_trails' 96,895 and nc_mst_trail's 327
-- (refresh-reference.yml 37772454847; both layers' object id is `FID`,
-- which neither writer reads, read from their metadata 2026-10-08).
--
-- `trail_status` (TL10) is 'open' or 'closed' from the status column, and
-- `closure_kind` 'long_term' where the steward marked a line closed. A
-- layer with no status column ships open: export_nearby_trails.py's
-- DEFAULT_STATUS, a default rather than a finding, since such a layer
-- cannot say "closed"; `trail_status_basis` records which. Temporary
-- closures are not applied here: they moved to the closures family under
-- #1152 — Move OPRHP's temporary closures onto the conditions clock, where
-- a safety layer belongs.
with unioned as (
    select * from {{ ref('int_trail_lines__network_unioned') }}
),

sources as (
    select * from {{ ref('int_trail_lines__network_sources') }}
),

registry as (
    select * from {{ ref('stg_registry__sources') }}
),

-- owned_route_names(): every entry's `owns_route_names`, the centerline's
-- included; where two entries claim one name the later in the file wins.
route_claims as (
    select
        source_key,
        file_row,
        unnest(
            cast(json_extract(entry, '$.owns_route_names') as varchar[])
        ) as route_name
    from registry
),

owned_routes as (
    select
        route_name,
        source_key as owner_key
    from route_claims
    qualify
        row_number() over (partition by route_name order by file_row desc) = 1
),

-- The boundary each entry names: the union of its `boundary_source` layer's
-- polygons whose `signname` is in its `boundary_names` (all, where it names
-- none). nyc_park_polygons is the only boundary layer today; an entry
-- naming another fails this model's test, as load_boundary() refuses a
-- layer that is not on disk.
boundary_polygons as (
    select
        'nyc_park_polygons' as boundary_source,
        signname,
        geom
    from {{ ref('base_nycparks__nyc_park_polygons') }}
    where geom is not null
),

boundaries as (
    select
        sources.source_key,
        st_union_agg(boundary_polygons.geom) as boundary
    from sources
    inner join boundary_polygons
        on
            sources.boundary_source = boundary_polygons.boundary_source
            and (
                sources.boundary_names is null
                or list_contains(
                    sources.boundary_names, boundary_polygons.signname
                )
            )
    group by sources.source_key
),

-- Each row with the JSON value of every field a test reads.
read_fields as (
    select
        unioned.trail_segment_key,
        unioned.source_key,
        unioned.club,
        coalesce(
            json_extract_string(unioned.properties, '$.globalid'),
            json_extract_string(unioned.properties, '$.objectid'),
            json_extract_string(unioned.properties, '$._socrata_id')
        ) as upstream_id,
        unioned.geom,
        unioned._loaded_at,
        unioned.properties,
        sources.file_row,
        sources.may_publish,
        sources.duplicate_of,
        sources.foot_field,
        sources.foot_allowed,
        sources.status_field,
        sources.name_constant,
        sources.name_placeholders,
        sources.boundary_source,
        sources.excluded_when,
        sources.declared_fields,
        sources.declared_columns,
        boundaries.boundary,
        json_extract(
            unioned.properties, '$.' || sources.foot_column
        ) as foot_value,
        json_extract(
            unioned.properties, '$.' || sources.status_column
        ) as status_value,
        json_extract(
            unioned.properties, '$.' || sources.name_column
        ) as name_value,
        -- The feature's place in its layer, for `generated-<n>`, every row
        -- counted as the Python counts them: `source_row`, the raw table's
        -- order and so the fetched file's (Reasoned, stg_nynjtc__long_path),
        -- which only the two NYNJTC layers with no id field carry. Null on
        -- every other layer, whose row then takes its staging key (above).
        unioned.source_row as layer_position
    from unioned
    inner join sources on unioned.source_key = sources.source_key
    left join boundaries on unioned.source_key = boundaries.source_key
),

-- `excluded_when`, one row per (row, field) in the entry's order.
exclusion_fields as (
    select
        trail_segment_key,
        properties,
        declared_fields,
        declared_columns,
        excluded_when,
        unnest(json_keys(excluded_when)) as field_name,
        generate_subscripts(json_keys(excluded_when), 1) as field_order
    from read_fields
),

exclusions as (
    select
        trail_segment_key,
        field_name,
        field_order,
        json_extract(
            properties,
            '$.'
            || list_extract(
                declared_columns, list_position(declared_fields, field_name)
            )
        ) as field_value,
        cast(
            json_extract(excluded_when, '$."' || field_name || '"') as varchar[]
        ) as excluded_values
    from exclusion_fields
),

-- The first field, in the entry's order, whose value is one it excludes.
first_exclusion as (
    select
        trail_segment_key,
        field_name,
        field_value
    from exclusions
    where
        json_type(field_value) = 'VARCHAR'
        and list_contains(
            excluded_values, json_extract_string(field_value, '$')
        )
    qualify
        row_number() over (
            partition by trail_segment_key order by field_order
        ) = 1
),

judged as (
    select
        read_fields.*,
        first_exclusion.field_name as excluded_field,
        first_exclusion.field_value as excluded_value,
        json_extract_string(read_fields.name_value, '$') as name_text
    from read_fields
    left join first_exclusion
        on read_fields.trail_segment_key = first_exclusion.trail_segment_key
),

-- Each value a drop names, with its JSON type, so `printed` can write it as
-- keep_reason() prints it with `!r`.
value_texts as (
    select
        *,
        case
            when json_type(name_value) = 'VARCHAR'
                then {{ python_strip('name_text') }}
            else name_text
        end as stripped_name,
        coalesce(json_type(foot_value), 'NULL') as foot_type,
        json_extract_string(foot_value, '$') as foot_text,
        coalesce(json_type(excluded_value), 'NULL') as excluded_type,
        json_extract_string(excluded_value, '$') as excluded_text,
        coalesce(json_type(status_value), 'NULL') as status_type,
        json_extract_string(status_value, '$') as status_text
    from judged
),

-- A string in quotes (single, or double where it holds a single one), None
-- for null, True or False, and a number as written. Close to repr(), not
-- equal to it for a string holding both quotes or a backslash; no message
-- is published.
printed as (
    select
        *,
        case foot_type
            when 'NULL' then 'None'
            when 'BOOLEAN'
                then case when foot_text = 'true' then 'True' else 'False' end
            when 'VARCHAR'
                then
                    case
                        when contains(foot_text, '''')
                            then '"' || foot_text || '"'
                        else '''' || foot_text || ''''
                    end
            else foot_text
        end as foot_printed,
        case excluded_type
            when 'NULL' then 'None'
            when 'BOOLEAN'
                then
                    case
                        when excluded_text = 'true' then 'True' else 'False'
                    end
            when 'VARCHAR'
                then
                    case
                        when contains(excluded_text, '''')
                            then '"' || excluded_text || '"'
                        else '''' || excluded_text || ''''
                    end
            else excluded_text
        end as excluded_printed,
        case status_type
            when 'NULL' then 'None'
            when 'BOOLEAN'
                then case when status_text = 'true' then 'True' else 'False' end
            when 'VARCHAR'
                then
                    case
                        when contains(status_text, '''')
                            then '"' || status_text || '"'
                        else '''' || status_text || ''''
                    end
            else status_text
        end as status_printed
    from value_texts
),

reasoned as (
    select
        printed.*,
        owned_routes.owner_key,
        case
            when printed.geom is null or st_isempty(printed.geom)
                then 'no geometry'
            when
                printed.boundary_source is not null
                and (
                    printed.boundary is null
                    or st_length(printed.geom) = 0
                    or st_length(
                        st_intersection(printed.geom, printed.boundary)
                    )
                    / st_length(printed.geom)
                    < {{
                        var('trail_lines_network_inside_boundary_min_fraction')
                    }}
                )
                then 'outside the boundary its registry entry names'
            when
                coalesce(printed.foot_field, '') != ''
                and not (
                    json_type(printed.foot_value) = 'VARCHAR'
                    and list_contains(
                        printed.foot_allowed,
                        json_extract_string(printed.foot_value, '$')
                    )
                )
                then
                    'not a foot trail: ' || printed.foot_field
                    || '=' || printed.foot_printed
            when printed.excluded_field is not null
                then
                    'excluded use: ' || printed.excluded_field
                    || '=' || printed.excluded_printed
            when
                coalesce(printed.status_field, '') != ''
                and not (
                    json_type(printed.status_value) = 'VARCHAR'
                    and json_extract_string(printed.status_value, '$')
                    in ('Open', 'Closed')
                )
                then 'status not shipped: ' || printed.status_printed
            when
                owned_routes.owner_key is not null
                and owned_routes.owner_key != printed.source_key
                then 'route owned by ' || owned_routes.owner_key
            when
                st_geometrytype(printed.geom)
                not in ('LINESTRING', 'MULTILINESTRING')
                then 'unsupported geometry'
        end as dropped_because
    from printed
    left join owned_routes on printed.stripped_name = owned_routes.route_name
),

-- declared_name()'s placeholder test: the stripped value, lowercased, is one
-- of the entry's `name_placeholders`, stripped and lowercased. DuckDB's
-- lower() stands in for Python's casefold(); they differ only on letters
-- like ß.
named as (
    select
        *,
        stripped_name is not null
        and list_contains(
            list_transform(
                name_placeholders,
                lambda placeholder: lower({{ python_strip('placeholder') }})
            ),
            lower(stripped_name)
        ) as is_placeholder
    from reasoned
)

select
    trail_segment_key,
    source_key,
    club,
    file_row,
    may_publish,
    -- The senior source this row's entry declares itself a duplicate of
    -- (TL18), for int_trail_lines__network_deduplicated.
    duplicate_of,
    dropped_because,
    source_key || ':'
    || coalesce(
        upstream_id, 'generated-' || layer_position, trail_segment_key
    ) as trail_line_id,
    case
        when name_constant is not null then name_constant
        when is_placeholder then null
        else json_extract_string(name_value, '$')
    end as name,
    case
        when coalesce(status_field, '') = '' then 'open'
        when json_extract_string(status_value, '$') = 'Closed' then 'closed'
        else 'open'
    end as trail_status,
    case
        when coalesce(status_field, '') = ''
            then 'default_without_status_column'
        else 'stated'
    end as trail_status_basis,
    case
        when
            coalesce(status_field, '') != ''
            and json_extract_string(status_value, '$') = 'Closed'
            then 'long_term'
    end as closure_kind,
    -- load_boundary()'s two refusals: an entry naming a boundary layer that
    -- is not landed, or `boundary_names` no polygon carries. Either way
    -- every row of the source would be dropped, so the test on this column
    -- stops the build instead.
    (boundary_source is not null and boundary is null) as boundary_missing,
    -- WKT, not GEOMETRY: a dbt 2.0.6 unit test panics on a GEOMETRY column
    -- (.claude/skills/dbt/SKILL.md). DuckDB writes the shortest digits that
    -- read back as the same double, so st_geomfromtext() downstream gets
    -- every vertex back exactly.
    st_astext(geom) as geom_wkt,
    _loaded_at
from named
