-- NYS Parks' statewide trail network, keyed on GlobalID (decision 40), with
-- its geometry. `globalid` and `geom` are carried for
-- int_trail_lines__network_unioned, which publishes these lines from stage 3 of
-- #1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
-- monthly refresh, published docs, and lighter phone downloads. Until then
-- this model was attributes only and the lines stayed in the Python spatial
-- scripts. `globalid` is also what lib/feature_id.py builds the published
-- `id` from, so it is staged as itself and not only inside the key.
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
-- `status` AND `public` ARE STAGED AND NOTHING FILTERS ON THEM, which
-- matches what the fetch already does. What those two columns gate is
-- UNMEASURED - the registry says so outright and defers it to a separate
-- measurement - so the fetch takes every row rather than guessing, and this
-- model does the same. Staging them is how the question stays askable.
--
-- `unit` is OPRHP's eleven administrative regions; nothing reads it today,
-- and it is staged because it is how OPRHP's own stewards talk about where a
-- trail is.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('oprhp', 'raw_nysparks__oprhp_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'oprhp_trails'",
            'globalid',
        ]) }} as trail_segment_key,
        globalid,
        name,
        alt_name,
        unit,
        blaze,
        map_blaze,
        surface,
        status,
        public as public_flag,
        foot,
        bike,
        horse,
        xc,
        ss,
        snowmb,
        miles,
        _loaded_at as loaded_at,
        geom
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='trail_segment_key'
) }}
