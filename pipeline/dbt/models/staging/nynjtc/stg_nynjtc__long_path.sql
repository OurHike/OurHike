-- The Long Path's per-segment attributes - the first trail in this warehouse
-- that is not the A.T., and the model Phase D exists to make ordinary
-- (#100). Attributes only; geometry stays in the Python spatial scripts,
-- the same scope line stg_atc__centerline_segments follows.
--
-- 43 polyline segments, measured live 2026-08-24 - the same count and the
-- same field list the survey read on 2026-08-18, so the shelf has not moved
-- under it. Trail_Name/Blaze/Maintainer/Mileage/Source/Comments/LP_Section/
-- GuideURL is that measured list, whole.
--
-- NO ID COLUMN, and this is an absence rather than an oversight. sources.json
-- records no `id_field` for this layer and no id in the measured field list,
-- so there is nothing to stage as a source_id. ST_Read does hand DuckDB an
-- `OGC_FID`, and it must not be used: that is GDAL's row number for this
-- fetch, not NYNJTC's identity for the segment, and a republished layer in a
-- different order would silently renumber every row. What would settle it is
-- one metadata read of the service's objectIdField.
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
    select * from {{ source('nynjtc', 'raw_nynjtc__nynjtc_long_path') }}
)

select
    trail_name,
    blaze,
    maintainer,
    source as published_by,
    mileage,
    lp_section,
    guideurl as guide_url,
    comments,
    _loaded_at as loaded_at
from layer
