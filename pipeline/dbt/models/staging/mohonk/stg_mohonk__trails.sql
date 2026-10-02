-- Mohonk Preserve's trails and carriage roads, keyed on GlobalID (decision
-- 40), with their geometry. `globalid` and `geom` are carried for
-- int_trail_lines__network_rows, which publishes these lines from stage 3 of
-- #1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
-- monthly refresh, published docs, and lighter phone downloads; until then
-- this model was attributes only, as stg_nynjtc__long_path was. `globalid`
-- is also what lib/feature_id.py builds the published `id` from, so it is
-- staged as itself and not only inside the key.
--
-- 304 polyline segments, measured live 2026-08-25 via returnCountOnly. The
-- measured field list is Name/General_Classification/Classification/Use_/
-- Blaze/Mileage/Surface/Owner/Manager, whole.
--
-- `blaze` HERE IS A GENUINE CODED FIELD, unlike the Long Path's plain string
-- and unlike the Highlands Trail's absent one - three organizations, three
-- different answers to the same question, which is the variety Phase D was
-- meant to surface. Still no accepted_values test: the values actually
-- present on the fetched 304 rows (not the domain's declared possibilities)
-- are N/A 124, Blue 61, Red 49, Other 33, Yellow 30, plus 7 rows with no
-- Blaze value at all. The literal string 'N/A' on 41% of rows is exactly the
-- dirt an accepted_values test would either bless or break on.
--
-- WHAT THIS LAYER IS NOT: it is already a filtered VIEW. Its own
-- definitionQuery keeps only General_Classification 'Carriage Road' or
-- 'Trail' AND Manager 'Mohonk Preserve', so this is Mohonk's curated public
-- extract rather than their internal dataset. `owner` and `manager` are
-- staged because they differ - 298 of 304 rows read Owner 'Mohonk Preserve'
-- and 6 read 'NYS OPRHP/PIPC' with Manager still Mohonk.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('mohonk', 'raw_mohonk__mohonk_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'mohonk_trails'",
            'globalid',
        ]) }} as trail_segment_key,
        globalid,
        name,
        general_classification,
        classification,
        use as permitted_use,
        blaze,
        mileage,
        surface,
        owner,
        manager,
        _loaded_at as loaded_at,
        geom
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='trail_segment_key'
) }}
