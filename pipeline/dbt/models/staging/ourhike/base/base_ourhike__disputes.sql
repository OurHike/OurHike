-- The places OurHike's field notes say are gone (extract/_shared/ourhike/
-- field_notes.py, export_conditions.py's PUBLIC_DISPUTES_SQL run whole),
-- keyed (decision 40): a count of accounts per place, never an account. No
-- mart reads them: conditions/disputes.json stays export_conditions.py's to
-- write (WN11), and this model is what that file's exposure names.
--
-- Key: the disputed place's POI id, the query's GROUP BY.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__disputes') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'ourhike_disputes'",
            'poi_id',
        ]) }} as ourhike_dispute_key,
        poi_id,
        accounts,
        latest_at,
        maintainer_said,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='ourhike_dispute_key', order_by='_dlt_id'
) }}
