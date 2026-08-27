-- NYS Parks' statewide trail network, attributes only - same scope line as
-- the other line layers, and no id column for the same reason
-- (stg_nynjtc__long_path has the argument).
--
-- 16,641 polyline segments, measured 2026-08-18, and the largest single
-- layer the warehouse now holds.
--
-- TWO BLAZE COLUMNS, NOT THREE. sources.json records "up to three Blaze
-- colours plus Map_Blaze" and SPELLS only `Blaze` and `Map_Blaze`. The other
-- two are real columns on the live layer whose names nobody wrote down, so
-- they are not here: two guessed identifiers would be two staged columns
-- upstream cannot answer for. What would settle it is one field-metadata
-- read of the service.
--
-- `status` AND `public_` ARE STAGED AND NOTHING FILTERS ON THEM, which
-- matches what the fetch already does. What those two columns gate is
-- UNMEASURED - the registry says so outright and defers it to a separate
-- measurement - so the fetch takes every row rather than guessing, and this
-- model does the same. Staging them is how the question stays askable.
--
-- `unit` is OPRHP's eleven administrative regions; nothing reads it today,
-- and it is staged because it is how OPRHP's own stewards talk about where a
-- trail is.
with source as (
    select * from {{ source('oprhp', 'raw_oprhp__oprhp_trails') }}
)

select
    name,
    alt_name,
    unit,
    blaze,
    map_blaze,
    surface,
    status,
    public_ as public_flag,
    foot,
    bike,
    horse,
    xc,
    ss,
    snowmb,
    miles,
    _loaded_at as loaded_at
from source
