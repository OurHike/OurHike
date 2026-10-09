-- The Long Path's segments - the first trail in this warehouse that is not
-- the A.T., and the model Phase D exists to make ordinary (#100). `geom` is
-- carried for int_trail_lines__network_unioned, which publishes these lines
-- from stage 3 of #1793 — Rebuild the data platform as dlt → dbt: seven
-- contracted marts, a monthly refresh, published docs, and lighter phone
-- downloads. Until then this model was attributes only, and the lines
-- stayed in the Python spatial scripts.
--
-- 43 polyline segments, measured live 2026-08-24 - the same count and the
-- same field list the survey read on 2026-08-18, so the shelf has not moved
-- under it. Trail_Name/Blaze/Maintainer/Mileage/Source/Comments/LP_Section/
-- GuideURL is that list. It left out two system fields the layer's metadata
-- names: FID and Shape__Length (read live 2026-10-09).
--
-- `fid` IS THE LAYER'S OBJECT ID, AND THE ID TODAY'S EXPORTER PUBLISHES.
-- The metadata names FID as the objectIdField (type esriFieldTypeOID), and
-- ArcGIS writes FID's value as each GeoJSON feature's `id`: equal on 43 of
-- 43 features, read live 2026-10-09. fetch_external_layers.py keeps that
-- `id`, and lib/feature_id.py publishes it where a layer has no GlobalID,
-- so export_nearby_trails.py calls these lines `nynjtc_long_path:<FID>`:
-- UA's release 2026-10-03-2, which it built, holds exactly the 43 live
-- FIDs (read 2026-10-09). int_trail_lines__network_judged reads `fid` from
-- this model and publishes the same id, so no line's id changes at cutover
-- (ELT.md, TL05).
--
-- FID IS NOT THE KEY. Decision 40 keys a row on current values and never
-- on an object id alone, because a reload mints object ids again. Whether
-- NYNJTC's seasonal republish in place keeps FIDs is @unvalidated: the live
-- ids run from 1 to 85 over 43 rows (2026-10-09), which reads as features
-- edited in place rather than reloaded (Reasoned, not measured). Today's
-- exporter carries the same exposure, so matching it adds none. Two reads
-- of the layer either side of a republish, compared, would settle it.
--
-- `blaze` IS NOT DECODED, and the difference from the A.T. side is the
-- point: this is a plain string with no coded domain, reading the lowercase
-- 'aqua' on all 43 rows (measured 2026-08-24), so export_nearby_trails.py
-- sends it straight to reference/blaze_mapping.json's reviewed table rather
-- than resolving a domain first. Staging keeps it verbatim.
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
    -- step_long_path_guide.py reads the lines in this order. The published
    -- id is `fid`; int_trail_lines__network_judged numbers a line by
    -- `source_row` (`generated-<n>`, lib/feature_id.py's last fallback) only
    -- where `fid` is null, which an esriFieldTypeOID field never is
    -- (Reasoned: ArcGIS gives every feature one).
    select
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nynjtc', 'raw_nynjtc__nynjtc_long_path') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nynjtc_long_path'",
            'lp_section',
            'mileage',
        ]) }} as trail_segment_key,
        -- Under its landed name: the judged model's id ladder reads `fid`.
        fid,
        trail_name,
        blaze,
        maintainer,
        source as published_by,
        mileage,
        lp_section,
        guideurl as guide_url,
        comments,
        _loaded_at as loaded_at,
        geom,
        source_row
    from layer
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='trail_segment_key'
) }}
