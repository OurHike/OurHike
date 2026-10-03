-- reference/poi_identity.json (_shared/ourhike/poi_identity.py): every POI
-- ever published, retired ones included, keyed (decision 40), with nothing
-- filtered and nothing joined.
--
-- Key: poi_id, the ledger's map key, unique by construction.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__poi_identity') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/poi_identity.json'",
            'poi_id',
        ]) }} as poi_identity_key,
        poi_id,
        name,
        poi_type,
        source,
        source_feature_id,
        stream_id,
        lat as latitude,
        lon as longitude,
        first_seen,
        retired,
        superseded_by,
        cast(history as json) as history,
        cast(fingerprint as json) as fingerprint,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_identity_key', order_by='_dlt_id'
) }}
