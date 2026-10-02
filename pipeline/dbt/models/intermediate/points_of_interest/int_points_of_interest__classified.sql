{{ config(materialized='table') }}
-- What each unioned row is: its poi_type, the id and name it publishes
-- under, its point, and, where it does not ship, the first reason why
-- (`drop_reason`, null on a row that goes on to
-- int_points_of_interest__publishable). One row per unioned row.
--
-- THE A.T. FAMILY, export_poi.py's unify_all_sources() (PO01, PO02, PO04):
-- ATC's six layers are typed whole by the poi_type_mapping seed's `atc`
-- rows, five at high confidence and the Communities at low (a town is a
-- proxy for resupply). opentrail's `icon` is typed by the seed's `opentrail`
-- rows: `w` is water at high, `s` water at low, and every other icon
-- publishes nothing. The two derived layers, OSM water and
-- fetch_trail_water.py's site water (`nhd_stream`), are water at low
-- confidence whole, as the poi_sources seed's own columns say
-- (export_poi.py's OSM_WATER_FIELD_MAP and load_trail_water()). The Long
-- Path guide's rows are records lib/nynjtc_long_path_guide.py's
-- build_records() already made (the seed's `unified`), so their type,
-- confidence, id and name are read as they stand, as export_nearby_poi.py
-- appends them. A row with no geometry is skipped, as has_geometry()
-- skips it; one whose geometry is not a point fails the build at this
-- model's test, as unify_poi() raises, because that is a wiring mistake
-- rather than a gap upstream.
--
-- THE OTHER ORGANIZATIONS, export_nearby_poi.py's build_records() and
-- classify() (PO30, PO31, PO32, PO37): a layer that declares a `poi_type` in
-- sources.json is typed whole by it; the three it types row by row
-- (TYPED_LAYERS) read one field each through the poi_value_types seed,
-- case-folded and stripped, and a value that maps to nothing is dropped with
-- the poi_named_exclusions seed's reason where it has one. A row that is not
-- a point with two coordinates is dropped, and a name or asset that is one
-- of DEC's null sentinels (var `poi_null_sentinels`) is no name.
--
-- The ids are `{source}:{the id field's value}`, the unified id
-- lib/poi_schema.py's unify_poi() mints (PO04): the A.T. family's id field is
-- the poi_sources seed's, from export_poi.py's field maps, and the other
-- organizations' is their sources.json id_field, OBJECTID where none is
-- declared, as export_nearby_poi.py reads it. dlt lowercases every field
-- name; Socrata's `:id` lands as `_socrata_id`.
with unioned as (
    select * from {{ ref('int_points_of_interest__unioned') }}
),

sources as (
    select * from {{ ref('poi_sources') }}
),

registry as (
    select
        source_key,
        entry
    from {{ ref('stg_registry__sources') }}
),

type_codes as (
    select * from {{ ref('poi_type_mapping') }}
),

value_types as (
    select * from {{ ref('poi_value_types') }}
),

named_exclusions as (
    select * from {{ ref('poi_named_exclusions') }}
),

fields as (
    -- The field each rule reads, per row, as the JSON member dlt landed
    -- it under.
    select
        unioned.*,
        sources.file_order,
        sources.club,
        sources.source,
        sources.phone_files,
        sources.trail_id,
        registry.entry,
        coalesce(
            sources.id_field,
            json_extract_string(registry.entry, '$.id_field'),
            'OBJECTID'
        ) as id_field,
        coalesce(
            sources.name_field,
            json_extract_string(registry.entry, '$.name_field'),
            'NAME'
        ) as name_field,
        sources.type_field,
        sources.poi_type as layer_poi_type,
        sources.confidence as layer_confidence,
        coalesce(sources.unified, false) as is_unified,
        json_extract_string(registry.entry, '$.poi_type') as declared_poi_type,
        json_extract_string(registry.entry, '$.asset_field') as asset_field,
        json_extract_string(registry.entry, '$.facility_field')
            as facility_field
    from unioned
    inner join sources on unioned.source_key = sources.source_key
    left join registry on unioned.source_key = registry.source_key
),

read as (
    select
        fields.*,
        -- unify_poi(): the id field's value, else the feature's own top-level
        -- id, which the GeoJSON extract kind lands as `feature_id`.
        case
            when
                json_extract_string(
                    fields.properties,
                    '$.' || {{ poi_field_member('fields.id_field') }}
                ) is not null
                then
                    json_extract(
                        fields.properties,
                        '$.' || {{ poi_field_member('fields.id_field') }}
                    )
            else json_extract(fields.properties, '$.feature_id')
        end as source_feature_id_json,
        json_extract_string(
            fields.properties,
            '$.' || {{ poi_field_member('fields.name_field') }}
        ) as raw_name,
        coalesce(
            json_extract_string(
                fields.properties,
                '$.' || {{ poi_field_member('fields.type_field') }}
            ),
            ''
        ) as type_value,
        json_extract_string(
            fields.properties,
            '$.' || {{ poi_field_member('fields.asset_field') }}
        ) as raw_asset,
        json_extract_string(
            fields.properties,
            '$.' || {{ poi_field_member('fields.facility_field') }}
        ) as raw_facility,
        st_geometrytype(fields.geom) = 'POINT'
        and not st_isempty(fields.geom) as is_point
    from fields
),

typed as (
    select
        read.*,
        {{ python_strip('read.type_value') }} as type_value_stripped,
        case
            when read.is_unified
                then json_extract_string(read.properties, '$.poi_type')
            when read.layer_poi_type is not null then read.layer_poi_type
            when
                read.phone_files = 'poi_by_type'
                and read.source_key = 'opentrail_at'
                then icon.poi_type
            when read.phone_files = 'poi_by_type' then layer.poi_type
            when read.declared_poi_type is not null then read.declared_poi_type
            else valued.poi_type
        end as poi_type,
        case
            when read.is_unified
                then json_extract_string(read.properties, '$.confidence')
            when read.layer_confidence is not null then read.layer_confidence
            when
                read.phone_files = 'poi_by_type'
                and read.source_key = 'opentrail_at'
                then icon.confidence
            when read.phone_files = 'poi_by_type' then layer.confidence
        end as family_confidence
    from read
    left join type_codes as layer
        on
            layer.source_system = 'atc'
            and read.source_key = layer.code
    left join type_codes as icon
        on
            icon.source_system = 'opentrail'
            and json_extract_string(read.properties, '$.icon') = icon.code
    left join value_types as valued
        on
            read.source_key = valued.source_key
            and lower({{ python_strip('read.type_value') }})
            = lower(valued.value)
),

cleaned as (
    -- export_nearby_poi.py's clean(): one of the organization's own strings,
    -- or null where what arrived was a sentinel. export_poi.py publishes the
    -- A.T. family's names as ATC and opentrail wrote them.
    select
        typed.*,
        case
            when typed.phone_files = 'poi_by_type' or typed.is_unified
                then typed.raw_name
            when
                {{ python_strip('coalesce(typed.raw_name, \'\')') }} = ''
                then null
            when
                list_contains(
                    {{ var('poi_null_sentinels') }},
                    upper({{ python_strip('typed.raw_name') }})
                )
                then null
            else {{ python_strip('typed.raw_name') }}
        end as poi_name,
        case
            when
                {{ python_strip('coalesce(typed.raw_asset, \'\')') }} = ''
                then null
            when
                list_contains(
                    {{ var('poi_null_sentinels') }},
                    upper({{ python_strip('typed.raw_asset') }})
                )
                then null
            else {{ python_strip('typed.raw_asset') }}
        end as asset,
        case
            when
                {{ python_strip('coalesce(typed.raw_facility, \'\')') }} = ''
                then null
            when
                list_contains(
                    {{ var('poi_null_sentinels') }},
                    upper({{ python_strip('typed.raw_facility') }})
                )
                then null
            else {{ python_strip('typed.raw_facility') }}
        end as facility
    from typed
)

select
    cleaned.poi_key,
    cleaned.source_key,
    cleaned.file_order,
    cleaned.source_row,
    cleaned.club,
    cleaned.source,
    cleaned.phone_files,
    cleaned.trail_id,
    json_extract_string(cleaned.source_feature_id_json, '$')
        as source_feature_id,
    cleaned.source_feature_id_json,
    case
        -- A unified record carries the id its own step minted (the guide's
        -- includes the type, as one entry can be two places).
        when cleaned.is_unified
            then json_extract_string(cleaned.properties, '$.id')
        else
            cleaned.source
            || ':'
            || json_extract_string(cleaned.source_feature_id_json, '$')
    end as derived_id,
    cleaned.poi_name as name,
    cleaned.poi_type,
    cleaned.family_confidence,
    cleaned.asset,
    cleaned.facility,
    case when cleaned.is_point then st_x(cleaned.geom) end as lon,
    case when cleaned.is_point then st_y(cleaned.geom) end as lat,
    cast(st_geometrytype(cleaned.geom) as varchar) as geometry_type,
    coalesce(cleaned.is_point, false) as is_point,
    cleaned.properties,
    cleaned.entry as registry_entry,
    case
        -- unify_all_sources() reads opentrail's icon before it asks
        -- has_geometry(), so an icon that publishes nothing is skipped
        -- uncounted whether or not the row has a geometry
        -- (export_poi.py:1079-1092).
        when cleaned.source_key = 'opentrail_at' and cleaned.poi_type is null
            then 'icon not published'
        -- has_geometry(): the A.T. family skips a row with none at all.
        when cleaned.phone_files = 'poi_by_type' and cleaned.geom is null
            then 'no geometry'
        -- build_records(): not a point with two coordinates.
        when
            cleaned.phone_files = 'nearby_poi'
            and not coalesce(cleaned.is_point, false)
            then 'no usable point geometry'
        when cleaned.poi_type is null and exclusion.reason is not null
            then
                'excluded: '
                || cleaned.type_value_stripped
                || ' - '
                || exclusion.reason
        when cleaned.poi_type is null
            then 'not a published POI type'
    end as drop_reason,
    cleaned._loaded_at
from cleaned
left join named_exclusions as exclusion
    on lower(cleaned.type_value_stripped) = lower(exclusion.value)
