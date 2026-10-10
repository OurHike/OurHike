-- The Highlands Trail's sections. Same shape and scope as
-- stg_nynjtc__long_path, geometry included; read that model for what reads
-- `geom`, and for why the object id is carried and is not the key.
--
-- 12 section features, measured live 2026-08-24, with the attribute fields
-- Trail_Name/Section_Name/Source/MapOrder. The layer's metadata names two
-- system fields beside them, OBJECTID and Shape__Length (read live
-- 2026-10-09).
--
-- `objectid` IS THE LAYER'S OBJECT ID, AND THE ID TODAY'S EXPORTER
-- PUBLISHES: the metadata's objectIdField, written by ArcGIS as each GeoJSON
-- feature's `id` (equal on 12 of 12 features, read live 2026-10-09; the ids
-- run from 4 to 350). export_nearby_trails.py calls these lines
-- `nynjtc_highlands_trail:<OBJECTID>` (UA's release 2026-10-03-2, which it
-- built, holds exactly the 12 live OBJECTIDs), and
-- int_trail_lines__network_judged reads `objectid` from this model to
-- publish the same id (ELT.md, TL05).
--
-- THIS MODEL HAS NO BLAZE COLUMN BECAUSE THE LAYER PUBLISHES NO BLAZE, and
-- that is the whole reason this model is worth reading beside its sibling.
-- The Highlands Trail does wear a blaze on the ground; this pipeline has
-- read it from no source it has registered. sources.json states the absence
-- as `blaze_default: "Unknown"` rather than asserting a paint, and a staging
-- model that added `'Unknown' as blaze` would turn a stated absence into a
-- value a join could match on. Omit rather than guess, applied to a colour.
-- What would settle it: a blaze field appearing in one of the seasonal
-- republishes this service does in place.
--
-- THE CTE IS `layer`, NOT THE HOUSE `source` EVERY OTHER MODEL USES: NYNJTC
-- spells one of this layer's own columns `Source`, and `source.source` is a
-- line nobody should have to read twice. The convention bends where upstream
-- has already taken the word.
with layer as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    --
    -- `rowid` is the row's place in the raw table, which extract/_warehouse.py
    -- fills in the order the layer's pages served the features: the order
    -- fetch_external_layers.py writes the GeoJSON export_nearby_trails.py
    -- reads (Reasoned from both files, as stg_atc__centerline_segments has
    -- it; @unvalidated across a load dlt splits into more than one file).
    -- The published id is `objectid`; int_trail_lines__network_judged
    -- numbers a line by `source_row` (`generated-<n>`, lib/feature_id.py's
    -- last fallback) only where `objectid` is null, which an
    -- esriFieldTypeOID field never is (Reasoned: ArcGIS gives every feature
    -- one).
    select
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nynjtc', 'raw_nynjtc__nynjtc_highlands_trail') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nynjtc_highlands_trail'",
            'section_name',
        ]) }} as trail_segment_key,
        -- Under its landed name: the judged model's id ladder reads `objectid`.
        objectid,
        trail_name,
        section_name,
        source as published_by,
        maporder as map_order,
        _loaded_at as loaded_at,
        geom,
        source_row
    from layer
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='trail_segment_key'
) }}
