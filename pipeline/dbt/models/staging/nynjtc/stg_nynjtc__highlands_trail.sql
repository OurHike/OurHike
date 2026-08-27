-- The Highlands Trail's sections. Same shape and scope as
-- stg_nynjtc__long_path; read that model for why there is no id column.
--
-- 12 section features, measured live 2026-08-24. The measured field list is
-- Trail_Name/Section_Name/Source/MapOrder and that is all four of them.
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
    select * from {{ source('nynjtc', 'raw_nynjtc__nynjtc_highlands_trail') }}
)

select
    trail_name,
    section_name,
    source as published_by,
    maporder as map_order,
    _loaded_at as loaded_at
from layer
