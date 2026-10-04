{{ config(materialized='table') }}
-- The parks and towns of the clubs' registered places layers (decision 54's
-- wave 1, int_places__unioned) that places.json lists, one row per place,
-- before anything is measured: int_places__resolved measures each as it
-- measures NY Parks' parks and the waypoint towns, and the places mart lists
-- them beside those.
--
-- WHICH LAYERS. Only a layer whose sources.json row gives a `place_kind`,
-- `park` or `town` (the places worker's read of each layer, 2026-10-03), and
-- only where int_sources__publication lets the layer publish. The filter
-- comes FIRST, before any geometry is touched, because a held layer can be
-- vast (GNIS's 176,566 populated places, MassGIS's 61,486 open-space
-- parcels) and measuring it only to drop it would cost the monthly lane its
-- hours. A layer whose places need a row filter the registry names but no
-- rule applies yet (MassGIS's PUB_ACCESS, BLM's FET_TYPE) stays held by its
-- row's `reaches_hikers`, which says so.
--
-- ONE ROW A PLACE. The id is `<source key>:<the row's key>`, its base
-- model's surrogate key, so it is stable while the layer's measured key is
-- and never minted from a position (a hiker keeps a place as their home). A
-- row with no name, or no geometry, is not a place. A park keeps its
-- polygon (ST_MakeValid, as NY Parks' park units are made valid), and a
-- town is its geometry's centroid, which is the point itself for a point
-- layer. `category` is the layer's own `category_field` value where its row
-- names one, on a park only. A polygon ST_MakeValid has to split keeps its
-- pieces as a collection, which every measurement below reads as a shape.
-- `state` is the postal code the layer's organization declares, as every
-- other place's is, and absent where none does: never guessed from the
-- shape.
--
-- Geometry is WKT text, as the other places intermediates carry it.
with unioned as (
    select * from {{ ref('int_places__unioned') }}
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

layers as (
    select
        registry.source_key,
        registry.provider,
        json_extract_string(registry.entry, '$.place_kind') as kind
    from registry
    inner join publication on registry.source_key = publication.source_key
    where
        publication.may_publish
        and json_extract_string(registry.entry, '$.place_kind')
        in ('park', 'town')
),

states as (
    select
        provider,
        max(org_state) as state
    from organizations
    where coalesce(org_state, '') != ''
    group by provider
),

places as (
    select
        unioned.source_key || ':' || unioned.place_key as place_id,
        layers.kind,
        nullif(trim(unioned.name), '') as name,
        case
            when layers.kind = 'park' then nullif(trim(unioned.category), '')
        end as category,
        states.state,
        case
            when layers.kind = 'park' then st_makevalid(unioned.geom)
            else st_centroid(unioned.geom)
        end as place_geom,
        unioned.source_key,
        unioned.club,
        unioned._loaded_at
    from unioned
    inner join layers on unioned.source_key = layers.source_key
    left join states on layers.provider = states.provider
    where unioned.geom is not null and not st_isempty(unioned.geom)
)

select
    place_id,
    kind,
    name,
    category,
    state,
    st_astext(place_geom) as geom_wkt,
    source_key,
    club,
    _loaded_at
from places
where
    name is not null
    and place_geom is not null
    and not st_isempty(place_geom)
    and (
        kind = 'town'
        or st_geometrytype(place_geom)
        in ('POLYGON', 'MULTIPOLYGON', 'GEOMETRYCOLLECTION')
    )
